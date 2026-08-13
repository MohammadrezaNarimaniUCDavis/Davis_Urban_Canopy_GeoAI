# Spearman-weighted attention map

Layer weights follow |Spearman ρ| with 100 m canopy cover
(`results/tables/spearman_vs_canopy.csv`), normalized to 100%.

**weight ∝ |Spearman ρ(layer, canopy)|**

| Layer | ρ vs canopy | Weight | Need direction |
|---|---:|---:|---|
| Canopy (%) | −0.342 | 16.2% | lower value → more attention |
| Value/acre | −0.342 | 16.2% | lower value → more attention |
| LST (°C) | −0.293 | 13.8% | higher value → more attention |
| DW built | 0.280 | 13.2% | higher value → more attention |
| Pop. density | 0.263 | 12.4% | higher value → more attention |
| Poverty | 0.207 | 9.8% | higher value → more attention |
| Income | −0.171 | 8.1% | lower value → more attention |
| Dist. park | −0.164 | 7.7% | higher value → more attention |
| Dist. bike | −0.053 | 2.5% | higher value → more attention |

Canopy self-weight is set to the maximum |ρ| among the other layers so canopy leads the screen without occupying 100% of the weight.

## Dropped

- `tree_count`: nearly redundant with canopy (|ρ| ≈ 0.90)
- `road_pct`: |ρ| ≈ 0 with canopy
- `sidewalk_pct`: |ρ| ≈ 0 with canopy

## Not available

Age and similar demographics are not in the 100 m enriched table and are not weighted here.

## Map

`results/figures/04b_weighted_attention_map.png` — multi-factor, Spearman-weighted screening surface. Not an official Tree Equity Score.

Reproduce:

```bash
python scripts/07_weighted_attention_map.py
```
