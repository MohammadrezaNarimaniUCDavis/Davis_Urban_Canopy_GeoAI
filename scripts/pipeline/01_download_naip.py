"""
Download USDA NAIP 2022 (RGB+NIR) for the City of Davis via Google Earth Engine.

Requirements:
  - Earth Engine account
  - Authenticate once with:  earthengine authenticate
    or set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON

Usage (from repo root, conda env with ee/geopandas/rasterio):
  python scripts/pipeline/01_download_naip.py

Output:
  data/raw/davis_naip_2022.tif
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import ee
import geopandas as gpd
import rasterio
import requests
from rasterio.merge import merge as rasterio_merge

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.paths import BOUNDARY  # noqa: E402

OUTPUT_PATH = ROOT / "data" / "raw" / "davis_naip_2022.tif"
DATE_START = "2022-01-01"
DATE_END = "2022-12-31"
SCALE = 0.6
CRS = "EPSG:4326"
TILE_DEG = 0.01


def authenticate_gee() -> None:
    """Prefer ADC / service account; fall back to interactive ee.Initialize()."""
    key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if key and Path(key).exists():
        with open(key, encoding="utf-8") as f:
            creds_json = f.read()
        creds_dict = json.loads(creds_json)
        credentials = ee.ServiceAccountCredentials(
            email=creds_dict["client_email"],
            key_data=creds_json,
        )
        ee.Initialize(credentials=credentials)
        print("GEE authenticated (service account).")
        return
    ee.Initialize()
    print("GEE authenticated (default credentials).")


def shapefile_to_ee_geometry(shp_path: Path):
    gdf = gpd.read_file(shp_path).to_crs("EPSG:4326")
    geom = gdf.geometry.union_all() if hasattr(gdf.geometry, "union_all") else gdf.unary_union
    return ee.Geometry(geom.__geo_interface__)


def download_tile(image, tile_roi, tile_path: Path, scale: float, crs: str) -> None:
    url = image.getDownloadURL(
        {"scale": scale, "crs": crs, "region": tile_roi, "format": "GEO_TIFF"}
    )
    r = requests.get(url, stream=True, timeout=300)
    r.raise_for_status()
    with open(tile_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)


def download_naip() -> None:
    if not BOUNDARY.exists():
        raise FileNotFoundError(f"Missing boundary: {BOUNDARY}")
    authenticate_gee()
    roi = shapefile_to_ee_geometry(BOUNDARY)

    collection = (
        ee.ImageCollection("USDA/NAIP/DOQQ")
        .filterBounds(roi)
        .filterDate(DATE_START, DATE_END)
        .select(["R", "G", "B", "N"])
    )
    count = collection.size().getInfo()
    print(f"Found {count} NAIP scene(s) within Davis boundary for 2022.")

    image = collection.mosaic().clip(roi)
    out_dir = OUTPUT_PATH.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    coords = roi.bounds().getInfo()["coordinates"][0]
    west = min(c[0] for c in coords)
    east = max(c[0] for c in coords)
    south = min(c[1] for c in coords)
    north = max(c[1] for c in coords)

    tile_paths: list[Path] = []
    tile_idx = 0
    lat = south
    while lat < north:
        lon = west
        while lon < east:
            t_roi = ee.Geometry.Rectangle(
                [lon, lat, min(lon + TILE_DEG, east), min(lat + TILE_DEG, north)]
            )
            tile_path = out_dir / f"_tile_{tile_idx:04d}.tif"
            try:
                download_tile(image, t_roi, tile_path, SCALE, CRS)
                tile_paths.append(tile_path)
                if tile_idx % 10 == 0:
                    print(f"  Tile {tile_idx}: [{lon:.3f},{lat:.3f}] ok")
            except Exception as e:
                print(f"  Tile {tile_idx}: skipped ({e})")
            tile_idx += 1
            lon += TILE_DEG
        lat += TILE_DEG

    if not tile_paths:
        raise RuntimeError("No tiles downloaded — check GEE quota and ROI.")

    print(f"\nDownloaded {len(tile_paths)}/{tile_idx} tiles. Mosaicking ...")
    datasets = [rasterio.open(p) for p in tile_paths]
    mosaic, transform = rasterio_merge(datasets)
    profile = datasets[0].profile.copy()
    profile.update(
        height=mosaic.shape[1],
        width=mosaic.shape[2],
        transform=transform,
        compress="lzw",
    )
    with rasterio.open(OUTPUT_PATH, "w", **profile) as dst:
        dst.write(mosaic)
    for ds in datasets:
        ds.close()
    for p in tile_paths:
        p.unlink(missing_ok=True)

    size_mb = OUTPUT_PATH.stat().st_size / 1e6
    print(f"Saved: {OUTPUT_PATH}  ({size_mb:.0f} MB)")
    print("Next: python scripts/pipeline/02_detect_trees.py")


if __name__ == "__main__":
    download_naip()
