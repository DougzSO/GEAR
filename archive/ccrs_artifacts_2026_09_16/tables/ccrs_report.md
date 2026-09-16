# CCRS -- final assembly summary

## Comparability warning (inherited from T4/risk_bands)

HeatRiskBand is sample-relative and is NOT comparable across runs. Its cuts are the p25/p75/p95 of extreme_heat_days over this study's plant sample under the primary GCM (gfdl_esm4), with all three scenarios pooled; any run whose scenario or GCM pool differs from the current data snapshot produces different cuts and a non-comparable classification. GFDL-ESM4 and MIROC6 are never pooled together. WaterRiskBand is the opposite: it uses fixed absolute WRI Aqueduct 4.0 cuts (0.208 / 0.415 / 0.667 / 1.0) that depend on neither the data pool nor the GCM, and IS stable across runs.

## Data caveats carried into this report (from T2/age_factor)

age_factor for wind uses a uniform 0.4%/yr relative retention rate for every wind plant (age_factor.WIND_RELATIVE_RATE). CF_initial (initial capacity factor) does not exist in any GEM file for any of the 1986 wind plants across the three countries, so the CF_initial-based form (age_factor._wind_retention_from_cf_initial) is dead code and is never called -- see src/index/age_factor.py and docs/DECISIONS.md 2026-09-04.

Plants with a missing commissioning_year get a neutral age_factor (1.0) and are kept, never dropped:

 country  missing_commissioning_year  total_plants  fraction
  Brazil                          97          5275  0.018389
Portugal                          11           450  0.024444
   India                         494          5083  0.097187

## Multiplicative assembly

CCRS_i,s = Hazard_i,s * age_factor_i * EventMultiplier_country(i), computed for every configured GCM's Hazard column side by side (never blended). Multiplicative only, never summed -- see compute_ccrs().

## % capacity by WaterRiskBand (V6 computable base; GCM-independent)

 country water_scenario           band  capacity_mw  capacity_share
  Brazil            bau            Low     57540.90        0.268382
  Brazil            bau     Low-Medium    118652.10        0.553416
  Brazil            bau    Medium-High     25704.90        0.119893
  Brazil            bau           High      9417.90        0.043927
  Brazil            bau Extremely-High      2113.90        0.009860
  Brazil            bau        NO_BAND       969.80        0.004523
  Brazil            opt            Low     55573.60        0.259206
  Brazil            opt     Low-Medium    132290.60        0.617028
  Brazil            opt    Medium-High     17412.80        0.081217
  Brazil            opt           High      6038.80        0.028166
  Brazil            opt Extremely-High      2113.90        0.009860
  Brazil            opt        NO_BAND       969.80        0.004523
  Brazil            pes            Low     52273.00        0.243811
  Brazil            pes     Low-Medium    130520.90        0.608774
  Brazil            pes    Medium-High     20572.40        0.095954
  Brazil            pes           High      7949.50        0.037078
  Brazil            pes Extremely-High      2113.90        0.009860
  Brazil            pes        NO_BAND       969.80        0.004523
   India            bau            Low      1007.00        0.002175
   India            bau     Low-Medium     46625.80        0.100708
   India            bau    Medium-High    136522.10        0.294878
   India            bau           High    100544.20        0.217168
   India            bau Extremely-High    176922.50        0.382140
   India            bau        NO_BAND      1357.10        0.002931
   India            opt            Low      1007.00        0.002175
   India            opt     Low-Medium     52456.70        0.113303
   India            opt    Medium-High    144522.40        0.312158
   India            opt           High     91216.40        0.197021
   India            opt Extremely-High    172419.10        0.372413
   India            opt        NO_BAND      1357.10        0.002931
   India            pes            Low      1007.00        0.002175
   India            pes     Low-Medium     58599.80        0.126571
   India            pes    Medium-High    131576.70        0.284196
   India            pes           High     98095.50        0.211879
   India            pes Extremely-High    172342.60        0.372247
   India            pes        NO_BAND      1357.10        0.002931
Portugal            bau            Low         0.00        0.000000
Portugal            bau     Low-Medium      3043.49        0.140164
Portugal            bau    Medium-High     12428.60        0.572383
Portugal            bau           High      4777.60        0.220026
Portugal            bau Extremely-High      1439.10        0.066276
Portugal            bau        NO_BAND        25.00        0.001151
Portugal            opt            Low         0.00        0.000000
Portugal            opt     Low-Medium      2750.89        0.126689
Portugal            opt    Medium-High     13887.80        0.639584
Portugal            opt           High      5050.10        0.232576
Portugal            opt Extremely-High         0.00        0.000000
Portugal            opt        NO_BAND        25.00        0.001151
Portugal            pes            Low         0.00        0.000000
Portugal            pes     Low-Medium      2750.89        0.126689
Portugal            pes    Medium-High     13277.00        0.611455
Portugal            pes           High      4221.80        0.194429
Portugal            pes Extremely-High      1439.10        0.066276
Portugal            pes        NO_BAND        25.00        0.001151

## % capacity by HeatRiskBand (V6 computable base, per GCM)

GFDL-ESM4 is the primary GCM for this headline figure; MIROC6 is shown beside it as the sensitivity panel, its own rows, never blended (ARCHITECTURE.md Section 5.4).

 country heat_scenario       gcm    band  capacity_mw  capacity_share
  Brazil        ssp126 gfdl_esm4     LOW     88758.50        0.413987
  Brazil        ssp126 gfdl_esm4  MEDIUM    125603.00        0.585836
  Brazil        ssp126 gfdl_esm4    HIGH        38.00        0.000177
  Brazil        ssp126 gfdl_esm4 EXTREME         0.00        0.000000
  Brazil        ssp126 gfdl_esm4 NO_BAND         0.00        0.000000
  Brazil        ssp126    miroc6     LOW     88568.10        0.413098
  Brazil        ssp126    miroc6  MEDIUM    110642.10        0.516056
  Brazil        ssp126    miroc6    HIGH     14957.60        0.069765
  Brazil        ssp126    miroc6 EXTREME         0.00        0.000000
  Brazil        ssp126    miroc6 NO_BAND       231.70        0.001081
  Brazil        ssp370 gfdl_esm4     LOW     62458.10        0.291316
  Brazil        ssp370 gfdl_esm4  MEDIUM    147794.90        0.689343
  Brazil        ssp370 gfdl_esm4    HIGH      4146.50        0.019340
  Brazil        ssp370 gfdl_esm4 EXTREME         0.00        0.000000
  Brazil        ssp370 gfdl_esm4 NO_BAND         0.00        0.000000
  Brazil        ssp370    miroc6     LOW     82600.70        0.385265
  Brazil        ssp370    miroc6  MEDIUM    116196.40        0.541962
  Brazil        ssp370    miroc6    HIGH     15370.70        0.071692
  Brazil        ssp370    miroc6 EXTREME         0.00        0.000000
  Brazil        ssp370    miroc6 NO_BAND       231.70        0.001081
  Brazil        ssp585 gfdl_esm4     LOW     51615.10        0.240743
  Brazil        ssp585 gfdl_esm4  MEDIUM    152619.60        0.711847
  Brazil        ssp585 gfdl_esm4    HIGH     10164.80        0.047411
  Brazil        ssp585 gfdl_esm4 EXTREME         0.00        0.000000
  Brazil        ssp585 gfdl_esm4 NO_BAND         0.00        0.000000
  Brazil        ssp585    miroc6     LOW     76363.70        0.356175
  Brazil        ssp585    miroc6  MEDIUM    113887.90        0.531195
  Brazil        ssp585    miroc6    HIGH     23916.20        0.111550
  Brazil        ssp585    miroc6 EXTREME         0.00        0.000000
  Brazil        ssp585    miroc6 NO_BAND       231.70        0.001081
   India        ssp126 gfdl_esm4     LOW     60730.60        0.131174
   India        ssp126 gfdl_esm4  MEDIUM    120891.40        0.261117
   India        ssp126 gfdl_esm4    HIGH    248217.30        0.536131
   India        ssp126 gfdl_esm4 EXTREME     33139.40        0.071579
   India        ssp126 gfdl_esm4 NO_BAND         0.00        0.000000
   India        ssp126    miroc6     LOW     45056.50        0.097319
   India        ssp126    miroc6  MEDIUM    214620.50        0.463565
   India        ssp126    miroc6    HIGH    179788.90        0.388331
   India        ssp126    miroc6 EXTREME     23512.80        0.050786
   India        ssp126    miroc6 NO_BAND         0.00        0.000000
   India        ssp370 gfdl_esm4     LOW     50351.10        0.108755
   India        ssp370 gfdl_esm4  MEDIUM    120745.80        0.260802
   India        ssp370 gfdl_esm4    HIGH    246515.00        0.532454
   India        ssp370 gfdl_esm4 EXTREME     45366.80        0.097989
   India        ssp370 gfdl_esm4 NO_BAND         0.00        0.000000
   India        ssp370    miroc6     LOW     45056.50        0.097319
   India        ssp370    miroc6  MEDIUM    219715.60        0.474570
   India        ssp370    miroc6    HIGH    169972.90        0.367129
   India        ssp370    miroc6 EXTREME     28233.70        0.060983
   India        ssp370    miroc6 NO_BAND         0.00        0.000000
   India        ssp585 gfdl_esm4     LOW     50259.30        0.108556
   India        ssp585 gfdl_esm4  MEDIUM     91516.50        0.197669
   India        ssp585 gfdl_esm4    HIGH    265935.20        0.574401
   India        ssp585 gfdl_esm4 EXTREME     55267.70        0.119374
   India        ssp585 gfdl_esm4 NO_BAND         0.00        0.000000
   India        ssp585    miroc6     LOW     39815.80        0.085999
   India        ssp585    miroc6  MEDIUM    195804.60        0.422924
   India        ssp585    miroc6    HIGH    186384.60        0.402577
   India        ssp585    miroc6 EXTREME     40973.70        0.088500
   India        ssp585    miroc6 NO_BAND         0.00        0.000000
Portugal        ssp126 gfdl_esm4     LOW      7155.40        0.329533
Portugal        ssp126 gfdl_esm4  MEDIUM     14558.39        0.670467
Portugal        ssp126 gfdl_esm4    HIGH         0.00        0.000000
Portugal        ssp126 gfdl_esm4 EXTREME         0.00        0.000000
Portugal        ssp126 gfdl_esm4 NO_BAND         0.00        0.000000
Portugal        ssp126    miroc6     LOW     14789.90        0.681129
Portugal        ssp126    miroc6  MEDIUM      6144.59        0.282981
Portugal        ssp126    miroc6    HIGH         0.00        0.000000
Portugal        ssp126    miroc6 EXTREME         0.00        0.000000
Portugal        ssp126    miroc6 NO_BAND       779.30        0.035890
Portugal        ssp370 gfdl_esm4     LOW      7155.40        0.329533
Portugal        ssp370 gfdl_esm4  MEDIUM     14558.39        0.670467
Portugal        ssp370 gfdl_esm4    HIGH         0.00        0.000000
Portugal        ssp370 gfdl_esm4 EXTREME         0.00        0.000000
Portugal        ssp370 gfdl_esm4 NO_BAND         0.00        0.000000
Portugal        ssp370    miroc6     LOW     14789.90        0.681129
Portugal        ssp370    miroc6  MEDIUM      6144.59        0.282981
Portugal        ssp370    miroc6    HIGH         0.00        0.000000
Portugal        ssp370    miroc6 EXTREME         0.00        0.000000
Portugal        ssp370    miroc6 NO_BAND       779.30        0.035890
Portugal        ssp585 gfdl_esm4     LOW      4554.30        0.209742
Portugal        ssp585 gfdl_esm4  MEDIUM     17159.49        0.790258
Portugal        ssp585 gfdl_esm4    HIGH         0.00        0.000000
Portugal        ssp585 gfdl_esm4 EXTREME         0.00        0.000000
Portugal        ssp585 gfdl_esm4 NO_BAND         0.00        0.000000
Portugal        ssp585    miroc6     LOW     14789.90        0.681129
Portugal        ssp585    miroc6  MEDIUM      6144.59        0.282981
Portugal        ssp585    miroc6    HIGH         0.00        0.000000
Portugal        ssp585    miroc6 EXTREME         0.00        0.000000
Portugal        ssp585    miroc6 NO_BAND       779.30        0.035890

## WaterRiskBand x HeatRiskBand -- auxiliary contingency table (never a single combined score)

### gfdl_esm4 (primary) -- row counts

heat_risk_band    LOW  MEDIUM  HIGH  EXTREME
water_risk_band                             
Low               985    2039    37        0
Low-Medium       3930    6311   502        0
Medium-High      1517    3158  1049       42
High             1156    2364  1011       91
Extremely-High    265    2417  3894     1533

### miroc6 (sensitivity panel) -- row counts

heat_risk_band    LOW  MEDIUM  HIGH  EXTREME
water_risk_band                             
Low              1793    1257    11        0
Low-Medium       4178    6130   393        0
Medium-High      1185    3455  1126        0
High              490    2730  1269       41
Extremely-High    314    2503  3695     1593

## CCRS score -- informational distribution (not a capacity share)

- ccrs_gfdl_esm4: n=32388, p50=0.3533, p95=1.5549, max=1.8172

- ccrs_miroc6: n=32250, p50=1.0230, p95=1.7018, max=1.8245
