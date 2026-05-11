# CV-Lab-EL

Automated dataset creation of ship imagery from satellite data using Google Earth Engine (GEE) and GIS processing.

This repository runs as a backend service and supports:

- Phase 1: GEE single-scene direct download or Drive export trigger
- Phase 2: NDWI masking
- Phase 3: geospatial tiling + quality filtering
- Phase 4: OpenCV DNN super-resolution (ESPCN x4)
- Phase 5: heuristic ship-candidate pseudo-label generation
- Phase 6: dataset metadata and summary generation
- Batch extraction across multiple locations and dates
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
- `POST /batch-extract` (returns `job_id` immediately)
- `GET /status/{job_id}`
- `GET /jobs`
- `GET /metadata`
- `GET /summary`

`POST /extract` payload fields:

- Required: `bbox`, `date`, `location_name`
- Optional: `run_fetch`, `fetch_only`, `download_scene`, `scene_path`, `masked_path`, `tile_dir`, `sr_tile_dir`, `sr_model_path`, `drive_folder`, `cloud_filter_pct`, `ndwi_threshold`, `tile_size`, `stride`, `black_threshold`, `blur_threshold`, `annotate_ships`, `ship_min_area_px`, `ship_max_area_px`, `ship_min_intensity`, `ship_threshold_percentile`

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

Batch request:

```bash
curl -X POST http://127.0.0.1:8000/batch-extract \
	-H "Content-Type: application/json" \
	-d '{
		"locations": [
			{"name": "mumbai", "bbox": [72.80, 18.87, 72.97, 18.98]},
			{"name": "kolkata", "bbox": [88.20, 21.95, 88.45, 22.20]}
		],
		"dates": ["2024-02-15", "2024-03-10"],
		"run_fetch": true,
		"download_scene": true
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
				annotations_coco.json
				ship_candidates.csv
				tile_index.csv
			<location>_<year>_sr/
				annotations_coco.json
				ship_candidates.csv
				tile_index.csv
			dataset_summary.csv
		metadata.json
```

## 6) Notes

- `download_scene=true` downloads normal-sized GEE scenes directly into `dataset/raw_exports/`; set it to `false` to use asynchronous Google Drive export.
- If `download_scene=false` and `run_fetch=true`, wait for the Drive export, download the GeoTIFF, then rerun local phases with `scene_path`.
- Keep `tile_index.csv` with tiles because JPEG files do not store CRS metadata.
- `annotations_coco.json` and `ship_candidates.csv` are heuristic pseudo-labels. They help locate likely ship pixels, but should be manually verified before serious model training.
- The runner validates that a local GeoTIFF covers the requested bbox to prevent accidentally reusing Mumbai imagery for another location.
