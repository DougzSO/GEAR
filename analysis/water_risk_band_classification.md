# WaterRiskBand classification — absolute (WRI Aqueduct 4.0) cuts

Diagnostic only, no production code. `ws` + `sv` + `iv` combined with weights derived from the WRI category step widths, cut at **absolute** thresholds anchored in WRI Aqueduct 4.0 (ws tracing to Raskin et al. 1997, SEI; sv/iv to WRI's own operational CV cutoffs — published but weaker, see `analysis/absolute_threshold_research.md`). No sample percentiles. Sentinel-substituted `ws_raw` (WRI 9999 -> country max) is used as-is; those basins are Extremely-High by definition.

## Weight derivation (auditable)

Each indicator's four finite WRI categories span raw 0 to its High->Extremely-High threshold `tau`. Average category width `delta_k = tau_k / 4`. Weight `w_k` proportional to `1 / delta_k` (= `4 / tau_k`; the 4 cancels, so `w_k` proportional to `1 / tau_k`), normalised to sum 1.

| indicator | tau (top threshold) | avg category width tau/4 | 1 / tau | weight w_k |
| --- | --- | --- | --- | --- |
| ws | 0.80 | 0.2000 | 1.25000 | 0.4164 |
| sv | 1.33 | 0.3325 | 0.75188 | 0.2505 |
| iv | 1.00 | 0.2500 | 1.00000 | 0.3331 |

`S_water_i = 0.4164*ws_raw + 0.2505*sv_raw + 0.3331*iv_raw`

Because `w_k * tau_k = 1/3` for every k, each indicator contributes exactly one third of the top cut and the High->Extremely-High cut lands at 1.0.

### Absolute band cuts on S_water

| boundary | all three indicators at | S_water |
| --- | --- | --- |
| Low / Low-Medium | ws=0.1, sv=0.33, iv=0.25 | 0.4164*0.1 + 0.2505*0.33 + 0.3331*0.25 = **0.2076** |
| Low-Medium / Medium-High | ws=0.2, sv=0.66, iv=0.5 | 0.4164*0.2 + 0.2505*0.66 + 0.3331*0.5 = **0.4152** |
| Medium-High / High | ws=0.4, sv=1, iv=0.75 | 0.4164*0.4 + 0.2505*1 + 0.3331*0.75 = **0.6669** |
| High / Extremely-High | ws=0.8, sv=1.33, iv=1 | 0.4164*0.8 + 0.2505*1.33 + 0.3331*1 = **0.9994** |

WaterRiskBand: **Low** < 0.208 · **Low-Medium** 0.208-0.415 · **Medium-High** 0.415-0.667 · **High** 0.667-0.999 · **Extremely-High** >= 0.999

## Heat GCM plant set: `gfdl_esm4`

WaterRiskBand does not depend on the GCM; the only difference between GCM sections is which plants are in the matched set (MIROC6 drops the western-Portugal / coastal-Brazil strip). Matched rows 32301 / 32424.

### Plants by WaterRiskBand — % (count)

| country | scenario | n plants | Low | Low-Medium | Medium-High | High | Extremely-High |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt/ssp126 | 5253 | 19.8% (1041) | 62.7% (3292) | 12.7% (668) | 3.8% (199) | 1.0% (53) |
| Brazil | bau/ssp370 | 5253 | 18.7% (984) | 57.9% (3040) | 16.1% (846) | 6.3% (330) | 1.0% (53) |
| Brazil | pes/ssp585 | 5253 | 18.0% (944) | 61.9% (3252) | 14.0% (735) | 5.1% (269) | 1.0% (53) |
| Portugal | opt/ssp126 | 449 | 0.0% (0) | 5.6% (25) | 49.9% (224) | 44.5% (200) | 0.0% (0) |
| Portugal | bau/ssp370 | 449 | 0.0% (0) | 7.1% (32) | 41.2% (185) | 31.6% (142) | 20.0% (90) |
| Portugal | pes/ssp585 | 449 | 0.0% (0) | 5.6% (25) | 47.2% (212) | 27.2% (122) | 20.0% (90) |
| India | opt/ssp126 | 5065 | 0.1% (3) | 8.2% (416) | 20.5% (1038) | 22.1% (1121) | 49.1% (2487) |
| India | bau/ssp370 | 5065 | 0.1% (3) | 5.7% (291) | 17.4% (880) | 21.6% (1094) | 55.2% (2797) |
| India | pes/ssp585 | 5065 | 0.1% (3) | 9.0% (454) | 19.3% (977) | 22.3% (1127) | 49.4% (2504) |

### Installed capacity by WaterRiskBand — % (MW)

| country | scenario | total MW | Low | Low-Medium | Medium-High | High | Extremely-High |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt/ssp126 | 217,316 | 25.7% (55,764 MW) | 62.2% (135,128 MW) | 8.4% (18,270 MW) | 2.8% (6,039 MW) | 1.0% (2,114 MW) |
| Brazil | bau/ssp370 | 217,316 | 24.6% (53,370 MW) | 57.7% (125,432 MW) | 12.4% (26,981 MW) | 4.3% (9,418 MW) | 1.0% (2,114 MW) |
| Brazil | pes/ssp585 | 217,316 | 23.9% (52,012 MW) | 61.4% (133,385 MW) | 10.1% (21,855 MW) | 3.7% (7,949 MW) | 1.0% (2,114 MW) |
| Portugal | opt/ssp126 | 21,778 | 0.0% (0 MW) | 12.6% (2,751 MW) | 63.9% (13,915 MW) | 23.5% (5,112 MW) | 0.0% (0 MW) |
| Portugal | bau/ssp370 | 21,778 | 0.0% (0 MW) | 14.0% (3,043 MW) | 57.2% (12,450 MW) | 22.0% (4,798 MW) | 6.8% (1,486 MW) |
| Portugal | pes/ssp585 | 21,778 | 0.0% (0 MW) | 12.6% (2,751 MW) | 61.1% (13,300 MW) | 19.5% (4,241 MW) | 6.8% (1,486 MW) |
| India | opt/ssp126 | 481,730 | 0.2% (1,007 MW) | 11.1% (53,339 MW) | 30.8% (148,180 MW) | 20.3% (97,711 MW) | 37.7% (181,494 MW) |
| India | bau/ssp370 | 481,730 | 0.2% (1,007 MW) | 9.8% (47,284 MW) | 29.0% (139,839 MW) | 21.9% (105,729 MW) | 39.0% (187,871 MW) |
| India | pes/ssp585 | 481,730 | 0.2% (1,007 MW) | 12.3% (59,491 MW) | 28.1% (135,225 MW) | 21.6% (104,047 MW) | 37.8% (181,960 MW) |

## Heat GCM plant set: `miroc6`

WaterRiskBand does not depend on the GCM; the only difference between GCM sections is which plants are in the matched set (MIROC6 drops the western-Portugal / coastal-Brazil strip). Matched rows 32163 / 32424.

### Plants by WaterRiskBand — % (count)

| country | scenario | n plants | Low | Low-Medium | Medium-High | High | Extremely-High |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt/ssp126 | 5241 | 19.9% (1041) | 62.6% (3280) | 12.7% (668) | 3.8% (199) | 1.0% (53) |
| Brazil | bau/ssp370 | 5241 | 18.8% (984) | 57.8% (3028) | 16.1% (846) | 6.3% (330) | 1.0% (53) |
| Brazil | pes/ssp585 | 5241 | 18.0% (944) | 61.8% (3240) | 14.0% (735) | 5.1% (269) | 1.0% (53) |
| Portugal | opt/ssp126 | 415 | 0.0% (0) | 5.5% (23) | 54.0% (224) | 40.5% (168) | 0.0% (0) |
| Portugal | bau/ssp370 | 415 | 0.0% (0) | 7.2% (30) | 44.6% (185) | 27.0% (112) | 21.2% (88) |
| Portugal | pes/ssp585 | 415 | 0.0% (0) | 5.5% (23) | 51.1% (212) | 22.2% (92) | 21.2% (88) |
| India | opt/ssp126 | 5065 | 0.1% (3) | 8.2% (416) | 20.5% (1038) | 22.1% (1121) | 49.1% (2487) |
| India | bau/ssp370 | 5065 | 0.1% (3) | 5.7% (291) | 17.4% (880) | 21.6% (1094) | 55.2% (2797) |
| India | pes/ssp585 | 5065 | 0.1% (3) | 9.0% (454) | 19.3% (977) | 22.3% (1127) | 49.4% (2504) |

### Installed capacity by WaterRiskBand — % (MW)

| country | scenario | total MW | Low | Low-Medium | Medium-High | High | Extremely-High |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Brazil | opt/ssp126 | 217,084 | 25.7% (55,764 MW) | 62.1% (134,896 MW) | 8.4% (18,270 MW) | 2.8% (6,039 MW) | 1.0% (2,114 MW) |
| Brazil | bau/ssp370 | 217,084 | 24.6% (53,370 MW) | 57.7% (125,201 MW) | 12.4% (26,981 MW) | 4.3% (9,418 MW) | 1.0% (2,114 MW) |
| Brazil | pes/ssp585 | 217,084 | 24.0% (52,012 MW) | 61.3% (133,154 MW) | 10.1% (21,855 MW) | 3.7% (7,949 MW) | 1.0% (2,114 MW) |
| Portugal | opt/ssp126 | 20,998 | 0.0% (0 MW) | 11.3% (2,382 MW) | 66.3% (13,915 MW) | 22.4% (4,701 MW) | 0.0% (0 MW) |
| Portugal | bau/ssp370 | 20,998 | 0.0% (0 MW) | 12.7% (2,674 MW) | 59.3% (12,450 MW) | 20.9% (4,399 MW) | 7.0% (1,475 MW) |
| Portugal | pes/ssp585 | 20,998 | 0.0% (0 MW) | 11.3% (2,382 MW) | 63.3% (13,300 MW) | 18.3% (3,842 MW) | 7.0% (1,475 MW) |
| India | opt/ssp126 | 481,730 | 0.2% (1,007 MW) | 11.1% (53,339 MW) | 30.8% (148,180 MW) | 20.3% (97,711 MW) | 37.7% (181,494 MW) |
| India | bau/ssp370 | 481,730 | 0.2% (1,007 MW) | 9.8% (47,284 MW) | 29.0% (139,839 MW) | 21.9% (105,729 MW) | 39.0% (187,871 MW) |
| India | pes/ssp585 | 481,730 | 0.2% (1,007 MW) | 12.3% (59,491 MW) | 28.1% (135,225 MW) | 21.6% (104,047 MW) | 37.8% (181,960 MW) |

---

## Dominance flags (> 50% of installed capacity in one band)

- **gfdl_esm4 set / Brazil / opt**: 62.2% of installed capacity in **Low-Medium** alone.
- **gfdl_esm4 set / Brazil / bau**: 57.7% of installed capacity in **Low-Medium** alone.
- **gfdl_esm4 set / Brazil / pes**: 61.4% of installed capacity in **Low-Medium** alone.
- **gfdl_esm4 set / Portugal / opt**: 63.9% of installed capacity in **Medium-High** alone.
- **gfdl_esm4 set / Portugal / bau**: 57.2% of installed capacity in **Medium-High** alone.
- **gfdl_esm4 set / Portugal / pes**: 61.1% of installed capacity in **Medium-High** alone.
- **miroc6 set / Brazil / opt**: 62.1% of installed capacity in **Low-Medium** alone.
- **miroc6 set / Brazil / bau**: 57.7% of installed capacity in **Low-Medium** alone.
- **miroc6 set / Brazil / pes**: 61.3% of installed capacity in **Low-Medium** alone.
- **miroc6 set / Portugal / opt**: 66.3% of installed capacity in **Medium-High** alone.
- **miroc6 set / Portugal / bau**: 59.3% of installed capacity in **Medium-High** alone.
- **miroc6 set / Portugal / pes**: 63.3% of installed capacity in **Medium-High** alone.