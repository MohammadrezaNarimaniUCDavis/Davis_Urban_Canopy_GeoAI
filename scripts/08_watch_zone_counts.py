"""
Watch-zone cell counts from the 100 m enriched table.

Quartile screens (city cells):
  low canopy = canopy_pct <= 25th percentile
  hot        = lst_c >= 75th percentile
  higher poverty = poverty >= 75th percentile

Watch zone = low canopy AND hot.
Watch + higher poverty = watch zone AND higher poverty.

Output: results/tables/story_class_counts.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.paths import ENRICHED_CSV, TABLES, ensure_output_dirs  # noqa: E402


def classify(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for c in ("canopy_pct", "lst_c", "poverty"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    c25 = d["canopy_pct"].quantile(0.25)
    t75 = d["lst_c"].quantile(0.75)
    p75 = d["poverty"].quantile(0.75)
    d["low_canopy"] = d["canopy_pct"] <= c25
    d["hot"] = d["lst_c"] >= t75
    d["high_poverty"] = d["poverty"] >= p75
    d["watch"] = d["low_canopy"] & d["hot"]
    d["watch_equity"] = d["watch"] & d["high_poverty"]

    def bucket(row):
        if bool(row["watch_equity"]):
            return "Watch + higher poverty"
        if bool(row["watch"]):
            return "Watch zone (low canopy + hot)"
        if bool(row["low_canopy"]):
            return "Low canopy only"
        if bool(row["hot"]):
            return "Hot only"
        return "Neither (more typical)"

    d["story_class"] = d.apply(bucket, axis=1)
    return d


def main() -> None:
    ensure_output_dirs()
    if not ENRICHED_CSV.exists():
        raise FileNotFoundError(f"Missing {ENRICHED_CSV}")
    d = classify(pd.read_csv(ENRICHED_CSV))
    n = len(d)
    counts = (
        d["story_class"]
        .value_counts()
        .rename_axis("story_class")
        .reset_index(name="n")
    )
    counts["pct"] = 100.0 * counts["n"] / n
    order = [
        "Neither (more typical)",
        "Low canopy only",
        "Hot only",
        "Watch zone (low canopy + hot)",
        "Watch + higher poverty",
    ]
    counts["story_class"] = pd.Categorical(counts["story_class"], categories=order, ordered=True)
    counts = counts.sort_values("story_class")
    out = TABLES / "story_class_counts.csv"
    counts.to_csv(out, index=False)
    print(f"Wrote {out} (n={n})")
    print(counts.to_string(index=False))


if __name__ == "__main__":
    main()
