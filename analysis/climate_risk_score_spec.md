# Climate Change Risk Score (CCRS) — formula specification (DRAFT)

**Status: draft for review. Not a decision, not code.** ARCHITECTURE.md
Section 9 still requires every verification item closed before index code is
written, and the SCI/NAES → unified-score redesign is not yet formalised in
`docs/DECISIONS.md`. This document is the proposal to be reviewed before any
of it becomes a DECISIONS.md entry or `src/` code.

Provisional name: **Climate Change Risk Score (CCRS)**. One value **per
plant, per scenario** (`ssp126`/`opt`, `ssp370`/`bau`, `ssp585`/`pes`).

---

## 1. Relationship to the current SCI / NAES design

ARCHITECTURE.md Section 5 currently specifies two non-interchangeable
outputs: the **SCI** (within-country ranking, per-country Min-Max, geometric
mean of risk × capacity share × inverse resilience) and the **NAES**
(cross-country, capacity-weighted sum of *raw* hazard).

CCRS collapses these into a **single per-plant score on one cross-country
scale**, with capacity applied only at the reporting roll-up (Section 9),
not inside the score. If adopted, this replaces §5.1 and §5.2 and forces a
rewrite of §6's `Risk_i` definition. That is the "unified climate-risk-score
redesign" the `Hazard combination` DECISIONS.md entry now points to.

---

## 2. Score formula (skeleton)

For plant `i` under scenario `s`:

```
CCRS_i,s  =  Hazard_i,s  ×  age_factor_i  ×  EventMultiplier_i

Hazard_i,s =  w_water · Tlog(WaterStress_raw_i,s)
            + w_heat  · Tlog(HeatStress_raw_i,s)
            + w_sv    · Tlin(SeasonalVariability_raw_i,s)
            + w_iv    · Tlin(InterannualVariability_raw_i,s)
```

- `Tlog(x)` = `MinMax( log1p(x) )` — the log1p option from
  `normalization_diagnostics.md` task 5, made concrete.
- `Tlin(x)` = `MinMax(x)` — linear, no log (Section 4 explains why).
- `MinMax` bounds are **global** — pooled over all three countries and all
  three scenarios, one fixed `(min, max)` per term (Section 8). Not
  per-country, not per-scenario.
- `w_water + w_heat + w_sv + w_iv = 1` within each technology bucket
  (`hydro`, `wind`, `solar`, `thermal`), consistent with §6's definition of
  a weight. **Values not set here** (Section 10, item A).
- `age_factor_i ≥ 1`, multiplicative (Section 6).
- `EventMultiplier_i ≥ 1`, multiplicative (Section 7).

`Hazard_i,s` lies in `[0, 1]` only if a single term carries all the weight;
in general it lies in `[0, max Σw·T]` and is **not** re-normalised — its
scale is fixed by the global per-term transforms, which is what keeps
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

### Not fully specified in this draft: a drought (SPEI) term

A drought term is a plausible fifth hazard. It is **not wired into the
formula here** (no weight, no transform), but the method choices it forces
are settled now so a later addition is unambiguous:

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

If added later, the drought term enters `Hazard_i,s` as a fifth weighted
term with its own transform, and the weight vector becomes 5-dimensional.

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
  silently move every plant's score. It should be stored in `config.py` or
  a versioned constants file, with the data snapshot it was derived from.
- **Min-Max is not outlier-robust.** One extreme basin sets the max for all
  three countries. The `log1p` in `Tlog` mitigates this for ws/heat; for
  sv/iv (linear) a p99 clip before Min-Max may be needed — flag for review.

---

## 5. Buckets and weights — unchanged derivation principle

The weight vector `(w_water, w_heat, w_sv, w_iv)` is **per technology
bucket** (`hydro`, `wind`, `solar`, `thermal`), summing to 1, exactly as
§6 defines a weight. The §6 derivation procedure — project each hazard's
literature coefficient onto its expected magnitude in this study, normalise
within the bucket — is unchanged; it now has two more terms to place.

Open, not decided here (Section 10 item A): whether `sv`/`iv` get non-zero
weight for buckets with no water-cooling or reservoir dependence (`wind`,
`solar`). The physical-mechanism screen in §6.1 currently gives `wind–water`
and `solar–water` Tier 3 ("no plausible mechanism"); the same screen would
presumably zero `w_sv`/`w_iv` for those buckets, leaving them as
`hydro`/`thermal` terms only. This must be argued in the weight derivation,
not assumed here.

---

## 6. `age_factor` — kept, multiplicative, with a declared scope limit

`age_factor_i` is retained from §7.1 (with the V1 fuel-specific sub-curves
for the `thermal` bucket: coal, gas, nuclear, bioenergy, mixed). In CCRS it
**multiplies** `Hazard_i,s` — it is not added as another term.

- Convention: `age_factor_i ≥ 1`, increasing with the cumulative
  age-driven performance loss implied by the bucket's curve (a plant that
  has lost ~20 % to age → ≈ ×1.2). This is the opposite sign convention to
  §7's `Resilience_i` (which is subtracted as `1 − Resilience_norm`); the
  review needs to confirm the mapping from the existing %/year curves to a
  ≥ 1 multiplier.
- `fuel_factor` (§7.3 / V5) and the resilience floor `max(…, 0.1)` and the
  per-country-scenario resilience ceiling normalisation are **not carried
  into CCRS** as drafted. V5 is still open; if `fuel_factor` survives its
  review it would enter as a second multiplicative factor alongside
  `age_factor`. Flag for review.

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
- **Functional form:** `EventMultiplier_i = f( N_events(country(i)) )`, where
  `N_events` is the type-filtered eligible EM-DAT event count on the same
  data base V2 uses — **239 (Brazil), 38 (Portugal), 622 (India)** eligible
  events (severity signal present in 95.0 % / 63.2 % / 98.6 % of them).
- **`f()` is an open item** (Section 10 item C): linear in the count,
  stepped/banded, or with a cap — plus whether the count is used raw or
  normalised by fleet capacity / plant-count exposure, or expressed as a
  rate over the EM-DAT 1900–2024 archive span. Same open question the V2
  entry already carries. Not decided here, alongside the weights (item A)
  and the band cutoffs (item B).

---

## 8. Two outputs from the one score

Both are derived from the same `CCRS_i,s`; neither re-normalises it.

### 8.1 Per-plant report (ranking / map)

- Every plant ranked by `CCRS_i,s`, per scenario, across all three countries
  on the one scale.
- Map of plant points coloured by CCRS band.
- **Absolute bands** `EXTREME / HIGH / MEDIUM / LOW` by fixed cutoffs on
  `CCRS_i,s`. Cutoff values **to be set after** the real CCRS distribution
  is computed and inspected (Section 10 item B) — not percentile bands
  (those would be relative and destroy the cross-country comparability the
  design just bought).

### 8.2 Per-country report

- For each country × scenario: the **share of installed capacity in each
  risk band** — `Σ capacity_mw` of plants in EXTREME / HIGH / MEDIUM / LOW,
  as a percentage of the country's computable capacity base.
- Capacity base = the V6 computable base (coordinates + `commissioning_year`
  present), consistent with the closed V6 decision. Capacity enters **only
  here**, never inside `CCRS_i,s`.
- This is the cross-country headline: "X % of Brazil's operating capacity is
  EXTREME-risk under SSP5-8.5" is directly comparable to the India figure.

---

## 9. Monte Carlo

Unchanged in principle from §8: N = 1000, perturbing the calibrated weights
and `age_factor` (and `EventMultiplier` if its form has free parameters) at
±10/20/30 %. CCRS and both output reports are recomputed inside each
iteration, giving a distribution per plant and per country×scenario band
share rather than a point estimate.

---

## 10. Open items — NOT decided in this draft

| # | item | status / precedent |
|---|---|---|
| A | **Weights `w_water`, `w_heat`, `w_sv`, `w_iv`** per bucket | Open. Same status as the original §6.1 weight matrix and V5. To be derived by projected-magnitude normalisation (§6) or an equivalent method. Includes: do `wind`/`solar` get non-zero `w_sv`/`w_iv` at all. |
| B | **Band cutoffs** for EXTREME/HIGH/MEDIUM/LOW | Open. Absolute cutoffs, set after inspecting the real CCRS distribution. |
| C | **`EventMultiplier` functional form `f()`** | Open. Linear / stepped / capped; count raw vs normalised by exposure vs rate over 1900–2024 — same open question as the V2 entry. Geocoding level is **not** open: country, per closed V2 (Section 7). |
| D | **`age_factor` → ≥ 1 multiplier mapping** | Open. Convert §7.1 %/year curves into a multiplicative factor; confirm sign convention. |
| E | **`fuel_factor` (V5)** | Open (V5). If it survives review it becomes a second multiplier; if removed, CCRS is unaffected as drafted. |
| F | **Drought / SPEI term — whether to add it, and its weight** | Open. Method is settled if it is added: SPEI with **Thornthwaite** PET (`pr`+`tas`), one method across both GCMs (Section 3). Catalogue constraint in `analysis/spei_catalog_check.md`. |
| G | **Global `(min, max)` constants per term** | To be computed once from a dated data snapshot and frozen in config; not a per-run quantity. |
| H | **sv/iv processing path** | New. sv/iv are not currently rasterised or extracted. Needs either a `water_stress_processor`-style rasterisation of `sv_x_r`/`iv_x_r`, or a plant-level point-in-polygon extraction (as in `analysis/aqueduct_indicator_correlation.py`). Design choice, not made here. |
| I | **Outlier handling for `Tlin` (sv/iv)** | Open. Whether a p99 clip precedes the linear Min-Max. |

---

## 11. What this draft explicitly does NOT do

- Does not set any weight, cutoff, or multiplier value.
- Does not reopen or close any V-item. `EventMultiplier` is country-level, so V2 stays closed as-is.
- Does not write or modify anything in `src/`.
- Does not supersede ARCHITECTURE.md §5/§6 — it proposes to, pending review.
- Does not commit anything.

---

## 12. New pipeline components implied (for scoping only)

If this spec is accepted roughly as-is, the index layer would need:

1. sv/iv extraction (item H).
2. A global per-term transform module — `log1p`/linear + frozen global
   Min-Max bounds (item G).
3. A CCRS assembly module — weighted sum × `age_factor` × `EventMultiplier`,
   per plant per scenario.
4. `age_factor` implementation with the V1 fuel sub-curves (item D).
5. `EventMultiplier` implementation (item C; country-level per closed V2).
6. Two report generators (Section 8) + Monte Carlo wrapper (Section 9).

None of this is built until the open items above are closed and a
DECISIONS.md entry records the accepted spec.
