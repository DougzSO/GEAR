# GEAR v3: Methods (consolidated draft)

## Overview of the risk assessment flow

GEAR produces two distinct, deliberately unmerged outputs per plant. There
is no "total plant risk" number in this framework. Summing heterogeneous
hazard types (e.g., wind risk plus drought risk) into one figure is treated
as a methodological fallacy and is not attempted anywhere.

```
Raw climate/water hazard data
      |
      v
Hazard_i,h  (normalized 0-1, per hazard h, per plant i,
             globally pooled cross-national bounds, Section 3)
      |
      +-----------------------------+
      |                             |
      v                             v
RiskBand_i,h                  Risk_i,h = Hazard_i,h x Exposure_i x Vulnerability_i
(threshold classification      (continuous, per hazard, MW- and
 of the raw hazard value        age-weighted; never summed across hazards)
 alone; Low/Medium/High/              |
 Extreme, Section 5)                  v
      |                         Asset Risk Magnitude
      v                         (per-hazard asset-level maps and
PSAE_i (Section 6)               prioritization rankings; comparable
(EXTREME/HIGH/MEDIUM/LOW,        across technology and country, strictly
 secondary, screening-only,      within the same hazard)
 comparable ONLY within the
 same technology bucket)
```

Layer 1 (Physical Hazard Screening, PSAE) answers: how many independent
physical stressors is this asset exposed to at a severe level, relative to
what is physically possible for its own technology. Layer 2 (Asset Risk
Magnitude, Risk_i,h) answers: how much capacity is at stake at this
specific asset, given its scale and condition, for one given hazard.
Comparability rules for both are stated explicitly (Section 6.3) and
enforced in code and in every figure/table produced from this pipeline;
neither output is ever collapsed into the other or into a new single
score.

Following the IPCC AR5/AR6 risk framework, for plant *i* under hazard *h*:

Risk_i,h = Hazard_i,h x Exposure_i x Vulnerability_i    (Equation 1)

- Hazard_i,h in [0,1]: physical hazard intensity, hazard-specific
  normalization, globally pooled cross-national bounds (Section 3).
- Exposure_i: installed capacity (MW), measured, not modeled, Tier 1 by
  construction. Reported in two explicit forms, never conflated: Systemic
  Capacity at Risk (raw linear MW, used wherever the question is
  grid-operator-relevant) and Intrinsic Asset Risk (log10(MW + 1), a
  visualization-only display transform so a handful of very large plants
  do not visually dominate a map and mask physically severe risk at
  smaller assets; the log base and offset are Tier 3, author-declared, no
  literature precedent). All comparability statements refer to the
  untransformed Risk_i,h.
- Vulnerability_i: age_factor in [1,2] (Section 2.6).

## 1. Study area and data sources

The study covers the operating power-generation fleet of Brazil, Portugal,
and India, drawn from the Global Energy Monitor Global Integrated Power
Tracker (manual snapshot dated 2026-08-09). Only records with
`Status == "operating"` enter the pipeline; other statuses (construction,
announced, pre-construction, and all others) are preserved separately and
counted, not silently dropped. Generating units are aggregated to plants
on country + normalized name + coordinate (tolerance ~100 m); capacity is
summed, commissioning year is the minimum (oldest unit) across
constituent units. Plants are assigned to one of four technology buckets
(hydro, thermal, wind, solar); coal, oil/gas, nuclear, bioenergy, and
geothermal are merged into `thermal` on the shared physical mechanism of
cooling-water dependence and temperature sensitivity.

National boundaries are the GADM 4.1 administrative level-0 polygon per
country. For Portugal, the boundary geometry is reduced to its largest
polygon by area, and asset records outside the resulting mainland
bounding box are physically excluded (archived, not dropped): the studied
fleet and hydroclimatic regime of interest are continental, and the
Azores/Madeira archipelagos would also inflate the country-level bounding
box used for climate queries. All hazard rasters are resampled to a
common ~1 km (0.008333 deg) grid per country, referenced to EPSG:4326.

Every CMIP6-sourced hazard is drawn from exactly two GCMs, GFDL-ESM4 and
MIROC6, run jointly across three scenarios (SSP1-2.6, SSP3-7.0,
SSP5-8.5), corresponding to the Aqueduct water-stress scenario labels
`opt`, `bau`, and `pes` respectively. GFDL-ESM4's selection as the
anchor model is an inherited operational default from the prior
repository this project's acquisition layer was reconstructed from, with
no surviving documented justification for that original choice; this is
stated plainly rather than reconstructed after the fact. MIROC6 was
selected, among four CDS-catalogue candidates fully covering all three
scenarios (IPSL-CM6A-LR excluded for missing scenario coverage;
CNRM-CM6-1 passed over for a realization-variant mismatch with GFDL-ESM4;
MPI-ESM1-2-LR retained only as an unused fallback), for its greater
structural divergence from GFDL-ESM4 — distinct convection scheme and
model lineage, a qualitative judgment at the time of selection.

By equilibrium climate sensitivity (ECS), the two models sit close to one
another near the low end of the CMIP6 ensemble: GFDL-ESM4 2.6-2.7 K
(Dunne et al., 2020, *JAMES*; Zelinka et al., 2020, *GRL*) and MIROC6
2.6 K (Tatebe et al., 2019, *GMD*), against a full ensemble spanning
approximately 1.8-5.6 K with a multi-model mean near 3.7 K (Zelinka et
al., 2020; Meehl et al., 2020, *Science Advances*). The pair therefore
does not bound or span the CMIP6 sensitivity range; it is reported as a
sensitivity check between two structurally and regionally divergent
models — distinct convection parameterization, model lineage, and native
grid resolution (GFDL-ESM4 approximately 1 deg x 1.25 deg cubed-sphere;
MIROC6 approximately 1.4 deg x 1.4 deg T85 spectral) — not as uncertainty
propagation across the CMIP6 ensemble or as a low-vs-high bounding
design. This project's own reprocessing found extreme-heat-day counts
differing by one to two orders of magnitude between the two models for
the same plants under identical scenarios, and wind/solar hazard scores
near-zero under GFDL-ESM4 and near-saturated under MIROC6, a genuine,
literature-consistent divergence in regional extremes and coarse-grid
behavior. Independent regional evaluation literature is directionally
consistent with MIROC6 producing outlier behavior for the specific
variables this pipeline uses: MIROC6 was flagged as significantly
underestimating near-surface wind speed relative to observations in a
22-model Mediterranean evaluation, and was the worst-performing model
among 13 CMIP6 GCMs for historical surface air temperature over Thailand
(Kamworapan et al., 2021, *Heliyon*) — regional, single-study findings,
reported at that evidentiary weight, not a global consensus verdict on
either model. GFDL-ESM4 is the primary GCM for every reported figure;
MIROC6 is a sensitivity panel, never blended with GFDL-ESM4 at any stage
(bounds, classification, or aggregation).

The water-stress indicator (`ws`) is drawn from the WRI Aqueduct 4.0
`future_annual` product (Earth Engine FeatureCollection,
horizon 50, i.e., conditions around 2050), already cross-walked to the
same three SSP pathways used elsewhere in the framework: `opt` ->
SSP1-2.6, `bau` -> SSP3-7.0, `pes` -> SSP5-8.5 (WRI data dictionary;
Kuzma et al., 2023). It is a mid-century projected value, not a
historical baseline. One residual, declared alignment note: the Aqueduct
future product represents conditions around 2050 (a period-representative
estimate), while the CMIP6 hazards use an explicit 2041-2070 thirty-year
window; the two are not an identical averaging window, treated here as a
standard, literature-consistent approximation of sustained mid-century
conditions, not a methodological flaw.

Disaster-event context (contextual validators, broad-impact class only)
draws from the EM-DAT Archive (UCLouvain Dataverse snapshot dated
2026-04-30, coverage 1900-2024), filtered to Drought, Extreme
temperature, Flood, and Storm event types.

## 2. Per-hazard processing

Six hazard terms are computed, comparably available across Brazil,
Portugal, and India: Water Stress, Extreme Heat, Drought (SPEI), Extreme
Precipitation, Extreme Wind, plus two water-variability extension terms
(Seasonal Variability, `sv`, and Interannual Variability, `iv`) confirmed
in Hydro's applicable-hazard set only. Wildfire (FWI/EFFIS) and
sea-level rise were evaluated and are deferred/excluded (Section 8);
neither contributes a hazard term.

### 2.1 Water Stress

Source: WRI Aqueduct 4.0 `future_annual` consumption-to-availability
ratio (Section 1). Mechanism: thermal cooling-water availability.
Applicable buckets: Hydro, Thermal. Tier 1, absolute WRI Aqueduct
category cutoffs (<0.1 / 0.1-0.4 / 0.4-0.8 / >0.8).

### 2.2 Extreme Heat

Source: CMIP6 daily maximum near-surface air temperature (`tasmax`),
2041-2070. Indicator: mean days/year with tasmax > 40 degC. Mechanism:
PV efficiency loss (Solar); thermal cycle efficiency (Thermal).
Applicable buckets: Thermal, Solar. A defensible Tier 1 PV
efficiency-loss-per-degree cutoff was investigated and rejected after a
bounded literature search: manufacturer Pmax temperature coefficients
vary by module technology by more than a factor of two (crystalline
silicon approximately -0.3 to -0.5 %/degC; CdTe approximately -0.21
%/degC; CIGS approximately -0.2 to -0.45 %/degC), GEM records no
per-plant PV module-technology field, and IEC 61215/61730 certify a
manufacturer-specific coefficient rather than mandate a single value;
IEC 61730's 98th-percentile module-operating-temperature <=70 degC limit
is a safety qualification threshold, not a performance-loss risk
threshold, and does not convert to an ambient-air days/year metric
without an irradiance/wind-dependent offset this pipeline does not
model. No peer-reviewed study was found translating a temperature
coefficient into a days/year-above-X ambient threshold for utility-scale
PV. Solar's Extreme Heat is therefore Tier 3, final (not provisional
pending a Tier 1 value): the same percentile method and pooled cuts as
Thermal's row, since the raw `tasmax > 40 degC` indicator does not vary
by bucket. Thermal's Extreme Heat is Tier 3 for the same reason
(cooling-water-temperature thresholds do not match the ambient-air
`tasmax` variable modeled): pooled P75/P90/P95 of days/year, P50
reported as a diagnostic only (Section 4.1).

### 2.3 Drought (SPEI)

Source: SPEI-12 (Thornthwaite potential evapotranspiration). Indicator:
mean months/year with SPEI-12 <= -1.0. Mechanism: hydro inflow, hydraulic
head. Applicable bucket: Hydro. Tier 3, no absolute threshold links SPEI
to generation impact: pooled P75/P90/P95 of months/year, P50 diagnostic
only. Thornthwaite PET (`pr` + `tas`) is used rather than Hargreaves PET
(`pr` + `tasmin` + `tasmax`) because daily `tasmin` is absent from the
CDS catalogue for GFDL-ESM4 x SSP3-7.0; Hargreaves would have silently
dropped one GCM/scenario cell from the drought term.

### 2.4 Extreme Precipitation

Source: the same daily CMIP6 precipitation (`pr`) series already
acquired for SPEI, no new download. Indicator: mean days/year with daily
`pr` exceeding that pixel's own P95 threshold of wet-day (`pr` >= 1
mm/day) amounts (ETCCDI "very wet days"/R95p convention, Zhang et al.,
2011). Mechanism: flooding/overtopping risk at low-elevation and
hydraulic assets. Applicable buckets: Hydro, Thermal, Solar (all three
confirmed by the correlation gate, Section 4). Tier 3, sample-relative
percentile cutoff, not a cited absolute inundation-depth threshold: the
drafted HAZUS-MH inundation-depth classes (0.2/0.5/1.5 m) do not exist in
the primary FEMA Hazus Flood Model Technical Manual — HAZUS-MH uses
continuous depth-damage curves per building-occupancy type (900+ curves,
depth in feet from finished floor), not discrete class thresholds
(verified against Hazus 6.1, July 2024, and Scawthorn et al., 2006,
*Natural Hazards Review* 7(2)). HAZUS-MH is also structurally
incompatible with this pipeline's input regardless of the class-value
mismatch: there is no hydrological conversion step from precipitation
amount to inundation depth anywhere in the pipeline. Pooled P75/P90/P95
of days/year, P50 diagnostic only; the same cuts are reused, bucket-
invariant, across Hydro, Thermal, and Solar, since the raw indicator does
not vary by bucket.

### 2.5 Extreme Wind

Source: ERA5 10 m instantaneous wind gust, historical reanalysis
baseline (1991-2020), not a CMIP6 SSP projection. Indicator: per-pixel
mean annual maximum 10 m gust (m/s). One threshold-agnostic raw layer
serves two mechanistically distinct downstream consumers with
non-convergent threshold designs:

- Wind bucket (turbine cut-out mechanism): Tier 1, IEC design-class
  cut-out speed (~25 m/s / 90 km/h), a single standardized,
  site-independent value. Binary classification (Low/Extreme).
- Solar bucket (tracker structural uplift mechanism): Tier 3, final, not
  a placeholder pending a Tier 1 value. No single defensible Tier 1
  structural wind-uplift threshold exists for solar trackers: ASCE 7's
  design wind speed is inherently site-specific (location, Risk
  Category, Exposure Category), and manufacturer survival ratings vary
  materially by product generation (observed range approximately
  51-60+ m/s across two data points from a single manufacturer alone).
  Pooled P90/P95/P99 of ERA5 mean annual max gust, P75 diagnostic only.

A CMIP6-based Extreme Wind (aligning this hazard to the same
2041-2070/three-SSP framing as every other hazard) was investigated on
request and rejected on two independent grounds, either sufficient
alone: (1) the CDS `projections-cmip6` catalogue's only daily-resolution
wind variable is `sfcWind` (daily-mean near-surface wind speed, confirmed
available for both GCMs across all three SSPs), but no daily-maximum
variant exists under any model/scenario and no gust variable exists on
this catalogue at all; (2) `sfcWind` and ERA5's
`instantaneous_10m_wind_gust` are not the same physical quantity — a
daily mean versus an instantaneous short-duration peak — and converting
one to the other requires an explicit gust-factor parameterization
(approximately 1.4-1.7 in open terrain per wind-engineering codes, but
conditional on atmospheric stability and terrain roughness, not a
universal constant) that this hazard's threshold design does not
implement. Peer-reviewed literature on GCM-resolution wind-extreme
underestimation (Shen et al., 2022, finding an observed-maximum gust
deficit of approximately 7 m/s at ~0.75 deg resolution; IPCC AR6 WGI
Chapter 11's "low confidence" attribution for projected severe-wind
changes, citing insufficient model resolution and parametrization to
resolve the convective and mesoscale processes that generate damaging
gusts) corroborates that a converted proxy would likely bias risk
downward in a known direction, but is supporting evidence, not the
primary rejection ground. ERA5 is therefore retained as Extreme Wind's
sole source; its Risk_i,h, RiskBand, and PSAE contributions are identical
across all three SSP columns of any comparison table or figure, stated
explicitly wherever such a table appears rather than left for a reader to
discover from columns that do not move (Section 6.3). This is treated as
a deliberate, settled epistemic position given the current state of the
science, not a data gap awaiting a better CMIP6 wind product.

### 2.6 Vulnerability (age_factor)

`age_factor` is the Vulnerability_i term of Equation 1, `>= 1`, computed
as `age_factor = 2 - clip(retention(age), 0, 1)`, where `retention(age)
<= 1` is a technology-specific capacity/efficiency retention curve and
`age = 2050 - commissioning_year` (the study horizon). A 20% retention
loss (retention 0.8) maps to `age_factor` 1.2. Per-technology retention:

- Coal: sawtooth decay, 0.25 pp/yr boiler heat-rate deterioration (IEA/
  CIAB 2010; Kim & Moon 2012, 500 MW unit; Sagaf 2020, *Journal of
  Thermal Engineering* 6(6):247-256, 660 MW unit, 0.19-0.44 %/yr, 0.25
  pp/yr central), decaying within a 5-year overhaul cycle, with 70% of
  each cycle's accumulated loss recovered at each completed cycle (30%
  becomes permanent). The 5-year cycle length and 70% recovery fraction
  are an assumed modelling premise, not values taken from the cited
  sources — no GEM field records per-plant overhaul dates (Section 8).
- Wind: linear, 0.4%/yr relative (Olauson, Edström & Rydén, 2017, *Wind
  Energy* 20:2049-2053, Swedish fleet), applied uniformly — no GEM field
  records an initial per-turbine capacity factor to condition an
  alternative form.
- Hydro: linear, 0.55%/yr (midpoint of the ~0.5-0.6 %/yr range; Turner et
  al., 2024, *Nature Communications*).
- Solar: compound, 0.7%/yr plant-level (module physics plus soiling/
  downtime/inverter losses; Deline et al., NREL, 2020, 2024; Boretti &
  Castellotto, 2024).
- Gas/oil-gas: pinned neutral, `age_factor = 1.0` — final after a bounded
  literature search (Section 8) found no citable monotonic calendar-age
  degradation curve; Grubert (2020, *IOPSciNotes*) finds the opposite
  fleet-level sign for US gas plants (running more, and more
  efficiently, as they age) but is not usable as a per-plant retention
  curve.
- Nuclear, bioenergy: fixed neutral, `age_factor = 1.0` (licensing/
  decommissioning-governed for nuclear, Blake 1992, Simola 1999; no
  fleet-level longitudinal degradation evidence for bioenergy).
- Mixed-fuel plants: simple average of component fuels' `age_factor`.
- Missing commissioning year (~5.6% of plants): `age_factor = 1.0`
  (neutral), rows kept and flagged, never dropped.

## 3. Normalization and threshold tiers

Every threshold is tagged with its evidence tier; no untagged threshold
is permitted. Min-Max normalization (`FROZEN_BOUNDS`) uses bounds
computed over the pooled distribution across all three countries jointly,
never per country — a precondition for cross-national comparability, since
a country-specific Min-Max would make Hazard = 1.0 mean different physical
intensities in different countries. Bounds are empirical pooled sample
minimum/maximum, with no percentile trim of any kind in their derivation;
they are frozen against a dated data snapshot and guarded against silent
drift by a regression check that raises on any recomputation mismatch.
Water-stress-family bounds (`ws`, `sv`, `iv`) and Extreme Wind's bound are
computed once, pooled across all three countries, with no GCM axis
(these rasters carry no GCM dimension). Extreme Heat, Drought, and
Extreme Precipitation bounds are computed per GCM, pooled over countries
and scenarios, and never blended across GFDL-ESM4/MIROC6.

Before a transform is applied, a normality/skewness check is run on each
hazard's pooled raster distribution: the Fisher-Pearson skewness
statistic (`|skew| > 0.5`, Bulmer 1979's "fairly symmetrical" convention)
is the deciding criterion; Shapiro-Wilk is computed and reported alongside
as a diagnostic only, since at the sample sizes used here (millions of
pixels, tens of thousands of plant x scenario rows) it rejects exact
normality for nearly any real geophysical sample, including mildly
skewed ones, and is not informative as a binary gate.

Variables found approximately normal or left/mildly skewed use direct
Min-Max (`direct_minmax`). Variables found significantly right-skewed use
`f(x) = -ln(1-x)` (applied to a preliminary Min-Max scaling of the raw
value padded by an upper-tail fraction of 0.05, then Min-Maxed again onto
[0,1]), not a plain log-transform: log1p compresses the upper tail of a
right-skewed variable (large values are pushed together near 1.0, exactly
where a physically extreme plant should be most separated from a
moderate one), which is the opposite of what a hazard normalization
should do; `-ln(1-x)` expands that tail instead. This is applied uniformly
to every hazard via the same empirical procedure, not preset or assumed
by hazard identity.

Applying the check to each hazard's real pooled sample yields:

| Hazard | Measured skew (GFDL-ESM4 / MIROC6, or pooled) | Classification | Transform |
|---|---|---|---|
| Water Stress (`ws`) | right-skewed, pooled | skewed | `-ln(1-x)` |
| Extreme Heat (`heat`) | right-skewed, both GCMs | skewed | `-ln(1-x)` |
| Drought/SPEI (`spei`) | 0.36 / 0.13 | fairly symmetrical | direct Min-Max |
| Extreme Precipitation (`precip`) | -0.125 / -0.586 | fairly symmetrical / mildly left-skewed | direct Min-Max |
| Seasonal Variability (`sv`) | pooled, not right-skewed | not skewed | direct Min-Max |
| Interannual Variability (`iv`) | pooled, not right-skewed | not skewed | direct Min-Max |
| Extreme Wind (`wind`) | +0.6215, pooled | skewed | `-ln(1-x)` |

Drought and Extreme Precipitation were carried on an inherited `log1p`
treatment early in development, mirroring the retired index architecture,
without having been re-evaluated against the project's own empirical
skewness check; both were subsequently reclassified to direct Min-Max
once their real pooled skew was measured and found not to be
right-skewed. Extreme Wind was classified into the `-ln(1-x)` group by
the identical empirical procedure once its own processed raster and
pooled sample became available, on its own measured skew, not by
assumed parity with any other hazard.

### 3.1 FROZEN_BOUNDS origin table

A structured table (variable, lower bound, upper bound, origin, tier,
skewness, Shapiro-Wilk diagnostic, transform applied) is produced as a
direct article/appendix asset, covering every hazard with a processed
raster. Every entry is derived empirically from the pooled sample
(minimum/maximum), never from an externally cited physical constant; the
empirical designation applies to bound derivation only and is independent
of each hazard's separately reported Tier 1/Tier 3 classification.

## 4. Correlation gate and tie-breaker rule

Before Extreme Precipitation (and, in Hydro, the water-variability terms
`sv`/`iv`) enter a bucket's applicable hazard set, correlation against
existing terms in that bucket is computed and gated using a single
symmetric criterion, |r| < 0.80, applied uniformly regardless of the
expected sign of the relationship. Two disjoint groups of pairs are
evaluated: (a) the mandatory, non-gated Water Stress/Drought pair,
exempt from the exclusion rule by design; and (b) five gated candidate
pairs, subject to the exclusion rule — Extreme Precipitation vs. Water
Stress, Extreme Precipitation vs. Drought, `sv` vs. Water Stress, `iv`
vs. Water Stress, and `sv` vs. `iv`. Extreme Wind and Wildfire are not
part of this gate: Extreme Wind is assigned per bucket by mechanistic
rationale (Section 2.5), never by inter-hazard correlation, and Wildfire
is deferred (Section 8).

Before computing r, both layers being compared are harmonized to a
common spatial support — every candidate raster already shares one
per-country 1 km reference grid by construction, verified programmatically
rather than reprocessed. Pearson's r is the default decision statistic
(all candidates are continuous physical quantities); Spearman's rho is
always computed alongside, and substitutes as the decision statistic on
a per-cell nonlinearity flag (`|rho| - |r| > 0.10`) rather than being
forced uniformly. r is computed per country, never pooled for the
verdict (a pooled reference row is also reported), and per GCM for the
two GCM-dependent terms (`spei`, `precip`), never blended.

**Pre-registered tie-breaker hierarchy**, fixed before the gate was run:
(1) mechanistic primacy — retain the variable with the more direct causal
link to the specific bucket's failure mode, decided per bucket, so the
same failed pair can resolve differently in different buckets; (2)
data-tier confidence — if mechanistic relevance is equal or ambiguous,
retain the higher-tier, lower-proxy-dependency dataset; (3) for the
`sv`/`iv` pair specifically, `iv` is retained over `sv` on convergent
Tier 2 evidence: PNNL's drought-hydropower technical report and FAQ
(Pacific Northwest National Laboratory, *Drought Impacts on Hydroelectric
Power Generation in the Western United States*, PNNL-33212) document,
via the Colorado River case, that reservoirs are managed to absorb
seasonal drought as routine operation, but sustained interannual drought
is a distinct structural threat; independently, Moghaddasi, Gavahi,
Moftakhari & Moradkhani (2024), *Environmental Research Letters* 19(8),
find that larger reservoir storage capacity weakens the correlation
between seasonal hydrological drought and hydropower generation. The two
sources are read together as convergent, mechanism-consistent Tier 2
evidence for treating the same buffering capacity that absorbs seasonal
drought as exhaustible under sustained multi-year drought.

**Empirical result, all three countries, closed:** every gated pair
passed (|r| < 0.80) in every country/bucket/GCM cell — no candidate was
excluded, and the tie-breaker hierarchy was never invoked on real data.
The highest observed |r| among the five gated pairs was 0.702 (Seasonal
vs. Interannual Variability, Hydro, Portugal). Representative real
values: Extreme Precipitation vs. Water Stress, Hydro, India, GFDL-ESM4,
r = -0.354; Extreme Precipitation vs. Drought, Hydro, India, GFDL-ESM4,
r = -0.495. The mandatory, non-gated Water Stress vs. Drought pair was
computed and reported alongside (Pearson/GFDL-ESM4 then Spearman/MIROC6):
Brazil r = 0.039/-0.283, Portugal r = -0.003/0.049, India r =
0.236/0.140 — consistently weak, corroborating the mechanistic
distinction between structural water stress and short-term
precipitation-evapotranspiration deficit without needing the correlation
to be high for that statement to hold. The nonlinearity flag fired for 4
of 48 real-data cells (Seasonal Variability vs. Water Stress, Hydro,
Portugal; Interannual Variability vs. Water Stress, Hydro, Portugal and
India; Water Stress vs. Drought, Hydro, Brazil, MIROC6), each reported
explicitly rather than silently substituted. The full pairwise matrix
(Pearson's r, Spearman's rho, sample size, and decision-method flag per
pair/bucket/country/GCM) is a retained supplementary-figure artifact.

## 5. RiskBand classification

Every plant is classified into a discrete band per applicable hazard, per
bucket, using the applicable-hazard table established by the correlation
gate (Section 4) and the mechanistic assignments of Section 2:

| Bucket | Applicable hazards (H_b) | \|H_b\| |
|---|---|---|
| Hydro | Water Stress, Drought, Extreme Precipitation, Seasonal Variability, Interannual Variability | 5 |
| Thermal | Water Stress, Extreme Heat, Extreme Precipitation | 3 |
| Wind | Extreme Wind | 1 |
| Solar | Extreme Heat, Extreme Precipitation, Extreme Wind | 3 |

`sv`/`iv` are included in Hydro's H_b only, not Thermal's: hydraulic head
and inflow are sensitive to both seasonal and multi-year water
variability, but no cooling-technology field exists in the ingested GEM
data to justify an equivalent water-variability-specific mechanism for
Thermal beyond what Water Stress already captures.

Consolidated tier/threshold table:

| Hazard | Bucket | Tier | Basis |
|---|---|---|---|
| Water Stress | Hydro, Thermal | 1 | WRI Aqueduct absolute cutoffs 0.1/0.4/0.8 |
| Drought (SPEI) | Hydro | 3 | pooled P75/P90/P95 of months/yr SPEI<=-1.0 (P50 diagnostic) |
| Extreme Precipitation | Hydro, Thermal, Solar | 3 | pooled P75/P90/P95 of days/yr pr>local-P95 (P50 diagnostic; bucket-invariant raw indicator, same cuts reused across all three buckets) |
| Extreme Heat | Thermal | 3 | pooled P75/P90/P95 of days/yr tasmax>40 degC (P50 diagnostic) |
| Extreme Heat | Solar | 3, final | same cuts as Thermal (bucket-invariant raw indicator) |
| Seasonal Variability | Hydro | 3 | pooled P75/P90/P95 of raw sv (P50 diagnostic) |
| Interannual Variability | Hydro | 3 | same as Seasonal Variability |
| Extreme Wind | Wind | 1 | IEC turbine cut-out ~25 m/s, binary (Low/Extreme) |
| Extreme Wind | Solar | 3, final | pooled P90/P95/P99 of ERA5 mean annual max gust (P75 diagnostic) |

Percentile cuts are computed live from the current plant sample, not
frozen: they are explicitly sample-relative, not absolute physical
thresholds, and are pooled globally (every applicable bucket's plants,
all countries, all water/heat scenarios), per GCM for GCM-dependent
hazards, never blended across GCMs.

### 5.1 Band-count convention

Every Tier 3 row above uses a four-percentile cutoff set (P50/P75/P90/P95,
or P75/P90/P95/P99 for Extreme Wind/Solar), but the framework names
exactly four RiskBand labels (Low/Medium/High/Extreme). Four cuts
naturally bound five zones; the lowest percentile in each set (P50, or
P75 for Extreme Wind/Solar) is reported as a diagnostic statistic only
and is never a RiskBand boundary, and the remaining three cuts bound the
four canonical labels. A fifth label ("Very High") to use every cut
literally was considered and rejected as inflating the band structure to
accommodate an implementation detail — the same category of move already
rejected for HAZUS-MH's depth cutoffs. Tier 1 hazards need no such rule:
Water Stress's three absolute cutoffs and Wind-bucket Extreme Wind's
single binary cutoff already fit the four-band/two-band schemes exactly.

## 6. PSAE aggregation

For plant *i* in bucket *b* with applicable hazard set H_b:

PSAE_i = ( sum over h in H_b of 1[RiskBand_i,h >= High] ) / |H_b|   (Equation 2)

PSAE_i uses RiskBand_i,h, the threshold classification of the raw hazard
value alone (Section 5); it does not incorporate Exposure or
Vulnerability. This answers a physical-exposure question independent of
asset scale or condition, avoiding the compensatory dilution a weighted
composite introduces. Weighting and a continuous/ordinal alternative were
both considered and rejected: weighting reopens the continuous-weighting
problem PSAE was designed to close, and a continuous/ordinal PSAE
reintroduces the same problem in a different form.

Classification, applied where |H_b| >= 3 (Hydro, Thermal, Solar):

- PSAE = 1.0 -> EXTREME
- 0.5 <= PSAE < 1.0 -> HIGH
- 0.0 < PSAE < 0.5 -> MEDIUM
- PSAE = 0.0 -> LOW

For Wind (|H_b| = 1), the four-band classification cannot be populated
(only {0, 1.0} are possible); a compressed scheme is used instead,
derived from the same cutoffs without introducing a new one: Wind maps
to {LOW, EXTREME}. The raw PSAE fraction is always reported alongside
the categorical label, for every bucket. The 1.0/0.5/0.0 cut points are
Tier 3, author-declared convention, no literature precedent, evaluated by
scenario-discovery sensitivity analysis (Section 7.3), not Sobol.

### 6.1 Missing-hazard convention: complete-case

A plant can have a missing/undefined RiskBand for one hazard in its
bucket's H_b — for example, plants outside Aqueduct basin coverage, or
outside a processed CMIP6/ERA5 raster's coverage at that coordinate. When
any hazard in a plant's H_b has a missing RiskBand, PSAE_i for that
plant is undefined (not computed over a reduced denominator, and not
silently treated as "not High"). |H_b| for a given bucket is always the
bucket's full nominal count (Section 5); it is never shrunk per-plant to
match whatever subset of hazards happens to have data for that specific
plant. This complete-case convention was chosen over two alternatives:
available-case (H_b shrinks per-plant to the count of hazards with a
real band) was rejected because it would make |H_b| silently
plant-dependent, undermining the exact within-bucket comparability
property PSAE is built to guarantee; treat-as-not-High (a missing hazard
counts toward the denominator but never the numerator) was rejected
because it would make every data gap silently read as "this hazard is
not severe here," systematically understating PSAE_i exactly where the
underlying data is weakest, with no signal that this occurred.

A plant with an undefined PSAE_i under this rule is never silently
omitted from the output table: the row exists with an explicit
undefined `psae` value, and the output carries a non-strippable,
explicit `psae_complete` flag distinguishing "PSAE_i = 0.0 (LOW,
computed, no hazard reached High)" from "PSAE_i = undefined (not
computed, at least one hazard in H_b has no RiskBand)" — these never
collapse to the same value. A `missing_hazards` field names which
member(s) of H_b were unavailable for that plant. A per-bucket,
per-country coverage summary (count and fraction of plants with PSAE_i
undefined) is part of the aggregation output.

### 6.2 Bucket identity and comparability

PSAE outputs carry their bucket identity as a non-strippable field. PSAE
is valid only within the same technology bucket (Solar vs. Solar, Thermal
vs. Thermal), across any country — never across buckets (Solar vs.
Thermal), because |H_b| differs by bucket and the index is a within-bucket
saturation fraction, not an absolute severity scale. This rule is stated
in every PSAE-based figure caption and table header; PSAE values from
different buckets are never plotted on the same shared color scale or
ranked in the same list. Risk_i,h is valid across both technology and
country, strictly within the same hazard (Risk_Heat for a Thermal plant
in Portugal vs. Risk_Heat for a Solar plant in India is a valid
comparison; Risk_Heat vs. Risk_Drought for the same plant is not, and is
never computed as a sum or otherwise combined figure). Cross-national
validity for both indices depends on the globally pooled FROZEN_BOUNDS
normalization (Section 3); a country-specific normalization would
invalidate this claim and is not used anywhere.

Extreme Wind's ERA5 source (Section 2.5) has no SSP axis: Extreme Wind's
Risk_i,h and RiskBand are identical across the ssp126/ssp370/ssp585
columns of any comparison table, and its contribution to PSAE_i is
identical across all three SSP columns by construction — computed once
from the ERA5 baseline and copied across the scenario axis, not because
the SSPs happened to produce the same result. This is structural exposure
to severe wind, scenario-independent, stated wherever such a table or
figure appears rather than left for a reader to infer from three
identical-looking columns.

## 7. Sensitivity and uncertainty analysis

Two distinct analyses are matched to parameter type, because
variance-based global sensitivity analysis is statistically unstable when
applied to step/threshold functions: Sobol/SALib for genuinely continuous
parameters (Section 7.1), and scenario discovery / one-at-a-time analysis
for structural/discrete parameters (Section 7.2). A general Monte Carlo
uncertainty-propagation run (Section 7.4) separately characterizes
per-country/scenario output uncertainty.

### 7.1 Sobol/SALib: parameter space (D=13)

Thirteen continuous parameters are perturbed, cross-checked directly
against the running production code before being fixed as bounds (each
row's nominal value is the production default; bounds are literature
ranges where a cited source constrains them, or a Tier 3 +/-20% default
where the nominal is itself an author-declared engineering assumption):

| # | Parameter | Nominal | Bounds | Source |
|---|---|---|---|---|
| 1 | `coal_decay_rate` | 0.0025/yr | [0.0019, 0.0044] | literature (Sagaf 2020) |
| 2 | `wind_relative_rate` | 0.004/yr | [0.0030, 0.0050] | literature (Olauson et al. 2017) |
| 3 | `hydro_retention_rate` | 0.0055/yr | [0.0050, 0.0060] | literature (Turner et al. 2024) |
| 4 | `solar_retention_rate` | 0.007/yr | [0.0056, 0.0084] | Tier 3, +/-20% default |
| 5 | `coal_overhaul_cycle_years` | 5 yr | [4, 6] | Tier 3, +/-20% default |
| 6 | `coal_overhaul_recovery` | 0.70 | [0.56, 0.84] | Tier 3, +/-20% default |
| 7 | `upper_tail_padding_fraction` | 0.05 | [0.04, 0.06] | Tier 3, +/-20% default |
| 8-13 | percentile-cut rank shift, one dimension per hazard name (`spei`, `precip`, `heat`, `sv`, `iv`, `wind`) | 0 pts | [-5, +5] percentile points | Tier 3, design default; `wind`'s positive shift clipped so no resulting percentile exceeds 99.5 |

Percentile-cut dimensions are grouped one per hazard name, not one per
percentile-family group; `wind`'s Wind-bucket assignment (Tier 1 binary
cutoff) carries no Sobol dimension of its own — only its Solar-bucket
percentile assignment does.

### 7.2 Sobol/SALib: full-scale run and results

A full-scale Sobol run (`N_0 = 1024`, `calc_second_order = False`, so the
real evaluation count is `N_0 * (D + 2) = 1024 * 15 = 15,360`) was
executed against real data for all three countries and both GCMs: 2.01
hours total runtime, 0.4712 s/draw, with `psae_complete` coverage of
99.847% (31,079,520 of 31,127,040 rows), consistent with the project's
already-established `psae_complete` incompleteness rate. Every
Sobol-aggregated statistic over `psae` masks `psae_complete = False` rows
to NaN rather than dropping them, reporting achieved coverage alongside
the statistic.

**Risk_i,h (capacity-weighted mean, pooled), full S1/ST table:**

| Parameter | S1 | ST |
|---|---|---|
| coal_decay_rate | 0.1964 | 0.2068 |
| wind_relative_rate | 0.0001 | 0.0001 |
| hydro_retention_rate | 0.4034 | 0.4046 |
| solar_retention_rate | 0.0033 | 0.0030 |
| coal_overhaul_cycle_years | 0.0008 | 0.0010 |
| coal_overhaul_recovery | 0.1908 | 0.2003 |
| upper_tail_padding_fraction | 0.1953 | 0.1946 |
| spei / precip / heat / sv / iv / wind percentile shifts (each) | ~0.0000 | ~0.0000 |

ΣS1 is approximately 0.99, with ST approximately equal to S1 for every
parameter — a near-additive response, with no meaningful parameter
interactions.

**PSAE_i (mean, `psae_complete = False` NaN-masked), full S1/ST table:**

| Parameter | S1 | ST |
|---|---|---|
| coal_decay_rate ... upper_tail_padding_fraction (all seven age_factor/padding parameters) | ~0.0000 | ~0.0000 |
| spei_percentile_shift | 0.0002 | 0.0001 |
| precip_percentile_shift | 0.4670 | 0.4675 |
| heat_percentile_shift | 0.4534 | 0.4530 |
| sv_percentile_shift | 0.0001 | 0.0002 |
| iv_percentile_shift | -0.0000 | 0.0000 |
| wind_percentile_shift | 0.0774 | 0.0776 |

ΣS1 is approximately 0.997, with ST approximately equal to S1 throughout
— the same near-additive pattern. This confirms, empirically and at full
scale, the two-chain independence built into the pipeline's own
architecture: Risk_i,h (via age_factor/normalization parameters) and
RiskBand/PSAE_i (via raw hazard percentile classification) never mix —
every age_factor/padding parameter carries S1 approximately 0 for
PSAE_i, and every percentile-cut parameter carries S1 approximately 0
for Risk_i,h.

**Manuscript caveat, binding, restated verbatim in substance from its
source closure:** `coal_overhaul_recovery` (S1 = 0.1908, ST = 0.2003) is
one of Risk_i,h's four leading sensitivity contributors — comparable in
magnitude to `coal_decay_rate` (S1 = 0.1964) and
`upper_tail_padding_fraction` (S1 = 0.1953), and roughly half of the
leading contributor, `hydro_retention_rate` (S1 = 0.4034).
`coal_overhaul_recovery` is an author-declared engineering assumption
with no calibrating source (no GEM-tracked field records plant-level
overhaul history). This finding must be reported in the manuscript as
"the model's Risk_i,h output is sensitive to an admittedly unsourced
modelling premise, not a validated empirical parameter," never as an
empirical finding about coal plant behavior.

### 7.3 Scenario discovery / one-at-a-time (structural/discrete parameters)

Applied to binary or threshold decisions Sobol is unsuited for: hazard
inclusion/exclusion in a bucket's H_b, the PSAE cut points, and the
correlation-gate cutoff. Each structural choice is toggled or shifted
independently and the resulting change in the distribution of
PSAE/RiskBand outcomes is reported, without claiming a variance
decomposition that does not apply to step functions. Executed at full
scale against real data (not only validated at small scale):

- **Hazard-removal OAT** (eleven meaningful removals: five Hydro, three
  Thermal, three Solar; Wind excluded, since |H_b| = 1 and removal would
  empty H_b). The largest observed capacity-fraction shifts are in
  Portugal: removing Extreme Heat from Solar moves 76.9 percentage
  points of capacity out of MEDIUM into HIGH/LOW; removing Extreme
  Precipitation or Extreme Wind from Solar produces the same-magnitude
  shift (76.9 pp) via the shrunk |H_b| (3 -> 2) mechanically changing
  which fraction of H_b crosses the >=1/2 HIGH threshold. Thermal/India
  removals shift 48.6-54.1 pp.

- **Correlation-gate threshold sweep** (seven thresholds, 0.60-0.90,
  against the real, closed correlation matrix). Flips relative to the
  production 0.80 baseline occur at 0.60 (15 cells), 0.65 (14), 0.70
  (13), and 0.75/0.85/0.90 (12 each); no flip occurs at 0.80 itself.
  The highest-value flip is Seasonal vs. Interannual Variability, Hydro,
  Portugal (the closest-to-gate real pair, |r| = 0.7021), which flips to
  "fail" at threshold <= 0.70, with the tie-breaker correctly retaining
  `iv` over `sv` (Criterion 3). Interannual Variability vs. Water Stress,
  Hydro, India also flips at <= 0.65 (|r| = 0.669), with the tie-breaker
  retaining Water Stress over `iv` (Criterion 2, data-tier rank).

- **PSAE cut-point sweep** (0.4/0.5/0.6 boundary shift, against real
  achievable PSAE values from the production baseline). Of nine
  achievable (H_b size, PSAE value) combinations x three shifted cuts =
  27 rows, exactly one produces a different classification than the 0.5
  baseline (H_b size = 5, PSAE value = 0.4: HIGH at cut = 0.4, MEDIUM at
  both the 0.5 baseline and cut = 0.6); every degenerate EXTREME
  (PSAE = 1.0) or LOW (PSAE = 0.0) row is unchanged at every cut, as
  designed — confirming the classification's coarseness at the extremes.

### 7.4 General Monte Carlo uncertainty propagation

A separate general Monte Carlo driver propagates the same continuous
parameter uncertainty (Section 7.1) into per-country/scenario point
estimates and confidence intervals, using per-country-scenario RNG
streams — nine streams (three countries x three water scenarios),
rather than per-country streams, since every downstream output is
already split by water_scenario and randomness should match that
granularity to avoid injecting spurious correlation across scenarios
that are supposed to be statistically independent. This choice costs a
9x runtime multiplier relative to a per-country design, since every
perturbed parameter is genuinely global (applied identically across
every country/scenario within one evaluation), so there is no cheap way
to draw one stream's own vector and get a partial recompute — each of
the nine streams requires its own full recompute per draw index.

A doubling sequence (N = 100, 200, 400, 800, 1600 per stream) was run
against real data, testing convergence on two criteria at each step: a
point-estimate relative change of less than 1% and a 95% confidence
interval half-width relative change of less than 5%, both required for
every stream and both outputs (risk, PSAE), confirmed by one further
doubling before convergence is declared:

| N (per stream) | Total draws (9x) | Elapsed | s/draw | Criteria met vs. previous step |
|---|---|---|---|---|
| 100 | 900 | 380.3 s | 0.4226 | (first step, no comparison) |
| 200 | 1800 | 738.5 s | 0.4103 | No |
| 400 | 3600 | 1457.0 s | 0.4047 | No |
| 800 | 7200 | 2983.4 s | 0.4144 | Yes (point <1% and CI half-width <5%, every stream, both outputs) |
| 1600 | 14400 | 6342.5 s | 0.4405 | Yes — confirms N=800 |

Convergence was reached and confirmed at N = 800 per stream, one
doubling short of the design's original 8,000-16,000 floor. N=800 point
estimates (mean, 95% confidence interval), per stream:

| Country/scenario | risk_mean | risk 95% CI | psae_mean | psae 95% CI |
|---|---|---|---|---|
| Brazil/bau | 645.655 | [632.282, 659.731] | 0.0388 | [0.0217, 0.0552] |
| Brazil/opt | 639.191 | [625.653, 652.524] | 0.0554 | [0.0312, 0.0799] |
| Brazil/pes | 743.260 | [726.678, 759.008] | 0.0403 | [0.0227, 0.0574] |
| India/bau | 318.161 | [311.457, 326.977] | 0.1144 | [0.0790, 0.1486] |
| India/opt | 305.244 | [298.368, 313.319] | 0.1098 | [0.0726, 0.1449] |
| India/pes | 320.975 | [314.198, 329.139] | 0.1203 | [0.0855, 0.1582] |
| Portugal/bau | 98.752 | [97.257, 100.142] | 0.5163 | [0.5004, 0.5334] |
| Portugal/opt | 95.965 | [94.528, 97.423] | 0.5158 | [0.4997, 0.5325] |
| Portugal/pes | 96.532 | [95.075, 97.938] | 0.5125 | [0.4875, 0.5312] |

The N=1600 confirmation step's relative change against N=800 was
comfortably inside tolerance for every stream and both outputs
(point-estimate relative change 0.00004-0.00838; confidence-interval
half-width relative change 0.00000-0.01703), confirming N=800 as the
converged sample size rather than a coincidental single-step pass.

## 8. Limitations

The following declared limitations are the standing, consolidated record
for this framework. Each is stated as declared; items marked
Revisitable remain open to a better alternative if one appears, and are
not resolved or softened here.

- **Sea-level rise excluded from the hazard set.** No defensible
  empirical basis (per-technology coastal-flooding/storm-surge
  coefficients) exists for the land-based fleet studied. Status:
  Revisitable — a natural extension once per-technology coefficients for
  coastal flooding and storm surge are available.

- **Per-bucket hazard weights are a judgment call, not a calibration.**
  (Applicable to the retired weighted-sum architecture's water/heat/
  drought weights; superseded in the current Risk_i,h/RiskBand/PSAE
  architecture, which uses no continuous cross-hazard weighting at all.)
  No published water/heat/drought relative-importance ratio exists in
  the literature for any of these technologies.

- **Thermal bucket treated as homogeneous.** Once-through, recirculating,
  dry, and hybrid cooling systems are not distinguished within the
  Thermal bucket; all thermal plants share one water-stress sensitivity.
  No cooling-technology field (under any name) exists in the GEM Global
  Integrated Power Tracker for Brazil, Portugal, or India; the closest
  field, `Technology`, records boiler/turbine cycle type, not condenser
  cooling system. Status: Final unless a future GEM release (or an
  alternative plant-level source) adds the field. Declared explicitly as
  likely overstating water-stress risk for whatever dry-cooled fraction
  exists within Thermal.

- **No per-plant overhaul/retrofit/repowering date is available.** The
  coal age_factor's overhaul cycle (5-year cycle, 70% recovery) is an
  assumed modelling premise, not derived from a real overhaul-history
  source. No "retrofit"/"repower"/"refurbish" column exists in the GEM
  workbook; the adjacent "Conversion" field family records fuel-
  conversion events, not overhaul dates, and is effectively empty.
  Status: Revisitable — would be revisited if a real overhaul-history
  source appears.

- **Extreme Precipitation: Tier 1 downgraded to Tier 3.** Uses a
  sample-relative percentile cutoff (P95 of wet-day `pr`, ETCCDI
  convention), not a cited absolute inundation-depth threshold. The
  drafted HAZUS-MH inundation-depth values do not exist in the primary
  FEMA Hazus Flood Model Technical Manual; HAZUS-MH uses continuous
  depth-damage curves per building-occupancy type, not discrete class
  thresholds. Status: Final at this tier; would only be revisited if a
  defensible absolute cross-national threshold is identified.

- **Solar Extreme Wind: no Tier 1 structural threshold exists; ERA5 gust
  percentile is final, not contingency.** No single defensible Tier 1
  value exists for solar-tracker structural wind uplift: ASCE 7's design
  wind speed is inherently site-specific, and manufacturer survival
  ratings vary by product generation. Status: Final, not contingency —
  explicitly not pending a future Tier 1 value.

- **Wildfire (FWI/EFFIS) deferred, not implemented.** Daily near-surface
  relative humidity, required for a self-computed Canadian FWI System, is
  absent from the CDS `projections-cmip6` daily catalogue for both
  configured GCMs under any scenario; the one alternative global source
  checked (ETH Zurich FWI-CMIP6, Quilcaille et al., 2023) has zero
  GFDL-ESM4 coverage and provides only annual, reference-period-relative
  indicators, not daily FWI or EFFIS-compatible absolute classes. Status:
  Same treatment as the SLR exclusion — deferred, future work if a data
  source appears.

- **Extreme Wind: ERA5 historical baseline, scenario-invariant by
  design.** Extreme Wind is the one hazard sourced from ERA5 historical
  reanalysis (1991-2020) rather than a CMIP6 SSP projection; its
  Risk_i,h/RiskBand/PSAE contribution is identical across all three SSP
  columns. No CMIP6 daily-maximum or gust wind variable exists on the CDS
  catalogue for either configured GCM, and the one daily variable that
  does exist (`sfcWind`, daily mean) is not the same physical quantity as
  the ERA5 instantaneous gust this hazard's threshold design uses.
  Status: Final — a settled epistemic position, not a placeholder.
  Explicitly not reopened as a "find better wind data" item; even a
  future CMIP6 daily-maximum/gust product appearing on the catalogue
  would resolve only one of the two independent rejection grounds and
  would not by itself reopen this.

- **GCM pair (GFDL-ESM4, MIROC6): operational selection, not an
  ECS-based bounding design.** The two-GCM pair is not a
  climate-sensitivity-bounding design: both sit near the low end of the
  CMIP6 ECS range and do not span it. GFDL-ESM4's original selection as
  the sole/primary model predates this project's decision record
  entirely and has no recorded justification. Status: Final as a
  documentation/framing matter — does not reopen the pair choice.

- **Gas/oil-gas age_factor: pinned neutral, confirmed final after a
  bounded literature search.** No citable Tier 1/Tier 2 monotonic
  calendar-age degradation curve exists for gas/combined-cycle turbines
  analogous to coal's curve; engineering degradation literature reports
  loss in fired-operating-hours terms, not calendar-age terms, confounded
  by dispatch pattern and maintenance regime this project has no
  per-plant data for. Fleet-level longitudinal evidence (Grubert, 2020,
  *IOPSciNotes*) found the opposite sign at the fleet level (US gas
  plants ran more, and more efficiently, as they aged), meaning even the
  directional sign of a naive age curve would be wrong if taken from this
  evidence at face value. Status: Final, not still-pending. Gas/oil-gas
  remains `age_factor = 1.0` by declared design choice (absence of
  evidence, not evidence of no effect); revisit only if a new,
  calendar-age-indexed, per-plant-comparable source is published.

- **IBTrACS physical-occurrence validator: fixed-radius proxy, not real
  per-storm wind-field data.** The `wind` hazard term's
  Corroborated/No Record state is decided by a fixed 100 km great-circle
  distance from the plant to any qualifying track point, not by each
  storm's own recorded wind-field extent. Per-quadrant wind-radius fields
  exist in IBTrACS but have large, non-random coverage gaps across
  agencies and decades; a fixed radius at the conservative (small) end of
  published mean 34-kt wind-radius climatology was chosen instead so this
  validator under-claims rather than over-claims corroboration. Basin
  CSV files are NOAA's "final" product, updated roughly twice a year — a
  storm from the last few months before acquisition may be under-revised
  or briefly absent. Status: Revisitable — would be reopened by a future
  decision to build a per-quadrant wind-field match instead, or to re-run
  acquisition nearer to a reporting date for maximal basin-file currency.

Two further items, though not standalone limitations in their own right,
are declared explicitly as bounded, transparent design choices rather
than validated empirical findings: (i) the PSAE aggregation cut points
(1.0/0.5/0.0) and the correlation-gate threshold (|r| < 0.80) are Tier 3,
author-declared conventions, evaluated by scenario-discovery sensitivity
analysis (Section 7.3), not derived from a calibration; (ii) age_factor's
role as a vulnerability proxy is explicitly bounded — it captures
structural exposure via capacity retention, not adaptive capacity
(retrofit, maintenance quality), a design limitation shared with
comparable published frameworks that also lack asset-level retrofit
data.
