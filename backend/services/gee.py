"""Earth Engine setup and scene export helpers (Phase 1)."""

from __future__ import annotations

import logging
import zipfile
from datetime import timedelta
from pathlib import Path
from typing import Sequence

import ee
import requests
from utils.constants import DEFAULT_BANDS, S2_COLLECTION
from utils.errors import ConfigurationError, EarthEnginePipelineError, ProcessingError
from utils.helpers import ensure_parent_dir, parse_iso_date, validate_bbox

LOGGER = logging.getLogger("backend.gee")


def initialize_earth_engine(
    project_id: str, authenticate_if_needed: bool = True
) -> None:
    """Initializes GEE once; optionally performs OAuth flow when required."""
    try:
        ee.Initialize(project=project_id)
        LOGGER.info("Earth Engine initialized for project '%s'.", project_id)
    except Exception as init_exc:
        if not authenticate_if_needed:
            raise EarthEnginePipelineError(
                "Earth Engine initialization failed and authentication is disabled."
            ) from init_exc

        LOGGER.warning(
            "Earth Engine initialize failed. Attempting interactive authentication..."
        )
        try:
            ee.Authenticate()
            ee.Initialize(project=project_id)
            LOGGER.info("Earth Engine authenticated and initialized.")
        except Exception as auth_exc:
            raise EarthEnginePipelineError(
                "Earth Engine authentication/initialization failed. "
                "Verify account access and project ID."
            ) from auth_exc


def fetch_single_scene(
    bbox: Sequence[float],
    target_date: str,
    drive_folder: str = "GEE_Ship_Dataset",
    cloud_filter_pct: float = 10.0,
    search_window_days: int = 3,
    output_path: str | Path | None = None,
    download_scene: bool = False,
    export_to_drive: bool = True,
) -> dict[str, str | int]:
    """Fetches one low-cloud Earth Engine scene by local download and/or Drive export."""
    bounds = validate_bbox(bbox)
    target = parse_iso_date(target_date)

    if cloud_filter_pct < 0 or cloud_filter_pct > 100:
        raise ConfigurationError("cloud_filter_pct must be in [0, 100].")
    if search_window_days < 0:
        raise ConfigurationError("search_window_days must be >= 0.")

    roi = ee.Geometry.Rectangle(list(bounds))
    start = target - timedelta(days=search_window_days)
    end = target + timedelta(days=search_window_days)

    collection = (
        ee.ImageCollection(S2_COLLECTION)
        .filterBounds(roi)
        .filterDate(start.isoformat(), (end + timedelta(days=1)).isoformat())
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_filter_pct))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )

    try:
        scene_count = int(collection.size().getInfo())
    except Exception as exc:
        raise EarthEnginePipelineError(
            "Failed to query scene count from Earth Engine."
        ) from exc

    if scene_count == 0:
        raise ProcessingError(
            "No Sentinel-2 scenes found for the given date window and cloud filter."
        )

    scene = ee.Image(collection.first())
    image_to_export = scene.select(list(DEFAULT_BANDS)).unmask(0).clip(roi)
    date_suffix = target.strftime("%Y%m%d")
    result: dict[str, str | int] = {"scene_candidates": scene_count}

    if download_scene:
        if output_path is None:
            raise ConfigurationError("output_path is required when download_scene=True.")
        local_path = Path(output_path)
        _download_image_to_geotiff(
            image=image_to_export,
            roi=roi,
            output_path=local_path,
            filename_prefix=f"scene_{date_suffix}",
        )
        result["download_path"] = str(local_path)
        LOGGER.info("Downloaded GEE scene directly to %s.", local_path)

    if not export_to_drive:
        return result

    try:
        task = ee.batch.Export.image.toDrive(
            image=image_to_export,
            description=f"ship_scene_{date_suffix}",
            folder=drive_folder,
            fileNamePrefix=f"scene_{date_suffix}",
            region=roi,
            scale=10,
            crs="EPSG:4326",
            maxPixels=1e9,
        )
        task.start()
    except Exception as exc:
        raise EarthEnginePipelineError(
            "Failed to create/start GEE export task."
        ) from exc

    LOGGER.info(
        "Started GEE export task '%s'. Scene candidates found: %d",
        task.id,
        scene_count,
    )
    result["task_id"] = task.id
    return result


def _download_image_to_geotiff(
    image: ee.Image,
    roi: ee.Geometry,
    output_path: Path,
    filename_prefix: str,
) -> None:
    """Downloads a clipped GEE image as a local GeoTIFF for normal-sized ROIs."""
    ensure_parent_dir(output_path)

    try:
        url = image.getDownloadURL(
            {
                "name": filename_prefix,
                "region": roi,
                "scale": 10,
                "crs": "EPSG:4326",
                "format": "GEO_TIFF",
                "filePerBand": False,
            }
        )
        response = requests.get(url, timeout=300)
        response.raise_for_status()
    except Exception as exc:
        raise EarthEnginePipelineError(
            "Failed to download scene from Earth Engine. "
            "For large ROIs, set download_scene=false and use the Drive export."
        ) from exc

    content = response.content
    if content[:2] == b"PK":
        _extract_first_tif_from_zip(content, output_path)
        return

    output_path.write_bytes(content)


def _extract_first_tif_from_zip(content: bytes, output_path: Path) -> None:
    """Handles Earth Engine responses that return a zipped GeoTIFF."""
    zip_path = output_path.with_suffix(".zip")
    zip_path.write_bytes(content)

    try:
        with zipfile.ZipFile(zip_path) as zip_file:
            tif_names = [
                name
                for name in zip_file.namelist()
                if name.lower().endswith((".tif", ".tiff"))
            ]
            if not tif_names:
                raise ProcessingError("Earth Engine ZIP did not contain a GeoTIFF.")

            with zip_file.open(tif_names[0]) as source:
                output_path.write_bytes(source.read())
    finally:
        zip_path.unlink(missing_ok=True)
