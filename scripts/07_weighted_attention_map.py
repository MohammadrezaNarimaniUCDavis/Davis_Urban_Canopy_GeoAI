"""
Spearman-informed weighted attention map.

Why each layer: weight = |Spearman ρ| with canopy (from the academic heatmap).
Layers with ~0 association (road %, sidewalk %) are dropped.
Need direction = planning screen (low canopy, hot, higher poverty, ...).

Outputs:
  results/figures/04a_spearman_weights.png
  results/figures/04b_weighted_attention_map.png
  results/tables/spearman_weights.csv
  docs/WEIGHTS.md
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "shade_maps", Path(__file__).resolve().parent / "06_shade_attention_maps.py"
)
sm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm)

ROOT = Path(__file__).resolve().parents[1]
FIG = sm.FIG
TAB = ROOT / "results" / "tables"
ENRICHED = sm.ENRICHED
PUB_DPI = sm.PUB_DPI
OUT = ROOT / "results"

# factor: (label, need_direction)
# need_direction: +1 = higher raw value => higher attention; -1 = invert
FACTORS = {
    "canopy_pct": ("Canopy (%)", -1),          # low canopy => attention
    "lst_c": ("LST (°C)", +1),                 # hot => attention
    "value_per_acre": ("Value/acre", -1),      # ρ negative with canopy; low value areas differ — use low value as market-context need
    "dw_built": ("DW built", +1),              # more built fabric => shade relevance
    "pop_density": ("Pop. density", +1),       # more people exposed
    "poverty": ("Poverty", +1),                # equity screen
    "income_proxy": ("Income", -1),            # lower income => attention
    "near_park_m": ("Dist. park", +1),         # farther from parks => attention
    "near_bike_m": ("Dist. bike", +1),         # farther from bike network
}

# Dropped from map (shown as near-zero in heatmap)
DROPPED = {
    "tree_count": "Almost the same as canopy (|ρ|≈0.90) — redundant",
    "road_pct": "|ρ|≈0 with canopy — no weight",
    "sidewalk_pct": "|ρ|≈0 with canopy — no weight",
}

MIN_ABS_RHO = 0.05  # skip essentially null associations


def spearman_vs_canopy(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col, (label, direction) in FACTORS.items():
        if col == "canopy_pct":
            # self: give strong fixed role via max of others after first pass
            rows.append(
                {
                    "variable": col,
                    "label": label,
                    "direction": direction,
                    "rho": 1.0,
                    "abs_rho": 1.0,
                }
            )
            continue
        pair = df[["canopy_pct", col]].dropna()
        if len(pair) < 30:
            continue
        r, _ = stats.spearmanr(pair["canopy_pct"], pair[col])
        rows.append(
            {
                "variable": col,
                "label": label,
                "direction": direction,
                "rho": float(r),
                "abs_rho": float(abs(r)),
            }
        )
    w = pd.DataFrame(rows)
    # Canopy weight = max |ρ| among others so it leads but doesn't dominate 100%
    other_max = w.loc[w["variable"] != "canopy_pct", "abs_rho"].max()
    w.loc[w["variable"] == "canopy_pct", "abs_rho"] = float(other_max)
    w.loc[w["variable"] == "canopy_pct", "rho"] = -float(other_max)  # inverted need
    w = w[w["abs_rho"] >= MIN_ABS_RHO].copy()
    w["weight"] = w["abs_rho"] / w["abs_rho"].sum()
    w = w.sort_values("weight", ascending=False).reset_index(drop=True)
    return w


def need_01(series: pd.Series, direction: int) -> pd.Series:
    x = pd.to_numeric(series, errors="coerce")
    # percentile rank 0-1
    r = x.rank(pct=True)
    return r if direction > 0 else (1.0 - r)


def plot_weights(w: pd.DataFrame, out: Path):
    from matplotlib.colors import LinearSegmentedColormap, Normalize

    # Same grey→red intensity as shade / Spearman heatmap
    cmap = LinearSegmentedColormap.from_list(
        "grey_red",
        ["#d9d9d9", "#ef8a62", "#b2182b"],
    )
    wts = (w["weight"] * 100).to_numpy()
    norm = Normalize(vmin=0.0, vmax=max(16.0, float(wts.max())))
    colors = [cmap(norm(v)) for v in wts]

    fig, ax = plt.subplots(figsize=(9.0, 6.2))
    y = np.arange(len(w))
    ax.barh(y, wts, color=colors, edgecolor="#666666", linewidth=0.4, height=0.72)
    ax.set_yticks(y)
    ax.set_yticklabels(
        [f"{lab}  (|ρ|={a:.2f})" for lab, a in zip(w["label"], w["abs_rho"])],
        fontsize=10,
    )
    ax.invert_yaxis()
    ax.set_xlabel("Weight in attention map (%)", fontsize=11)
    ax.set_title("Why these layers? Weights from |Spearman ρ| with canopy", fontsize=12, pad=10)
    ax.set_xlim(0, max(wts) * 1.18)
    ax.set_ylim(len(w) - 0.5, -0.5)
    for yi, wt in zip(y, wts):
        ax.text(wt + 0.35, yi, f"{wt:.1f}%", va="center", fontsize=9.5, color="#222222")

    # Full frame (all four spines), light grid for intensity reading
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(True)
        ax.spines[side].set_color("#444444")
        ax.spines[side].set_linewidth(1.0)
    ax.grid(axis="x", color="#dddddd", lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)

    ax.text(
        0.0,
        -0.12,
        "Darker red = stronger canopy association / larger weight. "
        "Road & sidewalk ~0 → omitted. No age layer in this dataset.",
        transform=ax.transAxes,
        fontsize=8.5,
        color="#444444",
    )
    fig.tight_layout()
    fig.savefig(out, dpi=PUB_DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_md(path: Path, w: pd.DataFrame):
    lines = [
        "# Spearman-weighted attention map",
        "",
        "Layer weights follow |Spearman ρ| with 100 m canopy cover",
        "(see `results/tables/spearman_vs_canopy.csv`):",
        "",
        "**weight ∝ |Spearman ρ(layer, canopy)|** (normalized to 100%).",
        "",
        "| Layer | ρ vs canopy | Weight | Need direction |",
        "|---|---:|---:|---|",
    ]
    for _, r in w.iterrows():
        need = "higher value → more attention" if r["direction"] > 0 else "lower value → more attention"
        lines.append(
            f"| {r['label']} | {r['rho']:.3f} | {100*r['weight']:.1f}% | {need} |"
        )
    lines += [
        "",
        "## Dropped",
        "",
    ]
    for k, why in DROPPED.items():
        lines.append(f"- `{k}`: {why}")
    lines += [
        "",
        "## Not available",
        "",
        "- **Age** (and similar demographics) are not in the 100 m enriched table, so they cannot be weighted here.",
        "",
        "## Map",
        "",
        "`results/figures/04b_weighted_attention_map.png` — same visual language as the shade map,",
        "but multi-factor and Spearman-weighted. Screening only — not an official Tree Equity Score.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    TAB.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(ENRICHED)
    for c in list(FACTORS) + ["lon", "lat"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    wtab = spearman_vs_canopy(df)
    wtab.to_csv(TAB / "spearman_weights.csv", index=False)
    plot_weights(wtab, FIG / "04a_spearman_weights.png")

    city = sm.load_city()
    src = sm.cells_gdf(df.reset_index(drop=True))
    for col in wtab["variable"]:
        src[col] = sm.fill_missing_knn(src, col)

    grid = sm.full_city_grid(city)
    g = sm.transfer_values(grid, src, list(wtab["variable"]))
    for col in wtab["variable"]:
        g[col] = sm.fill_missing_knn(g, col)

    # weighted need score
    score = np.zeros(len(g), dtype=float)
    for _, r in wtab.iterrows():
        n01 = need_01(g[r["variable"]], int(r["direction"])).to_numpy()
        score += float(r["weight"]) * n01
    score = score - float(np.mean(score))

    ww = sm.knn_w(g)
    sm.story_map_raster(
        g,
        sm.smooth(ww, score),
        city,
        FIG / "04b_weighted_attention_map.png",
        "Spearman-weighted attention (multi-factor)",
        "Smoothed attention (relative)",
        "Weights from |ρ| with canopy (heatmap). Includes heat, built, density, poverty, income, parks, …\n"
        "Red = higher combined attention · Blue = lower. Screening only — not a Tree Equity Score.\n"
        "White notches follow the official city boundary (not missing data).",
    )

    write_md(ROOT / "docs" / "WEIGHTS.md", wtab)
    print("Weights:")
    print(wtab[["label", "rho", "weight"]].to_string(index=False))
    print(f"Wrote {FIG / '04a_spearman_weights.png'}")
    print(f"Wrote {FIG / '04b_weighted_attention_map.png'}")


if __name__ == "__main__":
    main()
