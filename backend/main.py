"""FastAPI app for asynchronous extraction jobs."""

from __future__ import annotations

import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field
from services.runner import run_local_pipeline
from utils.config import create_run_config
from utils.constants import (
    DATASET_SUMMARY_CSV_PATH,
    DEFAULT_ANNOTATE_SHIPS,
    DEFAULT_BLACK_THRESHOLD,
    DEFAULT_BLUR_THRESHOLD,
    DEFAULT_CLOUD_FILTER_PCT,
    DEFAULT_DOWNLOAD_SCENE,
    DEFAULT_DRIVE_FOLDER,
    DEFAULT_NDWI_THRESHOLD,
    DEFAULT_PROJECT_ID,
    DEFAULT_SHIP_MAX_AREA_PX,
    DEFAULT_SHIP_MIN_AREA_PX,
    DEFAULT_SHIP_MIN_INTENSITY,
    DEFAULT_SHIP_THRESHOLD_PERCENTILE,
    DEFAULT_SR_MODEL_PATH,
    DEFAULT_STRIDE,
    DEFAULT_TILE_SIZE,
    INTERMEDIATE_DIR,
    METADATA_JSON_PATH,
    PROCESSED_TILES_DIR,
    RAW_EXPORTS_DIR,
)
from utils.helpers import configure_logging, parse_iso_date, validate_bbox

LOGGER = logging.getLogger("backend.api")

app = FastAPI(title="Ship Dataset API", version="1.0.0")

jobs: dict[str, dict[str, Any]] = {}
jobs_lock = Lock()


class ExtractionRequest(BaseModel):
    """Asynchronous extraction request payload."""

    bbox: list[float] = Field(
        ..., description="[min_lon, min_lat, max_lon, max_lat] in EPSG:4326"
    )
    date: str = Field(..., description="Target date in YYYY-MM-DD format")
    location_name: str = Field(..., description="Location tag, e.g. mumbai")

    project_id: str = Field(default=DEFAULT_PROJECT_ID)
    run_fetch: bool = Field(default=False)
    fetch_only: bool = Field(default=False)

    scene_path: str | None = Field(default=None)
    masked_path: str | None = Field(default=None)
    tile_dir: str | None = Field(default=None)
    sr_tile_dir: str | None = Field(default=None)
    sr_model_path: str = Field(default=str(DEFAULT_SR_MODEL_PATH))

    drive_folder: str = Field(default=DEFAULT_DRIVE_FOLDER)
    cloud_filter_pct: float = Field(default=DEFAULT_CLOUD_FILTER_PCT)
    ndwi_threshold: float = Field(default=DEFAULT_NDWI_THRESHOLD)
    tile_size: int = Field(default=DEFAULT_TILE_SIZE)
    stride: int = Field(default=DEFAULT_STRIDE)
    black_threshold: float = Field(default=DEFAULT_BLACK_THRESHOLD)
    blur_threshold: float = Field(default=DEFAULT_BLUR_THRESHOLD)
    download_scene: bool = Field(default=DEFAULT_DOWNLOAD_SCENE)
    annotate_ships: bool = Field(default=DEFAULT_ANNOTATE_SHIPS)
    ship_min_area_px: int = Field(default=DEFAULT_SHIP_MIN_AREA_PX)
    ship_max_area_px: int = Field(default=DEFAULT_SHIP_MAX_AREA_PX)
    ship_min_intensity: int = Field(default=DEFAULT_SHIP_MIN_INTENSITY)
    ship_threshold_percentile: float = Field(default=DEFAULT_SHIP_THRESHOLD_PERCENTILE)


class BatchLocation(BaseModel):
    """Named extraction location for batch jobs."""

    name: str = Field(..., description="Location tag, e.g. mumbai")
    bbox: list[float] = Field(
        ..., description="[min_lon, min_lat, max_lon, max_lat] in EPSG:4326"
    )


class BatchExtractionRequest(BaseModel):
    """Batch extraction request across many locations and dates."""

    locations: list[BatchLocation]
    dates: list[str]

    project_id: str = Field(default=DEFAULT_PROJECT_ID)
    run_fetch: bool = Field(default=False)
    fetch_only: bool = Field(default=False)
    download_scene: bool = Field(default=DEFAULT_DOWNLOAD_SCENE)

    drive_folder: str = Field(default=DEFAULT_DRIVE_FOLDER)
    cloud_filter_pct: float = Field(default=DEFAULT_CLOUD_FILTER_PCT)
    ndwi_threshold: float = Field(default=DEFAULT_NDWI_THRESHOLD)
    tile_size: int = Field(default=DEFAULT_TILE_SIZE)
    stride: int = Field(default=DEFAULT_STRIDE)
    black_threshold: float = Field(default=DEFAULT_BLACK_THRESHOLD)
    blur_threshold: float = Field(default=DEFAULT_BLUR_THRESHOLD)
    sr_model_path: str = Field(default=str(DEFAULT_SR_MODEL_PATH))
    annotate_ships: bool = Field(default=DEFAULT_ANNOTATE_SHIPS)
    ship_min_area_px: int = Field(default=DEFAULT_SHIP_MIN_AREA_PX)
    ship_max_area_px: int = Field(default=DEFAULT_SHIP_MAX_AREA_PX)
    ship_min_intensity: int = Field(default=DEFAULT_SHIP_MIN_INTENSITY)
    ship_threshold_percentile: float = Field(default=DEFAULT_SHIP_THRESHOLD_PERCENTILE)


def _now_iso() -> str:
    """Returns UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _slugify(value: str) -> str:
    """Converts location names to filesystem-safe slugs."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    slug = slug.strip("_")
    return slug or "location"


def _update_job(job_id: str, **fields: Any) -> None:
    """Thread-safe in-memory job update."""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(fields)


def _build_paths(request: ExtractionRequest) -> tuple[Path, Path, Path, Path]:
    """Builds default local paths for scene/mask/tile outputs."""
    parsed_date = parse_iso_date(request.date)
    date_tag = parsed_date.strftime("%Y%m%d")
    year_tag = parsed_date.strftime("%Y")
    location_slug = _slugify(request.location_name)

    default_scene_path = RAW_EXPORTS_DIR / f"scene_{location_slug}_{date_tag}.tif"
    legacy_scene_path = RAW_EXPORTS_DIR / f"scene_{date_tag}.tif"
    scene_path = Path(request.scene_path) if request.scene_path else default_scene_path
    if (
        request.scene_path is None
        and not default_scene_path.exists()
        and legacy_scene_path.exists()
    ):
        scene_path = legacy_scene_path
    masked_path = (
        Path(request.masked_path)
        if request.masked_path
        else INTERMEDIATE_DIR / f"masked_{location_slug}_{date_tag}.tif"
    )
    tile_dir = (
        Path(request.tile_dir)
        if request.tile_dir
        else PROCESSED_TILES_DIR / f"{location_slug}_{year_tag}"
    )
    sr_tile_dir = (
        Path(request.sr_tile_dir)
        if request.sr_tile_dir
        else PROCESSED_TILES_DIR / f"{location_slug}_{year_tag}_sr"
    )

    return scene_path, masked_path, tile_dir, sr_tile_dir


def _run_extraction_job(job_id: str, request: ExtractionRequest) -> None:
    """Background job worker for extraction requests."""
    _update_job(job_id, status="running", started_at=_now_iso())

    try:
        parse_iso_date(request.date)  # validates date format
        scene_path, masked_path, tile_dir, sr_tile_dir = _build_paths(request)

        run_config = create_run_config(
            project_id=request.project_id,
            bbox=request.bbox,
            target_date=request.date,
            scene_tif_path=scene_path,
            masked_tif_path=masked_path,
            tile_dir=tile_dir,
            sr_tile_dir=sr_tile_dir,
            sr_model_path=Path(request.sr_model_path),
            location_tag=_slugify(request.location_name),
            drive_folder=request.drive_folder,
            cloud_filter_pct=request.cloud_filter_pct,
            ndwi_threshold=request.ndwi_threshold,
            tile_size=request.tile_size,
            stride=request.stride,
            black_threshold=request.black_threshold,
            blur_threshold=request.blur_threshold,
            run_fetch=request.run_fetch,
            fetch_only=request.fetch_only,
            download_scene=request.download_scene,
            annotate_ships=request.annotate_ships,
            ship_min_area_px=request.ship_min_area_px,
            ship_max_area_px=request.ship_max_area_px,
            ship_min_intensity=request.ship_min_intensity,
            ship_threshold_percentile=request.ship_threshold_percentile,
        )

        result = run_local_pipeline(run_config)
        _update_job(job_id, status="complete", finished_at=_now_iso(), result=result)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Job %s failed", job_id)
        _update_job(job_id, status="failed", finished_at=_now_iso(), error=str(exc))


def _run_batch_job(job_id: str, request: BatchExtractionRequest) -> None:
    """Background job worker for batch extraction requests."""
    _update_job(job_id, status="running", started_at=_now_iso())

    results: list[dict[str, Any]] = []
    completed = 0
    failed = 0

    for location in request.locations:
        for target_date in request.dates:
            child_request = ExtractionRequest(
                bbox=location.bbox,
                date=target_date,
                location_name=location.name,
                project_id=request.project_id,
                run_fetch=request.run_fetch,
                fetch_only=request.fetch_only,
                download_scene=request.download_scene,
                drive_folder=request.drive_folder,
                cloud_filter_pct=request.cloud_filter_pct,
                ndwi_threshold=request.ndwi_threshold,
                tile_size=request.tile_size,
                stride=request.stride,
                black_threshold=request.black_threshold,
                blur_threshold=request.blur_threshold,
                sr_model_path=request.sr_model_path,
                annotate_ships=request.annotate_ships,
                ship_min_area_px=request.ship_min_area_px,
                ship_max_area_px=request.ship_max_area_px,
                ship_min_intensity=request.ship_min_intensity,
                ship_threshold_percentile=request.ship_threshold_percentile,
            )

            try:
                scene_path, masked_path, tile_dir, sr_tile_dir = _build_paths(
                    child_request
                )
                run_config = create_run_config(
                    project_id=child_request.project_id,
                    bbox=child_request.bbox,
                    target_date=child_request.date,
                    scene_tif_path=scene_path,
                    masked_tif_path=masked_path,
                    tile_dir=tile_dir,
                    sr_tile_dir=sr_tile_dir,
                    sr_model_path=Path(child_request.sr_model_path),
                    location_tag=_slugify(child_request.location_name),
                    drive_folder=child_request.drive_folder,
                    cloud_filter_pct=child_request.cloud_filter_pct,
                    ndwi_threshold=child_request.ndwi_threshold,
                    tile_size=child_request.tile_size,
                    stride=child_request.stride,
                    black_threshold=child_request.black_threshold,
                    blur_threshold=child_request.blur_threshold,
                    run_fetch=child_request.run_fetch,
                    fetch_only=child_request.fetch_only,
                    download_scene=child_request.download_scene,
                    annotate_ships=child_request.annotate_ships,
                    ship_min_area_px=child_request.ship_min_area_px,
                    ship_max_area_px=child_request.ship_max_area_px,
                    ship_min_intensity=child_request.ship_min_intensity,
                    ship_threshold_percentile=child_request.ship_threshold_percentile,
                )
                result = run_local_pipeline(run_config)
                completed += 1
                results.append(
                    {
                        "location": location.name,
                        "date": target_date,
                        "status": "complete",
                        "result": result,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception(
                    "Batch child failed for location=%s date=%s",
                    location.name,
                    target_date,
                )
                failed += 1
                results.append(
                    {
                        "location": location.name,
                        "date": target_date,
                        "status": "failed",
                        "error": str(exc),
                    }
                )

            _update_job(
                job_id,
                progress={
                    "completed": completed,
                    "failed": failed,
                    "total": len(request.locations) * len(request.dates),
                },
                partial_results=results,
            )

    final_status = "complete" if failed == 0 else "failed"
    _update_job(
        job_id,
        status=final_status,
        finished_at=_now_iso(),
        result={"completed": completed, "failed": failed, "items": results},
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Lightweight health endpoint."""
    return {"status": "ok"}


@app.post("/extract")
async def extract(
    request: ExtractionRequest, background_tasks: BackgroundTasks
) -> dict[str, str]:
    """Starts an asynchronous extraction pipeline job."""
    job_id = str(uuid4())

    with jobs_lock:
        jobs[job_id] = {
            "status": "queued",
            "created_at": _now_iso(),
            "location": request.location_name,
            "date": request.date,
        }

    background_tasks.add_task(_run_extraction_job, job_id, request)
    return {"job_id": job_id, "status": "queued"}


@app.post("/batch-extract")
async def batch_extract(
    request: BatchExtractionRequest, background_tasks: BackgroundTasks
) -> dict[str, str | int]:
    """Starts an asynchronous batch extraction job for many locations/dates."""
    if not request.locations:
        raise HTTPException(status_code=400, detail="At least one location is required")
    if not request.dates:
        raise HTTPException(status_code=400, detail="At least one date is required")

    for location in request.locations:
        validate_bbox(location.bbox)
    for target_date in request.dates:
        parse_iso_date(target_date)

    job_id = str(uuid4())
    total = len(request.locations) * len(request.dates)

    with jobs_lock:
        jobs[job_id] = {
            "status": "queued",
            "created_at": _now_iso(),
            "batch": True,
            "total": total,
        }

    background_tasks.add_task(_run_batch_job, job_id, request)
    return {"job_id": job_id, "status": "queued", "total": total}


@app.get("/status/{job_id}")
def status(job_id: str) -> dict[str, Any]:
    """Returns status and result/error for a submitted job."""
    with jobs_lock:
        payload = jobs.get(job_id)

    if payload is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return payload


@app.get("/jobs")
def list_jobs() -> dict[str, dict[str, Any]]:
    """Lists all in-memory jobs (course-project scope)."""
    with jobs_lock:
        return dict(jobs)


@app.get("/metadata")
def metadata() -> dict[str, Any]:
    """Returns generated dataset metadata.json."""
    if not METADATA_JSON_PATH.exists():
        raise HTTPException(status_code=404, detail="metadata.json not found")

    content = json.loads(METADATA_JSON_PATH.read_text(encoding="utf-8"))
    return {
        "path": str(METADATA_JSON_PATH),
        "content": content,
    }


@app.get("/summary")
def summary() -> dict[str, Any]:
    """Returns generated dataset_summary.csv."""
    if not DATASET_SUMMARY_CSV_PATH.exists():
        raise HTTPException(status_code=404, detail="dataset_summary.csv not found")

    with DATASET_SUMMARY_CSV_PATH.open("r", encoding="utf-8") as file_obj:
        rows = list(csv.DictReader(file_obj))

    return {
        "path": str(DATASET_SUMMARY_CSV_PATH),
        "content": rows,
    }


def run() -> int:
    """Runs API server for local development."""
    configure_logging("INFO")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    return 0


def entrypoint() -> None:
    """Console script entrypoint with process exit code propagation."""
    raise SystemExit(run())


if __name__ == "__main__":
    entrypoint()
