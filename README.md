# CV-Lab-EL

Automated dataset creation of ship imagery from satellite data using Google Earth Engine (GEE) and GIS processing.

This repository now supports:
- Phase 1: GEE single-scene export trigger
- Phase 2: NDWI masking
- Phase 3: geospatial tiling + quality filtering
- Phase 4: OpenCV DNN super-resolution (ESPCN x4)
- Phase 6: dataset metadata and summary generation
- Async FastAPI backend with job polling

## 1) Setup

```bash
uv sync
```

## 2) Download Super-Resolution Model (Manual)

Download `ESPCN_x4.pb` from OpenCV contrib:

`https://github.com/opencv/opencv_contrib/tree/4.x/modules/dnn_superres/samples`

Place it at:

`downloads/models/ESPCN_x4.pb`

## 3) Pipeline CLI

Show options:

```bash
uv run ship-pipeline --help
```

Run local full pipeline (Phases 2 -> 6) using a downloaded scene:

```bash
uv run ship-pipeline --skip-visualize
```

Trigger only GEE export task (Phase 1) and stop:

```bash
uv run ship-pipeline --run-fetch --fetch-only --bbox 72.80 18.87 72.97 18.98 --date 2024-02-15
```

Key configurable arguments:
- `--cloud-filter-pct`
- `--ndwi-threshold`
- `--tile-size`
- `--stride`
- `--black-threshold`
- `--blur-threshold`

## 4) Outputs

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

## 5) API Server (Async Jobs)

Run API:

```bash
uv run ship-api
```

Alternative run command:

```bash
uv run uvicorn main:app --reload --port 8000
```

Endpoints:
- `GET /health`
- `POST /extract` (returns `job_id` immediately)
- `GET /status/{job_id}`
- `GET /jobs`

Example request:

```bash
curl -X POST http://127.0.0.1:8000/extract \
	-H "Content-Type: application/json" \
	-d '{
		"bbox": [72.80, 18.87, 72.97, 18.98],
		"date": "2024-02-15",
		"location_name": "mumbai",
		"run_fetch": false,
		"skip_visualize": true
	}'
```

## 6) Frontend Dashboard (React + Vite)

Install dependencies:

```bash
cd frontend
npm install
```

Configure API URL (optional):

```bash
cp .env.example .env
```

Run development server:

```bash
npm run dev
```

Build production frontend:

```bash
npm run build
```

The frontend expects the API server at `http://127.0.0.1:8000` by default.
Override with `VITE_API_BASE_URL` in `frontend/.env`.

## 7) Notes

- GEE exports are asynchronous and appear in your Google Drive folder.
- If you use `--run-fetch` without `--fetch-only`, make sure the scene GeoTIFF exists locally before local phases continue.
- Keep `tile_index.csv` with tiles because JPEG files do not store CRS metadata.
