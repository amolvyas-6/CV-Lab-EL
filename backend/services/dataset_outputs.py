"""Phase 6 helpers for dataset metadata and summary files."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Iterable

from utils.constants import (
    DATASET_DIR,
    DATASET_SUMMARY_CSV_PATH,
    DEFAULT_RESOLUTION_ENHANCED_M,
    DEFAULT_RESOLUTION_NATIVE_M,
    METADATA_JSON_PATH,
    PROCESSED_TILES_DIR,
)

LOGGER = logging.getLogger("backend.dataset_outputs")


def _count_jpg_files(directory: Path) -> int:
    """Counts jpg files in a directory."""
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.iterdir() if path.suffix.lower() == ".jpg")


def _load_existing_metadata(metadata_path: Path) -> dict[str, Any]:
    """Loads metadata.json if present, otherwise returns an empty payload."""
    if not metadata_path.exists():
        return {}

    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}

    if isinstance(data, dict):
        return data
    return {}


def _iter_location_rows(locations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Converts metadata location entries to dataset summary rows."""
    rows: list[dict[str, Any]] = []

    for location in locations:
        bbox = location.get("bbox", [None, None, None, None])
        if len(bbox) != 4:
            bbox = [None, None, None, None]

        rows.append(
            {
                "name": location.get("name"),
                "date": location.get("date"),
                "tile_count": int(location.get("tile_count", 0)),
                "tile_count_sr": int(location.get("tile_count_sr", 0)),
                "candidate_count": int(location.get("candidate_count", 0)),
                "candidate_count_sr": int(location.get("candidate_count_sr", 0)),
                "min_lon": bbox[0],
                "min_lat": bbox[1],
                "max_lon": bbox[2],
                "max_lat": bbox[3],
                "tile_dir": location.get("tile_dir", ""),
                "sr_tile_dir": location.get("sr_tile_dir", ""),
                "annotations_coco": location.get("annotations_coco", ""),
                "annotations_coco_sr": location.get("annotations_coco_sr", ""),
            }
        )

    return rows


def update_dataset_metadata_and_summary(
    location_name: str,
    bbox: tuple[float, float, float, float],
    target_date: str,
    tile_dir: Path,
    sr_tile_dir: Path | None,
    tile_size: int,
    stride: int,
    ndwi_threshold: float,
    cloud_filter_pct: float,
    sr_model_path: Path,
    annotation_summary: dict[str, Any] | None = None,
    sr_annotation_summary: dict[str, Any] | None = None,
    metadata_path: Path = METADATA_JSON_PATH,
    summary_csv_path: Path = DATASET_SUMMARY_CSV_PATH,
    resolution_native_m: float = DEFAULT_RESOLUTION_NATIVE_M,
    resolution_enhanced_m: float = DEFAULT_RESOLUTION_ENHANCED_M,
) -> dict[str, Any]:
    """Creates/updates Phase 6 metadata.json and dataset_summary.csv."""
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_TILES_DIR.mkdir(parents=True, exist_ok=True)

    tile_count = _count_jpg_files(tile_dir)
    tile_count_sr = _count_jpg_files(sr_tile_dir) if sr_tile_dir is not None else 0

    location_entry = {
        "name": location_name,
        "bbox": [float(v) for v in bbox],
        "date": target_date,
        "tile_count": tile_count,
        "tile_count_sr": tile_count_sr,
        "tile_dir": str(tile_dir),
        "sr_tile_dir": str(sr_tile_dir) if sr_tile_dir is not None else "",
        "candidate_count": int((annotation_summary or {}).get("candidate_count", 0)),
        "annotations_coco": str((annotation_summary or {}).get("coco_annotations", "")),
        "ship_candidates_csv": str((annotation_summary or {}).get("candidates_csv", "")),
        "candidate_count_sr": int(
            (sr_annotation_summary or {}).get("candidate_count", 0)
        ),
        "annotations_coco_sr": str(
            (sr_annotation_summary or {}).get("coco_annotations", "")
        ),
        "ship_candidates_csv_sr": str(
            (sr_annotation_summary or {}).get("candidates_csv", "")
        ),
    }

    metadata = _load_existing_metadata(metadata_path)
    locations: list[dict[str, Any]] = list(metadata.get("locations", []))

    replaced = False
    for idx, existing in enumerate(locations):
        if (
            existing.get("name") == location_name
            and existing.get("date") == target_date
        ):
            locations[idx] = location_entry
            replaced = True
            break

    if not replaced:
        locations.append(location_entry)

    locations.sort(
        key=lambda item: (str(item.get("name", "")), str(item.get("date", "")))
    )
    for location in locations:
        location.setdefault("candidate_count", 0)
        location.setdefault("annotations_coco", "")
        location.setdefault("ship_candidates_csv", "")
        location.setdefault("candidate_count_sr", 0)
        location.setdefault("annotations_coco_sr", "")
        location.setdefault("ship_candidates_csv_sr", "")

    total_tiles = int(sum(int(item.get("tile_count", 0)) for item in locations))
    total_tiles_sr = int(sum(int(item.get("tile_count_sr", 0)) for item in locations))

    payload = {
        "project": "Ship Detection Dataset",
        "created_by": "GEE + GIS Pipeline v1.0",
        "satellite": "Sentinel-2 L2A (COPERNICUS/S2_SR_HARMONIZED)",
        "resolution_native_m": float(resolution_native_m),
        "resolution_enhanced_m": float(resolution_enhanced_m),
        "tile_size_px": int(tile_size),
        "stride_px": int(stride),
        "sr_model": sr_model_path.name,
        "annotation_source": "heuristic_bright_object_pseudo_label",
        "annotation_warning": (
            "Ship annotations are pseudo-labels and should be human-verified "
            "before scientific model training."
        ),
        "locations": locations,
        "total_tiles": total_tiles,
        "total_tiles_sr": total_tiles_sr,
        "ndwi_threshold": float(ndwi_threshold),
        "cloud_filter_pct": float(cloud_filter_pct),
    }

    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    summary_rows = _iter_location_rows(locations)
    summary_csv_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_csv_path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(
            file_obj,
            fieldnames=[
                "name",
                "date",
                "tile_count",
                "tile_count_sr",
                "candidate_count",
                "candidate_count_sr",
                "min_lon",
                "min_lat",
                "max_lon",
                "max_lat",
                "tile_dir",
                "sr_tile_dir",
                "annotations_coco",
                "annotations_coco_sr",
            ],
        )
        writer.writeheader()
        if summary_rows:
            writer.writerows(summary_rows)

    LOGGER.info(
        "Phase 6 complete. Metadata: %s | Summary: %s | total_tiles=%d",
        metadata_path,
        summary_csv_path,
        total_tiles,
    )

    return {
        "metadata_path": str(metadata_path),
        "summary_csv_path": str(summary_csv_path),
        "total_tiles": total_tiles,
        "total_tiles_sr": total_tiles_sr,
        "locations_count": len(locations),
    }
