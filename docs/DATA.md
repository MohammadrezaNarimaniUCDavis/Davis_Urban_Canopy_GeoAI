# Data guide

## Shipped with this GitHub repository

| Path | Description |
|---|---|
| `data/boundary/davis_city_boundary.*` | Census TIGER Place boundary for Davis, CA (official analysis extent, ~25.9 km²) |
| `data/derived/cell_context_enriched.csv` | 100 m cell table used for spatial statistics and screening maps |
| `data/derived/fair_comparison_metrics_tiger.csv` | Locked fair USDA comparison metrics |
| `results/tables/*.csv` | Precomputed Spearman / Moran / model / KW tables |

## From Zenodo (required for full replication)

Download the deposit (`https://doi.org/10.5281/zenodo.XXXXXXX`) and place files as:

```
data/
  raw/
    davis_naip_2022.tif   # USDA NAIP 2022 RGB+NIR (~581 MB), clipped to TIGER city
  boundary/               # already on GitHub; identical copy in Zenodo
  derived/
    canopy_mask.tif
    trees.geojson
    trees_boxes.geojson
    davis_lst_landsat.tif
    davis_street_centerlines_yolo.geojson
    grid_summary_100m.csv
    cell_context_enriched.csv
    fair_comparison_metrics_tiger.csv
    tables_academic/      # optional duplicate of results/tables
  reference/
    Davis_canopy2022.tif
```

The NAIP mosaic is **on Zenodo only** (too large for the GitHub code repo). It can also be re-downloaded with `scripts/pipeline/01_download_naip.py` if needed.

## External sources (context layers)

| Product | Access | Role |
|---|---|---|
| USDA NAIP 2022 | Zenodo deposit **or** GEE `USDA/NAIP/DOQQ` | Optical input |
| USDA / CAL FIRE urban canopy 2022 | Zenodo `reference/` | Reference canopy |
| Landsat LST | Zenodo `derived/` (or GEE) | Surface temperature |
| Dynamic World | GEE | Built fraction |
| ACS / census | Census API / ACS tables | Population, poverty, income proxies |
| Local roads / bikeways / parks | City of Davis / Yolo GIS / OSM | Context layers |
| Census TIGER Places | Census Bureau / `data/boundary/` | Municipal extent |

## What we intentionally do **not** share

- Full private working repository (manuscript drafts, scratch notebooks, intermediate dumps)
- Personal absolute paths, API keys, GEE service-account JSON
- Regenerable figure PNGs (scripts recreate them)
