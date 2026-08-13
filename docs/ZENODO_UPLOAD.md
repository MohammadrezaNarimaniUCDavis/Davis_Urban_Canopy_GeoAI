# Zenodo upload checklist

Use this when minting the public data DOI. After publication, paste the DOI into:

- `README.md` (badge + bibtex note)
- `CITATION.cff` (`url:` field)
- `docs/DATA.md`

## Suggested Zenodo metadata

| Field | Value |
|---|---|
| **Title** | Davis Urban Canopy GeoAI — geospatial products and NAIP mosaic (Davis, California) |
| **Upload type** | Dataset |
| **Creators** | Mohammadreza Narimani; Shreyan Mitra; Parastoo Farajpoor |
| **Affiliation** | University of California, Davis |
| **License** | Creative Commons Attribution 4.0 (CC-BY-4.0) recommended for data (NAIP retains USDA terms) |
| **Related** | GitHub: `MohammadrezaNarimaniUCDavis/Davis_Urban_Canopy_GeoAI` |
| **Keywords** | urban canopy, GeoAI, DeepForest, SAM, Davis CA, NAIP, USDA canopy |

## Files to upload (two items)

Upload from `Urban_Forest_Davis/Manuscript/V4/zenodo_deposit/`:

1. **`Davis_Urban_Canopy_GeoAI_derived_data.zip`** (~7 MB) — boundary, derived products, USDA reference  
2. **`raw/davis_naip_2022.tif`** (~581 MB) — USDA NAIP 2022 RGB+NIR clipped to the TIGER city shapefile  

Keep them as **separate Zenodo files** (do not nest the 581 MB NAIP inside the zip — better for upload resume and downloaders who only need tables).

Folder mirror:

```
zenodo_deposit/
  README_ZENODO.txt
  raw/
    davis_naip_2022.tif          # UPLOAD SEPARATELY
    README_NAIP.txt
  boundary/davis_city_boundary.*
  derived/
    canopy_mask.tif
    trees.geojson
    trees_boxes.geojson
    davis_lst_landsat.tif
    davis_street_centerlines_yolo.geojson
    grid_summary_100m.csv
    cell_context_enriched.csv
    fair_comparison_metrics_tiger.csv
    tables_academic/*.csv
  reference/
    Davis_canopy2022.tif
```

## Description text (paste into Zenodo)

Geospatial products supporting optical GeoAI canopy mapping for the City of Davis, California. Includes the USDA NAIP 2022 RGB+NIR mosaic clipped to the Census TIGER municipal boundary (~25.9 km2), DeepForest+SAM canopy mask and crown detections, Landsat LST, street centerlines, the 100 m enriched analysis table, fair USDA comparison metrics, and the USDA/CAL FIRE 2022 canopy reference raster redistributed for replication. Companion code: https://github.com/MohammadrezaNarimaniUCDavis/Davis_Urban_Canopy_GeoAI

## After publishing

1. Copy the concept DOI (version-agnostic) or version DOI.
2. Replace every `10.5281/zenodo.XXXXXXX` in the public repo.
3. Optionally link the GitHub release to Zenodo for automated DOI minting on future tags.
