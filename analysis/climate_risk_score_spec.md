# Climate Change Risk Score (CCRS) — formula specification

**Status: implemented and committed.** `src/index/` (T1–T6, all committed —
`ccrs_calculator.py`, `age_factor.py`, `event_multiplier.py`, `risk_bands.py`,
`ccrs_report.py`) implements the closed items of this document: the Hazard
term and its frozen global bounds, `age_factor`, `EventMultiplier`, both risk
bands, and the final multiplicative assembly with its per-country
capacity-share report. ARCHITECTURE.md Section 9's V1–V6 verification items
are all resolved and the SCI/NAES → CCRS redesign is formalised in
`docs/DECISIONS.md`. This document remains the full derivation reference;
`docs/DECISIONS.md` is authoritative on decision history, and the code in
`src/index/` is authoritative on what actually runs.

The **band structure** (Section 8) is closed: absolute `WaterRiskBand`,
sample-relative `HeatRiskBand`, replacing the single-combined-score band —
implemented in `src/index/risk_bands.py`. The `sv`/`iv` rasteriser it depends
on is built and tested (`src/processors/water_variability_processor.py`).
The **per-bucket `(w_water, w_heat, w_drought)` split** (Section 5) is set —
hydro (0.55, 0.00, 0.45), thermal (0.525, 0.175, 0.30), wind (0.00, 0.95,
0.05), solar (0.00, 0.95, 0.05) — replacing the flat `w = 0.25` of the
earlier diagnostics and the earlier 2-way matrix. The
**`EventMultiplier` functional form** (Section 7) is set:
`EventMultiplier_c = 1 + k·(rate_c/rate_max)`, `k = 0.5`, country-level per
V2 — implemented in `src/index/event_multiplier.py`, regression-fixture
validated. The **primary-GCM rule** (Section 8.6) is set: `GFDL-ESM4` is the
cited figure, `MIROC6` a sensitivity panel, never a blend. **V5 is closed** —
`fuel_factor` removed entirely (E). The **`age_factor` mapping** (item D) is
closed — `age_factor = 2 - clip(retention(age), 0, 1)`, confirmed final
2026-09-04 (Section 6, `docs/DECISIONS.md`), implemented in
`src/index/age_factor.py`. The **frozen global transform bounds** (item G)
are closed — `ccrs_calculator.FROZEN_BOUNDS`, one pair per term for
`ws`/`sv`/`iv` (GCM-independent), one pair **per GCM** each for `heat` and
`spei` (never pooled between GFDL-ESM4 and MIROC6), data snapshot
2026-09-04. **The drought/SPEI term (item F) is closed and implemented** —
`Hazard_i,s` gains a third additive term, `w_drought[bucket] *
Tlog(spei_freq)`, with a 3-way `(w_water, w_heat, w_drought)` bucket matrix
replacing the earlier 2-way one (Section 5). Still open in Section 10: the
sv/iv outlier clip (I), and the Monte Carlo sensitivity of the judgment-call
constants — thermal `(w_water, w_heat, w_drought)`, `EventMultiplier` `k`,
and select `age_factor` rates (J). Not implemented.

Provisional name: **Climate Change Risk Score (CCRS)**. One value **per
plant, per scenario** (`ssp126`/`opt`, `ssp370`/`bau`, `ssp585`/`pes`).

---

## 1. Relationship to the current SCI / NAES design

ARCHITECTURE.md Section 5 currently specifies two non-interchangeable
outputs: the **SCI** (within-country ranking, per-country Min-Max, geometric
mean of risk × capacity share × inverse resilience) and the **NAES**
(cross-country, capacity-weighted sum of *raw* hazard).

CCRS collapses these into a **single per-plant score on one cross-country
scale**, with capacity applied only at the reporting roll-up (Section 8.5),
not inside the score. This has been adopted: it replaces the former §5.1 and
§5.2 (now ARCHITECTURE.md Section 5, rewritten 2026-09-03) and the former
§6's `Risk_i` definition. This is the "unified climate-risk-score redesign"
the `Hazard combination` DECISIONS.md entry points to, formalised by "CCRS
replaces SCI/NAES as the unified risk architecture".

---

## 2. Score formula (skeleton)

For plant `i` under scenario `s`:

```
CCRS_i,s  =  Hazard_i,s  ×  age_factor_i  ×  EventMultiplier_i

Hazard_i,s =  w_water[bucket_i]   · water_sub_i,s
            + w_heat[bucket_i]    · Tlog(HeatStress_raw_i,s)
            + w_drought[bucket_i] · Tlog(DroughtFreq_raw_i,s)

water_sub_i,s =  w_ws · Tlog(WaterStress_raw_i,s)
               + w_sv · Tlin(SeasonalVariability_raw_i,s)
               + w_iv · Tlin(InterannualVariability_raw_i,s)
```

- `Tlog(x)` = `MinMax( log1p(x) )` — the log1p option from
  `normalization_diagnostics.md` task 5, made concrete.
- `Tlin(x)` = `MinMax(x)` — linear, no log (Section 4 explains why).
- `MinMax` bounds are **global** — pooled over all three countries and all
  three scenarios, one fixed `(min, max)` per term (Section 8). Not
  per-country, not per-scenario.
- **`water_sub` uses the within-water weights `(w_ws, w_sv, w_iv) =
  (0.4164, 0.2505, 0.3331)`** derived from the WRI category step widths in
  §8.1 — the same three numbers, here applied to the *transformed* terms for
  the numeric score (they act on *raw* values in the absolute
  `WaterRiskBand`). Unchanged by the SPEI integration, never renormalised.
- **`(w_water, w_heat, w_drought)` is per technology bucket** and set in
  Section 5: `hydro` (0.55, 0.00, 0.45), `thermal` (0.525, 0.175, 0.30),
  `wind` (0.00, 0.95, 0.05), `solar` (0.00, 0.95, 0.05). For `wind`/`solar`
  the entire water side — `ws`, `sv` **and** `iv` — is weighted to zero (the
  drought side is not). This replaces the flat `w = 0.25` on every term used
  in the earlier `analysis/ccrs_*` diagnostics, and the earlier 2-way
  `(w_water, w_heat)` matrix.
- `DroughtFreq_raw` = `spei_freq`, mean months/year with SPEI-12 ≤ −1.0
  (`src/processors/spei_processor.py`). `Tlog` bounds are **per GCM**, same
  treatment as `heat`.
- `age_factor_i ≥ 1`, multiplicative (Section 6).
- `EventMultiplier_i ≥ 1`, multiplicative (Section 7).

`w_water + w_heat + w_drought = 1` per bucket and `w_ws + w_sv + w_iv = 1`
within `water_sub`, and every transformed term is in `[0, 1]`, so
`Hazard_i,s ∈ [0, 1]`. It is **not** re-normalised after the weighted sum —
the scale is fixed by the global per-term transforms, which is what keeps
countries comparable.

---

## 3. Hazard terms

| term | indicator | raw source | raw column / layer | transform | scenario axis |
|---|---|---|---|---|---|
| `WaterStress_raw` | Aqueduct `ws` (water stress) | `water_stress_raw_{country}_{scenario}_1km.tif` (already produced) | `{scenario}50_ws_x_r`, sentinel 9999 → country max (as today) | `Tlog` (log1p + global Min-Max) | `bau`/`opt`/`pes` |
| `HeatStress_raw` | `extreme_heat_days` (days/yr tasmax > 40 °C) | `extreme_heat_days_{country}_{model}_{scenario}_1km.tif` (already produced) | passthrough raw layer | `Tlog` (log1p + global Min-Max) | `ssp126`/`ssp370`/`ssp585`, per GCM (gfdl_esm4, miroc6) |
| `SeasonalVariability_raw` | Aqueduct `sv` (seasonal variability) | same Aqueduct FeatureCollection as `ws` — **no new download** | `{scenario}50_sv_x_r` | `Tlin` (global Min-Max, no log) | `bau`/`opt`/`pes` |
| `InterannualVariability_raw` | Aqueduct `iv` (interannual variability) | same FeatureCollection | `{scenario}50_iv_x_r` | `Tlin` (global Min-Max, no log) | `bau`/`opt`/`pes` |

Scenario pairing across the water and heat axes is the existing
`config.AQUEDUCT_SCENARIO_FOR_CMIP6` identity map (`opt↔ssp126`,
`pes↔ssp585`, `bau↔ssp370`).

**Why `Tlog` for ws/heat but `Tlin` for sv/iv** — from
`analysis/aqueduct_indicator_correlation.md` task 4 (plant level, 3
scenarios pooled):

| indicator | Brazil skew | Portugal skew | India skew |
|---|---|---|---|
| ws | 4.37 | 1.35 | 3.28 |
| heat (gfdl_esm4, `normalization_diagnostics.md` task 1) | 2.6–3.3 | 1.6–1.9 | 0.8–1.0 |
| sv | 0.91 | −0.54 | −0.05 |
| iv | 1.49 | −0.41 | 0.97 |

`ws` (and `heat` for Brazil/Portugal) carry the severe right skew that
motivated the log1p option. `sv` and `iv` are near-symmetric to mildly
skewed — log1p would over-correct and could invert their ordering. They get
linear Min-Max only. (`iv` Brazil at +1.5 is the one borderline case — flag
for the review.)

### Excluded term: water depletion (`wd`)

`wd` is **not** a CCRS term. `analysis/aqueduct_indicator_correlation.md`
task 1 measured plant-level Spearman `ws × wd` at **0.98–0.998 in all three
countries** (Brazil 0.994, Portugal 0.998, India 0.985), i.e. `wd` carries
essentially the same rank information as `ws`. Including both would
double-count the water-stress *level* channel and distort any
magnitude-derived weight. `ws` is kept (it is the WRI headline indicator and
the one already in the pipeline); `wd` is dropped with this correlation
result cited as the justification.

### Drought (SPEI) term — CLOSED, implemented

`spei_freq` (mean months/year with SPEI-12 ≤ −1.0, McKee, Doesken & Kleist
1993) is the fifth hazard term, wired into `Hazard_i,s` as a **third
additive component alongside `water_sub` and `Tlog(heat)`** — not folded
into `water_sub` (Section 5 explains why: `water_sub`'s three weights are a
closed, derived quantity, not renormalised to make room for a fourth term).

- **Index: SPEI** (Standardised Precipitation-Evapotranspiration Index) —
  precipitation minus PET, not SPI (precipitation only), so that the
  warming signal enters the drought term.
- **PET method: Thornthwaite** (`pr` + `tas`, daily mean near-surface air
  temperature). `analysis/spei_catalog_check.md` confirms `pr` and `tas`
  are both on the CDS catalogue for **both GCMs × all three scenarios**
  over 2041–2070 with **no gap**. Hargreaves PET (`pr` + `tasmin` +
  `tasmax`) is rejected: daily `tasmin` is **missing for `gfdl_esm4` ×
  `ssp3_7_0`** on the catalogue, which would block the drought term for
  that one model/scenario cell.
- **One PET method across all models** — Thornthwaite for `gfdl_esm4` and
  for `miroc6`. PET methods are not mixed between GCMs (a Hargreaves-for-
  MIROC6 / Thornthwaite-for-GFDL split would make the two models'
  drought terms non-comparable, defeating the point of the second GCM).
- **Accumulation/threshold** (engineering choice, not a source-of-truth
  decision): SPEI-12 (annual accumulation), log-logistic fit via
  probability-weighted moments (Vicente-Serrano, Beguería & López-Moreno
  2010), drought defined as SPEI-12 ≤ −1.0 ("moderately dry or worse").
  Documented in `src/processors/spei_processor.py`.
- **Transform and bounds**: `Tlog(spei_freq) = MinMax(log1p(spei_freq))`,
  same treatment as `heat` — one `(min, max)` pair **per GCM**, since
  `spei_freq` depends on the GCM (unlike the Aqueduct water terms). Frozen
  in `ccrs_calculator.FROZEN_BOUNDS["spei"]` as an **extension** of the
  existing frozen constant (the `ws`/`sv`/`iv`/`heat` values are untouched)
  — see item G and `docs/DECISIONS.md`.
- **Bucket weights**: see Section 5's 3-way `(w_water, w_heat, w_drought)`
  table — a qualitative translation of author judgment, not a formal
  calibration or a literature value.

Implemented in `src/index/ccrs_calculator.py` (formula, transform, bounds)
and `src/processors/spei_processor.py` (the raster layer). See
`docs/DECISIONS.md` "[2026-09-04] SPEI drought term added to Hazard".

---

## 4. Normalisation philosophy — global per-term, no per-country Min-Max

The current SCI Min-Maxes hazard **per country** (`compute_country_minmax`,
`heat_stress_processor` per-country domain). CCRS does **not**. Each term is
transformed once, with `(min, max)` (and the `log1p` applied before Min-Max
for `Tlog`) computed over **all countries and all scenarios pooled**. The
weights then act on values that are already on a single fixed scale.

Consequences to weigh in review:

- **Comparability is preserved end to end** — a CCRS of 0.4 means the same
  hazard exposure in Lisbon and in Chennai. This is the property NAES had
  and SCI deliberately gave up.
- **The per-country normalised rasters (`water_stress_*`, `heat_stress_*`)
  are no longer the CCRS inputs.** CCRS consumes the *raw* layers
  (`water_stress_raw_*`, `extreme_heat_days_*`) plus sv/iv extracted from
  the Aqueduct basins, and applies its own global transform. The existing
  per-country normalised rasters remain valid as a standalone
  within-country product but are not on the CCRS path.
- **The global `(min, max)` is a fixed, documented constant** once computed,
  not recomputed per run — otherwise adding a country or scenario would
  silently move every plant's score. Implemented as `ccrs_calculator.FROZEN_BOUNDS`
  (a module-level constant, not `config.py`), data snapshot 2026-09-04,
  regression-locked against the data on disk (`tests/test_ccrs_calculator.py`
  fails on drift). **Heat gets one pair per GCM** — GFDL-ESM4 and MIROC6 are
  never pooled into the same bound, applying the Section 8.6 no-blend rule to
  the bounds computation itself; `ws`/`sv`/`iv` get a single pair per term,
  since the water rasters carry no GCM axis. This GCM split was not spelled
  out when this item was first drafted (see `docs/DECISIONS.md`, "CCRS global
  Min-Max bounds: heat per-GCM, water GCM-independent").
- **Min-Max is not outlier-robust.** One extreme basin sets the max for all
  three countries. The `log1p` in `Tlog` mitigates this for ws/heat; for
  sv/iv (linear) a p99 clip before Min-Max may be needed — flag for review.

---

## 5. Buckets and weights — per-bucket water/heat/drought split

The numeric `Hazard_i,s` has **three** weighted sides: a water side
(`water_sub`, itself the fixed §8.1 `ws`/`sv`/`iv` combination), a heat side
(`Tlog(heat)`), and a drought side (`Tlog(spei_freq)`, closed with the SPEI
integration — see "Drought (SPEI) term" above). The `(w_water, w_heat,
w_drought)` split between them is **per technology bucket** and set here; it
replaces the flat `w = 0.25` on every term used in the earlier diagnostics,
and supersedes the earlier 2-way `(w_water, w_heat)` matrix.

| Bucket | `w_water` | `w_heat` | `w_drought` | Justification |
|---|---|---|---|---|
| Hydro | 0.55 | 0.00 | 0.45 | Water/heat justification as before (ARCHITECTURE.md §6.1: no independent heat coefficient for hydro). Rescaled to make room for a substantial drought weight: reservoirs are directly and materially exposed to prolonged drought, on top of the (already-covered) evaporation mechanism inside water stress. |
| Thermal | 0.525 | 0.175 | 0.30 | Water/heat ratio (3:1) preserved from the original 0.75/0.25 judgment call (Van Vliet et al. vs. Ibrahim & Attia), both rescaled proportionally to free 0.30 for drought — cooling-water-dependent thermal plants are materially exposed to prolonged drought. |
| Wind | 0.00 | 0.95 | 0.05 | No plausible physical water-*stress* mechanism (ARCHITECTURE.md §6.1, unchanged), but not given an absolute zero on drought: a small, non-mechanistic allowance for regional drought-driven system stress. |
| Solar | 0.00 | 0.95 | 0.05 | Same reasoning as wind. |

**Origin of the drought weights — explicit, not a formal calibration.** Each
row is a direct translation of a qualitative judgment (hydro and
cooling-water-dependent thermal plants are materially more exposed to
prolonged drought than to a single hot day; wind/solar have no physical
water-dependence mechanism but are not set to an *absolute* zero). This is
**not** an AHP/pairwise-derived weight and **not** a literature value — there
is no published water/heat/drought importance ratio for any of these
technologies. Same transparency standard as `age_factor.py`'s assumed coal
overhaul cycle. See `docs/DECISIONS.md`.

**These weights replace the single flat weight** (`w = 0.25` on each of the
four terms) used in `analysis/ccrs_preliminary_distribution`,
`analysis/ccrs_band_classification` and `analysis/ccrs_final_summary`, and
the earlier 2-way matrix used in `analysis/ccrs_bucket_weighted_distribution`.
Those reports remain valid as **exploration of the distribution shape**, not
as a final weight result.

**`sv`/`iv` follow the water side, and `water_sub` itself is untouched.** The
`w_water` weights above apply to the whole (unchanged) `water_sub =
0.4164·ws + 0.2505·sv + 0.3331·iv`, §8.1 — never renormalised for the SPEI
addition. So for `wind`/`solar`, `sv` and `iv` are zeroed **together with**
`ws` — `sv`/`iv` measure the variability of *water availability*, the same
mechanism that is absent for those buckets. There is no separate
`w_sv`/`w_iv` question for `wind`/`solar` any more.

**Monte Carlo (Section 9), open item:** the `thermal` `(0.525, 0.175, 0.30)`
triple (and the analogous small `wind`/`solar` drought allowance) is a
candidate for sensitivity perturbation (±10/20/30 %, the same design as
ARCHITECTURE.md Section 8) once Monte Carlo is implemented — **not
implemented now**, documented as open item J.

The §8.1 within-water weights `(w_ws, w_sv, w_iv)` are **not** open — they
are fixed by the WRI category-width derivation, and are **not** affected by
the SPEI integration.

---

## 6. `age_factor` — kept, multiplicative, with a declared scope limit

`age_factor_i` is retained from §7.1 (with the V1 fuel-specific sub-curves
for the `thermal` bucket: coal, gas, nuclear, bioenergy, mixed). In CCRS it
**multiplies** `Hazard_i,s` — it is not added as another term. Implemented in
`src/index/age_factor.py`; closes item D (Section 10).

- **Convention (closed, confirmed final 2026-09-04 —
  `docs/DECISIONS.md`):** `age_factor_i = 2 - clip(retention(age), 0, 1) ≥ 1`,
  increasing with the cumulative age-driven performance loss implied by the
  bucket's `retention(age) ≤ 1` curve (a plant that has lost ~20 % to age →
  ×1.2, exactly this section's example). `age = 2050 - commissioning_year`
  (`config.YEAR_TARGET`). This is the opposite sign convention to §7's
  `Resilience_i` (which is subtracted as `1 − Resilience_norm`) — an earlier
  session briefly reverted this module to a `≤ 1` retention multiplier on a
  mistaken premise about which document was authoritative; that reversal is
  itself superseded, and `≥ 1` is definitive.
- **Coal** decays 0.25 pp/yr in a sawtooth, not a plain curve: within an
  **assumed** 5-year overhaul cycle (`COAL_OVERHAUL_CYCLE_YEARS`), 70 % of
  that cycle's accumulated loss is recovered at the boundary
  (`COAL_OVERHAUL_RECOVERY`, 30 % permanent). The cycle length and recovery
  fraction are a modelling premise, not values from the cited literature — no
  GEM file carries a per-plant overhaul date; provisional, revisable if one
  appears.
- **Wind** uses a fixed 0.4 %/yr relative retention rate for every plant,
  unconditionally — there is no runtime branch on an initial capacity
  factor. The alternative form,
  `retention = 1 - 0.0015·age/CF_initial`, is kept in
  `src/index/age_factor.py` as documented dead code (never called): no GEM
  file carries a `CF_initial` for any of the 1986 wind plants across the
  three countries.
- **Hydro** uses 0.55 %/yr (linear), the midpoint of the ~0.5–0.6 %/yr range;
  the 0.79 "non-water-attributable share" scaling from an earlier revision
  had no documented origin and is removed.
- **Gas / oil-gas** is pinned neutral (`age_factor = 1.0`), **provisional** —
  no literature-backed rate or functional form was ever found in any project
  document for the "efficiency gain with age" noted since the original V1.
- A missing `commissioning_year` (~5.6 % of plants; concentrated in India's
  wind and solar fleet) neutralises `age_factor` to 1.0 — the row is kept and
  flagged, never dropped.
- `fuel_factor`, the resilience floor `max(…, 0.1)` and the
  per-country-scenario resilience ceiling normalisation are **not carried
  into CCRS**. V5 is closed — `fuel_factor` is removed entirely
  (`docs/DECISIONS.md`, entry "fuel_factor removed from resilience formula
  (V5 closed)"); it does not enter the CCRS as a second multiplier or
  otherwise. `age_factor` and `EventMultiplier` are the only multipliers on
  the hazard score.

**Declared scope limit (for the manuscript):** CCRS measures
**hazard × exposure × `age_factor`**, where `age_factor` is a *partial
proxy for vulnerability* (asset-structural degradation only). It is **not**
the full hazard × exposure × vulnerability triangle — adaptive capacity of
operators/regulators, maintenance regime, retrofit history and design
margin beyond age are not represented. This is the same class of limitation
already listed in ARCHITECTURE.md Section 10 ("Capacidade de adaptação").

---

## 7. `EventMultiplier_i` — EM-DAT, applied as a multiplier on the score

`EventMultiplier_i ≥ 1`, built from EM-DAT disaster frequency, **multiplying**
the central score — not summed alongside the hazard terms, and not folded
into the resilience factor as `event_factor` was.

- **Geocoding level: country.** Every plant in a country shares that
  country's `EventMultiplier`. This is aligned with the closed V2 decision
  (`docs/DECISIONS.md`, "Event factor: country-level EM-DAT frequency") —
  V2 chose country-level and rejected a state/district factor because
  structured sub-national location is present for only ~30–37 % of events
  at adm1 (`analysis/emdat_coverage_diagnostics.md`); an adm1
  `EventMultiplier` would silently reopen that decision. V2 stays closed.
- **Event base:** the type-filtered eligible EM-DAT event count on the same
  data base V2 uses — **`N_events` = 239 (Brazil), 38 (Portugal), 622
  (India)** (severity signal present in 95.0 % / 63.2 % / 98.6 % of them).

- **Functional form (closes Section 10 item C):**

  ```
  rate_c            = N_events(c) / 124          # events per year over the
                                                 # EM-DAT archive span 1900–2024
  EventMultiplier_c = 1 + k · (rate_c / rate_max)
  ```

  - `rate_max = max_c rate_c` — the highest national rate among the three
    study countries (India). The `/124` cancels in `rate_c / rate_max`, so
    the ratio is simply `N_events(c) / N_events(India)`; the rate is
    reported for interpretability, not because the span enters the result.
  - `k = 0.5` — amplitude ceiling: the country with the most frequent
    disaster record has its score lifted by at most +50 %, the rest scale
    linearly below that. `k` is a **Monte Carlo sensitivity parameter**
    (perturbed ±10/20/30 %, same design as Section 8 / open item J); it is
    not re-derived from data.
  - `EventMultiplier_c ≥ 1` always (the reference country sits at `1 + k`,
    not at 1; no country is scored *down*).

  | country | `N_events` | `rate_c` (yr⁻¹) | `rate_c / rate_max` | **`EventMultiplier_c`** (`k = 0.5`) |
  |---|---|---|---|---|
  | Brazil | 239 | 1.927 | 0.3842 | **1.192** |
  | Portugal | 38 | 0.306 | 0.0611 | **1.031** |
  | India | 622 | 5.016 | 1.0000 | **1.500** |

- **Country-level, per V2 (not reopened).** `EventMultiplier_i =
  EventMultiplier_{country(i)}` — constant across every plant in a country.
  It shifts a whole country's scores up uniformly and does **not**
  differentiate the intra-country ranking (the same observation already
  recorded for the former `Resilience_i` / `event_factor`, which was also
  country-uniform). Choosing a rate over raw count, and normalising by the
  cross-country maximum rather than by fleet/exposure, are the resolutions
  of the sub-questions the V2 entry left to this implementation.

Implemented in `src/index/event_multiplier.py`, joined onto the Hazard term
by `country` (never `plant_uid`), multiplicative, validated
many-to-one. The regression fixture recomputes the three values at full
precision — Brazil 1.192122, Portugal 1.030547, India 1.500000 — against the
table above; differences under 0.0005, well inside the 0.01 acceptance
threshold (the table values are 3-decimal roundings of the recomputed ones).

---

## 8. Outputs — one numeric score, two discrete bands

Both bands, and the auxiliary `WaterRiskBand × HeatRiskBand` contingency
table, are implemented in `src/index/risk_bands.py`; the per-country capacity
shares (8.5) are reported by `src/index/ccrs_report.py`.

### 8.0 The numeric `CCRS_i,s` is unchanged

`CCRS_i,s` stays a **single continuous weighted sum** (Section 2:
`Hazard_i,s × age_factor_i × EventMultiplier_i`, with `age_factor` and
`EventMultiplier` applied once implemented). It is the value used for the
**overall per-plant ranking and the per-plant map**. Nothing in this section
changes it.

What changed: the discrete risk classification is **no longer one band on the
whole `CCRS_i,s`**. A single combined band was tried
(`analysis/ccrs_band_classification.py`, `_v2.py`) and rejected — the water
and heat terms have very different evidentiary bases (Section 8.3), and one
band forces the whole classification onto the weaker of the two. The
classification is now **two independently-cut bands**:

### 8.1 `WaterRiskBand_i` — absolute, WRI-anchored (ws + sv + iv)

A combined water score cut at **absolute** thresholds anchored in WRI
Aqueduct 4.0 — no sample percentiles.

**Combined score.** `S_water_i = w_ws·ws_raw_i + w_sv·sv_raw_i + w_iv·iv_raw_i`,
using the `ws_raw` (sentinel-substituted, per the closed water-stress
decision), `sv_raw` and `iv_raw` layers from
`water_stress_processor` / `water_variability_processor`.

**Weights — derived from the WRI category step widths, fully auditable:**

Each indicator has four finite WRI category boundaries; its categories span
raw 0 up to its High→Extremely-High threshold `τ_k`:

| indicator | raw quantity | WRI boundaries (Low \| Low-Med \| Med-High \| High \| Extremely-High) | `τ_k` |
|---|---|---|---|---|
| `ws` | withdrawal ÷ available supply (ratio) | 0.10 / 0.20 / 0.40 / 0.80 | 0.80 |
| `sv` | within-year CV of blue-water supply | 0.33 / 0.66 / 1.00 / 1.33 | 1.33 |
| `iv` | between-year CV of blue-water supply | 0.25 / 0.50 / 0.75 / 1.00 | 1.00 |

1. Average WRI category width for indicator `k`: `Δ_k = τ_k / 4`
   → `Δ_ws = 0.2000`, `Δ_sv = 0.3325`, `Δ_iv = 0.2500`.
   (For `ws` the four steps 0.10/0.10/0.20/0.40 are unequal, so the average
   is used; `sv`/`iv` steps are ~uniform.)
2. Weight ∝ inverse average category width, so that traversing one average
   WRI category of **any** indicator adds the same amount to `S_water`:
   `w_k = (1/Δ_k) / Σ_j (1/Δ_j) = (4/τ_k) / Σ_j (4/τ_j) = (1/τ_k) / Σ_j (1/τ_j)`.

   | | `1/τ_k` | `w_k` |
   |---|---|---|
   | `ws` | 1.25000 | **0.4164** |
   | `sv` | 0.75188 | **0.2505** |
   | `iv` | 1.00000 | **0.3331** |
   | Σ | 3.00188 | 1.0000 |

   `S_water_i = 0.4164·ws_raw + 0.2505·sv_raw + 0.3331·iv_raw`

**Absolute band cuts** on `S_water` = the value of `S_water` when all three
indicators sit exactly on the same WRI category boundary:

| WaterRiskBand boundary | ws / sv / iv at | `S_water` cut |
|---|---|---|
| Low → Low-Medium | 0.10 / 0.33 / 0.25 | **0.208** |
| Low-Medium → Medium-High | 0.20 / 0.66 / 0.50 | **0.415** |
| Medium-High → High | 0.40 / 1.00 / 0.75 | **0.667** |
| High → Extremely-High | 0.80 / 1.33 / 1.00 | **0.999 ≈ 1.0** |

Because `w_k·τ_k = 1/3` for every `k`, each indicator contributes exactly one
third of the top cut, which lands at 1.0. `S_water` above 1.0 (possible —
`iv` and `ws` raw values run well past their top threshold) is deeper into
Extremely-High.

**Anchor strength (declared).** `ws` — strong: the 20 %/40 % withdrawal-ratio
lines trace to Raskin et al. 1997 (SEI) and are standard in the
water-resources literature. `sv`/`iv` — published but weaker: WRI's own
operational round-number CV cutoffs (framework from Brauman et al. 2016),
not tied to a documented impact level. See
`analysis/absolute_threshold_research.md`.

### 8.2 `HeatRiskBand_i` — sample-relative (heat alone)

`extreme_heat_days` (mean days/yr with tasmax > 40 °C) classified on its
**own**, at the **pooled p25 / p75 / p95** of this study's plant sample,
GFDL-ESM4 as the primary GCM (MIROC6 reported as the GCM-sensitivity
variant, using its own pooled percentiles). Percentile cuts are
rank-invariant, so this is equivalently a cut on the transformed heat term.

> **Declared limitation.** There is no published absolute threshold that
> classifies the annual frequency of days above 40 °C into risk categories.
> The literature classifies single-day intensity (WBGT, ISO 7243) or the
> presence/absence of a temperature threshold (World Bank CKP), not
> cumulative annual frequency. Heat-mortality epidemiology deliberately
> avoids fixed absolute cuts because they do not carry across different
> baseline climates — the same physical value (e.g. 35 °C) represents very
> different risk in different climates. `HeatRiskBand` therefore uses cuts
> relative to this study's sample (pooled percentiles) and is sensitive to
> the GCM used (~10–100× difference between GFDL-ESM4 and MIROC6 in the
> underlying absolute values, though the classification itself is recomputed
> per percentile). This is a declared limitation, not an implementation
> flaw — it is the available state of the art for this kind of indicator.

### 8.3 Why two bands and not one

`ws`/`sv`/`iv` can be cut at externally-published absolute thresholds; the
heat term cannot. A single combined band inherits the weakest link — its
cuts could not be physically anchored while heat is in it, *and* absolute
water information would be diluted by heat's sample-relative nature. Keeping
them separate lets water's stronger basis stand on its own and makes heat's
limitation explicit rather than hidden inside a blended cut.

### 8.4 Per-plant report

- Every plant ranked by the numeric `CCRS_i,s`, per scenario, across all
  three countries on the one scale; map of plant points.
- Each plant additionally carries **both** bands: `WaterRiskBand_i` and
  `HeatRiskBand_i` — shown as a pair, never merged.

### 8.5 Per-country report — two separate metrics, never combined

For each country × scenario, **two** capacity shares, reported side by side
and never summed into one percentage:

- "**X % of installed capacity in [band] water risk** (absolute, WRI
  Aqueduct 4.0 categories)"
- "**Y % of installed capacity in [band] heat risk** (relative to this
  study's sample, GCM-dependent)"

Capacity base = the V6 computable base (coordinates + `commissioning_year`),
consistent with the closed V6 decision. Capacity enters only here, never
inside `CCRS_i,s`. A joint cross-tabulation (capacity in each
`WaterRiskBand × HeatRiskBand` cell) is an auxiliary output — see
`analysis/ccrs_final_summary.md` Section 4.

`src/index/ccrs_report.py` asserts every row it sums already is the V6
computable base (`ccrs_calculator.computable_base`) before summing
`capacity_mw` — a hard failure, never a silent fallback, if a raw-fleet row
without `commissioning_year` reaches the sum. `src/index/risk_bands.py` draws
on the same computable base for its own optional per-band capacity summaries
and contingency table — both consumers go through
`ccrs_calculator.computable_base`, never raw `capacity_mw`.

### 8.6 Primary GCM vs sensitivity panel — `GFDL-ESM4` is "the" figure

The heat term (and therefore `HeatRiskBand`, and the `w_heat` share of the
numeric `CCRS_i,s`) is computed for two GCMs, `gfdl_esm4` and `miroc6`. They
are **not** an equal-weight ensemble.

- **`GFDL-ESM4` is the primary GCM for every CCRS report.** The numeric
  score, both risk bands, and any "X % of installed capacity in band …"
  figure quoted as a **headline result of the study** use `GFDL-ESM4`.
- **`MIROC6` is always shown as a sensitivity panel beside the primary
  result** — an extra column in the same table, or a separate "sensitivity
  check" section — **never** averaged or 50/50-blended with `GFDL-ESM4`, and
  never presented as the study's number on its own.
- **Why not a blend.** ARCHITECTURE.md Section 4 already defines the second
  GCM as a *mandatory sensitivity check*, not an ensemble member with equal
  weight. `analysis/ccrs_bucket_weighted_distribution.md` shows why a blend
  would be meaningless here: for the **same physical wind/solar plants**, the
  bucket-weighted hazard (heat only for those buckets) is ~0.006–0.03 under
  `GFDL-ESM4` and saturates near ~0.78 under `MIROC6` — about two orders of
  magnitude apart. Any average or 50/50 combination of the two would be an
  artifact of an arbitrary inter-model weight, not a climate result. Keeping
  them as primary + sensitivity makes the model dependence visible instead of
  hiding it inside a merged number.
- **Retroactive on reading, not on computation.** Every CCRS report already
  produced (`analysis/ccrs_final_summary.md`,
  `analysis/ccrs_bucket_weighted_distribution.md`,
  `analysis/water_risk_band_classification.md`) shows both GCMs side by side —
  nothing needs recomputing. This rule only settles which column is *the*
  cited value when the manuscript text needs a single figure: the
  `GFDL-ESM4` one, with the `MIROC6` value given alongside as the range.

---

## 9. Monte Carlo

Unchanged in principle from §8: N = 1000, perturbing free parameters at
±10/20/30 %. CCRS and both output reports are recomputed inside each
iteration, giving a distribution per plant and per country×scenario band
share rather than a point estimate.

Free parameters to perturb (item J): the **thermal
`(w_water, w_heat, w_drought)` triple** (`0.525 / 0.175 / 0.30`, §5, since
the SPEI integration), the **`EventMultiplier` amplitude `k`** (`0.5`, §7) —
judgment calls rather than derivations — plus `age_factor` now that its
multiplier mapping exists (item D closed).
**Not** perturbed: the within-water `(w_ws, w_sv, w_iv)` (fixed by the WRI
category-width derivation, §8.1, unaffected by the SPEI integration), the
`FROZEN_BOUNDS` for every term including the new `spei` entry (structural
constants, regression-locked), the `risk_bands.py` cuts, and the
`EventMultiplier` event base (`N_events` counts, and India as `rate_max`).
Whether the small, non-mechanistic `wind`/`solar` drought allowance (0.05)
is itself perturbed is left to item J's implementation, not decided here.

---

## 10. Open items — NOT decided in this draft

| # | item | status / precedent |
|---|---|---|
| A | **Weights in the combined numeric `CCRS_i,s`** | ~~Open~~ **Set** (Section 5), 3-way since the SPEI integration (item F). Per-bucket `(w_water, w_heat, w_drought)`: hydro (0.55, 0.00, 0.45), thermal (0.525, 0.175, 0.30), wind (0.00, 0.95, 0.05), solar (0.00, 0.95, 0.05). `sv`/`iv` follow the water side (zeroed for wind/solar). Within-water `(w_ws, w_sv, w_iv) = (0.4164, 0.2505, 0.3331)` fixed in §8.1, unchanged by the drought addition. Residual freedom (thermal triple, wind/solar drought allowance) is a qualitative judgment, flagged for Monte Carlo perturbation (item J), not for re-derivation. |
| B | **Band cutoffs** | ~~Open~~ **Closed** (Section 8). `WaterRiskBand` = absolute WRI Aqueduct 4.0 category cuts on `S_water` (0.208 / 0.415 / 0.667 / 1.0); `HeatRiskBand` = sample-relative pooled p25/p75/p95 of `extreme_heat_days`, GFDL-ESM4 primary, with a declared limitation. The single-combined-CCRS band is dropped. |
| C | **`EventMultiplier` functional form `f()`** | ~~Open~~ **Set** (Section 7). `EventMultiplier_c = 1 + k·(rate_c/rate_max)` with `rate_c = N_events(c)/124`, `rate_max` the cross-country max (India), `k = 0.5`. Values: Brazil 1.192, Portugal 1.031, India 1.500. Country-level per closed V2. Only `k` remains free — as a Monte Carlo sensitivity parameter (item J), not for re-derivation. |
| D | **`age_factor` → ≥ 1 multiplier mapping** | ~~Open~~ **Closed**, confirmed final 2026-09-04 (Section 6, `docs/DECISIONS.md`). `age_factor = 2 - clip(retention(age), 0, 1)`; per-technology curves in Section 6 and ARCHITECTURE.md Section 7.1. Implemented in `src/index/age_factor.py`. |
| E | **`fuel_factor` (V5)** | **Set** — V5 closed, `fuel_factor` removed entirely. See `docs/DECISIONS.md`, entry "fuel_factor removed from resilience formula (V5 closed)". |
| F | **Drought / SPEI term — whether to add it, and its weight** | ~~Open~~ **Closed, implemented** (see "Drought (SPEI) term" above and Section 5). Added as a third additive Hazard term, `w_drought[bucket] * Tlog(spei_freq)`, method Thornthwaite PET (`pr`+`tas`, Section 3). Weights: hydro 0.45, thermal 0.30, wind/solar 0.05 — a qualitative judgment, not a calibration (Section 5). `water_sub` is unchanged, never renormalised. `FROZEN_BOUNDS` extended with a `spei` entry (item G). Implemented in `src/index/ccrs_calculator.py` / `src/processors/spei_processor.py`. |
| G | **Global `(min, max)` constants per term** | ~~Open~~ **Closed.** Frozen as `ccrs_calculator.FROZEN_BOUNDS` (data snapshot 2026-09-04, regression-locked, not recomputed per run): one pair per term for `ws`/`sv`/`iv` (GCM-independent — the water rasters carry no GCM axis), one pair **per GCM** each for `heat` and `spei` (GFDL-ESM4/MIROC6 never pooled, per the Section 8.6 no-blend rule). This per-GCM split was not spelled out when this item was first drafted — see `docs/DECISIONS.md`, "CCRS global Min-Max bounds: heat per-GCM, water GCM-independent". The `spei` entry was added later as an **authorised extension** (item F) — the pre-existing `ws`/`sv`/`iv`/`heat` values are untouched (recomputed and confirmed byte-identical before the extension), so this is a new key added to the frozen constant, not a redefinition of any existing bound. |
| H | **sv/iv processing path** | ~~New~~ **Done.** `src/processors/water_variability_processor.py` rasterises `sv_x_r`/`iv_x_r` into `seasonal_variability[_raw]_*` / `interannual_variability[_raw]_*` on the heat grid, mirroring `water_stress_processor` (per-country per-indicator Min-Max, no log, no sentinel). |
| I | **Outlier handling for `Tlin` (sv/iv)** | Open. Whether a p99 clip precedes the linear Min-Max. |
| J | **Monte Carlo perturbation of the judgment-call constants** | Open (not implemented now). Qualitative choices rather than derivations: the thermal `(w_water, w_heat, w_drought)` triple (`0.525 / 0.175 / 0.30`, §5, since the SPEI integration) and the `EventMultiplier` amplitude `k` (`0.5`, §7). Both perturbed at ±10/20/30 %, same design as ARCHITECTURE.md Section 8. `hydro`/`wind`/`solar` splits, the within-water weights, the `spei`/`heat` `FROZEN_BOUNDS`, and the event *base* (`N_events`, `rate_max` country) are not perturbed. |

---

## 11. What this draft does and does not settle

Settled here (Section 8): the **band structure** — two independent bands,
absolute `WaterRiskBand` (with its ws/sv/iv weights and cuts fully derived)
and sample-relative `HeatRiskBand` (with its declared limitation). The
single-combined-CCRS band is dropped. `sv`/`iv` rasterisation is built
(`water_variability_processor.py`).

Settled here (Section 5): the **per-bucket `(w_water, w_heat, w_drought)`
split** for the numeric `CCRS_i,s` — hydro (0.55, 0.00, 0.45), thermal
(0.525, 0.175, 0.30), wind (0.00, 0.95, 0.05), solar (0.00, 0.95, 0.05),
replacing the flat `w = 0.25` of the earlier diagnostics and the earlier
2-way matrix. Bucket-weighted re-run (pre-SPEI, 2-way):
`analysis/ccrs_bucket_weighted_distribution.md`.

Settled here (Section 7): the **`EventMultiplier` functional form** —
`EventMultiplier_c = 1 + k·(rate_c/rate_max)`, `k = 0.5`, country-level per
closed V2. Values: Brazil 1.192, Portugal 1.031, India 1.500.

Settled here (Section 8.6): **`GFDL-ESM4` is the primary GCM for every CCRS
report; `MIROC6` is a sensitivity panel beside it, never a 50/50 blend** —
ARCHITECTURE.md Section 4's second-GCM-as-sensitivity-check rule, applied to
the CCRS. Retroactive on reading only; no report is recomputed.

Settled here (item E): **V5 is closed** — `fuel_factor` removed entirely, no
bucket gets one (`docs/DECISIONS.md`, "fuel_factor removed from resilience
formula (V5 closed)"). With V5 closed, all six post-data verification items
(V1–V6) are resolved.

Settled here (Section 6, item D): the **`age_factor` → ≥ 1 multiplier
mapping and its code** — `age_factor = 2 - clip(retention(age), 0, 1)`,
confirmed final 2026-09-04, implemented in `src/index/age_factor.py`.

Settled here (Section 4/10, item G): the **frozen global transform bounds**
— `ccrs_calculator.FROZEN_BOUNDS`, one pair per term for `ws`/`sv`/`iv`
(GCM-independent) and one pair per GCM each for `heat` and `spei` (never
pooled between GFDL-ESM4 and MIROC6), data snapshot 2026-09-04.

Settled here (Section 3/5/10, item F): the **drought (SPEI) term** — added
to `Hazard_i,s` as a third additive term, `w_drought[bucket] *
Tlog(spei_freq)`, with the 3-way bucket matrix above and a `FROZEN_BOUNDS`
extension for `spei`. `water_sub` is untouched. Implemented in
`src/index/ccrs_calculator.py` / `src/processors/spei_processor.py`.

Not settled (Section 10): the sv/iv outlier clip (item I), and the Monte
Carlo sensitivity of the judgment-call constants — thermal
`(w_water, w_heat, w_drought)` and `EventMultiplier` `k` (item J).

Also: this draft does not reopen or close any V-item (`EventMultiplier` is
country-level, so V2 stays closed), and does not by itself supersede
ARCHITECTURE.md §5/§6 — that happens when a `docs/DECISIONS.md` entry records
the accepted spec.

---

## 12. Pipeline components — status

All items originally scoped here are now built and committed, except the
Monte Carlo wrapper:

1. **Done** — the global per-term transform (`log1p`/linear) and the frozen
   global Min-Max bounds (item G): `src/index/ccrs_calculator.py`.
2. **Done** — the `CCRS_i,s` assembly module (weighted sum × `age_factor` ×
   `EventMultiplier`, per plant per scenario): `src/index/ccrs_report.py`
   (`compute_ccrs`).
3. **Done** — `age_factor` with the fuel sub-curves (item D):
   `src/index/age_factor.py`.
4. **Done** — `EventMultiplier`, the country-level lookup, form fixed in §7:
   `src/index/event_multiplier.py`.
5. **Done** — `WaterRiskBand` + `HeatRiskBand` classifiers, promoted from the
   `analysis/` diagnostics into `src/index/risk_bands.py`.
6. **Not done** — the Monte Carlo wrapper (Section 9). The per-plant and
   per-country report generators (Section 8) are built
   (`src/index/ccrs_report.py`, `src/index/risk_bands.py`) but run as a point
   estimate, not yet wrapped in the N = 1000 perturbation loop.

Also done: `sv`/`iv` rasterisation (`src/processors/water_variability_processor.py`,
tested).

Remaining before the design is fully closed end-to-end: a decision on the
SPEI term (item F), the sv/iv outlier clip (item I), and the Monte Carlo
sensitivity of the thermal split / `EventMultiplier` `k` (item J) — none of
which the index layer built so far depends on.
