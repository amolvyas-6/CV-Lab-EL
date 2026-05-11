"""Heuristic ship candidate and COCO annotation outputs."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

LOGGER = logging.getLogger("backend.annotations")

CANDIDATE_FIELDS = (
    "filename",
    "x",
    "y",
    "width",
    "height",
    "area_px",
    "score",
    "min_lon",
    "min_lat",
    "max_lon",
    "max_lat",
)


def generate_ship_candidate_annotations(
    tile_dir: str | Path,
    min_area_px: int = 2,
    max_area_px: int = 600,
    min_intensity: int = 130,
    threshold_percentile: float = 99.5,
) -> dict[str, Any]:
    """Writes ship_candidates.csv and COCO JSON using bright-object heuristics.

    These outputs are pseudo-labels, not human-verified ground truth.
    """
    input_dir = Path(tile_dir)
    if not input_dir.is_dir():
        raise FileNotFoundError(f"Tile directory not found: {input_dir}")

    tile_rows = _load_tile_index(input_dir / "tile_index.csv")
    image_files = sorted(path for path in input_dir.glob("*.jpg"))
    coco_images: list[dict[str, Any]] = []
    coco_annotations: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    annotation_id = 1
    for image_id, image_path in enumerate(image_files, start=1):
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            continue

        height, width = image.shape[:2]
        tile_meta = tile_rows.get(image_path.name, {})
        coco_images.append(
            {
                "id": image_id,
                "file_name": image_path.name,
                "width": width,
                "height": height,
                "geospatial_bbox": _tile_bbox(tile_meta),
                "location": tile_meta.get("location", ""),
            }
        )

        candidates = _detect_candidates(
            image,
            min_area_px=min_area_px,
            max_area_px=max_area_px,
            min_intensity=min_intensity,
            threshold_percentile=threshold_percentile,
        )
        for candidate in candidates:
            x, y, box_width, box_height = candidate["bbox"]
            geo_bbox = _candidate_geo_bbox(tile_meta, x, y, box_width, box_height, width, height)
            candidate_rows.append(
                {
                    "filename": image_path.name,
                    "x": x,
                    "y": y,
                    "width": box_width,
                    "height": box_height,
                    "area_px": candidate["area"],
                    "score": f"{candidate['score']:.4f}",
                    "min_lon": geo_bbox[0],
                    "min_lat": geo_bbox[1],
                    "max_lon": geo_bbox[2],
                    "max_lat": geo_bbox[3],
                }
            )
            coco_annotations.append(
                {
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": 1,
                    "bbox": [x, y, box_width, box_height],
                    "area": candidate["area"],
                    "iscrowd": 0,
                    "score": candidate["score"],
                    "source": "heuristic_bright_object_pseudo_label",
                    "geospatial_bbox": geo_bbox,
                }
            )
            annotation_id += 1

    candidates_csv = input_dir / "ship_candidates.csv"
    with candidates_csv.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(CANDIDATE_FIELDS))
        writer.writeheader()
        if candidate_rows:
            writer.writerows(candidate_rows)

    coco_path = input_dir / "annotations_coco.json"
    coco_payload = {
        "info": {
            "description": "Ship candidate pseudo-labels generated from Sentinel-2 water tiles",
            "annotation_source": "heuristic_bright_object_pseudo_label",
            "warning": "Pseudo-labels require human verification before scientific model training.",
        },
        "licenses": [],
        "categories": [{"id": 1, "name": "ship", "supercategory": "vessel"}],
        "images": coco_images,
        "annotations": coco_annotations,
    }
    coco_path.write_text(json.dumps(coco_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    summary = {
        "images_indexed": len(coco_images),
        "candidate_count": len(candidate_rows),
        "candidates_csv": str(candidates_csv),
        "coco_annotations": str(coco_path),
        "annotation_source": "heuristic_bright_object_pseudo_label",
    }
    LOGGER.info("Phase 5 complete. Annotation summary: %s", summary)
    return summary


def _detect_candidates(
    image_bgr: np.ndarray,
    min_area_px: int,
    max_area_px: int,
    min_intensity: int,
    threshold_percentile: float,
) -> list[dict[str, Any]]:
    """Finds compact bright blobs that may be ships or wakes."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    valid = gray[gray > 0]
    if valid.size == 0:
        return []

    percentile_threshold = float(np.percentile(valid, threshold_percentile))
    threshold = int(max(min_intensity, percentile_threshold))
    mask = np.where(gray >= threshold, 255, 0).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    candidates: list[dict[str, Any]] = []
    for component_id in range(1, component_count):
        area = int(stats[component_id, cv2.CC_STAT_AREA])
        if area < min_area_px or area > max_area_px:
            continue

        x = int(stats[component_id, cv2.CC_STAT_LEFT])
        y = int(stats[component_id, cv2.CC_STAT_TOP])
        width = int(stats[component_id, cv2.CC_STAT_WIDTH])
        height = int(stats[component_id, cv2.CC_STAT_HEIGHT])
        if width <= 0 or height <= 0:
            continue

        component_mask = labels == component_id
        score = float(gray[component_mask].mean() / 255.0)
        candidates.append(
            {
                "bbox": [x, y, width, height],
                "area": area,
                "score": score,
            }
        )

    return candidates


def _load_tile_index(index_path: Path) -> dict[str, dict[str, str]]:
    if not index_path.exists():
        return {}

    with index_path.open("r", newline="", encoding="utf-8") as csv_file:
        return {
            row["filename"]: row
            for row in csv.DictReader(csv_file)
            if row.get("filename")
        }


def _tile_bbox(tile_meta: dict[str, str]) -> list[float] | None:
    try:
        return [
            float(tile_meta["min_lon"]),
            float(tile_meta["min_lat"]),
            float(tile_meta["max_lon"]),
            float(tile_meta["max_lat"]),
        ]
    except (KeyError, TypeError, ValueError):
        return None


def _candidate_geo_bbox(
    tile_meta: dict[str, str],
    x: int,
    y: int,
    width: int,
    height: int,
    image_width: int,
    image_height: int,
) -> list[float | str]:
    tile_bbox = _tile_bbox(tile_meta)
    if tile_bbox is None:
        return ["", "", "", ""]

    min_lon, min_lat, max_lon, max_lat = tile_bbox
    lon_per_px = (max_lon - min_lon) / image_width
    lat_per_px = (max_lat - min_lat) / image_height
    box_min_lon = min_lon + x * lon_per_px
    box_max_lon = min_lon + (x + width) * lon_per_px
    box_max_lat = max_lat - y * lat_per_px
    box_min_lat = max_lat - (y + height) * lat_per_px
    return [box_min_lon, box_min_lat, box_max_lon, box_max_lat]
