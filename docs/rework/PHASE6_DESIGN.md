# GEAR v3 Phase 6 Design: Sensitivity and Uncertainty

Design-only document. No code is implemented or run against this document.
Written ahead of its dependencies closing (Phase 4, PSAE aggregation; Phase
3.3, normalization transform swap applied to `risk_calculator.py`) so that
Phase 6 can convert directly into an implementation prompt the moment both
close, without design work sitting on the critical path at that point.

Companion documents read to produce this design: `docs/rework/
GEAR_v3_work_plan.md` (Phase 6 section), `docs/DECISIONS.md`, `docs/
LIMITATIONS.md`, `docs/rework/GEAR_v3_methodology_nature_format.md` Section
8 (Uncertainty and sensitivity analysis) and its supporting Sections 3-6.
Also read directly: `src/index/normalization.py`, `src/index/age_factor.py`,
`src/index/hazard_scope.py`, `src/index/monte_carlo.py` (current, CCRS-era,
one of the Phase-1-broken modules -- read for its RNG/N mechanics, which
Phase 6 supersedes rather than reuses as-is).

Every parameter below is either (a) traced to a specific named constant
already in the codebase, with its file/line-level source, or (b) explicitly
flagged as unconfirmed, per the standing instruction not to guess a
plausible-sounding range. Where the methodology text (Section 8.1) names a
parameter group ("FROZEN_BOUNDS percentile choices") that does not map
cleanly onto a single constant in the current code, that mismatch is stated
as an open point, not silently resolved one way or the other.

---

## 0. Preconditions and what blocks this design from becoming code

- **Phase 4 (PSAE aggregation)**: not implemented. Section 6's PSAE
  equation, cut points (1.0/0.5/0.0), and per-bucket four-band/compressed
  classification exist only as methodology prose (`GEAR_v3_methodology_
  nature_format.md` Section 6). No `src/index/psae.py` (or equivalent)
  exists yet. Section 2's discrete-parameter design (6.3) references the
  PSAE cut points conceptually; the concrete perturbation interface (what
  function to call, what it returns) cannot be pinned down until that
  module exists.
- **Phase 3.3 (normalization swap applied)**: `src/index/normalization.py`
  currently *recommends* per-hazard transforms and bounds (Phase 2.4,
  closed) but `src/index/risk_calculator.py`'s `FROZEN_BOUNDS`/
  `transform_term` are still on the retired `log1p_minmax` path pending
  Phase 3.3 applying the recommendation. Every FROZEN_BOUNDS-adjacent
  continuous parameter named below (Section 1.2) is described against the
  post-3.3 `neg_log_minmax` transform design, not the current production
  code path.
- **Phase 2.5 (correlation gate)**: closed, all three countries (see
  `docs/DECISIONS.md`, "GEAR v3 Phase 2.5 follow-up"). This is the one
  Phase 6 dependency that is actually satisfied; Section 2.3 below uses its
  real, closed output (max observed `|r| = 0.702`) directly.

This document assumes both blockers close with the H_b table, transform
selections, and PSAE mechanics as currently specified in the methodology
text and in `src/index/hazard_scope.py`. If either closes with a materially
different shape (e.g., a different bucket's H_b membership, a different
PSAE cut scheme), the parameter inventories in Sections 1 and 2 need a
re-check against the actual closed state before implementation -- this
design is not self-updating.

---

## 1. Phase 6.2 -- Sobol/SALib global sensitivity (continuous parameters only)

Per Methods Section 8.1, restricted to parameters that vary smoothly and
whose effect on the reported statistic (e.g., capacity-weighted mean
`Risk_i,h`, or the resulting PSAE/RiskBand distribution) is itself smooth,
not a step function. Each entry below states: the current constant (file,
name, value), the range to perturb over, and whether that range is
literature-backed or engineering judgment.

### 1.1 age_factor decay rates (`src/index/age_factor.py`)

| Parameter | Current value | Perturbation range | Source | Tier |
|---|---|---|---|---|
| Coal decay rate (`COAL_DECAY_RATE`) | 0.0025 /yr | **0.0019 - 0.0044 /yr** | Sagaf (2020), 660 MW unit, 0.19-0.44 %/yr observed range | Literature-backed |
| Wind fallback relative rate (`WIND_RELATIVE_RATE`) | 0.004 /yr | **0.003 - 0.005 /yr** | Olauson, Edstrom & Ryden (2017), 0.3-0.5 %/yr midpoint range (the same range already used by the legacy `monte_carlo.py`'s `WIND_RATE_RANGE`) | Literature-backed |
| Hydro retention rate (`HYDRO_RETENTION_RATE`) | 0.0055 /yr | **0.0050 - 0.0060 /yr** | Turner et al. (2024), *Nature Communications*, "~0.5-0.6 %/yr" range cited in `docs/DECISIONS.md`'s age_factor entries | Literature-backed |
| Solar retention rate (`SOLAR_RETENTION_RATE`) | 0.007 /yr (compound) | **⚠️ Not characterized** | Deline et al. (NREL, 2020/2024) and Boretti & Castellotto (2024) are cited in `docs/DECISIONS.md` for the 0.7 %/yr point value only -- no range is quoted anywhere in the decision record. Flagging rather than inventing a plausible-looking band (e.g., "±0.2 pp/yr") with no cited basis. **Needs author input**: either a literature range from the same sources (module physics 0.5%/yr + soiling/downtime/inverter losses -- the underlying components may have individually cited ranges even if the composite 0.7%/yr does not) or an explicit engineering-judgment band the author is willing to defend as such. |
| Coal overhaul cycle length (`COAL_OVERHAUL_CYCLE_YEARS`) | 5 yr | **⚠️ Not characterized** | Explicitly logged as "ASSUMED... a modelling premise, not values taken from Kim & Moon or Sagaf" (`docs/DECISIONS.md`, age_factor final entry; `docs/LIMITATIONS.md`, "GEM retrofit/repowering field absent"). No GEM overhaul-date field exists to calibrate against. A perturbation range here would itself be an assumption stacked on an assumption -- flagging for an explicit author-judgment call (e.g., 3-7 yr) rather than picking one silently. |
| Coal overhaul recovery fraction (`COAL_OVERHAUL_RECOVERY`) | 0.70 | **⚠️ Not characterized** | Same "ASSUMED" status as the cycle length, same source. Flag together -- if the author sets a range for one, the other should get one too rather than perturbing only half of a paired assumption. |

Two fuels are **explicitly excluded**, not omitted by oversight:

- **Gas/oil-gas**: `age_factor = 1.0`, fixed, confirmed final after a
  bounded literature search (`docs/DECISIONS.md`, "Gas/oil-gas age_factor:
  pinned-neutral treatment confirmed final"; `docs/LIMITATIONS.md`,
  2026-09-11 entry). A fixed neutral parameter has no range to perturb --
  there is nothing for Sobol to vary. This is not a gap in this design; it
  is the direct consequence of that closure, restated here explicitly per
  the task's instruction.
- **Nuclear and Bioenergy**: same status, `age_factor = 1.0` fixed
  (licensing/decommissioning-governed for nuclear; coal-proxy dropped for
  want of fleet-level evidence for bioenergy). Same non-candidate
  reasoning as gas/oil-gas.
- **Mixed-fuel plants**: `age_factor` is the simple average of the
  component fuels' own `age_factor` values -- a derived quantity, not an
  independent parameter. It inherits whatever variance its component
  fuels' rates carry; it does not need (or get) its own Sobol dimension.

### 1.2 RiskBand percentile-cut thresholds (Phase 3.2) -- and a naming mismatch to flag

Section 8.1 names "FROZEN_BOUNDS percentile choices" as a Sobol candidate
group. Read literally against the current code, this does not point at a
single clean target:

- `src/index/normalization.py`'s `FROZEN_BOUNDS`-equivalent (the
  `compute_normalization_recommendations` bounds) are **empirical pooled
  min/max**, not a percentile choice -- there is no percentile trimming in
  the bounds computation itself (`_recommend_one` takes `sample.min()`/
  `sample.max()` directly).
- The actual percentile-based constants in the pipeline are the Tier 3
  **RiskBand classification cuts** (Phase 3.2, Methods Section 4, table
  reproduced in Section 4.1 there): P50/P75/P90/P95 for Extreme Heat,
  Drought/SPEI, Extreme Precipitation, and both water-variability terms
  (sv, iv); P75/P90/P95/P99 for Extreme Wind (Wind and Solar buckets). Per
  Section 4.1's resolved band-count convention, the **lowest** percentile
  in each set is diagnostic-only and never a RiskBand boundary -- so the
  operative cuts that actually gate `RiskBand_i,h >= High` (and therefore
  PSAE) are P75/P90/P95 for the four-percentile group and P90/P95/P99 for
  the Wind/Solar group.

**⚠️ Point to validate before implementation**: this design treats
Section 8.1's "FROZEN_BOUNDS percentile choices" as referring to these
RiskBand percentile cuts, since that is the only percentile-shaped
continuous parameter family that actually exists in the pipeline. This is
the most defensible reading, but it is a reading, not a confirmed mapping
-- the author should confirm this is what Section 8.1 meant before a Sobol
implementation prompt is written against it, since "FROZEN_BOUNDS" and
"RiskBand percentile cuts" are two different, already-named things
elsewhere in the same methodology document (Sections 4.2 and 4, Section 4.1
respectively) and conflating them in code would misname the parameter in
every downstream table/figure.

| Parameter group | Current value | Perturbation approach | Tier |
|---|---|---|---|
| Extreme Heat / Drought / Extreme Precipitation / sv / iv operative cuts (P75/P90/P95) | Sample-relative percentiles of each hazard's own pooled distribution | Perturb the percentile **rank**, not a fixed physical value (e.g., shift each cut by ±5 percentile points: P70/P85/P90 .. P80/P95/P100-epsilon), recomputed against the same pooled sample each draw | Tier 3, author-declared convention, no literature precedent (methodology Section 4, "none available"/"none defensible" for every Tier 1 alternative checked) |
| Extreme Wind / Solar operative cuts (P90/P95/P99) | Sample-relative percentiles of pooled ERA5 gust | Same rank-shift approach, own range (percentiles bounded above by 100, so the P99 cut's shift range is asymmetric near the ceiling -- needs an explicit clipping rule, e.g. shift range shrinks as the cut approaches P99.5) | Tier 3, same convention |

The **neg-log transform's tail-padding fraction** (`src/index/
normalization.py`, `UPPER_TAIL_PADDING_FRACTION = 0.05`) is a separate,
genuinely continuous parameter that *is* part of the Section 4.2
normalization design (post-3.3): it controls how far the preliminary
Min-Max scaling keeps the pooled maximum from the `-ln(1-x)` singularity,
and shifting it smoothly changes every `neg_log_minmax`-transformed
hazard's normalized value continuously. It is explicitly documented in
the module as "author-declared engineering parameter... not derived from
any cited source." **⚠️ Not characterized**: no literature range exists
to cite; an engineering-judgment band (e.g., 0.01-0.10, keeping the padded
maximum comfortably inside `[0,1)` at every setting) would need explicit
author sign-off before being written into an implementation prompt, same
as the coal overhaul parameters above.

The **skewness threshold that selects between `direct_minmax` and
`neg_log_minmax`** (`SKEWNESS_NORMAL_THRESHOLD = 0.5`, Bulmer 1979) is
**not** a Sobol candidate, despite being continuous-valued: shifting it
does not smoothly perturb `Hazard_i,h` -- it can flip which of two
structurally different transforms applies to a hazard, a discontinuous
change in functional form, not a smooth dial. This belongs conceptually
with the discrete/structural analysis (Section 2), flagged here so it is
not silently dropped between the two designs; Section 2.4 below returns to
it.

### 1.3 Summary: continuous-parameter dimension count for Sobol sampling

Confirmed, ready-to-use candidates (7): coal decay rate, wind fallback
rate, hydro retention rate, the RiskBand percentile-cut rank (grouped as
one dimension per hazard-percentile family or per-hazard if the author
wants finer resolution -- five hazard families in the P75/P90/P95 group
plus one in the P90/P95/P99 group, so 6 dimensions there alone if not
grouped), and the neg-log tail-padding fraction.

Flagged, pending author input (4): solar retention rate range, coal
overhaul cycle length range, coal overhaul recovery fraction range, and
confirmation of the "FROZEN_BOUNDS percentile choices" mapping in Section
1.2. Section 3 below's Sobol sample-size proposal is given as a function
of the final dimension count `D`, since `D` cannot be pinned to one number
until these four are resolved.

---

## 2. Phase 6.3 -- Scenario-discovery / one-at-a-time (discrete/structural parameters)

Per Methods Section 8.2, a separate analysis type from Sobol, reported
separately, for parameters where variance-based decomposition does not
apply (binary inclusion/exclusion, threshold cutoffs that change
classification membership rather than a continuous output).

### 2.1 Hazard inclusion/exclusion per bucket (H_b tables, `src/index/hazard_scope.py`)

One-at-a-time: remove exactly one hazard from one bucket's `H_b`, recompute
PSAE for that bucket's plants with the reduced set (denominator `|H_b|`
shrinks by one), compare the resulting PSAE/RiskBand distribution against
the closed baseline.

| Bucket | H_b (baseline, `|H_b|`) | Meaningful one-at-a-time removals |
|---|---|---|
| Hydro | ws, spei, precip, sv, iv (5) | 5 -- remove each in turn |
| Thermal | ws, heat, precip (3) | 3 -- remove each in turn |
| Solar | heat, precip, wind (3) | 3 -- remove each in turn |
| Wind | wind (1) | **0, not meaningful** -- removing Wind's only hazard leaves an empty `H_b`, which `hazard_scope._validate()` already treats as a structural error ("bucket has an empty H_b"), not a valid degraded state to score. Wind is excluded from this OAT sweep for that reason, stated explicitly rather than silently skipped. |

12 meaningful single-hazard removals total across the three buckets that
have more than one hazard. Report per removal: the shift in each bucket's
PSAE category distribution (fraction of capacity in EXTREME/HIGH/MEDIUM/
LOW) versus the full-H_b baseline, per country.

### 2.2 PSAE cut points (0.0 / 0.5 / 1.0)

Cannot be pinned to a concrete function call yet -- Phase 4 has not been
implemented (Section 0). Conceptual design, to be adapted once the actual
PSAE module's interface is known:

- Shift the 0.5 ("High" boundary, `HIGH <= PSAE < EXTREME`... actually the
  boundary between MEDIUM and HIGH) by discrete steps -- e.g., 0.4 and 0.6
  -- and re-classify the same underlying PSAE fractions against the shifted
  cut, without recomputing `Risk_i,h`/RiskBand upstream (the cut is a
  classification boundary on an already-computed fraction, per Equation 2
  and the Section 6 classification table).
- Since `|H_b|` is 3 for Hydro/Thermal/Solar (four-band scheme) and 1 for
  Wind (compressed LOW/EXTREME scheme), and PSAE is itself a fraction with
  denominator `|H_b|`, the practical set of achievable PSAE values is
  discrete and small (`{0, 1/|H_b|, 2/|H_b|, ..., 1}`). A 0.5 cut shift
  therefore does not move continuously through the outcome space the way a
  Sobol perturbation would -- for `|H_b| = 3`, the achievable values are
  `{0, 0.33, 0.67, 1.0}`, so shifting the boundary from 0.5 to 0.4 or 0.6
  does not change which achievable values fall on which side unless the
  shift crosses one of those discrete points. This makes the OAT report
  naturally coarse (a small number of distinct classification outcomes to
  enumerate directly, not a curve to trace) -- worth stating in the
  eventual implementation prompt so the test is not designed expecting
  smooth movement it cannot produce.
- The 1.0/0.0 cuts (EXTREME/LOW boundaries) are degenerate by construction
  (PSAE = 1.0 or 0.0 exactly) and are not meaningfully perturbable the same
  way -- only the internal 0.5 boundary has room to move without
  redefining what EXTREME/LOW mean.

### 2.3 Correlation-gate cutoff (`|r| >= 0.80`)

This is the highest-value test in this phase, per the task's framing, and
the data to justify that claim already exists from Phase 2.5's closed run:
**the maximum observed `|r|` across every gated pair/bucket/country/GCM
cell was 0.702** (Seasonal vs. Interannual Variability, Hydro, Portugal;
`docs/DECISIONS.md`, "GEAR v3 Phase 2.5 follow-up"). The entire Phase 2.5
closure -- Hydro keeping both sv and iv, no exclusions anywhere, the
tie-breaker never invoked -- depends on 0.702 staying under whatever the
gate threshold is. At the current 0.80 threshold there is a 0.098
cushion; a plausible alternative threshold (e.g., 0.70) would flip this
specific pair's verdict for the first time.

Design: re-run `src/index/correlation_gate.py`'s decision logic (not the
raw `r`/`rho` computation, which does not depend on the threshold and does
not need to be recomputed) at a swept set of thresholds -- e.g., **0.60,
0.65, 0.70, 0.75, 0.80 (baseline), 0.85, 0.90** -- against the already-
computed `data/outputs/tables/correlation_gate.csv` pairwise matrix. Report,
per threshold: which (pair, bucket, country, GCM) cells flip from pass to
fail, and for each flip, which variable the pre-registered tie-breaker
hierarchy (Section 5, Criteria 1-3) would retain. This is pure
post-processing of an existing table, not a new correlation computation --
cheap to run, and directly answers "how fragile is the current H_b
membership to this one design choice."

### 2.4 Tie-breaker hierarchy's practical effect

As stated in Section 2.3, the tie-breaker has never fired on real data at
the production threshold (0.80) -- the closest real pair (0.702) does not
cross it. Read literally, an OAT test of "the tie-breaker hierarchy" in
isolation, at the current threshold, has **no real-data effect to
measure**: there is nothing to toggle, since it was never invoked. Two
honest ways to report this, both of which this design keeps in scope
rather than picking one silently:

1. **State the null result directly**: at the current 0.80 cutoff, the
   tie-breaker hierarchy has zero observable effect on the production
   output, because it never activates. This is itself a reportable
   sensitivity finding (the hierarchy is dormant infrastructure at current
   data), not an absence of a result.
2. **Combine with Section 2.3's threshold sweep**: at any swept threshold
   below 0.702 (e.g., 0.70, 0.65, 0.60), the tie-breaker activates for the
   Seasonal-vs-Interannual-Variability/Hydro/Portugal cell for the first
   time, and its Criterion 3 resolution (retain `iv` over `sv`, per the
   PNNL/Moghaddasi et al. evidence already on record) becomes directly
   observable. This is not a separate, independent OAT dimension from
   2.3 -- it is a derived observation *within* the threshold sweep, and
   should be reported as such (a callout inside the 2.3 results, not a
   fourth standalone test), so as not to imply the tie-breaker was tested
   independently when it was actually only exercised as a side effect of
   lowering the correlation threshold.

The task's framing anticipated this might be "a smaller or moot test" --
confirmed: moot as an independent test at production settings, non-moot
only as a sub-finding of Section 2.3.

### 2.5 Skewness threshold for transform selection (carried over from Section 1.2)

`SKEWNESS_NORMAL_THRESHOLD = 0.5` (Bulmer 1979 convention,
`src/index/normalization.py`) belongs here, not in Sobol, because moving it
can flip a hazard's selected transform (`direct_minmax` <->
`neg_log_minmax`) discontinuously. One-at-a-time design: recompute
`select_transform` for every hazard candidate at a small set of alternative
thresholds (e.g., 0.4, 0.5 baseline, 0.6, matching the "fairly symmetrical"
convention's own stated tolerance band in Bulmer 1979 rather than an
arbitrary sweep), and report which hazards' transform selection actually
flips. Given the already-recorded skewness values in the origin table
(`data/outputs/tables/normalization_origin_table.csv`, produced by Phase
2.4), this is again cheap post-processing of already-computed skewness
statistics, not a new distributional computation, once Phase 3.3 has run
and that table reflects the applied (not just recommended) transform
choices.

---

## 3. Phase 6.4 -- RNG-granularity open question (restated, not resolved)

**What is actually pending, per the record**: the legacy (CCRS-era,
Phase-1-broken) `src/index/monte_carlo.py` uses **one independent RNG
stream per country** (not per country-scenario), keyed via `zlib.crc32` +
`numpy.random.SeedSequence` off `config.RANDOM_SEED`. This was an
author-approved deviation from an earlier brief that specified "per
country/scenario" streams, justified at the time because none of that
module's three perturbed parameter groups -- the Thermal bucket's
water/heat weight ratio, `age_factor` retention rates, and
`EventMultiplier`'s amplitude `k` -- were scenario-dependent quantities:
`EventMultiplier_c` and the bucket weights are applied identically across
a country's three scenario rows in production, so a scenario-keyed stream
would have injected non-physical scenario-dependent noise into a
scenario-invariant judgment call.

**This module and its RNG design are not carried forward as-is.** Phase 1
deleted `ccrs_calculator.py`/`ccrs_report.py` and removed `EventMultiplier`
from the core entirely; Phase 6.2/6.3's parameter set (Sections 1-2 above)
is structurally different from the three groups the old approval covered.
The per-country rationale's *premise* -- "none of the perturbed parameters
are scenario-dependent" -- appears to still hold for the new parameter set
on inspection (age_factor rates do not depend on scenario; RiskBand
percentile cuts and the neg-log padding fraction are pooled across
scenarios by design, per Section 4.2's cross-national/cross-scenario
pooling rule) -- but this is an observation made while writing this design
document, not a re-confirmed author decision. The old approval was scoped
to the old parameter set and should not be silently treated as covering
the new one.

**What this design does, without resolving the question**: the RNG
stream-derivation utility for Phase 6's implementation should be written as
a small, isolated function parameterized by an explicit granularity flag
(`per_country` vs. `per_country_scenario`), mirroring the shape of the old
`country_rng()` but not hardcoding either answer into the simulation loop's
structure. Whichever way the author confirms this for the new parameter
set, the simulation loop itself (draw parameters -> recompute the affected
chain -> aggregate) does not need to change, only which key feeds the
`SeedSequence` spawn. This keeps the open question genuinely open at the
design level rather than pre-deciding it through an implementation detail
that would be awkward to unwind later.

---

## 4. Phase 6.1 -- Monte Carlo N and convergence criteria

Two distinct sampling needs exist under Phase 6, each with its own N and
its own convergence diagnostic -- conflating them would understate the
sample size Sobol actually needs or overstate what the general
uncertainty-propagation run requires.

### 4.1 General Monte Carlo uncertainty propagation (feeds percentile CIs)

Current legacy value: `N_ITERATIONS = 1000` (`src/index/monte_carlo.py`),
inherited unchanged from "the pre-SPEI design" per that module's own
docstring -- i.e., not itself derived from a convergence check, a round
number carried forward across several methodology revisions.

**Proposed convergence diagnostic**: running-mean / running-CI
stabilization across a doubling sequence, not a single arbitrarily larger
N. Procedure:

1. Run the simulation at `N = 1000, 2000, 4000, 8000, 16000` (doubling from
   the current value, five points).
2. At each `N`, record the point estimate (e.g., capacity-weighted mean
   `Risk_i,h` per hazard/bucket/country, or the PSAE-band capacity fraction
   once Phase 4 exists) and its 95% percentile CI (2.5/97.5, matching the
   existing `PERCENTILES` convention).
3. Declare convergence at the smallest `N` in the sequence where **both**:
   - the point estimate's relative change from the previous `N` in the
     sequence is `< 1%`, and
   - the 95% CI half-width's relative change from the previous `N` is
     `< 5%` (CI width is noisier than the point estimate and converges
     more slowly, so it is given a looser tolerance deliberately, not
     the same one).
4. Confirm, not just declare: the *next* doubling beyond the point where
   both criteria are first met must also satisfy them. A single doubling
   that happens to look stable can be a fluke of that particular draw
   sequence; requiring two consecutive doublings to pass guards against
   reporting a false-converged N.
5. Report the Monte Carlo standard error (`SE = sample_std / sqrt(N)`) at
   the converged `N` as a secondary, corroborating statistic alongside the
   stabilization result -- not as the primary criterion, since SE alone can
   look small while the underlying distribution is still shifting shape
   (the running-mean/CI check catches that; a bare SE threshold would not).

This is a defensible, checkable procedure rather than a round target number
picked in advance -- the actual converged N is whatever the data says it
is, reported once the run happens, not asserted here.

### 4.2 Sobol/SALib sampling (feeds Section 1's continuous-parameter analysis)

Separate sample-size convention from 4.1, because Saltelli sampling for
Sobol indices scales with the number of continuous parameters `D`, not with
the same logic as a plain Monte Carlo CI. Total model evaluations for
first-order + total-order indices under Saltelli's scheme are
`N_0 * (2D + 2)`, where `N_0` is the base sample size (SALib convention:
a power of two).

- `D` is not fixed yet (Section 1.3): 7 confirmed continuous dimensions,
  up to 4 more pending author input on the flagged items, plus however the
  RiskBand percentile-cut family is grouped (one dimension per hazard vs.
  one per percentile family) once Section 1.2's naming question is
  resolved. This design proposes the sampling procedure as a function of
  `D`, not a fixed evaluation count, since `D` genuinely cannot be pinned
  down before those points are settled.
- **Proposed base `N_0`**: start at 1024 (2^10, the standard SALib
  starting convention), giving `1024 * (2D + 2)` evaluations -- e.g., at
  `D = 7` (confirmed dimensions only), that is 16,384 evaluations; at
  `D = 11` (all candidates included), 25,600.
- **Convergence diagnostic**: SALib's own bootstrap confidence intervals on
  first-order (`S1`) and total-order (`ST`) indices. Double `N_0`
  (1024 -> 2048 -> 4096 -> ...) until, for every reported index, the
  bootstrap CI half-width is below a stated absolute tolerance on the
  0-1 index scale (proposed: `0.02`) **and** does not shrink materially
  (`< 10%` relative) on the next doubling -- the same "confirm with one
  more doubling" discipline as 4.1, applied to index CIs instead of the
  point estimate.
- Each of the ~16k-26k Saltelli evaluations still needs one recomputation
  of the perturbed chain (age_factor -> RiskBand -> PSAE), not a full
  raster re-read -- the same "fixed inputs computed once, perturbed chain
  recomputed per draw" structure the legacy `monte_carlo.py` already uses
  and documents (its module docstring's "What recomputing the full CCRS +
  band report per draw means" section) should carry forward as the
  computational shape for the new PSAE-based chain, since the reasoning
  (raster I/O is the expensive, non-perturbed part; only the downstream
  scalar chain depends on the sampled parameters) still applies unchanged
  under the new architecture.

---

## 5. Open points requiring author confirmation before an implementation prompt is written

Collected from Sections 1-4 for visibility, not repeated reasoning:

1. Solar `age_factor` retention-rate perturbation range -- no literature
   range on record (Section 1.1).
2. Coal overhaul cycle length and recovery-fraction perturbation ranges --
   both "ASSUMED" with no source to bound a range (Section 1.1).
3. Whether Section 8.1's "FROZEN_BOUNDS percentile choices" means the
   RiskBand percentile-cut thresholds (this design's working assumption)
   or something else (Section 1.2).
4. Neg-log transform tail-padding fraction's perturbation range -- no
   literature range on record (Section 1.2).
5. How finely to grain the RiskBand percentile-cut Sobol dimension (one
   dimension per hazard vs. one per percentile family) -- affects `D` and
   therefore the Saltelli evaluation count (Section 1.3, 4.2).
6. RNG granularity for Phase 6's simulation (per-country vs.
   per-country-scenario) -- explicitly not resolved here; needs a fresh
   author decision scoped to the new parameter set, not inherited from the
   superseded CCRS-era approval (Section 3).

None of these block writing Phase 6.2/6.3/6.4's code structure -- the
simulation loop, RNG utility shape, and OAT/threshold-sweep procedures in
Sections 1-3 do not depend on their answers. They block only the specific
numeric ranges fed into that structure for four parameters, and the exact
dimension count for the Sobol sampling budget.
