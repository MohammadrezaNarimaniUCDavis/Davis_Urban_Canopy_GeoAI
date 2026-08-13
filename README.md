# Davis Urban Canopy GeoAI

Reproducible code and derived data for optical GeoAI urban-canopy mapping in **Davis, California**, accompanying:

> *From crown candidates to neighborhood screening: integrating optical GeoAI and spatial modeling for urban-canopy assessment in Davis, California*

**Authors:** Mohammadreza Narimani, Shreyan Mitra, Parastoo Farajpoor  
**Target journal:** *Geocarto International*

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.XXXXXXX-blue.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)

> **Zenodo DOI:** placeholder â€” replace `XXXXXXX` after the deposit is published.

This repository is the **public replication package**. It intentionally contains only the scripts and products needed to reproduce the paperâ€™s core results. The authorsâ€™ full working archive remains private.

---

## What this study does

1. Detect tree-crown candidates on **NAIP 2022** (DeepForest + NDVI gate).
2. Segment crowns with **SAM** and build a binary **canopy mask**.
3. Aggregate to a **100 m** grid and join urban / SES / climate context layers.
4. Compare against **USDA / CAL FIRE** canopy on the shared **Census TIGER** city extent (~25.9 kmÂ²).
5. Screen spatial **associations** (Spearman + FDR, Moranâ€™s I, spatial lag) and build **planning screens** (shade / weighted attention).

Claims are framed as **association / co-location / screening**, not causal cooling or an official Tree Equity Score.

### Locked fair-comparison numbers (TIGER extent)

| Metric | Value |
|---|---|
| City area | ~25.92 kmÂ² |
| Our canopy | 2.43 kmÂ² (9.37%) |
| USDA canopy | 7.11 kmÂ² (27.4%) |
| Recovery | 34.2% |
| IoU / Dice | 0.288 / 0.448 |
| Detection-center precision | 0.974 |

---

## Repository layout

```
Davis_Urban_Canopy_GeoAI/
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ boundary/          # Census TIGER Davis city boundary (shipped)
â”‚   â”œâ”€â”€ derived/           # Small tables shipped; large rasters from Zenodo
â”‚   â”œâ”€â”€ reference/         # USDA canopy (from Zenodo)
â”‚   â””â”€â”€ raw/               # User-downloaded NAIP / SAM weights (not shipped)
â”œâ”€â”€ scripts/
â”‚   â”œâ”€â”€ pipeline/          # 01â€“04: NAIP â†’ detect â†’ SAM â†’ 100 m grid
â”‚   â”œâ”€â”€ run_spatial_stats.py
â”‚   â”œâ”€â”€ 05_fair_usda_compare.py
â”‚   â”œâ”€â”€ 06_shade_attention_maps.py
â”‚   â””â”€â”€ 07_weighted_attention_map.py
â”œâ”€â”€ src/paths.py           # All I/O paths (no personal directories)
â”œâ”€â”€ results/tables/        # Precomputed statistical tables (shipped)
â”œâ”€â”€ docs/                  # Data sources, Zenodo upload notes
â”œâ”€â”€ requirements.txt
â”œâ”€â”€ CITATION.cff
â””â”€â”€ LICENSE
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
| Statistical result tables | yes | yes | Spearman, Moran, models, â€¦ |
| `canopy_mask.tif`, trees GeoJSON, LST, roads | no | **yes** | Too large for a lean code repo |
| USDA `Davis_canopy2022.tif` | no | **yes** | Reference product (redistributed for replication) |
| Raw NAIP mosaic (city clip) | no | **yes** | `davis_naip_2022.tif` (~581 MB); also re-downloadable via GEE |

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

Code is released under the [MIT License](LICENSE). Third-party data retain their original licenses (USDA canopy, NAIP, ACS, etc.) â€” see [`docs/DATA.md`](docs/DATA.md).

---

## Contact

Mohammadreza Narimani â€” `mnarimani@ucdavis.edu` (University of California, Davis)

