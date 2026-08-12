"""
2-3 story maps in the same style as the smoothed OLS residual figure.

1) Canopy vs expected (OLS residual) — places with more/less trees than
   heat + built + density + poverty would suggest
2) Heat vs canopy — places hotter/cooler than tree cover (+ built) suggests
3) Shade-attention surface — continuous low-canopy + high-heat score (smoothed)

Outputs: results/figures/
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from libpysal.weights import KNN, lag_spatial
from shapely.geometry import box as shapely_box
from shapely.ops import unary_union
from spreg import OLS

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "results" / "figures"
ENRICHED = ROOT / "data" / "derived" / "cell_context_enriched.csv"
BOUNDARY = ROOT / "data" / "boundary" / "davis_city_boundary.shp"
PUB_DPI = 300
K = 8


def load_city():
    city = gpd.read_file(BOUNDARY)
    if city.crs is None:
        city = city.set_crs(4326)
    return city.to_crs(4326)


def cells_gdf(df: pd.DataFrame) -> gpd.GeoDataFrame:
    g = gpd.GeoDataFrame(df.copy(), geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=4326)
    u = g.to_crs(32610)
    half = 50.0
    u["geometry"] = [shapely_box(p.x - half, p.y - half, p.x + half, p.y + half) for p in u.geometry]
    return u.to_crs(4326)


def knn_w(gdf: gpd.GeoDataFrame):
    w = KNN.from_dataframe(gdf.to_crs(32610), k=K, use_index=False)
    w.transform = "r"
    return w


def smooth(w, x: np.ndarray) -> np.ndarray:
    return np.asarray(lag_spatial(w, x), dtype=float)


def fill_missing_knn(gdf: gpd.GeoDataFrame, col: str, rounds: int = 8) -> pd.Series:
    """Fill NaNs with KNN-neighbor means so maps have no holes inside the city grid."""
    g = gdf.reset_index(drop=True).copy()
    x = pd.to_numeric(g[col], errors="coerce").astype(float).values.copy()
    if np.isfinite(x).all():
        return pd.Series(x, index=g.index)
    w = knn_w(g)
    for _ in range(rounds):
        miss = ~np.isfinite(x)
        if not miss.any():
            break
        # lag_spatial needs finite values; temporarily fill miss with nanmean for lag calc
        tmp = x.copy()
        tmp[miss] = np.nanmean(x[np.isfinite(x)])
        neigh = np.asarray(lag_spatial(w, tmp), dtype=float)
        x[miss] = neigh[miss]
    # any leftover -> global mean
    if (~np.isfinite(x)).any():
        x[~np.isfinite(x)] = np.nanmean(x[np.isfinite(x)])
    return pd.Series(x, index=g.index)


def fit_resid(y: np.ndarray, X: np.ndarray, names: list[str], w):
    ols = OLS(
        y.reshape((-1, 1)),
        X,
        w=w,
        name_y="y",
        name_x=names,
        spat_diag=False,
        moran=False,
    )
    return np.asarray(ols.u).ravel()


def story_map_raster(
    gdf: gpd.GeoDataFrame,
    values: np.ndarray,
    city,
    out: Path,
    title: str,
    cbar_label: str,
    footnote: str,
    res_m: float = 25.0,
):
    """Continuous surface filling the city polygon (no interior holes)."""
    from matplotlib.colors import LinearSegmentedColormap
    from scipy.interpolate import NearestNDInterpolator
    from shapely.geometry import box as sbox

    city_utm = city.to_crs(32610)
    g_utm = gdf.to_crs(32610)
    u = city_utm.union_all() if hasattr(city_utm, "union_all") else unary_union(city_utm.geometry)
    minx, miny, maxx, maxy = u.bounds
    pad = res_m * 2
    minx, miny, maxx, maxy = minx - pad, miny - pad, maxx + pad, maxy + pad
    width = int(np.ceil((maxx - minx) / res_m))
    height = int(np.ceil((maxy - miny) / res_m))

    xs = np.asarray(g_utm.geometry.centroid.x)
    ys = np.asarray(g_utm.geometry.centroid.y)
    vv = np.asarray(values, dtype=float)
    ok = np.isfinite(xs) & np.isfinite(ys) & np.isfinite(vv)
    interp = NearestNDInterpolator(np.column_stack([xs[ok], ys[ok]]), vv[ok])

    gx = minx + (np.arange(width) + 0.5) * res_m
    gy = miny + (np.arange(height) + 0.5) * res_m
    XX, YY = np.meshgrid(gx, gy)
    grid = interp(XX, YY)

    cmap = LinearSegmentedColormap.from_list(
        "gap",
        ["#2166ac", "#67a9cf", "#d9d9d9", "#ef8a62", "#b2182b"],
    )
    finite = grid[np.isfinite(grid)]
    vmax = float(np.percentile(np.abs(finite), 95)) if len(finite) else 1.0
    vmax = max(vmax, 1e-6)

    fig, ax = plt.subplots(figsize=(7.5, 6.5), facecolor="white")
    x_edges = minx + np.arange(width + 1) * res_m
    y_edges = miny + np.arange(height + 1) * res_m
    mesh = ax.pcolormesh(
        x_edges,
        y_edges,
        grid,
        cmap=cmap,
        vmin=-vmax,
        vmax=vmax,
        shading="flat",
        zorder=1,
    )

    # Mask outside city with opaque white so only the city shows color
    outside = sbox(minx - 50, miny - 50, maxx + 50, maxy + 50).difference(u)
    gpd.GeoSeries([outside], crs=32610).plot(ax=ax, color="white", edgecolor="none", zorder=2)
    city_utm.boundary.plot(ax=ax, color="#222222", lw=0.95, zorder=4)

    ax.set_xlim(u.bounds[0] - pad * 0.25, u.bounds[2] + pad * 0.25)
    ax.set_ylim(u.bounds[1] - pad * 0.25, u.bounds[3] + pad * 0.25)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.set_title(title, fontsize=12, pad=8)
    cbar = fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04, shrink=0.72)
    cbar.set_label(cbar_label)
    ax.text(
        0.5,
        -0.02,
        footnote,
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8.3,
        color="#333333",
    )
    fig.tight_layout()
    fig.savefig(out, dpi=PUB_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_readme(path: Path):
    path.write_text(
        """# Story maps (3 figures)

Same visual language as the smoothed residual map you liked.

| Figure | Plain reading |
|---|---|
| `01_more_or_less_canopy_than_expected.png` | Red = more trees than heat/built/density/poverty suggest. Blue = fewer. |
| `02_hotter_or_cooler_than_canopy_suggests.png` | Red = hotter ground than canopy (+ built) would suggest. Blue = cooler. |
| `03_shade_attention_surface.png` | Red = stronger “low canopy + hot” attention. Blue = opposite. |

All maps use KNN-8 neighbor smoothing so neighborhoods read clearly (not salt-and-pepper).
Associations only — not cause-and-effect; not an official Tree Equity Score.
""",
        encoding="utf-8",
    )


def full_city_grid(city_wgs84: gpd.GeoDataFrame, cell_m: float = 100.0) -> gpd.GeoDataFrame:
    """Regular grid clipped to city — every intersecting 100 m cell, no interior holes."""
    city = city_wgs84.to_crs(32610)
    u = city.union_all() if hasattr(city, "union_all") else unary_union(city.geometry)
    minx, miny, maxx, maxy = u.bounds
    # snap origin so cells align
    minx = np.floor(minx / cell_m) * cell_m
    miny = np.floor(miny / cell_m) * cell_m
    polys = []
    for x in np.arange(minx, maxx + cell_m, cell_m):
        for y in np.arange(miny, maxy + cell_m, cell_m):
            b = shapely_box(x, y, x + cell_m, y + cell_m)
            if not u.intersects(b):
                continue
            clipped = b.intersection(u)
            if clipped.is_empty:
                continue
            polys.append(clipped)
    g = gpd.GeoDataFrame(geometry=polys, crs=32610)
    g["cx"] = g.geometry.centroid.x
    g["cy"] = g.geometry.centroid.y
    return g.to_crs(4326)


def transfer_values(grid: gpd.GeoDataFrame, src: gpd.GeoDataFrame, cols: list[str]) -> gpd.GeoDataFrame:
    """Nearest-neighbor transfer from enriched cells onto the full city grid."""
    from scipy.spatial import cKDTree

    g = grid.copy()
    s = src.to_crs(32610)
    gg = g.to_crs(32610)
    tree = cKDTree(np.column_stack([s.geometry.centroid.x, s.geometry.centroid.y]))
    pts = np.column_stack([gg.geometry.centroid.x, gg.geometry.centroid.y])
    _, idx = tree.query(pts, k=1)
    for c in cols:
        g[c] = src.iloc[idx][c].to_numpy()
    return g


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(ENRICHED)
    for c in ["canopy_pct", "lst_c", "dw_built", "pop_density", "poverty"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    city = load_city()
    src = cells_gdf(df.reset_index(drop=True))
    # fill LST on source first
    src["lst_c"] = fill_missing_knn(src, "lst_c")
    src["canopy_pct"] = fill_missing_knn(src, "canopy_pct")

    # complete clipped grid covering whole city polygon
    grid = full_city_grid(city)
    g_all = transfer_values(grid, src, ["canopy_pct", "lst_c", "dw_built", "pop_density", "poverty"])
    g_all["lst_c"] = fill_missing_knn(g_all, "lst_c")
    g_all["canopy_pct"] = fill_missing_knn(g_all, "canopy_pct")
    print(f"Full city grid cells: {len(g_all)} (enriched source had {len(src)})")

    # --- Shade attention only (map 01 residual dropped) ---
    w3 = knn_w(g_all)
    c_need = 1.0 - pd.Series(g_all["canopy_pct"]).rank(pct=True).values
    t_need = pd.Series(g_all["lst_c"]).rank(pct=True).values
    score = 0.5 * c_need + 0.5 * t_need
    score = score - float(np.mean(score))
    story_map_raster(
        g_all,
        smooth(w3, score),
        city,
        FIG / "03_shade_attention_surface.png",
        "Shade attention: low canopy + hot surfaces",
        "Smoothed attention (relative)",
        "Red = stronger low-canopy + hot combination · Blue = more canopy and/or cooler.\n"
        "Color fills the full city polygon. White notches are outside the official boundary (not missing data).\n"
        "Planning screen only — not a Tree Equity Score.",
    )

    pass  # optional local readme skipped
    print(f"Wrote story maps to {FIG}")


if __name__ == "__main__":
    main()
