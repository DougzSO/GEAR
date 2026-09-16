# GEAR v3: Results (skeleton draft)

Companion to `GEAR_v3_METHODS_DRAFT.md`. This chapter is structured
around the comparative logic Methods already establishes: cross-country
(Brazil / Portugal / India), cross-scenario (SSP1-2.6 / SSP3-7.0 /
SSP5-8.5, Aqueduct labels `opt` / `bau` / `pes` respectively), cross-bucket
(Hydro / Thermal / Wind / Solar) via PSAE, and intra-hazard priority via
Risk_i,h — never blended across hazards. Two results groups are closed and
carry real, citable numbers (the correlation-gate matrix, Section 1 below,
and the Phase 6 sensitivity/uncertainty results, Section 4): both are
sourced from `docs/DECISIONS.md` closure entries (and, where Methods
already reconciled the numbers, from `GEAR_v3_METHODS_DRAFT.md` directly).
Every other result — RiskBand distributions, PSAE score distributions,
per-hazard priority maps, technology-marker maps, validator overlays — is
not yet computed at full, production scale (Phase 4's DECISIONS.md closure
is a mapping/schema/complete-case-rule closure, not a numeric production
run; confirmed by direct inspection, not assumed) and is marked with the
placeholder format below, tied to its Phase 7 work-plan line.

No number in this draft is invented. Every placeholder names its intended
source module/script and Phase 7 work-plan line, and its status reflects
that `data/outputs/` is entirely gitignored in this repository (confirmed:
`git ls-files data/outputs` returns zero tracked files) — so even where a
table or figure already exists on disk from a prior pipeline run, it is
not a committed, citable artifact and is marked accordingly rather than
as "exists and committed."

---

## 1. Cross-country, cross-hazard hazard-term validation: the correlation
   gate (closed, real numbers)

Before Extreme Precipitation and, within Hydro, the water-variability
terms (`sv`, `iv`) were admitted into any bucket's applicable-hazard set,
each was tested against |r| < 0.80 (Pearson, cross-checked against
Spearman under a per-cell nonlinearity flag) against every existing term
in that bucket, per country, per GCM where GCM-dependent. This gate is a
methods-validation result in its own right — it is the empirical basis
for the applicable-hazard tables (H_b) that every downstream RiskBand and
PSAE result depends on — and is reported here as such.

**Result, all three countries, closed:** every gated pair passed
(|r| < 0.80) in every country/bucket/GCM cell; no candidate hazard was
excluded, and the pre-registered tie-breaker hierarchy was never invoked
on real data. The highest observed |r| among the five gated pairs was
0.702 (Seasonal vs. Interannual Variability, Hydro, Portugal) — close to,
but under, the 0.80 threshold. Representative real values: Extreme
Precipitation vs. Water Stress, Hydro, India, GFDL-ESM4, r = -0.354;
Extreme Precipitation vs. Drought, Hydro, India, GFDL-ESM4, r = -0.495.
The mandatory, non-gated Water Stress vs. Drought pair (exempt from
exclusion by design) was consistently weak across all three countries
(Pearson/GFDL-ESM4 then Spearman/MIROC6): Brazil r = 0.039/-0.283,
Portugal r = -0.003/0.049, India r = 0.236/0.140 — corroborating the
mechanistic distinction between structural water stress and short-term
precipitation-evapotranspiration deficit without needing a high
correlation for that distinction to hold. The per-cell nonlinearity flag
(|rho| - |r| > 0.10) fired for 4 of 48 real-data cells (Seasonal
Variability vs. Water Stress, Hydro, Portugal; Interannual Variability vs.
Water Stress, Hydro, Portugal and India; Water Stress vs. Drought, Hydro,
Brazil, MIROC6), each reported explicitly.

Source: `docs/DECISIONS.md`, "GEAR v3 Phase 2.5: correlation gate
implemented and run — every gated pair passed, no exclusion" and "GEAR v3
Phase 2.5 follow-up: Portugal/India Extreme Precipitation processed, gate
closed for all three countries" (both 2026-09-12); reconciled in
`GEAR_v3_METHODS_DRAFT.md` Section 4.

```
[FIGURE/TABLE PLACEHOLDER: Full pairwise correlation-gate matrix (Pearson's r, Spearman's rho, sample size n, decision-method flag, pass/fail) for all five gated pairs x three countries x applicable GCMs, plus the mandatory Water Stress/Drought reference row | Source: computed by src/index/correlation_gate.py, reported in docs/DECISIONS.md, "GEAR v3 Phase 2.5: correlation gate implemented and run" and its Portugal/India follow-up closure | Caption draft: Pairwise correlation matrix for the five gated hazard-term pairs (Extreme Precipitation vs. Water Stress; Extreme Precipitation vs. Drought/SPEI; Seasonal Variability vs. Water Stress; Interannual Variability vs. Water Stress; Seasonal vs. Interannual Variability) and the mandatory, non-gated Water Stress vs. Drought reference pair, computed per country (Brazil, Portugal, India) and, for GCM-dependent terms, per driving GCM (GFDL-ESM4, MIROC6, never blended). Cell values report Pearson's r and Spearman's rho; cells where |rho|-|r| > 0.10 are flagged and rho is substituted as the decision statistic. All 48 real-data cells pass the |r| < 0.80 exclusion threshold; the closest approach is Seasonal vs. Interannual Variability, Hydro, Portugal (|r| = 0.702). No candidate hazard was excluded from any bucket's applicable-hazard set on this basis. | Status: exists on disk (data/outputs/tables/correlation_gate.csv), not committed to this repository (data/outputs/ is fully gitignored) — pending Phase 7 asset promotion to a committed article/appendix artifact]
```

---

## 2. Cross-hazard priority via RiskBand: per-plant classification
   outcomes

RiskBand_i,h classifies each plant into Low/Medium/High/Extreme per
applicable hazard, using the Tier 1 (Water Stress, Wind-bucket Extreme
Wind) or Tier 3 sample-relative percentile (all other hazards) cutoffs
established in Methods Section 5. [Esta seção descreve resultados já
computados e salvos em `data/outputs/tables/risk_bands.csv` (última
atualização em disco: 2026-09-16; não git-tracked -- `data/outputs/` é
gitignored neste repositório).

O arquivo contém 88.116 linhas <!-- risk_bands.csv, wc -l = 88117 - 1 header, 2026-09-16 -->,
uma linha por combinação (plant x water_scenario x heat_scenario x model x
hazard_term), não uma linha por país -- **não** é a mesma estrutura que
`wc -l` = "número de países" assumida no comando original; a contagem
real de países é obtida separadamente (ver abaixo). Cobertura: 10.808
plantas únicas <!-- cut -d',' -f1 risk_bands.csv | sort -u | wc -l -->,
3 países -- Brazil, India, Portugal <!-- cut -d',' -f2 risk_bands.csv | sort -u -->,
4 buckets -- hydro, solar, thermal, wind <!-- cut -d',' -f4 risk_bands.csv | sort -u -->,
7 hazard_term -- heat, iv, precip, spei, sv, wind, ws
<!-- cut -d',' -f8 risk_bands.csv | sort -u -->.

Distribuição bruta de `risk_band` (coluna 13, todas as linhas agregadas,
sem quebra por país/bucket/scenario -- essa quebra faceted é o que o
FIGURE/TABLE PLACEHOLDER abaixo ainda pede e não foi extraída aqui):
Low = 69.349, Medium = 10.248, High = 4.003, Extreme = 4.438, valor vazio
= 78 <!-- cut -d',' -f13 risk_bands.csv | sort | uniq -c, 2026-09-16 -->.
As 78 linhas com `risk_band` vazio não têm explicação no CSV (sem coluna
de motivo/flag correspondente); reportado como está, sem inferir causa.]

```
[FIGURE/TABLE PLACEHOLDER: Per-hazard RiskBand distribution (count and MW-share of plants in Low/Medium/High/Extreme), faceted by country x bucket x SSP scenario | Source: risk_bands.py output, per GEAR_v3_work_plan.md Phase 7.1 ("per-hazard risk band maps remain primary") | Caption draft: Distribution of RiskBand_i,h classifications (Low/Medium/High/Extreme) across the operating fleet, by hazard, technology bucket, country, and SSP scenario (SSP1-2.6/SSP3-7.0/SSP5-8.5). Bars show both plant count and installed-capacity share (MW) per band. Extreme Wind's three SSP columns are identical by construction (Section 3 below) and are shown once, annotated as scenario-invariant rather than repeated as three visually distinct bars. | Status: pending Phase 7 implementation (production-scale RiskBand run and figure code not yet executed/committed)]

[FIGURE/TABLE PLACEHOLDER: Per-hazard, per-country RiskBand asset map (point symbology, technology-differentiated markers, colored by RiskBand) | Source: mapping module under src/visualization/, per GEAR_v3_work_plan.md Phase 7.1-7.2 (technology-differentiated map markers) | Caption draft: Geographic distribution of the operating power-generation fleet in Brazil, Portugal, and India, symbol shape encoding technology bucket (Hydro/Thermal/Wind/Solar) and color encoding RiskBand_i,h for [hazard], under [SSP scenario]. Marker size is not used to encode capacity on this map (see Risk_i,h asset-magnitude figures, Section 3, for capacity-weighted display). | Status: pending Phase 7 implementation]
```

---

## 3. Intra-hazard asset risk magnitude: Risk_i,h (never blended across
   hazards)

Risk_i,h = Hazard_i,h x Exposure_i x Vulnerability_i is valid for
comparison across technology and country, strictly within the same
hazard; it is never summed or otherwise combined across hazards for the
same asset, and no "total plant risk" figure is produced anywhere in this
framework. [Esta seção descreve resultados já computados e salvos em
`data/outputs/tables/risk_by_hazard.csv` (última atualização em disco:
2026-09-16; não git-tracked -- `data/outputs/` é gitignored neste
repositório).

453.936 linhas <!-- risk_by_hazard.csv, wc -l = 453937 - 1 header,
2026-09-16 -->, mesma granularidade plant x hazard x scenario x model
que `risk_bands.csv`, não uma linha por país. Cobertura: 10.808 plantas
únicas <!-- cut -d',' -f1 risk_by_hazard.csv | sort -u | wc -l -->, 3
países -- Brazil, India, Portugal <!-- cut -d',' -f2 risk_by_hazard.csv | sort -u -->,
7 hazard_term -- heat, iv, precip, spei, sv, wind, ws
<!-- cut -d',' -f12 risk_by_hazard.csv | sort -u -->. O campo `risk_i_h`
varia de 0.0 (Brazil, hydro, ws, plant BRA-4cc1c9e5df02) a
14538.66546653318 (Brazil, hydro, spei, plant BRA-7fc1bf22ac79)
<!-- awk sobre a coluna risk_i_h (16), min/max exatos sem arredondamento,
2026-09-16 -->. Nenhuma coluna de RiskBand ou de agregação por
país/bucket existe neste arquivo além do que foi extraído; a
distribuição faceted pedida pelos FIGURE/TABLE PLACEHOLDER abaixo (3.2)
não foi extraída aqui.]

### 3.1 Extreme Wind: scenario-invariant structural exposure (explicit
    result, not a data gap)

Extreme Wind is sourced from ERA5 historical reanalysis
(1991-2020), not a CMIP6 SSP projection, because no CMIP6 daily-maximum
or gust wind variable exists on the CDS catalogue for either configured
GCM, and the one daily variable that does exist (`sfcWind`, daily mean)
is not the same physical quantity as ERA5's instantaneous gust this
hazard's threshold design uses. As a direct, structural consequence,
**Extreme Wind's Risk_i,h, RiskBand, and PSAE contribution are identical
across all three SSP columns (SSP1-2.6/SSP3-7.0/SSP5-8.5) of every
comparison table and figure in this chapter** — computed once from the
ERA5 baseline and copied across the scenario axis, not a coincidental
convergence of three independent projections. This is reported here as
its own explicit result, not left implicit in a table whose Extreme Wind
columns simply do not move: it reflects structural exposure to severe
wind that this framework treats as scenario-independent by design, a
settled epistemic position (not a placeholder pending better CMIP6 wind
data — even a future CMIP6 daily-maximum/gust product would resolve only
one of the two independent grounds for this decision and would not by
itself reopen it).

```
[FIGURE/TABLE PLACEHOLDER: Extreme Wind Risk_i,h / RiskBand / PSAE contribution, single-column display (SSP-invariant), by country and bucket (Wind, Solar) | Source: risk_calculator.py / risk_bands.py Extreme Wind term, per GEAR_v3_work_plan.md Phase 7.5 (Risk_i,h intra-hazard comparison figures, explicitly labeled by hazard) | Caption draft: Extreme Wind's contribution to Risk_i,h, RiskBand, and PSAE_i, shown as a single value per plant rather than three near-duplicate SSP columns, since this hazard is sourced from ERA5 historical reanalysis (1991-2020) and is identical across SSP1-2.6/SSP3-7.0/SSP5-8.5 by construction (Methods Section 2.5). Annotated explicitly as scenario-invariant structural exposure, not a missing-data artifact. | Status: pending Phase 7 implementation (production-scale Risk_i,h for Extreme Wind additionally depends on ERA5 gust acquisition and the compute_mean_annual_max_gust() reduction step, per docs/LIMITATIONS.md, "2026-09-14 — Extreme Wind: ERA5 gust acquisition complete... Risk_i,h gap unchanged, still open" — acquisition is complete for all three countries but the Risk_i,h integration step had not yet been run as of that entry)]
```

### 3.2 Per-hazard, per-country, per-bucket Risk_i,h comparison

```
[FIGURE/TABLE PLACEHOLDER: Risk_i,h intra-hazard comparison figure, one panel per hazard, capacity-weighted asset markers colored/sized by Risk_i,h, faceted by country and SSP scenario | Source: src/visualization/ risk-magnitude mapping module, per GEAR_v3_work_plan.md Phase 7.5 | Caption draft: Asset-level Risk_i,h for [hazard], across Brazil, Portugal, and India, under [SSP scenario]. Marker size encodes Systemic Capacity at Risk (raw linear MW); color encodes Risk_i,h. Comparisons are valid across technology and country strictly within this single hazard panel (Methods Section 9); no cross-hazard sum or blended score is computed or displayed. Technology bucket is additionally encoded by marker shape. | Status: pending Phase 7 implementation]

[FIGURE/TABLE PLACEHOLDER: Top-N asset risk ranking table per hazard, per country (Risk_i,h, MW, RiskBand, age_factor) | Source: risk_calculator.py output ranked and filtered, per GEAR_v3_work_plan.md Phase 7.1/7.5 | Caption draft: The N highest-Risk_i,h assets for [hazard] in [country] under [SSP scenario], reporting installed capacity (MW), age_factor, Hazard_i,h, and resulting Risk_i,h. Rankings are hazard-specific and not comparable across the different hazard panels in this table set. | Status: pending Phase 7 implementation]
```

A material caveat applies to any Risk_i,h ranking or sensitivity claim
involving Thermal/coal assets: the age_factor vulnerability term for coal
plants uses an assumed overhaul cycle (5-year cycle, 70% recovery
fraction per completed cycle) that is a modelling premise, not a value
derived from a real per-plant overhaul-history source — no GEM field
records overhaul, retrofit, or repowering dates for any of the three
countries. This assumption is one of Risk_i,h's leading sensitivity
contributors (Section 4.1 below); any coal-plant risk ranking should be
read with this in mind rather than as reflecting confirmed plant-specific
maintenance history.

---

## 4. Sensitivity and uncertainty analysis (closed, real numbers)

Two analyses, matched to parameter type: Sobol/SALib global sensitivity
indices for the thirteen genuinely continuous parameters (Section 4.1),
and scenario discovery / one-at-a-time analysis for structural/discrete
decisions that a variance-based method is unsuited to (Section 4.2). A
separate general Monte Carlo run characterizes per-country/scenario point
estimates and confidence intervals (Section 4.3). All three are closed,
executed against real production data for all three countries and both
GCMs.

Source for this section throughout: `docs/DECISIONS.md`, "GEAR v3 Phase 6
closure: full-scale Sobol run (N_0=1024) and general-MC convergence run
(N=100..1600, converged at N=800) executed, real results, Phase 6 CLOSED"
(2026-09-15); reconciled in `GEAR_v3_METHODS_DRAFT.md` Section 7.

### 4.1 Sobol/SALib global sensitivity (D=13, N_0=1024)

A full-scale Sobol run (N_0 = 1024, `calc_second_order = False`,
15,360 real evaluations) was executed against real data for all three
countries and both GCMs: 2.01 hours total runtime, 0.4712 s/draw, with
`psae_complete` coverage of 99.847% (31,079,520 of 31,127,040 rows).

For Risk_i,h (capacity-weighted mean, pooled), the leading sensitivity
contributors are `hydro_retention_rate` (S1 = 0.4034, ST = 0.4046),
`coal_decay_rate` (S1 = 0.1964, ST = 0.2068), `upper_tail_padding_fraction`
(S1 = 0.1953, ST = 0.1946), and `coal_overhaul_recovery` (S1 = 0.1908,
ST = 0.2003) — the four together account for nearly all of ΣS1
(approximately 0.99), with ST approximately equal to S1 throughout,
indicating a near-additive response with no meaningful parameter
interactions. Every percentile-cut/hazard-shift parameter carries S1
approximately 0 for Risk_i,h.

**Binding manuscript caveat:** `coal_overhaul_recovery` is an
author-declared engineering assumption with no calibrating source — no
GEM-tracked field records plant-level overhaul history for any of the
three countries (Methods Section 2.6; `docs/LIMITATIONS.md`, "GEM
retrofit/repowering field absent"). Its position as one of Risk_i,h's four
leading sensitivity contributors, comparable in magnitude to
`coal_decay_rate` and roughly half of the leading contributor
(`hydro_retention_rate`), must be reported as "the model's Risk_i,h output
is sensitive to an admittedly unsourced modelling premise, not a
validated empirical parameter" — never as an empirical finding about coal
plant behavior.

For PSAE_i (mean, `psae_complete = False` NaN-masked), the sensitivity
pattern is structurally distinct: every age_factor/normalization
parameter (all seven of the parameters that dominate Risk_i,h's
sensitivity) carries S1 approximately 0, while `precip_percentile_shift`
(S1 = 0.4670), `heat_percentile_shift` (S1 = 0.4534), and
`wind_percentile_shift` (S1 = 0.0774) dominate (ΣS1 approximately 0.997,
again near-additive). This empirically confirms, at full production
scale, the two-chain independence built into the pipeline's architecture:
Risk_i,h and RiskBand/PSAE_i never mix inputs.

```
[FIGURE/TABLE PLACEHOLDER: Sobol S1/ST bar chart, two panels (Risk_i,h, PSAE_i), all thirteen parameters | Source: Sobol/SALib output reported in docs/DECISIONS.md, "GEAR v3 Phase 6 closure..." (2026-09-15); numeric table already reconciled in GEAR_v3_METHODS_DRAFT.md Section 7.2 | Caption draft: First-order (S1) and total-order (ST) Sobol sensitivity indices for all thirteen perturbed continuous parameters, shown separately for Risk_i,h (capacity-weighted pooled mean) and PSAE_i (mean, psae_complete-masked). The two outputs draw on structurally disjoint parameter subsets (age_factor/normalization parameters for Risk_i,h; hazard percentile-shift parameters for PSAE_i), confirming the pipeline's two-chain architectural independence at full production scale (N_0=1024, 15,360 evaluations, 99.847% psae_complete coverage). coal_overhaul_recovery is flagged as an unsourced modelling assumption despite its high sensitivity rank for Risk_i,h. | Status: pending Phase 7 asset promotion — underlying numbers are closed and committed via docs/DECISIONS.md; the rendered figure/table asset itself has not yet been produced as a committed article file]
```

### 4.2 Scenario discovery / one-at-a-time (structural/discrete
    parameters)

Applied to binary or threshold decisions unsuited to variance
decomposition: hazard inclusion/exclusion per bucket, the PSAE cut
points, and the correlation-gate threshold. Executed at full scale
against real data:

- **Hazard-removal OAT** (eleven meaningful removals). The largest
  observed capacity-fraction shifts are in Portugal: removing Extreme
  Heat from Solar moves 76.9 percentage points of capacity out of MEDIUM
  into HIGH/LOW; removing Extreme Precipitation or Extreme Wind from
  Solar produces the same-magnitude shift via the shrunk H_b (3 -> 2)
  mechanically changing which fraction crosses the >=1/2 HIGH threshold.
  Thermal/India removals shift 48.6-54.1 percentage points.
- **Correlation-gate threshold sweep** (seven thresholds, 0.60-0.90).
  Flips relative to the production 0.80 baseline occur at 0.60 (15
  cells), 0.65 (14), 0.70 (13), and 0.75/0.85/0.90 (12 each); no flip
  occurs at 0.80 itself. The highest-value flip is Seasonal vs.
  Interannual Variability, Hydro, Portugal (|r| = 0.7021, the closest
  real pair to the gate), flipping to "fail" at threshold <= 0.70, with
  the tie-breaker correctly retaining `iv` over `sv`.
- **PSAE cut-point sweep** (0.4/0.5/0.6 boundary shift). Of 27 (H_b size,
  PSAE value, shifted cut) combinations, exactly one produces a different
  classification than the 0.5 baseline (H_b size = 5, PSAE value = 0.4:
  HIGH at cut = 0.4, MEDIUM at both 0.5 baseline and cut = 0.6); every
  degenerate EXTREME/LOW row is unchanged at every cut.

```
[FIGURE/TABLE PLACEHOLDER: Hazard-removal OAT summary table (capacity-fraction shift per removal, by country and bucket) | Source: scenario-discovery module output reported in docs/DECISIONS.md, "GEAR v3 Phase 6 closure..." (2026-09-15) | Caption draft: Change in the distribution of PSAE band classifications (percentage points of installed capacity reassigned) when each applicable hazard is individually removed from its bucket's H_b, by country. Portugal/Solar shows the largest shifts (up to 76.9 pp) due to the mechanical effect of a shrinking H_b denominator on the >=1/2 HIGH threshold. Wind is excluded from this analysis (|H_b|=1; removal would empty the applicable-hazard set). | Status: pending Phase 7 asset promotion — underlying numbers closed via docs/DECISIONS.md, rendered table not yet committed]

[FIGURE/TABLE PLACEHOLDER: Correlation-gate threshold sweep, flip count vs. threshold (0.60-0.90) | Source: scenario-discovery module, per docs/DECISIONS.md Phase 6 closure | Caption draft: Number of correlation-gate pairwise cells that would flip pass/fail status under seven alternative |r| exclusion thresholds (0.60-0.90), relative to the production baseline of 0.80 (zero flips at baseline by construction). The closest real pair to the gate, Seasonal vs. Interannual Variability (Hydro, Portugal, |r|=0.7021), is annotated as the first pair to flip (at threshold <= 0.70). | Status: pending Phase 7 asset promotion]
```

### 4.3 General Monte Carlo uncertainty propagation

A separate general Monte Carlo driver propagates the same continuous
parameter uncertainty into per-country/scenario point estimates and
confidence intervals, using nine independent RNG streams (three countries
x three water scenarios). A doubling sequence (N = 100, 200, 400, 800,
1600 per stream) was run against real data; convergence (point-estimate
relative change < 1% and 95% CI half-width relative change < 5%, both
required for every stream and both outputs) was reached and confirmed at
**N = 800 per stream**, one doubling short of the design's original
8,000-16,000 floor, confirmed by the N = 1600 step (relative change
0.00004-0.00838 for point estimates, 0.00000-0.01703 for CI half-width,
both comfortably inside tolerance for every stream).

Cross-country, cross-scenario point estimates at N = 800 (mean, 95% CI):
Brazil risk_mean ranges 639.2 (opt) to 743.3 (pes); India risk_mean
ranges 305.2 (opt) to 321.0 (pes); Portugal risk_mean ranges 96.0 (opt)
to 98.8 (bau) — Portugal's risk_mean is an order of magnitude below
Brazil's and roughly a third of India's, consistent with Portugal's
smaller and comparatively newer fleet. PSAE_mean shows the reverse
country ordering: Portugal (0.512-0.516) is far higher than India
(0.110-0.120) and Brazil (0.039-0.055), reflecting PSAE's within-bucket
saturation-fraction construction rather than fleet scale. Full numeric
table: `GEAR_v3_METHODS_DRAFT.md` Section 7.4.

```
[FIGURE/TABLE PLACEHOLDER: General-MC convergence diagnostic (point-estimate and CI half-width relative change vs. N, both outputs, all nine streams) | Source: general Monte Carlo driver output reported in docs/DECISIONS.md, "GEAR v3 Phase 6 closure..." (2026-09-15); numeric table already reconciled in GEAR_v3_METHODS_DRAFT.md Section 7.4 | Caption draft: Convergence of the general Monte Carlo uncertainty-propagation run across a doubling sequence (N=100 to 1600 draws per stream), for both point-estimate relative change (<1% criterion) and 95% confidence-interval half-width relative change (<5% criterion), for risk_mean and psae_mean, across all nine country-scenario RNG streams. Convergence is reached and confirmed at N=800 per stream, one doubling short of the design's original 8,000-16,000 floor. | Status: pending Phase 7 asset promotion — underlying numbers closed and committed via docs/DECISIONS.md]

[FIGURE/TABLE PLACEHOLDER: Cross-country, cross-scenario risk_mean/psae_mean bar chart with 95% CI error bars, N=800 | Source: general Monte Carlo driver output, numeric table in GEAR_v3_METHODS_DRAFT.md Section 7.4 | Caption draft: Mean Risk_i,h (capacity-weighted, pooled) and mean PSAE_i, with 95% confidence intervals from N=800-per-stream Monte Carlo uncertainty propagation, for each of nine country x water-scenario combinations (Brazil/Portugal/India x opt/bau/pes, i.e. SSP1-2.6/SSP3-7.0/SSP5-8.5). Note the inverse country ordering between the two outputs: Brazil and India lead on risk_mean while Portugal leads on psae_mean, a consequence of PSAE's within-bucket saturation-fraction construction (Methods Section 6) rather than a contradiction. | Status: pending Phase 7 asset promotion]
```

---

## 5. Cross-bucket screening comparison: PSAE distributions

PSAE_i is valid only within the same technology bucket, across any
country — never across buckets, since |H_b| differs by bucket and the
index is a within-bucket saturation fraction, not an absolute severity
scale (Methods Section 6.2). No PSAE figure or table in this chapter
plots different buckets on a shared color scale or ranks them in one
list. [Esta seção descreve resultados já computados e salvos em
`data/outputs/tables/psae.csv` (última atualização em disco: 2026-09-16;
não git-tracked -- `data/outputs/` é gitignored neste repositório).

32.424 linhas <!-- psae.csv, wc -l = 32425 - 1 header, 2026-09-16 -->,
uma linha por combinação (plant x water_scenario x heat_scenario x
model), não uma linha por país. Cobertura: 10.808 plantas únicas
<!-- cut -d',' -f1 psae.csv | sort -u | wc -l -->, 3 países -- Brazil,
India, Portugal <!-- cut -d',' -f2 psae.csv | sort -u -->. O campo
`psae` varia de 0.0 a 1.0, com mediana 0.0 sobre 32.388 valores não
vazios <!-- valor central da lista ordenada de psae.csv coluna psae
(10), n=32388, 2026-09-16 -->. `psae_complete` = True em 32.388 linhas
e False em 36 <!-- cut -d',' -f12 psae.csv | sort | uniq -c -->.
Distribuição de `psae_label`: LOW = 24.479, MEDIUM = 6.971, HIGH = 395,
EXTREME = 543, vazio = 36 <!-- cut -d',' -f11 psae.csv | sort | uniq -c,
2026-09-16 -->. Esta é a distribuição bruta agregada, sem quebra por
bucket/país/scenario, que é o que o FIGURE/TABLE PLACEHOLDER abaixo
ainda pede e não foi extraído aqui.] The N=800 general-MC psae_mean point estimates
(Section 4.3) remain the only PSAE-related numbers already reconciled into
narrative text in this draft; those are pooled means with confidence
intervals, not full band-distribution counts.

```
[FIGURE/TABLE PLACEHOLDER: PSAE_i band distribution (EXTREME/HIGH/MEDIUM/LOW, plant count and MW-share), separate panel per bucket (Hydro/Thermal/Solar four-band; Wind two-band LOW/EXTREME), faceted by country and SSP scenario | Source: PSAE aggregation module (src/index/, per Methods Section 6 / Equation 2), per GEAR_v3_work_plan.md Phase 7.1 ("PSAE map becomes explicitly labeled secondary/screening, intra-technology only") | Caption draft: Distribution of PSAE_i categorical classifications across the operating fleet, shown as one independent panel per technology bucket (Hydro, Thermal, Solar: EXTREME/HIGH/MEDIUM/LOW; Wind: compressed LOW/EXTREME scheme, |H_b|=1), by country and SSP scenario. Panels are never combined on a shared color scale or ranked against one another: PSAE is a within-bucket saturation fraction (fraction of applicable hazards at RiskBand >= High), not an absolute cross-bucket severity measure (Methods Section 6.2). psae_complete coverage (fraction of plants with a fully defined PSAE_i under the complete-case convention) is reported alongside each panel. | Status: pending Phase 7 implementation (production-scale PSAE run and figure code not yet executed/committed)]

[FIGURE/TABLE PLACEHOLDER: PSAE secondary/screening map, one map per bucket, colored by PSAE category, technology-differentiated marker shape, validator overlay | Source: mapping module, per GEAR_v3_work_plan.md Phase 7.1-7.3 | Caption draft: Geographic distribution of PSAE_i screening classifications for [bucket] plants across Brazil, Portugal, and India under [SSP scenario], explicitly labeled as a secondary, screening-only index (not asset risk magnitude; see Risk_i,h maps, Section 3, for that). Marker shape encodes technology bucket where a country/bucket combination includes sub-technologies; color encodes PSAE category. Physical-occurrence (IBTrACS) and broad-impact (EM-DAT) validator markers are overlaid with visually distinct symbology, per Methods Section 7's two-class validator taxonomy — a broad-impact "No Record" state is never rendered as equivalent to "no hazard occurred." | Status: pending Phase 7 implementation]
```

---

## 6. Contextual validator overlays

Physical-occurrence (IBTrACS cyclone/storm-track) and broad-impact
(EM-DAT) validators corroborate hazard occurrence independently of the
Risk_i,h/RiskBand/PSAE computation chain; they are not inputs to any of
the three. Real, country-level validator match patterns are on record
(the IBTrACS radius-based matching found Brazil's only corroborating
storm across the full post-2000 South Atlantic record to be Hurricane
Catarina, 2004 — the basin's one documented case — and Portugal's
corroborations traced to five identifiable storms: Joaquin 2015, Leslie
2018, Michael 2018, Alpha 2020, Gabrielle 2025). [Esta seção descreve
resultados já computados e salvos em
`data/outputs/tables/contextual_validators.csv` (última atualização em
disco: 2026-09-15; não git-tracked -- `data/outputs/` é gitignored neste
repositório). Ver também "Known Issues" abaixo: MANIFEST.md item 14
registra um join de produção completo (58.744 linhas) contra as tabelas
de risco finais, o que contradiz a formulação "not yet produced" mantida
até aqui neste texto.

58.744 linhas confirmado <!-- contextual_validators.csv, wc -l = 58745 -
1 header, 2026-09-16; bate com MANIFEST.md item 14 -->. Colunas:
plant_uid, country, plant_name, bucket, validator_class, source,
hazard_term, state, n_geocoded_events, gid_1
<!-- head -1 contextual_validators.csv -->. `validator_class`:
broad_impact = 29.372, physical_occurrence = 29.372
<!-- cut -d',' -f5 contextual_validators.csv | sort | uniq -c -->.
`state`: Corroborated = 10.430, No Record = 9.180, Not Applicable =
39.134 <!-- cut -d',' -f8 contextual_validators.csv | sort | uniq -c -->.
Cruzamento validator_class x state: broad_impact/Corroborated = 8.342,
broad_impact/No Record = 2.117, broad_impact/Not Applicable = 18.913,
physical_occurrence/Corroborated = 2.088, physical_occurrence/No Record
= 7.063, physical_occurrence/Not Applicable = 20.221
<!-- cut -d',' -f5,8 contextual_validators.csv | sort | uniq -c,
2026-09-16 -->. Cobertura: 3 países -- Brazil, India, Portugal
<!-- cut -d',' -f2 contextual_validators.csv | sort -u -->. Esta é a
contagem agregada de todas as linhas, sem quebra por país/hazard, que é
o que o FIGURE/TABLE PLACEHOLDER abaixo ainda pede e não foi extraído
aqui.]

The IBTrACS physical-occurrence validator uses a fixed 100 km
great-circle radius as a proxy for each storm's wind-field extent, not
each storm's own recorded per-quadrant wind radius (those fields exist in
IBTrACS but have large, non-random coverage gaps across agencies and
decades); the radius was deliberately set at the conservative, small end
of published 34-kt wind-radius climatology so the validator under-claims
rather than over-claims corroboration. Any validator-overlay result
should be read as "plausibly consistent with a fixed-radius proxy," not
as ground-truth confirmation of a storm's wind field at the asset.

```
[FIGURE/TABLE PLACEHOLDER: Validator overlay summary table (Corroborated / No Record / Not Applicable counts, by validator type, hazard, country) | Source: contextual_validators.py output, per GEAR_v3_work_plan.md Phase 7.3 | Caption draft: Count and fraction of applicable plants in each of the three validator states (Corroborated / No Record / Not Applicable) for the physical-occurrence (IBTrACS, wind/cyclone) and broad-impact (EM-DAT, drought/extreme temperature/flood/storm) validator classes, by country and hazard. A broad-impact "No Record" state is explicitly distinguished from a physical-occurrence "No Record" state in both this table's schema and its caption text — neither is interpreted as "no hazard occurred" (Methods Section 7 / work-plan Phase 5.3). | Status: pending Phase 7 implementation (validator match logic is closed for IBTrACS per docs/LIMITATIONS.md, "2026-09-15 — IBTrACS physical-occurrence validator," but a full production join against final asset-level risk tables and its rendered figure/table asset have not yet been produced/committed)]
```

---

## 7. Normalization provenance and threshold tier-provenance tables

Two reusable reference tables are planned per the Phase 7 work plan,
distinct from any result panel above: the FROZEN_BOUNDS origin table
(every hazard's pooled-sample minimum/maximum, tier, skewness, and
transform, Methods Section 3.1) and a threshold tier-provenance table
(every hazard's Tier 1/Tier 3 classification and basis, Methods Section
5). Both are structural/methods-documentation tables rather than
country/scenario results, but are listed here since Phase 7 specifies
them as direct article/appendix assets.

```
[FIGURE/TABLE PLACEHOLDER: FROZEN_BOUNDS origin table (variable, lower bound, upper bound, origin, tier, skewness, Shapiro-Wilk diagnostic, transform applied), one row per hazard with a processed raster | Source: src/index/normalization.py, per GEAR_v3_work_plan.md Phase 7.4 | Caption draft: Provenance table for every Min-Max normalization bound used in this framework (FROZEN_BOUNDS), reporting each hazard's pooled empirical sample minimum/maximum (no percentile trim), evidence tier, measured Fisher-Pearson skewness (the deciding classification statistic), the Shapiro-Wilk diagnostic (reported alongside, not decisive), and the resulting transform (direct Min-Max or -ln(1-x)). Bounds are pooled across all three countries jointly, never per country; Extreme Heat/Drought/Extreme Precipitation bounds are computed per GCM, water-stress-family and Extreme Wind bounds carry no GCM axis. | Status: pending Phase 7 implementation]

[FIGURE/TABLE PLACEHOLDER: Threshold tier-provenance table (hazard, bucket, tier, basis, absolute vs. sample-relative), one row per hazard/bucket combination in every H_b | Source: consolidated from risk_bands.py threshold definitions, per GEAR_v3_work_plan.md Phase 7.4 | Caption draft: Evidence-tier provenance for every RiskBand classification threshold used in this framework, one row per hazard/bucket combination, reporting the tier (1 = absolute literature/standard-derived cutoff; 3 = sample-relative percentile cutoff, no absolute physical threshold) and its basis (e.g. WRI Aqueduct absolute cutoffs for Water Stress; IEC turbine cut-out speed for Wind-bucket Extreme Wind; pooled P75/P90/P95 percentiles for all remaining Tier 3 rows). No threshold in this framework is untagged. | Status: pending Phase 7 implementation]
```

---

## Notes on claims not made in this draft

Several claims were considered while drafting this chapter and
deliberately not stated as results, because no committed,
`docs/DECISIONS.md`-sourced number supports them at the country/bucket
granularity a Results sentence would need:

- Any specific RiskBand or PSAE distribution number (e.g. "X% of Thermal
  capacity in India is classified EXTREME under SSP5-8.5") — Phase 4's
  closure in `docs/DECISIONS.md` covers the PSAE input-mapping and
  complete-case design, not a production-scale numeric run; no such
  number is on record.
- Any specific Risk_i,h asset ranking or top-N list — not yet computed at
  production scale; only the pooled, capacity-weighted mean and its
  Sobol/general-MC sensitivity behavior are on record (Section 4).
- Any validator-overlay count beyond the two qualitative, real examples
  cited in Section 6 (Brazil's single Hurricane Catarina match; Portugal's
  five named storms) — these are real and DECISIONS.md/LIMITATIONS.md-
  sourced, but a full production join producing per-country/hazard
  Corroborated/No Record counts has not been run.
- Any claim that Extreme Wind's scenario-invariant Risk_i,h value has
  itself been computed for real plants — per `docs/LIMITATIONS.md`,
  "2026-09-14 — Extreme Wind: ERA5 gust acquisition complete... Risk_i,h
  gap unchanged, still open," acquisition is complete for all three
  countries but the Risk_i,h integration step (`compute_mean_annual_max_
  gust()` and wiring `wind` into `HAZARD_TERMS`) had not yet been run as
  of that entry's date; this draft states the structural
  (SSP-invariance) fact, sourced to Methods/LIMITATIONS, without implying
  the underlying Risk_i,h numbers already exist.

---

## Known Issues

### Item 1 (Correlation Gate) — ANOMALIA IDENTIFICADA

`data/outputs/results_draft/MANIFEST.md` linha 30 afirma "12 gated cells
failed the |r|<0.80 threshold (expected 0)", mas
`data/outputs/tables/correlation_gate.csv` verificado em 2026-09-16
mostra:
- 48 pares gated
- `gate_verdict` = 0 "fail" (zero falhas)
- 36 pass + 6 report_only + 14 não-gated (linhas `pooled`, sem
  `gate_verdict` atribuído)

**Ação pendente:** Verificar se a nota do MANIFEST é erro de geração ou
artefato de rodada anterior. Não citar Item 1 do MANIFEST como fonte até
resolver esta inconsistência.
