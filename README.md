# Davis Urban Canopy GeoAI

Reproducible code and derived data for optical GeoAI urban-canopy mapping in **Davis, California**, accompanying:

> *From crown candidates to neighborhood screening: integrating optical GeoAI and spatial modeling for urban-canopy assessment in Davis, California*

**Authors:** Mohammadreza Narimani, Shreyan Mitra, Parastoo Farajpoor  
**Target journal:** *Geocarto International*

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.XXXXXXX-blue.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)

> **Zenodo DOI:** placeholder — replace `XXXXXXX` after the deposit is published.

This repository is the **public replication package**. It intentionally contains only the scripts and products needed to reproduce the paper’s core results. The authors’ full working archive remains private.

---

## What this study does

1. Detect tree-crown candidates on **NAIP 2022** (DeepForest + NDVI gate).
2. Segment crowns with **SAM** and build a binary **canopy mask**.
3. Aggregate to a **100 m** grid and join urban / SES / climate context layers.
4. Compare against **USDA / CAL FIRE** canopy on the shared **Census TIGER** city extent (~25.9 km²).
5. Screen spatial **associations** (Spearman + FDR, Moran’s I, spatial lag) and build **planning screens** (shade / weighted attention).

Claims are framed as **association / co-location / screening**, not causal cooling or an official Tree Equity Score.

### Locked fair-comparison numbers (TIGER extent)

| Metric | Value |
|---|---|
| City area | ~25.92 km² |
| Our canopy | 2.43 km² (9.37%) |
| USDA canopy | 7.11 km² (27.4%) |
| Recovery | 34.2% |
| IoU / Dice | 0.288 / 0.448 |
| Detection-center precision | 0.974 |

---

## Repository layout

```
Davis_Urban_Canopy_GeoAI/
├── data/
│   ├── boundary/          # Census TIGER Davis city boundary (shipped)
│   ├── derived/           # Small tables shipped; large rasters from Zenodo
│   ├── reference/         # USDA canopy (from Zenodo)
│   └── raw/               # User-downloaded NAIP / SAM weights (not shipped)
├── scripts/
│   ├── pipeline/          # 01–04: NAIP → detect → SAM → 100 m grid
│   ├── run_spatial_stats.py
│   ├── 05_fair_usda_compare.py
│   ├── 06_shade_attention_maps.py
│   └── 07_weighted_attention_map.py
├── src/paths.py           # All I/O paths (no personal directories)
├── results/tables/        # Precomputed statistical tables (shipped)
├── docs/                  # Data sources, Zenodo upload notes
├── requirements.txt
├── CITATION.cff
└── LICENSE
```

---

## Quick start (statistics + maps)

Most reviewers only need the **enriched 100 m table** (already in `data/derived/`) plus the scripts below.

```bash
# 1. Clone
git clone https://github.com/MohammadrezaNarimaniUCDavis/Davis_Urban_Canopy_GeoAI.git
cd Davis_Urban_Canopy_GeoAI

# 2. Environment (example)
conda create -n davis-canopy python=3.11 -y
conda activate davis-canopy
pip install -r requirements.txt

# 3. Reproduce spatial statistics
python scripts/run_spatial_stats.py

# 4. Shade / weighted attention maps
python scripts/06_shade_attention_maps.py
python scripts/07_weighted_attention_map.py
```

### Full fair USDA comparison (needs Zenodo rasters)

1. Download the Zenodo archive (DOI above).
2. Unpack so that files land under `data/derived/` and `data/reference/` (see [`docs/DATA.md`](docs/DATA.md)).
3. Run:

```bash
python scripts/05_fair_usda_compare.py
```

### Optional: re-run crown detection from NAIP

Requires Google Earth Engine, GPU strongly recommended for SAM, and substantial disk/time.

```bash
python scripts/pipeline/01_download_naip.py
python scripts/pipeline/02_detect_trees.py
python scripts/pipeline/03_segment_trees.py
python scripts/pipeline/04_grid_summary.py
```

---

## Data

| Layer | In GitHub? | In Zenodo? | Notes |
|---|---|---|---|
| TIGER city boundary | yes | yes | Official analysis extent |
| `cell_context_enriched.csv` | yes | yes | 100 m analysis table |
| Fair-comparison metrics CSV | yes | yes | Locked TIGER metrics |
| Statistical result tables | yes | yes | Spearman, Moran, models, … |
| `canopy_mask.tif`, trees GeoJSON, LST, roads | no | **yes** | Too large for a lean code repo |
| USDA `Davis_canopy2022.tif` | no | **yes** | Reference product (redistributed for replication) |
| Raw NAIP mosaic | no | no | Re-download via GEE (`01_download_naip.py`) |

Public sources (NAIP, Landsat LST, Dynamic World, ACS, OSM / local GIS, TIGER) are documented in [`docs/DATA.md`](docs/DATA.md). Do **not** commit service-account keys or personal absolute paths.

---

## Citation

Please cite the journal article when available, and this software/data package:

```bibtex
@software{Narimani_Davis_Urban_Canopy_GeoAI,
  author  = {Narimani, Mohammadreza and Mitra, Shreyan and Farajpoor, Parastoo},
  title   = {Davis Urban Canopy GeoAI: replication code and derived data},
  year    = {2026},
  url     = {https://github.com/MohammadrezaNarimaniUCDavis/Davis_Urban_Canopy_GeoAI},
  note    = {Zenodo DOI: https://doi.org/10.5281/zenodo.XXXXXXX}
}
```

See also [`CITATION.cff`](CITATION.cff).

---

## License

Code is released under the [MIT License](LICENSE). Third-party data retain their original licenses (USDA canopy, NAIP, ACS, etc.) — see [`docs/DATA.md`](docs/DATA.md).

---

## Contact

Mohammadreza Narimani — `mnarimani@ucdavis.edu` (University of California, Davis)
