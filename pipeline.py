import ee
import geemap
import rasterio
from rasterio.windows import Window
import numpy as np
import os
import matplotlib.pyplot as plt
import cv2
import csv

def fetch_single_scene(bbox: list, target_date: str, output_dir: str):
    """
    Phase 1: Single-Scene Data Acquisition (GEE)
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
    
    # We replace NoData with 0 before export to avoid NaN issues
    rgb_nir_unmasked = rgb_nir.unmask(0)

    # Export to Google Drive (GEE free tier)
    date_str = target_date.replace('-', '')
    description = f"ship_scene_{date_str}"
    
    print(f"Starting GEE export task for {description}...")
    task = ee.batch.Export.image.toDrive(
        image=rgb_nir_unmasked.clip(roi),
        description=description,
        folder='GEE_Ship_Dataset',
        fileNamePrefix=f"scene_{date_str}",
        region=roi,
        scale=10,           # Native Sentinel-2 resolution
        crs='EPSG:4326',
        maxPixels=1e9
    )
    task.start()
    return task.id

def apply_ndwi_mask(geotiff_path: str, output_path: str):
    """
    Phase 2: NDWI Water Masking
    Opens a 4-band GeoTIFF (B4=R, B3=G, B2=B, B8=NIR),
    computes NDWI, and zeroes out land pixels.
    """
    if not os.path.exists(geotiff_path):
        raise FileNotFoundError(f"GeoTIFF file not found: {geotiff_path}")

    with rasterio.open(geotiff_path) as src:
        # Band order from GEE export: B4, B3, B2, B8
        red   = src.read(1).astype(float)
        green = src.read(2).astype(float)
        blue  = src.read(3).astype(float)
        nir   = src.read(4).astype(float)
        profile = src.profile

    # Compute NDWI: (Green - NIR) / (Green + NIR)
    # Avoid division by zero by using np.where
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

    # Update profile to save only 3 bands (RGB)
    profile.update(count=3, dtype='uint16')
    
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(red_masked,   1)
        dst.write(green_masked, 2)
        dst.write(blue_masked,  3)

    print(f"[Phase 2] Water mask applied to {os.path.basename(geotiff_path)}. Water coverage: {water_mask.mean()*100:.1f}%")

def visualize_ndwi_mask(original_path: str, masked_path: str):
    """
    Visualizes the before vs after of the NDWI land masking side-by-side using matplotlib.
    """
    if not os.path.exists(original_path) or not os.path.exists(masked_path):
        print("Error: Could not find original or masked GeoTIFF files for visualization.")
        return

    # Read original RGB
    with rasterio.open(original_path) as src:
        r = src.read(1).astype(float)
        g = src.read(2).astype(float)
        b = src.read(3).astype(float)
        # Sentinel-2 values are 0-10000+, clip to 3000 for display brightness
        rgb_orig = np.dstack((r, g, b))
        rgb_orig = np.clip(rgb_orig / 3000.0, 0, 1)

    # Read masked RGB
    with rasterio.open(masked_path) as src:
        r_m = src.read(1).astype(float)
        g_m = src.read(2).astype(float)
        b_m = src.read(3).astype(float)
        rgb_mask = np.dstack((r_m, g_m, b_m))
        rgb_mask = np.clip(rgb_mask / 3000.0, 0, 1)

    fig, axes = plt.subplots(1, 2, figsize=(15, 8))
    
    axes[0].imshow(rgb_orig)
    axes[0].set_title('Original Scene (RGB)')
    axes[0].axis('off')
    
    axes[1].imshow(rgb_mask)
    axes[1].set_title('NDWI Masked Scene (Water Only)')
    axes[1].axis('off')
    
    plt.tight_layout()
    plt.show()

def is_valid_tile(tile: np.ndarray,
                  black_threshold: float = 0.95,
                  blur_threshold: float = 50.0) -> bool:
    """
    Phase 5: Tile Quality Filtering
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

def tile_geotiff(masked_tif_path: str, output_dir: str, location_tag: str,
                 tile_size=256, stride=204):
    """
    Phase 3: Geospatial Tiling (Sliding Window)
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
    if tile_index:
        csv_path = os.path.join(output_dir, 'tile_index.csv')
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=tile_index[0].keys())
            writer.writeheader()
            writer.writerows(tile_index)

    print(f"[Phase 3] Generated {tile_count} valid tiles → {output_dir}")
    return tile_count

if __name__ == "__main__":
    # --- Instructions for local run ---
    # 1. Authenticate with Google Earth Engine (run this once)
    print("Authenticating with Google Earth Engine...")
    try:
        ee.Initialize(project="fiery-surf-477011-p0")
    except Exception as e:
        print("Earth Engine not initialized. Please authenticate:")
        ee.Authenticate()
        ee.Initialize(project="fiery-surf-477011-p0")
    
    print("Successfully initialized Earth Engine.")
    
    # 2. Test Phase 1 (Mumbai Port)
    # Mumbai (JNPT): Min Lon=72.80, Min Lat=18.87, Max Lon=72.97, Max Lat=18.98
    mumbai_bbox = [72.80, 18.87, 72.97, 18.98]
    test_date = '2024-02-15'
    
    # Uncomment to trigger export task
    # task_id = fetch_single_scene(mumbai_bbox, test_date, "")
    # print(f"Export task started with ID: {task_id}")
    # print("Please check Google Earth Engine Code Editor or your Google Drive for the exported file.")
    
    # 3. Test Phase 2
    # You will need to download the file from Google Drive first, then pass its path here.
    apply_ndwi_mask("scene_20240215.tif", "masked_scene_20240215.tif")
    visualize_ndwi_mask("scene_20240215.tif", "masked_scene_20240215.tif")

    # 4. Test Phase 3
    tile_geotiff(
        masked_tif_path="masked_scene_20240215.tif", 
        output_dir="dataset/processed_tiles/mumbai_2024", 
        location_tag="mumbai"
    )
