# CCRS score bands — installed capacity by technology

**Diagnostic only.** Capacity (MW) of each technology falling in each band of the numeric CCRS score, per country and scenario, for both GCMs. Regenerated live from `src/index/*` via `src.visualization.data.load_ccrs_final()` (never a cached CSV).

> ⚠️ `analysis/climate_risk_score_spec.md` Section 8.3 records that a single band on the whole CCRS score was **tried and rejected** in favour of the two independent bands (WaterRiskBand + HeatRiskBand). This table applies the rejected classification — use it as an internal score-distribution view, not a manuscript methodology output, unless Section 8.3 is revised.

Bands: country-balanced percentiles of the score — the mean of the three per-country p25/p75/p95 (one vote per country, all scenarios pooled), computed separately per GCM (same convention as `analysis/ccrs_band_classification_v2.py`). Scenarios are the paired water/heat trajectories: `opt` = SSP1-2.6, `bau` = SSP3-7.0, `pes` = SSP5-8.5. Plants with an undefined CCRS (GFDL-ESM4 36, MIROC6 174 of 32,424 plant-scenario rows — thermal cells outside any Aqueduct basin) are excluded, so per-GCM totals differ by < 0.1%. MW rounded to whole numbers.

## gfdl_esm4 — capacity (MW) by technology and CCRS-score band

Country-balanced cuts on `ccrs_gfdl_esm4`: **Low** < 0.205 · **Medium** 0.205–0.666 · **High** 0.666–0.981 · **Extreme** ≥ 0.981

| Country | Scenario | Technology | Low | Medium | High | Extreme | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt (SSP1-2.6) | Hydro | 18,640 | 87,602 | 3,425 | 0 | 109,667 |
| Brazil | opt (SSP1-2.6) | Thermal | 14,730 | 32,346 | 0 | 0 | 47,076 |
| Brazil | opt (SSP1-2.6) | Wind | 36,045 | 0 | 0 | 0 | 36,045 |
| Brazil | opt (SSP1-2.6) | Solar | 21,843 | 2,527 | 529 | 7 | 24,906 |
| Brazil | bau (SSP3-7.0) | Hydro | 4,805 | 103,782 | 1,080 | 0 | 109,667 |
| Brazil | bau (SSP3-7.0) | Thermal | 21,968 | 25,107 | 0 | 0 | 47,076 |
| Brazil | bau (SSP3-7.0) | Wind | 36,045 | 0 | 0 | 0 | 36,045 |
| Brazil | bau (SSP3-7.0) | Solar | 20,781 | 2,617 | 1,462 | 46 | 24,906 |
| Brazil | pes (SSP5-8.5) | Hydro | 1,053 | 100,526 | 8,088 | 0 | 109,667 |
| Brazil | pes (SSP5-8.5) | Thermal | 17,905 | 29,171 | 0 | 0 | 47,076 |
| Brazil | pes (SSP5-8.5) | Wind | 34,984 | 1,061 | 0 | 0 | 36,045 |
| Brazil | pes (SSP5-8.5) | Solar | 21,123 | 1,419 | 2,224 | 141 | 24,906 |
| Portugal | opt (SSP1-2.6) | Hydro | 0 | 7,783 | 0 | 0 | 7,783 |
| Portugal | opt (SSP1-2.6) | Thermal | 860 | 3,873 | 0 | 0 | 4,733 |
| Portugal | opt (SSP1-2.6) | Wind | 5,755 | 0 | 0 | 0 | 5,755 |
| Portugal | opt (SSP1-2.6) | Solar | 2,760 | 772 | 0 | 0 | 3,532 |
| Portugal | bau (SSP3-7.0) | Hydro | 0 | 7,389 | 394 | 0 | 7,783 |
| Portugal | bau (SSP3-7.0) | Thermal | 0 | 4,733 | 0 | 0 | 4,733 |
| Portugal | bau (SSP3-7.0) | Wind | 5,164 | 590 | 0 | 0 | 5,755 |
| Portugal | bau (SSP3-7.0) | Solar | 1,794 | 1,738 | 0 | 0 | 3,532 |
| Portugal | pes (SSP5-8.5) | Hydro | 0 | 7,783 | 0 | 0 | 7,783 |
| Portugal | pes (SSP5-8.5) | Thermal | 0 | 4,733 | 0 | 0 | 4,733 |
| Portugal | pes (SSP5-8.5) | Wind | 5,164 | 590 | 0 | 0 | 5,755 |
| Portugal | pes (SSP5-8.5) | Solar | 1,794 | 1,738 | 0 | 0 | 3,532 |
| India | opt (SSP1-2.6) | Hydro | 429 | 36,716 | 11,581 | 1,120 | 49,846 |
| India | opt (SSP1-2.6) | Thermal | 1,139 | 190,108 | 86,544 | 15,830 | 293,621 |
| India | opt (SSP1-2.6) | Wind | 6,580 | 9,316 | 4,539 | 18,502 | 38,937 |
| India | opt (SSP1-2.6) | Solar | 7,470 | 9,974 | 2,206 | 79,708 | 99,357 |
| India | bau (SSP3-7.0) | Hydro | 300 | 33,251 | 14,706 | 1,589 | 49,846 |
| India | bau (SSP3-7.0) | Thermal | 0 | 120,691 | 153,658 | 19,272 | 293,621 |
| India | bau (SSP3-7.0) | Wind | 5,850 | 10,066 | 3,744 | 19,276 | 38,937 |
| India | bau (SSP3-7.0) | Solar | 7,356 | 10,120 | 2,156 | 79,725 | 99,357 |
| India | pes (SSP5-8.5) | Hydro | 0 | 27,252 | 21,077 | 1,517 | 49,846 |
| India | pes (SSP5-8.5) | Thermal | 0 | 100,253 | 165,821 | 27,547 | 293,621 |
| India | pes (SSP5-8.5) | Wind | 6,241 | 7,547 | 3,290 | 21,860 | 38,937 |
| India | pes (SSP5-8.5) | Solar | 7,200 | 4,860 | 6,237 | 81,060 | 99,357 |

### All technologies pooled

| Country | Scenario | Low | Medium | High | Extreme | Total |
| --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt (SSP1-2.6) | 91,258 | 122,475 | 3,954 | 7 | 217,694 |
| Brazil | bau (SSP3-7.0) | 83,600 | 131,507 | 2,542 | 46 | 217,694 |
| Brazil | pes (SSP5-8.5) | 75,065 | 132,177 | 10,312 | 141 | 217,694 |
| Portugal | opt (SSP1-2.6) | 9,374 | 12,428 | 0 | 0 | 21,803 |
| Portugal | bau (SSP3-7.0) | 6,958 | 14,451 | 394 | 0 | 21,803 |
| Portugal | pes (SSP5-8.5) | 6,958 | 14,845 | 0 | 0 | 21,803 |
| India | opt (SSP1-2.6) | 15,618 | 246,114 | 104,870 | 115,160 | 481,762 |
| India | bau (SSP3-7.0) | 13,506 | 174,127 | 174,265 | 119,863 | 481,762 |
| India | pes (SSP5-8.5) | 13,441 | 139,912 | 196,425 | 131,984 | 481,762 |

## miroc6 — capacity (MW) by technology and CCRS-score band

Country-balanced cuts on `ccrs_miroc6`: **Low** < 0.605 · **Medium** 0.605–1.055 · **High** 1.055–1.258 · **Extreme** ≥ 1.258

| Country | Scenario | Technology | Low | Medium | High | Extreme | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt (SSP1-2.6) | Hydro | 69,569 | 40,098 | 0 | 0 | 109,667 |
| Brazil | opt (SSP1-2.6) | Thermal | 47,042 | 34 | 0 | 0 | 47,076 |
| Brazil | opt (SSP1-2.6) | Wind | 11,354 | 19,513 | 4,947 | 0 | 35,813 |
| Brazil | opt (SSP1-2.6) | Solar | 3,952 | 15,025 | 5,574 | 355 | 24,906 |
| Brazil | bau (SSP3-7.0) | Hydro | 78,406 | 31,261 | 0 | 0 | 109,667 |
| Brazil | bau (SSP3-7.0) | Thermal | 47,076 | 0 | 0 | 0 | 47,076 |
| Brazil | bau (SSP3-7.0) | Wind | 11,354 | 13,643 | 10,816 | 0 | 35,813 |
| Brazil | bau (SSP3-7.0) | Solar | 2,969 | 13,577 | 7,976 | 384 | 24,906 |
| Brazil | pes (SSP5-8.5) | Hydro | 61,689 | 47,978 | 0 | 0 | 109,667 |
| Brazil | pes (SSP5-8.5) | Thermal | 46,911 | 165 | 0 | 0 | 47,076 |
| Brazil | pes (SSP5-8.5) | Wind | 11,354 | 13,367 | 11,092 | 0 | 35,813 |
| Brazil | pes (SSP5-8.5) | Solar | 2,785 | 13,175 | 8,552 | 394 | 24,906 |
| Portugal | opt (SSP1-2.6) | Hydro | 7,414 | 0 | 0 | 0 | 7,414 |
| Portugal | opt (SSP1-2.6) | Thermal | 4,642 | 0 | 0 | 0 | 4,642 |
| Portugal | opt (SSP1-2.6) | Wind | 3,820 | 1,634 | 0 | 0 | 5,454 |
| Portugal | opt (SSP1-2.6) | Solar | 2,442 | 1,071 | 0 | 0 | 3,513 |
| Portugal | bau (SSP3-7.0) | Hydro | 7,414 | 0 | 0 | 0 | 7,414 |
| Portugal | bau (SSP3-7.0) | Thermal | 4,642 | 0 | 0 | 0 | 4,642 |
| Portugal | bau (SSP3-7.0) | Wind | 3,820 | 1,634 | 0 | 0 | 5,454 |
| Portugal | bau (SSP3-7.0) | Solar | 2,223 | 1,290 | 0 | 0 | 3,513 |
| Portugal | pes (SSP5-8.5) | Hydro | 7,414 | 0 | 0 | 0 | 7,414 |
| Portugal | pes (SSP5-8.5) | Thermal | 4,642 | 0 | 0 | 0 | 4,642 |
| Portugal | pes (SSP5-8.5) | Wind | 3,820 | 1,634 | 0 | 0 | 5,454 |
| Portugal | pes (SSP5-8.5) | Solar | 2,080 | 1,434 | 0 | 0 | 3,513 |
| India | opt (SSP1-2.6) | Hydro | 19,108 | 29,315 | 1,076 | 347 | 49,846 |
| India | opt (SSP1-2.6) | Thermal | 45,281 | 229,132 | 19,209 | 0 | 293,621 |
| India | opt (SSP1-2.6) | Wind | 1,276 | 915 | 5,852 | 30,894 | 38,937 |
| India | opt (SSP1-2.6) | Solar | 924 | 1,380 | 5,126 | 91,927 | 99,357 |
| India | bau (SSP3-7.0) | Hydro | 25,011 | 21,094 | 3,183 | 558 | 49,846 |
| India | bau (SSP3-7.0) | Thermal | 40,671 | 228,520 | 24,430 | 0 | 293,621 |
| India | bau (SSP3-7.0) | Wind | 1,200 | 970 | 6,062 | 30,705 | 38,937 |
| India | bau (SSP3-7.0) | Solar | 916 | 1,401 | 4,763 | 92,277 | 99,357 |
| India | pes (SSP5-8.5) | Hydro | 8,205 | 38,650 | 1,665 | 1,326 | 49,846 |
| India | pes (SSP5-8.5) | Thermal | 48,766 | 223,080 | 21,475 | 300 | 293,621 |
| India | pes (SSP5-8.5) | Wind | 1,200 | 357 | 3,808 | 33,572 | 38,937 |
| India | pes (SSP5-8.5) | Solar | 858 | 645 | 2,112 | 95,742 | 99,357 |

### All technologies pooled

| Country | Scenario | Low | Medium | High | Extreme | Total |
| --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt (SSP1-2.6) | 131,917 | 74,669 | 10,521 | 355 | 217,462 |
| Brazil | bau (SSP3-7.0) | 139,805 | 58,481 | 18,792 | 384 | 217,462 |
| Brazil | pes (SSP5-8.5) | 122,739 | 74,685 | 19,645 | 394 | 217,462 |
| Portugal | opt (SSP1-2.6) | 18,319 | 2,705 | 0 | 0 | 21,023 |
| Portugal | bau (SSP3-7.0) | 18,100 | 2,924 | 0 | 0 | 21,023 |
| Portugal | pes (SSP5-8.5) | 17,956 | 3,068 | 0 | 0 | 21,023 |
| India | opt (SSP1-2.6) | 66,589 | 260,741 | 31,263 | 123,168 | 481,762 |
| India | bau (SSP3-7.0) | 67,798 | 251,985 | 38,438 | 123,540 | 481,762 |
| India | pes (SSP5-8.5) | 59,030 | 262,733 | 29,059 | 130,940 | 481,762 |
