"""OpenCV DNN super-resolution module (Phase 4)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import cv2

from .errors import ProcessingError

LOGGER = logging.getLogger("ship_pipeline.super_resolution")


def apply_super_resolution(
    input_dir: str | Path,
    output_dir: str | Path,
    model_path: str | Path,
    copy_tile_index: bool = True,
) -> dict[str, int]:
    """Applies ESPCN x4 super-resolution to JPEG tiles."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    model = Path(model_path)

    if not input_path.is_dir():
        raise FileNotFoundError(f"Input tile directory not found: {input_path}")
    if not model.is_file():
        raise FileNotFoundError(
            f"SR model not found: {model}. "
            "Download ESPCN_x4.pb and place it under downloads/models/."
        )
    if not hasattr(cv2, "dnn_superres"):
        raise ProcessingError(
            "OpenCV dnn_superres is unavailable. "
            "Install opencv-contrib-python-headless."
        )

    output_path.mkdir(parents=True, exist_ok=True)

    try:
        sr = cv2.dnn_superres.DnnSuperResImpl_create()
        sr.readModel(str(model))
        sr.setModel("espcn", 4)
    except cv2.error as exc:
        raise ProcessingError(f"Failed loading SR model: {model}") from exc

    jpg_files = sorted(
        path for path in input_path.iterdir() if path.suffix.lower() == ".jpg"
    )

    processed = 0
    skipped_unreadable = 0
    failed_write = 0
    failed_sr = 0

    for file_path in jpg_files:
        image = cv2.imread(str(file_path), cv2.IMREAD_COLOR)
        if image is None:
            skipped_unreadable += 1
            continue

        try:
            upscaled = sr.upsample(image)
        except cv2.error:
            failed_sr += 1
            continue

        out_file = output_path / file_path.name
        if not cv2.imwrite(str(out_file), upscaled):
            failed_write += 1
            continue

        processed += 1

    if copy_tile_index:
        src_index = input_path / "tile_index.csv"
        dst_index = output_path / "tile_index.csv"
        if src_index.exists():
            shutil.copy2(src_index, dst_index)

    summary = {
        "tiles_found": len(jpg_files),
        "tiles_upscaled": processed,
        "skipped_unreadable": skipped_unreadable,
        "failed_sr": failed_sr,
        "failed_write": failed_write,
    }
    LOGGER.info(
        "Phase 4 complete. Output: %s | Summary: %s",
        output_path,
        summary,
    )
    return summary
