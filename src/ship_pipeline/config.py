"""Runtime configuration and CLI argument parsing."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

from .constants import (
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
    DEFAULT_TILE_SIZE,
    DEFAULT_TILE_DIR,
)
from .utils import parse_iso_date, validate_bbox


@dataclass(frozen=True)
class RunConfig:
    """Runtime configuration for local end-to-end execution."""

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
    skip_visualize: bool


def build_arg_parser() -> argparse.ArgumentParser:
    """Builds CLI parser for local workflow."""
    parser = argparse.ArgumentParser(
        description="Ship dataset pipeline runner (Phases 1 to 6)."
    )
    parser.add_argument(
        "--project-id",
        default=os.getenv("GEE_PROJECT_ID", DEFAULT_PROJECT_ID),
        help="Google Earth Engine project ID.",
    )
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        default=list(DEFAULT_MUMBAI_BBOX),
        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
        help="ROI bounding box in EPSG:4326.",
    )
    parser.add_argument(
        "--date",
        default=DEFAULT_TARGET_DATE,
        help="Target acquisition date in YYYY-MM-DD.",
    )
    parser.add_argument(
        "--scene-path",
        default=str(DEFAULT_SCENE_PATH),
        help="Local raw scene GeoTIFF path.",
    )
    parser.add_argument(
        "--masked-path",
        default=str(DEFAULT_MASKED_PATH),
        help="Output path for NDWI-masked GeoTIFF.",
    )
    parser.add_argument(
        "--tile-dir",
        default=str(DEFAULT_TILE_DIR),
        help="Output directory for Phase 3 tiles.",
    )
    parser.add_argument(
        "--sr-tile-dir",
        default=str(DEFAULT_SR_TILE_DIR),
        help="Output directory for Phase 4 super-resolved tiles.",
    )
    parser.add_argument(
        "--sr-model",
        default=str(DEFAULT_SR_MODEL_PATH),
        help="Path to ESPCN x4 model file.",
    )
    parser.add_argument(
        "--location-tag",
        default=DEFAULT_LOCATION_TAG,
        help="Location label written in tile_index.csv.",
    )
    parser.add_argument(
        "--drive-folder",
        default=DEFAULT_DRIVE_FOLDER,
        help="Google Drive folder name used for GEE exports.",
    )
    parser.add_argument(
        "--cloud-filter-pct",
        type=float,
        default=DEFAULT_CLOUD_FILTER_PCT,
        help="Maximum cloud percentage for Phase 1 scene selection.",
    )
    parser.add_argument(
        "--ndwi-threshold",
        type=float,
        default=DEFAULT_NDWI_THRESHOLD,
        help="NDWI threshold for water masking.",
    )
    parser.add_argument(
        "--tile-size",
        type=int,
        default=DEFAULT_TILE_SIZE,
        help="Tile size in pixels for sliding-window tiling.",
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=DEFAULT_STRIDE,
        help="Stride in pixels for sliding-window tiling.",
    )
    parser.add_argument(
        "--black-threshold",
        type=float,
        default=DEFAULT_BLACK_THRESHOLD,
        help="Maximum allowed black-pixel ratio in a valid tile.",
    )
    parser.add_argument(
        "--blur-threshold",
        type=float,
        default=DEFAULT_BLUR_THRESHOLD,
        help="Minimum Laplacian variance required for a valid tile.",
    )
    parser.add_argument(
        "--run-fetch",
        action="store_true",
        help="Run Phase 1 GEE export task before local processing.",
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Only trigger Phase 1 export and exit without local processing.",
    )
    parser.add_argument(
        "--skip-visualize",
        action="store_true",
        help="Skip all matplotlib visualizations.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level.",
    )
    return parser


def build_run_config(args: argparse.Namespace) -> RunConfig:
    """Converts argparse values to a validated runtime config."""
    return RunConfig(
        project_id=args.project_id,
        bbox=validate_bbox(args.bbox),
        target_date=parse_iso_date(args.date).isoformat(),
        scene_tif_path=Path(args.scene_path),
        masked_tif_path=Path(args.masked_path),
        tile_dir=Path(args.tile_dir),
        sr_tile_dir=Path(args.sr_tile_dir),
        sr_model_path=Path(args.sr_model),
        location_tag=args.location_tag,
        drive_folder=args.drive_folder,
        cloud_filter_pct=float(args.cloud_filter_pct),
        ndwi_threshold=float(args.ndwi_threshold),
        tile_size=int(args.tile_size),
        stride=int(args.stride),
        black_threshold=float(args.black_threshold),
        blur_threshold=float(args.blur_threshold),
        run_fetch=args.run_fetch,
        fetch_only=args.fetch_only,
        skip_visualize=args.skip_visualize,
    )
