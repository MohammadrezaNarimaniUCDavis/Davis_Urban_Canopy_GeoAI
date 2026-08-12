"""
Spatial association suite for Davis 100 m canopy cells.

Reproduces the manuscript statistical core from cell_context_enriched.csv:
  - Spearman screen with Benjamini-Hochberg FDR
  - Global Moran's I (KNN-8)
  - OLS + residual Moran
  - Spatial lag / spatial error (GMM)
  - Kruskal-Wallis by poverty / income quintiles
  - Partial Spearman canopy-LST | built

Associations only — not causal claims; not an official Tree Equity Score.
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from esda.moran import Moran
from libpysal.weights import KNN
from scipy import stats
from shapely.geometry import box as shapely_box
from spreg import GM_Error, GM_Lag, OLS
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.paths import BOUNDARY, ENRICHED_CSV, TABLES, ensure_output_dirs  # noqa: E402

K_NEIGHBORS = 8
Y_COL = "canopy_pct"
CORE_X = ["lst_c", "dw_built", "pop_density", "poverty"]
ALL_SCREEN = [
    "canopy_pct",
    "tree_count",
    "lst_c",
    "dw_built",
    "road_pct",
    "sidewalk_pct",
    "pop_density",
    "poverty",
    "income_proxy",
    "value_per_acre",
    "near_park_m",
    "near_bike_m",
]
LABELS = {
    "canopy_pct": "Canopy (%)",
    "tree_count": "Tree count",
    "lst_c": "LST (C)",
    "dw_built": "DW built",
    "road_pct": "Road %",
    "sidewalk_pct": "Sidewalk %",
    "pop_density": "Pop. density",
    "poverty": "Poverty",
    "income_proxy": "Income",
    "value_per_acre": "Value/acre",
    "near_park_m": "Dist. park",
    "near_bike_m": "Dist. bike",
}


def load_enriched() -> pd.DataFrame:
    df = pd.read_csv(ENRICHED_CSV)
    if "income_proxy" in df.columns:
        df["log_income"] = np.log1p(df["income_proxy"].clip(lower=0))
    return df


def cells_gdf(df: pd.DataFrame) -> gpd.GeoDataFrame:
    g = gpd.GeoDataFrame(
        df.copy(),
        geometry=gpd.points_from_xy(df["lon"], df["lat"]),
        crs=4326,
    )
    u = g.to_crs(32610)
    half = 50.0
    u["geometry"] = [
        shapely_box(p.x - half, p.y - half, p.x + half, p.y + half) for p in u.geometry
    ]
    return u.to_crs(4326)


def knn_weights(gdf: gpd.GeoDataFrame) -> KNN:
    w = KNN.from_dataframe(gdf.to_crs(32610), k=K_NEIGHBORS, use_index=False)
    w.transform = "r"
    return w


def spearman_fdr(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    rows = []
    for c in cols:
        if c == Y_COL or c not in df.columns:
            continue
        pair = df[[Y_COL, c]].dropna()
        if len(pair) < 30:
            continue
        rho, p = stats.spearmanr(pair[Y_COL], pair[c])
        rows.append(
            {
                "variable": c,
                "label": LABELS.get(c, c),
                "rho": float(rho),
                "p": float(p),
                "n": int(len(pair)),
            }
        )
    out = pd.DataFrame(rows).sort_values("rho", key=lambda s: s.abs(), ascending=False)
    if len(out):
        _, q, _, _ = multipletests(out["p"].to_numpy(), method="fdr_bh")
        out["q_fdr"] = q
        out["stars"] = out["q_fdr"].map(
            lambda qv: "***" if qv < 0.001 else ("**" if qv < 0.01 else ("*" if qv < 0.05 else ""))
        )
    return out.reset_index(drop=True)


def global_moran(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    g = cells_gdf(df.dropna(subset=["lon", "lat"]))
    w = knn_weights(g)
    rows = []
    for c in cols:
        if c not in g.columns:
            continue
        x = g[c].to_numpy(dtype=float)
        mask = np.isfinite(x)
        if mask.sum() < 50:
            continue
        # For simplicity use complete cases on this column with KNN on full grid coords
        mi = Moran(g[c].fillna(g[c].median()).to_numpy(dtype=float), w, permutations=999)
        rows.append({"variable": c, "label": LABELS.get(c, c), "I": float(mi.I), "p_sim": float(mi.p_sim)})
    return pd.DataFrame(rows)


def fit_core_models(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    use = df[[Y_COL, *CORE_X, "lon", "lat"]].dropna().copy()
    g = cells_gdf(use)
    w = knn_weights(g)
    y = g[Y_COL].to_numpy(dtype=float)
    x = g[CORE_X].to_numpy(dtype=float)
    name_x = CORE_X

    ols = OLS(y, x, name_y=Y_COL, name_x=name_x, white_test=True)
    resid = np.asarray(ols.u).ravel()
    mi = Moran(resid, w, permutations=999)

    lag = GM_Lag(y, x, w=w, name_y=Y_COL, name_x=name_x)
    err = GM_Error(y, x, w=w, name_y=Y_COL, name_x=name_x)

    fit = pd.DataFrame(
        [
            {
                "model_set": "core",
                "n": len(use),
                "ols_r2": float(ols.r2),
                "moran_resid_I": float(mi.I),
                "moran_resid_p": float(mi.p_sim),
                "lag_rho": float(lag.rho) if hasattr(lag, "rho") else np.nan,
                "preferred": "SpatialLag" if mi.p_sim < 0.05 else "OLS",
            }
        ]
    )

    def coef_table(model, tag: str) -> pd.DataFrame:
        names = list(model.name_x)
        betas = np.asarray(model.betas).ravel()
        se = np.asarray(model.std_err).ravel() if hasattr(model, "std_err") else np.full_like(betas, np.nan)
        # t/p availability varies; keep beta/se
        rows = []
        for i, nm in enumerate(names):
            rows.append({"model": tag, "variable": nm, "coef": float(betas[i]), "se": float(se[i]) if i < len(se) else np.nan})
        return pd.DataFrame(rows)

    coefs = pd.concat(
        [coef_table(ols, "OLS"), coef_table(lag, "SpatialLag"), coef_table(err, "SpatialError")],
        ignore_index=True,
    )
    return fit, coefs


def kruskal_quintiles(df: pd.DataFrame, by: str) -> pd.DataFrame:
    d = df[[Y_COL, by]].dropna().copy()
    d["q"] = pd.qcut(d[by], 5, labels=False, duplicates="drop")
    groups = [g[Y_COL].to_numpy() for _, g in d.groupby("q")]
    if len(groups) < 2:
        return pd.DataFrame()
    h, p = stats.kruskal(*groups)
    n = len(d)
    eps2 = (h - len(groups) + 1) / (n - len(groups)) if n > len(groups) else np.nan
    return pd.DataFrame([{"by": by, "H": float(h), "p": float(p), "epsilon2": float(eps2), "n": n}])


def partial_spearman(df: pd.DataFrame, x: str, y: str, covar: str) -> pd.DataFrame:
    d = df[[x, y, covar]].dropna()
    rx = stats.rankdata(d[x])
    ry = stats.rankdata(d[y])
    rz = stats.rankdata(d[covar])
    # residualize ranks
    def resid(a, b):
        slope, intercept, *_ = stats.linregress(b, a)
        return a - (intercept + slope * b)

    r, p = stats.spearmanr(resid(rx, rz), resid(ry, rz))
    return pd.DataFrame([{"x": x, "y": y, "covar": covar, "n": len(d), "spearman_partial": float(r), "p": float(p)}])


def main() -> None:
    ensure_output_dirs()
    if not ENRICHED_CSV.exists():
        raise FileNotFoundError(
            f"Missing {ENRICHED_CSV}. Place Zenodo derived files under data/derived/ first."
        )
    df = load_enriched()
    print(f"Loaded {len(df)} cells from {ENRICHED_CSV.name}")

    sp = spearman_fdr(df, ALL_SCREEN)
    sp.to_csv(TABLES / "spearman_vs_canopy.csv", index=False)
    print("Wrote spearman_vs_canopy.csv")

    mor = global_moran(df, [Y_COL, *CORE_X, "income_proxy", "value_per_acre", "near_park_m", "near_bike_m"])
    mor.to_csv(TABLES / "moran_global.csv", index=False)
    print("Wrote moran_global.csv")

    fit, coefs = fit_core_models(df)
    fit.to_csv(TABLES / "model_fit_summary.csv", index=False)
    coefs.to_csv(TABLES / "coefs_core.csv", index=False)
    print("Wrote model_fit_summary.csv / coefs_core.csv")

    kw = pd.concat(
        [
            kruskal_quintiles(df, "poverty"),
            kruskal_quintiles(df, "income_proxy"),
        ],
        ignore_index=True,
    )
    kw.to_csv(TABLES / "kruskal_wallis_summary.csv", index=False)

    part = partial_spearman(df, "canopy_pct", "lst_c", "dw_built")
    part.to_csv(TABLES / "partial_canopy_lst.csv", index=False)
    print("Done. Tables in", TABLES)


if __name__ == "__main__":
    main()
