"""Utility helpers for validation, logging, and array conversion."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Sequence

import numpy as np

from .errors import ConfigurationError


def configure_logging(level: str = "INFO") -> None:
    """Configures root logging for script execution."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )


def parse_iso_date(value: str) -> date:
    """Parses YYYY-MM-DD date strings safely."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigurationError(
            f"Invalid date '{value}'. Expected format: YYYY-MM-DD."
        ) from exc


def validate_bbox(bbox: Sequence[float]) -> tuple[float, float, float, float]:
    """Validates bounding box coordinates in EPSG:4326."""
    if len(bbox) != 4:
        raise ConfigurationError(
            "Bounding box must contain exactly 4 values: "
            "[min_lon, min_lat, max_lon, max_lat]."
        )

    min_lon, min_lat, max_lon, max_lat = [float(v) for v in bbox]

    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
        raise ConfigurationError("Longitude values must be in [-180, 180].")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise ConfigurationError("Latitude values must be in [-90, 90].")
    if min_lon >= max_lon or min_lat >= max_lat:
        raise ConfigurationError("Invalid bbox: min values must be smaller than max.")

    return min_lon, min_lat, max_lon, max_lat


def ensure_parent_dir(path: Path) -> None:
    """Creates parent directory tree when absent."""
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def to_uint8(arr: np.ndarray) -> np.ndarray:
    """Safely converts arrays to uint8 for JPEG/OpenCV operations."""
    if arr.dtype == np.uint8:
        return arr
    if arr.dtype == np.uint16:
        return (arr / 256).astype(np.uint8)

    arr_f = np.nan_to_num(arr.astype(np.float32), nan=0.0, posinf=255.0, neginf=0.0)
    arr_f = np.clip(arr_f, 0, 255)
    return arr_f.astype(np.uint8)
