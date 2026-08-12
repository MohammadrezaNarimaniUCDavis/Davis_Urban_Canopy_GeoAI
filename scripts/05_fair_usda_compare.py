"""
Fair USDA vs pipeline canopy comparison on the shared Census TIGER city extent.

Clips both products to data/boundary/davis_city_boundary.shp (~25.9 km2), then
reports pixel agreement and detection-center precision.

Usage (from repo root):
  python scripts/05_fair_usda_compare.py

Requires Zenodo-derived files under data/derived/ and data/reference/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from rasterio.transform import from_bounds, rowcol
from rasterio.warp import Resampling, reproject
from shapely.geometry import mapping
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.paths import (  # noqa: E402
    BOUNDARY,
    CANOPY_MASK,
    FIGURES,
    TABLES,
    TREES_GEOJSON,
    USDA_CANOPY,
    ensure_output_dirs,
)

TARGET_RES_M = 0.6
PUB_DPI = 300


def load_city():
    gdf = gpd.read_file(BOUNDARY)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.to_crs("EPSG:3310")


def city_geom_3310(city_gdf):
    return (
        city_gdf.geometry.union_all()
        if hasattr(city_gdf.geometry, "union_all")
        else unary_union(city_gdf.geometry)
    )


def build_city_grid(city_gdf, res_m=TARGET_RES_M):
    minx, miny, maxx, maxy = city_gdf.total_bounds
    minx -= res_m
    miny -= res_m
    maxx += res_m
    maxy += res_m
    width = int(np.ceil((maxx - minx) / res_m))
    height = int(np.ceil((maxy - miny) / res_m))
    transform = from_bounds(minx, miny, maxx, maxy, width, height)
    return transform, width, height


def rasterize_to_city(src_path, city_gdf, transform, width, height, canopy_value=1):
    geom = city_geom_3310(city_gdf)
    city_mask = ~geometry_mask(
        [mapping(geom)], out_shape=(height, width), transform=transform, invert=False
    )
    out = np.full((height, width), 0, dtype=np.uint8)
    with rasterio.open(src_path) as src:
        src_data = src.read(1)
        src_bin = np.zeros(src_data.shape, dtype=np.uint8)
        if canopy_value is None:
            # any positive / non-nodata as canopy
            nodata = src.nodata
            valid = np.ones(src_data.shape, dtype=bool)
            if nodata is not None:
                valid &= src_data != nodata
            src_bin[(src_data > 0) & valid] = 1
        else:
            src_bin[src_data == canopy_value] = 1
        dest = np.zeros((height, width), dtype=np.uint8)
        reproject(
            source=src_bin,
            destination=dest,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs="EPSG:3310",
            resampling=Resampling.nearest,
        )
        out[city_mask] = dest[city_mask]
    outside = ~city_mask
    out_full = out.copy()
    out_full[outside] = 255
    return out_full, city_mask


def metrics(our, usda, city_mask):
    a = our[city_mask] == 1
    b = usda[city_mask] == 1
    tp = int(np.logical_and(a, b).sum())
    fp = int(np.logical_and(a, ~b).sum())
    fn = int(np.logical_and(~a, b).sum())
    tn = int(np.logical_and(~a, ~b).sum())
    inter = tp
    union = tp + fp + fn
    iou = inter / union if union else np.nan
    dice = 2 * inter / (2 * inter + fp + fn) if (2 * inter + fp + fn) else np.nan
    prec = tp / (tp + fp) if (tp + fp) else np.nan
    rec = tp / (tp + fn) if (tp + fn) else np.nan
    city_m2 = float(city_mask.sum()) * (TARGET_RES_M**2)
    our_m2 = float(a.sum()) * (TARGET_RES_M**2)
    usda_m2 = float(b.sum()) * (TARGET_RES_M**2)
    return {
        "city_area_km2": city_m2 / 1e6,
        "our_canopy_km2": our_m2 / 1e6,
        "our_canopy_pct": 100 * our_m2 / city_m2,
        "usda_canopy_km2": usda_m2 / 1e6,
        "usda_canopy_pct": 100 * usda_m2 / city_m2,
        "recovery_pct": 100 * our_m2 / usda_m2 if usda_m2 else np.nan,
        "iou": iou,
        "dice": dice,
        "pixel_precision": prec,
        "pixel_recall": rec,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }


def detection_precision(trees_path, usda, transform, city_gdf):
    trees = gpd.read_file(trees_path).to_crs("EPSG:3310")
    geom = city_geom_3310(city_gdf)
    trees = trees[trees.geometry.within(geom)].copy()
    n = len(trees)
    if n == 0:
        return {"n_detections_in_city": 0, "detection_precision": np.nan, "tp_det": 0, "fp_det": 0}
    xs = trees.geometry.x.to_numpy()
    ys = trees.geometry.y.to_numpy()
    rows, cols = rowcol(transform, xs, ys)
    rows = np.asarray(rows)
    cols = np.asarray(cols)
    h, w = usda.shape
    ok = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)
    hit = np.zeros(n, dtype=bool)
    hit[ok] = usda[rows[ok], cols[ok]] == 1
    tp = int(hit.sum())
    fp = int((~hit).sum())
    return {
        "n_detections_in_city": n,
        "tp_det": tp,
        "fp_det": fp,
        "detection_precision": tp / n if n else np.nan,
    }


def main() -> None:
    ensure_output_dirs()
    for p in (BOUNDARY, CANOPY_MASK, USDA_CANOPY, TREES_GEOJSON):
        if not p.exists():
            raise FileNotFoundError(
                f"Missing {p}. Unpack the Zenodo deposit into data/ first."
            )

    city = load_city()
    transform, width, height = build_city_grid(city)
    print("Warping our canopy_mask -> city grid ...")
    our, city_mask = rasterize_to_city(CANOPY_MASK, city, transform, width, height, canopy_value=1)
    print("Warping USDA canopy -> city grid ...")
    usda, _ = rasterize_to_city(USDA_CANOPY, city, transform, width, height, canopy_value=1)

    m = metrics(our, usda, city_mask)
    d = detection_precision(TREES_GEOJSON, usda, transform, city)
    m.update(d)

    out_csv = TABLES / "fair_comparison_metrics_tiger.csv"
    pd.DataFrame([m]).to_csv(out_csv, index=False)
    print("Wrote", out_csv)
    for k, v in m.items():
        print(f"  {k}: {v}")

    # Quick agreement map
    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    rgb = np.zeros((*our.shape, 3), dtype=np.uint8)
    both = (our == 1) & (usda == 1) & city_mask
    only_us = (our == 1) & (usda != 1) & city_mask
    only_usda = (our != 1) & (usda == 1) & city_mask
    rgb[both] = (34, 139, 34)
    rgb[only_us] = (220, 50, 50)
    rgb[only_usda] = (70, 130, 180)
    ax.imshow(rgb)
    ax.set_axis_off()
    ax.set_title("Fair canopy agreement (TIGER extent)\nGreen=both  Red=ours only  Blue=USDA only")
    fig_path = FIGURES / "fair_usda_agreement.png"
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_path, dpi=PUB_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("Wrote", fig_path)


if __name__ == "__main__":
    main()
