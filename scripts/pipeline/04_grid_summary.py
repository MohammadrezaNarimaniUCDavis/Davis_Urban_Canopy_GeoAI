"""
Script 04 — 100 m grid summary and pipeline figures
=====================================================
Run after 03_segment_trees.py.

Outputs:
  data/derived/analysis/summary.csv (and related rasters)
  results/figures/pipeline/
"""

import os
import numpy as np
import rasterio
import rasterio.features
import rasterio.mask
import rasterio.windows
from rasterio.windows import from_bounds as win_from_bounds
import geopandas as gpd
from shapely.geometry import box as shapely_box
from matplotlib.patches import Rectangle
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pyproj import Transformer

from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
# ---------------------------------------------------------------------------
# Configuration (paths relative to repository root)
# ---------------------------------------------------------------------------
TREES_GEOJSON = str(ROOT / "data/derived/detections/trees.geojson")
BOXES_GEOJSON = str(ROOT / "data/derived/detections/trees_boxes.geojson")
MASK_TIF      = str(ROOT / "data/derived/segments/canopy_mask.tif")
SOURCE_TIF    = str(ROOT / "data/raw/davis_naip_2022.tif")
BOUNDARY_SHP  = str(ROOT / "data/boundary/davis_city_boundary.shp")
OUTPUT_DIR    = str(ROOT / "data/derived/analysis")
VIZ_DIR       = str(ROOT / "results/figures/pipeline")
GRID_SIZE_M   = 100
PUB_DPI       = 300
N_ZOOM        = 2
ZOOM_HALF_DEG = 0.0025
# ---------------------------------------------------------------------------


# ── Analysis helpers ─────────────────────────────────────────────────────────

def get_utm_bounds(source_tif):
    with rasterio.open(source_tif) as src:
        bounds  = src.bounds
        src_crs = src.crs
    t = Transformer.from_crs(src_crs, "EPSG:32610", always_xy=True)
    w, s = t.transform(bounds.left,  bounds.bottom)
    e, n = t.transform(bounds.right, bounds.top)
    return w, s, e, n


def build_grid(west, south, east, north, cell_size_m, crs="EPSG:32610"):
    rows    = []
    cell_id = 0
    y = south
    while y < north:
        x = west
        while x < east:
            rows.append({
                "cell_id":  cell_id,
                "geometry": shapely_box(x, y,
                                        min(x + cell_size_m, east),
                                        min(y + cell_size_m, north)),
            })
            cell_id += 1
            x += cell_size_m
        y += cell_size_m
    return gpd.GeoDataFrame(rows, crs=crs)


def count_points_in_cells(grid, points_gdf):
    # Join points→cells (inner) so each tree is counted in exactly one cell.
    # The previous grid→points LEFT join counted every empty cell as 1 tree.
    pts    = points_gdf.to_crs(grid.crs)
    joined = gpd.sjoin(pts, grid, how="inner", predicate="within")
    counts = joined.groupby("cell_id").size().reset_index(name="tree_count")
    result = grid.merge(counts, on="cell_id", how="left")
    result["tree_count"] = result["tree_count"].fillna(0).astype(int)
    return result


def compute_canopy_fraction_per_cell(grid, mask_tif_path):
    """Canopy fraction = (#pixels==1) / (#pixels in cell). Counts canopy(1) against
    ALL pixels (canopy + background 0); does not rely on the file's nodata value."""
    fractions = []
    with rasterio.open(mask_tif_path) as src:
        grid_src = grid.to_crs(src.crs)
        for i, (_, cell) in enumerate(grid_src.iterrows()):
            if i % 500 == 0:
                print(f"  Canopy fraction: {i}/{len(grid_src)} cells", end="\r")
            geom = [cell.geometry.__geo_interface__]
            try:
                # filled=False → masked array marks pixels outside the cell polygon
                out, _ = rasterio.mask.mask(src, geom, crop=True, filled=False)
                band   = out[0]
                inside = ~np.ma.getmaskarray(band)
                total  = int(inside.sum())
                canopy = int(((band.data == 1) & inside).sum())
                frac   = canopy / total if total > 0 else 0.0
            except Exception:
                frac = 0.0
            fractions.append(frac)
    result = grid.copy()
    result["canopy_frac"] = fractions
    return result


def rasterize_grid_values(grid, value_col, source_tif, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with rasterio.open(source_tif) as src:
        profile  = src.profile.copy()
        profile.update(count=1, dtype="float32", nodata=-9999.0)
        grid_src = grid.to_crs(src.crs)
        shapes   = list(zip(
            grid_src.geometry,
            grid_src[value_col].fillna(-9999).astype(float),
        ))
        out = rasterio.features.rasterize(
            shapes,
            out_shape=(src.height, src.width),
            transform=src.transform,
            fill=-9999.0,
            dtype=np.float32,
        )
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(out, 1)
    print(f"  Saved {output_path}")


# ── Main analysis ────────────────────────────────────────────────────────────

def run_analysis():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(VIZ_DIR,    exist_ok=True)

    print("Loading tree detections ...")
    trees = gpd.read_file(TREES_GEOJSON).to_crs("EPSG:32610")
    print(f"  {len(trees):,} trees")

    if len(trees) == 0:
        print("No trees detected — skipping analysis.")
        return

    print("Building 100 m analysis grid ...")
    w, s, e, n = get_utm_bounds(SOURCE_TIF)
    grid = build_grid(w, s, e, n, cell_size_m=GRID_SIZE_M, crs="EPSG:32610")
    print(f"  {len(grid):,} cells ({GRID_SIZE_M} m × {GRID_SIZE_M} m)")

    print("Clipping grid to Davis city boundary ...")
    boundary = gpd.read_file(BOUNDARY_SHP).to_crs("EPSG:32610")
    grid = gpd.clip(grid, boundary).reset_index(drop=True)
    grid = grid[~grid.geometry.is_empty]
    print(f"  {len(grid):,} cells within boundary")

    print("Counting trees per cell ...")
    grid = count_points_in_cells(grid, trees)

    print("Computing canopy fraction per cell ...")
    grid = compute_canopy_fraction_per_cell(grid, MASK_TIF)
    grid["canopy_pct"] = (grid["canopy_frac"] * 100).round(2)

    centroids_4326 = grid.to_crs("EPSG:4326").geometry.centroid
    grid["lon"] = centroids_4326.x.round(6)
    grid["lat"] = centroids_4326.y.round(6)

    csv_path = os.path.join(OUTPUT_DIR, "summary.csv")
    grid[["cell_id", "lon", "lat", "tree_count", "canopy_pct"]].to_csv(csv_path, index=False)
    print(f"  Saved {csv_path}")

    print("Writing GeoTIFFs ...")
    rasterize_grid_values(grid, "tree_count", SOURCE_TIF,
                          os.path.join(OUTPUT_DIR, "density_map.tif"))
    rasterize_grid_values(grid, "canopy_frac", SOURCE_TIF,
                          os.path.join(OUTPUT_DIR, "canopy_coverage.tif"))

    # Area-weighted canopy cover (cells differ in size after boundary clip)
    cell_area = grid.geometry.area                      # m², EPSG:32610
    canopy_area_m2 = float((grid["canopy_frac"] * cell_area).sum())
    land_area_m2   = float(cell_area.sum())
    canopy_cover   = 100 * canopy_area_m2 / land_area_m2 if land_area_m2 else 0.0

    print("\n=== Analysis Complete ===")
    print(f"Total trees detected:    {int(grid['tree_count'].sum()):,}")
    print(f"City area analysed:      {land_area_m2/1e6:.2f} km²")
    print(f"Canopy area:             {canopy_area_m2/1e6:.2f} km²")
    print(f"Canopy cover:            {canopy_cover:.1f}%")

    stats = {
        # authoritative detection count (every detection is already boundary-clipped
        # in script 02); grid['tree_count'].sum() can be a hair lower due to cells
        # trimmed at the boundary, so report the true count on the figures.
        "tree_count":   len(trees),
        "canopy_km2":   canopy_area_m2 / 1e6,
        "canopy_cover": canopy_cover,
    }
    save_visualizations(grid.to_crs("EPSG:4326"),
                        gpd.read_file(TREES_GEOJSON), stats)
    print(f"\nAll outputs in {OUTPUT_DIR}/ and {VIZ_DIR}/")


# ── Visualization helpers ────────────────────────────────────────────────────

def _read_rgb(west=None, south=None, east=None, north=None, max_px=3000):
    with rasterio.open(SOURCE_TIF) as src:
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
    with rasterio.open(MASK_TIF) as src:
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
    """Blend green over canopy pixels (mask==1)."""
    out = rgb.astype(np.float32)
    m   = (mask == 1)
    out[m, 0] = out[m, 0] * (1 - alpha)
    out[m, 1] = out[m, 1] * (1 - alpha) + 180 * alpha
    out[m, 2] = out[m, 2] * (1 - alpha)
    return np.clip(out, 0, 255).astype(np.uint8)


def _apply_color_overlay(rgb, mask, color=(170, 0, 220), alpha=0.55):
    """Blend an arbitrary RGB `color` over canopy pixels (default purple)."""
    out = rgb.astype(np.float32)
    m   = (mask == 1)
    for ch in range(3):
        out[m, ch] = out[m, ch] * (1 - alpha) + color[ch] * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def _badge(ax, text):
    """Large on-image stat badge (bottom-left)."""
    ax.text(0.015, 0.025, text, transform=ax.transAxes,
            fontsize=19, fontweight="bold", color="white", va="bottom", ha="left",
            bbox=dict(boxstyle="round,pad=0.45", facecolor="black", alpha=0.6,
                      edgecolor="white", linewidth=1.2), zorder=10)


def _load_boxes_4326():
    try:
        return gpd.read_file(BOXES_GEOJSON).to_crs("EPSG:4326")
    except Exception:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")


# ---- Heatmaps (corrected numbers) -------------------------------------------

def save_density_heatmap(grid_4326, out_path):
    fig, ax = plt.subplots(figsize=(14, 10), dpi=PUB_DPI)
    grid_4326.plot(column="tree_count", ax=ax, cmap="YlGn",
                   legend=True, edgecolor="none",
                   legend_kwds={"label": "Trees per 100 m cell", "shrink": 0.7})
    ax.set_title("Urban Tree Density — City of Davis, CA\n(NAIP 2022, 100 m grid)",
                 fontsize=16, fontweight="bold", pad=12)
    ax.set_xlabel("Longitude", fontsize=12); ax.set_ylabel("Latitude", fontsize=12)
    ax.tick_params(labelsize=10)
    plt.tight_layout(); plt.savefig(out_path, dpi=PUB_DPI, bbox_inches="tight"); plt.close()
    print(f"  {out_path}")


def save_coverage_heatmap(grid_4326, out_path):
    fig, ax = plt.subplots(figsize=(14, 10), dpi=PUB_DPI)
    grid_4326.plot(column="canopy_pct", ax=ax, cmap="Greens",
                   legend=True, edgecolor="none",
                   legend_kwds={"label": "Canopy coverage (%)", "shrink": 0.7})
    ax.set_title("Urban Canopy Coverage — City of Davis, CA\n(NAIP 2022, 100 m grid)",
                 fontsize=16, fontweight="bold", pad=12)
    ax.set_xlabel("Longitude", fontsize=12); ax.set_ylabel("Latitude", fontsize=12)
    ax.tick_params(labelsize=10)
    plt.tight_layout(); plt.savefig(out_path, dpi=PUB_DPI, bbox_inches="tight"); plt.close()
    print(f"  {out_path}")


# ---- Full-city hero figures -------------------------------------------------

def save_full_combined_map(trees_gdf, boxes_gdf, stats, out_path):
    """THE hero figure: full Davis — NAIP + SAM canopy (green) + detection boxes
    (yellow) + centroids, with the tree count and canopy stats on the image."""
    rgb, extent, shape2d = _read_rgb(max_px=8000)
    mask    = _read_mask(shape2d)
    base    = _apply_canopy_overlay(rgb, mask) if mask is not None else rgb

    fig, ax = plt.subplots(figsize=(26, 20), dpi=PUB_DPI)
    ax.imshow(base, extent=extent, aspect="equal")
    for _, box in boxes_gdf.iterrows():
        b = box.geometry.bounds
        ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1],
                               lw=0.35, edgecolor="#FFD700", facecolor="none", alpha=0.85))
    if len(trees_gdf) > 0:
        ax.scatter(trees_gdf.geometry.x, trees_gdf.geometry.y,
                   s=1.0, c="#FF1744", alpha=0.85, linewidths=0, zorder=5)
    ax.set_title("Tree Detection + Canopy Segmentation — City of Davis, CA  (NAIP 2022)\n"
                 "green = SAM+NDVI canopy · yellow = DeepForest crown box · red = centroid",
                 fontsize=19, fontweight="bold", pad=14)
    ax.set_xlabel("Longitude", fontsize=13); ax.set_ylabel("Latitude", fontsize=13)
    ax.tick_params(labelsize=11)
    _badge(ax, f"{stats['tree_count']:,} trees   |   "
               f"{stats['canopy_km2']:.2f} km² canopy ({stats['canopy_cover']:.1f}%)")
    plt.tight_layout(); plt.savefig(out_path, dpi=PUB_DPI, bbox_inches="tight"); plt.close()
    print(f"  {out_path}")


def save_full_detection_map(trees_gdf, boxes_gdf, stats, out_path):
    """Full-city NAIP with every detection box + centroid (no canopy fill)."""
    rgb, extent, _ = _read_rgb(max_px=8000)
    fig, ax = plt.subplots(figsize=(26, 20), dpi=PUB_DPI)
    ax.imshow(rgb, extent=extent, aspect="equal")
    for _, box in boxes_gdf.iterrows():
        b = box.geometry.bounds
        ax.add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1],
                               lw=0.35, edgecolor="#FFD700", facecolor="none", alpha=0.9))
    if len(trees_gdf) > 0:
        ax.scatter(trees_gdf.geometry.x, trees_gdf.geometry.y,
                   s=1.2, c="#00FF41", alpha=0.8, linewidths=0, zorder=5)
    ax.set_title("DeepForest + NDVI Tree Detections — City of Davis, CA\n"
                 "yellow = crown box, green = centroid",
                 fontsize=20, fontweight="bold", pad=14)
    ax.set_xlabel("Longitude", fontsize=13); ax.set_ylabel("Latitude", fontsize=13)
    ax.tick_params(labelsize=11)
    _badge(ax, f"{stats['tree_count']:,} trees detected")
    plt.tight_layout(); plt.savefig(out_path, dpi=PUB_DPI, bbox_inches="tight"); plt.close()
    print(f"  {out_path}")


def save_full_mask_map(stats, out_path):
    """Full-city NAIP with the SAM+NDVI canopy mask painted in purple."""
    rgb, extent, shape2d = _read_rgb(max_px=8000)
    mask = _read_mask(shape2d)
    if mask is None:
        print("  (skipped full mask map — canopy_mask.tif not found)")
        return
    overlay = _apply_color_overlay(rgb, mask, color=(170, 0, 220), alpha=0.55)
    fig, ax = plt.subplots(figsize=(26, 20), dpi=PUB_DPI)
    ax.imshow(overlay, extent=extent, aspect="equal")
    ax.set_title("SAM + NDVI Canopy Segmentation — City of Davis, CA\n"
                 "purple = segmented tree canopy",
                 fontsize=20, fontweight="bold", pad=14)
    ax.set_xlabel("Longitude", fontsize=13); ax.set_ylabel("Latitude", fontsize=13)
    ax.tick_params(labelsize=11)
    _badge(ax, f"{stats['canopy_km2']:.2f} km² canopy ({stats['canopy_cover']:.1f}%)")
    plt.tight_layout(); plt.savefig(out_path, dpi=PUB_DPI, bbox_inches="tight"); plt.close()
    print(f"  {out_path}")


# ---- Auto-selected high-density zoom insets ---------------------------------

def pick_zoom_centers(grid_4326, n, min_sep_deg=0.012):
    g = grid_4326.sort_values("tree_count", ascending=False)
    centers = []
    for _, row in g.iterrows():
        if row["tree_count"] <= 0:
            break
        c = row.geometry.centroid
        if all(((c.x - px) ** 2 + (c.y - py) ** 2) ** 0.5 > min_sep_deg for px, py in centers):
            centers.append((c.x, c.y))
        if len(centers) >= n:
            break
    return centers


def save_zoom_insets(grid_4326, trees_gdf, boxes_gdf):
    """A couple of detailed insets at the densest tree clusters: raw vs detections+canopy."""
    centers = pick_zoom_centers(grid_4326, N_ZOOM)
    for i, (clon, clat) in enumerate(centers, 1):
        h = ZOOM_HALF_DEG
        w, s, e, n = clon - h, clat - h, clon + h, clat + h
        rgb, extent, shape2d = _read_rgb(west=w, south=s, east=e, north=n, max_px=2500)
        if rgb is None:
            continue
        mask    = _read_mask(shape2d, west=w, south=s, east=e, north=n)
        overlay = _apply_canopy_overlay(rgb, mask) if mask is not None else rgb

        win = shapely_box(w, s, e, n)
        pts = trees_gdf[trees_gdf.intersects(win)] if len(trees_gdf) else trees_gdf
        bxs = boxes_gdf[boxes_gdf.intersects(win)] if len(boxes_gdf) else boxes_gdf

        fig, axes = plt.subplots(1, 2, figsize=(18, 8), dpi=PUB_DPI)
        fig.suptitle(f"High-Density Detail #{i}  ({len(pts):,} trees in frame)",
                     fontsize=15, fontweight="bold", y=1.0)
        axes[0].imshow(rgb, extent=extent, aspect="equal")
        axes[0].set_title("NAIP 2022 (True Color)", fontsize=13, pad=8)
        axes[0].set_ylabel("Latitude", fontsize=10)

        axes[1].imshow(overlay, extent=extent, aspect="equal")
        for _, box in bxs.iterrows():
            b = box.geometry.bounds
            axes[1].add_patch(Rectangle((b[0], b[1]), b[2] - b[0], b[3] - b[1],
                                        lw=1.0, edgecolor="#FFD700", facecolor="none", alpha=0.9))
        if len(pts) > 0:
            axes[1].scatter(pts.geometry.x, pts.geometry.y,
                            s=10, c="#FF1744", alpha=0.9, linewidths=0, zorder=5)
        axes[1].set_title("Detections (boxes+centroids) + SAM/NDVI canopy", fontsize=13, pad=8)

        for ax in axes:
            ax.set_xlabel("Longitude", fontsize=10)
            ax.tick_params(labelsize=9)
        plt.tight_layout()
        out_path = os.path.join(VIZ_DIR, f"11_zoom_inset_{i}.png")
        plt.savefig(out_path, dpi=PUB_DPI, bbox_inches="tight")
        plt.close()
        print(f"  {out_path}")


def save_visualizations(grid_4326, trees_gdf, stats):
    os.makedirs(VIZ_DIR, exist_ok=True)
    boxes_gdf = _load_boxes_4326()
    print("\nSaving publication figures ...")
    save_density_heatmap( grid_4326, os.path.join(VIZ_DIR, "06_density_heatmap.png"))
    save_coverage_heatmap(grid_4326, os.path.join(VIZ_DIR, "07_coverage_heatmap.png"))
    save_full_combined_map(trees_gdf, boxes_gdf, stats, os.path.join(VIZ_DIR, "08_full_combined.png"))
    save_full_detection_map(trees_gdf, boxes_gdf, stats, os.path.join(VIZ_DIR, "09_full_detections.png"))
    save_full_mask_map(stats, os.path.join(VIZ_DIR, "10_full_canopy_purple.png"))
    save_zoom_insets(grid_4326, trees_gdf, boxes_gdf)
    print("Analysis figures saved.\n")


run_analysis()
