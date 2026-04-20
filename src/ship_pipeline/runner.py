"""Pipeline runner that orchestrates Phases 1 to 4."""

from __future__ import annotations

import logging
from typing import Any

from .config import RunConfig
from .constants import (
    INTERMEDIATE_DIR,
    MODELS_DIR,
    PROCESSED_TILES_DIR,
    RAW_EXPORTS_DIR,
)
from .dataset_outputs import update_dataset_metadata_and_summary
from .gee import fetch_single_scene, initialize_earth_engine
from .masking import apply_ndwi_mask
from .super_resolution import apply_super_resolution
from .tiling import tile_geotiff
from .visualize import visualize_all_steps

LOGGER = logging.getLogger("ship_pipeline.runner")


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
    """Runs local phases sequentially with robust checks and logging."""
    ensure_workspace_layout()
    result: dict[str, Any] = {}

    if config.run_fetch:
        initialize_earth_engine(config.project_id)
        task_id = fetch_single_scene(
            bbox=config.bbox,
            target_date=config.target_date,
            drive_folder=config.drive_folder,
            cloud_filter_pct=config.cloud_filter_pct,
        )
        result["phase1"] = {"task_id": task_id}
        LOGGER.info(
            "GEE export task started: %s. Download scene GeoTIFF and rerun local phases.",
            task_id,
        )
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

    if config.sr_model_path.exists():
        sr_summary = apply_super_resolution(
            input_dir=config.tile_dir,
            output_dir=config.sr_tile_dir,
            model_path=config.sr_model_path,
        )
        LOGGER.info("Super-resolution summary: %s", sr_summary)
        result["phase4"] = sr_summary
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
    )
    LOGGER.info("Phase 6 summary: %s", phase6_summary)
    result["phase6"] = phase6_summary

    if not config.skip_visualize:
        visualize_all_steps(
            scene_tif_path=config.scene_tif_path,
            masked_tif_path=config.masked_tif_path,
            tile_dir=config.tile_dir,
            sr_tile_dir=config.sr_tile_dir,
        )

    return result
