# Optical detection pipeline

Crown candidates (DeepForest + NDVI gate + NMS) and SAM canopy segmentation.

Requires `data/raw/davis_naip_2022.tif` (from Zenodo or script 01) and `pip install -r requirements-pipeline.txt`.

| Step | Script | Output |
|---|---|---|
| 1 | `01_download_naip.py` | `data/raw/davis_naip_2022.tif` |
| 2 | `02_detect_trees.py` | `data/derived/detections/trees.geojson`, `trees_boxes.geojson` |
| 3 | `03_segment_trees.py` | `data/derived/segments/canopy_mask.tif` |
| 4 | `04_grid_summary.py` | 100 m grid summary under `data/derived/analysis/` |

SAM ViT-B weights (~375 MB) download on first run of script 03 into `data/raw/`.
