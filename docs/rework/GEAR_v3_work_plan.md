# GEAR v3: Implementation Work Plan

Companion to GEAR_v3_methodology_nature_format.md. Sequences
implementation so decisions with the widest blast radius are confirmed
before dependent code is written. Each phase below is meant to become
one or more Claude Code prompts in a future chat. Carry both files into
that chat for context.

Standing rules for every Claude Code prompt derived from this plan
(restate in each prompt, do not assume carryover):
- Update docs/memory/ unconditionally on task completion.
- Update docs/ARCHITECTURE.md and docs/DECISIONS.md when the task
  implements a methodological decision, fixed format (Decision /
  Reason / Status), tier of evidence stated, prior entries marked
  superseded, never deleted.
- No changelog language ("this was changed because...") outside
  DECISIONS.md and docs/memory.
- Investigation tasks (marked "Verify" below) report factually, do not
  decide or implement; implementation only proceeds after the author
  confirms the finding.
- Structure all new code modularly: normalization (FROZEN_BOUNDS,
  transform selection) as its own isolated module; the correlation gate
  as its own class implementing the symmetric \|r\| < 0.80 test and the
  spatial-harmonization step, not inlined into a processor; every
  hazard's temporal-window assumption exposed as an explicit, readable
  flag/constant (not buried in a docstring), so a future audit of the
  Python codebase can check data-window alignment without reading every
  processor line by line.
- When a task is finalized, don't need to send the whole document, just
  just send the part that need to be substituted in this document to
  prevail that the task was done and a briefly explanation of the
  output(s) when the task is finalized, just to made a reminder in
  future changes.

## Phase 0: Blocking verifications (do first, gates everything else)

Note: the item on Aqueduct's temporal horizon from earlier drafts of
this plan is resolved and removed. The pipeline's water stress
indicator (`ws`, future_annual product, horizon 50) is already a
mid-century projection aligned to the same three SSP labels used
elsewhere; no verification or code change is needed for this point
(Methods Section 1.1).

1. **Closed (2026-09-11)**: GEM cooling-technology field confirmed
   absent. See `docs/DECISIONS.md`, "GEM cooling-technology field:
   confirmed absent (v3 Phase 0.1)".
2. **Closed (2026-09-11)**: FWI/EFFIS 6-class system verified and
   adopted; HAZUS-MH rejected, Extreme Precipitation downgraded Tier
   1 -> Tier 3. See `docs/DECISIONS.md`, "FWI/EFFIS wildfire danger
   classes: 6-class system adopted (v3 Phase 0.2)" and "Extreme
   Precipitation downgraded Tier 1 -> Tier 3 (v3 Phase 0.2)".
3. **Closed (2026-09-11)**: GEM retrofit/repowering field re-confirmed
   empty, unchanged. See `docs/DECISIONS.md`, "GEM retrofit/repowering
   field: re-confirmed empty (v3 Phase 0.3)".
4. **Closed (2026-09-11)**: no defensible Tier 1 solar tracker wind
   threshold; ERA5 gust percentile confirmed final for Solar. See
   `docs/DECISIONS.md`, "Solar Extreme Wind: ERA5 gust percentile is
   final, not contingency (v3 Phase 0.4)".

Phase 0 closed 2026-09-11, all four items confirmed by the author. Phase
1 may proceed.

## Phase 1: Core equation and hazard layer restructuring -- CLOSED (2026-09-11)

`src/index/ccrs_calculator.py` / `ccrs_report.py` deleted (not deprecated),
replaced by `src/index/risk_calculator.py`: `Risk_i,h = Hazard_i,h x
Exposure_i x Vulnerability_i`, per hazard, never summed; `EventMultiplier`
removed from the core; Exposure's log10 display transform is type-guarded
(`ExposureLog10Display`, `risk_i_h` raises `TypeError` on it); every hazard's
temporal window is the named `HAZARD_TEMPORAL_WINDOW` constant; Thermal
stays homogeneous. `sv`/`iv` (water seasonal/interannual variability) are
computed as independent, explicitly-flagged hazard terms pending Phase 3's
applicable-hazard-set decision -- not folded into Water Stress, not dropped.
Expected, documented breakage: `risk_bands.py`, `monte_carlo.py`,
`emdat_validation.py`, `main.py`, `src/visualization/` still import the
deleted symbols and are broken pending Phases 3/4/6/7 -- not patched here.
See `docs/DECISIONS.md`, "GEAR v3 Phase 1: Risk_i,h replaces the CCRS core"
and "GEAR v3 Phase 1.3: Thermal bucket implemented as homogeneous"; engineering
detail in `docs/memory/05-decisoes-tecnicas.md` item 27. 189/189 tests passing
outside the four broken modules; `tests/test_risk_calculator.py` new (18
tests).

## Phase 2: New hazard layers (data acquisition and processing)

Independent of each other; can be parallelized across separate Claude
Code sessions, but each must pass Phase 2.5 before being added to the
applicable-hazard tables in Phase 3.

2.1. **CLOSED (2026-09-11)**: `src/processors/extreme_precipitation_
     processor.py` -- raw indicator is mean days/year with daily CMIP6 `pr`
     exceeding that pixel's own P95 wet-day threshold (Tier 3
     percentile-cutoff, ETCCDI convention; no HAZUS-MH reference anywhere).
     Reuses the `pr` series already downloaded for SPEI, no new download.
     Same grid/normalisation infrastructure as heat/SPEI (native -> 1 km
     resample -> per-country Min-Max, shared GridMismatchError guard).
     `PRECIP_TEMPORAL_WINDOW` extends Phase 1's `HAZARD_TEMPORAL_WINDOW`
     schema without merging into it -- not wired into
     `risk_calculator.HAZARD_TERMS`, not in any applicable-hazard table
     (both pending Phase 2.5 / Phase 3). See `docs/DECISIONS.md`, "GEAR v3
     Phase 2.1: Extreme Precipitation processor (Tier 3, percentile-cutoff)";
     engineering detail in `docs/memory/05-decisoes-tecnicas.md` item 28.
     11 new tests, 200/200 passing outside the four Phase-1-broken modules.
2.2. **Deferred (2026-09-11)**, see `docs/DECISIONS.md`, "GEAR v3 Phase
     2.2: Wildfire deferred (data availability)".
2.3. Extreme Wind processor, ERA5 acquisition (gust or sustained speed
     at 10m/100m), same unified grid infrastructure. Built to serve two
     downstream consumers (Wind bucket, Solar bucket) with potentially
     different thresholds per Phase 0 item 4, not hardcoded to one.
2.4. **CLOSED (2026-09-11)**: `src/index/normalization.py` -- isolated
     module (imports `risk_calculator.py`'s plant/raster infrastructure,
     does not modify it) running the normality/skewness check (Fisher-
     Pearson skewness, decisive; Shapiro-Wilk reported as a diagnostic
     only) uniformly over `ws, heat, sv, iv, spei, precip, wind`
     (Wildfire absent by construction). Selection is now 3-way, not the
     draft's binary choice: author-confirmed extension (asked before
     implementing, not assumed) that `f(x) = -ln(1-x)` REPLACES the
     log-transform for skewed hazards everywhere, not only Extreme
     Heat -- log1p compresses a right-skewed variable's upper tail,
     `-ln(1-x)` expands it instead. Produces a recommendation
     (bounds + transform + structured origin table, Section 4.3) for
     Phase 3.3 to apply; `risk_calculator.FROZEN_BOUNDS`/`transform_term`
     are untouched and stay log1p-based until then. See
     `docs/DECISIONS.md`, "GEAR v3 Phase 2.4: Normalization module,
     neg-log transform confirmed to replace log1p (Methods Section 4.2
     closed)"; engineering detail in
     `docs/memory/05-decisoes-tecnicas.md` item 31. 23 new tests (pure
     function only), 236/236 passing outside the Phase-1-broken modules.
2.5. Correlation gate module, implemented as its own class per the
     standing modularity rule: spatial-harmonization step (upscale to
     coarser native resolution or aggregate to zonal/basin statistics)
     followed by the symmetric \|r\| < 0.80 test. Compute and report for
     (Extreme Precipitation vs Water Stress/Drought), and, report-only
     with no exclusion gate, (Water Stress vs Drought/sv/iv) per region.
     Note (2026-09-11): the (Wildfire vs Extreme Heat/Water Stress) pair
     is removed from this gate's scope -- Wildfire is deferred (Phase
     2.2, `docs/DECISIONS.md`). Extreme Precipitation is the only gated
     candidate remaining.

## Phase 3: Applicable hazard subsets and threshold tiers

Depends on Phase 2 outcomes (which candidate hazards passed the gate)
and Phase 0 items 2 and 4.

3.1. Implement the per-bucket H_b applicable-hazard tables (Methods
     Section 3), including the corrected Hydro set (+ Extreme
     Precipitation) and Solar set (+ Extreme Wind), reflecting Phase
     2.5 outcomes for the two candidate hazards.
3.2. Implement RiskBand_i,h threshold classification per hazard, per
     the Tier 1/Tier 3 table (Methods Section 4), using the Phase 0
     verified thresholds where Tier 1 applies, including the
     bucket-specific Extreme Wind thresholds (Wind vs. Solar may
     differ, Phase 0 item 4).
3.3. Apply the Phase 2.4 normalization module's transform decision to
     Extreme Heat specifically, resolving the tail-compression concern
     for heat days as part of the general normality-check procedure,
     not as a special case.

## Phase 4: PSAE aggregation

Depends on Phase 3 (needs finalized RiskBand per hazard).

4.1. Implement PSAE_i (Equation 2) per Methods Section 6, including the
     dual-mode classification (four-band for \|H_b\|>=3, compressed for
     Wind), with the raw fraction always output alongside the
     categorical label.
4.2. Enforce the Section 9 comparability rule in code: PSAE outputs
     carry their bucket identity as a non-strippable field, and any
     shared visualization/table function that would plot or rank PSAE
     across buckets on one scale raises an explicit error rather than
     silently producing a misleading comparison.

## Phase 5: Contextual validator layer

Independent of Phase 3/4, can run in parallel once Phase 1.4 (removal
of EventMultiplier from the core) is done.

5.1. Implement the two-class validator taxonomy (Methods Section 7):
     physical-occurrence validators (IBTrACS for cyclone/storm surge,
     FIRMS for wildfire ignition history, moved here from the hazard
     layer per Phase 2.2) and broad-impact validators (EM-DAT,
     redefined explicitly as long-range/societal-impact corroboration,
     not physical-occurrence confirmation).
5.2. Implement the three-state output (Corroborated / No Record / Not
     Applicable) per validator per asset, post-2000 window, scoped to
     each validator's physically applicable asset subset
     (coastal/cyclone-basin, high-slope terrain, etc., verified per
     hazard before implementation).
5.3. Confirm in code and in docs/memory that "No Record" from a
     broad-impact validator is never interpreted or labeled as "no
     hazard occurred"; the distinction from physical-occurrence
     validators is preserved in the output schema, not just in prose.

## Phase 6: Sensitivity and uncertainty

Depends on Phase 4 (PSAE cut points must exist to be perturbed) and
Phase 2.5 (correlation cutoff must exist to be perturbed).

6.1. Increase Monte Carlo N; determine and report convergence.
6.2. Implement Sobol/SALib global sensitivity indices restricted to
     continuous parameters only (Methods Section 8.1): FROZEN_BOUNDS
     percentile/transform-related parameters, age_factor decay rates.
6.3. Implement a separate scenario-discovery / one-at-a-time analysis
     for discrete/structural parameters (Methods Section 8.2): hazard
     inclusion/exclusion per bucket, PSAE cut points, correlation-gate
     cutoff. Report as a distinct analysis type, not folded into the
     Sobol output.
6.4. Carry forward the previously flagged open RNG-granularity question
     (per country vs. per country-scenario) for any remaining
     continuous parameter.

## Phase 7: Visualization and reporting updates

Depends on Phases 4 and 5 producing final data shapes.

7.1. Update or replace CCRS-labeled figures to reflect the PSAE/
     Risk_i,h split (per-hazard risk band maps remain primary; PSAE map
     becomes explicitly labeled secondary/screening, intra-technology
     only per Section 9, never on a shared cross-bucket color scale).
7.2. Add technology-differentiated map markers (shape by fuel-type
     bucket), addressing the advisor's request for per-technology
     visual distinction.
7.3. Add the validator overlay to relevant maps, with physical-
     occurrence and broad-impact validators visually distinguished, not
     merged into one marker type.
7.4. Produce the FROZEN_BOUNDS origin table (Section 4.3) and the
     threshold tier-provenance table as reusable figure/table assets
     for the article.
7.5. Implement the Risk_i,h intra-hazard comparison figures (Section 9)
     explicitly labeled by hazard, confirming no figure sums or
     visually blends Risk values across different hazards for the same
     asset.

## Phase 8: Documentation reconciliation

Do last, after code stabilizes.

8.1. Add the missing formal DECISIONS.md entry for SLR exclusion
     (currently only in ARCHITECTURE.md prose).
8.2. Add the missing DECISIONS.md entry closing the Monte Carlo
     implementation status (already implemented in code per the prior
     inventory, but undocumented in DECISIONS.md), resolving the
     previously flagged RNG-granularity question as part of this entry.
8.3. Full reconciliation pass: docs/ARCHITECTURE.md, docs/DECISIONS.md,
     analysis/climate_risk_score_spec.md, and docs/memory/ all
     consistent with the final code state, no remaining references to
     CCRS as a computed quantity anywhere, no remaining references to
     EventMultiplier as a score component, no remaining references to
     FIRMS as a hazard-normalization input.
8.4. Confirm no changelog language leaked into docs/ARCHITECTURE.md,
     code docstrings, or any article-facing output generated during
     Phases 1-7.

## Sequencing notes

Phase 0 blocks Phase 1 and Phase 3 fully. Phase 1 blocks Phase 4. Phase
2 is independent of Phase 1 and can start in parallel, but Phase 3
needs both Phase 1 and Phase 2 complete. Phase 5 only needs Phase 1.4,
not Phase 3/4, and can run in parallel with Phase 2-4. Phase 6 needs
Phase 4 and Phase 2.5. Phase 7 needs Phase 4 and 5. Phase 8 is always
last.

Minimum viable path to a first full pipeline run: Phase 0 -> Phase 1 ->
Phase 2 -> Phase 3 -> Phase 4 -> Phase 6 -> Phase 7 -> Phase 8, with
Phase 5 merged in whenever convenient before Phase 7.
