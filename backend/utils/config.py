"""Backend runtime configuration for the pipeline service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from utils.constants import (
    DEFAULT_BLACK_THRESHOLD,
    DEFAULT_BLUR_THRESHOLD,
    DEFAULT_CLOUD_FILTER_PCT,
    DEFAULT_DRIVE_FOLDER,
    DEFAULT_LOCATION_TAG,
    DEFAULT_MASKED_PATH,
    DEFAULT_MUMBAI_BBOX,
    DEFAULT_NDWI_THRESHOLD,
    DEFAULT_PROJECT_ID,
    DEFAULT_SCENE_PATH,
    DEFAULT_SR_MODEL_PATH,
    DEFAULT_SR_TILE_DIR,
    DEFAULT_STRIDE,
    DEFAULT_TARGET_DATE,
    DEFAULT_TILE_DIR,
    DEFAULT_TILE_SIZE,
)
from utils.helpers import parse_iso_date, validate_bbox


@dataclass(frozen=True)
class RunConfig:
    """Runtime configuration for end-to-end pipeline execution."""

    project_id: str
    bbox: tuple[float, float, float, float]
    target_date: str
    scene_tif_path: Path
    masked_tif_path: Path
    tile_dir: Path
    sr_tile_dir: Path
    sr_model_path: Path
    location_tag: str
    drive_folder: str
    cloud_filter_pct: float
    ndwi_threshold: float
    tile_size: int
    stride: int
    black_threshold: float
    blur_threshold: float
    run_fetch: bool
    fetch_only: bool


def create_run_config(
    *,
    project_id: str = DEFAULT_PROJECT_ID,
    bbox: Sequence[float] = DEFAULT_MUMBAI_BBOX,
    target_date: str = DEFAULT_TARGET_DATE,
    scene_tif_path: str | Path = DEFAULT_SCENE_PATH,
    masked_tif_path: str | Path = DEFAULT_MASKED_PATH,
    tile_dir: str | Path = DEFAULT_TILE_DIR,
    sr_tile_dir: str | Path = DEFAULT_SR_TILE_DIR,
    sr_model_path: str | Path = DEFAULT_SR_MODEL_PATH,
    location_tag: str = DEFAULT_LOCATION_TAG,
    drive_folder: str = DEFAULT_DRIVE_FOLDER,
    cloud_filter_pct: float = DEFAULT_CLOUD_FILTER_PCT,
    ndwi_threshold: float = DEFAULT_NDWI_THRESHOLD,
    tile_size: int = DEFAULT_TILE_SIZE,
    stride: int = DEFAULT_STRIDE,
    black_threshold: float = DEFAULT_BLACK_THRESHOLD,
    blur_threshold: float = DEFAULT_BLUR_THRESHOLD,
    run_fetch: bool = False,
    fetch_only: bool = False,
) -> RunConfig:
    """Creates a validated run config for backend execution."""
    return RunConfig(
        project_id=project_id,
        bbox=validate_bbox(bbox),
        target_date=parse_iso_date(target_date).isoformat(),
        scene_tif_path=Path(scene_tif_path),
        masked_tif_path=Path(masked_tif_path),
        tile_dir=Path(tile_dir),
        sr_tile_dir=Path(sr_tile_dir),
        sr_model_path=Path(sr_model_path),
        location_tag=location_tag,
        drive_folder=drive_folder,
        cloud_filter_pct=float(cloud_filter_pct),
        ndwi_threshold=float(ndwi_threshold),
        tile_size=int(tile_size),
        stride=int(stride),
        black_threshold=float(black_threshold),
        blur_threshold=float(blur_threshold),
        run_fetch=bool(run_fetch),
        fetch_only=bool(fetch_only),
    )
