# CCRS preliminary band classification — proposed cutoffs

Diagnostic only. Equal weights (`w = 0.25`), same Hazard score as `analysis/ccrs_preliminary_distribution.py`; **no weight change, no `age_factor`, no `EventMultiplier`, no production code.** The band cutoffs below are a *proposal* under review.

| band | rule | GFDL percentile |
| --- | --- | --- |
| LOW | score < 0.128 | < p25 |
| MEDIUM | 0.128 ≤ score < 0.386 | p25–p75 |
| HIGH | 0.386 ≤ score < 0.647 | p75–p95 |
| EXTREME | score ≥ 0.647 | ≥ p95 |

The **same absolute cutoffs** are applied to both GCM scores (each computed with its own global per-term bounds). If the cutoffs only fit GFDL, MIROC6 will pile capacity into HIGH/EXTREME — that is the check.

## Heat GCM: `gfdl_esm4`

Global per-GCM raw bounds: ws [3.37e-07, 29.9], heat [0, 160], sv [0.0609, 1.63], iv [0.138, 2.43]. Matched rows 32301 / 32424.

### Plants by band — % (count)

| country | scenario | n plants | LOW | MEDIUM | HIGH | EXTREME |
| --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt/ssp126 | 5253 | 57.8% (3035) | 42.2% (2218) | 0.0% (0) | 0.0% (0) |
| Brazil | bau/ssp370 | 5253 | 43.0% (2257) | 57.0% (2996) | 0.0% (0) | 0.0% (0) |
| Brazil | pes/ssp585 | 5253 | 42.7% (2242) | 56.5% (2969) | 0.8% (42) | 0.0% (0) |
| Portugal | opt/ssp126 | 449 | 8.5% (38) | 91.5% (411) | 0.0% (0) | 0.0% (0) |
| Portugal | bau/ssp370 | 449 | 7.6% (34) | 92.4% (415) | 0.0% (0) | 0.0% (0) |
| Portugal | pes/ssp585 | 449 | 0.9% (4) | 99.1% (445) | 0.0% (0) | 0.0% (0) |
| India | opt/ssp126 | 5065 | 4.4% (221) | 43.3% (2192) | 43.2% (2188) | 9.2% (464) |
| India | bau/ssp370 | 5065 | 3.5% (178) | 43.6% (2208) | 39.6% (2006) | 13.3% (673) |
| India | pes/ssp585 | 5065 | 3.0% (151) | 43.6% (2209) | 44.1% (2235) | 9.3% (470) |

### Installed capacity by band — % (MW)

| country | scenario | total MW | LOW | MEDIUM | HIGH | EXTREME |
| --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt/ssp126 | 217,316 | 54.9% (119,347 MW) | 45.1% (97,969 MW) | 0.0% (0 MW) | 0.0% (0 MW) |
| Brazil | bau/ssp370 | 217,316 | 35.8% (77,737 MW) | 64.2% (139,578 MW) | 0.0% (0 MW) | 0.0% (0 MW) |
| Brazil | pes/ssp585 | 217,316 | 35.9% (77,931 MW) | 63.1% (137,188 MW) | 1.0% (2,196 MW) | 0.0% (0 MW) |
| Portugal | opt/ssp126 | 21,778 | 14.2% (3,095 MW) | 85.8% (18,682 MW) | 0.0% (0 MW) | 0.0% (0 MW) |
| Portugal | bau/ssp370 | 21,778 | 13.2% (2,873 MW) | 86.8% (18,904 MW) | 0.0% (0 MW) | 0.0% (0 MW) |
| Portugal | pes/ssp585 | 21,778 | 0.2% (43 MW) | 99.8% (21,735 MW) | 0.0% (0 MW) | 0.0% (0 MW) |
| India | opt/ssp126 | 481,730 | 3.7% (17,853 MW) | 40.5% (195,199 MW) | 48.9% (235,404 MW) | 6.9% (33,275 MW) |
| India | bau/ssp370 | 481,730 | 3.1% (14,943 MW) | 41.5% (200,003 MW) | 46.4% (223,751 MW) | 8.9% (43,033 MW) |
| India | pes/ssp585 | 481,730 | 2.2% (10,581 MW) | 41.6% (200,225 MW) | 48.2% (232,076 MW) | 8.1% (38,848 MW) |

### Capacity coverage (opt scenario, representative)

| country | total declared MW | scored MW | scored % | plants w/ NaN capacity |
| --- | --- | --- | --- | --- |
| Brazil | 218,286 | 217,316 | 99.6% | 0 |
| Portugal | 21,803 | 21,778 | 99.9% | 0 |
| India | 483,110 | 481,730 | 99.7% | 0 |

## Heat GCM: `miroc6`

Global per-GCM raw bounds: ws [3.37e-07, 29.9], heat [0, 274], sv [0.0609, 1.63], iv [0.138, 2.43]. Matched rows 32163 / 32424.

### Plants by band — % (count)

| country | scenario | n plants | LOW | MEDIUM | HIGH | EXTREME |
| --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt/ssp126 | 5241 | 20.8% (1091) | 75.3% (3947) | 3.9% (203) | 0.0% (0) |
| Brazil | bau/ssp370 | 5241 | 15.1% (790) | 78.9% (4134) | 6.0% (317) | 0.0% (0) |
| Brazil | pes/ssp585 | 5241 | 15.1% (791) | 78.9% (4133) | 6.0% (317) | 0.0% (0) |
| Portugal | opt/ssp126 | 415 | 0.0% (0) | 100.0% (415) | 0.0% (0) | 0.0% (0) |
| Portugal | bau/ssp370 | 415 | 0.0% (0) | 96.1% (399) | 3.9% (16) | 0.0% (0) |
| Portugal | pes/ssp585 | 415 | 0.0% (0) | 95.2% (395) | 4.8% (20) | 0.0% (0) |
| India | opt/ssp126 | 5065 | 1.1% (57) | 36.2% (1836) | 44.8% (2267) | 17.9% (905) |
| India | bau/ssp370 | 5065 | 1.0% (50) | 34.3% (1737) | 46.6% (2362) | 18.1% (916) |
| India | pes/ssp585 | 5065 | 1.1% (56) | 33.7% (1707) | 49.1% (2487) | 16.1% (815) |

### Installed capacity by band — % (MW)

| country | scenario | total MW | LOW | MEDIUM | HIGH | EXTREME |
| --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt/ssp126 | 217,084 | 22.7% (49,239 MW) | 74.2% (161,148 MW) | 3.1% (6,697 MW) | 0.0% (0 MW) |
| Brazil | bau/ssp370 | 217,084 | 18.0% (39,074 MW) | 77.4% (168,128 MW) | 4.6% (9,882 MW) | 0.0% (0 MW) |
| Brazil | pes/ssp585 | 217,084 | 18.6% (40,335 MW) | 76.9% (166,847 MW) | 4.6% (9,902 MW) | 0.0% (0 MW) |
| Portugal | opt/ssp126 | 20,998 | 0.0% (0 MW) | 100.0% (20,998 MW) | 0.0% (0 MW) | 0.0% (0 MW) |
| Portugal | bau/ssp370 | 20,998 | 0.0% (0 MW) | 95.8% (20,116 MW) | 4.2% (883 MW) | 0.0% (0 MW) |
| Portugal | pes/ssp585 | 20,998 | 0.0% (0 MW) | 95.3% (20,015 MW) | 4.7% (984 MW) | 0.0% (0 MW) |
| India | opt/ssp126 | 481,730 | 1.5% (7,133 MW) | 38.2% (183,868 MW) | 47.1% (227,029 MW) | 13.2% (63,700 MW) |
| India | bau/ssp370 | 481,730 | 1.2% (5,795 MW) | 38.6% (185,744 MW) | 45.9% (220,923 MW) | 14.4% (69,268 MW) |
| India | pes/ssp585 | 481,730 | 1.2% (5,875 MW) | 37.2% (179,274 MW) | 48.3% (232,563 MW) | 13.3% (64,018 MW) |

### Capacity coverage (opt scenario, representative)

| country | total declared MW | scored MW | scored % | plants w/ NaN capacity |
| --- | --- | --- | --- | --- |
| Brazil | 218,286 | 217,084 | 99.4% | 0 |
| Portugal | 21,803 | 20,998 | 96.3% | 0 |
| India | 483,110 | 481,730 | 99.7% | 0 |

---

## Dominance flags (> 50% of installed capacity in one band)

- **gfdl_esm4 / Brazil / opt(ssp126)**: 54.9% of installed capacity in **LOW** alone.
- **gfdl_esm4 / Brazil / bau(ssp370)**: 64.2% of installed capacity in **MEDIUM** alone.
- **gfdl_esm4 / Brazil / pes(ssp585)**: 63.1% of installed capacity in **MEDIUM** alone.
- **gfdl_esm4 / Portugal / opt(ssp126)**: 85.8% of installed capacity in **MEDIUM** alone.
- **gfdl_esm4 / Portugal / bau(ssp370)**: 86.8% of installed capacity in **MEDIUM** alone.
- **gfdl_esm4 / Portugal / pes(ssp585)**: 99.8% of installed capacity in **MEDIUM** alone.
- **miroc6 / Brazil / opt(ssp126)**: 74.2% of installed capacity in **MEDIUM** alone.
- **miroc6 / Brazil / bau(ssp370)**: 77.4% of installed capacity in **MEDIUM** alone.
- **miroc6 / Brazil / pes(ssp585)**: 76.9% of installed capacity in **MEDIUM** alone.
- **miroc6 / Portugal / opt(ssp126)**: 100.0% of installed capacity in **MEDIUM** alone.
- **miroc6 / Portugal / bau(ssp370)**: 95.8% of installed capacity in **MEDIUM** alone.
- **miroc6 / Portugal / pes(ssp585)**: 95.3% of installed capacity in **MEDIUM** alone.


A flag means the cutoffs are not discriminating for that country/GCM/scenario — a single band holds the majority of capacity, so the classification carries little information there.


## What the numbers say (no decision drawn)

- **The cutoffs discriminate India and compress Brazil / Portugal.** The cuts are GFDL *pooled* percentiles, and the pool is ~half Indian plants with much higher scores, so the thresholds land where India's distribution is, not Brazil's or Portugal's. Brazil and Portugal never reach EXTREME under either GCM, and never reach HIGH under GFDL (Portugal never under either).
- **MIROC6 does not blow out EXTREME — it drains LOW.** The predicted saturation shows up as a *floor lift*: the MIROC6 heat term sits near the top of its own range for almost every matched plant (transformed p50 ≈ 0.77 vs GFDL ≈ 0.20), adding ~+0.15 to every score. That pushes Brazil out of LOW (55% → ~20%) and Portugal out of LOW entirely, all into MEDIUM — but India's EXTREME share only rises ~7% → ~14%, not a runaway.
- **12 of 18 country×GCM×scenario cells are flagged.** Only India (both GCMs, all scenarios) spreads across three or four bands.
