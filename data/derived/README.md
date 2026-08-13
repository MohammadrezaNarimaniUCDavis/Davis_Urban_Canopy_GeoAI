# Derived products

## Shipped in this repository

| File | Description |
|---|---|
| `cell_context_enriched.csv` | 100 m cells: canopy, detections, LST, built probability, roads, ACS/SES proxies, amenity distances |
| `fair_comparison_metrics_tiger.csv` | Locked fair USDA comparison on the TIGER city extent |

These two tables are enough to reproduce the spatial statistics (`scripts/run_spatial_stats.py`), shade map, weighted attention map, and watch-zone counts.

## Add from Zenodo for raster replication

Download https://doi.org/10.5281/zenodo.21925527 and copy from the zip `derived/` folder:

| File | Description |
|---|---|
| `canopy_mask.tif` | Binary optical canopy mask (DeepForest + NDVI + SAM) |
| `trees.geojson` | Crown-candidate centroids |
| `trees_boxes.geojson` | Crown-candidate bounding boxes |
| `davis_lst_landsat.tif` | Landsat land-surface temperature |
| `davis_street_centerlines_yolo.geojson` | Street centerlines used in the paper |
| `grid_summary_100m.csv` | 100 m grid summary from the detection pipeline |

Pipeline re-runs write detections/segments/analysis subfolders here; those outputs are gitignored.
