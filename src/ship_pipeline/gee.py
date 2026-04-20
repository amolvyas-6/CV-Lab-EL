"""Earth Engine setup and scene export helpers (Phase 1)."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Sequence

import ee

from .constants import DEFAULT_BANDS, S2_COLLECTION
from .errors import ConfigurationError, EarthEnginePipelineError, ProcessingError
from .utils import parse_iso_date, validate_bbox

LOGGER = logging.getLogger("ship_pipeline.gee")


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
) -> str:
    """Starts an Earth Engine export task for one low-cloud scene."""
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
    return task.id
