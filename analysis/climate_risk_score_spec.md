# Climate Change Risk Score (CCRS) — formula specification (DRAFT)

**Status: draft for review. Not a decision, not production `src/` code.**
ARCHITECTURE.md Section 9 still requires every verification item closed
before index code is written, and the SCI/NAES → unified-score redesign is
not yet formalised in `docs/DECISIONS.md`. This document is the proposal to
be reviewed before any of it becomes a DECISIONS.md entry or `src/` code.

The **band structure** (Section 8) is closed: absolute `WaterRiskBand`,
sample-relative `HeatRiskBand`, replacing the single-combined-score band.
The `sv`/`iv` rasteriser it depends on is built and tested
(`src/processors/water_variability_processor.py`). Everything else in
Section 10 is still open.

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
  entry already carries. Not decided here, alongside the combined-score
  weights (item A).

---

## 8. Outputs — one numeric score, two discrete bands

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
| A | **Weights in the combined numeric `CCRS_i,s`** (`w_water`/`w_heat`/`w_sv`/`w_iv` per bucket) | Open. Same status as the original §6.1 weight matrix and V5. To be derived by projected-magnitude normalisation (§6). Includes: do `wind`/`solar` get non-zero `w_sv`/`w_iv` at all. **Note:** the *within-water* weights for `WaterRiskBand` (ws/sv/iv relative) are separately fixed in §8.1 from the WRI category widths — that derivation is for the absolute water band only, not the combined-score weight vector. |
| B | **Band cutoffs** | ~~Open~~ **Closed** (Section 8). `WaterRiskBand` = absolute WRI Aqueduct 4.0 category cuts on `S_water` (0.208 / 0.415 / 0.667 / 1.0); `HeatRiskBand` = sample-relative pooled p25/p75/p95 of `extreme_heat_days`, GFDL-ESM4 primary, with a declared limitation. The single-combined-CCRS band is dropped. |
| C | **`EventMultiplier` functional form `f()`** | Open. Linear / stepped / capped; count raw vs normalised by exposure vs rate over 1900–2024 — same open question as the V2 entry. Geocoding level is **not** open: country, per closed V2 (Section 7). |
| D | **`age_factor` → ≥ 1 multiplier mapping** | Open. Convert §7.1 %/year curves into a multiplicative factor; confirm sign convention. |
| E | **`fuel_factor` (V5)** | Open (V5). If it survives review it becomes a second multiplier; if removed, CCRS is unaffected as drafted. |
| F | **Drought / SPEI term — whether to add it, and its weight** | Open. Method is settled if it is added: SPEI with **Thornthwaite** PET (`pr`+`tas`), one method across both GCMs (Section 3). Catalogue constraint in `analysis/spei_catalog_check.md`. |
| G | **Global `(min, max)` constants per term** | To be computed once from a dated data snapshot and frozen in config; not a per-run quantity. |
| H | **sv/iv processing path** | ~~New~~ **Done.** `src/processors/water_variability_processor.py` rasterises `sv_x_r`/`iv_x_r` into `seasonal_variability[_raw]_*` / `interannual_variability[_raw]_*` on the heat grid, mirroring `water_stress_processor` (per-country per-indicator Min-Max, no log, no sentinel). |
| I | **Outlier handling for `Tlin` (sv/iv)** | Open. Whether a p99 clip precedes the linear Min-Max. |

---

## 11. What this draft does and does not settle

Settled here (Section 8): the **band structure** — two independent bands,
absolute `WaterRiskBand` (with its ws/sv/iv weights and cuts fully derived)
and sample-relative `HeatRiskBand` (with its declared limitation). The
single-combined-CCRS band is dropped. `sv`/`iv` rasterisation is built
(`water_variability_processor.py`).

Not settled (Section 10): the combined numeric `CCRS_i,s` weight vector
(item A), `EventMultiplier` functional form (item C), `age_factor` →
multiplier mapping and its code (item D), `fuel_factor` / V5 (item E),
whether a SPEI term is added (item F), the frozen global transform constants
(item G).

Also: this draft does not reopen or close any V-item (`EventMultiplier` is
country-level, so V2 stays closed), and does not by itself supersede
ARCHITECTURE.md §5/§6 — that happens when a `docs/DECISIONS.md` entry records
the accepted spec.

---

## 12. New pipeline components implied (for scoping only)

If this spec is accepted roughly as-is, the index layer would still need:

1. A global per-term transform module for the numeric score — `log1p`/linear
   + frozen global Min-Max bounds (item G).
2. A `CCRS_i,s` assembly module — weighted sum × `age_factor` ×
   `EventMultiplier`, per plant per scenario.
3. `age_factor` implementation with the V1 fuel sub-curves (item D).
4. `EventMultiplier` implementation (item C; country-level per closed V2).
5. `WaterRiskBand` + `HeatRiskBand` classifiers promoted from the `analysis/`
   diagnostics (`water_risk_band_classification.py`, the heat-percentile cut
   in `ccrs_final_summary.py`) into `src/`.
6. Report generators (Section 8) + Monte Carlo wrapper (Section 9).

Done: `sv`/`iv` rasterisation (`src/processors/water_variability_processor.py`,
tested).

None of the above is built until the remaining open items are closed and a
DECISIONS.md entry records the accepted spec.
