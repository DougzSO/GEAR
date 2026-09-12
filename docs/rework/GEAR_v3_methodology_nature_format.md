# GEAR v3: Methods (Nature Climate Change format, ready for drafting)

## Overview of the risk assessment flow

GEAR produces two distinct, deliberately unmerged outputs per plant, and
retires the single aggregate index (formerly CCRS) entirely. There is
no "total plant risk" number in v3. Summing heterogeneous hazard types
(e.g., wind risk plus drought risk) into one figure is treated as a
methodological fallacy and is not attempted anywhere in this framework.

```
Raw climate/water/fire-weather data
      |
      v
Hazard_i,h  (normalized 0-1, per hazard h, per plant i,
             globally pooled cross-national bounds, Section 4)
      |
      +-----------------------------+
      |                             |
      v                             v
RiskBand_i,h                  Risk_i,h = Hazard_i,h x Exposure_i x Vulnerability_i
(threshold classification      (continuous, per hazard, MW- and
 of Hazard_i,h alone;           age-weighted; NEVER summed across hazards)
 Low/Medium/High/Extreme)             |
      |                               v
      v                         Asset Risk Magnitude
PSAE_i = count(RiskBand_i,h    (per-hazard asset-level maps and
  >= High, h in H_b) / |H_b|    prioritization rankings; comparable
      |                          across technology and country, strictly
      v                          within the same hazard, Section 9)
Physical Hazard Screening Index
(EXTREME/HIGH/MEDIUM/LOW,
 secondary, screening-only,
 comparable ONLY within the
 same technology bucket, Section 9)
      |
      v
Contextual validator overlay
(two validator classes: broad-impact
 corroboration and physical-occurrence
 corroboration; tags only, never alters
 PSAE, RiskBand, or Risk_i,h)
```

Layer 1 (Physical Hazard Screening, PSAE) answers: how many independent
physical stressors is this asset exposed to at a severe level, relative
to what is physically possible for its own technology. Layer 2 (Asset
Risk Magnitude, Risk_i,h) answers: how much capacity is at stake at this
specific asset, given its scale and condition, for one given hazard.
Comparability rules for both are stated explicitly in Section 9 and
enforced in the code and in every figure/table produced from this
pipeline; neither output is ever collapsed into the other or into a
new single score.

## 1. Hazard-Exposure-Vulnerability formulation

Following the IPCC AR5/AR6 risk framework, for plant i under hazard h:

Risk_i,h = Hazard_i,h x Exposure_i x Vulnerability_i    (1)

- Hazard_i,h in [0,1]: physical hazard intensity, hazard-specific
  normalization, globally pooled cross-national bounds (Section 4).
- Exposure_i: installed capacity (MW), measured, not modeled, Tier 1 by
  construction. Reported in two explicit forms, never conflated:
  - Systemic Capacity at Risk: raw linear MW. Used wherever the
    question is grid-operator-relevant ("how much capacity is exposed
    in absolute terms").
  - Intrinsic Asset Risk (visualization only): log10(MW + 1). Used only
    as a map/legend transform so that a handful of very large plants do
    not visually dominate a map and mask physically severe risk at
    smaller assets. This is a display transform, not a second metric;
    all comparability statements in Section 9 refer to the untransformed
    Risk_i,h. The log base and offset are Tier 3, author-declared, no
    literature precedent, stated as such.
- Vulnerability_i: age_factor in [1,2], unchanged from the existing
  implementation (2 - capacity retention curve, technology-specific).

### 1.1 Temporal horizon of hazard terms (resolved)

Prior drafts of this methodology treated Water Stress as a historical
baseline (1979-2019) in conflict with the 2041-2070 CMIP6 projection
window used for Heat, Drought, and the new hazards. This premise was
incorrect and is corrected here: the water stress indicator actually
consumed by the pipeline (`ws`, from the Aqueduct 4.0 `future_annual`
product, horizon 50) is itself a mid-century projected value, already
cross-walked to the same three SSP pathways used elsewhere in the
framework (opt->SSP1-2.6, bau->SSP3-7.0, pes->SSP5-8.5). No baseline
substitution and no reframing as a "structural proxy" are needed; the
"Tier 3 temporal framing" argument from the prior draft is withdrawn.

One residual, minor alignment note, declared rather than hidden: the
Aqueduct future product represents conditions around 2050 (a
period-representative estimate), while the CMIP6 hazards use an
explicit 2041-2070 thirty-year window. The two are not an identical
averaging window. This is treated in the article as a standard,
literature-consistent approximation (both target sustained mid-century
conditions), not a methodological flaw, and is stated as such rather
than left implicit.

## 2. Core hazard checklist

Five hazards, comparably available across Brazil, Portugal, and India,
all referenced to the same nominal mid-century window (Section 1.1) and
resampled to the same unified spatial grid (Section 4):

| Hazard | Data source | Mechanism |
|---|---|---|
| Water Stress | WRI Aqueduct 4.0 (future_annual, 2050) | Thermal cooling-water availability |
| Extreme Heat | CMIP6 tasmax | PV efficiency loss; thermal cycle efficiency |
| Drought | SPEI-12 (Thornthwaite PET) | Hydro inflow, hydraulic head |
| Extreme Precipitation | CMIP6 pr (already acquired as SPEI input) | Flooding/overtopping risk at low-elevation and hydraulic assets |
| Extreme Wind | ERA5 gust or sustained speed (10m/100m) | Wind turbine cut-out stress; solar tracker structural uplift |

Wildfire (FWI/EFFIS) was evaluated and is deferred for lack of a viable
data source across the required model/scenario matrix -- see Section
10.1, same treatment as the SLR exclusion.

Inclusion of Extreme Precipitation in a given bucket's applicable set is
conditional on the correlation gate (Section 5). Extreme Wind is not
part of a single shared hazard core; it is assigned per bucket per the
mechanistic rationale in Section 3.

**Declared limitation, not merely "data unavailable":** Extreme Wind is
the one hazard in this checklist sourced from historical reanalysis
(ERA5, 1991-2020) rather than a CMIP6 SSP-scenario projection under the
shared mid-century framing every other row uses. A CMIP6 substitution
was investigated and rejected on two independent grounds (Section 3.1):
CMIP6's only daily-resolution wind variable (`sfcWind`, daily-mean
sustained wind -- no daily-maximum variant exists on the catalogue) is
not the same physical quantity as the ERA5 instantaneous gust this
hazard's threshold design already uses, and no CMIP6 gust product exists
under any name. See Section 3.1 for the full finding and Section 9 for
the resulting cross-hazard comparability consequence.

### 2.1 GCM selection rationale (GFDL-ESM4, MIROC6)

Every CMIP6-sourced row in Section 2 (Extreme Heat, Drought, Extreme
Precipitation) is drawn from exactly two GCMs, `gfdl_esm4` and `miroc6`,
run jointly across all three active scenarios (SSP1-2.6, SSP3-7.0,
SSP5-8.5). This subsection states plainly why this specific pair, and
separates two different kinds of justification that this project's
own history blended informally: what was **operational** (catalogue
availability at the time the second model was chosen) and what is
**climatological** (how the pair actually sits in the CMIP6 ensemble).
Both are reported; neither is allowed to borrow the other's authority.

**Origin of GFDL-ESM4 as the first/primary model.** GFDL-ESM4 was the
sole CMIP6 GCM in the prior repository this project's acquisition layer
was reconstructed from, and its selection as the initial model predates
this project's own decision record. No documented justification for that
original choice survives in either repository. This is stated here
rather than reconstructed after the fact: GFDL-ESM4's role as the
anchor model is an inherited operational default, not a result of this
project having compared it against alternatives.

**Why MIROC6 as the second model (operational).** When a second GCM
became a mandatory sensitivity check, four candidates were checked
against the Copernicus CDS `projections-cmip6` catalogue for full
SSP1-2.6/SSP3-7.0/SSP5-8.5 coverage: IPSL-CM6A-LR, MIROC6, MPI-ESM1-2-LR,
CNRM-CM6-1. IPSL-CM6A-LR was excluded outright (SSP1-2.6 and SSP5-8.5
absent from its catalogue entry). CNRM-CM6-1 was passed over because
CNRM-family models typically ship as realization `r1i1p1f2`, which would
have broken variant parity with the already-downloaded GFDL-ESM4
(`r1i1p1f1`). Among the two catalogue- and variant-compatible candidates
remaining, MIROC6 was chosen over MPI-ESM1-2-LR (kept on record as the
fallback) for its greater structural divergence from GFDL-ESM4 --
distinct convection scheme and model lineage. This divergence claim was
a qualitative, author-level judgment at the time of selection, not a
comparison against a cited sensitivity metric; it is put on a
quantitative footing below.

**Climatological standing (Tier 1, literature values).** By equilibrium
climate sensitivity (ECS), the two models are close to each other and
both sit near the low end of the CMIP6 ensemble: GFDL-ESM4 ECS is
reported at 2.6-2.7 K (Dunne et al., 2020, *JAMES*; Zelinka et al., 2020,
*GRL*) and MIROC6 at 2.6 K, explicitly unchanged from its predecessor
MIROC5 (Tatebe et al., 2019, *GMD*). The full CMIP6 ensemble spans
approximately 1.8-5.6 K (INM-CM4-8 low, CanESM5 high), with a
multi-model mean near 3.7 K (Zelinka et al., 2020; Meehl et al., 2020,
*Science Advances*). **The pair therefore does not bound or span the
CMIP6 sensitivity range** -- both models sit in the lower third of it,
roughly 0.05-0.1 K apart. Framing this pair as a low-vs-high
"sensitivity bounding" pair, as this project's internal history informally
did based on observed output spread, overstates what the pair
demonstrates about global climate sensitivity and is not repeated in
this form here.

What the pair does demonstrate, and what the observed spread in this
pipeline's own outputs is actually attributable to, is structural and
regional divergence rather than global-mean sensitivity: distinct
convection parameterization, model lineage, and native grid resolution
(GFDL-ESM4's atmosphere is a cubed-sphere grid at approximately
1 deg x 1.25 deg; MIROC6 uses a T85 spectral grid at approximately
1.4 deg x 1.4 deg -- Dunne et al., 2020; Tatebe et al., 2019). This
project's own reprocessing found extreme-heat-day counts differing by
one to two orders of magnitude between the two models for the same
plants under identical scenarios, and wind/solar hazard scores that were
near-zero under GFDL-ESM4 and near-saturated under MIROC6
(`analysis/ccrs_bucket_weighted_distribution.md`) -- a genuine,
literature-consistent divergence in regional extremes and coarse-grid
behavior, not an artifact of one model being "more sensitive" in the
ECS sense. Independent regional evaluation literature is directionally
consistent with MIROC6 producing outlier behavior for the specific
variables this pipeline uses: MIROC6 was flagged as significantly
underestimating near-surface wind speed relative to observations in a
22-model Mediterranean evaluation, and was the worst-performing model
among 13 CMIP6 GCMs for historical surface air temperature over
Thailand (Kamworapan et al., 2021, *Heliyon*). These are regional,
single-study findings, not a global consensus verdict on either model,
and are reported at that evidentiary weight.

**Data-completeness track record (operational, kept separate from the
above).** Across every CDS catalogue check run in this project
(Phase 0 SPEI/Hargreaves, Phase 2.1 Extreme Precipitation, Phase 2.2
FWI/humidity, Phase 2.3 Extreme Wind), exactly one model-specific
availability gap was ever found, and it was GFDL-ESM4's, not MIROC6's:
daily `tasmin` is absent from the catalogue for `gfdl_esm4` x SSP3-7.0,
which is why this pipeline's drought term uses Thornthwaite PET
(`pr` + `tas`) rather than Hargreaves PET (`pr` + `tasmin` + `tasmax`) --
Hargreaves would have silently dropped one GCM/scenario cell from the
drought term (`analysis/spei_catalog_check.md`). Extreme Precipitation
(Phase 2.1) reuses that same already-clean `pr` series and adds no new
gap for either model. Extreme Wind (Phase 2.3) found `near_surface_wind_speed`
fully available for both models across all three scenarios; the only
absences (a daily-maximum wind variant, an instantaneous gust variable)
are not on the CDS daily catalogue for *either* model and are not
model-specific. Wildfire (Phase 2.2) was blocked by relative humidity
being entirely absent from the daily catalogue for both models under
every scenario -- a symmetric, variable-level gap, not one model doing
worse than the other; within the specific-humidity fallback that was
explored and ultimately rejected, MIROC6 had zero scenario coverage
against GFDL-ESM4's partial coverage, but this never became operative
since the fallback itself was abandoned on other grounds (Section 10.1).
Taken together, MIROC6 has not been the source of a single realized data
gap in this pipeline; if anything, the one gap on record argues against,
not for, treating MIROC6 as the operationally weaker choice.

**Why the pair remains defensible going forward.** The selection above was
made on operational grounds, not on any comparison against a sensitivity
metric -- that much is stated plainly and is not revisited here. What the
retrospective climatological analysis in this subsection adds is a
separate, after-the-fact finding: the original operational choice happens
to hold up under retrospective structural scrutiny. It does not hold up as
an ECS-bounding pair -- both models sit within 0.05-0.1 K of each other
near the low end of the CMIP6 range, and that finding is not softened or
withdrawn here. Where the pair does deliver genuine comparative value is
along a different axis than ECS: structural and regional divergence in
convection representation and native grid resolution (GFDL-ESM4 at
approximately 1 deg x 1.25 deg versus MIROC6 at approximately
1.4 deg x 1.4 deg), consistent with the two independent regional findings
already cited above -- MIROC6's wind-speed underestimation in the
22-model Mediterranean evaluation and its weakest-of-13 ranking for
Thailand surface air temperature (Kamworapan et al., 2021). This is
reported as a retrospective observation about what the pair turned out to
be useful for, not as a claim that GFDL-ESM4 and MIROC6 were deliberately
chosen for their convection-scheme or resolution contrast at the time of
selection; that would contradict the operational account given above and
is not asserted here.

## 3. Technology-specific applicable hazard subsets

Each bucket is evaluated only against hazards with a declared physical
transmission mechanism. No continuous weighting; binary inclusion with
a stated mechanistic reason. Revised from the prior draft to correct
two omissions identified on review: hydraulic structures are vulnerable
to extreme precipitation (spillway overtopping, powerhouse flooding),
and utility-scale solar trackers are vulnerable to extreme wind
(structural uplift), independent of any thermal or turbine mechanism.

| Bucket | H_b (applicable) | \|H_b\| | Exclusion rationale for the rest |
|---|---|---|---|
| Hydro | Drought, Water Stress, Extreme Precipitation | 3 | Not thermally cooled; no heat mechanism modeled for hydraulic structures |
| Thermal | Water Stress, Extreme Heat, Extreme Precipitation | 3 | Drought mechanism already captured via Water Stress; no wind-uplift mechanism for thermal plant structures |
| Wind | Extreme Wind | 1 | No water dependency; heat is not the governing failure mechanism |
| Solar PV | Extreme Heat, Extreme Precipitation, Extreme Wind | 3 | No water dependency |

Declared limitation, explicit rather than implicit: this framework
models operational and structural-stress mechanisms captured by the
five hazards above; it does not model all conceivable structural
failure modes (e.g., seismic, foundation subsidence, wildfire -- see
Section 10.1). The boundary of "in scope" is the five hazards, stated
plainly, not defended as exhaustive.

### 3.1 Wind threshold distinction between buckets (resolved)

Extreme Wind enters both the Wind bucket (turbine cut-out mechanism)
and the Solar bucket (tracker structural uplift mechanism). These are
physically distinct failure modes, and verification (Section 6, Phase 0)
found they are not comparable in evidence rigor either: turbine cut-out
speed is a single, standardized IEC design-class value (~25 m/s),
independent of site; tracker structural wind resistance is not a fixed
engineering constant, since ASCE 7's design wind speed is inherently
site-specific (derived from location, Risk Category, Exposure Category)
and manufacturer survival ratings vary materially by product generation
(observed range ~51-60+ m/s across two data points from a single
manufacturer alone). No defensible Tier 1 threshold exists for the Solar
case. The two buckets therefore do not share a threshold and are not
expected to converge on one: Wind keeps the IEC cut-out speed as Tier 1;
Solar's Extreme Wind is Tier 3, ERA5 gust percentile-based, final (see
Section 4).

**ERA5 source retained, CMIP6 substitution investigated and rejected
(declared limitation, resolved).** A CMIP6-based Extreme Wind (aligning
this hazard to the same 2041-2070/3-SSP projection framing as every other
row in Section 2) was investigated on the author's request and rejected
on two independent grounds, either sufficient alone: (1) the CDS
`projections-cmip6` catalogue's only daily-resolution wind variable is
`sfcWind` (daily-MEAN near-surface wind speed) -- confirmed available for
both configured GCMs across all three SSPs, full 2041-2070 coverage, but
no daily-maximum variant exists under any model/scenario, and no gust
variable exists on this catalogue at all; (2) `sfcWind` and ERA5's
`instantaneous_10m_wind_gust` are not the same physical quantity -- a
daily mean vs. an instantaneous short-duration peak -- and converting one
to the other requires an explicit gust-factor parameterization
(~1.4-1.7 in open terrain per wind-engineering codes, but conditional on
atmospheric stability, terrain roughness, and gust-generation mechanism,
not a universal constant) that the Wind/Solar threshold design above does
not implement. Peer-reviewed literature on GCM-resolution wind-extreme
underestimation (Shen et al. 2022; a direct comparison at ~0.75 deg
resolution finding an observed-maximum gust deficit of ~7 m/s; IPCC AR6
WGI Chapter 11's "low confidence" attribution for severe wind to
model-resolution limits) corroborates that a converted proxy would likely
bias risk downward in a known direction, but is supporting evidence, not
the primary rejection ground. ERA5 (1991-2020 historical baseline) is
therefore retained as Extreme Wind's sole source; the resulting
scenario-invariance of this one hazard is carried into Section 9's
comparability discussion. Full finding: `docs/DECISIONS.md`, "GEAR v3
Phase 2.3 follow-up: ERA5 temporal asymmetry retained (CMIP6
substitution investigated and rejected)".

**This is a stance, not an oversight.** The investigation above is not
reported here as an unresolved gap the project failed to close; it is
the basis for treating Extreme Wind's historical baseline as a
deliberate choice. IPCC AR6 WGI Chapter 11 itself attributes "low
confidence" to projected changes in severe wind in most regions,
specifically because current-generation GCMs "often do not have
sufficient resolution or accurate parametrization" to resolve the
convective and mesoscale processes that generate damaging gusts --
the same resolution limit finding 1 above documents directly on this
project's own two configured GCMs. Building a CMIP6-based future wind
trend for this hazard would have required exactly the unvalidated
gust-factor conversion rejected in finding 2 -- manufacturing an
apparent SSP-dependent trend for a physical quantity the climate
science itself does not yet claim to project reliably. A stable,
directly observed historical exposure baseline is, given the current
state of the science, the more epistemically honest representation of
Extreme Wind risk, not merely the more convenient one: it is scenario-
invariant because the underlying physical evidence does not support
a scenario-resolved alternative, not because one was never sought. This
project treats Extreme Wind as a deliberate scenario-invariant
structural exposure baseline, and this framing is not conditional on a
better CMIP6 wind product eventually appearing (Section 9; `docs/
DECISIONS.md`, "GEAR v3 Extreme Wind: reframed as scenario-invariant
structural exposure (not a data gap)").

### 3.2 Cooling technology heterogeneity within Thermal (resolved)

Applicability decides which hazards apply to a bucket, not the
magnitude of exposure within it. Once-through and dry-cooled thermal
plants have materially different water stress sensitivity, but no split
is implemented: verification (Section 6, Phase 0) confirmed no
cooling-technology field (once-through/recirculating/dry/hybrid) exists
under any name in the ingested GEM data, for any of the three countries.
The closest field, `Technology`, records boiler/turbine cycle type, not
condenser cooling system. Thermal is therefore retained as a homogeneous
bucket, and this is declared explicitly as a limitation in the article:
the current treatment likely overstates water stress risk for whatever
dry-cooled fraction exists within Thermal, which cannot be separated out
with the available data.

## 4. Hazard normalization and threshold tiers

Every threshold is tagged with its evidence tier; no untagged threshold
is permitted. All hazard rasters are resampled to a single unified
spatial grid and referenced to the same nominal temporal window before
normalization (Section 1.1), so that cross-national and cross-hazard
comparisons within the rules of Section 9 are not confounded by
differing native resolution or reference period.

| Hazard | Bucket | Tier 1 (cited, absolute) | Tier 3 (fallback) |
|---|---|---|---|
| Water Stress | Hydro, Thermal | WRI Aqueduct category cutoffs (<0.1 / 0.1-0.4 / 0.4-0.8 / >0.8) | not required |
| Extreme Heat | Solar | PV efficiency-loss-per-degree engineering threshold | not required |
| Extreme Heat | Thermal | none defensible (cooling-water-temperature thresholds do not match the ambient-air tasmax variable modeled; rejected as a mismatched-mechanism Tier 1) | Sample percentiles P50/P75/P90/P95 of tasmax>40C days (current method, retained) |
| Drought | Hydro | none available linking SPEI to generation impact | Sample percentiles of SPEI<=-1.0 months/year (current method, retained) |
| Extreme Precipitation | Thermal, Solar, Hydro | none defensible: HAZUS-MH uses continuous depth-damage curves, not categorical depth cutoffs, and is structurally incompatible with this pipeline's CMIP6 `pr` input (no precipitation-to-inundation-depth conversion step exists); verified against the primary FEMA Hazus Flood Model Technical Manual, rejected as Tier 1 | Percentiles P50/P75/P90/P95 of daily pr extremes (same method as Extreme Heat) |
| Extreme Wind | Wind | Turbine cut-out speed (~25 m/s / 90 km/h, IEC design standard) | Percentiles P75/P90/P95/P99 of ERA5 gust |
| Extreme Wind | Solar | none defensible: ASCE 7 design wind speed is inherently site-specific (location, Risk Category, Exposure Category), not a universal constant; manufacturer survival ratings vary by product generation (observed range ~51-60+ m/s across two data points from one manufacturer); verified not comparable in rigor to the Wind-bucket turbine cut-out speed | Percentiles P75/P90/P95/P99 of ERA5 gust, final method, not a contingency pending a Tier 1 value |

Declared limitation, both Wind and Solar rows above: Extreme Wind's ERA5
gust source is historical reanalysis (1991-2020), not a CMIP6 SSP
projection like every other hazard in this table -- a CMIP6 substitution
was investigated and rejected (Section 3.1) because CMIP6's only
daily-resolution wind variable is a daily-mean sustained-wind quantity,
not a gust product, and no daily-maximum variant exists either.

Wildfire's Tier 1 EFFIS 6-class table and its FIRMS-as-validator argument
are deferred, not deleted -- see Section 10.1.

### 4.2 Normalization transform: FROZEN_BOUNDS

Min-Max normalization (FROZEN_BOUNDS) uses bounds computed over the
pooled distribution across all three countries jointly, not per
country. This is a precondition for the cross-national comparability
claims in Section 9: a country-specific Min-Max would make Hazard=1.0
mean different physical intensities in different countries, breaking
comparability entirely.

Not every hazard variable is well suited to the same transform. Before
FROZEN_BOUNDS is finalized for a given hazard, a normality/skewness
check is run on that hazard's pooled raster distribution: the
Fisher-Pearson skewness statistic (`|skew| > 0.5`, Bulmer 1979's
"fairly symmetrical" convention) is the deciding criterion; Shapiro-Wilk
is computed and reported alongside as a diagnostic only, since at the
sample sizes used here (thousands of plant x scenario rows) it rejects
exact normality for nearly any real geophysical sample -- including
mildly skewed ones -- and is not informative as a binary gate.
Approximately normal variables (e.g., temperature-derived hazards) use
direct Min-Max.

Long-tailed variables (e.g., precipitation extremes, drought duration)
use `f(x) = -ln(1-x)` (applied to a preliminary, padded Min-Max scaling
of the raw value, then Min-Maxed again onto [0,1]), **not** a plain
log-transform. This replaces an earlier log1p-based design: log1p
compresses the upper tail of a right-skewed variable (large values are
pushed together near 1.0, exactly where a physically extreme plant
should be most separated from a moderate one), which is the opposite of
what a hazard normalization should do; `-ln(1-x)` expands that tail
instead (`-> infinity` as `x -> 1`). The check result and the resulting
transform choice are recorded per hazard in the origin table (Section
4.3), not assumed silently. Implemented as its own isolated module,
`src/index/normalization.py` (`docs/DECISIONS.md`, "GEAR v3 Phase 2.4:
Normalization module, neg-log transform confirmed to replace log1p"),
which produces this recommendation without yet altering the currently
deployed `FROZEN_BOUNDS`/transform in `src/index/risk_calculator.py`.

The prior log-transform tail-compression concern for Extreme Heat
(Section 4, threshold-based scaling vs. log test on a heat-day
subsample) is retained and evaluated using this same normality-check
procedure, not as a special case -- this is the concern the `-ln(1-x)`
replacement above is designed to resolve, applied uniformly rather than
as a heat-only fix.

### 4.3 FROZEN_BOUNDS origin table

A structured table (variable, lower bound, upper bound, origin, tier,
normality-check result, transform applied) is produced as a direct
article/appendix asset, covering every hazard in the framework, not
only the newly added ones.

## 5. Correlation gate for candidate hazards

Before Extreme Precipitation enters a bucket's applicable set,
correlation against existing terms in that bucket is computed and
gated using a single symmetric criterion:

|r| < 0.80

applied uniformly, regardless of the expected sign of the relationship
(Extreme Precipitation is expected to correlate negatively with
Drought). The expected direction is reported alongside the coefficient,
but does not change the exclusion rule: any |r| >= 0.80, positive or
negative, indicates redundant information and excludes the candidate
from that bucket's applicable set. This replaces the asymmetric cutoff
in the prior draft (r > -0.85 for precipitation).

Wildfire's candidate pairs (Wildfire vs. Extreme Heat, Wildfire vs.
Water Stress) are removed from this gate's scope along with the hazard
itself -- deferred, Section 10.1. The gate's only candidate as of this
methodology is Extreme Precipitation (vs. Water Stress/Drought); the
mandatory, non-gated Water Stress/Drought pair (ws/sv/iv trio) below is
unaffected.

Before computing r, both layers being compared are harmonized to a
common spatial support: aggregated (upscaled) to the coarser of the two
native resolutions, or aggregated to administrative/basin zonal
statistics, before the correlation matrix is computed. Computing
Spearman correlation at native pixel resolution across rasters of very
different native resolution (e.g., a coarse global climate grid against
finer Aqueduct basin polygons) inflates apparent correlation through
spatial autocorrelation and is not used.

Water Stress and Drought, both mandatory for Hydro by design (not
conditional candidates), are not subject to the exclusion gate but are
computed with the same harmonized-grid methodology and reported: r
(Water Stress, Drought) per region, with the mechanistic distinction
between structural water stress and short-term precipitation-
evapotranspiration deficit stated even where correlation is high.

## 6. Aggregation: Physical Hazard Screening Index (PSAE)

For plant i in bucket b with applicable hazard set H_b:

PSAE_i = ( sum over h in H_b of 1[RiskBand_i,h >= High] ) / |H_b|   (2)

PSAE_i uses RiskBand_i,h, the threshold classification of Hazard_i,h
alone (Section 4); it does not incorporate Exposure or Vulnerability.
This answers a physical-exposure question independent of asset scale or
condition, avoiding the compensatory dilution a weighted composite
introduces.

Classification, applied where |H_b| >= 3 (Hydro, Thermal, Solar):
- PSAE = 1.0 -> EXTREME
- 0.5 <= PSAE < 1.0 -> HIGH
- 0.0 < PSAE < 0.5 -> MEDIUM
- PSAE = 0.0 -> LOW

For Wind (|H_b| = 1), the four-band classification cannot be populated
(only {0, 1.0} are possible); a compressed scheme is used instead,
derived from the same cutoffs without introducing a new one: Wind maps
to {LOW, EXTREME}. The raw PSAE fraction is always reported alongside
the categorical label, for every bucket, so the underlying granularity
is never hidden by the label alone.

The 1.0/0.5/0.0 cut points are Tier 3, author-declared convention, no
literature precedent; declared as such and evaluated by scenario-
discovery sensitivity analysis, not Sobol (Section 8).

Two alternatives were considered and rejected: a continuous/ordinal
PSAE (reopens the continuous-weighting problem PSAE was designed to
close) and artificially expanding Wind's H_b to gain resolution
(conflicts with the closed hazard-scope decision, Section 10).

## 7. Contextual validators: two distinct classes

Two validator classes are used, deliberately not conflated, because
they answer different questions and have different blind spots.

### 7.1 Physical-occurrence validators

Confirm that a specific physical hazard event actually occurred at an
asset's location, independent of any downstream human or economic
impact. Sources: IBTrACS (cyclone track/intensity), FIRMS (fire
ignition history; originally scoped out of the hazard layer per Section
10.1's FIRMS-as-validator argument, and retained here as a validator
candidate independent of Wildfire's own deferral -- Section 10.1).
Additional physical catalogs for landslide and lightning are used where
available and physically applicable.

### 7.2 Broad-impact validators

EM-DAT catalogs disasters that crossed a documented human or economic
impact threshold; it systematically under-detects hazards affecting
isolated, low-population-density assets (e.g., a severe rainfall event
that floods and disables a substation far from any urban center will
rarely appear in EM-DAT). EM-DAT is therefore redefined explicitly in
the article as a long-range/broad-impact corroboration source, not a
physical-occurrence validator. Where EM-DAT returns "No Record" for an
isolated asset, this is not interpreted as "no hazard occurred"; the
physical-occurrence validators (7.1) are the primary source for that
question.

### 7.3 Validator states and scope

Both classes report the same three-state output per applicable hazard
per asset:
- Corroborated: a qualifying event/detection is found in that source
  for the asset's location/radius, post-2000.
- No Record: the validator is applicable, but no qualifying event/
  detection was found in that source. The class-specific interpretation
  in 7.1/7.2 applies.
- Not Applicable: the validator does not apply to this asset (e.g., a
  non-coastal asset under the cyclone/storm-surge validator).

Historical window: post-2000 only for all sources (EM-DAT's own
guidance flags pre-2000 coverage as unreliable; IBTrACS/FIRMS windows
matched for consistency). No validator state modifies PSAE, RiskBand,
or Risk_i,h under any circumstance.

This removes the confound where raw national EM-DAT event frequency
penalized large countries (India) independent of genuine systemic
vulnerability, since event data no longer enters the score at all in
any form.

## 8. Uncertainty and sensitivity analysis

Two distinct analyses are used, matched to parameter type, because
variance-based global sensitivity analysis is statistically unstable
when applied to step/threshold functions.

### 8.1 Sobol/SALib (continuous parameters only)

Applied only to genuinely continuous parameters: FROZEN_BOUNDS
percentile choices, age_factor decay rates, and any other parameter
that varies smoothly. First-order and total-order indices computed via
SALib, N increased substantially above the current 1000, final value
set by measured convergence of the summary statistic of interest.

### 8.2 Scenario discovery / one-at-a-time (structural/discrete parameters)

Applied to binary or threshold decisions that Sobol is unsuited for:
hazard inclusion/exclusion in a bucket's H_b, the PSAE cut points
(0.0/0.5/1.0), and the correlation-gate cutoff (|r| < 0.80). Each
structural choice is toggled or shifted independently, and the
resulting change in the distribution of PSAE/RiskBand outcomes is
reported, showing how sensitive the classification is to each discrete
design choice, without claiming a variance decomposition that does not
apply to step functions.

## 9. Comparability rules

Stated explicitly here and enforced in code and in every figure/table:
no aggregate "total risk" score exists in this framework. The
following are the only valid comparisons.

- **PSAE**: valid only within the same technology bucket (Solar vs.
  Solar, Thermal vs. Thermal), across any country. Not valid across
  buckets (Solar vs. Thermal), because \|H_b\| differs by bucket and the
  index is a within-bucket saturation fraction, not an absolute
  severity scale. This rule is stated in every PSAE-based figure
  caption and table header, and PSAE values from different buckets are
  never plotted on the same shared color scale or ranked in the same
  list.
- **Risk_i,h**: valid across both technology and country, strictly
  within the same hazard (Risk_Heat for a Thermal plant in Portugal vs.
  Risk_Heat for a Solar plant in India is a valid comparison; Risk_Heat
  vs. Risk_Drought for the same plant is not, and is never computed as
  a sum or otherwise combined figure).
- Cross-national validity for both indices depends on the globally
  pooled FROZEN_BOUNDS normalization (Section 4.2); a country-specific
  normalization would invalidate the cross-national comparability claim
  above and is not used anywhere in this framework.
- **Scenario comparability, Extreme Wind excepted, declared not silent**:
  every hazard's `Risk_i,h`/RiskBand is computed per SSP scenario except
  Extreme Wind, whose ERA5 source (Section 2, Section 3.1) has no SSP
  axis -- a CMIP6 substitution was investigated and rejected on physical-
  quantity-incompatibility grounds, not merely deferred. Extreme Wind's
  RiskBand is therefore the same value across the ssp126/ssp370/ssp585
  columns of any comparison table or figure; this must be stated wherever
  such a table appears, not left to be discovered by a reader comparing
  columns that happen not to move.
- **PSAE, same exception, same reason**: Extreme Wind's contribution to
  PSAE_i (Section 6) -- whether it counts toward the RiskBand >= High
  numerator for a given bucket -- is identical across all three SSP
  columns by construction, because it is computed once from the ERA5
  baseline and copied across the scenario axis, not because the SSPs
  happened to produce the same result. This is stated plainly as
  **structural exposure to severe wind, scenario-independent** (Section
  3.1), not left as a silent artifact for a reader to infer from three
  identical-looking columns.
  **Requirement carried forward to Phase 7 (visualization/reporting,
  not yet built):** any PSAE table or figure that presents the
  ssp126/ssp370/ssp585 columns side by side must visually distinguish
  Extreme Wind's row/contribution from the scenario-varying hazards --
  e.g., a footnote marker on the hazard label, or shading distinct from
  the scenario-varying cells -- so the figure itself does not imply a
  scenario sensitivity for Extreme Wind that does not exist. This is
  recorded here as a Phase 7 requirement, not implemented by this entry.

## 10. Declared scope boundaries (closed, not reopened)

- Full SSP scenario matrix (5 scenarios): not pursued. Aqueduct water
  stress is fixed at 3 scenarios (opt/bau/pes); the remaining hazards
  are kept aligned to the same three scenario labels for consistency.
  Sensitivity to scenario threshold is instead assessed via
  interpolation across the 3 available points, optionally adding one
  intermediate scenario (SSP2-4.5) if Aqueduct coverage is confirmed.
- Hazard set beyond the five modeled here (sea-level rise, icing,
  lightning/landslide as core hazards rather than validators): out of
  active scope, declared as such, consistent with the prior SLR
  exclusion rationale (Brazil, Portugal, and India lack comparably
  reliable core data for these hazards; the modeled hazards were
  selected for cross-national data comparability).

### 10.1 Deferred hazards / future work

Hazards evaluated and set aside for a genuine data-availability gap,
not modeled as a judgment call and not silently omitted -- same
treatment as the SLR exclusion above, future work if a data source
appears.

**Wildfire (FWI/EFFIS).** Deferred (2026-09-11): FWI requires daily
near-surface relative humidity, which is absent from the CDS catalogue
for the required gfdl_esm4 + miroc6 x 3-SSP matrix, and the one
alternative global source checked (the ETH Zurich FWI-CMIP6 dataset,
Quilcaille et al. 2023) has zero GFDL-ESM4 coverage and provides only
annual, reference-period-relative indicators, not daily FWI or the
EFFIS absolute class boundaries this methodology's Tier 1 approach
needs. Full rationale: `docs/DECISIONS.md`, "GEAR v3 Phase 2.2:
Wildfire deferred (data availability)". The values below are kept
verbatim, citable if a data source is found later -- not deleted:

- Tier 1 danger classes -- EFFIS 6-class FWI system, verified against
  primary source (Copernicus EFFIS technical background, Van Wagner &
  Pickett 1985 basis): Low (<11.2), Moderate (11.2-21.3), High
  (21.3-38.0), Very High (38.0-50.0), Extreme (50.0-70.0), Very Extreme
  (>70.0, added June 2021).
- Tier 3 fallback -- percentiles P50/P75/P90/P95 of local FWI history,
  for cells where the 6-class assignment cannot be computed.
- Applicable buckets, if reinstated: Thermal, Solar (transmission line
  and rural asset exposure) -- the mechanistic rationale is unaffected
  by the data-availability gap.
- FIRMS/FWI distinction (unaffected by the deferral, applies whenever
  Wildfire is reinstated): treating NASA FIRMS active-fire detections
  and the FWI danger index as interchangeable is an ontological error --
  FIRMS records where fire already occurred (a historical occurrence
  layer), while FWI computes where fire-conducive atmospheric
  conditions exist and can be projected under CMIP6 (a prospective
  hazard layer). Hazard_i,h for Wildfire, if reinstated, would be
  computed from FWI/EFFIS alone; FIRMS stays a physical-occurrence
  validator (Section 7.1), never a hazard-normalization input, whether
  or not Wildfire itself is active.

## 11. Framing corrections (text-only, no methodology change)

- All references to raster resolution state explicitly that grid
  alignment is geospatial interpolation, not statistical or dynamical
  downscaling; effective information content remains bounded by each
  GCM's native resolution.
- PSAE and its risk-band classification are described throughout as a
  relative, intra-technology screening index for comparative
  prioritization, never as a calibrated absolute risk measure and never
  as a proxy for "total risk." This framing extends to the title,
  abstract, and conclusion, not only the Methods section.
- Two-GCM comparison (GFDL-ESM4, MIROC6) is described as a sensitivity
  check between two structurally distinct models, not as uncertainty
  propagation across the CMIP6 ensemble.
- age_factor's role as a vulnerability proxy is explicitly bounded: it
  captures structural exposure via capacity retention, not adaptive
  capacity (retrofit, maintenance quality); this is stated as a design
  limitation shared with comparable published frameworks that also lack
  asset-level retrofit data, not as an omission.
