"""Pipeline runner that orchestrates Phases 1 to 6."""

from __future__ import annotations

import logging
from typing import Any

import rasterio
from rasterio.errors import RasterioError
from services.annotations import generate_ship_candidate_annotations
from services.dataset_outputs import update_dataset_metadata_and_summary
from services.gee import fetch_single_scene, initialize_earth_engine
from services.masking import apply_ndwi_mask
from services.super_resolution import apply_super_resolution
from services.tiling import tile_geotiff
from utils.config import RunConfig
from utils.constants import (
    INTERMEDIATE_DIR,
    MODELS_DIR,
    PROCESSED_TILES_DIR,
    RAW_EXPORTS_DIR,
)
from utils.errors import ProcessingError

LOGGER = logging.getLogger("backend.runner")


def ensure_workspace_layout() -> None:
    """Creates expected local folders for downloaded and generated artifacts."""
    for directory in (
        RAW_EXPORTS_DIR,
        INTERMEDIATE_DIR,
        PROCESSED_TILES_DIR,
        MODELS_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def run_local_pipeline(config: RunConfig) -> dict[str, Any]:
    """Runs backend phases sequentially with robust checks and logging."""
    ensure_workspace_layout()
    result: dict[str, Any] = {}

    if config.run_fetch:
        initialize_earth_engine(config.project_id)
        phase1_summary = fetch_single_scene(
            bbox=config.bbox,
            target_date=config.target_date,
            drive_folder=config.drive_folder,
            cloud_filter_pct=config.cloud_filter_pct,
            output_path=config.scene_tif_path,
            download_scene=config.download_scene,
            export_to_drive=not config.download_scene,
        )
        result["phase1"] = phase1_summary
        if config.fetch_only:
            LOGGER.info("Fetch-only mode enabled. Skipping local processing phases.")
            return result

    if config.fetch_only and not config.run_fetch:
        LOGGER.warning("fetch-only was set without run-fetch. Nothing to do.")
        return {"phase1": {"skipped": True, "reason": "run-fetch not enabled"}}

    if not config.scene_tif_path.exists():
        raise FileNotFoundError(
            f"Scene GeoTIFF not found: {config.scene_tif_path}. "
            "If you just triggered fetch, wait for export completion and download the file first."
        )

    _validate_scene_matches_bbox(config.scene_tif_path, config.bbox)

    water_coverage = apply_ndwi_mask(
        geotiff_path=config.scene_tif_path,
        output_path=config.masked_tif_path,
        ndwi_threshold=config.ndwi_threshold,
    )
    LOGGER.info("Water coverage from NDWI mask: %.2f%%", water_coverage)
    result["phase2"] = {"water_coverage_pct": water_coverage}

    tiling_summary = tile_geotiff(
        masked_tif_path=config.masked_tif_path,
        output_dir=config.tile_dir,
        location_tag=config.location_tag,
        tile_size=config.tile_size,
        stride=config.stride,
        black_threshold=config.black_threshold,
        blur_threshold=config.blur_threshold,
    )
    LOGGER.info("Tiling summary: %s", tiling_summary)
    result["phase3"] = tiling_summary

    annotation_summary: dict[str, Any] | None = None
    if config.annotate_ships:
        annotation_summary = generate_ship_candidate_annotations(
            tile_dir=config.tile_dir,
            min_area_px=config.ship_min_area_px,
            max_area_px=config.ship_max_area_px,
            min_intensity=config.ship_min_intensity,
            threshold_percentile=config.ship_threshold_percentile,
        )
        result["phase5"] = annotation_summary
    else:
        result["phase5"] = {"skipped": True, "reason": "annotate_ships disabled"}

    sr_annotation_summary: dict[str, Any] | None = None
    if config.sr_model_path.exists():
        sr_summary = apply_super_resolution(
            input_dir=config.tile_dir,
            output_dir=config.sr_tile_dir,
            model_path=config.sr_model_path,
        )
        LOGGER.info("Super-resolution summary: %s", sr_summary)
        result["phase4"] = sr_summary
        if config.annotate_ships:
            sr_annotation_summary = generate_ship_candidate_annotations(
                tile_dir=config.sr_tile_dir,
                min_area_px=config.ship_min_area_px * 16,
                max_area_px=config.ship_max_area_px * 16,
                min_intensity=config.ship_min_intensity,
                threshold_percentile=config.ship_threshold_percentile,
            )
            result["phase5_sr"] = sr_annotation_summary
    else:
        LOGGER.warning("Phase 4 skipped. Model not found at %s", config.sr_model_path)
        result["phase4"] = {
            "skipped": True,
            "reason": f"Model not found at {config.sr_model_path}",
        }

    phase6_summary = update_dataset_metadata_and_summary(
        location_name=config.location_tag,
        bbox=config.bbox,
        target_date=config.target_date,
        tile_dir=config.tile_dir,
        sr_tile_dir=config.sr_tile_dir,
        tile_size=config.tile_size,
        stride=config.stride,
        ndwi_threshold=config.ndwi_threshold,
        cloud_filter_pct=config.cloud_filter_pct,
        sr_model_path=config.sr_model_path,
        annotation_summary=annotation_summary,
        sr_annotation_summary=sr_annotation_summary,
    )
    LOGGER.info("Phase 6 summary: %s", phase6_summary)
    result["phase6"] = phase6_summary

    return result


def _validate_scene_matches_bbox(
    scene_tif_path: Any,
    bbox: tuple[float, float, float, float],
    tolerance_degrees: float = 0.02,
) -> None:
    """Stops accidental reuse of a scene from another location."""
    try:
        with rasterio.open(scene_tif_path) as src:
            bounds = src.bounds
            crs = src.crs
    except RasterioError as exc:
        raise ProcessingError(f"Failed reading scene bounds: {scene_tif_path}") from exc

    if crs and crs.to_string() != "EPSG:4326":
        LOGGER.warning("Scene CRS is %s; bbox validation assumes EPSG:4326.", crs)
        return

    min_lon, min_lat, max_lon, max_lat = bbox
    covers_bbox = (
        bounds.left <= min_lon + tolerance_degrees
        and bounds.right >= max_lon - tolerance_degrees
        and bounds.bottom <= min_lat + tolerance_degrees
        and bounds.top >= max_lat - tolerance_degrees
    )
    if not covers_bbox:
        raise ProcessingError(
            "Scene GeoTIFF bounds do not match the requested bbox. "
            f"Scene bounds={tuple(bounds)}, requested bbox={bbox}. "
            "Use a location/date-specific scene_path or run_fetch=true."
        )
