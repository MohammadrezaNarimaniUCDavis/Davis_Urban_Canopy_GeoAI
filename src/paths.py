"""Repository paths (no personal absolute directories)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BOUNDARY = DATA / "boundary" / "davis_city_boundary.shp"
DERIVED = DATA / "derived"
REFERENCE = DATA / "reference"
RESULTS = ROOT / "results"
TABLES = RESULTS / "tables"
FIGURES = RESULTS / "figures"

ENRICHED_CSV = DERIVED / "cell_context_enriched.csv"
FAIR_METRICS_CSV = DERIVED / "fair_comparison_metrics_tiger.csv"
CANOPY_MASK = DERIVED / "canopy_mask.tif"
TREES_GEOJSON = DERIVED / "trees.geojson"
TREES_BOXES_GEOJSON = DERIVED / "trees_boxes.geojson"
USDA_CANOPY = REFERENCE / "Davis_canopy2022.tif"
LST_TIF = DERIVED / "davis_lst_landsat.tif"
ROADS_GEOJSON = DERIVED / "davis_street_centerlines_yolo.geojson"


def ensure_output_dirs() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
