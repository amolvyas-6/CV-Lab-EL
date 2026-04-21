# CV-Lab-EL

Automated dataset creation of ship imagery from satellite data using Google Earth Engine (GEE) and GIS processing.

This repository runs as a backend service and supports:

- Phase 1: GEE single-scene export trigger
- Phase 2: NDWI masking
- Phase 3: geospatial tiling + quality filtering
- Phase 4: OpenCV DNN super-resolution (ESPCN x4)
- Phase 6: dataset metadata and summary generation
- Async FastAPI backend with job polling

## 1) Setup

```bash
cd backend
uv sync
```

## 2) Download Super-Resolution Model (Manual)

Download `ESPCN_x4.pb` from OpenCV contrib:

`https://github.com/opencv/opencv_contrib/tree/4.x/modules/dnn_superres/samples`

Place it at:

`downloads/models/ESPCN_x4.pb`

## 3) Backend API Server

Run API service:

```bash
uv run python -m uvicorn main:app --reload --port 8000
```

## 4) API Endpoints

- `GET /health`
- `POST /extract` (returns `job_id` immediately)
- `GET /status/{job_id}`
- `GET /jobs`
- `GET /metadata`
- `GET /summary`

`POST /extract` payload fields:

- Required: `bbox`, `date`, `location_name`
- Optional: `run_fetch`, `fetch_only`, `scene_path`, `masked_path`, `tile_dir`, `sr_tile_dir`, `sr_model_path`, `drive_folder`, `cloud_filter_pct`, `ndwi_threshold`, `tile_size`, `stride`, `black_threshold`, `blur_threshold`

Example request:

```bash
curl -X POST http://127.0.0.1:8000/extract \
	-H "Content-Type: application/json" \
	-d '{
		"bbox": [72.80, 18.87, 72.97, 18.98],
		"date": "2024-02-15",
		"location_name": "mumbai",
		"run_fetch": false
	}'
```

Check status:

```bash
curl http://127.0.0.1:8000/status/<job_id>
```

## 5) Outputs

Generated files are organized as:

```text
dataset/
	raw_exports/
	intermediate/
	processed_tiles/
		<location>_<year>/
		<location>_<year>_sr/
		dataset_summary.csv
	metadata.json
```

## 6) Notes

- GEE exports are asynchronous and appear in your Google Drive folder.
- If `run_fetch=true` and `fetch_only=false`, make sure the scene GeoTIFF exists locally before local phases continue.
- Keep `tile_index.csv` with tiles because JPEG files do not store CRS metadata.
