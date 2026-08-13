# Raw optical input

Place the USDA NAIP 2022 RGB+NIR mosaic here as:

```
davis_naip_2022.tif
```

The file is ~581 MB (4-band GeoTIFF, EPSG:4326, clipped to the TIGER city boundary). Download it from the Zenodo dataset:

https://doi.org/10.5281/zenodo.21925527

Alternatively, recreate it with Google Earth Engine:

```bash
python scripts/pipeline/01_download_naip.py
```

The GeoTIFF is not stored on GitHub. Original NAIP terms of use apply (USDA).
