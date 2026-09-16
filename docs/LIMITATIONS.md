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

**Coordination convention (binding, effective 2026-09-12): a phase's
primary deliverable file is written by that phase's session only.** When
two phases run in parallel Claude Code sessions and one depends on the
other's output (e.g. Phase 3.2's `RiskBand_{i,h}` classification depends on
Phase 3.1's per-bucket `H_b` table), the dependent session must not write a
placeholder or draft version of the file it is waiting on, even to unblock
its own progress — doing so risks silently overwriting the upstream
session's real, in-progress, or already-author-confirmed work. A session
that hits a missing prerequisite file must stop and report the blocker
rather than create one. This was not a hypothetical risk: a Phase 3.2
session wrote its own version of `src/index/hazard_scope.py` (Phase 3.1's
deliverable) to unblock itself, overwriting the Phase 3.1 session's version
and reintroducing a Thermal sv/iv inclusion the author had already
explicitly rejected in favor of Hydro-only. The conflict was caught and
reconciled before either phase proceeded further only because the Phase
3.1 session diffed the file against its own last-known state and noticed
the mismatch. See `docs/DECISIONS.md`, "GEAR v3 Phase 3.1: hazard_scope.py
reconciliation after parallel-session conflict" for the full incident.

**Coordination convention (binding, effective 2026-09-12): a background
process from an earlier task must be confirmed stopped before its code is
changed or a fresh run of the same acquisition starts.** Same failure
family as the convention above -- coordination between sessions/processes,
not a single-session code bug -- but the other direction: instead of two
sessions racing on a file, one session's own previously-launched background
process kept running, on the OLD in-memory code, after a *later* session
had already found and fixed a bug in that same code on disk. A long-running
acquisition process does not reload its module code mid-run; fixing a
source file on disk has no effect on a process that imported it minutes or
hours earlier. Before editing a file a known background process is
actively using, or before starting a new run of the same acquisition,
confirm that process is actually stopped (not just "the file is fixed
now") -- checking only the file is not enough. This was not a hypothetical
risk: the ERA5 wind gust download launched earlier the same session
(GEAR v3 Phase 3.2 follow-up, "Extreme Wind data-gap investigation") kept
running, unnoticed, straight through the disk-full incident, the disk
cleanup, and the start of the GRIB-mislabeling bug fix -- still executing
`era5_wind_downloader.py`'s original, buggy, pre-fix code the whole time.
It was still actively downloading Portugal, and had already produced 3
more mislabeled/duplicated years there (the same defect the fix addressed
for Brazil), by the time it was noticed via a stray process still visible
in `ps aux` and stopped. Caught only because the per-year verification
step for Brazil prompted a fresh process check, not because anything
about the stale process itself raised an alarm. See `docs/DECISIONS.md`,
"GEAR v3 Phase 3.2 follow-up: stale background download process ran on
pre-fix code, Portugal partial re-corruption caught and cleaned" for the
full incident.

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

## 2026-09-12 — Extreme Wind: ERA5 gust input not yet downloaded for any country (acquisition status, open)

| Field | Content |
|---|---|
| Limitation | `data/raw/climate/` has no `era5_wind/` directory for Brazil, Portugal, or India — the hourly ERA5 `instantaneous_10m_wind_gust` download (`era5_wind_downloader.py`, Phase 2.3) has not been run for any country. `extreme_wind_processor.py` is code-complete and unit-tested (14 tests, monkeypatched), but has never produced a real processed raster for any country. Phase 3.2's real-data run correctly reported `insufficient_data` for both Extreme Wind rows (Wind and Solar buckets) in every country as a direct consequence, not a bug. |
| Reason | This was never silently assumed complete: the original Phase 2.3 closing entry (`docs/memory/05-decisoes-tecnicas.md` item 30) already logged "1 expected skip (real ERA5 data absent)" and its status line already read "Ativa" (active), not "closed" — the phase never claimed the acquisition step was done, only that the processor code was. This entry makes that already-honest scope explicit in `LIMITATIONS.md` for the first time, prompted by Phase 3.2's real-data run surfacing the same gap the Phase 2.5 correlation-gate incident already established a naming convention for. |
| Evidence tier | Direct filesystem check (`data/raw/climate/` contents), not inferred. |
| Alternatives considered and rejected | None — no substitution or workaround was attempted; per standing instruction, a missing-data finding is reported factually and left for the author to authorize the acquisition (90 CDS API requests: 30 years x 3 countries), not silently worked around. |
| Status | **In progress, author-authorized 2026-09-12.** Two blockers found and fixed en route: (1) a data-integrity bug silently mislabeled 18 already-downloaded Brazil years as NetCDF when they were actually GRIB — fixed and all 18 recovered without re-downloading (`docs/DECISIONS.md`, "ERA5 GRIB mislabeling bug fixed"); (2) the original bulk-download shape kept every year's raw file on disk at once, which is what caused the disk-full incident — restructured to download/reduce/delete one year at a time (`docs/DECISIONS.md`, "ERA5 download disk-footprint restructuring"). The download for the remaining years (Brazil 2009-2020, all of Portugal, all of India) was launched under the fixed, disk-safe pipeline; see the follow-up status entry for completion. |
| Reference | `docs/DECISIONS.md`, "GEAR v3 Phase 3.2 follow-up: Extreme Wind data-gap investigation", "...GRIB mislabeling bug fixed, 18 Brazil years recovered", "...ERA5 download disk-footprint restructuring"; `docs/memory/05-decisoes-tecnicas.md` items 30, 37, 38. Superseded by the 2026-09-14 follow-up entry below for current acquisition status. |

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

## 2026-09-13 — Extreme Wind: no Risk_i,h (Equation 1) yet, not only a RiskBand gap

| Field | Content |
|---|---|
| Limitation | `src/index/risk_calculator.py`'s `HAZARD_TERMS`/`FROZEN_BOUNDS` do not include `wind` — no plant/bucket/country has a continuous `Risk_i,h` value for Extreme Wind. This is a narrower, more precise restatement of the 2026-09-12 acquisition-status entry above: that entry described the RiskBand/classification consequence (`risk_bands.py` reports `insufficient_data`); this entry names the Equation 1 consequence explicitly, since a manuscript-preparation check confirmed the two are not the same claim and both needed to be on record. `precip`, which had the identical prior gap (closed processor and RiskBand, no Risk_i,h), was wired in during the same task that surfaced this — see reference below. |
| Reason | Same root cause as the 2026-09-12 entry: ERA5 gust acquisition is incomplete (Brazil 30/30 years cached, Portugal 12/30, India 2/30), and no country has a processed `extreme_wind_gust_raw_*.tif`. `risk_calculator.py` deliberately does not adopt `risk_bands.py`'s missing-raster-tolerant sampling for this term: a continuous `Risk_i,h` value, unlike a classification label, should not silently exist as a function of zero real observations. |
| Evidence tier | Direct filesystem check (`data/processed/climate/`, `data/raw/climate/era5_wind/{country}/`), not inferred. |
| Alternatives considered and rejected | Wiring `wind` in now with the same NaN-tolerant sampling `risk_bands.py` uses — rejected: would produce a published `Risk_i,h` number backed by zero real data for every plant, a materially different (and worse) failure mode than a classification label correctly reporting "insufficient data". |
| Status | Open, blocked on the same author-authorized ERA5 acquisition as the 2026-09-12 entry. `hazard_scope.PENDING_RISK_I_H_HAZARDS["wind"]` is now the code-level record of this gap (not only this file) — remove that entry in the same change that adds `wind` to `HAZARD_TERMS`, never separately. |
| Reference | `docs/DECISIONS.md`, "GEAR v3 Risk_i,h integration gap: precip wired in, wind still blocked on ERA5 acquisition" (2026-09-13); `docs/LIMITATIONS.md`, "2026-09-12 — Extreme Wind: ERA5 gust input not yet downloaded for any country" (the acquisition-status entry this one narrows, not replaces); `src/index/hazard_scope.py`, `PENDING_RISK_I_H_HAZARDS`. |

## 2026-09-14 — Extreme Wind: ERA5 gust acquisition complete for all three countries (Risk_i,h gap unchanged, still open)

| Field | Content |
|---|---|
| Limitation | Narrow, per-country-scope update to the two entries above, per the binding partial-closure convention: the ERA5 gust acquisition itself is now complete — Brazil 30/30, Portugal 30/30, India 30/30 years cached (`data/raw/climate/era5_wind/{country}/{year}/annual_max.nc`), verified by direct filesystem count and a file-integrity pass (all 90 files open cleanly, no all-NaN grids, no out-of-range values, per-country grid shape consistent, inter-annual means physically plausible). This closes the acquisition blocker only — it does not close the 2026-09-13 Risk_i,h integration gap, which depends on a separate, not-yet-run step. |
| Reason | Portugal (was 12/30) and India (was 2/30) finished downloading across this and the prior session, using the disk-safe, one-year-at-a-time pipeline already fixed in the 2026-09-12 entries. No new acquisition bug was found; two operational incidents were handled (mixing two concurrent download scripts briefly exceeded the CDS per-account queue limit and caused transient job rejections for a few India years, later retried successfully; a machine suspend left the download process hung post-resume, detected via a stalled log and a stopped-progress check, and cleanly restarted — it resumed only the still-missing years, no re-download of completed ones). |
| Evidence tier | Direct filesystem check (`data/raw/climate/era5_wind/{country}/`, 90/90 files) plus a scripted integrity pass (`xarray.open_dataarray` on all 90 files, NaN-fraction/range/shape checks, inter-annual mean sanity check). |
| Alternatives considered and rejected | None — straightforward completion of the already-authorized acquisition, no new decision made. |
| Status | **Acquisition closed, for all three countries.** `compute_mean_annual_max_gust()` (the reduction from 30 per-year rasters to one processed `extreme_wind_gust_raw_{country}_1km.tif` per country) has not yet been run for any country — this remains the blocker for the 2026-09-13 Risk_i,h integration gap, which stays **open, unchanged** by this entry. |
| Reference | `docs/DECISIONS.md`, "GEAR v3 Risk_i,h integration gap: precip wired in, wind still blocked on ERA5 acquisition" (2026-09-13, the entry whose blocker this closes); `docs/LIMITATIONS.md`, "2026-09-12 — Extreme Wind: ERA5 gust input not yet downloaded for any country" and "2026-09-13 — Extreme Wind: no Risk_i,h (Equation 1) yet, not only a RiskBand gap" (both narrowed by this entry, not replaced — the Risk_i,h gap they describe is still open); `src/index/hazard_scope.py`, `PENDING_RISK_I_H_HAZARDS["wind"]` (counts updated to match). |

## 2026-09-15 — IBTrACS physical-occurrence validator: fixed-radius proxy, not real per-storm wind-field data

| Field | Content |
|---|---|
| Limitation | `contextual_validators.compute_physical_occurrence_validation`'s `Corroborated`/`No Record` state for the `wind` hazard term is decided by a fixed 100 km great-circle distance from the plant to any qualifying track point (`STORM_TRACK_RADIUS_KM`), not by each storm's own recorded wind-field extent. A track point with no wind speed reported by either `WMO_WIND` or `USA_WIND` cannot be evaluated against the gale-force floor (`IBTRACS_MIN_WIND_KT = 34`) and is silently excluded from every match — the same "excluded, not counted as absence of the hazard" posture EM-DAT's own coverage gap already carries in this module. Basin CSV files are NOAA's "final" product, updated roughly twice a year — a storm from the last few months before acquisition may be under-revised or briefly absent versus the near-real-time product. |
| Reason | Per-quadrant wind-radius fields (`USA_R34`/`REUNION_R34`/etc.) exist in IBTrACS but have large, non-random coverage gaps across agencies and decades (worst for older and non-US-basin storms) — using them directly would replace one honest proxy with a differently-gapped one, not with ground truth. A fixed radius at the conservative (small) end of published mean 34-kt wind-radius climatology (~150-250 km typical) was chosen instead so this validator under-claims rather than over-claims corroboration; see `src/index/contextual_validators.py`, `STORM_TRACK_RADIUS_KM`'s own comment for the full rationale. Real-data verification (this task) found the radius produces physically sensible results at both extremes: Brazil's only corroborating storm across the full post-2000 South Atlantic record is Hurricane Catarina (2004), the basin's one documented case; Portugal's corroborations trace to five identifiable, real storms (Joaquin 2015, Leslie 2018, Michael 2018, Alpha 2020, Gabrielle 2025) plausibly consistent with known Iberian storm-landfall/near-miss history. |
| Evidence tier | Tier: methodological-proxy judgment (radius choice) grounded in general TC climatology, not a per-storm citable value; the near-null Brazil / real-density India / thin-but-attributable Portugal outcomes are direct verification against real IBTrACS + plant data, not assumed. |
| Alternatives considered and rejected | Per-quadrant R34 polygon matching — rejected, coverage too sparse and non-random to be a defensible upgrade over a fixed radius; a larger (e.g. 200+ km) radius — rejected in favor of the conservative end of the climatology range, to keep the validator's stated Corroborated claim closer to "gale-force winds plausibly reached this asset" than to a looser "a storm passed somewhere in the region." |
| Status | Revisitable — would be reopened by a future author decision to build a per-quadrant wind-field match instead of a fixed radius, or to re-run acquisition nearer to a reporting date for maximal basin-file currency. Not a blocking gap for the current Phase 5 partial closure. |
| Reference | `docs/DECISIONS.md`, "GEAR v3 Phase 5: physical-occurrence validator (IBTrACS)"; `src/index/contextual_validators.py`, `STORM_TRACK_RADIUS_KM`/`IBTRACS_MIN_WIND_KT`/`compute_physical_occurrence_validation`; `src/downloaders/ibtracs_downloader.py`. |

## 2026-09-15 — Phase 5 hazard-mapping scope: landslide/lightning excluded, Storm/Flood mapping still open (not complete)

| Field | Content |
|---|---|
| Limitation | Phase 5's contextual-validator layer does not cover the full EM-DAT disaster-type spectrum. (1) **Landslide and lightning are excluded entirely** — no physical-occurrence source for either is acquired, and neither hazard is investigated for a disaster-type/hazard-term mapping. (2) Of the hazards that are covered, the disaster-type -> hazard-term mapping is itself incomplete: `Flood` maps to `ws` (Water Stress), not `precip` (Extreme Precipitation); `Storm` has **no** EM-DAT broad-impact mapping at all (excluded from `EMDAT_DISASTER_TYPE_TO_TERM`); the only Storm-related coverage is the `wind` term's physical-occurrence corroboration via IBTrACS track-radius matching, which is a separate mechanism, not a disaster-type mapping. Phase 5 is therefore **partial, not functionally complete**, for both the physical-occurrence class and the broad-impact class. |
| Reason | Landslide/lightning: same structural gate as the Wildfire/FIRMS exclusion (below in this file, and `docs/DECISIONS.md`, "GEAR v3 Phase 5: physical-occurrence validator (IBTrACS)") — neither is a modeled hazard term in `hazard_scope.APPLICABLE_HAZARDS`, so a physical-occurrence validator would have nothing to attach to; adding either requires an `ARCHITECTURE.md`-level hazard-scope decision, not a Phase 5 data-acquisition step, and neither has been investigated even at that level. Flood/Storm mapping: `Flood -> ws` and the absence of a `Storm` entry are inherited verbatim (author-approved 2026-09-04) from a pre-v3 module built before `precip` and `wind` existed as hazard terms; extending the mapping to `Flood -> precip` and/or `Storm -> wind` was identified as a plausible improvement but is an unresolved methodology judgment call (Flood also has non-precipitation causes such as dam failure; Storm damage can also arise from associated precipitation, not only wind) — not decided, not silently extended, by any task to date. |
| Evidence tier | Landslide/lightning: scope-boundary judgment (structural, not data-availability). Flood/Storm mapping: methodology judgment call, explicitly flagged as open, not a data-availability finding. |
| Alternatives considered and rejected | None formally investigated for landslide/lightning (open item, not evaluated). For Flood/Storm, no alternative mapping has been adopted or rejected — the question itself remains open. |
| Status | **Open on both counts**, not deferred-and-forgotten: landslide/lightning exclusion is revisitable only via an `ARCHITECTURE.md` hazard-scope decision; the Flood/Storm mapping question is revisitable via an author methodology decision, tracked as a standing open item. Neither blocks Phase 5's existing partial closure (EM-DAT broad-impact for `heat`/`spei`/`ws`, IBTrACS physical-occurrence for `wind`), but the manuscript must state Phase 5 as **partial** against the full EM-DAT disaster-type spectrum, not complete. |
| Reference | `docs/DECISIONS.md`, "GEAR v3 Phase 5: contextual validator layer (broad-impact only, PARTIAL)" (2026-09-14); "GEAR v3 Phase 5: physical-occurrence validator (IBTrACS)" (2026-09-15, Storm/landslide/lightning scoping); `src/index/contextual_validators.py`, `EMDAT_DISASTER_TYPE_TO_TERM` module docstring ("inherited UNCHANGED, an open item flagged"). Superseded for the Flood/Storm mapping question by "Hazard Mapping Proxies (Phase 5)" below (2026-09-15, author decision) — landslide/lightning exclusion is unchanged and still open. |

## 2026-09-15 — Hazard Mapping Proxies (Phase 5): Flood -> precip, Storm -> wind (author decision)

| Field | Content |
|---|---|
| Limitation | The EM-DAT broad-impact validator's disaster-type -> hazard-term mapping (`contextual_validators.EMDAT_DISASTER_TYPE_TO_TERM`) now assigns `Flood -> precip` (previously `Flood -> ws`) and adds `Storm -> wind` (previously unmapped, `Not Applicable` for every row). Both are proxy assumptions, not exact disaster-cause matches: **Flood** — using precipitation as the flood proxy excludes non-meteorological flood causes (e.g. dam failure, rapid snowmelt) from corroboration; an EM-DAT `Flood` event caused by one of those excluded mechanisms will never be matched to a `precip`-driven `Risk_i,h` signal, regardless of geocoding. **Storm** — using wind as the storm proxy consolidates data volume onto a single, real hazard term (`wind`, Extreme Wind), but carries an inherent methodological noise source: EM-DAT's own `Storm` category does not separate infrastructure damage caused by wind gusts from damage caused by concurrent flooding in the same event, so a `Storm -> wind` corroboration may in fact reflect flood damage misattributed to the wind term. |
| Reason | Author decision (2026-09-15), replacing the CCRS-era `Flood -> ws` placeholder (an already-acknowledged poor match — water STRESS, not excess water — kept only because `precip`/`wind` did not exist as hazard terms when the original mapping was approved, 2026-09-04). `precip` (Extreme Precipitation) and `wind` (Extreme Wind) are now real, computable hazard terms, making a direct proxy assignment possible instead of the prior stopgap. |
| Evidence tier | Tier 3 (author-declared proxy assumption) — not a validated one-to-one disaster-cause mapping; EM-DAT's `Disaster Type` field does not itself distinguish sub-causes within `Flood` or `Storm`, so no finer-grained source exists to validate against at this granularity. |
| Alternatives considered and rejected | Leaving `Flood -> ws` unchanged — rejected as a strictly worse proxy (water stress is not excess water, an acknowledged mismatch already on record). Leaving `Storm` unmapped — rejected now that `wind` exists as a real hazard term with no EM-DAT broad-impact coverage. A sub-cause-disaggregated mapping (e.g. splitting `Storm` into wind-dominant vs. flood-dominant events) — not pursued, EM-DAT's own schema does not carry that distinction. |
| Status | Active. Revisitable if EM-DAT (or a supplementary source) adds sub-cause detail for `Flood`/`Storm`, or if the author identifies a better proxy. Not blocking Phase 5's existing partial-closure status — see the "Phase 5 hazard-mapping scope" entry above, which remains partial for landslide/lightning regardless of this mapping update. |
| Reference | `src/index/contextual_validators.py`, `EMDAT_DISASTER_TYPE_TO_TERM` (module docstring and inline comments, 2026-09-15 author-confirmed extension); `docs/DECISIONS.md`, "GEAR v3 Phase 5: contextual validator layer (broad-impact only, PARTIAL)" (2026-09-14, original open item) and the "Phase 5 hazard-mapping scope" LIMITATIONS.md entry above (landslide/lightning, unaffected by this change). |

## 2026-09-16 — Legacy CCRS visualization/sensitivity layer removed (`src/index/monte_carlo.py`, `src/visualization/{charts,tables,data,maps}.py`, `analysis/ccrs_capacity_by_score_band.py`)

| Field | Content |
|---|---|
| Limitation | The pre-v3 CCRS visualization and Monte Carlo sensitivity layer is deleted, not left broken in place: `src/index/monte_carlo.py`, `src/visualization/charts.py`, `src/visualization/tables.py`, `src/visualization/data.py`, `src/visualization/maps.py`, `analysis/ccrs_capacity_by_score_band.py`, and their dedicated test files `tests/test_monte_carlo.py`/`tests/test_visualization.py`. None of these figures/tables are available from this code going forward. |
| Reason | `docs/DECISIONS.md` [2026-09-11] GEAR v3 Phase 1 deleted `src/index/ccrs_calculator.py`/`ccrs_report.py` and left these seven callers importing the now-deleted symbols, deliberately, rather than inventing v3-era methodology ahead of its own phase. A verification pass (2026-09-16) confirmed none of them is reachable from `src/reporting/results_draft/` (the current production pipeline) or from any active `analysis/*.py` script; every one of `maps.py`'s plotting functions operates on a combined per-plant CCRS score (`vdata.load_ccrs_final()`) that has no v3 equivalent (`Risk_i,h` is never combined across hazards, Methods Section 1); `monte_carlo.py`'s bucket-weight perturbation has no v3 equivalent either (no `BUCKET_WEIGHTS` concept in `risk_calculator.py`). `tests/test_monte_carlo.py`/`test_visualization.py` were already CCRS-era test suites (both import `ccrs_calculator` directly) and have not been collectible since the Phase 1 deletion. |
| Evidence tier | Engineering/architecture decision executing a methodology closure already recorded in `docs/DECISIONS.md`; no new empirical threshold introduced. |
| Alternatives considered and rejected | Mechanical import rename (à la `age_factor.py`/`event_multiplier.py`) — rejected: `BUCKET_WEIGHTS`, `ccrs_report.assemble_ccrs`/`attach_risk_bands`/`compute_water_band_shares`/`compute_heat_band_shares`/`build_summary`/`band_capacity_shares`/`compute_ccrs`, and the combined per-plant CCRS score have no v3 successor to rename onto without inventing the still-open Phase 3-7 methodology. Leaving the files in place, broken — rejected once confirmed they are unreachable from the production pipeline and their only test coverage was itself already non-collectible CCRS-era code; keeping unreachable, non-importable modules in the tree was assessed as dead weight, not a live "left broken pending a decision" state. |
| Status | Final for the deleted layer itself (not expected to be resurrected in this form). Revisitable only if a future phase decides to rebuild v3-native visualizations reusing this code's plotting logic as a reference — `src/reporting/results_draft/common.py` already independently reimplements the map-drawing helpers (`docs/_audit/2026-09-15_phase7_legacy_maps_audit.md` Section 2) rather than importing the deleted `_common.py`-adjacent code, so no future work is currently blocked on this removal. |
| Reference | `docs/DECISIONS.md` [2026-09-11] "GEAR v3 Phase 1: Risk_i,h replaces the CCRS core (Equation 1)"; `src/index/general_mc.py` and `docs/DECISIONS.md` [2026-09-15] "GEAR v3 Phase 6 closure" (the actual functional successor to `monte_carlo.py`'s sensitivity role, `data/outputs/tables/phase6_general_mc_convergence.json`); `src/reporting/results_draft/` (items 01-16 + `run_all.py`, generated 2026-09-16, the functional successor to the visualization layer); `src/main.py` (kept, not migrated, marked with an in-file warning pointing to `results_draft/run_all.py`) — see the dedicated entry below for `main.py`'s own scope. |

## 2026-09-16 — `src/index/sensitivity_recompute.py` (Phase 6): recomputation infrastructure, not a sensitivity result

| Field | Content |
|---|---|
| Limitation | `sensitivity_recompute.py` implements only the raster-caching / partial-recomputation optimization `PHASE6_DESIGN.md` Section 4.2 proposed (one-time expensive raster-sampling precompute, held in memory, reused across cheap per-draw `age_factor`/RiskBand-percentile recomputation). It does not itself run Sobol, sample from SALib, or produce any sensitivity index, ranking, or convergence statistic. It must not be cited as, or mistaken for, the project's sensitivity analysis. |
| Reason | The module's own docstring states this explicitly: it resolves none of Phase 6's three open items (RNG granularity, RiskBand percentile-cut Sobol-dimension grouping, `psae_complete=False` treatment under a sensitivity statistic) and exists only to make a per-draw evaluation cheap enough (~29.7s/draw naive, ~79 days projected at `N_0=16000`, `D=6` was the measured problem) for a driver built on top of it to be tractable at all. The actual sensitivity analyses are separate, later modules: `sobol_sensitivity.py` (Phase 6.2, SALib Sobol indices over the reconciled D=13 continuous-parameter problem) and `scenario_discovery.py` (Phase 6.3, one-at-a-time discrete/structural-parameter analysis, deliberately kept separate from Sobol and never folded together per an explicit author task requirement). |
| Evidence tier | Direct code/docstring inspection of `sensitivity_recompute.py`, `sobol_sensitivity.py`, `scenario_discovery.py` — not inferred. |
| Alternatives considered and rejected | None — this is a scope clarification, not a design choice under review. |
| Status | Final as a scope statement. Not expected to change unless `sensitivity_recompute.py` itself is extended to run a driver, which would be a new, separately-declared capability, not a revision of this entry. |
| Reference | `src/index/sensitivity_recompute.py` module docstring; `src/index/sobol_sensitivity.py` module docstring (Phase 6.2, D=13 reconciliation); `src/index/scenario_discovery.py` module docstring (Phase 6.3); `docs/rework/PHASE6_DESIGN.md` Sections 1, 2, 4.2; `docs/DECISIONS.md`, "GEAR v3 Phase 6" entries. |

## 2026-09-16 — `src/main.py`: kept in the tree, not migrated to the v3 (`risk_calculator`) pipeline

| Field | Content |
|---|---|
| Limitation | `src/main.py`, the pre-v3 orchestrator, still imports the deleted `ccrs_calculator`/`ccrs_report` symbols and fails at import/call time. It was never updated to call `risk_calculator.py` or any other v3 module, and carries only an in-file comment pointing elsewhere ("Uso nao recomendado. Sucessor funcional: `src/reporting/results_draft/run_all.py`", `src/main.py:73`) — no functional migration was attempted. |
| Reason | Same Phase 1 decision that deleted `ccrs_calculator.py`/`ccrs_report.py` (2026-09-11) deliberately left every downstream caller — including `main.py` — broken rather than patched, to avoid inventing v3-era methodology (RiskBand_i,h, PSAE, sensitivity analysis, visualization) ahead of its own phase. `src/reporting/results_draft/run_all.py` (generated 2026-09-16) has since become the actual functional pipeline entry point, built independently rather than by migrating `main.py` in place. |
| Evidence tier | Direct code inspection (`src/main.py` imports and in-file warning comment) — not inferred. |
| Alternatives considered and rejected | Migrating `main.py` to call `risk_calculator`/`results_draft` internals — not attempted; `results_draft/run_all.py` already serves the orchestration role, so migrating `main.py` would duplicate rather than restore functionality. |
| Status | Final for the current pipeline shape — `main.py` is not on a path to being fixed in place. Any future reference to "the pipeline entry point" must mean `src/reporting/results_draft/run_all.py`, not `src/main.py`. Revisitable only if a future task explicitly decides to consolidate orchestration back into `main.py`. |
| Reference | `src/main.py:73` (in-file warning); `docs/DECISIONS.md` [2026-09-11] "GEAR v3 Phase 1: Risk_i,h replaces the CCRS core (Equation 1)" (original deliberate-breakage decision); `src/reporting/results_draft/run_all.py` (the functional successor); the "Legacy CCRS visualization/sensitivity layer removed" entry above (2026-09-16, sibling scope for the visualization/Monte Carlo layer). |
