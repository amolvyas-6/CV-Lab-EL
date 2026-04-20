"""GeoTIFF tiling and quality filtering (Phases 3 and 5)."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import cv2
import numpy as np
import rasterio
from rasterio.errors import RasterioError
from rasterio.windows import Window

from .constants import TILE_INDEX_FIELDS
from .errors import ConfigurationError, ProcessingError
from .utils import to_uint8

LOGGER = logging.getLogger("ship_pipeline.tiling")


def is_valid_tile(
    tile: np.ndarray,
    black_threshold: float = 0.95,
    blur_threshold: float = 50.0,
) -> bool:
    """Quality gate: rejects mostly black or blurry tiles."""
    if tile.ndim != 3 or tile.shape[2] < 3:
        return False

    rgb = tile[:, :, :3]
    tile_u8 = to_uint8(rgb)

    black_pixels = np.sum(np.all(tile_u8 == 0, axis=2))
    total_pixels = tile_u8.shape[0] * tile_u8.shape[1]
    if total_pixels == 0:
        return False
    if black_pixels / total_pixels > black_threshold:
        return False

    # Use contrast-normalized tile for blur scoring so uint16->uint8 scaling
    # does not suppress edge energy and over-reject valid ocean tiles.
    tile_norm_u8 = cv2.normalize(rgb, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    gray = cv2.cvtColor(tile_norm_u8, cv2.COLOR_RGB2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    if blur_score < blur_threshold:
        return False

    return True


def tile_geotiff(
    masked_tif_path: str | Path,
    output_dir: str | Path,
    location_tag: str,
    tile_size: int = 256,
    stride: int = 204,
    black_threshold: float = 0.95,
    blur_threshold: float = 50.0,
) -> dict[str, int]:
    """Generates geospatial JPEG tiles and metadata CSV."""
    input_tif = Path(masked_tif_path)
    output_path = Path(output_dir)

    if not input_tif.is_file():
        raise FileNotFoundError(f"Masked GeoTIFF not found: {input_tif}")
    if tile_size <= 0 or stride <= 0:
        raise ConfigurationError("tile_size and stride must be positive integers.")

    output_path.mkdir(parents=True, exist_ok=True)

    tile_index_rows: list[dict[str, float | int | str]] = []
    tile_count = 0
    rejected_count = 0
    write_failures = 0
    total_windows = 0

    try:
        with rasterio.open(input_tif) as src:
            if src.count < 3:
                raise ProcessingError(
                    f"Expected at least 3 RGB bands, found {src.count} in {input_tif}."
                )

            width, height = src.width, src.height

            for row_off in range(0, height - tile_size + 1, stride):
                for col_off in range(0, width - tile_size + 1, stride):
                    total_windows += 1
                    window = Window(col_off, row_off, tile_size, tile_size)
                    tile_chw = src.read(indexes=(1, 2, 3), window=window)
                    tile_hwc = np.transpose(tile_chw, (1, 2, 0))

                    if not is_valid_tile(
                        tile_hwc,
                        black_threshold=black_threshold,
                        blur_threshold=blur_threshold,
                    ):
                        rejected_count += 1
                        continue

                    tile_transform = src.window_transform(window)
                    min_lon = float(tile_transform.c)
                    max_lat = float(tile_transform.f)
                    max_lon = float(min_lon + tile_size * tile_transform.a)
                    min_lat = float(max_lat + tile_size * tile_transform.e)

                    filename = f"tile_{tile_count:05d}.jpg"
                    filepath = output_path / filename

                    tile_u8 = to_uint8(tile_hwc)
                    tile_bgr = cv2.cvtColor(tile_u8, cv2.COLOR_RGB2BGR)
                    write_ok = cv2.imwrite(str(filepath), tile_bgr)
                    if not write_ok:
                        write_failures += 1
                        continue

                    tile_index_rows.append(
                        {
                            "filename": filename,
                            "location": location_tag,
                            "min_lon": min_lon,
                            "min_lat": min_lat,
                            "max_lon": max_lon,
                            "max_lat": max_lat,
                            "row_offset": row_off,
                            "col_offset": col_off,
                        }
                    )
                    tile_count += 1
    except RasterioError as exc:
        raise ProcessingError(f"Failed during tiling: {input_tif}") from exc

    csv_path = output_path / "tile_index.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(TILE_INDEX_FIELDS))
        writer.writeheader()
        if tile_index_rows:
            writer.writerows(tile_index_rows)

    summary = {
        "total_windows": total_windows,
        "tiles_saved": tile_count,
        "tiles_rejected": rejected_count,
        "write_failures": write_failures,
    }
    LOGGER.info(
        "Phase 3 complete. Output: %s | Summary: %s",
        output_path,
        summary,
    )
    return summary
