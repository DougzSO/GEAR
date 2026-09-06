# Preliminary CCRS Hazard-term distribution — equal weights

Diagnostic only. **Provisional `w = 0.25` for every term**, purely to see the shape — not a weight decision. `age_factor` and `EventMultiplier` are excluded (pure Hazard term). Transforms per `analysis/climate_risk_score_spec.md`: `log1p`→Min-Max for `ws`/`heat`, plain Min-Max for `sv`/`iv`. **Min-Max bounds are global** — pooled over all three countries and all three scenarios (matched plants), no per-country normalisation.

- Plant→raster: nearest-pixel sample of the processed raw rasters.
- Scenario pairing (SSP identity): opt ↔ ssp126, bau ↔ ssp370, pes ↔ ssp585.
- Two heat GCMs reported separately — `heat` is the one term whose GCM choice is still open, and MIROC6's day-counts run ~10–100× GFDL, so the Hazard shape depends on it.

## Heat GCM: `gfdl_esm4`

Matched plant×scenario rows: 32301 (of 32424; unmatched = plant outside a basin or the heat raster).

### Global per-term bounds (pooled, all countries × all scenarios)

| term | transform | raw min | raw max |
| --- | --- | --- | --- |
| ws | log1p → Min-Max | 3.37e-07 | 29.88 |
| heat | log1p → Min-Max | 0 | 159.9 |
| sv | Min-Max | 0.06095 | 1.631 |
| iv | Min-Max | 0.138 | 2.434 |

### Transformed term distributions (0–1), pooled

| term | p1 | p5 | p25 | p50 | p75 | p95 | p99 | max | skew |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ws | 3.748e-05 | 0.0004315 | 0.01377 | 0.08755 | 0.2573 | 0.6212 | 1 | 1 | 1.580 |
| heat | 0 | 0 | 0.006454 | 0.1979 | 0.6831 | 0.8936 | 0.9704 | 1 | 0.450 |
| sv | 0.05515 | 0.08593 | 0.1868 | 0.3105 | 0.4917 | 0.7158 | 0.7858 | 1 | 0.560 |
| iv | 0.04378 | 0.0615 | 0.1255 | 0.1794 | 0.2672 | 0.5915 | 0.7582 | 1 | 1.630 |

### Hazard score (Σ 0.25·term), equal weights — NO age_factor, NO EventMultiplier

| country | n | p1 | p5 | p25 | p50 | p75 | p95 | p99 | max | skew |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Brazil | 15759 | 0.04123 | 0.05149 | 0.08617 | 0.1312 | 0.1788 | 0.292 | 0.3586 | 0.4256 | 0.972 |
| Portugal | 1347 | 0.115 | 0.1223 | 0.1495 | 0.1969 | 0.2186 | 0.3136 | 0.3331 | 0.3331 | 0.779 |
| India | 15195 | 0.1081 | 0.1351 | 0.2584 | 0.407 | 0.5615 | 0.6914 | 0.7592 | 0.8691 | -0.002 |
| **pooled** | 32301 | 0.04774 | 0.0596 | 0.1278 | 0.2009 | 0.3862 | 0.647 | 0.7374 | 0.8691 | 0.870 |

### Pooled Hazard score by scenario

| scenario (water / heat) | n | p25 | p50 | p75 | p95 | p99 | max | skew |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| opt / ssp126 | 10767 | 0.1177 | 0.1875 | 0.3807 | 0.6388 | 0.7255 | 0.7721 | 0.887 |
| bau / ssp370 | 10767 | 0.1366 | 0.1981 | 0.3847 | 0.659 | 0.7419 | 0.8691 | 0.919 |
| pes / ssp585 | 10767 | 0.1327 | 0.2195 | 0.3933 | 0.6369 | 0.713 | 0.8069 | 0.800 |

## Heat GCM: `miroc6`

Matched plant×scenario rows: 32163 (of 32424; unmatched = plant outside a basin or the heat raster).

### Global per-term bounds (pooled, all countries × all scenarios)

| term | transform | raw min | raw max |
| --- | --- | --- | --- |
| ws | log1p → Min-Max | 3.37e-07 | 29.88 |
| heat | log1p → Min-Max | 0 | 274.2 |
| sv | Min-Max | 0.06095 | 1.631 |
| iv | Min-Max | 0.138 | 2.434 |

### Transformed term distributions (0–1), pooled

| term | p1 | p5 | p25 | p50 | p75 | p95 | p99 | max | skew |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ws | 3.748e-05 | 0.0004267 | 0.01377 | 0.08607 | 0.2573 | 0.6212 | 1 | 1 | 1.578 |
| heat | 0 | 0 | 0.5263 | 0.7674 | 0.8601 | 0.9812 | 0.9912 | 1 | -1.076 |
| sv | 0.05485 | 0.08631 | 0.1868 | 0.3105 | 0.4931 | 0.7158 | 0.7858 | 1 | 0.559 |
| iv | 0.04378 | 0.06064 | 0.1254 | 0.1794 | 0.2675 | 0.5915 | 0.7582 | 1 | 1.626 |

### Hazard score (Σ 0.25·term), equal weights — NO age_factor, NO EventMultiplier

| country | n | p1 | p5 | p25 | p50 | p75 | p95 | p99 | max | skew |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Brazil | 15723 | 0.04468 | 0.07221 | 0.1668 | 0.2502 | 0.3195 | 0.3923 | 0.469 | 0.5037 | -0.132 |
| Portugal | 1245 | 0.1411 | 0.1447 | 0.1867 | 0.2599 | 0.3095 | 0.3536 | 0.4047 | 0.4309 | -0.036 |
| India | 15195 | 0.1214 | 0.2834 | 0.3665 | 0.4516 | 0.6027 | 0.725 | 0.7892 | 0.8824 | 0.150 |
| **pooled** | 32163 | 0.05136 | 0.08358 | 0.2355 | 0.3333 | 0.4447 | 0.6884 | 0.767 | 0.8824 | 0.500 |

### Pooled Hazard score by scenario

| scenario (water / heat) | n | p25 | p50 | p75 | p95 | p99 | max | skew |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| opt / ssp126 | 10721 | 0.2237 | 0.3219 | 0.4433 | 0.6943 | 0.7631 | 0.7927 | 0.514 |
| bau / ssp370 | 10721 | 0.2408 | 0.3348 | 0.4453 | 0.7153 | 0.7809 | 0.8824 | 0.550 |
| pes / ssp585 | 10721 | 0.2502 | 0.3386 | 0.4444 | 0.6733 | 0.7525 | 0.8167 | 0.432 |

---

No band cutoffs proposed here. The point of the table is the shape (skew, percentile spacing) and the country ordering under a global scale, as input to the EXTREME/HIGH/MEDIUM/LOW cutoff discussion (spec Section 10 item B).