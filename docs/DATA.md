# Data guide

Companion dataset: [https://doi.org/10.5281/zenodo.21925527](https://doi.org/10.5281/zenodo.21925527)

## Shipped with this GitHub repository

| Path | Description |
|---|---|
| `data/boundary/davis_city_boundary.*` | Census TIGER Place boundary for Davis, CA (official analysis extent, ~25.92 km²) |
| `data/derived/cell_context_enriched.csv` | 100 m cell table used for spatial statistics and screening maps |
| `data/derived/fair_comparison_metrics_tiger.csv` | Locked fair USDA comparison metrics |
| `results/tables/*.csv` | Precomputed Spearman, Moran, model, Kruskal–Wallis, and watch-zone tables |

## Unpack the Zenodo deposit

The deposit contains two files:

1. `davis_naip_2022.tif` — NAIP 2022 RGB+NIR mosaic (~581 MB)
2. `Davis_Urban_Canopy_GeoAI_derived_data.zip` — boundary, derived products, USDA reference

Copy them into this repository as:

```
data/
  raw/davis_naip_2022.tif
  boundary/                 # already on GitHub; identical copy in the zip
  derived/
    canopy_mask.tif
    trees.geojson
    trees_boxes.geojson
    davis_lst_landsat.tif
    davis_street_centerlines_yolo.geojson
    grid_summary_100m.csv
    cell_context_enriched.csv
    fair_comparison_metrics_tiger.csv
  reference/
    Davis_canopy2022.tif
```

Then:

```bash
python scripts/05_fair_usda_compare.py
python scripts/run_spatial_stats.py
```

## External sources (context layers)

| Product | Access | Role |
|---|---|---|
| USDA NAIP 2022 | Zenodo **or** GEE `USDA/NAIP/DOQQ` | Optical input |
| USDA / CAL FIRE urban canopy 2022 | Zenodo `reference/` | Reference canopy |
| Landsat LST | Zenodo `derived/` | Surface temperature |
| Dynamic World | GEE | Built fraction (already joined in the enriched table) |
| ACS / census | Census Bureau | Population, poverty, income proxies (in the enriched table) |
| Local roads / bikeways / parks | City of Davis / Yolo GIS / OSM | Context layers (summarized in the enriched table) |
| Census TIGER Places | `data/boundary/` | Municipal extent |

## What this repository does not include

- The private working archive (manuscript drafts, notebooks, intermediate dumps)
- Personal paths, API keys, or Earth Engine service-account JSON
- Regenerable figure PNGs (scripts recreate them under `results/figures/`)
