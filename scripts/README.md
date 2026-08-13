# Scripts

Run from the repository root. Paths are relative (`src/paths.py`); no personal directories.

## Core replication (uses GitHub tables)

```bash
pip install -r requirements.txt
python scripts/run_spatial_stats.py
python scripts/06_shade_attention_maps.py
python scripts/07_weighted_attention_map.py
python scripts/08_watch_zone_counts.py
```

| Script | Role |
|---|---|
| `run_spatial_stats.py` | Spearman + FDR, Moran's I, OLS / spatial lag / spatial error, Kruskal–Wallis, partial canopy–LST |
| `06_shade_attention_maps.py` | Low-canopy + high-LST screening surface |
| `07_weighted_attention_map.py` | Multi-factor attention map weighted by \|ρ\| with canopy |
| `08_watch_zone_counts.py` | Quartile watch-zone cell counts |
| `05_fair_usda_compare.py` | Pixel and detection agreement vs USDA canopy on the TIGER extent (needs Zenodo rasters) |

## Optional optical pipeline (needs NAIP + GPU recommended)

```bash
pip install -r requirements-pipeline.txt
python scripts/pipeline/01_download_naip.py   # skip if NAIP is already in data/raw/
python scripts/pipeline/02_detect_trees.py
python scripts/pipeline/03_segment_trees.py
python scripts/pipeline/04_grid_summary.py
```
