# GEAR v3 — Project State Snapshot

**Purpose**: reconstruct the real state of the GEAR v3 rework for resumption
in a new chat, without depending on prior conversation memory. This is an
audit of what exists, verified by direct code/commit/`DECISIONS.md` reading
— not a plan, not a set of recommendations. Every status claim below cites
a file, line, commit hash, or `DECISIONS.md` entry it was checked against.

**Snapshot date**: 2026-09-14. **Latest commit at time of writing**:
`6b70a36` ("feat(psae): Phase 4 -- PSAE_i aggregation from RiskBand_i,h").
`docs/DECISIONS.md` has further uncommitted content beyond `6b70a36` as of
this snapshot (Phase 6 mapping, `FROZEN_BOUNDS` reopening/closure, four
Sobol-parameter closures) — see the "Uncommitted state" note at the end.

**Repository boundary**: commit `a367672` ("Start GEAR v3 rework: retire
CCRS core...") is where the v3 rework begins. Every commit before it
(`aa54bb3` through `f6e50bb`/`159d6c6`/etc., 30 commits) belongs to the
retired CCRS-era codebase (`ccrs_calculator.py`, `ccrs_report.py`,
`event_multiplier.py`, the old `risk_bands.py`, `monte_carlo.py`). That
codebase is not this document's subject except where a v3 module still
imports a piece of it (age_factor.py — reused unchanged) or where a v3
module is broken because it does not (see Phase 1, "broken by design").

---

## Phase 0: Blocking verifications — **CLOSED (2026-09-11)**

**Resolves in one sentence**: confirm four data-availability/threshold
questions before any Phase 1+ code depends on their answers.

**Status by code/commit, not by work-plan text**: closed. All four items
have a dated `DECISIONS.md` entry and no downstream code branches on an
unconfirmed Phase 0 answer today (verified: `hazard_scope.py`,
`risk_bands.py` both assume closed Phase 0 answers without a pending-guard).

**Items and their `DECISIONS.md` entries** (exact titles, no commit
introduced a new Phase 0 code module — these are investigation-only,
work-plan Phase 0 items 1-4):
1. GEM cooling-technology field absent — "GEM cooling-technology field:
   confirmed absent (v3 Phase 0.1)".
2. FWI/EFFIS adopted, Extreme Precipitation downgraded Tier 1→3 — "FWI/EFFIS
   wildfire danger classes: 6-class system adopted (v3 Phase 0.2)" and
   "Extreme Precipitation downgraded Tier 1 -> Tier 3 (v3 Phase 0.2)".
3. GEM retrofit/repowering field re-confirmed empty — "GEM
   retrofit/repowering field: re-confirmed empty (v3 Phase 0.3)".
4. Solar Extreme Wind Tier 1 threshold rejected, ERA5 percentile final —
   "Solar Extreme Wind: ERA5 gust percentile is final, not contingency (v3
   Phase 0.4)".

No files created; no open items belonging to this phase.

---

## Phase 1: Core equation and hazard layer restructuring — **CLOSED (2026-09-11)**

**Resolves in one sentence**: replace the retired CCRS composite score with
`Risk_{i,h} = Hazard_{i,h} × Exposure_i × Vulnerability_i`, computed and
kept per hazard, never summed across hazards.

**Status by code**: closed. `src/index/ccrs_calculator.py`/`ccrs_report.py`
confirmed deleted (`python -c "import src.index.ccrs_calculator"` raises
`ModuleNotFoundError`, checked repeatedly through this snapshot's own
research). `src/index/risk_calculator.py` exists, is the live production
module every later phase builds on.

**Files/functions this phase created**: `src/index/risk_calculator.py` —
`risk_i_h()`, `exposure_capacity_mw()`/`exposure_log10_display()` (the
`ExposureLog10Display`-tagged type guard, `risk_i_h` raises `TypeError` on
it), `HAZARD_TEMPORAL_WINDOW` (named constant, not buried in prose).
Commit: `a367672`.

**Decisions closed here** (`DECISIONS.md`): "GEAR v3 Phase 1: Risk_i,h
replaces the CCRS core"; "GEAR v3 Phase 1.3: Thermal bucket implemented as
homogeneous". `sv`/`iv` kept as independent, explicitly-flagged terms
pending Phase 3's H_b decision (not folded into Water Stress, not dropped)
— resolved later by Phase 3.1 (below).

**Broken by design, not a regression**: `risk_bands.py` (the CCRS-era
version, later replaced), `monte_carlo.py`, `emdat_validation.py`,
`src/main.py`, `src/visualization/` all imported the deleted
`ccrs_calculator` symbols and were left broken on purpose — work plan text
states this explicitly ("not patched here"). Confirmed still broken today
(2026-09-14) for `monte_carlo.py` (`ImportError: cannot import name
'ccrs_calculator'`, verified this snapshot), `emdat_validation.py` (same
error, verified this snapshot), `main.py` (`tests/test_main.py` collection
error, same cause), `src/visualization/` (`tests/test_visualization.py`
collection error, same cause). `risk_bands.py` is the one exception — it
was rewritten for v3 in Phase 3.2 (below) and no longer imports the retired
module.

No open items belonging to this phase.

---

## Phase 2: New hazard layers

Five sub-phases, independent of each other by design.

### 2.1 Extreme Precipitation processor — **CLOSED (2026-09-11)**

**Resolves in one sentence**: mean days/year where CMIP6 `pr` exceeds that
pixel's own P95 wet-day threshold (Tier 3, ETCCDI percentile-cutoff
convention, not HAZUS-MH).

**Status by code**: closed and live. `src/processors/
extreme_precipitation_processor.py` exists, `PRECIP_TEMPORAL_WINDOW`
constant present, `raw_raster_path()` imported and used by
`risk_calculator.py:171` and `risk_bands.py:146`. Commit `a367672`
(processor added same commit as Phase 1's core rewrite).

**Decision closed**: "GEAR v3 Phase 2.1: Extreme Precipitation processor
(Tier 3, percentile-cutoff)". 11 tests at close, now 11 in
`tests/test_extreme_precipitation_processor.py` (current collected count).

### 2.2 Wildfire — **DEFERRED (2026-09-11), not implemented**

**Resolves in one sentence**: decide whether Wildfire (FWI/EFFIS) can be
computed with available CMIP6 inputs.

**Status by code**: confirmed absent by design, not a gap. No
`wildfire`/`fwi`/`effis` processor exists anywhere in `src/`. `hazard_scope.
DEFERRED_OR_EXCLUDED_HAZARDS = ("wildfire", "slr")`
(`hazard_scope.py:117`) names it explicitly excluded;
`hazard_scope._validate()` asserts at import time it never appears in any
bucket's `H_b`.

**Decision**: "GEAR v3 Phase 2.2: Wildfire deferred (data availability)";
`docs/LIMITATIONS.md`, "Wildfire (FWI/EFFIS) deferred, not implemented" —
CDS catalogue lacks the daily near-surface humidity input for either
configured GCM; the one alternative source checked (ETH Zurich FWI-CMIP6)
has zero GFDL-ESM4 coverage. Status: revisitable, not a standing TODO.

### 2.3 Extreme Wind processor + ERA5 acquisition — **CLOSED (2026-09-14, acquisition + wiring both complete)**

**Resolves in one sentence**: ERA5 gust-based Extreme Wind hazard, two
consumers (Wind-bucket IEC cut-out, Solar-bucket percentile), both
thresholds independently designed.

**Status by code**: closed, end to end. `src/processors/
extreme_wind_processor.py` exists (`IEC_TURBINE_CUTOUT_SPEED_MS`,
`SOLAR_GUST_PERCENTILES`, `raw_raster_path()`, `WIND_TEMPORAL_WINDOW`).
`data/processed/climate/extreme_wind_gust_raw_{Brazil,Portugal,India}
_1km.tif` confirmed present on disk (verified this snapshot, `find`).
`risk_calculator.HAZARD_TERMS` includes `"wind"` (`risk_calculator.py:214`)
and `LOG_TERMS` includes `"wind"` (`:224`); `FROZEN_BOUNDS["wind"] =
(9.123578071594238, 31.070894241333008)` (`:344-363`).
`hazard_scope.PENDING_RISK_I_H_HAZARDS = {}` (empty, `hazard_scope.py:143`)
confirms no hazard is missing its `Risk_{i,h}` wiring.

**Commits, in order**: `8c15714` (processor, dual-consumer design) →
`1a4ae25` (Phase 2.3 follow-up: ERA5 kept as historical baseline,
CMIP6-substitution investigated and rejected) → `5a56cac` (ERA5 acquisition
complete, all 3 countries, 30/30 years each) → `adea4d5` (pre-wiring audit,
decision points only) → `b305787` (wired into `risk_calculator.py`) →
`74915ea` (Phase 3.3, transform formula finalized for `wind` along with the
other `LOG_TERMS`).

**Decisions closed**: "GEAR v3 Phase 2.3: Extreme Wind processor (ERA5
gust, dual-consumer threshold design)"; "GEAR v3 Phase 2.3 follow-up: ERA5
temporal asymmetry retained"; "GEAR v3 Extreme Wind: reframed as
scenario-invariant structural exposure"; "GEAR v3 Phase 3.2 follow-up:
ERA5 GRIB mislabeling bug fixed, 18 Brazil years recovered"; "GEAR v3 Phase
3.2 follow-up: ERA5 download disk-footprint restructuring"; "GEAR v3 wind
Risk_i,h integration: empirical transform result, PENDING_RISK_I_H_HAZARDS
closed" (2026-09-14, skew +0.6215 readout). 30 tests in
`tests/test_extreme_wind_processor.py` (current collected count).

**Note on stale "open" statuses still literally in the file**: three older
`DECISIONS.md` entries (2026-09-12/13, around the Phase 3.2 real-data run
and the "Risk_i,h integration gap" entry) have their own `Status:` lines
still reading "open, blocked on author-authorized ERA5 acquisition" or
"Point 1 open, blocked on author decision." These are **not edited** (this
project's append-only convention for reopening/superseding), but are
functionally resolved by the later commits/entries above — flagged here so
a reader does not mistake a stale per-entry `Status:` line for the true
current state.

### 2.4 Normalization module — **CLOSED (2026-09-11, recommendation layer); its recommendation applied to production in Phase 3.3**

**Resolves in one sentence**: an isolated module that runs a real
skewness-based normality check on every hazard candidate and recommends
`direct_minmax` or `neg_log_minmax` (`-ln(1-x)`) — never modifies
`risk_calculator.py` itself.

**Status by code**: closed as a recommendation engine; its recommendation
is now the live production transform for `LOG_TERMS` (via Phase 3.3, not
via this module directly — `normalization.py` still never imports back into
`risk_calculator.py`, confirmed by grep, no executable
`risk_calculator.FROZEN_BOUNDS`/`transform_term` reference in
`normalization.py` outside docstring prose). `SKEWNESS_NORMAL_THRESHOLD =
0.5` (Bulmer 1979), `UPPER_TAIL_PADDING_FRACTION = 0.05` — both confirmed
live constants, `normalization.py:161,211`.

**Commit**: `48e4920`. **Decision**: "GEAR v3 Phase 2.4: Normalization
module, neg-log transform confirmed to replace log1p (Methods Section 4.2
closed)". 23 tests, `tests/test_normalization.py` (current collected
count, same number).

### 2.5 Correlation gate — **CLOSED (2026-09-12), all three countries**

**Resolves in one sentence**: an isolated module testing `|r| >= 0.80`
exclusion for candidate hazard pairs (Extreme Precipitation vs. Water
Stress/Drought, `sv`/`iv` vs. Water Stress and each other), with a
pre-registered tie-breaker hierarchy for a fail.

**Status by code and real data, not by work-plan trust (independently
re-verified in this session before this snapshot)**: closed.
`correlation_gate.py:181`: `GATE_THRESHOLD = 0.80`.
`data/outputs/tables/correlation_gate.csv` exists on disk (56 rows,
`Brazil`/`Portugal`/`India`/`pooled` all present, confirmed by direct
`pandas.read_csv` in this session). Among 44 gated rows:
`decision_r.abs().max() == 0.7020788...` (Seasonal vs. Interannual
Variability, Hydro), `(gate_verdict == "fail").any() == False` — every
gated pair passed, tie-breaker never invoked on real data.

**Commit**: `c63164e`. **Decisions**: "GEAR v3 Phase 2.5: correlation gate
implemented and run -- every gated pair passed, no exclusion"; "...
follow-up: Portugal/India Extreme Precipitation processed, gate closed for
all three countries"; "GEAR v3 Phase 2.5: pre-registered correlation-gate
tie-breaker rule". 27 tests, `tests/test_correlation_gate.py`.

No open items belonging to Phase 2 as a whole (2.1, 2.4, 2.5 closed; 2.2
deferred by design; 2.3 closed).

---

## Phase 3: Applicable hazard subsets and threshold tiers

Three sub-phases.

### 3.1 Per-bucket H_b tables — **CLOSED (2026-09-12)**

**Resolves in one sentence**: which hazards apply to which technology
bucket (`hydro`/`thermal`/`wind`/`solar`), single source of truth for every
downstream phase.

**Status by code**: closed, live.
`src/index/hazard_scope.py::APPLICABLE_HAZARDS` (`:107-112`):
`hydro=(ws,spei,precip,sv,iv)` (5), `thermal=(ws,heat,precip)` (3),
`wind=(wind,)` (1), `solar=(heat,precip,wind)` (3). File first appears in
git at commit `1929d58` — the reconciled version, after a documented
parallel-session conflict (two Claude Code sessions edited this file
concurrently; one overwrote the other's already-confirmed `sv`/`iv`
Hydro-only decision). `_validate()` runs at import time and is not a
substitute for `tests/test_hazard_scope.py` (13 tests, current collected
count).

**Decision**: "GEAR v3 Phase 3.1: hazard_scope.py reconciliation after
parallel-session conflict" (2026-09-12) — this is also the origin of this
project's binding "a phase's primary deliverable file is written by that
phase's session only" convention, now in `docs/LIMITATIONS.md`'s
coordination-convention preamble.

### 3.2 RiskBand_{i,h} threshold classification — **CLOSED**

**Resolves in one sentence**: classify each hazard's raw (untransformed)
physical value into a discrete band (Low/Medium/High/Extreme, or
Wind-bucket's compressed Low/Extreme) per a Tier 1 (absolute) or Tier 3
(sample-relative percentile) threshold table.

**Status by code**: closed for every `(hazard, bucket)` pair
`hazard_scope.APPLICABLE_HAZARDS` names, including Extreme Wind in both its
buckets (verified: `THRESHOLD_REGISTRY` in `risk_bands.py:225-314` has
exactly one entry per pair, and a module-level assertion
(`risk_bands.py:316-324`) fails import if that 1:1 correspondence with
`hazard_scope.APPLICABLE_HAZARDS` ever breaks). **Important, confirmed by
direct code read**: this module classifies on **raw physical values**, not
on the `Tlog`/`Tlin`-transformed `Hazard_{i,h}`; `risk_bands.py`'s own
docstring (`:16-23`) states it does not touch
`risk_calculator.FROZEN_BOUNDS`/`transform_term`, and no executable line in
the module references either name — confirmed by grep. **This means Phase
3.3's transform-formula change (below) has zero effect on RiskBand
classification or PSAE** — a correction this snapshot's own preceding
sessions made after initially overstating this (see `DECISIONS.md`'s Phase
3.3 entry's appended "Correction" block).

**Files/functions**: `src/index/risk_bands.py` — `classify_hazard()`,
`compute_risk_bands()`, `percentile_band_cuts()`, `_bandize()`,
`THRESHOLD_REGISTRY`, `BAND_LABELS`/`WIND_BUCKET_BAND_LABELS`. First
appears (v3 version) in commit `ec76f03` ("Phase 3.2 follow-up:
RiskBand_i,h consolidation, ERA5 GRIB fix and disk-footprint
restructuring, Solar Extreme Heat Tier 1 closed") — the only commit
touching this file since Phase 1's retirement of the old CCRS-era version,
meaning the v3 rewrite and its "follow-up" fixes landed in one commit.

**Decisions closed**: "GEAR v3 Phase 3.2: RiskBand_i,h threshold
classification, consolidated tier/threshold table"; "GEAR v3 Phase 3.2
follow-up: Solar Extreme Heat Tier 1 PV threshold -- bounded search closed,
Tier 3 confirmed final" (2026-09-12, closes the one item that entry's own
`Status:` line had flagged open). 29 tests, `tests/test_risk_bands.py`
(current collected count).

### 3.3 Apply Phase 2.4's transform recommendation to production — **CLOSED (2026-09-14)**

**Resolves in one sentence**: `risk_calculator.transform_term`'s `Tlog`
branch (for `ws`/`heat`/`spei`/`wind`) is `-ln(1-x)`, not the retired
`log1p`.

**Status by code**: closed. `risk_calculator.py:508-543`
(`transform_term`), new constant `TLOG_UPPER_TAIL_PADDING_FRACTION = 0.05`
(`:511`, mirrors `normalization.UPPER_TAIL_PADDING_FRACTION`, not imported
across the circular-import boundary). Grep-confirmed: no
`np.log1p(raw)`/`np.log1p(lo)`/`np.log1p(hi)` anywhere in the module.
`LIN_TERMS = {sv, iv, precip}` untouched, `FROZEN_BOUNDS` values
unchanged (raw bounds are transform-independent).

**Author decision (Option B, not inferred)**: the swap applies to the full
current `LOG_TERMS` set (`ws`, `heat`, `spei`, `wind`), not only the three
terms that predate `wind`'s Phase 2.3/3.3 wiring.

**Commit**: `74915ea`. **Decision**: "Phase 3.3 -- Tlog is -ln(1-x) for
ws/heat/spei/wind" section of `DECISIONS.md` (the "Phase 3.3 scope over
`wind`: CLOSED, Option B" entry). 336/336 (at the time)→ later 363/363
tests pass (`tests/test_risk_calculator.py`: `test_tlog_is_neg_log_minmax`,
`test_tlog_matches_normalization_neg_log_minmax`, others).

**Published-article cross-check (this session, verbatim quote from the
author-pasted Supplementary Table S3)**: every `FROZEN_BOUNDS` row the
article documents (`ws`, `sv`, `iv`, Extreme Heat x2 GCMs, Extreme
Precipitation x2 GCMs, Drought/SPEI x2 GCMs) is tiered **"empirical
(pooled sample min/max)"** — confirms bounds were never percentile-based,
closing a separate methodology-text ambiguity (below, "Findings/
divergences").

**Open item belonging to this sub-phase (found, not resolved, by this
session)**: Table S3's `Transform` column lists **Drought (SPEI) as
`direct Min-Max`** for both GCMs (skew 0.36/0.13, both `<0.5`), but
`risk_calculator.LOG_TERMS` still includes `spei` unconditionally
(inherited from the retired CCRS design, never re-evaluated against the
real empirical skewness check the way `precip`/`wind` were). **Not
registered as a formal `DECISIONS.md` open entry as of this snapshot** —
flagged only in conversation so far. See "Findings/divergences" below.

---

## Phase 4: PSAE aggregation — **CLOSED (2026-09-14)**

**Resolves in one sentence**: `PSAE_i = count(RiskBand_{i,h} >= High, h in
H_b) / |H_b|`, per plant × water_scenario, an unweighted physical-exposure
screening fraction, classified into LOW/MEDIUM/HIGH/EXTREME (or Wind's
compressed LOW/EXTREME).

**Status by code**: closed and tested. `src/index/psae.py` exists (did
not exist before this phase — confirmed via `git log --diff-filter=A`,
first and only commit `6b70a36`). Consumes
`risk_bands.RiskBandTable.frame` only — does not import
`risk_calculator` at all (confirmed: no `risk_calculator`/`rc` import in
`psae.py`), so it has zero exposure, direct or indirect, to Phase 3.3's
transform-formula change.

**Files/functions**: `compute_psae()`, `classify_psae_fraction()`,
`assert_single_bucket()`/`CrossBucketPSAEComparisonError`,
`rank_within_bucket()`, `build_summary()`. All in `src/index/psae.py`.

**Complete-case decision (closed, author-confirmed, not the assistant's
default)**: if any hazard in a plant's bucket's `H_b` has a missing/`NaN`
`RiskBand_{i,h}`, `psae` for that plant/water_scenario is `NaN` —
`h_b_size` stays the bucket's full nominal count (never shrunk),
the missing hazard never counts toward the numerator, and the row is
never dropped (`psae_complete: bool`, `missing_hazards: tuple[str, ...]`
carry the distinction explicitly). `DECISIONS.md`, "Phase 4 (PSAE) input
mapping; missing/NaN RiskBand handling in the PSAE denominator: CLOSED,
complete-case" (2026-09-14).

**Comparability guard (work plan Phase 4.2)**: implemented —
`assert_single_bucket`/`CrossBucketPSAEComparisonError` raise on any
cross-bucket PSAE frame; `rank_within_bucket` is the one shared
ranking function this module provides, guarded.

**Commit**: `6b70a36`. 27 tests, `tests/test_psae.py` (current collected
count, includes a dedicated regression test proving a missing hazard
never yields the same result a "treat-as-not-High" reading would have
produced).

**Wildfire/6-hazard-count correction, made during this phase's own
mapping (not this task's premise)**: the methodology's Section 2 checklist
names six core hazards (Water Stress, Extreme Heat, Drought, Extreme
Precipitation, Wildfire, Extreme Wind); by direct code read, only **five**
are integrated in `HAZARD_TERMS` — Wildfire remains deferred (Phase 2.2).
`sv`/`iv` are two additional non-checklist terms, resolved into Hydro's
`H_b` but not part of the six-name list.

No open items belonging to Phase 4 as scoped by the work plan (4.1, 4.2
both done). One item belongs to Phase 6 instead — see below (item 6, PSAE
`psae_complete=False` treatment under Sobol/OAT).

---

## Phase 5: Contextual validator layer — **NOT STARTED (0%)**

**Resolves in one sentence**: a two-class validator taxonomy
(physical-occurrence: IBTrACS/FIRMS; broad-impact: EM-DAT), three-state
output (Corroborated/No Record/Not Applicable) per validator per asset,
never modifying `PSAE`/`RiskBand`/`Risk_{i,h}`.

**Status by code, confirmed by grep, not assumed from "independent, can
run anytime"**: not started. `grep -rl "IBTrACS\|FIRMS\|Corroborated"
src/` returns **zero matches** anywhere in the live source tree. The only
EM-DAT-adjacent code is `src/index/emdat_validation.py`, which is
CCRS-era, one of the four Phase-1-broken modules (`ImportError: cannot
import name 'ccrs_calculator'`, confirmed this snapshot) — not a Phase 5
implementation, and not reusable as-is (it predates the two-class
taxonomy/three-state-output redesign). No `tests/test_emdat_validation.py`
exists.

**Files/functions this phase has created**: none.

**Decisions closed belonging to this phase**: none. The retired `event_
multiplier.py` (`src/index/event_multiplier.py`, CCRS-era) is explicitly
named a Phase 5 candidate input in its own comment (`:98`,
`risk_calculator.py:21`) and in `DECISIONS.md` (`:991`), but this is a
forward-looking note attached to an already-retired module, not Phase 5
work itself.

**Open items belonging to this phase**: the entire phase is open — no
`DECISIONS.md` entry frames it as blocked on a specific author question
the way later phases are; it is simply unstarted, dependency-free (per
work plan: "only needs Phase 1.4," already done).

---

## Phase 6: Sensitivity and uncertainty — **NOT IMPLEMENTED; extensively mapped, partially decided**

**Resolves in one sentence**: Sobol/SALib global sensitivity indices for
continuous parameters (age_factor rates, RiskBand percentile-cut ranks,
neg-log tail-padding fraction), plus a separate one-at-a-time/
scenario-discovery analysis for discrete/structural parameters (H_b
membership, PSAE cut points, correlation-gate cutoff).

**Status by code**: **no Sobol/OAT code exists**. No
`src/index/sensitivity.py` or equivalent. `src/index/monte_carlo.py`
exists but is CCRS-era (imports the retired `ccrs_calculator`, confirmed
broken this snapshot) and is explicitly **not** carried forward as-is —
its RNG mechanics (`country_rng`, `zlib.crc32`+`SeedSequence`,
`N_ITERATIONS = 1000`, `PERCENTILES = (2.5, 50.0, 97.5)`) are read as
precedent only, confirmed accurate by direct grep
(`monte_carlo.py:143-175`) in this session's mapping work.

**`docs/rework/PHASE6_DESIGN.md`** (read in full this session; previously
untracked, never read before): a **design-only research draft, not an
approved plan** — states so of itself ("No code is implemented or run
against this document"), and its own Section 5 lists six items needing
author confirmation. Verified accurate against real code where checkable
(age_factor constants, `hazard_scope.APPLICABLE_HAZARDS`, `monte_carlo.py`
mechanics) but stale in one place (Section 0 said Phase 4 "not
implemented" — now closed) and silent on one real mechanic that postdates
it (`psae.py`'s complete-case fields).

**Phase 2.5 dependency, independently re-verified this session (not
trusted from the work plan's "Sequencing notes" line)**: closed — see
Phase 2.5 above.

**Entry points (by import/call, not by sequence assumption)**:
- Sobol candidates: `age_factor.py` (`COAL_DECAY_RATE`,
  `WIND_RELATIVE_RATE`, `HYDRO_RETENTION_RATE`; `SOLAR_RETENTION_RATE`/
  `COAL_OVERHAUL_CYCLE_YEARS`/`COAL_OVERHAUL_RECOVERY` now closed as
  Sobol candidates too, see below); `normalization.
  UPPER_TAIL_PADDING_FRACTION`; `risk_bands.THRESHOLD_REGISTRY`'s Tier 3
  `percentiles` field, per hazard/bucket.
- OAT candidates: `hazard_scope.APPLICABLE_HAZARDS`; `psae.
  classify_psae_fraction`'s inline `1.0`/`0.5`/`0.0` cuts (not yet named
  constants); `correlation_gate.GATE_THRESHOLD`; `normalization.
  SKEWNESS_NORMAL_THRESHOLD`.
- Output statistic: methodology Section 8.1 names only "the summary
  statistic of interest" for Sobol (ambiguous between `Risk_{i,h}` and
  `PSAE_i`); Section 8.2 explicitly names "PSAE/RiskBand outcomes" for
  OAT — resolved for OAT, **not resolved for Sobol**.

**Decisions closed this session (2026-09-14, appended to the Phase 6
mapping entry, `DECISIONS.md`)**:
- **Distribution default**: uniform, ±20% around the current nominal value,
  for any parameter with no better-sourced prior. Binding manuscript note:
  must be flagged as a Tier 3 engineering default, not a literature range.
- **Convergence procedure**: `PHASE6_DESIGN.md` Section 4.1's doubling
  sequence (1000→2000→4000→8000→16000; <1% point-estimate tolerance, <5%
  CI half-width tolerance, confirmed by one further doubling; SE as
  secondary statistic) — adopted, cited as source.
- **`SOLAR_RETENTION_RATE` range**: ±20% around `0.007`/yr →
  `[0.0056, 0.0084]`, no literature source, documented as a limitation.
- **`COAL_OVERHAUL_CYCLE_YEARS`/`COAL_OVERHAUL_RECOVERY` ranges**: ±20%
  around their current ASSUMED values (`5`yr→`[4,6]`; `0.70`→`[0.56,
  0.84]`). Binding note: a high Sobol sensitivity index for either must
  cite the ASSUMED flag in the final report, never presented as a
  confirmed empirical finding.
- **`FROZEN_BOUNDS` percentile ambiguity**: closed separately (see
  "Findings/divergences" below) — there is no bounds-percentile parameter;
  Sobol dimension count `D` revised **7 → 6**.

**Open items belonging to this phase** (literal text preserved in the
dedicated section below): seed/RNG granularity for the new parameter set;
RiskBand percentile-cut Sobol-dimension grouping granularity (affects `D`
further); PSAE `psae_complete=False` rows' treatment under Sobol/OAT.

**Measured cost (this session, real numbers, not estimated)**:
`compute_risk()` (the actual `Risk_{i,h}` pipeline, 3 countries, both
GCMs) timed at **30.50s and 28.87s** on two runs (average 29.68s).
Naive full-recompute-per-draw projection: `D=6` (`2D+2=14`) at `N=16000` ≈
**224,000 evaluations ≈ 79.1 days**; `D=2` (`2D+2=6`) at `N=16000` ≈
96,000 evaluations ≈ **33.9 days**. Both use the naive "re-run the whole
pipeline per Saltelli draw" assumption; `PHASE6_DESIGN.md` Section 4.2's
intended "recompute only the downstream chain" architecture is not
implemented, so its actual cost is unmeasured (see "Findings/divergences").

No further code has been written for this phase.

---

## Phase 7: Visualization and reporting updates — **NOT STARTED for the PSAE/RiskBand split; legacy CCRS visualization exists but is broken**

**Resolves in one sentence**: update/replace CCRS-labeled figures for the
`PSAE`/`Risk_{i,h}` split, add technology-differentiated markers, add the
Phase 5 validator overlay, produce the `FROZEN_BOUNDS`/threshold
tier-provenance tables, implement intra-hazard `Risk_{i,h}` comparison
figures.

**Status by code**: `src/visualization/` exists (11 CCRS figure
categories per its own commit `02664c4`) but is one of the four
Phase-1-broken modules — `tests/test_visualization.py` fails collection
(`ImportError: cannot import name 'ccrs_calculator'`, confirmed this
snapshot; 101 `def test_` functions in that file, **0 collected**). No
PSAE-aware or `Risk_{i,h}`-per-hazard figure code exists. Depends on
Phases 4 (done) and 5 (not started) per the work plan; not viable to start
in full until Phase 5 exists, though the PSAE/Risk_{i,h}-only items
(7.1, 7.4, 7.5) do not themselves need Phase 5.

No open items formally registered for this phase; it is simply blocked/
not started.

---

## Phase 8: Documentation reconciliation — **NOT STARTED**

**Resolves in one sentence**: final documentation cleanup pass — SLR's
missing formal `DECISIONS.md` entry, Monte Carlo's missing closure entry,
a full consistency pass, and a changelog-language check.

**Status by code/docs, confirmed this session**: not started.
`grep "Sea-level rise" docs/DECISIONS.md` finds **zero matches** — SLR
exclusion exists only in `docs/LIMITATIONS.md` ("2026-09-03 -- Sea-level
rise (SLR) excluded from the hazard set"), confirming work-plan item 8.1
is still open exactly as the work plan itself already flags it. Monte
Carlo's implementation-status entry (8.2) is also absent — consistent with
Phase 6 not existing yet to close it.

No open items beyond "everything in this phase is pending," by design
("do last").

---

# Cross-phase data-dependency graph (by import/call, not by sequence)

```
risk_calculator.py (Phase 1/2.3/3.3)
  Risk_i,h = Hazard_i,h x Exposure_i x Vulnerability_i
  imports: age_factor.py (Vulnerability_i)
        |
        v  (raw physical values, NOT Hazard_i,h -- risk_bands.py never
        |   imports transform_term/FROZEN_BOUNDS, confirmed by grep)
  risk_bands.py (Phase 3.2)
    imports: hazard_scope.py (H_b table, Phase 3.1)
             risk_calculator.py (plant/raster loading only, sample_raster,
                                  raster_path -- infrastructure reuse,
                                  never the transform)
    -> RiskBand_i,h (classification label per hazard/bucket)
        |
        v
  psae.py (Phase 4)
    imports: risk_bands.py (RiskBandTable.frame)
             hazard_scope.py (APPLICABLE_HAZARDS, for H_b/denominator)
    does NOT import risk_calculator.py at all
    -> PSAE_i (complete-case fraction + label + coverage flags)
        |
        v
  [Phase 6: Sobol/Monte Carlo -- NOT IMPLEMENTED]
    would consume: age_factor.py rates, normalization.py's
    UPPER_TAIL_PADDING_FRACTION, risk_bands.py's percentile cuts,
    hazard_scope.py's H_b membership, correlation_gate.py's GATE_THRESHOLD,
    psae.py's classify_psae_fraction cuts -- output statistic (Risk_i,h,
    PSAE_i, or both) not yet resolved (Phase 6 open item)
        |
        v
  [Phase 7: Visualization -- NOT STARTED for PSAE/Risk_i,h split]

normalization.py (Phase 2.4)
  imports: risk_calculator.py (plant/raster infrastructure only)
  produces an INDEPENDENT recommendation (bounds + transform + origin
  table) -- never feeds back into risk_calculator.py automatically.
  Its recommendation was manually applied to risk_calculator.py's Tlog
  branch by Phase 3.3 (a separate task/commit, not an automatic wire).

correlation_gate.py (Phase 2.5)
  imports: risk_calculator.py (plant/raster infrastructure), _common.py
  runs on RAW pre-normalization values, independent of normalization.py
  output feeds Phase 3.1's H_b decision (a human read of
    correlation_gate.csv, not an automated import)

Phase 5 (contextual validators) -- NOT STARTED
  by design (Methods Section 7 / work plan): independent of Phase 3/4,
  consumes nothing from Risk_i,h/RiskBand/PSAE, and Section 7.3/methodology
  states explicitly no validator state may ever modify PSAE, RiskBand, or
  Risk_i,h in the other direction either. Its only planned consumer is
  Phase 7 (map overlay).
```

**Key finding from tracing this graph directly (not assumed)**: Phase
3.3's transform-formula change (`log1p` → `-ln(1-x)`) has **zero** effect
on `RiskBand_{i,h}` or `PSAE_i` — both are computed from raw physical
values, never from the `Tlog`/`Tlin`-transformed `Hazard_{i,h}`. This was
initially mis-stated in this project's own `DECISIONS.md` (Phase 3.3's
original "Consequence" bullet) and corrected in an appended block the same
day, per this file's append-only convention.

---

# Repeated conventions across phases

| Convention | First appearance | Reapplied |
|---|---|---|
| **Complete-case for missing data** (never shrink a denominator to match available data, never silently treat missing as "no risk") | Phase 4, `psae.py`'s `psae_complete`/`missing_hazards` (`DECISIONS.md`, "Phase 4 (PSAE) input mapping... CLOSED, complete-case", 2026-09-14) | Flagged (not yet resolved) as the open question for how Phase 6's Sobol/OAT should treat `psae_complete=False` rows (Phase 6 open item 6) |
| **Fail-loud instead of masking a data gap** | Project-wide convention, `CLAUDE.md` Section 8; concrete precedent: `risk_bands.HazardNotApplicableError`, `_sample_raster_or_nan`'s explicit-NaN-plus-logged-warning (Phase 3.2) | Cited explicitly as the reasoning against PSAE's rejected option (c) "treat-as-not-High" (Phase 4 closure); cited again as the reasoning behind the ±20%/ASSUMED-flag binding notes (Phase 6 closures, this session) |
| **Diff review separated from commit, as its own gated step** | First explicit in this conversation at Phase 3.3 (a dedicated "review the diff, no commit" turn before a separate "commit" turn) | Reapplied identically for Phase 4/PSAE (review turn, then commit turn `6b70a36`) |
| **Undocumented decision registered as Open in `DECISIONS.md`, never assumed** | Phase 4 mapping (missing/NaN PSAE denominator handling logged Open before being closed) | Reapplied for Phase 6 mapping (six items logged Open, four later closed this session); reapplied for the `FROZEN_BOUNDS` percentile ambiguity (logged Open, then closed citing Table S3) |
| **Never reopen a closed decision without an explicit new reason** | Stated as the operating rule when the `FROZEN_BOUNDS` (Phase 3.1's origin entry, 2026-09-04) reopening was done -- the reopening itself states the new reason (a *later* methodology document's wording contradicting the *earlier*, unchanged implementation) rather than re-litigating the original 2026-09-04 decision | The reopening was itself appended, not edited, and closed the same day once the real methodology source (Table S3) was available -- the original entry's text was never rewritten |
| **A phase's primary deliverable file is written by that phase's session only** | `docs/LIMITATIONS.md`'s binding coordination convention, originating in the Phase 3.1 `hazard_scope.py` parallel-session conflict | Not violated again since; cited as the reason this snapshot does not modify any phase's own deliverable file |

---

# Methodology summary (plain language)

**Hazard normalization (`Hazard_{i,h}`, Section 4.2/Equation in
`risk_calculator.transform_term`)**: each hazard's raw physical value is
scaled to `[0, 1]` against a frozen empirical bound (pooled sample
min/max, never a percentile trim — confirmed by the published article's
Supplementary Table S3, tier label "empirical (pooled sample min/max)"
for every hazard the article documents). Which of two transforms applies
is decided per hazard by a real skewness check (Fisher-Pearson, decisive;
Shapiro-Wilk reported as a diagnostic only), `|skew| <= 0.5` = "fairly
symmetrical" (Bulmer 1979 convention): **direct Min-Max** for
approximately-symmetric hazards (`sv`, `iv`, Extreme Precipitation, per
Table S3 — and, per Table S3's own reported skew values, arguably `spei`
too; see "Findings/divergences"); **`f(x) = -ln(1-x)`** (on a padded
preliminary `[0,1]` scaling) for right-skewed hazards (`ws`, Extreme Heat,
`wind`). This replaces an earlier `log1p` transform, which compressed the
upper tail of right-skewed hazards — the difference between, e.g., 80 and
120 extreme-heat days/year was compressed toward a smaller normalized
difference under `log1p`, obscuring exactly the tail contrast most
relevant to infrastructure risk; `-ln(1-x)` expands rather than compresses
that region.

**RiskBand classification (`risk_bands.py`)**: independent of the
normalization above — classifies each hazard's **raw, untransformed**
physical value into Low/Medium/High/Extreme (or Wind-bucket's compressed
Low/Extreme, since its single IEC cut-out threshold only ever produces two
outcomes) against either an absolute Tier 1 cutoff (Water Stress's WRI
Aqueduct cutoffs, Wind's IEC cut-out speed) or a Tier 3 sample-relative
percentile cutoff (P75/P90/P95 for most hazards, P90/P95/P99 for
Extreme Wind's Solar-bucket consumer).

**PSAE aggregation (`psae.py`)**: for plant `i` in bucket `b`, `PSAE_i` is
the unweighted fraction of that bucket's applicable hazards (`H_b`) whose
`RiskBand` is High or Extreme — a physical-exposure screening count, not a
severity-weighted score, deliberately avoiding the "compensatory dilution"
a weighted composite would introduce. Classified LOW/MEDIUM/HIGH/EXTREME
at fixed cuts (`0.0`/`0.5`/`1.0`), with Wind's single-hazard bucket
naturally producing only LOW/EXTREME under the same cut function (no
special-cased branch). Comparable only within the same technology bucket,
never across buckets (`|H_b|` differs by bucket).

**Sobol/Monte Carlo (Phase 6, not yet implemented)**: intended to measure
how sensitive the reported statistic is to continuous parameters that have
no hard literature value (age_factor decay rates, the neg-log tail-padding
fraction, RiskBand percentile-cut ranks) via variance-based Sobol indices,
and separately, via one-at-a-time toggling, how sensitive classification
outcomes are to discrete/structural choices (which hazards belong to a
bucket's `H_b`, the PSAE cut points, the correlation-gate cutoff). Exactly
which output statistic this measures (`Risk_{i,h}`, `PSAE_i`, or both) is
still unresolved (Phase 6 open item, see below) — the methodology text
names only "the summary statistic of interest" for the Sobol half.

---

# Implemented and tested, by module (no optimism)

| Module | Phase | Tests (collected, current) | Status |
|---|---|---|---|
| `risk_calculator.py` | 1/2.3/3.3 | 24 (`test_risk_calculator.py`) | Complete for the 5 checklist hazards + sv/iv. Wildfire absent by design. |
| `hazard_scope.py` | 3.1 | 13 (`test_hazard_scope.py`) | Complete. |
| `risk_bands.py` | 3.2 | 29 (`test_risk_bands.py`) | Complete for every `(hazard, bucket)` pair in `APPLICABLE_HAZARDS`. |
| `normalization.py` | 2.4 | 23 (`test_normalization.py`) | Complete as a recommendation engine. |
| `correlation_gate.py` | 2.5 | 27 (`test_correlation_gate.py`) | Complete, run against real data, all 3 countries. |
| `psae.py` | 4 | 27 (`test_psae.py`) | Complete: aggregation, complete-case, comparability guard. |
| `extreme_wind_processor.py` | 2.3 | 30 (`test_extreme_wind_processor.py`) | Complete, acquisition done for all 3 countries. |
| `extreme_precipitation_processor.py` | 2.1 | 11 | Complete. |
| `age_factor.py` | 1 (reused, not rewritten) | 20 | Complete, live, consumed by `risk_calculator.compute_risk_by_hazard`. |
| Phase 5 (validators) | 5 | 0 (no test file) | **Not started at all.** |
| Phase 6 (Sobol/OAT) | 6 | 0 (no module, no test file) | **Not implemented.** Design draft exists (`PHASE6_DESIGN.md`), four Sobol-parameter decisions now closed (this session), several items still open (below). |
| Phase 7 (viz, PSAE-aware) | 7 | 0 for the new split; 101 defined/0 collected for the legacy CCRS figures (`test_visualization.py`, broken import) | Legacy CCRS visualization exists but does not run; no PSAE/Risk_i,h-split figures exist. |
| `monte_carlo.py` (legacy) | pre-v3 | 23 defined / 0 collected (`ImportError`) | Broken by design (Phase 1), read only for RNG/N precedent, not runnable. |
| `main.py` | pre-v3 | 7 defined / 0 collected | Broken by design (Phase 1), CCRS-era orchestrator. |
| `emdat_validation.py` | pre-v3 | 0 (no test file) | Broken by design (Phase 1), CCRS-era, not a Phase 5 implementation. |

**Full suite, this session's last actual run**: 363/363 passing, excluding
`test_main.py`/`test_monte_carlo.py`/`test_visualization.py` (all three
confirmed broken on the same pre-existing, unrelated cause —
`ImportError: cannot import name 'ccrs_calculator'`).

---

# Every item currently Open in `DECISIONS.md` (literal text, grouped by phase)

## Phase 3.3 (found during Phase 4 mapping, not yet a formal `DECISIONS.md`
entry as of this snapshot — see "Findings/divergences" below for why it
is listed here rather than quoted from the file)

Not a `DECISIONS.md` entry yet. Described in conversation only: whether
`spei`'s membership in `LOG_TERMS` (inherited from the retired CCRS
design, never re-evaluated against the real skewness check) should be
reclassified to `LIN_TERMS`, given the published article's own Table S3
reports SPEI's transform as `direct Min-Max` (skew 0.36/0.13, both under
the `|skew|<=0.5` threshold) for both GCMs.

## Phase 6 (Sensitivity/uncertainty) input mapping — remaining open items,
quoted verbatim from `DECISIONS.md`

> 3. **Seed/reproducibility and RNG granularity for the new parameter
> set.** `PHASE6_DESIGN.md` Section 3 already states this explicitly as
> unresolved (not this entry's own finding, restated here so it is not
> left standing only in the untracked draft): whether Phase 6's RNG
> streams are keyed per-country or per-country-scenario has no
> author-confirmed answer for the current (post-CCRS) parameter set --
> the old per-country approval was scoped to the retired
> `EventMultiplier`/bucket-weight parameters, not to age_factor rates or
> RiskBand percentile cuts. Whether `config.RANDOM_SEED` (the constant
> the retired module keyed off) is reused for Phase 6, or a new seed
> constant is introduced, is also not stated anywhere.

> 4(c). [part of item 4] whether the RiskBand percentile-cut Sobol
> dimension is grouped one-per-hazard-family or one-per-hazard changes `D`
> from 2 to 6 for that family alone, directly changing the Saltelli
> evaluation budget (`N_0 * (2D + 2)`). ... still open, not addressed by
> this closure. Whether that family is one dimension or six remains
> undecided; `D`'s exact final value still depends on this sub-item.

> 6. **PSAE `psae_complete=False` rows' treatment in the sensitivity
> analysis -- not addressed anywhere, found in this entry.**
> `PHASE6_DESIGN.md` predates `psae.py`'s actual complete-case mechanic...
> and has no provision for it in its Section 2.2 PSAE-cut-point OAT
> design. Three plausible readings, none written down anywhere: (a)
> restrict every Phase 6 PSAE-based statistic to `psae_complete=True` rows
> only, silently narrowing the plant sample the sensitivity analysis
> actually covers; (b) treat an incomplete row's contribution to any
> aggregate statistic (e.g. capacity-weighted PSAE-band fraction) as
> itself missing/NaN, propagating the gap into the reported statistic
> rather than silently dropping the plant; (c) something else not yet
> articulated. This is the same category of gap the Phase 4 entry above
> closed for PSAE's own denominator -- unresolved here for how Phase 6
> consumes PSAE's output.

**Items 1, 2, 4(a), 4(b), and 5 of this same entry are CLOSED (this
session)** — not reproduced here since they are no longer open; see Phase
3.3 and Phase 6 sections above for their resolutions.

## No other currently-open `DECISIONS.md` entries found

Every other `Status:`/`- Status` line in the file containing the word
"open" (grepped exhaustively this session) belongs to one of two
categories, neither a live open question: (a) historical entries about
`wind`'s ERA5 acquisition being blocked, now factually superseded by
`wind`'s completed wiring (Phase 2.3/3.3 above) even though their own
`Status:` line was never edited to say so (append-only convention); (b)
conditional/aspirational language ("open to revision only if...") that is
not a pending decision, just a stated willingness to revisit given new
evidence.

---

# Findings / divergences identified but not resolved

1. **`spei` classification divergence (Phase 3.3).** The published
   article's Table S3 reports Drought (SPEI)'s transform as `direct
   Min-Max` for both GCMs (skew 0.36 GFDL-ESM4, 0.13 MIROC6 — both under
   the `|skew|<=0.5` threshold that would select `direct_minmax`), but
   `risk_calculator.LOG_TERMS` (`risk_calculator.py:224`) still includes
   `spei` unconditionally, applying `-ln(1-x)` to it. `spei`'s `LOG_TERMS`
   membership was inherited from the retired CCRS design (`ws`/`heat`/
   `spei` were `LOG_TERMS` from Phase 1 onward) and was never re-evaluated
   against the real empirical skewness check `normalization.py` runs for
   every candidate — unlike `precip` and `wind`, which were classified
   from their own measured skew. Flagged in conversation, **not yet a
   formal `DECISIONS.md` entry**, not investigated further, not acted on.

2. **Manuscript pendency: Table S3 missing the `wind` row.** The
   author-pasted Table S3 excerpt carries a footnote stating Extreme Wind
   is absent because "no country yet has a processed ERA5 raster... so no
   bounds exist to report" — true when the article text was written, false
   now. `wind` has a real, empirical `FROZEN_BOUNDS` entry
   (`(9.123578071594238, 31.070894241333008)`) and a real `-ln(1-x)`
   transform (Phase 3.3). This is registered in `DECISIONS.md` (the
   `FROZEN_BOUNDS` reopening/closure entry) as **explicitly a
   manuscript-update pendency, not a code pendency** — the author owns
   revising the submitted/published table, this repository's code is
   already correct and complete for `wind`.

3. **Naive Sobol recompute is not viable at the proposed `N`/`D`.**
   Measured this session: one full `compute_risk()` run (3 countries, both
   GCMs) takes ~29.7s (two runs: 30.50s, 28.87s). A naive
   "re-run-the-whole-pipeline-per-Saltelli-draw" approach projects to
   **~79.1 days** at `D=6`, `N=16000` (224,000 evaluations), or **~33.9
   days** at `D=2`, `N=16000` (96,000 evaluations) — both measured, not
   estimated from code inspection alone. `PHASE6_DESIGN.md` Section 4.2
   already proposes the fix (recompute only the downstream
   `age_factor -> RiskBand -> PSAE` chain per draw, not re-read every
   raster), matching the legacy `monte_carlo.py`'s own "fixed inputs
   computed once, perturbed chain recomputed per draw" architecture — but
   **this partial-recomputation path is not implemented for the new
   PSAE-based chain**, so its actual (much lower, expected) cost has not
   itself been measured. No decision was made about which cost model
   Phase 6 will actually run under.

---

# Uncommitted state as of this snapshot

`git status --short` at the time of writing: `docs/DECISIONS.md` and
`docs/rework/GEAR_v3_methodology_nature_format.md` are both modified but
**not committed** (contain, respectively: the Phase 6 mapping entry, the
`FROZEN_BOUNDS` reopening/closure citing Table S3, and the four
Sobol-parameter closures from this session; and the Section 8.1 text
correction removing "FROZEN_BOUNDS percentile choices"). `docs/rework/
PHASE6_DESIGN.md` and four `scratch_run_*.py` files at the repository root
are untracked, pre-existing, unrelated to this snapshot, and were not
created or modified by it. This snapshot document itself
(`docs/PROJECT_STATE_SNAPSHOT.md`) is new and untracked as of writing.
