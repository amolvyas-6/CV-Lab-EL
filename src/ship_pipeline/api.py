"""FastAPI app for asynchronous extraction jobs."""

from __future__ import annotations

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

from .config import RunConfig
from .constants import (
    DEFAULT_BLACK_THRESHOLD,
    DEFAULT_BLUR_THRESHOLD,
    DEFAULT_CLOUD_FILTER_PCT,
    DEFAULT_DRIVE_FOLDER,
    DEFAULT_NDWI_THRESHOLD,
    DEFAULT_PROJECT_ID,
    DEFAULT_SR_MODEL_PATH,
    DEFAULT_STRIDE,
    DEFAULT_TILE_SIZE,
    INTERMEDIATE_DIR,
    PROCESSED_TILES_DIR,
    RAW_EXPORTS_DIR,
)
from .runner import run_local_pipeline
from .utils import configure_logging, parse_iso_date, validate_bbox

LOGGER = logging.getLogger("ship_pipeline.api")

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
    skip_visualize: bool = Field(default=True)

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

    scene_path = (
        Path(request.scene_path)
        if request.scene_path
        else RAW_EXPORTS_DIR / f"scene_{date_tag}.tif"
    )
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
        bbox = validate_bbox(request.bbox)
        parse_iso_date(request.date)  # validates date format

        scene_path, masked_path, tile_dir, sr_tile_dir = _build_paths(request)

        run_config = RunConfig(
            project_id=request.project_id,
            bbox=bbox,
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
            skip_visualize=request.skip_visualize,
        )

        result = run_local_pipeline(run_config)
        _update_job(job_id, status="complete", finished_at=_now_iso(), result=result)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Job %s failed", job_id)
        _update_job(job_id, status="failed", finished_at=_now_iso(), error=str(exc))


@app.get("/health")
def health() -> dict[str, str]:
    """Lightweight health endpoint."""
    return {"status": "ok"}


@app.post("/extract")
async def extract(request: ExtractionRequest, background_tasks: BackgroundTasks) -> dict[str, str]:
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


def run() -> int:
    """Runs API server for local development."""
    configure_logging("INFO")
    uvicorn.run("ship_pipeline.api:app", host="0.0.0.0", port=8000, reload=True)
    return 0


def entrypoint() -> None:
    """Console script entrypoint with process exit code propagation."""
    raise SystemExit(run())


if __name__ == "__main__":
    entrypoint()
