# 🛰️ LLM Context Document: Automated Dataset Creation of Ship Images from Satellite Data using GEE and GIS

> **Purpose of this file:** This document is a complete technical context brief intended to onboard any AI assistant, LLM, or collaborator onto this project. Read the entire document before generating any code, architecture, or suggestions. All rules listed under "Agentic Directives" are non-negotiable constraints.

---

## 📌 1. Project Identity

| Field                   | Value                                                                                                                              |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Project Title**       | Automated Dataset Creation of Ship Images from Satellite Data using GEE and GIS                                                    |
| **Type**                | Course Project (Academic Submission)                                                                                               |
| **Developer Profile**   | Beginner Python, no prior GEE or GIS experience                                                                                    |
| **Submission Timeline** | < 4 weeks from project start                                                                                                       |
| **Target Geography**    | Indian Coastline — Priority ports: Mumbai, Chennai, Kochi, Visakhapatnam                                                           |
| **Primary Goal**        | Build an end-to-end pipeline that acquires, masks, tiles, and enhances satellite imagery to produce an ML-ready ship image dataset |

---

## 🎯 2. Core Objectives

1. Acquire satellite imagery of coastal regions in and around India using **Google Earth Engine (GEE)**.
2. Identify and extract water body Regions of Interest (ROI) using **NDWI-based geospatial masking**.
3. Automate large-scale image collection across **multiple Indian port locations and multiple timeframes**.
4. Generate image patches (tiles) at a target spatial resolution of approximately **2m/pixel** (achieved via super-resolution upscaling from 10m Sentinel-2 data).
5. Organize and store extracted images into a **structured, ML-ready dataset** (COCO-compatible).

---

## 🏗️ 3. Technology Stack

### Backend & Core Processing

| Library                  | Version | Role                                               |
| ------------------------ | ------- | -------------------------------------------------- |
| Python                   | 3.10+   | Primary language                                   |
| FastAPI                  | latest  | REST API framework with async background tasks     |
| `earthengine-api` (`ee`) | latest  | Google Earth Engine Python API                     |
| `geemap`                 | latest  | GEE wrapper, simplifies auth and visualization     |
| `rasterio`               | latest  | GeoTIFF reading, tiling, CRS handling              |
| `geopandas`              | latest  | Vector data and spatial operations                 |
| `shapely`                | latest  | Geometry creation for ROI bounding boxes           |
| `opencv-python-headless` | latest  | Image processing and super-resolution (DNN module) |
| `numpy`                  | latest  | Array math for band calculations                   |

Make use of `uv` to manage dependencies:
- To initialize project, use `uv init`
- To activate virtual env, use `source .venv/bin/activate`
- To add a package, use `uv add <package-name>`
- To run a command, use `uv run <command>`
- To sync dependencies, use `uv sync`

### Frontend (Web UI)

| Library         | Role                                               |
| --------------- | -------------------------------------------------- |
| React.js        | SPA framework                                      |
| `react-leaflet` | Interactive map with bounding box drawing tool     |
| Axios           | HTTP client to POST coordinates to FastAPI backend |

### Data Formats

| Format                      | Use Case                                                 |
| --------------------------- | -------------------------------------------------------- |
| GeoTIFF (`.tif`)            | Raw exported imagery from GEE (preserves CRS metadata)   |
| JPEG / PNG (`.jpg`, `.png`) | Final ML-ready image tiles                               |
| JSON (COCO format)          | Annotation metadata for object detection                 |
| CSV                         | Lightweight tile index with geospatial metadata per tile |

---

## 🚨 4. Agentic Directives (Rules — Read Before Writing Any Code)

These are absolute constraints. Do not deviate from them.

### Rule 1 — GEE First, Always

**Never** suggest downloading raw `.tif` or `.nc` files directly from ESA Copernicus Hub, USGS EarthExplorer, or any other portal. All satellite data acquisition **must** go through the Google Earth Engine Python API (`ee`). GEE handles server-side processing, reducing download size significantly.

### Rule 2 — Never Use Temporal Composites for Ship Tiles

> ⚠️ This is the most critical scientific rule in the project.

A **temporal median composite** averages pixel values across multiple acquisitions over a date range. Since ships are moving objects, they appear in only 1–2 scenes out of many, so the median pixel value at their location will resolve to **open water** — the ship is statistically erased.

- **CORRECT approach:** Use **single-date scene acquisition** for ship tile extraction. Select individual Sentinel-2 scenes with `< 10%` cloud cover on a specific target date near a port.
- **ALLOWED use of composites:** Generate the **stable water/land background mask** using a multi-date median composite. Then apply that mask to a single-scene image.

```python
# ✅ CORRECT PATTERN
# Step 1: Build a stable water mask from a composite
composite_for_mask = collection.filterDate('2024-01-01', '2024-03-31').median()
ndwi = composite_for_mask.normalizedDifference(['B3', 'B8'])
water_mask = ndwi.gt(0)

# Step 2: Apply mask to a SINGLE clear-sky scene for actual ship tiles
ship_scene = collection.filterDate('2024-02-15', '2024-02-16').first()
masked_ship_scene = ship_scene.updateMask(water_mask)
```

### Rule 3 — Coordinate Reference Systems

- **Frontend bounding boxes:** Always in `EPSG:4326` (WGS 84 — standard lat/lon).
- **Distance calculations and tiling:** Reproject to `EPSG:32643` (WGS 84 / UTM Zone 43N) for western India, or `EPSG:32644` (UTM Zone 44N) for eastern India. Do not use degrees for pixel distance math.
- **GEE exports:** Use `crs='EPSG:4326'` unless doing area calculations.

### Rule 4 — No Paid Satellite Data

Use only free, open-access datasets available on GEE:

- ✅ `COPERNICUS/S2_SR_HARMONIZED` — Sentinel-2 L2A Multispectral (10m)
- ✅ `COPERNICUS/S1_GRD` — Sentinel-1 SAR (10m, optional but recommended)
- ❌ PlanetScope, Maxar WorldView, Airbus SPOT — commercial, do not use unless explicitly requested

### Rule 5 — Asynchronous API Endpoints

GEE processing and GeoTIFF downloads can take 30–300 seconds. All FastAPI endpoints that trigger GEE operations **must** use `BackgroundTasks` (non-blocking). Return a job ID immediately; let the client poll for status.

### Rule 6 — Super-Resolution via OpenCV DNN, Not PyTorch

For this project's scope and timeline, use **OpenCV's built-in DNN Super-Resolution module** with a pre-trained `ESPCN_x4.pb` model. PyTorch SRCNN integration is too complex for the given timeline. The result is academically sufficient and should be framed as _data augmentation / resolution enhancement_, not as a sensor improvement claim.

```python
import cv2
sr = cv2.dnn_superres.DnnSuperResImpl_create()
sr.readModel("ESPCN_x4.pb")  # Pre-trained weights file
sr.setModel("espcn", 4)       # 4x upscale factor
upscaled_tile = sr.upsample(tile_bgr)
```

> **Download model weights:** `https://github.com/opencv/opencv_contrib/tree/master/modules/dnn_superres`

### Rule 7 — Tile Quality Filtering is Mandatory

After tiling, discard low-quality tiles using two filters before saving:

1. **Black pixel filter:** Discard tiles where > 95% of pixels are black (pure land/masked area).
2. **Blur detection (Laplacian variance):** Discard tiles with a variance < 50 (blurry/featureless water).

```python
def is_valid_tile(tile: np.ndarray, black_threshold=0.95, blur_threshold=50) -> bool:
    black_pixels = np.sum(np.all(tile == 0, axis=2))
    total_pixels = tile.shape[0] * tile.shape[1]
    if black_pixels / total_pixels > black_threshold:
        return False
    gray = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
    if cv2.Laplacian(gray, cv2.CV_64F).var() < blur_threshold:
        return False
    return True
```

---

## ⚙️ 5. Corrected Pipeline Architecture (6 Phases)

```
[Phase 1] → [Phase 2] → [Phase 3] → [Phase 4] → [Phase 5] → [Phase 6]
  GEE         NDWI       Rasterio    OpenCV DNN   Quality     Dataset
  Single      Water      Sliding     4x Super     Filtering   Structure
  Scene       Masking    Window      Resolution   + Indexing  + Metadata
  Fetch                  Tiling
```

---

### Phase 1: Single-Scene Data Acquisition (GEE)

**Input:** Bounding box `[min_lon, min_lat, max_lon, max_lat]` + target date.  
**Satellite:** `COPERNICUS/S2_SR_HARMONIZED` (Sentinel-2 L2A).  
**Cloud filter:** `CLOUDY_PIXEL_PERCENTAGE < 10`.  
**Output:** A single Sentinel-2 scene clipped to the ROI, exported as GeoTIFF.

```python
import ee
import geemap

def fetch_single_scene(bbox: list, target_date: str, output_path: str):
    """
    bbox: [min_lon, min_lat, max_lon, max_lat] in EPSG:4326
    target_date: 'YYYY-MM-DD' string
    """
    roi = ee.Geometry.Rectangle(bbox)

    # Date window: ±3 days around target date for scene availability
    start = ee.Date(target_date).advance(-3, 'day')
    end   = ee.Date(target_date).advance(3, 'day')

    collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                  .filterBounds(roi)
                  .filterDate(start, end)
                  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 10))
                  .sort('CLOUDY_PIXEL_PERCENTAGE'))

    scene = collection.first()  # Least cloudy scene in window

    # Select RGB + NIR bands for NDWI computation later
    rgb_nir = scene.select(['B4', 'B3', 'B2', 'B8'])  # R, G, B, NIR

    # Export to Google Drive (GEE free tier)
    task = ee.batch.Export.image.toDrive(
        image=rgb_nir.clip(roi),
        description=f"ship_scene_{target_date.replace('-', '')}",
        folder='GEE_Ship_Dataset',
        fileNamePrefix=f"scene_{target_date.replace('-', '')}",
        region=roi,
        scale=10,           # Native Sentinel-2 resolution
        crs='EPSG:4326',
        maxPixels=1e9
    )
    task.start()
    return task.id
```

---

### Phase 2: NDWI Water Masking

**Algorithm:** McFeeters (1996) NDWI.  
**Formula:** `NDWI = (Green - NIR) / (Green + NIR)`  
**Sentinel-2 bands:** Green = B3, NIR = B8.  
**Threshold:** `NDWI > 0` → Water pixel (keep). `NDWI ≤ 0` → Land pixel (mask to 0).

```python
import rasterio
import numpy as np

def apply_ndwi_mask(geotiff_path: str, output_path: str):
    """
    Opens a 4-band GeoTIFF (B4=R, B3=G, B2=B, B8=NIR),
    computes NDWI, and zeroes out land pixels.
    """
    with rasterio.open(geotiff_path) as src:
        # Band order from GEE export: B4, B3, B2, B8
        red   = src.read(1).astype(float)
        green = src.read(2).astype(float)
        blue  = src.read(3).astype(float)
        nir   = src.read(4).astype(float)
        profile = src.profile

    # Compute NDWI
    ndwi = np.where(
        (green + nir) == 0, 0,
        (green - nir) / (green + nir)
    )

    # Binary water mask: 1 = water, 0 = land
    water_mask = (ndwi > 0).astype(np.uint8)

    # Apply mask: land pixels become 0 in all bands
    red_masked   = (red   * water_mask).astype(np.uint16)
    green_masked = (green * water_mask).astype(np.uint16)
    blue_masked  = (blue  * water_mask).astype(np.uint16)

    profile.update(count=3, dtype='uint16')
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(red_masked,   1)
        dst.write(green_masked, 2)
        dst.write(blue_masked,  3)

    print(f"[Phase 2] Water mask applied. Water coverage: {water_mask.mean()*100:.1f}%")
```

---

### Phase 3: Geospatial Tiling (Sliding Window)

**Tile size:** 256×256 pixels (standard for YOLO/Faster-RCNN training).  
**Stride:** 204 pixels → ~20% overlap to prevent ships from being cut at tile boundaries.  
**Output format:** JPEG tiles with geospatial metadata in accompanying CSV.

```python
import rasterio
from rasterio.windows import Window
import numpy as np
import os, csv

def tile_geotiff(masked_tif_path: str, output_dir: str, location_tag: str,
                 tile_size=256, stride=204):
    """
    Sliding window tiling of a masked GeoTIFF.
    Saves valid tiles as JPEG and logs metadata to CSV.
    """
    os.makedirs(output_dir, exist_ok=True)
    tile_index = []
    tile_count = 0

    with rasterio.open(masked_tif_path) as src:
        width, height = src.width, src.height
        transform = src.transform

        for row_off in range(0, height - tile_size + 1, stride):
            for col_off in range(0, width - tile_size + 1, stride):
                window = Window(col_off, row_off, tile_size, tile_size)
                tile = src.read(window=window)  # Shape: (bands, H, W)

                # Transpose to HWC for OpenCV compatibility
                tile_hwc = np.transpose(tile, (1, 2, 0))

                if not is_valid_tile(tile_hwc):
                    continue

                # Compute tile's geographic bounding box
                tile_transform = src.window_transform(window)
                min_lon = tile_transform.c
                max_lat = tile_transform.f
                max_lon = min_lon + tile_size * tile_transform.a
                min_lat = max_lat + tile_size * tile_transform.e

                filename = f"tile_{tile_count:05d}.jpg"
                filepath = os.path.join(output_dir, filename)

                # Convert uint16 → uint8 for JPEG
                tile_uint8 = (tile_hwc / 256).astype(np.uint8)
                import cv2
                cv2.imwrite(filepath, cv2.cvtColor(tile_uint8, cv2.COLOR_RGB2BGR))

                tile_index.append({
                    'filename': filename,
                    'location': location_tag,
                    'min_lon': min_lon, 'min_lat': min_lat,
                    'max_lon': max_lon, 'max_lat': max_lat,
                    'row_offset': row_off, 'col_offset': col_off
                })
                tile_count += 1

    # Save CSV index
    csv_path = os.path.join(output_dir, 'tile_index.csv')
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=tile_index[0].keys())
        writer.writeheader()
        writer.writerows(tile_index)

    print(f"[Phase 3] Generated {tile_count} valid tiles → {output_dir}")
    return tile_count
```

---

### Phase 4: Resolution Enhancement (OpenCV DNN Super-Resolution)

**Model:** ESPCN (Efficient Sub-Pixel Convolutional Neural Network) — 4× upscale.  
**Input:** 256×256 pixel tile at 10m/pixel.  
**Output:** 1024×1024 pixel tile at ~2.5m/pixel (visually equivalent to ~2m target).  
**Framing note:** This is _resolution enhancement via learned upscaling_, not actual sensor data. Acknowledge this limitation in your project report.

```python
import cv2
import os

def apply_super_resolution(input_dir: str, output_dir: str, model_path: str = "ESPCN_x4.pb"):
    """
    Applies 4x ESPCN super-resolution to all JPEG tiles in input_dir.
    Saves enhanced tiles to output_dir.
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"SR model not found at {model_path}. "
            "Download from: https://github.com/opencv/opencv_contrib/tree/master/modules/dnn_superres"
        )

    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    sr.readModel(model_path)
    sr.setModel("espcn", 4)

    os.makedirs(output_dir, exist_ok=True)
    processed = 0

    for filename in os.listdir(input_dir):
        if not filename.endswith('.jpg'):
            continue

        img = cv2.imread(os.path.join(input_dir, filename))
        if img is None:
            continue

        upscaled = sr.upsample(img)
        cv2.imwrite(os.path.join(output_dir, filename), upscaled)
        processed += 1

    print(f"[Phase 4] Super-resolution applied to {processed} tiles → {output_dir}")
```

---

### Phase 5: Tile Quality Filtering

Applied **before** saving tiles in Phase 3. Also available as a standalone post-processing pass.

```python
import cv2, numpy as np

def is_valid_tile(tile: np.ndarray,
                  black_threshold: float = 0.95,
                  blur_threshold: float = 50.0) -> bool:
    """
    Returns True if tile passes quality checks.
    tile: HWC uint8 or uint16 numpy array.
    """
    # Check 1: Black pixel ratio (land/masked area)
    black_pixels = np.sum(np.all(tile == 0, axis=2))
    total_pixels = tile.shape[0] * tile.shape[1]
    if black_pixels / total_pixels > black_threshold:
        return False  # Mostly masked land

    # Check 2: Blur detection via Laplacian variance
    if tile.dtype != np.uint8:
        tile_u8 = (tile / 256).astype(np.uint8)
    else:
        tile_u8 = tile
    gray = cv2.cvtColor(tile_u8, cv2.COLOR_RGB2GRAY)
    if cv2.Laplacian(gray, cv2.CV_64F).var() < blur_threshold:
        return False  # Featureless water / blurry tile

    return True
```

---

### Phase 6: Dataset Structuring

**Required directory layout:**

```
/dataset/
├── metadata.json                  ← Global config: date range, locations, total tiles, model used
├── /raw_exports/                  ← Original GeoTIFFs from GEE (unmodified)
│     ├── mumbai_20240215.tif
│     └── chennai_20240310.tif
└── /processed_tiles/
      ├── /mumbai_2024/
      │     ├── tile_00001.jpg
      │     ├── tile_00002.jpg
      │     ├── tile_index.csv         ← Geospatial metadata per tile
      │     └── annotations.json      ← COCO-format bounding boxes (if labeled)
      ├── /chennai_2024/
      │     ├── tile_00001.jpg
      │     └── tile_index.csv
      └── dataset_summary.csv          ← Aggregate statistics across all locations
```

**`metadata.json` schema:**

```json
{
  "project": "Ship Detection Dataset",
  "created_by": "GEE + GIS Pipeline v1.0",
  "satellite": "Sentinel-2 L2A (COPERNICUS/S2_SR_HARMONIZED)",
  "resolution_native_m": 10,
  "resolution_enhanced_m": 2.5,
  "tile_size_px": 256,
  "stride_px": 204,
  "sr_model": "ESPCN_x4",
  "locations": [
    {
      "name": "mumbai",
      "bbox": [72.8, 18.87, 72.97, 18.98],
      "date": "2024-02-15",
      "tile_count": 412
    }
  ],
  "total_tiles": 1850,
  "ndwi_threshold": 0.0,
  "cloud_filter_pct": 10
}
```

---

## 🌐 6. FastAPI Backend Structure

```python
# main.py — Skeleton structure

from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import ee, uuid

app = FastAPI(title="Ship Dataset API")

# --- GEE Init ---
ee.Authenticate()
ee.Initialize(project='your-gee-project-id')

# --- Request Models ---
class ExtractionRequest(BaseModel):
    bbox: list[float]        # [min_lon, min_lat, max_lon, max_lat]
    date: str                # 'YYYY-MM-DD'
    location_name: str       # e.g., 'mumbai'

# --- Job Store (in-memory for course project; use Redis for production) ---
jobs = {}

# --- Endpoints ---
@app.post("/extract")
async def trigger_extraction(req: ExtractionRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "queued", "tiles": 0}
    background_tasks.add_task(run_pipeline, job_id, req)
    return {"job_id": job_id, "status": "queued"}

@app.get("/status/{job_id}")
def get_status(job_id: str):
    return jobs.get(job_id, {"error": "Job not found"})

async def run_pipeline(job_id: str, req: ExtractionRequest):
    jobs[job_id]["status"] = "running"
    try:
        # Call Phase 1 → 2 → 3 → 4 → 5 → 6 functions here
        jobs[job_id]["status"] = "complete"
    except Exception as e:
        jobs[job_id]["status"] = f"failed: {str(e)}"
```

---

## 🗺️ 7. Target Indian Port Bounding Boxes (EPSG:4326)

| Port          | Min Lon | Min Lat | Max Lon | Max Lat | UTM Zone |
| ------------- | ------- | ------- | ------- | ------- | -------- |
| Mumbai (JNPT) | 72.80   | 18.87   | 72.97   | 18.98   | 43N      |
| Chennai       | 80.24   | 13.04   | 80.34   | 13.14   | 44N      |
| Kochi         | 76.22   | 9.94    | 76.32   | 10.04   | 43N      |
| Visakhapatnam | 83.25   | 17.65   | 83.35   | 17.75   | 44N      |

**Recommended test dates** (low monsoon cloud cover): January–March 2024.

---

## ⚠️ 8. Known Pitfalls & Failure Modes

| Pitfall                             | Description                                                       | Fix                                                               |
| ----------------------------------- | ----------------------------------------------------------------- | ----------------------------------------------------------------- |
| **GEE Auth Delay**                  | `ee.Authenticate()` requires OAuth + account approval (24–48 hrs) | Register at earthengine.google.com immediately                    |
| **Temporal Composite Erases Ships** | Median composite across days removes moving ships                 | Use single-date scene for ship tiles (see Rule 2)                 |
| **uint16 → JPEG Overflow**          | Sentinel-2 reflectance is uint16; JPEG requires uint8             | Divide by 256: `(arr / 256).astype(np.uint8)`                     |
| **NoData in GEE Export**            | Masked pixels export as `NaN` or very large values                | Use `.unmask(0)` before export to convert NoData → 0              |
| **SR Model File Not Found**         | `ESPCN_x4.pb` must be in working directory                        | Download from `opencv_contrib` GitHub before running              |
| **Monsoon Cloud Cover**             | Jun–Sep: < 10% cloud scenes are extremely rare for Indian coast   | Target Jan–Mar or Oct–Nov acquisition dates                       |
| **Tile CRS Loss**                   | Plain JPEG has no CRS metadata                                    | Always save `tile_index.csv` alongside tiles                      |
| **GEE Export Quota**                | Free tier: max 10 concurrent tasks, 10 GB Drive                   | Export one port at a time; monitor at code.earthengine.google.com |

---

## 📦 9. Python Environment Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Core dependencies
pip install earthengine-api geemap rasterio geopandas shapely
pip install fastapi uvicorn python-multipart
pip install opencv-contrib-python-headless numpy
pip install requests python-dotenv

# Run the API server
uvicorn main:app --reload --port 8000

# GEE Authentication (one-time setup)
python -c "import ee; ee.Authenticate()"
```

---

## 🗓️ 10. Recommended 4-Week Execution Plan

### Week 1 — Core GEE Pipeline

- [ ] Register and authenticate GEE account
- [ ] Write `fetch_single_scene()` — test with Mumbai port bbox
- [ ] Implement `apply_ndwi_mask()` — verify land erasure visually
- [ ] Export first masked GeoTIFF to Google Drive
- **Deliverable:** A masked GeoTIFF of Mumbai harbor

### Week 2 — Tiling & Super-Resolution

- [ ] Implement `tile_geotiff()` with quality filters
- [ ] Download ESPCN model weights, implement `apply_super_resolution()`
- [ ] Run end-to-end pipeline on Mumbai GeoTIFF
- [ ] Set up dataset directory structure
- **Deliverable:** 200+ valid 256×256 ship tiles from one port

### Week 3 — API & Multi-Location Support

- [ ] Wrap pipeline in FastAPI with `/extract` and `/status` endpoints
- [ ] Test API using Postman (no frontend needed yet)
- [ ] Run pipeline on 2nd port (e.g., Chennai)
- [ ] Generate `metadata.json` automatically
- **Deliverable:** Working REST API callable via Postman; 400+ tiles from 2 ports

### Week 4 — Frontend UI & Final Submission

- [ ] Build React + `react-leaflet` UI with bounding box draw tool
- [ ] Connect frontend to FastAPI `/extract` endpoint
- [ ] Write project report — include scientific limitations section (SR framing, NDWI threshold choices)
- [ ] Record demo video showing end-to-end flow
- **Deliverable:** Completed web app + documented dataset + academic report

> **Fallback:** If Week 4 time runs short, replace React UI with a simple HTML form. A working backend pipeline with a documented dataset is more valuable than a polished UI with a broken pipeline.

---

## 📚 11. Academic References (IEEE Format)

> [1] K. S. McFeeters, "The use of the Normalized Difference Water Index (NDWI) in the delineation of open water features," _International Journal of Remote Sensing_, vol. 17, no. 7, pp. 1425–1432, 1996, doi: 10.1080/01431169608948714.

> [2] N. Gorelick, M. Hancher, M. Dixon, S. Ilyushchenko, D. Thau, and R. Moore, "Google Earth Engine: Planetary-scale geospatial analysis for everyone," _Remote Sensing of Environment_, vol. 202, pp. 18–27, Dec. 2017, doi: 10.1016/j.rse.2017.06.031.

> [3] C. Dong, C. C. Loy, K. He, and X. Tang, "Image Super-Resolution Using Deep Convolutional Networks," _IEEE Transactions on Pattern Analysis and Machine Intelligence_, vol. 38, no. 2, pp. 295–307, Feb. 2016, doi: 10.1109/TPAMI.2015.2439281.

> [4] X. Gui, L. Wang, R. Yao, D. Yu, and C. Li, "Investigating the Long-Term Trends (2001–2019) and Ship Traffic-Related Ship Detection in Ship-Wake SAR Images," _IEEE Journal of Selected Topics in Applied Earth Observations and Remote Sensing_, vol. 14, pp. 6251–6264, 2021, doi: 10.1109/JSTARS.2021.3083060.

> [5] W. Shi et al., "Real-Time Single Image and Video Super-Resolution Using an Efficient Sub-Pixel Convolutional Neural Network," in _Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition (CVPR)_, Las Vegas, NV, USA, 2016, pp. 1874–1883, doi: 10.1109/CVPR.2016.207.

> [6] S. Kanjir, H. Greidanus, and K. Oštir, "Vessel detection and classification from spaceborne optical images: A literature survey," _Remote Sensing of Environment_, vol. 207, pp. 1–26, Mar. 2018, doi: 10.1016/j.rse.2017.12.033.

---

## 🔬 12. Optional Enhancement: Sentinel-1 SAR (Bonus Points)

If time permits, add a Sentinel-1 SAR comparison. SAR is **cloud-independent and weather-independent** — ships appear as bright point scatterers on a dark water background (high Radar Cross Section). This is the most reliable satellite modality for ship detection.

```python
# GEE Collection ID for Sentinel-1
s1_collection = (ee.ImageCollection('COPERNICUS/S1_GRD')
                 .filterBounds(roi)
                 .filterDate(start, end)
                 .filter(ee.Filter.eq('instrumentMode', 'IW'))       # Interferometric Wide Swath
                 .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
                 .select('VV'))  # VV polarization — best for ship detection
```

**Academic value:** Including even a brief visual comparison between Sentinel-2 RGB tiles and Sentinel-1 SAR tiles of the same port area in your report will demonstrate graduate-level understanding of multi-modal remote sensing.

---

_Document Version: 1.1 — Reviewed and corrected for scientific accuracy. Generated for course project use._
