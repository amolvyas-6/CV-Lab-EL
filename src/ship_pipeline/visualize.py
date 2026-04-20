"""Visualization helpers for outputs from each pipeline phase."""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.errors import RasterioError

from .errors import ProcessingError

LOGGER = logging.getLogger("ship_pipeline.visualize")


def _read_tif_rgb_for_display(path: Path, clip_max: float = 3000.0) -> np.ndarray:
    """Reads first 3 GeoTIFF bands and normalizes image for plotting."""
    if not path.is_file():
        raise FileNotFoundError(f"GeoTIFF not found for visualization: {path}")

    try:
        with rasterio.open(path) as src:
            if src.count < 3:
                raise ProcessingError(f"Expected >=3 bands for display in {path}.")
            r = src.read(1).astype(np.float32)
            g = src.read(2).astype(np.float32)
            b = src.read(3).astype(np.float32)
    except RasterioError as exc:
        raise ProcessingError(
            f"Failed to read GeoTIFF for visualization: {path}"
        ) from exc

    rgb = np.dstack((r, g, b))
    rgb = np.clip(rgb / clip_max, 0, 1)
    return rgb


def _read_jpg_rgb(path: Path) -> np.ndarray:
    """Reads JPEG as RGB for matplotlib display."""
    if not path.is_file():
        raise FileNotFoundError(f"JPEG not found for visualization: {path}")

    image_bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise ProcessingError(f"Could not read image file: {path}")
    return cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)


def visualize_phase1_scene(scene_tif_path: str | Path) -> None:
    """Visualizes raw scene output from Phase 1."""
    scene_path = Path(scene_tif_path)
    rgb = _read_tif_rgb_for_display(scene_path)

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(rgb)
    ax.set_title("Phase 1: Raw Scene (RGB)")
    ax.axis("off")
    plt.tight_layout()
    plt.show()


def visualize_phase2_mask_comparison(
    original_tif_path: str | Path,
    masked_tif_path: str | Path,
) -> None:
    """Visualizes before/after NDWI masking side-by-side."""
    original_rgb = _read_tif_rgb_for_display(Path(original_tif_path))
    masked_rgb = _read_tif_rgb_for_display(Path(masked_tif_path))

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    axes[0].imshow(original_rgb)
    axes[0].set_title("Phase 2 Input: Original Scene")
    axes[0].axis("off")

    axes[1].imshow(masked_rgb)
    axes[1].set_title("Phase 2 Output: NDWI Masked (Water)")
    axes[1].axis("off")

    plt.tight_layout()
    plt.show()


def visualize_phase3_tiles(tile_dir: str | Path, max_tiles: int = 6) -> None:
    """Visualizes sample tile outputs from Phase 3."""
    directory = Path(tile_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"Tile directory not found: {directory}")

    tile_files = sorted(
        path for path in directory.iterdir() if path.suffix.lower() == ".jpg"
    )
    if not tile_files:
        LOGGER.warning(
            "No Phase 3 tiles found in %s. Skipping tile preview.", directory
        )
        return

    selected = tile_files[: max(1, max_tiles)]
    cols = min(3, len(selected))
    rows = int(np.ceil(len(selected) / cols))

    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows))
    axes_flat = np.atleast_1d(axes).ravel()

    for idx, img_path in enumerate(selected):
        axes_flat[idx].imshow(_read_jpg_rgb(img_path))
        axes_flat[idx].set_title(img_path.name)
        axes_flat[idx].axis("off")

    for idx in range(len(selected), len(axes_flat)):
        axes_flat[idx].axis("off")

    fig.suptitle("Phase 3 Output: Sample Tiles", fontsize=14)
    plt.tight_layout()
    plt.show()


def visualize_phase4_sr_comparison(
    tile_dir_before_sr: str | Path,
    tile_dir_after_sr: str | Path,
    sample_count: int = 3,
) -> None:
    """Visualizes side-by-side tile comparisons for Phase 4 outputs."""
    before_dir = Path(tile_dir_before_sr)
    after_dir = Path(tile_dir_after_sr)

    if not before_dir.is_dir():
        raise FileNotFoundError(f"Pre-SR tile directory not found: {before_dir}")
    if not after_dir.is_dir():
        raise FileNotFoundError(f"Post-SR tile directory not found: {after_dir}")

    before_names = {
        path.name for path in before_dir.iterdir() if path.suffix.lower() == ".jpg"
    }
    after_names = {
        path.name for path in after_dir.iterdir() if path.suffix.lower() == ".jpg"
    }
    common_names = sorted(before_names & after_names)

    if not common_names:
        LOGGER.warning(
            "No matching JPEG filenames between %s and %s. Skipping SR comparison.",
            before_dir,
            after_dir,
        )
        return

    selected_names = common_names[: max(1, sample_count)]

    fig, axes = plt.subplots(
        len(selected_names), 2, figsize=(12, 4 * len(selected_names))
    )
    axes_2d = np.atleast_2d(axes)

    for row_idx, name in enumerate(selected_names):
        before_img = _read_jpg_rgb(before_dir / name)
        after_img = _read_jpg_rgb(after_dir / name)

        axes_2d[row_idx, 0].imshow(before_img)
        axes_2d[row_idx, 0].set_title(f"Before SR: {name}")
        axes_2d[row_idx, 0].axis("off")

        axes_2d[row_idx, 1].imshow(after_img)
        axes_2d[row_idx, 1].set_title(f"After SR (x4): {name}")
        axes_2d[row_idx, 1].axis("off")

    plt.tight_layout()
    plt.show()


def visualize_all_steps(
    scene_tif_path: str | Path,
    masked_tif_path: str | Path,
    tile_dir: str | Path,
    sr_tile_dir: str | Path | None = None,
) -> None:
    """Convenience visualizer to inspect outputs phase-by-phase."""
    visualize_phase1_scene(scene_tif_path)
    visualize_phase2_mask_comparison(scene_tif_path, masked_tif_path)
    visualize_phase3_tiles(tile_dir)

    if sr_tile_dir is not None and Path(sr_tile_dir).is_dir():
        visualize_phase4_sr_comparison(tile_dir, sr_tile_dir)
