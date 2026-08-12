"""
Script 03 — Crown Segmentation with SAM
========================================
Run after 02_detect_trees.py. GPU strongly recommended.
Downloads SAM ViT-B checkpoint (~375 MB) on first run.

Outputs:
  data/derived/segments/canopy_mask.tif
  data/derived/segments/tree_crowns.geojson
  results/figures/pipeline/
"""

import os
import urllib.request
import numpy as np
import rasterio
import rasterio.windows
import rasterio.transform
from rasterio.windows import from_bounds as win_from_bounds
import geopandas as gpd
import torch
from pyproj import Transformer
from shapely.geometry import Polygon
from rasterio.features import shapes as rasterio_shapes
from shapely.geometry import shape
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
# ---------------------------------------------------------------------------
# Configuration (paths relative to repository root)
# ---------------------------------------------------------------------------
INPUT_TIF      = str(ROOT / "data/raw/davis_naip_2022.tif")
BOXES_GEOJSON  = str(ROOT / "data/derived/detections/trees_boxes.geojson")
OUTPUT_DIR     = str(ROOT / "data/derived/segments")
VIZ_DIR        = str(ROOT / "results/figures/pipeline")
SAM_CHECKPOINT = str(ROOT / "data/raw/sam_vit_b_01ec64.pth")
SAM_MODEL_TYPE = "vit_b"
SAM_URL        = "https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth"
PATCH_SIZE     = 800
OVERLAP        = 100
CANOPY_NDVI    = 0.2
PUB_DPI        = 300
# ---------------------------------------------------------------------------


# ── Segmentation helpers ─────────────────────────────────────────────────────

def download_sam_checkpoint():
    if os.path.exists(SAM_CHECKPOINT):
        print(f"SAM checkpoint found: {SAM_CHECKPOINT}")
        return
    os.makedirs(os.path.dirname(SAM_CHECKPOINT), exist_ok=True)
    print("Downloading SAM ViT-B checkpoint (~375 MB) ...")
    urllib.request.urlretrieve(SAM_URL, SAM_CHECKPOINT)
    print("Download complete.")


def mask_to_polygons(mask):
    polys = []
    for geom, val in rasterio_shapes(mask.astype(np.uint8)):
        if val == 1:
            polys.append(shape(geom))
    return polys


def load_boxes_in_pixel_coords(src):
    gdf = gpd.read_file(BOXES_GEOJSON).to_crs(src.crs)
    inv = ~src.transform
    pixel_boxes = []
    for _, row in gdf.iterrows():
        b = row.geometry.bounds
        col_min, row_max = inv * (b[0], b[1])
        col_max, row_min = inv * (b[2], b[3])
        pixel_boxes.append({
            "xmin": max(0, int(col_min)),
            "ymin": max(0, int(row_min)),
            "xmax": min(src.width  - 1, int(col_max)),
            "ymax": min(src.height - 1, int(row_max)),
        })
    return pixel_boxes


def mask_to_geo_polygons(mask, window_transform, src_crs):
    raw_polys = mask_to_polygons(mask)
    if not raw_polys:
        return []
    needs_reproject = str(src_crs).upper() != "EPSG:4326"
    if needs_reproject:
        reproj = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
    geo_polys = []
    for poly in raw_polys:
        try:
            coords_px = list(poly.exterior.coords)
            native = [rasterio.transform.xy(window_transform, c[1], c[0]) for c in coords_px]
            if needs_reproject:
                native = [reproj.transform(x, y) for x, y in native]
            geo_polys.append(Polygon(native))
        except Exception:
            pass
    return geo_polys


# ── Main segmentation ────────────────────────────────────────────────────────

def segment_trees():
    from segment_anything import sam_model_registry, SamPredictor

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    download_sam_checkpoint()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")

    sam = sam_model_registry[SAM_MODEL_TYPE](checkpoint=SAM_CHECKPOINT)
    sam.to(device)
    predictor = SamPredictor(sam)

    stride           = PATCH_SIZE - OVERLAP
    all_crown_records = []

    with rasterio.open(INPUT_TIF) as src:
        H, W    = src.height, src.width
        profile = src.profile.copy()
        # nodata=255 (NOT 0) so background 0 stays a valid value. With nodata=0 the
        # downstream analysis treats all non-canopy pixels as nodata and reports
        # every cell as 0% or 100% canopy.
        profile.update(count=1, dtype="uint8", nodata=255)

        pixel_boxes = load_boxes_in_pixel_coords(src)
        print(f"Loaded {len(pixel_boxes):,} bounding boxes")

        if len(pixel_boxes) == 0:
            print("Warning: no bounding boxes found — skipping segmentation.")
            return

        mask_path  = os.path.join(OUTPUT_DIR, "canopy_mask.tif")
        rows_steps = list(range(0, H, stride))
        col_steps  = list(range(0, W, stride))
        total      = len(rows_steps) * len(col_steps)
        idx        = 0

        with rasterio.open(mask_path, "w", **profile) as dst:
            for r0 in rows_steps:
                for c0 in col_steps:
                    r1  = min(r0 + PATCH_SIZE, H)
                    c1  = min(c0 + PATCH_SIZE, W)
                    idx += 1
                    if idx % 50 == 0 or idx == total:
                        print(f"  [{idx}/{total}] patches, {len(all_crown_records)} crowns", end="\r")

                    patch_boxes_local = [
                        {
                            "xmin": b["xmin"] - c0,
                            "ymin": b["ymin"] - r0,
                            "xmax": b["xmax"] - c0,
                            "ymax": b["ymax"] - r0,
                        }
                        for b in pixel_boxes
                        if b["xmax"] >= c0 and b["xmin"] <= c1
                        and b["ymax"] >= r0 and b["ymin"] <= r1
                    ]

                    if not patch_boxes_local:
                        continue

                    window          = rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0)
                    patch_data      = src.read([1, 2, 3, 4], window=window)   # R,G,B,NIR
                    patch_rgb       = patch_data[:3].transpose(1, 2, 0)
                    r_band          = patch_data[0].astype(np.float32)
                    nir_band        = patch_data[3].astype(np.float32)
                    ndvi            = (nir_band - r_band) / (nir_band + r_band + 1e-6)
                    patch_transform = src.window_transform(window)

                    h_p, w_p = patch_rgb.shape[:2]
                    combined = np.zeros((h_p, w_p), dtype=bool)
                    predictor.set_image(patch_rgb.astype(np.uint8))

                    for b in patch_boxes_local:
                        box = np.array([b["xmin"], b["ymin"], b["xmax"], b["ymax"]], dtype=float)
                        x1 = max(0, int(b["xmin"])); y1 = max(0, int(b["ymin"]))
                        x2 = min(w_p, int(b["xmax"])); y2 = min(h_p, int(b["ymax"]))
                        try:
                            masks, _, _ = predictor.predict(box=box, multimask_output=False)
                            combined |= masks[0]
                        except Exception:
                            pass
                        # Recall boost: also count vegetated (NDVI≥thresh) pixels inside the
                        # crown box. SAM alone often under-segments dense/contiguous canopy;
                        # the box keeps this tree-specific (no lawns far from a detection).
                        if x2 > x1 and y2 > y1:
                            veg = np.zeros((h_p, w_p), dtype=bool)
                            veg[y1:y2, x1:x2] = ndvi[y1:y2, x1:x2] >= CANOPY_NDVI
                            combined |= veg

                    dst.write(combined.astype(np.uint8), 1, window=window)

                    for poly in mask_to_geo_polygons(combined, patch_transform, src.crs):
                        try:
                            area_m2 = float(
                                gpd.GeoSeries([poly], crs="EPSG:4326")
                                .to_crs("EPSG:32610").area.iloc[0]
                            )
                        except Exception:
                            area_m2 = 0.0
                        all_crown_records.append({"geometry": poly, "area_m2": round(area_m2, 2)})

    print(f"\nCanopy mask saved → {mask_path}")
    crowns_path = os.path.join(OUTPUT_DIR, "tree_crowns.geojson")
    gpd.GeoDataFrame(all_crown_records, crs="EPSG:4326").to_file(crowns_path, driver="GeoJSON")
    print(f"Crown polygons saved → {crowns_path}  ({len(all_crown_records):,} crowns)")

    save_visualizations()
    print("Done. Run 04_analyze.py next.")


# ── Visualization helpers ────────────────────────────────────────────────────

def _read_rgb(west=None, south=None, east=None, north=None, max_px=3000):
    with rasterio.open(INPUT_TIF) as src:
        if west is not None:
            win     = win_from_bounds(west, south, east, north, src.transform)
            col_off = max(0, int(win.col_off))
            row_off = max(0, int(win.row_off))
            width   = min(int(win.width),  src.width  - col_off)
            height  = min(int(win.height), src.height - row_off)
            if width <= 0 or height <= 0:
                return None, None, None
            win    = rasterio.windows.Window(col_off, row_off, width, height)
            # rasterio.windows.bounds returns a (left, bottom, right, top) tuple
            left, bottom, right, top = rasterio.windows.bounds(win, src.transform)
            scale  = max(1, max(width, height) // max_px)
            out_h  = max(1, height // scale)
            out_w  = max(1, width  // scale)
            rgb    = src.read([1, 2, 3], window=win, out_shape=(3, out_h, out_w))
        else:
            b = src.bounds
            left, bottom, right, top = b.left, b.bottom, b.right, b.top
            scale  = max(1, max(src.width, src.height) // max_px)
            out_h  = src.height // scale
            out_w  = src.width  // scale
            rgb    = src.read([1, 2, 3], out_shape=(3, out_h, out_w))
    extent = [left, right, bottom, top]
    return np.clip(rgb.transpose(1, 2, 0), 0, 255).astype(np.uint8), extent, (out_h, out_w)


def _read_mask(out_shape, west=None, south=None, east=None, north=None):
    mask_path = os.path.join(OUTPUT_DIR, "canopy_mask.tif")
    with rasterio.open(mask_path) as src:
        if west is not None:
            win     = win_from_bounds(west, south, east, north, src.transform)
            col_off = max(0, int(win.col_off))
            row_off = max(0, int(win.row_off))
            width   = min(int(win.width),  src.width  - col_off)
            height  = min(int(win.height), src.height - row_off)
            if width <= 0 or height <= 0:
                return None
            win  = rasterio.windows.Window(col_off, row_off, width, height)
            mask = src.read(1, window=win, out_shape=out_shape)
        else:
            mask = src.read(1, out_shape=out_shape)
    return mask


def _apply_canopy_overlay(rgb, mask, alpha=0.45):
    """Blend green over canopy pixels (mask==1) on top of the RGB image."""
    out = rgb.astype(np.float32)
    m   = (mask == 1)
    out[m, 0] = out[m, 0] * (1 - alpha)            # reduce red
    out[m, 1] = out[m, 1] * (1 - alpha) + 180 * alpha  # boost green
    out[m, 2] = out[m, 2] * (1 - alpha)            # reduce blue
    return np.clip(out, 0, 255).astype(np.uint8)


def save_canopy_overview(out_path):
    rgb, extent, shape2d = _read_rgb(max_px=6000)
    mask = _read_mask(shape2d)
    if mask is None:
        return
    overlay = _apply_canopy_overlay(rgb, mask)
    pct = 100 * (mask == 1).sum() / mask.size

    fig, axes = plt.subplots(1, 2, figsize=(22, 8), dpi=PUB_DPI)
    fig.suptitle("Canopy Segmentation — City of Davis, CA", fontsize=18, fontweight="bold")

    axes[0].imshow(rgb, extent=extent, aspect="equal")
    axes[0].set_title("NAIP 2022 (True Color)", fontsize=14)
    axes[0].set_xlabel("Longitude", fontsize=11)
    axes[0].set_ylabel("Latitude",  fontsize=11)

    axes[1].imshow(overlay, extent=extent, aspect="equal")
    axes[1].set_title(f"SAM + NDVI Canopy Mask  ({pct:.1f}% of frame)", fontsize=14)
    axes[1].set_xlabel("Longitude", fontsize=11)

    for ax in axes:
        ax.tick_params(labelsize=10)

    plt.tight_layout()
    plt.savefig(out_path, dpi=PUB_DPI, bbox_inches="tight")
    plt.close()
    print(f"  {out_path}")


def save_visualizations():
    os.makedirs(VIZ_DIR, exist_ok=True)
    print("\nSaving publication figures ...")
    save_canopy_overview(os.path.join(VIZ_DIR, "04_canopy_overview.png"))
    print("Segmentation figures saved.\n")


segment_trees()
