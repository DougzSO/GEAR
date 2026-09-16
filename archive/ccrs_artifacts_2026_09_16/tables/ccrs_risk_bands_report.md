# CCRS risk bands -- summary

## Comparability warning

HeatRiskBand is sample-relative and is NOT comparable across runs. Its cuts are the p25/p75/p95 of extreme_heat_days over this study's plant sample under the primary GCM (gfdl_esm4), with all three scenarios pooled; any run whose scenario or GCM pool differs from the current data snapshot produces different cuts and a non-comparable classification. GFDL-ESM4 and MIROC6 are never pooled together. WaterRiskBand is the opposite: it uses fixed absolute WRI Aqueduct 4.0 cuts (0.208 / 0.415 / 0.667 / 1.0) that depend on neither the data pool nor the GCM, and IS stable across runs.

## The two bands are never merged

WaterRiskBand and HeatRiskBand are reported as two separate columns (and, below, as an auxiliary cross-tabulation). No value in this report combines them into a single risk number or ordinal score (spec Section 8.4/8.5).

## WaterRiskBand -- absolute WRI Aqueduct 4.0 cuts (fixed)

`S_water = 0.4164*ws_raw + 0.2505*sv_raw + 0.3331*iv_raw`; cuts 0.208 / 0.415 / 0.667 / 1.0 (left-closed). Independent of data pool and GCM; stable across runs.

          band  rows  row_share  capacity_mw  capacity_share
           Low  3061   0.094765    168408.50        0.080570
    Low-Medium 10743   0.332590    547691.17        0.262026
   Medium-High  5766   0.178508    515904.70        0.246818
          High  4622   0.143092    327311.80        0.156592
Extremely-High  8109   0.251045    530904.10        0.253994

## HeatRiskBand -- sample-relative percentile cuts (gfdl_esm4)

`extreme_heat_days` pooled p25/p75/p95 = 0.03333 / 31 / 92.7 days/yr > 40 C (all countries, 3 scenarios pooled). By construction the pooled split is ~25 / 50 / 20 / 5 %.

   band  rows  row_share  capacity_mw  capacity_share
    LOW  7968   0.245744    383037.80        0.182636
 MEDIUM 16297   0.502622    805447.47        0.384045
   HIGH  6493   0.200253    775016.80        0.369535
EXTREME  1666   0.051382    133773.90        0.063785

## Auxiliary cross view -- WaterRiskBand x HeatRiskBand (row counts)

heat_risk_band    LOW  MEDIUM  HIGH  EXTREME
water_risk_band                             
Low               985    2039    37        0
Low-Medium       3930    6311   502        0
Medium-High      1517    3158  1049       42
High             1156    2364  1011       91
Extremely-High    265    2417  3894     1533


Cross-tabulation only. Capacity in each cell (`contingency_table(frame, 'capacity_mw')`) is an auxiliary output too; the two bands are still never summed into one number.
