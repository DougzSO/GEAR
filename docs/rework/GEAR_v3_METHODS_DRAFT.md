# GEAR: Methods

*Consolidated draft, distilled from `docs/DECISIONS.md`, `docs/LIMITATIONS.md`,
`docs/PROJECT_STATE_SNAPSHOT.md`, `docs/rework/GEAR_v3_methodology_nature_format.md`
and `docs/rework/PHASE6_DESIGN.md`. Nature Climate Change Methods format.
Not a replacement for the working methodology draft; a review distillation.*

## Study area and data sources

The assessment covers the operating power-generation fleet of Brazil,
Portugal, and India, drawn from the Global Energy Monitor (GEM) Global
Integrated Power Tracker (manual export, dated snapshot). Only plants with
recorded status "operating" enter the analysis; under-construction,
announced, and pre-construction records are retained separately. Because
only operating plants are included, the most recent representable
commissioning year is capped at the export date — a declared boundary of
the input data, not a modelling artefact. Generating units are aggregated
to plants by country, normalised name, and coordinate (tolerance ≈100 m);
capacity is summed, commissioning year is the earliest constituent unit's
year, and a divergent fuel type across units is flagged as a mixed-fuel
plant. Plants are assigned to one of four technology buckets — Hydro,
Thermal (coal, oil/gas, nuclear, bioenergy, geothermal merged on the shared
mechanism of cooling-water dependence), Wind, and Solar PV.

National boundaries are GADM 4.1 (administrative level 0). For Portugal,
the boundary and asset set are reduced to the mainland polygon; Azores and
Madeira records are excluded and archived separately, since the
hydroclimatic regime and the bounding boxes used for climate data queries
are continental in focus. All spatial layers are produced in EPSG:4326 on a
common ~1 km nominal grid (0.008333°) — the resolution of the finest native
hazard input (Aqueduct basin rasterisation); coarser climate-model layers
are geospatially interpolated onto this grid, a statement that is made
explicit throughout: this is geospatial interpolation, not statistical or
dynamical downscaling, and effective information content remains bounded
by each source's native resolution.

Broad-impact disaster corroboration draws on the EM-DAT Archive
(UCLouvain Dataverse), filtered to the three study countries and to
Drought, Extreme temperature, Flood, and Storm event types, post-2000.
Physical-occurrence corroboration for the wind hazard draws on NOAA NCEI
IBTrACS v04r01 (public domain, one WMO ocean-basin file per country).

## The Hazard–Exposure–Vulnerability formulation

GEAR produces two deliberately distinct, unmerged outputs per plant and
does not compute a single aggregate "total risk" score. Following the
IPCC AR5/AR6 risk framework, for plant *i* under hazard *h*:

Risk<sub>i,h</sub> = Hazard<sub>i,h</sub> × Exposure<sub>i</sub> × Vulnerability<sub>i</sub>  (1)

- **Hazard<sub>i,h</sub>** ∈ [0,1]: hazard-specific normalised intensity,
  bounds pooled across all three countries jointly (see Normalization).
- **Exposure<sub>i</sub>**: installed capacity in MW, measured rather than
  modelled (Tier 1 by construction). Reported in two forms that are never
  conflated: raw linear MW ("Systemic Capacity at Risk", used for any
  grid-operator-relevant absolute comparison) and log<sub>10</sub>(MW + 1)
  ("Intrinsic Asset Risk"), used only as a map/legend display transform so
  that a small number of very large plants do not visually mask physically
  severe risk at smaller assets. The log transform is a visualisation
  device, not a second metric; all comparability statements below refer to
  the untransformed Risk<sub>i,h</sub>. The log base and offset are Tier 3,
  author-declared, with no literature precedent.
- **Vulnerability<sub>i</sub>**: an age_factor ∈ [1,2], computed as
  2 − clip(retention(age), 0, 1), where retention(age) is a
  technology-specific capacity/efficiency retention curve and
  age = 2050 − commissioning year. A 20% retention loss therefore maps to
  an age_factor of 1.2. age_factor is explicitly bounded in scope: it
  captures structural exposure via capacity retention, not adaptive
  capacity (retrofit quality, maintenance regime) — a limitation shared
  with comparable published frameworks that also lack asset-level retrofit
  data, not treated as an omission.

  Retention curves by technology: **coal** follows a sawtooth decay
  (0.25 pp/yr boiler heat-rate deterioration; IEA/CIAB 2010; Kim & Moon,
  2012; Sagaf, 2020, *Journal of Thermal Engineering* 6(6):247–256,
  0.19–0.44%/yr observed range) within an assumed 5-year overhaul cycle,
  recovering 70% of that cycle's accumulated loss at each overhaul — the
  cycle length and recovery fraction are an explicit modelling premise, not
  values taken from the cited sources, because no per-plant overhaul-date
  field exists in GEM for any of the three countries. **Wind** uses a
  uniform 0.4%/yr relative decline (Olauson, Edström & Rydén, 2017, *Wind
  Energy* 20:2049–2053, Swedish turbine fleet), since no per-plant initial
  capacity factor exists in GEM to support a capacity-factor-conditioned
  form (that form is retained in source as unused, documented dead code).
  **Hydro** uses a linear 0.55%/yr decline (midpoint of a ~0.5–0.6%/yr
  range; Turner et al., 2024, *Nature Communications*). **Solar** uses a
  compound 0.7%/yr decline (Deline et al., NREL, 2020/2024; Boretti &
  Castellotto, 2024). **Gas/oil-gas, nuclear, and bioenergy** are pinned at
  age_factor = 1.0 (neutral); for gas/oil-gas this was confirmed final
  after a bounded literature search found no citable calendar-age
  degradation curve analogous to coal's — engineering degradation
  literature for gas turbines is reported in fired-operating-hours terms
  (dominated by recoverable compressor fouling), not calendar age, and
  fleet-level longitudinal evidence (Grubert, 2020, *IOPSciNotes*) finds
  the opposite sign at fleet level to coal, meaning even the direction of
  a naive age curve would be unsupported. Mixed-fuel plants (6, all
  thermal) take the simple average of their component fuels' age_factor.
  Plants with missing commissioning year (5.6% of the fleet: Brazil 1.8%,
  Portugal 2.4%, India 9.7%, concentrated in wind and solar) are retained,
  flagged, and given a neutral age_factor rather than dropped or imputed.

### Temporal horizon

Water Stress (`ws`, WRI Aqueduct 4.0 `future_annual`, horizon 50) is
itself a mid-century projected indicator, already cross-walked to the same
three SSP pathways used elsewhere (opt→SSP1-2.6, bau→SSP3-7.0,
pes→SSP5-8.5); no historical-baseline substitution is used. One residual,
declared alignment note: the Aqueduct product represents conditions
"around 2050" (period-representative), while the CMIP6-sourced hazards use
an explicit 2041–2070 thirty-year window — treated in the manuscript as a
standard, literature-consistent approximation of the same mid-century
target, not a methodological flaw.

## GCM selection

Every CMIP6-sourced hazard (Extreme Heat, Drought, Extreme Precipitation)
is drawn from two GCMs, GFDL-ESM4 and MIROC6, run across SSP1-2.6,
SSP3-7.0, and SSP5-8.5, never blended (GFDL-ESM4 is treated as primary,
MIROC6 as an independent sensitivity panel). GFDL-ESM4's role as the
anchor model is an inherited operational default from this project's prior
codebase, with no documented original justification. MIROC6 was selected
operationally: of four CDS-catalogued candidates with full three-SSP
coverage, two were excluded on availability/realisation-variant grounds,
and MIROC6 was chosen over the remaining fallback (MPI-ESM1-2-LR) for
qualitative structural divergence from GFDL-ESM4.

By equilibrium climate sensitivity (ECS), the two models sit close
together near the low end of the CMIP6 ensemble — GFDL-ESM4 2.6–2.7 K
(Dunne et al., 2020, *JAMES*; Zelinka et al., 2020, *GRL*), MIROC6 2.6 K
(Tatebe et al., 2019, *GMD*), against a full-ensemble range of
approximately 1.8–5.6 K and a multi-model mean near 3.7 K (Zelinka et al.,
2020; Meehl et al., 2020, *Science Advances*). The pair therefore does not
bound or span the CMIP6 sensitivity range and is not presented as an
ECS-bounding design. What it demonstrates instead is structural and
regional divergence — distinct convection schemes, model lineage, and
native grid resolution (GFDL-ESM4 ≈1°×1.25°, MIROC6 ≈1.4°×1.4°) — reflected
in this pipeline's own reprocessing, where extreme-heat-day counts for
identical plants and scenarios differed by one to two orders of magnitude
between the two models, and wind/solar hazard scores were near-zero under
GFDL-ESM4 and near-saturated under MIROC6. Independent regional evaluation
literature is directionally consistent: MIROC6 was flagged as
significantly underestimating near-surface wind speed in a 22-model
Mediterranean evaluation and ranked worst-of-13 CMIP6 models for
historical surface air temperature over Thailand (Kamworapan et al., 2021,
*Heliyon*) — single-study, regional findings, reported at that weight, not
as a global consensus verdict.

**Declared limitation (open, not reopening the pair choice itself).** The
original operational selection of this pair has no recorded
climate-sensitivity justification; this is stated as a documentation
matter, not treated as authorising a change to the pair.

## Per-hazard processing

Five core hazards, comparably available across all three countries, plus
Extreme Wind assigned per technology bucket on mechanistic grounds:

| Hazard | Source | Mechanism | Threshold tier |
|---|---|---|---|
| Water Stress | WRI Aqueduct 4.0 (`future_annual`, 2050) | Thermal cooling-water availability; hydraulic inflow | Tier 1 — WRI absolute category cutoffs (<0.1 / 0.1–0.4 / 0.4–0.8 / >0.8) |
| Extreme Heat | CMIP6 `tasmax`, mean days/yr >40 °C | PV efficiency loss; thermal cycle efficiency | Tier 3 (both Thermal and Solar) — pooled P75/P90/P95 of days/yr, P50 diagnostic only |
| Drought (SPEI-12, Thornthwaite PET) | CMIP6 `pr` + `tas` | Hydro inflow, hydraulic head | Tier 3 — pooled P75/P90/P95 of months/yr SPEI ≤ −1.0 |
| Extreme Precipitation | CMIP6 `pr` (ETCCDI P95 wet-day exceedance, days/yr) | Flooding/overtopping at hydraulic, thermal, and solar assets | Tier 3 — pooled P75/P90/P95, same cuts reused across buckets |
| Extreme Wind (Wind bucket) | ERA5 instantaneous 10 m gust, 1991–2020 | Turbine cut-out stress | Tier 1 — IEC design cut-out speed, ~25 m/s, binary Low/Extreme |
| Extreme Wind (Solar bucket) | ERA5 mean annual maximum gust, 1991–2020 | Tracker structural uplift | Tier 3 — pooled P90/P95/P99, P75 diagnostic only, final (not a placeholder) |
| Seasonal / interannual water variability (sv, iv) | Derived water-variability indicators | Hydro headloss under short- and multi-year variability | Tier 3 — same P75/P90/P95 convention, no Tier 1 source exists |

Thornthwaite PET (rather than Hargreaves) was used for the drought term
because daily `tasmin` is absent from the CDS catalogue for GFDL-ESM4
under SSP3-7.0; Hargreaves would have silently dropped one GCM/scenario
cell.

**Extreme Heat, Solar bucket.** A Tier 1 PV efficiency-loss-per-degree
cutoff was investigated and rejected after a bounded search: manufacturer
temperature coefficients vary by module technology by more than a factor
of two (crystalline silicon ≈−0.3 to −0.5%/°C; CdTe ≈−0.21%/°C; CIGS
≈−0.2 to −0.45%/°C), GEM records no per-plant module-technology field, and
IEC 61215/61730 certify a manufacturer-specific coefficient rather than
mandate a universal one; IEC 61730's 98th-percentile module-temperature
limit is a safety qualification, not a performance-loss threshold. Solar
Extreme Heat therefore uses the same Tier 3 percentile method and cuts as
the Thermal row (the underlying `tasmax`>40 °C indicator does not vary by
bucket); this is final, confirmed after the bounded search closed, not a
provisional placeholder.

**Extreme Precipitation.** A drafted HAZUS-MH absolute inundation-depth
threshold (0.2/0.5/1.5 m) was rejected: the specific values do not exist
in the primary FEMA Hazus Flood Model Technical Manual, which uses
continuous depth–damage curves per building-occupancy type, structurally
incompatible with this pipeline's CMIP6 `pr` input (no
precipitation-to-inundation-depth conversion exists). The hazard is
therefore Tier 3 throughout, a sample-relative percentile cutoff (ETCCDI
R95p convention; Zhang et al., 2011).

**Extreme Wind.** Solar tracker structural wind resistance has no
defensible Tier 1 value: ASCE 7's design wind speed is inherently
site-specific (location, Risk Category, Exposure Category), and
manufacturer survival ratings vary by product generation (observed range
≈51–60+ m/s across two data points from a single manufacturer). This is
final, not contingent on a future Tier 1 value appearing. Extreme Wind is
the one hazard sourced from historical ERA5 reanalysis (1991–2020) rather
than a CMIP6 SSP projection: a CMIP6 substitution was investigated and
rejected on two independent grounds — no CMIP6 daily-maximum or gust wind
variable exists for either configured GCM under any scenario (only daily
mean `sfcWind`), and converting a daily mean to an instantaneous gust
requires an unvalidated, condition-dependent gust-factor parameterisation.
Corroborating literature on GCM-resolution wind-extreme underestimation
(Shen et al., 2022; IPCC AR6 WGI Chapter 11's "low confidence" attribution
for projected severe-wind change, on the same resolution/parameterisation
grounds) supports this as a deliberate, final choice rather than an
unresolved data gap: this hazard's Risk<sub>i,h</sub> and RiskBand are
therefore identical across the ssp126/ssp370/ssp585 columns of any
comparison table by construction, computed once from the ERA5 baseline and
carried across the scenario axis — stated explicitly in every such table,
never left for a reader to infer from unmoving columns.

**Technology-specific applicable hazard sets (H<sub>b</sub>).** Each
bucket is evaluated only against hazards with a declared physical
transmission mechanism (binary inclusion, no continuous weighting):

| Bucket | Applicable hazards (H<sub>b</sub>) | \|H<sub>b</sub>\| |
|---|---|---|
| Hydro | Drought, Water Stress, Extreme Precipitation, seasonal variability (sv), interannual variability (iv) | 5 |
| Thermal | Water Stress, Extreme Heat, Extreme Precipitation | 3 |
| Wind | Extreme Wind | 1 |
| Solar PV | Extreme Heat, Extreme Precipitation, Extreme Wind | 3 |

sv and iv are included in Hydro's H<sub>b</sub> (hydraulic head/inflow is
sensitive to both seasonal and multi-year variability) but explicitly not
in Thermal's, since no cooling-technology field exists in GEM to justify a
water-variability-specific mechanism for Thermal beyond what Water Stress
already captures. Per-bucket weighting of the water/heat/drought
contribution within a bucket (w<sub>water</sub>/w<sub>heat</sub>/w<sub>drought</sub>)
is an explicit author judgement call, not a calibration — no published
relative-importance ratio exists for these technologies (Tier 3,
author-declared, flagged as a Phase 6 sensitivity candidate).

Wildfire (FWI/EFFIS) was evaluated and deferred, not modelled: daily
near-surface relative humidity, required for a self-computed Canadian FWI
System, is absent from the CDS `projections-cmip6` daily catalogue for
both configured GCMs under any scenario, and the one alternative global
source checked (ETH Zurich FWI-CMIP6; Quilcaille et al., 2023) has zero
GFDL-ESM4 coverage and provides only annual, reference-period-relative
indicators rather than daily FWI or EFFIS-compatible absolute classes.
Sea-level rise is excluded from the hazard set for the land-based fleet
studied, for lack of a defensible per-technology coastal-flooding/storm-
surge coefficient. Both exclusions are treated as future-work
opportunities, not standing TODOs.

## Normalization

All hazard rasters are resampled onto a single unified spatial grid and
referenced to the same nominal temporal window before normalisation.
Min–Max normalisation (`FROZEN_BOUNDS`) uses bounds computed over the
pooled distribution across all three countries jointly, not per country —
a precondition for cross-national comparability, since a country-specific
Min–Max would make Hazard = 1.0 mean different physical intensities in
different countries.

Before finalising a hazard's transform, a skewness check (Fisher–Pearson,
|skew| > 0.5, Bulmer 1979's "fairly symmetrical" convention) decides
between two transforms; Shapiro–Wilk is reported alongside as a diagnostic
only, since at this sample size it rejects exact normality for nearly any
real geophysical sample and is not informative as a binary gate.
Approximately normal variables use direct Min–Max. Right-skewed,
long-tailed variables use *f*(x) = −ln(1−x) (applied to a preliminary,
padded Min–Max scaling, then Min–Maxed again onto [0,1]), which expands
the upper tail instead of compressing it — replacing an earlier
log1p-based design, which pushed large values together near 1.0, exactly
where a physically extreme plant should be most separated from a moderate
one. Applied empirically, not by hazard-name default: Extreme Precipitation
and Drought (SPEI) were both measured as not right-skewed (SPEI skew 0.36
GFDL-ESM4 / 0.13 MIROC6) and use direct Min–Max; Extreme Wind was measured
as right-skewed (skew +0.62) and uses the neg-log transform. A structured
FROZEN_BOUNDS origin table (variable, bounds, origin, tier, normality
result, transform applied) is produced as a direct article/appendix asset
covering every hazard.

## Correlation gate for candidate hazards

Before Extreme Precipitation, seasonal variability (sv), or interannual
variability (iv) enters a bucket's applicable set, correlation against
existing terms in that bucket is computed and gated on a single symmetric
criterion, |r| < 0.80, applied regardless of expected sign. Both layers
are harmonised to a common spatial support (upscaled to the coarser native
resolution, or to zonal statistics) before Pearson's r is computed;
Spearman's ρ is always computed alongside and substitutes as the decision
statistic where a per-cell nonlinearity flag (|ρ| − |r| > 0.10) indicates
it should. Water Stress vs. Drought, mandatory for Hydro by design, is
reported alongside but never gated.

**Pre-registered tie-breaker hierarchy**, fixed before the gate was run
against real data: (1) mechanistic primacy — retain the variable with the
more direct causal link to the bucket's failure mode, decided per bucket;
(2) data-tier confidence — if mechanistic relevance is ambiguous, retain
the higher-tier source; (3) for sv vs. iv specifically, retain iv over sv
on convergent Tier 2 evidence that seasonal drought is routinely buffered
by reservoir operation while multi-year drought depletes that same buffer
(Pacific Northwest National Laboratory, PNNL-33212, Colorado River case;
Moghaddasi, Gavahi, Moftakhari & Moradkhani, 2024, *Environmental Research
Letters* 19(8), on storage capacity weakening the seasonal-drought/
generation correlation).

The gate was run against real processed data for all three countries.
**Every gated pair passed (|r| < 0.80) everywhere data existed; no
candidate was excluded and the tie-breaker was never invoked on production
data.** The highest observed |r| was 0.702 (seasonal vs. interannual
variability, Hydro, Portugal), 0.098 below the threshold. The full
pairwise matrix (Pearson's r, Spearman's ρ, sample size, decision-method
flag per pair/bucket/country/GCM) is retained as a supplementary artefact.

## RiskBand classification

Every threshold used to classify Hazard<sub>i,h</sub> into a discrete
RiskBand carries its evidence tier. Every Tier 3 hazard except Extreme
Wind/Solar uses a four-percentile cut set (P50/P75/P90/P95); Extreme
Wind/Solar uses P75/P90/P95/P99. Because four cuts naturally bound five
zones but the framework names exactly four labels (Low/Medium/High/
Extreme), the **lowest** percentile in each set is reported as a
diagnostic statistic only and is never a band boundary; the remaining
three cuts bound the four canonical labels. A fifth label to use every
cut literally was considered and rejected as inflating the band structure
to accommodate an implementation detail. Percentiles are computed live
from the current plant sample on every run (never frozen), pooled globally
across buckets/countries/scenarios, and per GCM for GCM-dependent hazards,
consistent with the pooling convention used for normalisation bounds.

## PSAE aggregation

For plant *i* in bucket *b* with applicable hazard set H<sub>b</sub>:

PSAE<sub>i</sub> = ( Σ<sub>h∈Hb</sub> **1**[RiskBand<sub>i,h</sub> ≥ High] ) / |H<sub>b</sub>|  (2)

PSAE uses the RiskBand classification of Hazard<sub>i,h</sub> alone; it
does not incorporate Exposure or Vulnerability, avoiding the compensatory
dilution a weighted composite would introduce. Where |H<sub>b</sub>| ≥ 3
(Hydro, Thermal, Solar): PSAE = 1.0 → EXTREME; 0.5 ≤ PSAE < 1.0 → HIGH;
0 < PSAE < 0.5 → MEDIUM; PSAE = 0.0 → LOW. For Wind (|H<sub>b</sub>| = 1),
only {0, 1.0} are achievable, so a compressed {LOW, EXTREME} scheme is
used instead, derived from the same cut points; the raw PSAE fraction is
always reported alongside the categorical label for every bucket. The
1.0/0.5/0.0 cut points are Tier 3, author-declared, with no literature
precedent.

**Missing-hazard handling (complete-case).** When any hazard in a plant's
H<sub>b</sub> has a missing/NaN RiskBand, PSAE<sub>i</sub> for that plant
is undefined rather than computed over a shrunken denominator or treated
as "not High." |H<sub>b</sub>| is always the bucket's full nominal count,
never reduced per plant. This choice avoids two worse alternatives: an
implicitly plant-varying denominator that would break the bucket-level
comparability the index is designed to guarantee, and a systematic
downward bias in exactly the plants with the weakest data coverage (a
missing observation is never read as evidence of low severity). Every
plant with an undefined PSAE is retained in the output with an explicit
completeness flag and a per-bucket, per-country coverage summary,
never silently dropped or collapsed into a computed 0.0.

**Comparability.** PSAE is valid only for comparison within the same
technology bucket (any country); it is not valid across buckets, because
|H<sub>b</sub>| differs by bucket and the index is a within-bucket
saturation fraction, not an absolute severity scale — this rule is carried
into every PSAE-based figure caption and table header, and PSAE values
from different buckets are never plotted on a shared colour scale or
ranked together. Risk<sub>i,h</sub> is valid across both technology and
country, strictly within the same hazard; it is never summed or otherwise
combined across hazards for the same asset. Cross-national validity for
both indices depends on the globally pooled normalisation bounds. Every
hazard's Risk<sub>i,h</sub>/RiskBand and PSAE contribution is computed per
SSP scenario except Extreme Wind, whose ERA5 source has no SSP axis by
the deliberate design described above; any table or figure presenting the
three scenario columns side by side must visually distinguish Extreme
Wind's row from the scenario-varying hazards.

## Contextual validators

Two validator classes report the same three-state output
(Corroborated / No Record / Not Applicable) per applicable hazard per
asset, post-2000, but answer different questions and are never conflated
with each other or allowed to alter PSAE, RiskBand, or Risk<sub>i,h</sub>.

**Broad-impact validators** (EM-DAT) confirm whether a disaster crossed a
documented human/economic impact threshold; because EM-DAT systematically
under-detects hazards affecting isolated, low-population assets, a "No
Record" result is never interpreted as "no hazard occurred." This class
is fully implemented and verified against real data for all three
countries (spatial join to GADM admin-1 polygons; disaster-type-to-hazard
mapping: Extreme temperature→heat, Drought→spei, Flood→water stress).

**Physical-occurrence validators** confirm that a specific hazard event
occurred at an asset's location, independent of downstream impact. Only
the Extreme Wind term is currently covered, via IBTrACS cyclone tracks: a
`Corroborated`/`No Record` state is assigned from a fixed 100 km
great-circle radius around each plant, against post-2000 track points
meeting a 34-knot (gale-force) wind-speed floor. The 100 km radius is
deliberately conservative (the small end of published mean 34-kt
wind-radius climatology, ~150–250 km typical), chosen so the validator
under-claims rather than over-claims corroboration, given that most
IBTrACS track points — especially older and non-US-basin records — carry
no per-quadrant wind-radius field to match against directly. Verified
against real data: Brazil's only corroborating storm across the full
post-2000 South Atlantic record is Hurricane Catarina (2004), the basin's
one documented case; India shows a real, substantial corroboration density
(41.1% of wind/solar plants, 156 distinct storms) consistent with an
active cyclone basin; Portugal's corroborations trace to five identifiable
storms plausibly consistent with known Iberian storm-landfall history.

Landslide and lightning physical-occurrence sources were not investigated.
FIRMS (fire detection) was evaluated and not acquired: it would validate a
hazard (Wildfire) already excluded from the modelled hazard set, so
acquiring it would not close the physical-occurrence class under the
current hazard scope. Whether the EM-DAT disaster-type mapping should be
extended (Storm→wind; Flood→Extreme Precipitation, a more direct proxy
than Water Stress) is an open item, not yet decided.

## Sensitivity and uncertainty analysis

This analysis is **in progress, not closed**, as of the most recent
review of its implementation status. Two distinct analysis types are used
because variance-based global sensitivity analysis is unstable when
applied to step/threshold functions.

**Sobol/SALib (continuous parameters).** A 13-dimension parameter set has
been reconciled and implemented (`sobol_sensitivity.py`): three
literature-backed age_factor rates (coal decay, wind relative rate, hydro
retention), three parameters with no literature-cited perturbation range
that use a declared Tier 3 default of ±20% around the current nominal
value (solar retention rate; the assumed coal overhaul cycle length and
recovery fraction — the latter two are already declared modelling
premises, not literature-sourced points, and any resulting high
sensitivity index must be reported as a finding about the model's
sensitivity to an unsourced premise, not as an empirical finding about
coal-plant behaviour), the neg-log transform's tail-padding fraction
(same ±20% default), and one percentile-cut rank-shift dimension per
hazard name (six hazards) rather than one per percentile family. Any
parameter perturbed under the ±20% default rather than a literature-cited
range is reported in the manuscript as a Tier 3, author-declared
engineering default, never as a calibrated or literature-backed
distribution. A real, small-scale validation run (N₀=32, both output
statistics) confirms the two output chains are mechanistically
independent: RiskBand/PSAE-affecting parameters (percentile-cut shifts)
show zero sensitivity on Risk<sub>i,h</sub>, and age_factor/padding
parameters show zero sensitivity on PSAE — an empirical confirmation of
the architectural separation between the two output layers. The full-scale
Sobol run (N₀ ≥ 1024, ≈1.9 hours of computation) has not yet been
executed, pending author authorisation.

**Scenario discovery / one-at-a-time (discrete/structural parameters).**
Applied to hazard inclusion/exclusion per bucket, the PSAE cut points, and
the correlation-gate cutoff — parameters for which a variance decomposition
does not apply. This has been run at full scale against real data.
Removing any single hazard from a bucket's H<sub>b</sub> (11 meaningful
removals; Wind is excluded from this sweep since it has only one hazard
and removing it would leave an empty H<sub>b</sub>) produces PSAE-category
shifts of up to 76.9 percentage points of capacity in the most sensitive
case (removing Heat, Precipitation, or Wind from the Solar bucket in
Portugal). A sweep of the correlation-gate threshold from 0.60 to 0.90
found no flips relative to the production 0.80 cutoff at 0.80 itself; at
thresholds of 0.70 and below, the closest real pair (seasonal vs.
interannual variability, Hydro, Portugal, |r| = 0.702) flips to fail, with
the pre-registered tie-breaker correctly retaining interannual over
seasonal variability. A shift of the PSAE 0.5 boundary to 0.4/0.6 changes
the classification outcome for exactly one of 27 tested combinations,
confirming that PSAE's achievable-value structure is discrete and coarse
by construction, not a smoothly varying quantity.

**General Monte Carlo uncertainty propagation.** A convergence procedure
has been adopted: run at N = 1000, 2000, 4000, 8000, 16000; declare
convergence at the smallest N where both the point estimate's relative
change and the 95% CI half-width's relative change fall under stated
tolerances (<1% and <5% respectively) for two consecutive doublings.
Random-number-generator streams are keyed per country-scenario (rather
than per country only), so that scenario columns — which are reported as
statistically distinct throughout this framework — do not share spurious
correlation from a common random draw; this granularity was an explicit
author decision for the current parameter set, not inherited from an
earlier, structurally different parameter set. Because every perturbed
parameter is global rather than country/scenario-specific, delivering
genuine per-stream independence costs approximately ninefold more
computation than a single global draw (nine `(country, water_scenario)`
streams must each run a full recomputation per draw). A small-scale
validation run (N = 25, 50 per stream) confirms the mechanism works but is
explicitly **not converged** by the adopted criteria; the full-scale run
(N ≥ 8000 per stream, of order half a day to a day of computation on top
of the Sobol run) has not yet been executed, pending author authorisation
given this cost.

**Open items, stated as such and not resolved by inference:**
- Whether the methodology text's phrase "FROZEN_BOUNDS percentile choices"
  refers to the RiskBand Tier 3 percentile-cut thresholds (the only
  percentile-shaped continuous-parameter family that actually exists in
  the pipeline, and the reading the implemented Sobol design uses) or
  something else has not received a final author confirmation; this is a
  wording ambiguity in the methodology text between two separately named
  concepts (frozen normalisation bounds vs. RiskBand percentile cuts), not
  a modelling error.
- How plants with an undefined ("incomplete-case") PSAE value are to be
  treated inside every Phase 6 aggregate statistic is not settled as a
  final, author-confirmed policy. The current implementation masks such
  rows to NaN in every reported aggregate (never dropping the row, always
  reporting achieved coverage alongside the statistic), but this was
  adopted as an implementation default rather than closed as a
  methodological decision distinct from the earlier, separately-closed
  decision governing PSAE's own denominator.

## Limitations

The table below consolidates every declared limitation, Tier 3 downgrade,
excluded hazard, or scenario-invariance decision in the project's decision
record. "Final" indicates the item is not expected to be revisited without
new data; "Revisitable" indicates it is explicitly open to change if a
better alternative appears; "Open" indicates it is an active, unresolved
methodological question, most concentrated in the still-open sensitivity
analysis.

| Limitation | Evidence tier | Status | Date |
|---|---|---|---|
| Sea-level rise excluded from the hazard set entirely | Scope-boundary judgement | Revisitable | 2026-09-03 |
| Per-bucket hazard weights (water/heat/drought) are an author judgement call, not a calibration | Tier 3 | Revisitable (Phase 6 candidate) | 2026-09-04 |
| GEM cooling-technology field absent; Thermal bucket treated as homogeneous, likely overstating water-stress risk for any dry-cooled fraction | Data-availability finding | Final unless GEM adds the field | 2026-09-11 |
| GEM retrofit/repowering field absent; coal overhaul cycle (5 yr) and recovery fraction (70%) are assumed modelling premises | Data-availability finding | Revisitable if a real overhaul-history source appears | 2026-09-11 |
| Extreme Precipitation downgraded Tier 1 → Tier 3 (HAZUS-MH absolute thresholds rejected as not existing in the primary source) | Tier 3, ETCCDI percentile convention | Final at this tier | 2026-09-11 |
| Solar Extreme Wind uses ERA5 gust percentiles as Tier 3, final — no defensible Tier 1 structural threshold exists | Tier 3 | Final, not contingency | 2026-09-11 |
| Solar Extreme Heat uses the same Tier 3 percentile method as Thermal — no defensible Tier 1 PV efficiency-loss threshold exists | Tier 3 | Final, confirmed after bounded search | 2026-09-12 |
| Wildfire (FWI/EFFIS) deferred — required daily near-surface humidity absent from the CDS catalogue for both GCMs; the one alternative source has zero GFDL-ESM4 coverage | Data-availability finding | Revisitable, future work | 2026-09-11 |
| Extreme Wind sourced from ERA5 historical reanalysis (1991–2020), scenario-invariant by design — a CMIP6 substitution was investigated and rejected on physical-quantity-incompatibility grounds | Tier 1 (gap) + Tier 2 corroborating literature | **Final — a settled epistemic position, not a placeholder** | 2026-09-11 |
| GCM pair (GFDL-ESM4, MIROC6) does not span or bound the CMIP6 ECS range; the pair's original selection has no recorded sensitivity-based justification | Tier 1 for ECS values; none for the original pairing choice | Final as a documentation/framing matter | 2026-09-11 |
| Gas/oil-gas age_factor pinned neutral (1.0) after a bounded literature search found no citable calendar-age degradation curve; nuclear and bioenergy likewise pinned neutral | Bounded-search finding | Final | 2026-09-11 |
| Missing commissioning year (5.6% of the fleet, concentrated in Indian wind/solar) given a neutral age_factor rather than dropped or imputed | Data-completeness handling | Final (standing convention) | 2026-09-04 |
| PSAE undefined (complete-case) for any plant missing a RiskBand for one of its bucket's applicable hazards, rather than a shrunk denominator or a "not High" default | Methodological design decision | Final | 2026-09-14 |
| IBTrACS physical-occurrence validator uses a fixed 100 km radius, not real per-storm wind-field extent; track points with no reported wind speed are silently excluded from matching | Methodological-proxy judgement, general TC climatology | Revisitable | 2026-09-15 |
| Contextual validators cover only EM-DAT (broad-impact, full) and IBTrACS/wind (physical-occurrence, partial); FIRMS rejected as a hazard-scope mismatch; landslide/lightning not investigated; the EM-DAT disaster-type-to-hazard mapping has not been re-derived for two hazard terms added after it was first approved | Mixed | Open | 2026-09-14/15 |
| Sensitivity/uncertainty analysis (Sobol, scenario discovery, general Monte Carlo) implemented and validated at small scale only; full-scale runs not yet executed pending author authorisation on computational cost | Implementation status | **Open — phase in progress** | 2026-09-15 |
| Distribution family for any Sobol/Monte Carlo parameter with no literature-cited range defaults to a Tier 3, author-declared ±20% uniform band around its nominal value | Tier 3, author-declared engineering default | Final for the default itself; individual parameter ranges Open where flagged above | 2026-09-14 |
| Interpretation of "FROZEN_BOUNDS percentile choices" (methodology Section 8.1) as referring to RiskBand Tier 3 percentile-cut thresholds is the working assumption used by the implemented Sobol design, not a confirmed textual mapping | Wording ambiguity | Open | 2026-09-14 |
| Treatment of PSAE-incomplete ("complete-case") rows inside Phase 6 aggregate sensitivity statistics (currently NaN-masked, coverage reported) is an implementation default, not a closed, author-confirmed policy | Implementation default | Open | 2026-09-14/15 |
