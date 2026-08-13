# Statistical tables

Precomputed outputs matching the manuscript. Reproduce with:

```bash
python scripts/run_spatial_stats.py
python scripts/08_watch_zone_counts.py
```

| File | Contents |
|---|---|
| `spearman_vs_canopy.csv` | Spearman ρ of each layer vs canopy, with BH-FDR q-values |
| `spearman_rho.csv`, `spearman_p.csv`, `spearman_q_fdr.csv` | Full pairwise Spearman matrices |
| `moran_global.csv` | Global Moran's I (KNN-8) |
| `model_fit_summary.csv` | OLS vs spatial lag/error fit (core and SES sets) |
| `coefs_core.csv`, `coefs_ses.csv` | Model coefficients |
| `vif_core.csv`, `vif_ses.csv` | Variance inflation factors |
| `kruskal_wallis_summary.csv` | Kruskal–Wallis of canopy by poverty / income quintiles |
| `kw_canopy_by_poverty.csv`, `kw_canopy_by_income_proxy.csv` | Quintile detail |
| `partial_canopy_lst.csv` | Partial canopy–LST association controlling for built probability |
| `spearman_weights.csv` | Layer weights for the multi-factor attention map |
| `story_class_counts.csv` | Watch-zone cell counts (quartile screens) |
