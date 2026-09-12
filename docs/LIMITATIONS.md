# GEAR — Declared Limitations (standing reference)

This file is the single consolidated index of every declared limitation,
Tier 3 downgrade, excluded hazard, or scenario-invariance decision closed
in this project. It does not replace `docs/DECISIONS.md` — each row here
is a pointer to the full entry there (context, alternatives investigated,
evidence). This file exists so a reader (author, reviewer, or a future
Claude Code session) can see the whole set of "what this project chose not
to do, and why" in one place, without reading the entire dated
`docs/DECISIONS.md` log end to end.

**Maintenance convention (binding, effective 2026-09-11):** any future
phase closure that introduces a new Tier 3 declaration, an excluded
hazard, a scenario-invariance decision, a pinned/provisional parameter, or
any other declared limitation **must add a dated row to this file in the
same task that closes it** — not as a separate deferred cleanup step. A
`docs/DECISIONS.md` entry alone is not sufficient; if the decision fits
the pattern of a limitation as described above, this file is updated in
the same sitting.

**Process convention (binding, effective 2026-09-12): partial closures
must be labeled as such, not rounded up to "closed."** A phase whose
completion depends on per-country (or otherwise per-subset) processed
data may only be marked "closed" without qualification if every subset
came back clean in the same run. If a closure is written while one or
more subsets are missing, still pending, or unverified, it must say so
explicitly in its own status line (e.g. "closed for Brazil only, Portugal/
India pending Phase X" — not "closed" followed by the gap buried in a
later paragraph). This was not a hypothetical risk: GEAR v3 Phase 2.5's
correlation gate was first run and reported against real data while
`extreme_precipitation_processor.py` had, in fact, never been executed
for Portugal or India (only Brazil had a processed raster on disk) — a
genuine per-country processing gap, not a data-unavailability or pipeline
defect, confirmed by checking that the same underlying `pr` input already
existed for all three countries and was already used successfully by
SPEI. The gap was caught before Phase 3 was approved to start only
because the closing entry stated the per-country scope explicitly rather
than asserting a blanket "closed." See `docs/DECISIONS.md`, "GEAR v3
Phase 2.5: correlation gate implemented and run" and its follow-up
closing entry once Portugal/India were reprocessed, for the full
incident.

Columns: **Limitation** (what was not done, or what is pinned/excluded) |
**Reason** (why, one line) | **Evidence tier** | **Alternative(s)
considered and rejected** | **Status** (Final = not expected to be
revisited without new data; Revisitable = explicitly open to a better
alternative if one appears) | **Reference** (pointer to the full
`docs/DECISIONS.md` entry).

---

## 2026-09-03 — Sea-level rise (SLR) excluded from the hazard set

| Field | Content |
|---|---|
| Limitation | SLR is not modeled as a hazard for any bucket or country. |
| Reason | No defensible empirical basis (per-technology coastal-flooding/storm-surge coefficients) exists for the land-based fleet studied. |
| Evidence tier | Tier: scope-boundary judgment, not a data-availability finding. |
| Alternatives considered and rejected | None formally investigated at the time; declared out of scope from the outset. |
| Status | Revisitable — "a natural extension once per-technology coefficients for coastal flooding and storm surge are available" (explicit, not closed against future work). |
| Reference | `docs/ARCHITECTURE.md` Section 10 ("What GEAR does not do"); carried forward unchanged into v3, `docs/rework/GEAR_v3_methodology_nature_format.md` Section 10. |

## 2026-09-04 — Per-bucket hazard weights (w_water / w_heat / w_drought): judgment call, not a calibration

| Field | Content |
|---|---|
| Limitation | The weights combining water, heat, and drought into `Hazard_i,s` per technology bucket (hydro/thermal/wind/solar) are an explicit author judgment call, not derived from a calibration or a published importance ratio. |
| Reason | No published water/heat/drought relative-importance ratio exists in the literature for any of these technologies. |
| Evidence tier | Tier 3 (author-declared, transparent, not literature-backed). |
| Alternatives considered and rejected | An AHP/pairwise calibration was considered and not pursued — no data basis to calibrate against. |
| Status | Revisitable — flagged as a Monte Carlo sensitivity-analysis candidate (spec item J); not re-derived as of this writing. |
| Reference | `docs/DECISIONS.md`, "SPEI drought term added to Hazard (spec item F closed)" (2026-09-04). |

## 2026-09-11 — GEM cooling-technology field absent: Thermal bucket treated as homogeneous

| Field | Content |
|---|---|
| Limitation | Once-through, recirculating, dry, and hybrid cooling systems are not distinguished within the Thermal bucket; all thermal plants share one water-stress sensitivity. |
| Reason | No cooling-technology field (under any name) exists in the GEM Global Integrated Power Tracker for Brazil, Portugal, or India. The closest field, `Technology`, records boiler/turbine cycle type, not condenser cooling system. |
| Evidence tier | Data-availability finding (primary source: raw GEM workbook), not a literature threshold. |
| Alternatives considered and rejected | None available — no alternative data source identified for cooling-technology classification at plant level. |
| Status | Final unless a future GEM release (or an alternative plant-level cooling-technology source) adds the field. Declared explicitly in the manuscript as likely overstating water-stress risk for whatever dry-cooled fraction exists within Thermal. |
| Reference | `docs/DECISIONS.md`, "GEM cooling-technology field: confirmed absent (v3 Phase 0.1)" and "GEAR v3 Phase 1.3: Thermal bucket implemented as homogeneous (no cooling-technology split)". |

## 2026-09-11 — GEM retrofit/repowering field absent

| Field | Content |
|---|---|
| Limitation | No per-plant overhaul, retrofit, or repowering date is available; `age_factor`'s coal overhaul cycle (5-year cycle, 70% recovery) is an assumed modelling premise, not derived from a real overhaul-history source. |
| Reason | Re-inspection of the GEM snapshot found no "retrofit"/"repower"/"refurbish" column; the adjacent "Conversion" field family records fuel-conversion events, not overhaul dates, and is effectively empty (0 non-null, two immaterial exceptions in Brazil). |
| Evidence tier | Data-availability finding (primary source: raw GEM workbook). |
| Alternatives considered and rejected | None available at plant level for any of the three countries. |
| Status | Revisitable — "revisit if a real overhaul-history source appears" (explicit in the original 2026-09-04 `age_factor` entry, re-confirmed unchanged 2026-09-11). |
| Reference | `docs/DECISIONS.md`, "GEM retrofit/repowering field: re-confirmed empty (v3 Phase 0.3)"; original overhaul-cycle assumption in "age_factor: >=1 multiplier ... with corrected coal/hydro/wind retention curves (final)" (2026-09-04). |

## 2026-09-11 — Extreme Precipitation: HAZUS-MH absolute threshold rejected, Tier 1 downgraded to Tier 3

| Field | Content |
|---|---|
| Limitation | Extreme Precipitation uses a sample-relative percentile cutoff (P95 of wet-day `pr`, ETCCDI convention), not a cited absolute inundation-depth threshold. |
| Reason | The drafted HAZUS-MH inundation-depth values (0.2/0.5/1.5 m) do not exist in the primary FEMA Hazus Flood Model Technical Manual; HAZUS-MH uses continuous depth-damage curves per building-occupancy type, not the discrete class thresholds the draft assumed. |
| Evidence tier | Tier 3 (percentile-cutoff, ETCCDI R95p convention, Zhang et al. 2011) — explicitly not a cited absolute damage threshold. |
| Alternatives considered and rejected | HAZUS-MH absolute inundation-depth classes — rejected, the specific values do not exist in the primary source. |
| Status | Final at this tier; would only be revisited if a defensible absolute cross-national threshold is identified. |
| Reference | `docs/DECISIONS.md`, "Extreme Precipitation downgraded Tier 1 -> Tier 3 (v3 Phase 0.2)" and "GEAR v3 Phase 2.1: Extreme Precipitation processor (Tier 3, percentile-cutoff)". |

## 2026-09-11 — Solar Extreme Wind: no Tier 1 structural threshold exists; ERA5 gust percentile is final

| Field | Content |
|---|---|
| Limitation | The Solar bucket's Extreme Wind hazard uses ERA5 gust percentiles (P75/P90/P95/P99) as Tier 3, final — not a placeholder pending a Tier 1 structural wind-uplift threshold. |
| Reason | No single defensible Tier 1 value exists for solar-tracker structural wind uplift: ASCE 7's design wind speed is inherently site-specific by construction, and manufacturer survival ratings vary by product generation (~51-60+ m/s observed range from a single manufacturer alone). |
| Evidence tier | Tier 3 (percentile-based, not a structural engineering constant). |
| Alternatives considered and rejected | A shared IEC-style cut-out constant (as used for the Wind bucket's turbine cut-out speed, ~25 m/s) — rejected, no equivalent universal value exists for tracker structural survival. |
| Status | Final, not contingency — explicitly stated as not pending a future Tier 1 value. |
| Reference | `docs/DECISIONS.md`, "Solar Extreme Wind: ERA5 gust percentile is final, not contingency (v3 Phase 0.4)". |

## 2026-09-11 — Wildfire (FWI/EFFIS) deferred, not implemented

| Field | Content |
|---|---|
| Limitation | Wildfire is not part of the v3 hazard set; no FWI/EFFIS layer is produced for any bucket or country. |
| Reason | Daily near-surface relative humidity, required for a self-computed Canadian FWI System, is absent from the CDS `projections-cmip6` daily catalogue for both configured GCMs under any scenario; the one alternative global source checked (ETH Zurich FWI-CMIP6, Quilcaille et al. 2023) has zero GFDL-ESM4 coverage and provides only annual, reference-period-relative indicators, not daily FWI or EFFIS-compatible absolute classes. |
| Evidence tier | Tier: data-availability finding (CDS catalogue query) plus primary-source archive inspection (ETH Zurich dataset ZIP directory) for the alternative. |
| Alternatives considered and rejected | Specific-humidity + sea-level-pressure fallback to derive RH — rejected, incomplete model/scenario coverage; ETH Zurich FWI-CMIP6 — rejected, no GFDL-ESM4 coverage and structurally incompatible (annual/percentile-relative, not daily/absolute). |
| Status | Same treatment as the SLR exclusion — deferred, future work if a data source appears; not reopened as a standing TODO in the interim. |
| Reference | `docs/DECISIONS.md`, "GEAR v3 Phase 2.2: Wildfire deferred (data availability)". |

## 2026-09-11 — Extreme Wind: ERA5 historical baseline, scenario-invariant by design

| Field | Content |
|---|---|
| Limitation | Extreme Wind is the one hazard sourced from ERA5 historical reanalysis (1991-2020) rather than a CMIP6 SSP projection; its `Risk_i,h`/RiskBand/PSAE contribution is identical across all three SSP columns. |
| Reason | No CMIP6 daily-maximum or gust wind variable exists on the CDS catalogue for either configured GCM, and the one daily variable that does exist (`sfcWind`, daily mean) is not the same physical quantity as the ERA5 instantaneous gust this hazard's threshold design uses — converting between them requires an unvalidated, condition-dependent gust-factor parameterization. IPCC AR6 WGI Chapter 11 independently attributes "low confidence" to projected severe-wind changes for the same resolution/parametrization reasons. |
| Evidence tier | Tier: primary catalogue investigation (Tier 1/citable for the gap itself) plus corroborating Tier 2 literature (Shen et al. 2022; IPCC AR6 WGI Ch. 11) on GCM wind-extreme underestimation. |
| Alternatives considered and rejected | A CMIP6-`sfcWind`-to-ERA5-gust conversion via an empirical gust factor — rejected as manufactured precision, not implemented. |
| Status | **Final — a settled epistemic position, not a placeholder.** Explicitly not reopened as a "TODO: find better wind data" item. Even a future CMIP6 daily-maximum/gust product appearing on the catalogue would resolve only one of the two independent rejection grounds and would not by itself reopen this. |
| Reference | `docs/DECISIONS.md`, "GEAR v3 Phase 2.3 follow-up: ERA5 temporal asymmetry retained (CMIP6 substitution investigated and rejected)" and "GEAR v3 Extreme Wind: reframed as scenario-invariant structural exposure (not a data gap)". |

## 2026-09-11 — GCM pair (GFDL-ESM4, MIROC6): operational selection, not an ECS-based bounding design

| Field | Content |
|---|---|
| Limitation | The two-GCM pair is not a climate-sensitivity-bounding design: GFDL-ESM4 (ECS ~2.6-2.7 K) and MIROC6 (ECS 2.6 K) sit next to each other near the low end of the CMIP6 ECS range (~1.8-5.6 K) and do not span it. GFDL-ESM4's original selection as the sole/primary model predates this project's decision record entirely and has no recorded justification. |
| Reason | MIROC6 was chosen operationally (V4): of four CDS-catalogued candidates, two were excluded for missing scenario coverage or realization-variant mismatch, and MIROC6 was picked over the remaining fallback for a qualitative "structural divergence" judgment, not a cited sensitivity metric. |
| Evidence tier | Tier 1/citable for ECS values (Dunne et al. 2020; Tatebe et al. 2019; Zelinka et al. 2020; Meehl et al. 2020); Tier: none for GFDL-ESM4's original selection (stated as inherited operational default, not invented). |
| Alternatives considered and rejected | Among catalogue/variant-compatible candidates, IPSL-CM6A-LR and CNRM-CM6-1 were excluded on availability/variant grounds; MPI-ESM1-2-LR was kept only as an unused fallback. |
| Status | Final as a documentation/framing matter — does not reopen the V4 pair choice and does not authorize adding, removing, or replacing either model. |
| Reference | `docs/DECISIONS.md`, "GCM pair (GFDL-ESM4, MIROC6) selection rationale -- retroactive documentation, not a new methodological choice"; `docs/rework/GEAR_v3_methodology_nature_format.md` Section 2.1. |

## 2026-09-11 — Gas/oil-gas `age_factor`: pinned neutral, confirmed final after a bounded literature search

| Field | Content |
|---|---|
| Limitation | Gas and oil-gas thermal plants receive `age_factor = 1.0` (neutral, no age-driven adjustment) — unlike coal (sawtooth overhaul-cycle decay), hydro, wind, and solar, which all have literature-backed retention curves. |
| Reason | A bounded literature search (this entry) found no citable Tier 1/Tier 2 monotonic age-degradation curve for gas/combined-cycle turbines analogous to coal's Kim & Moon (2012)/Sagaf (2020). Engineering degradation literature reports loss in fired-operating-hours terms (dominated by recoverable compressor fouling, resolved by routine washing), not calendar-age terms, and is confounded by dispatch pattern, wash schedule, and maintenance regime — none of which this project has per-plant data for. Fleet-level longitudinal evidence (Grubert, 2020, *IOPSciNotes*, "Same-plant trends in capacity factor and heat rate for US power plants, 2001-2018") found the *opposite* sign at the fleet level: US gas plants ran more, and more efficiently, as they aged (in contrast to coal, which declined), attributable to retrofits, dispatch shifts, and vintage effects rather than a pure age-degradation mechanism — meaning even the directional sign of a naive age curve for gas would be wrong if taken from this evidence at face value. |
| Evidence tier | Tier: bounded-search finding — no source of the required kind exists; Grubert (2020) is Tier 2/citable for the fleet-level *contrast* with coal, but is explicitly not usable as a per-plant retention curve (no isolable %/year age effect, confounded with vintage/retrofit/dispatch). |
| Alternatives considered and rejected | Turbomachinery degradation literature (fired-hours-based, largely recoverable) — rejected, wrong unit of exposure (hours vs. calendar age) and this project has no per-plant operating-hours or wash-schedule data; Grubert (2020) fleet CAGR — rejected as a per-plant curve, since it reflects fleet composition/retrofit trends, not an isolated aging mechanism. |
| Status | **Final, not still-pending.** This closes the "provisional/open" status carried in `src/index/age_factor.py` and prior `docs/DECISIONS.md` entries since 2026-09-04. Gas/oil-gas remains `age_factor = 1.0` by declared design choice (absence of evidence, not evidence of no effect), not as an open item awaiting a source that will eventually appear. Revisit only if a new, calendar-age-indexed, per-plant-comparable source is published. |
| Reference | `docs/DECISIONS.md`, "Gas/oil-gas age_factor: pinned-neutral treatment confirmed final after a bounded literature search" (2026-09-11); prior provisional status in "age_factor: >=1 multiplier via `2 - retention(age)`, with corrected coal/hydro/wind retention curves (final)" (2026-09-04). `src/index/age_factor.py`'s "PROVISIONAL" code comment is now stale and is a candidate for a small follow-up edit — not made here (documentation-only task). |
