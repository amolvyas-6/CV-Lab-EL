"""Project-wide constants and default paths."""

from pathlib import Path
from typing import Final

S2_COLLECTION: Final[str] = "COPERNICUS/S2_SR_HARMONIZED"
DEFAULT_BANDS: Final[tuple[str, ...]] = ("B4", "B3", "B2", "B8")  # R,G,B,NIR
DEFAULT_PROJECT_ID: Final[str] = "fiery-surf-477011-p0"
DEFAULT_TARGET_DATE: Final[str] = "2024-02-15"
DEFAULT_LOCATION_TAG: Final[str] = "mumbai"
DEFAULT_DRIVE_FOLDER: Final[str] = "GEE_Ship_Dataset"

DEFAULT_CLOUD_FILTER_PCT: Final[float] = 10.0
DEFAULT_NDWI_THRESHOLD: Final[float] = 0.0
DEFAULT_TILE_SIZE: Final[int] = 256
DEFAULT_STRIDE: Final[int] = 204
DEFAULT_BLACK_THRESHOLD: Final[float] = 0.95
DEFAULT_BLUR_THRESHOLD: Final[float] = 50.0

DEFAULT_RESOLUTION_NATIVE_M: Final[float] = 10.0
DEFAULT_RESOLUTION_ENHANCED_M: Final[float] = 2.5

DEFAULT_MUMBAI_BBOX: Final[tuple[float, float, float, float]] = (
    72.80,
    18.87,
    72.97,
    18.98,
)

TILE_INDEX_FIELDS: Final[tuple[str, ...]] = (
    "filename",
    "location",
    "min_lon",
    "min_lat",
    "max_lon",
    "max_lat",
    "row_offset",
    "col_offset",
)

DATASET_DIR: Final[Path] = Path("dataset")
RAW_EXPORTS_DIR: Final[Path] = DATASET_DIR / "raw_exports"
INTERMEDIATE_DIR: Final[Path] = DATASET_DIR / "intermediate"
PROCESSED_TILES_DIR: Final[Path] = DATASET_DIR / "processed_tiles"
METADATA_JSON_PATH: Final[Path] = DATASET_DIR / "metadata.json"
DATASET_SUMMARY_CSV_PATH: Final[Path] = PROCESSED_TILES_DIR / "dataset_summary.csv"

DOWNLOADS_DIR: Final[Path] = Path("downloads")
MODELS_DIR: Final[Path] = DOWNLOADS_DIR / "models"

DEFAULT_SCENE_PATH: Final[Path] = RAW_EXPORTS_DIR / "scene_20240215.tif"
DEFAULT_MASKED_PATH: Final[Path] = INTERMEDIATE_DIR / "masked_scene_20240215.tif"
DEFAULT_TILE_DIR: Final[Path] = PROCESSED_TILES_DIR / "mumbai_2024"
DEFAULT_SR_TILE_DIR: Final[Path] = PROCESSED_TILES_DIR / "mumbai_2024_sr"
DEFAULT_SR_MODEL_PATH: Final[Path] = MODELS_DIR / "ESPCN_x4.pb"
