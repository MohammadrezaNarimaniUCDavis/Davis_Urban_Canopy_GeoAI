"""
Script 02 — Tree Detection via DeepForest + NDVI Post-Filter
============================================================
Detects tree crowns using DeepForest and discards non-tree false positives
by requiring mean NDVI >= NDVI_THRESHOLD within each detected bounding box.

Inputs:
  data/raw/davis_naip_2022.tif
  data/boundary/davis_city_boundary.shp

Outputs:
  data/derived/detections/trees.geojson
  data/derived/detections/trees_boxes.geojson
  results/figures/pipeline/
"""

import os
import numpy as np
import rasterio
import rasterio.windows
import rasterio.transform
from rasterio.windows import from_bounds as win_from_bounds
import geopandas as gpd
from shapely.geometry import Point, box as shapely_box
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
from torchvision.ops import nms as torch_nms
from pyproj import Transformer
from deepforest import main as deepforest_main

from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
# ---------------------------------------------------------------------------
# Configuration (paths relative to repository root)
# ---------------------------------------------------------------------------
INPUT_TIF         = str(ROOT / "data/raw/davis_naip_2022.tif")
BOUNDARY_SHP      = str(ROOT / "data/boundary/davis_city_boundary.shp")
OUTPUT_DIR        = str(ROOT / "data/derived/detections")
VIZ_DIR           = str(ROOT / "results/figures/pipeline")
PATCH_SIZE        = 512
OVERLAP           = 128
MIN_PATCH_PX      = 64
NDVI_THRESHOLD    = 0.2
NMS_IOU_THRESHOLD = 0.3
SCORE_THRESH      = 0.05
PUB_DPI           = 300
# ---------------------------------------------------------------------------


# ── Detection helpers ────────────────────────────────────────────────────────

def mean_ndvi(r_patch, nir_patch):
    r   = r_patch.astype(np.float32)
    nir = nir_patch.astype(np.float32)
    return float(np.mean((nir - r) / (nir + r + 1e-6)))


def apply_nms(detections, iou_threshold):
    if not detections:
        return []
    boxes  = torch.tensor(
        [[d["xmin"], d["ymin"], d["xmax"], d["ymax"]] for d in detections],
        dtype=torch.float32,
    )
    scores = torch.tensor([d["score"] for d in detections], dtype=torch.float32)
    keep   = torch_nms(boxes, scores, iou_threshold)
    return [detections[i] for i in keep.tolist()]


def pixel_to_lonlat(transform, src_crs, col, row):
    x, y = rasterio.transform.xy(transform, row, col)
    if str(src_crs).upper() != "EPSG:4326":
        t = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
        return t.transform(x, y)
    return x, y


# ── Model loading ────────────────────────────────────────────────────────────
# deepforest 1.3.3's use_release() queries GitHub /releases/latest, which now
# returns empty assets (IndexError) and has no 1.3.3-tagged model release. The
# weights are reliably hosted on Hugging Face (weecology/deepforest-tree/NEON.pt),
# which we use as the primary source. NEON.pt is a plain state_dict.

HF_REPO     = "weecology/deepforest-tree"
HF_FILENAME = "NEON.pt"

def load_deepforest_model():
    """Load DeepForest weights, preferring Hugging Face over the broken GitHub release API."""
    model = deepforest_main.deepforest()

    # Primary: Hugging Face Hub (huggingface_hub ships as a deepforest dependency).
    try:
        from huggingface_hub import hf_hub_download
        weights_path = hf_hub_download(repo_id=HF_REPO, filename=HF_FILENAME)
        state_dict   = torch.load(weights_path, map_location="cpu")
        model.model.load_state_dict(state_dict)
        print(f"  Loaded NEON.pt from Hugging Face ({HF_REPO}).")
        return model
    except Exception as e:
        print(f"  Hugging Face load failed ({e}). Trying use_release() ...")

    # Fallback: the original GitHub-release path (works if GitHub assets are restored).
    model.use_release()
    print("  Loaded via use_release().")
    return model


# ── Main detection ───────────────────────────────────────────────────────────

def detect_trees():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading DeepForest pretrained model ...")
    model = load_deepforest_model()
    model.model.eval()

    # Lower the confidence floor to improve recall (we keep NDVI + NMS as guards).
    try:
        model.model.score_thresh = SCORE_THRESH
    except Exception:
        pass
    try:
        model.config["score_thresh"] = SCORE_THRESH
    except Exception:
        pass
    print(f"  Detection score threshold: {SCORE_THRESH}")

    stride   = PATCH_SIZE - OVERLAP
    all_dets = []

    with rasterio.open(INPUT_TIF) as src:
        transform = src.transform
        src_crs   = src.crs
        H, W      = src.height, src.width
        print(f"Image: {W}×{H} px | CRS: {src_crs} | Bands: {src.count}")

        rows_steps = list(range(0, H, stride))
        col_steps  = list(range(0, W, stride))
        total      = len(rows_steps) * len(col_steps)
        idx        = 0

        for r0 in rows_steps:
            for c0 in col_steps:
                r1 = min(r0 + PATCH_SIZE, H)
                c1 = min(c0 + PATCH_SIZE, W)
                ph, pw = r1 - r0, c1 - c0

                idx += 1
                if ph < MIN_PATCH_PX or pw < MIN_PATCH_PX:
                    continue
                if idx % 100 == 0 or idx == total:
                    print(f"  [{idx}/{total}] patches | {len(all_dets)} raw dets", end="\r")

                window   = rasterio.windows.Window(c0, r0, pw, ph)
                data     = src.read([1, 2, 3, 4], window=window)   # (4, ph, pw)
                rgb      = data[:3].transpose(1, 2, 0).astype(np.uint8)
                r_band   = data[0]
                nir_band = data[3]

                # Pass float32 (0-255 range) so DeepForest doesn't warn on every patch
                boxes = model.predict_image(image=rgb.astype(np.float32), return_plot=False)
                if boxes is None or len(boxes) == 0:
                    continue

                for _, box in boxes.iterrows():
                    x1 = max(0, int(box.xmin));  y1 = max(0, int(box.ymin))
                    x2 = min(pw - 1, int(box.xmax)); y2 = min(ph - 1, int(box.ymax))
                    if x2 <= x1 or y2 <= y1:
                        continue
                    if mean_ndvi(r_band[y1:y2, x1:x2], nir_band[y1:y2, x1:x2]) < NDVI_THRESHOLD:
                        continue
                    all_dets.append({
                        "xmin":  float(box.xmin) + c0,
                        "ymin":  float(box.ymin) + r0,
                        "xmax":  float(box.xmax) + c0,
                        "ymax":  float(box.ymax) + r0,
                        "score": float(box.score),
                    })

    print(f"\nRaw detections:  {len(all_dets):,}")
    all_dets = apply_nms(all_dets, NMS_IOU_THRESHOLD)
    print(f"After NMS:       {len(all_dets):,}")

    with rasterio.open(INPUT_TIF) as src:
        transform = src.transform
        src_crs   = src.crs

    points, boxes_list = [], []
    for d in all_dets:
        cx = (d["xmin"] + d["xmax"]) / 2
        cy = (d["ymin"] + d["ymax"]) / 2
        lon_c,  lat_c  = pixel_to_lonlat(transform, src_crs, cx,        cy)
        lon_tl, lat_tl = pixel_to_lonlat(transform, src_crs, d["xmin"], d["ymin"])
        lon_br, lat_br = pixel_to_lonlat(transform, src_crs, d["xmax"], d["ymax"])
        points.append({"geometry": Point(lon_c, lat_c), "confidence": d["score"]})
        boxes_list.append({
            "geometry": shapely_box(
                min(lon_tl, lon_br), min(lat_tl, lat_br),
                max(lon_tl, lon_br), max(lat_tl, lat_br),
            ),
            "confidence": d["score"],
        })

    gdf_points = gpd.GeoDataFrame(points,     crs="EPSG:4326")
    gdf_boxes  = gpd.GeoDataFrame(boxes_list, crs="EPSG:4326")

    print("Clipping to Davis city boundary ...")
    boundary = gpd.read_file(BOUNDARY_SHP).to_crs("EPSG:4326")
    if len(gdf_points) > 0:
        gdf_points = gpd.clip(gdf_points, boundary)
        gdf_boxes  = gpd.clip(gdf_boxes,  boundary)
    print(f"After boundary clip: {len(gdf_points):,} trees")

    gdf_points.to_file(os.path.join(OUTPUT_DIR, "trees.geojson"),       driver="GeoJSON")
    gdf_boxes.to_file( os.path.join(OUTPUT_DIR, "trees_boxes.geojson"), driver="GeoJSON")
    print(f"Saved → {OUTPUT_DIR}/")

    save_visualizations(gdf_points, gdf_boxes)
    print("Done. Run 03_segment_trees.py next.")


# ── Visualization helpers ────────────────────────────────────────────────────

def _read_rgb(west=None, south=None, east=None, north=None, max_px=3000):
    """Read RGB bands from INPUT_TIF, optionally clipped to a lat/lon window."""
    with rasterio.open(INPUT_TIF) as src:
        if west is not None:
            win     = win_from_bounds(west, south, east, north, src.transform)
            col_off = max(0, int(win.col_off))
            row_off = max(0, int(win.row_off))
            width   = min(int(win.width),  src.width  - col_off)
            height  = min(int(win.height), src.height - row_off)
            if width <= 0 or height <= 0:
                return None, None
            win    = rasterio.windows.Window(col_off, row_off, width, height)
            # rasterio.windows.bounds returns a (left, bottom, right, top) tuple
            left, bottom, right, top = rasterio.windows.bounds(win, src.transform)
            scale  = max(1, max(width, height) // max_px)
            rgb    = src.read([1, 2, 3], window=win,
                               out_shape=(3, max(1, height // scale), max(1, width // scale)))
        else:
            b = src.bounds
            left, bottom, right, top = b.left, b.bottom, b.right, b.top
            scale  = max(1, max(src.width, src.height) // max_px)
            rgb    = src.read([1, 2, 3],
                               out_shape=(3, src.height // scale, src.width // scale))
    extent = [left, right, bottom, top]
    return np.clip(rgb.transpose(1, 2, 0), 0, 255).astype(np.uint8), extent


def _annotate_count(ax, text):
    """Large on-image stat badge (bottom-left)."""
    ax.text(0.015, 0.025, text, transform=ax.transAxes,
            fontsize=20, fontweight="bold", color="white", va="bottom", ha="left",
            bbox=dict(boxstyle="round,pad=0.45", facecolor="black", alpha=0.6,
                      edgecolor="white", linewidth=1.2), zorder=10)


def save_raw_overview(out_path):
    rgb, extent = _read_rgb(max_px=6000)
    fig, ax = plt.subplots(figsize=(18, 12), dpi=PUB_DPI)
    ax.imshow(rgb, extent=extent, aspect="equal")
    ax.set_title("NAIP 2022 — City of Davis, CA  (True Color)",
                 fontsize=18, fontweight="bold", pad=14)
    ax.set_xlabel("Longitude", fontsize=13)
    ax.set_ylabel("Latitude",  fontsize=13)
    ax.tick_params(labelsize=11)
    plt.tight_layout()
    plt.savefig(out_path, dpi=PUB_DPI, bbox_inches="tight")
    plt.close()
    print(f"  {out_path}")


def save_detection_overview(trees_gdf, out_path):
    rgb, extent = _read_rgb(max_px=6000)
    fig, ax = plt.subplots(figsize=(18, 12), dpi=PUB_DPI)
    ax.imshow(rgb, extent=extent, aspect="equal")
    if len(trees_gdf) > 0:
        ax.scatter(trees_gdf.geometry.x, trees_gdf.geometry.y,
                   s=1.0, c="#00FF41", alpha=0.7, linewidths=0, zorder=4)
    ax.set_title("DeepForest + NDVI Tree Detections — City of Davis, CA",
                 fontsize=18, fontweight="bold", pad=14)
    ax.set_xlabel("Longitude", fontsize=13)
    ax.set_ylabel("Latitude",  fontsize=13)
    ax.tick_params(labelsize=11)
    _annotate_count(ax, f"{len(trees_gdf):,} trees detected")
    plt.tight_layout()
    plt.savefig(out_path, dpi=PUB_DPI, bbox_inches="tight")
    plt.close()
    print(f"  {out_path}")


def save_visualizations(trees_gdf, boxes_gdf):
    os.makedirs(VIZ_DIR, exist_ok=True)
    print("\nSaving publication figures ...")
    save_raw_overview(os.path.join(VIZ_DIR, "01_raw_naip_davis.png"))
    save_detection_overview(trees_gdf, os.path.join(VIZ_DIR, "02_detections_overview.png"))
    print("Detection figures saved.\n")


detect_trees()
