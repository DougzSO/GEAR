# CCRS — consolidated diagnostic summary

Diagnostic only, no production code. Equal provisional weights (`w = 0.25` on each of ws/heat/sv/iv) for the numeric score; `age_factor` and `EventMultiplier` not yet applied. The discrete classification is now **two separate bands**, not one band on the combined score:

- **WaterRiskBand** (ws + sv + iv) — **absolute** cuts from WRI Aqueduct 4.0 categories (`analysis/water_risk_band_classification.md`, `analysis/absolute_threshold_research.md`).
- **HeatRiskBand** (`extreme_heat_days` alone) — **sample-relative** percentile cuts, GFDL-ESM4 primary, with a declared limitation (no absolute annual-frequency threshold exists for this indicator).


## 1. CCRS numeric score (unchanged) — descriptive

Single continuous weighted sum, used for overall ranking and the per-plant map. Transcribed from `analysis/ccrs_preliminary_distribution.md` (not recomputed).


**Heat GCM `gfdl_esm4`**

| country | n | p1 | p5 | p25 | p50 | p75 | p95 | p99 | max | skew |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Brazil | 15759 | 0.041 | 0.051 | 0.086 | 0.131 | 0.179 | 0.292 | 0.359 | 0.426 | 0.972 |
| Portugal | 1347 | 0.115 | 0.122 | 0.149 | 0.197 | 0.219 | 0.314 | 0.333 | 0.333 | 0.779 |
| India | 15195 | 0.108 | 0.135 | 0.258 | 0.407 | 0.561 | 0.691 | 0.759 | 0.869 | -0.002 |
| pooled | 32301 | 0.048 | 0.060 | 0.128 | 0.201 | 0.386 | 0.647 | 0.737 | 0.869 | 0.870 |

**Heat GCM `miroc6`**

| country | n | p1 | p5 | p25 | p50 | p75 | p95 | p99 | max | skew |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Brazil | 15723 | 0.045 | 0.072 | 0.167 | 0.250 | 0.320 | 0.392 | 0.469 | 0.504 | -0.132 |
| Portugal | 1245 | 0.141 | 0.145 | 0.187 | 0.260 | 0.309 | 0.354 | 0.405 | 0.431 | -0.036 |
| India | 15195 | 0.121 | 0.283 | 0.366 | 0.452 | 0.603 | 0.725 | 0.789 | 0.882 | 0.150 |
| pooled | 32163 | 0.051 | 0.084 | 0.235 | 0.333 | 0.445 | 0.688 | 0.767 | 0.882 | 0.500 |

## 2. WaterRiskBand — absolute WRI-anchored bands

`S_water = 0.4164·ws_raw + 0.2505·sv_raw + 0.3331·iv_raw`; cuts 0.208 / 0.415 / 0.667 / 0.999 (derivation in `water_risk_band_classification.md`). % of installed capacity per band, per country x scenario. GCM-independent by construction; the plant set differs slightly between GCM columns (MIROC6 drops coastal plants).


**gfdl_esm4 plant set**

| country | scenario | Low | Low-Medium | Medium-High | High | Extremely-High |
| --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt | 25.7% | 62.2% | 8.4% | 2.8% | 1.0% |
| Brazil | bau | 24.6% | 57.7% | 12.4% | 4.3% | 1.0% |
| Brazil | pes | 23.9% | 61.4% | 10.1% | 3.7% | 1.0% |
| Portugal | opt | 0.0% | 12.6% | 63.9% | 23.5% | 0.0% |
| Portugal | bau | 0.0% | 14.0% | 57.2% | 22.0% | 6.8% |
| Portugal | pes | 0.0% | 12.6% | 61.1% | 19.5% | 6.8% |
| India | opt | 0.2% | 11.1% | 30.8% | 20.3% | 37.7% |
| India | bau | 0.2% | 9.8% | 29.0% | 21.9% | 39.0% |
| India | pes | 0.2% | 12.3% | 28.1% | 21.6% | 37.8% |

**miroc6 plant set**

| country | scenario | Low | Low-Medium | Medium-High | High | Extremely-High |
| --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt | 25.7% | 62.1% | 8.4% | 2.8% | 1.0% |
| Brazil | bau | 24.6% | 57.7% | 12.4% | 4.3% | 1.0% |
| Brazil | pes | 24.0% | 61.3% | 10.1% | 3.7% | 1.0% |
| Portugal | opt | 0.0% | 11.3% | 66.3% | 22.4% | 0.0% |
| Portugal | bau | 0.0% | 12.7% | 59.3% | 20.9% | 7.0% |
| Portugal | pes | 0.0% | 11.3% | 63.3% | 18.3% | 7.0% |
| India | opt | 0.2% | 11.1% | 30.8% | 20.3% | 37.7% |
| India | bau | 0.2% | 9.8% | 29.0% | 21.9% | 39.0% |
| India | pes | 0.2% | 12.3% | 28.1% | 21.6% | 37.8% |

## 3. HeatRiskBand — sample-relative percentile bands


**gfdl_esm4** — pooled p25/p75/p95 of `extreme_heat_days` = **0.03 / 31.2 / 92.7 days/yr > 40 °C**. By construction the pooled split is 25 / 50 / 20 / 5 %.

| country | scenario | LOW | MEDIUM | HIGH | EXTREME |
| --- | --- | --- | --- | --- | --- |
| Brazil | opt | 41.5% | 58.5% | 0.0% | 0.0% |
| Brazil | bau | 29.3% | 68.8% | 1.9% | 0.0% |
| Brazil | pes | 24.3% | 71.0% | 4.7% | 0.0% |
| Portugal | opt | 33.0% | 67.0% | 0.0% | 0.0% |
| Portugal | bau | 33.0% | 67.0% | 0.0% | 0.0% |
| Portugal | pes | 21.0% | 79.0% | 0.0% | 0.0% |
| India | opt | 12.6% | 27.2% | 52.9% | 7.2% |
| India | bau | 10.5% | 27.5% | 51.8% | 10.2% |
| India | pes | 10.4% | 20.6% | 56.6% | 12.3% |

**miroc6** — pooled p25/p75/p95 of `extreme_heat_days` = **18.23 / 124.4 / 246.7 days/yr > 40 °C**. By construction the pooled split is 25 / 50 / 20 / 5 %.

| country | scenario | LOW | MEDIUM | HIGH | EXTREME |
| --- | --- | --- | --- | --- | --- |
| Brazil | opt | 41.0% | 52.0% | 6.9% | 0.0% |
| Brazil | bau | 38.0% | 54.9% | 7.1% | 0.0% |
| Brazil | pes | 35.6% | 53.3% | 11.1% | 0.0% |
| Portugal | opt | 70.7% | 29.3% | 0.0% | 0.0% |
| Portugal | bau | 70.7% | 29.3% | 0.0% | 0.0% |
| Portugal | pes | 70.7% | 29.3% | 0.0% | 0.0% |
| India | opt | 9.5% | 45.8% | 39.5% | 5.3% |
| India | bau | 9.5% | 46.8% | 37.4% | 6.3% |
| India | pes | 8.4% | 41.6% | 40.5% | 9.5% |

_Note: under GFDL-ESM4 the pooled p25 is ~0.03 days/yr — 24 % of plants have exactly zero 40 °C days in the 2041–2070 mean — so the GFDL LOW band is effectively "no extreme heat". Under MIROC6 the same percentile is ~18 days/yr._


> **Declared limitation (HeatRiskBand).** No published absolute threshold classifies the annual frequency of days above 40 °C into risk categories. Published schemes classify single-day intensity (WBGT, ISO 7243) or the presence/absence of a temperature threshold (World Bank CKP), not cumulative annual frequency. Heat-mortality epidemiology deliberately avoids absolute cuts because they do not carry across different baseline climates — the same physical value (e.g. 35 °C) is a very different risk in different climates. HeatRiskBand therefore uses cuts relative to this study's sample (pooled percentiles) and is sensitive to the GCM used (~10–100× difference between GFDL-ESM4 and MIROC6 in the underlying absolute values, though the classification itself is recomputed per percentile). This is a declared limitation, not an implementation flaw — it is the available state of the art for this kind of indicator.


## 4. Joint reading — WaterRiskBand × HeatRiskBand by country

% of a country's installed capacity in each (water band, heat band) cell, three scenarios pooled. This crossing is not visible in any of the single-band reports.


### gfdl_esm4


**Brazil** (capacity pooled over 3 scenarios)

|  | heat LOW | heat MEDIUM | heat HIGH | heat EXTREME |
| --- | --- | --- | --- | --- |
| water Low | 5.2% | 19.3% | 0.2% | 0.0% |
| water Low-Medium | 20.1% | 38.4% | 1.9% | 0.0% |
| water Medium-High | 5.1% | 5.2% | 0.0% | 0.0% |
| water High | 1.4% | 2.2% | 0.0% | 0.0% |
| water Extremely-High | 0.0% | 1.0% | 0.0% | 0.0% |

_Brazil/gfdl_esm4: **0.0%** of capacity is (water High or Extremely-High) AND (heat HIGH or EXTREME) at once; **0.0%** is water Extremely-High AND heat EXTREME simultaneously._


**Portugal** (capacity pooled over 3 scenarios)

|  | heat LOW | heat MEDIUM | heat HIGH | heat EXTREME |
| --- | --- | --- | --- | --- |
| water Low | 0.0% | 0.0% | 0.0% | 0.0% |
| water Low-Medium | 4.2% | 8.9% | 0.0% | 0.0% |
| water Medium-High | 13.4% | 47.3% | 0.0% | 0.0% |
| water High | 9.6% | 12.1% | 0.0% | 0.0% |
| water Extremely-High | 1.8% | 2.8% | 0.0% | 0.0% |

_Portugal/gfdl_esm4: **0.0%** of capacity is (water High or Extremely-High) AND (heat HIGH or EXTREME) at once; **0.0%** is water Extremely-High AND heat EXTREME simultaneously._


**India** (capacity pooled over 3 scenarios)

|  | heat LOW | heat MEDIUM | heat HIGH | heat EXTREME |
| --- | --- | --- | --- | --- |
| water Low | 0.2% | 0.0% | 0.0% | 0.0% |
| water Low-Medium | 2.5% | 3.7% | 4.9% | 0.0% |
| water Medium-High | 3.2% | 6.5% | 19.6% | 0.0% |
| water High | 4.5% | 5.4% | 10.3% | 1.0% |
| water Extremely-High | 0.7% | 9.6% | 19.0% | 8.9% |

_India/gfdl_esm4: **39.2%** of capacity is (water High or Extremely-High) AND (heat HIGH or EXTREME) at once; **8.9%** is water Extremely-High AND heat EXTREME simultaneously._


### miroc6


**Brazil** (capacity pooled over 3 scenarios)

|  | heat LOW | heat MEDIUM | heat HIGH | heat EXTREME |
| --- | --- | --- | --- | --- |
| water Low | 12.7% | 12.0% | 0.0% | 0.0% |
| water Low-Medium | 22.8% | 29.7% | 7.9% | 0.0% |
| water Medium-High | 2.7% | 7.3% | 0.4% | 0.0% |
| water High | 0.0% | 3.5% | 0.1% | 0.0% |
| water Extremely-High | 0.0% | 1.0% | 0.0% | 0.0% |

_Brazil/miroc6: **0.1%** of capacity is (water High or Extremely-High) AND (heat HIGH or EXTREME) at once; **0.0%** is water Extremely-High AND heat EXTREME simultaneously._


**Portugal** (capacity pooled over 3 scenarios)

|  | heat LOW | heat MEDIUM | heat HIGH | heat EXTREME |
| --- | --- | --- | --- | --- |
| water Low | 0.0% | 0.0% | 0.0% | 0.0% |
| water Low-Medium | 5.8% | 6.0% | 0.0% | 0.0% |
| water Medium-High | 43.6% | 19.4% | 0.0% | 0.0% |
| water High | 17.5% | 3.1% | 0.0% | 0.0% |
| water Extremely-High | 3.9% | 0.8% | 0.0% | 0.0% |

_Portugal/miroc6: **0.0%** of capacity is (water High or Extremely-High) AND (heat HIGH or EXTREME) at once; **0.0%** is water Extremely-High AND heat EXTREME simultaneously._


**India** (capacity pooled over 3 scenarios)

|  | heat LOW | heat MEDIUM | heat HIGH | heat EXTREME |
| --- | --- | --- | --- | --- |
| water Low | 0.2% | 0.0% | 0.0% | 0.0% |
| water Low-Medium | 3.6% | 7.0% | 0.5% | 0.0% |
| water Medium-High | 3.3% | 16.7% | 9.2% | 0.0% |
| water High | 1.0% | 11.6% | 8.2% | 0.5% |
| water Extremely-High | 1.1% | 9.4% | 21.2% | 6.5% |

_India/miroc6: **36.4%** of capacity is (water High or Extremely-High) AND (heat HIGH or EXTREME) at once; **6.5%** is water Extremely-High AND heat EXTREME simultaneously._


## 5. Still open after this close

- **Weight of `heat` inside the combined numeric CCRS.** The numeric score still uses provisional equal weights (0.25 each). The magnitude-derived weight vector (spec §5/§6, same status as the original weight matrix / V5) is not set.
- **`EventMultiplier` functional form `f()`.** Country-level EM-DAT frequency (V2, closed); linear vs stepped vs capped, raw count vs exposure-normalised vs rate — not decided (spec §10 item C).
- **`age_factor` not implemented in code.** V1 fuel-specific curves are decided but unwritten; the ≥1 multiplier mapping (spec §10 item D) is not fixed.
- **SPEI / drought term not implemented.** Method settled if added (SPEI + Thornthwaite PET, one method across both GCMs; spec §3), but no term, transform or weight exists.
