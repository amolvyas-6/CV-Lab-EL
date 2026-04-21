"""NDWI masking utilities (Phase 2)."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import rasterio
from rasterio.errors import RasterioError
from utils.errors import ProcessingError
from utils.helpers import ensure_parent_dir

LOGGER = logging.getLogger("backend.masking")


def apply_ndwi_mask(
    geotiff_path: str | Path,
    output_path: str | Path,
    ndwi_threshold: float = 0.0,
) -> float:
    """Applies NDWI mask and writes RGB water-only GeoTIFF."""
    input_path = Path(geotiff_path)
    output_tif = Path(output_path)

    if not input_path.is_file():
        raise FileNotFoundError(f"GeoTIFF file not found: {input_path}")

    ensure_parent_dir(output_tif)

    try:
        with rasterio.open(input_path) as src:
            if src.count < 4:
                raise ProcessingError(
                    f"Expected 4 bands (R,G,B,NIR), found {src.count} in {input_path}."
                )

            red = src.read(1).astype(np.float32)
            green = src.read(2).astype(np.float32)
            blue = src.read(3).astype(np.float32)
            nir = src.read(4).astype(np.float32)
            profile = src.profile
    except RasterioError as exc:
        raise ProcessingError(f"Failed reading GeoTIFF: {input_path}") from exc

    denominator = green + nir
    ndwi = np.divide(
        green - nir,
        denominator,
        out=np.zeros_like(green, dtype=np.float32),
        where=denominator != 0,
    )

    water_mask = (ndwi > ndwi_threshold).astype(np.uint8)
    red_masked = (red * water_mask).astype(np.uint16)
    green_masked = (green * water_mask).astype(np.uint16)
    blue_masked = (blue * water_mask).astype(np.uint16)

    profile.update(count=3, dtype="uint16", nodata=0)

    try:
        with rasterio.open(output_tif, "w", **profile) as dst:
            dst.write(red_masked, 1)
            dst.write(green_masked, 2)
            dst.write(blue_masked, 3)
    except RasterioError as exc:
        raise ProcessingError(f"Failed writing masked GeoTIFF: {output_tif}") from exc

    water_coverage_pct = float(water_mask.mean() * 100.0)
    LOGGER.info(
        "Phase 2 complete. Output: %s | Water coverage: %.2f%%",
        output_tif,
        water_coverage_pct,
    )
    return water_coverage_pct
