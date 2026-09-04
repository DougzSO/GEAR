# GEAR Framework — ARCHITECTURE.md

## Propósito deste documento

Especifica o que o GEAR fará: escopo, o score de risco (CCRS), pesos,
fatores de condição do ativo (idade, evento) e incerteza. As decisões aqui
registradas estão tomadas. Os itens de **verificação pós-dados** (V1–V6),
que só podiam ser resolvidos após a reconstrução da camada de aquisição e a
inspeção dos dados reais, estão **todos fechados** (V5 fechado em
2026-09-03). O desenho do CCRS (Seção 5) está fechado e registrado em
`docs/DECISIONS.md`.

The index layer is now implemented and committed: `src/index/ccrs_calculator.py`
(T1, the Hazard term and the frozen global Min-Max bounds), `src/index/age_factor.py`
(T2), `src/index/event_multiplier.py` (T3), `src/index/risk_bands.py` (T4) and
`src/index/ccrs_report.py` (T5/T6, the multiplicative assembly and the
per-country capacity-share report) — see `docs/DECISIONS.md` for the closing
entries and `analysis/climate_risk_score_spec.md` for the full derivations.
Only the Monte Carlo wrapper (Section 8) and spec items F/I/J (Section 10)
remain unimplemented.

---

## 1. Pergunta de pesquisa

Qual é o nível de exposição ao risco climático do sistema elétrico
nacional — no Brasil, em Portugal e na Índia — e como ele se compara
dentro de cada país e entre os três países, sob trajetórias contrastantes
de emissões?

O produto final é um sinal comparativo interpretável para tomadores de
decisão, reguladores, investidores e atores da sociedade civil — não dados
brutos de hazard.

---

## 2. Escopo

- **Unidade de análise:** planta de geração elétrica individual, agregada
  a partir de registros por unidade.
- **Países:** Brasil, Portugal e Índia — escolhidos por contrastes em mix
  tecnológico, concentração de portfólio e regime hidroclimático.
- **Base de ativos:** Global Energy Monitor Global Integrated Power
  Tracker, snapshot manual versionado e datado. Apenas ativos com
  `Status == "operating"` entram no pipeline.
- **Limiar de capacidade:** os limiares nativos do GEM por tecnologia são
  mantidos sem modificação (hidro 45 MW, eólica 10 MW, solar 20 MW
  utilitário ou 1 MW distribuído). Essa heterogeneidade é declarada
  explicitamente no manuscrito em vez de ser corrigida por um limiar
  uniforme artificial.
- **Cenários de emissão:** SSP1-2.6 e SSP5-8.5 como extremos; SSP3-7.0
  como cenário intermediário (ver Seção 3 e item V3, RESOLVIDO).
- **Horizonte temporal:** 2041–2070, representado pelo ponto médio 2050.
- **Hazards:** estresse hídrico e calor extremo. SLR está fora do escopo
  ativo (ver Seção 3).

---

## 3. Hazards: estresse hídrico e calor extremo

SLR foi retirado do escopo ativo. A razão não é negar o risco: Brasil e
Índia têm ativos costeiros genuinamente expostos a inundação e ressaca. A
razão é que a frota estudada é esmagadoramente terrestre e interior, e a
base empírica disponível não sustenta coeficientes defensáveis por
tecnologia para esse hazard neste escopo. SLR é declarado no manuscrito
como limite de escopo e trabalho futuro explícito — não omitido
silenciosamente.

The two active hazards and their data sources (this paragraph and the table
have been updated to English to reflect the closed V3/V4 decisions; the SLR
rationale above is unchanged and stays in Portuguese):

| Hazard | Source | Scenarios | Raw unit |
|---|---|---|---|
| Water stress | WRI Aqueduct 4.0, via Google Earth Engine | `bau` (SSP3-7.0), `opt` (SSP1-2.6), `pes` (SSP5-8.5) | `consumption_to_availability_ratio` |
| Extreme heat | Copernicus CDS, CMIP6 `gfdl_esm4` + `miroc6` | `ssp126`, `ssp370`, `ssp585` | days/year with tasmax > 40 °C |

The Aqueduct `bau` scenario (SSP3-7.0) now has a heat counterpart: daily
`tasmax` for `ssp370` is on the CDS catalogue for both GCMs over 2041-2070,
so SSP3-7.0 enters the active scenario set as the intermediate trajectory
(see Post-data verification items, V3 — RESOLVED). Implementation state:
`config.CMIP6_SCENARIOS` holds `["ssp126", "ssp585", "ssp370"]` and
`config.CMIP6_SOURCE_ID_CDS` holds `["gfdl_esm4", "miroc6"]`; all three
scenarios for both GCMs have been downloaded and processed.

---

## 4. Second GCM — mandatory sensitivity check

(This section has been updated to English to reflect the closed V4
decision.)

A second CMIP6 model is mandatory as a sensitivity check on the
extreme-heat rasters, not optional. `cds_tasmax_downloader.py` and
`config.py` support a configurable list of `source_id` models for the
`ssp126` / `ssp585` (and now `ssp370`) scenarios.

**RESOLVED (V4):** the second model is `MIROC6`, covering the three
countries — selected for the greatest structural divergence from GFDL-ESM4.
IPSL-CM6A-LR was excluded (no ssp126/ssp585 on the CDS catalogue) and
CNRM-CM6-1 was passed over (typically `r1i1p1f2`, which would break variant
parity with the downloaded `gfdl_esm4` at `r1i1p1f1`); MPI-ESM1-2-LR is the
fallback. See `docs/DECISIONS.md` and `analysis/gcm_catalog_check.md`. Both
`gfdl_esm4` and `miroc6` rasters exist on disk (all three scenarios, three
countries); MIROC6's realisation member is confirmed `r1i1p1f1` (grid `gn`).

---

## 5. Index architecture — the Climate Change Risk Score (CCRS)

*(This section was rewritten in English on 2026-09-03 when the CCRS replaced
the SCI/NAES design. The original architecture is kept as a historical note
in §5.6.)*

One score. A single continuous **Climate Change Risk Score (CCRS)** per plant
per scenario, on one cross-country scale, replaces the two
non-interchangeable outputs of the original design (within-country SCI,
cross-country NAES). Capacity is **not** in the per-plant score; it enters
only at the per-country reporting roll-up (§5.5).

Closed design of record: `analysis/climate_risk_score_spec.md`. This section
is the ARCHITECTURE-level summary; the spec carries the full derivations and
`docs/DECISIONS.md` the decision history.

### 5.1 The numeric score

For plant `i` under scenario `s`:

$$CCRS_{i,s} = Hazard_{i,s} \times age\_factor_i \times EventMultiplier_{c(i)}$$

$$Hazard_{i,s} = w_{water}[bucket_i]\cdot water\_sub_{i,s}
             + w_{heat}[bucket_i]\cdot T_{log}(HeatStress^{raw}_{i,s})
             + w_{drought}[bucket_i]\cdot T_{log}(DroughtFreq^{raw}_{i,s})$$

$$water\_sub_{i,s} = 0.4164\cdot T_{log}(WaterStress^{raw}_{i,s})
                  + 0.2505\cdot T_{lin}(SeasonalVar^{raw}_{i,s})
                  + 0.3331\cdot T_{lin}(InterannualVar^{raw}_{i,s})$$

- `Tlog(x) = MinMax(log1p(x))`, `Tlin(x) = MinMax(x)`. `log1p` is applied to
  `ws` and `heat` (severe right skew at plant level); `sv`/`iv` are
  near-symmetric and get linear Min-Max only.
- **Min-Max bounds are global** — one fixed `(min, max)` per term over all
  three countries and all three scenarios pooled. No per-country Min-Max
  anywhere in the aggregate. This is the property that makes a CCRS of 0.4
  mean the same exposure in Lisbon and in Chennai — the property NAES had and
  SCI deliberately gave up. For `heat` and `spei` the pair is computed **per
  GCM** — GFDL-ESM4 and MIROC6 never pooled together, applying the §5.4
  no-blend rule to the bounds computation itself, not only to the final
  Hazard value; for `ws`/`sv`/`iv` there is a single pair per term, since the
  water rasters carry no GCM axis. Frozen as `ccrs_calculator.FROZEN_BOUNDS`
  (data snapshot 2026-09-04, extended in place — not redefined — when `spei`
  was added), regression-locked against the data on disk — see
  `docs/DECISIONS.md`, "CCRS global Min-Max bounds: heat per-GCM, water
  GCM-independent" and "SPEI drought term added to Hazard".
- Five hazard terms: `ws` = Aqueduct water stress; `sv`/`iv` = Aqueduct
  seasonal / interannual variability of blue-water supply; `heat` = mean
  days/yr with tasmax > 40 °C; `spei` = `DroughtFreq^{raw}`, mean months/yr
  with SPEI-12 ≤ −1.0 (Thornthwaite PET, `src/processors/spei_processor.py`).
  Water depletion (`wd`) is **excluded** — plant-level Spearman `ws × wd` is
  0.98–0.998, so `wd` carries no independent rank information
  (`analysis/aqueduct_indicator_correlation.md`).
- The within-`water_sub` weights `(0.4164, 0.2505, 0.3331)` are **not** the
  §6.1 magnitude derivation. They come from the WRI Aqueduct 4.0 category
  step widths ($w_k \propto 1/\tau_k$, spec §8.1) — the same weights the
  absolute WaterRiskBand uses. Unchanged by the drought-term addition; never
  renormalised.
- `age_factor_i ≥ 1` (§7.1) and `EventMultiplier_c ≥ 1` (§7.2) **multiply**
  the hazard score; they are not added as terms.

`w_water + w_heat + w_drought = 1` per bucket, `Σ w_k = 1` inside
`water_sub`, and every transformed term is in `[0, 1]`, so `Hazard_i,s ∈
[0, 1]`. It is not re-normalised after the weighted sum.

**Impact of the drought term (added 2026-09-04):** adding `w_drought` and
extending `FROZEN_BOUNDS` changes `Hazard_{i,s}` and therefore `CCRS_{i,s}`
for every plant. Numbers computed after this point are not directly
comparable to any T1–T6 number computed before it — see
`docs/DECISIONS.md`.

### 5.2 Two classification bands

The discrete risk classification is **two independently-cut bands**, not one
band on `CCRS_i,s`. Water and heat rest on very different evidentiary bases;
a single combined band forces the whole classification onto the weaker of
the two (tried and rejected — `analysis/ccrs_band_classification*.py`).

- **WaterRiskBand_i — absolute, WRI-anchored.** A combined water score
  $S_{water,i} = 0.4164\cdot ws^{raw}_i + 0.2505\cdot sv^{raw}_i +
  0.3331\cdot iv^{raw}_i$ (raw values), cut at the value of $S_{water}$ when
  all three indicators sit on the same WRI Aqueduct 4.0 category boundary:
  **0.208 / 0.415 / 0.667 / 1.0** → Low / Low-Medium / Medium-High / High /
  Extremely-High. The `ws` thresholds trace to Raskin et al. 1997 (SEI); the
  `sv`/`iv` CV cutoffs are WRI's own operational values (weaker but
  published — `analysis/absolute_threshold_research.md`).
- **HeatRiskBand_i — sample-relative.** `extreme_heat_days` classified on its
  own at the **pooled p25 / p75 / p95 of this study's plant sample**
  (`analysis/ccrs_preliminary_distribution.md`), GFDL-ESM4 primary. There is
  no published absolute threshold for the annual frequency of 40 °C days —
  this is a declared scope limit (§10), not an implementation flaw.

The per-country report gives **two separate capacity shares** — "% capacity
in [band] water risk" and "% capacity in [band] heat risk" — never summed
into one number.

Implemented in `src/index/risk_bands.py` (both bands, the auxiliary
`WaterRiskBand × HeatRiskBand` contingency table) and reported per country in
`src/index/ccrs_report.py`.

### 5.3 Per-bucket water/heat/drought weights

$(w_{water}, w_{heat}, w_{drought})$ is per technology bucket, closed. The
2-way matrix below was superseded 2026-09-04 by the 3-way one when the SPEI
drought term was integrated (spec item F):

| bucket | `w_water` | `w_heat` | `w_drought` | basis |
|---|---|---|---|---|
| hydro | 0.55 | 0.00 | 0.45 | §6.1 water/heat basis unchanged (no independent heat coefficient). Rescaled to admit a large drought weight: reservoirs are directly exposed to prolonged drought beyond the evaporation channel already inside water stress. |
| thermal | 0.525 | 0.175 | 0.30 | The original `0.75 / 0.25` water/heat ratio (Van Vliet vs. Ibrahim & Attia, §6.1) is preserved, both terms rescaled proportionally to free 0.30 for drought — cooling-water-dependent thermal generation is materially exposed to prolonged drought. |
| wind | 0.00 | 0.95 | 0.05 | §6.1: still no plausible physical water-*stress* mechanism, but not given an absolute zero on drought — a small, non-mechanistic allowance for regional drought-driven system stress. |
| solar | 0.00 | 0.95 | 0.05 | Same reasoning as wind. |

**Origin, explicit:** the drought column is a direct translation of a
qualitative judgment (hydro/thermal water-dependent generation is more
exposed to prolonged drought than to a single hot day; wind/solar are
near-neutral, not absolutely zero), not a formal AHP/pairwise calibration
and not a literature-derived ratio — same transparency standard as
`age_factor.py`'s assumed coal-overhaul cycle. See `docs/DECISIONS.md`.

For `wind`/`solar` the whole water side — `ws`, `sv` **and** `iv` — is
weighted to zero (`sv`/`iv` measure variability of water availability, the
same absent mechanism); the drought side is not zero. These splits replace
the flat `w = 0.25` used in the exploratory diagnostics
(`analysis/ccrs_bucket_weighted_distribution.md`, pre-SPEI) and the earlier
2-way matrix. The thermal triple (and the small wind/solar drought
allowance) remain judgment calls open to Monte Carlo perturbation (§8).

### 5.4 One primary GCM, one sensitivity panel

The heat term is computed for two GCMs; they are **not** an equal-weight
ensemble (§4).

- **GFDL-ESM4 is the primary GCM for every CCRS figure** — numeric score,
  both bands, and any "% of installed capacity in band …" quoted as a
  headline result.
- **MIROC6 is always a sensitivity panel beside the primary result** — an
  extra column or a separate section — **never** averaged or 50/50-blended
  with GFDL-ESM4.
- Why not a blend: for the same physical wind/solar plants the
  bucket-weighted hazard is ~0.006–0.03 under GFDL-ESM4 and saturates near
  ~0.78 under MIROC6 — two orders of magnitude apart
  (`analysis/ccrs_bucket_weighted_distribution.md`). Any average would be an
  inter-model-weighting artifact, not a climate result.

### 5.5 Capacity and the reporting roll-up

Capacity enters only here, never inside `CCRS_i,s`. The per-country base is
the computable base (valid coordinates + `commissioning_year`), the V6
decision, unchanged. The raw-water-layer limitation (Aqueduct sentinel
basins substituted by `country_max`, India most affected) is a declared
manuscript limitation of the cross-country water term. A joint
`WaterRiskBand × HeatRiskBand` capacity cross-tabulation is an auxiliary
output (`analysis/ccrs_final_summary.md`).

The per-country "% capacity by risk band" roll-up (this section) is
implemented in `src/index/ccrs_report.py`, which asserts every row it sums
already is the V6 computable base (`ccrs_calculator.computable_base`) before
summing `capacity_mw` — a hard failure, not a silent fallback, if a raw-fleet
row without `commissioning_year` reaches the sum. `src/index/risk_bands.py`
draws on the same computable base for its own optional per-band capacity
summaries (the WaterRiskBand/HeatRiskBand distributions and contingency
table), so the V6 base is not exclusive to the final report module — both
consumers go through `ccrs_calculator.computable_base`, never raw
`capacity_mw`.

### 5.6 Historical note — the original SCI / NAES architecture

The design of record until 2026-09-03 was two separate, non-interchangeable
outputs:

- **SCI (Spatial Criticality Index)** — within-country ranking,
  $SCI_i = (Risk_i/Risk_{max,c})^{1/3} \times
  (Capacity_i/Capacity_{total,c})^{1/3} \times (1 - Resilience_{norm,i})^{1/3}$,
  per-country Min-Max, with $Risk_i = w_{water}\cdot WaterStress_i +
  w_{heat}\cdot HeatStress_i$ (two terms). The geometric mean was used
  because the capacity-share term's coefficient of variation dominates a
  linear form — that rationale is why capacity was moved *out* of the
  per-plant CCRS entirely rather than kept as a third linear term.
- **NAES (National Aggregate Exposure Score)** — cross-country,
  capacity-weighted sum of the *raw* hazard per country–scenario, never
  through the per-country Min-Max. The CCRS inherits the raw-layer /
  no-per-country-normalisation principle and carries the cross-country role
  NAES had; the standalone NAES metric is replaced by the per-country "%
  capacity by risk band" report.

Replaced by the CCRS — see `docs/DECISIONS.md`, entry "CCRS replaces
SCI/NAES as the unified risk architecture", for the full reason (among them:
SCI's per-country normalisation made the country-uniform `event_factor`
cancel algebraically out of the within-country ranking, so a country-level
disaster signal did no work anywhere in the original outputs).

---

## 6. Derivação de pesos

Um peso ($w_{water}$, $w_{heat}$) é uma fração adimensional que soma 1
dentro de cada bucket tecnológico. Responde: de toda a sensibilidade
climática desta tecnologia, que fração vem de cada hazard?

O coeficiente da literatura (por exemplo, −0,65 %/°C para sensibilidade
solar ao calor) é evidência usada para derivar essa fração — não a fração
em si.

**Por que uma etapa de conversão é necessária:** os coeficientes
encontrados na literatura não são nativamente comparáveis. Alguns são
taxas marginais (perda percentual por grau de aumento de temperatura).
Outros são outcomes totais sob uma condição já severa (perda percentual
de capacidade sob estresse hídrico agudo). Tratar −0,65 e 85 como números
diretamente comparáveis, ou usar qualquer um deles como valor de peso
diretamente, é um erro de categoria.

**Procedimento — normalização por magnitude projetada:** para cada bucket,
projeta-se o impacto de cada hazard sobre o intervalo esperado do hazard
neste estudo, produzindo uma figura de "impacto total esperado" comparável
por hazard. Coeficientes de taxa marginal (calor, majoritariamente) são
multiplicados por um delta de temperatura de referência fixo por
tecnologia. Coeficientes já totais (água, majoritariamente) são usados
diretamente. As magnitudes resultantes são normalizadas dentro do bucket
para somar 1.

O delta de referência é fixo por tecnologia — não recomputado por país
ou cenário. Variação por país e cenário entra pelos dados de hazard,
não pelos pesos. Isso mantém a matriz de pesos estável e auditável.

**Cross-reference — how these coefficients feed the CCRS (added 2026-09-03,
extended to 3-way 2026-09-04).**
The CCRS per-bucket water/heat weights (Section 5.3) were set from the §6.1
matrix by **informed qualitative judgment**, not a mechanical conversion
formula. The magnitude-normalisation procedure above is the framework for
that judgment — e.g. thermal's original `0.75 / 0.25` reflected that Van
Vliet's water figure is a *total-outcome* coefficient roughly an order of
magnitude larger than the *marginal* heat rate — but the exact fractions are
a documented judgment call, flagged for Monte Carlo sensitivity (Section 8),
not the output of an equation. The drought column added 2026-09-04 (`0.45`
hydro, `0.30` thermal, `0.05` wind/solar) is the same kind of judgment call,
not derived from §6.1's magnitude-normalisation procedure (there is no
drought coefficient in the literature comparable in form to the water/heat
ones) — see Section 5.3 and `docs/DECISIONS.md`. Hydro/wind/solar's
water/heat split still traces to the §6.1 "no independent mechanism" rows;
only the drought fraction they carry is new judgment. The within-water
`ws/sv/iv` weights are derived separately, from the WRI Aqueduct 4.0 category
widths (Section 5.1), unaffected by any of this. The `sv`/`iv` hazard terms
themselves are not in the §6.1 matrix — only the water/heat split is.

### 6.1 Matriz de pesos — estado atual das evidências

| Bucket | Hazard | Coeficiente / intervalo | Tipo | Tier | Fonte |
|---|---|---|---|---|---|
| Hidro | Água | 61–74% de redução de capacidade utilizável sob estresse hídrico | Outcome total sob estresse | 1 | Van Vliet et al. (referência [1] na lista do manuscrito) |
| Hidro | Calor | Sem coeficiente independente — mecanismo (evaporação de reservatório) sobrepõe o canal de estresse hídrico já medido | — | 3, justificado por sobreposição | Turner, S. W. D. et al. Hydropower capacity factors trending down in the United States. *Nature Communications*, 2024; Zhao et al. Evaluating Enhanced Reservoir Evaporation Losses From CMIP6-Based Future Projections in the Contiguous United States. *Earth's Future*, 2023 |
| Eólica | Água | Sem mecanismo físico plausível | — | 3 | — |
| Eólica | Calor | Derating por segurança acima de ~40 °C, resposta em forma de degrau tratada como equivalente linear | Taxa marginal (equivalente linear) | 2 | Al-Khayat, M.; Al-Rasheedi, M. A new method for estimating the annual energy production of wind turbines in hot environments. 2024. *(título do periódico a confirmar na fonte primária)* |
| Solar | Água | Sem mecanismo físico plausível | — | 3 | — |
| Solar | Calor | −0,65 %/K de potência; −0,08 %/K de eficiência de conversão; literatura converge entre −0,3 % e −0,65 %/°C | Taxa marginal | 1 | Radziemska, E. The effect of temperature on the power drop in crystalline silicon solar cells. *Renewable Energy*, v. 28, n. 1, p. 1–12, 2003 |
| Thermal | Água | 81–86% de redução de capacidade utilizável sob estresse hídrico | Outcome total sob estresse | 1 | Van Vliet et al. (mesma fonte que hidro–água) |
| Thermal | Calor | −0,12 %/°C a −0,44 %/°C em eficiência ou produção | Taxa marginal | 1 | Ibrahim, S. M. A.; Attia, S. I. The influence of condenser cooling seawater fouling on the thermal performance of a nuclear power plant. *Annals of Nuclear Energy*, v. 76, p. 421–430, 2015. DOI: 10.1016/j.anucene.2014.10.018; Durmayaz, A.; Sogut, O. S. (2006) *(verificação primária pendente — ver nota abaixo)* |

**Nota — verificação bibliográfica pendente (thermal–calor):** Durmayaz, A.
e Sogut, O. S. (2006) são conhecidos apenas via citação secundária. Os
valores exatos do coeficiente e o título completo do artigo primário
precisam ser verificados antes da submissão do manuscrito. Esta
verificação é uma tarefa bibliográfica, não uma decisão metodológica.

**Decisão confirmada:** eólica–calor é tratada como coeficiente linear
equivalente. A resposta real é em forma de degrau; a simplificação é
declarada explicitamente no manuscrito.

**Decisão confirmada:** carvão e outros termoeléctricos são fusionados no
bucket `thermal` para derivação de pesos de água e calor. O mecanismo
físico é o mesmo (dependência de água de refrigeração e sensibilidade
à temperatura dessa água). A fusão cria uma tensão na curva de idade
(`age_factor`), tratada na Seção 7.

---

## 7. Asset-condition factor (age)

*(Rewritten in English on 2026-09-03. The original design multiplied three
sub-factors into a single normalised `Resilience_i`; the CCRS dissolves that
product — see below and `docs/DECISIONS.md`.)*

The original design was
$Resilience_i = \max(age_{factor,i}\times fuel_{factor,i}\times
event_{factor,i},\ 0.1)$, normalised by the empirically observed ceiling
within each country–scenario pair. **That product is dissolved under the
CCRS.** `age_factor` becomes a direct multiplier on `Hazard_i,s` (§7.1),
`event_factor` becomes the separate `EventMultiplier` (§7.2), `fuel_factor`
is removed entirely (§7.3, V5 closed), and the 0.1 floor and per-country
ceiling normalisation are gone. `age_factor` is now the only asset-condition
factor.

**Why the product is dissolved, not just relabelled.** `event_factor` was
country-uniform (every plant in a country shared it) and `fuel_factor` was
bucket-uniform. SCI normalised `Resilience_i` by the per-country ceiling
$\max_{j\in c}Resilience_j$, so the country-uniform `event_factor` appeared
identically in the numerator and the ceiling and **cancelled exactly** out
of `Resilience_norm,i` (modulo the rarely-binding 0.1 floor) — it contributed
nothing to the within-country SCI ranking. NAES used no resilience term at
all. A country-level disaster-frequency signal therefore did no work
anywhere in the original outputs. It only does work on a score that is
**not** per-country normalised — which is what the CCRS aggregate is (§5.1),
so `event_factor` moves out of the resilience product and becomes
`EventMultiplier`, a multiplier on the absolute CCRS score where a
country-uniform factor genuinely shifts that country's plants relative to
the other two.

### 7.1 Age factor (`age_factor`)

`age_factor_i ≥ 1`, a direct multiplier on `Hazard_i,s` (§5.1), increasing
with cumulative age-driven performance loss (a plant that has lost ~20 % to
age → ≈ ×1.2). This is the opposite sign convention to the old
`1 − Resilience_norm`. **Confirmed final** (`docs/DECISIONS.md`, 2026-09-04,
"age_factor: >=1 multiplier via `2 - retention(age)`, with corrected
coal/hydro/wind retention curves (final)"):
`age_factor = 2 - clip(retention(age), 0, 1)`, where `retention(age) ≤ 1` is
the technology's capacity/efficiency retention curve below and
`age = year_target(2050) - commissioning_year`. Observed range on the current
data: 1.0000–1.7480. A plant with a missing `commissioning_year` (~5.6 % of
plants, concentrated in India's wind and solar fleet) gets a neutral
`age_factor` of 1.0 — kept, flagged, never dropped.

Curves per technology (V1 closed, then revised — see `docs/DECISIONS.md`
entries "Age factor for thermal bucket … (V1 closed)" and "Age factor curves
revised with additional literature (V1 revision)"):

| Technology | Curve | Source |
|---|---|---|
| Wind | 0.4 %/yr relative retention rate, applied uniformly to every wind plant (no conditional branch) | Olauson, Edström & Rydén 2017, *Wind Energy* (Swedish fleet); Shin, Ko & Huh 2015; Byrne, Astolfi, Castellani & Hewitt 2020 — midpoint of the 0.3–0.5 %/yr range. The capacity-factor-based form (`retention = 1 - 0.0015·age/CF_initial`) exists in the source as documented dead code, never called: no GEM file carries an initial capacity factor for any of the 1986 wind plants across the three countries |
| Solar | 0.7 %/yr at plant level (0.5 %/yr module physics + soiling / downtime / inverter), compound decay | Deline et al. (NREL) 2020/2024; Boretti & Castellotto 2024 |
| Hydro | 0.55 %/yr (midpoint of "~0.5–0.6 %/yr"), linear | Turner et al. 2024, *Nature Communications* — 23 % cumulative over 610 US plants 1980–2022; only 21 % of that attributable to water availability, keeping this distinct from the water-stress hazard captured separately |
| Coal | 0.25 %/yr heat-rate deterioration, **sawtooth**: decays within an **assumed** 5-year overhaul cycle, recovering 70 % of that cycle's accumulated loss at each cycle boundary (30 % permanent) | IEA/CIAB 2010; Kim & Moon 2012 (500 MW unit); cross-validated by Sagaf 2020 (0.19–0.44 %/yr, two 660 MW units). The 5-year cycle length and the 70 % recovery fraction are a modelling premise, not values from the cited sources — no GEM file carries a per-plant overhaul date; provisional, revisable if one appears |
| Gas / oil-gas | 1.0 (neutral), **provisional** | No literature-backed rate or functional form exists in any project document — the original V1 note of an "efficiency gain with age" (US data 2001–2018) has no citable number attached to it. Pinned neutral until a defensible source is found; a genuinely improving-with-age curve could not be represented under the `age_factor ≥ 1` convention regardless |
| Nuclear | 1.0 (neutral) | licensing- / decommissioning-governed, not gradual physical decay; Blake 1992, Simola 1999 |
| Bioenergy | 1.0 (neutral) | coal-proxy dropped for want of fleet-level longitudinal evidence (V1 revision) |
| Mixed-fuel | average of component curves (capacity-weighted where per-fuel capacity is known; simple average used here — no per-fuel capacity in the source data) | — |

Implemented in `src/index/age_factor.py`.

The `thermal` fusion is kept for the **hazard weights** (§6.1 — shared
cooling-water dependence) but not for `age_factor`, which tracks a
fuel-specific physical process.

### 7.2 Event multiplier (`EventMultiplier`)

`EventMultiplier_c ≥ 1`, built from EM-DAT disaster frequency, **country-
level** (V2 closed — see `docs/DECISIONS.md`), applied as a multiplier on the
CCRS score, not folded into a resilience factor:

$$rate_c = N_{events}(c)\ /\ 124 \quad\text{(events/yr, EM-DAT 1900–2024)}$$
$$EventMultiplier_c = 1 + k\cdot(rate_c / rate_{max}), \qquad k = 0.5$$

with $N_{events}$ = 239 (Brazil) / 38 (Portugal) / 622 (India) — the same
type-filtered eligible counts as V2 — and $rate_{max}$ the highest national
rate (India). The `/124` cancels in the ratio. Values: **Brazil 1.192,
Portugal 1.031, India 1.500**. Every plant in a country shares its country's
value: it shifts a whole country's scores uniformly and does not
differentiate the intra-country ranking. `k` is a judgment-call amplitude
ceiling, flagged for Monte Carlo perturbation (§8), not re-derived from data.
The V2 sub-question (raw count vs rate vs exposure-normalised) is resolved
here in favour of the rate; country-level granularity is unchanged (V2 not
reopened).

Implemented in `src/index/event_multiplier.py`. The regression fixture
recomputes the three values at full precision (Brazil 1.192122, Portugal
1.030547, India 1.500000) against the 1.192/1.031/1.500 figures above —
differences under 0.0005, well inside the 0.01 acceptance threshold (the
published figures are 3-decimal roundings of the recomputed ones).

### 7.3 Fuel factor (`fuel_factor`) — removed (V5 closed)

`fuel_factor` was meant to carry per-technology structural robustness not
captured by age or by the measured hazard. Its original justification leaned
partly on SLR, which is out of active scope. **It is removed entirely** —
see `docs/DECISIONS.md`, entry "fuel_factor removed from resilience formula
(V5 closed)". No bucket receives a `fuel_factor`, and `CCRS_i,s` (Section 5)
carries no such term; only `age_factor` and `EventMultiplier` multiply the
hazard score.

The V5 investigation covered all four buckets — thermal cooling-system type,
hydro storage / regularisation, wind and solar component thermal robustness.
Every candidate mechanism is physically real but fails the test of being
defensible, codifiable, and independent of the water/heat hazard weights
already captured: thermal cooling type governs *how* a plant responds to
`WaterStress_i` rather than adding a separable quantity (and coverage data
is not public for the three countries); hydro storage would need
basin-specific hydrological simulation outside this scope; wind and solar
component differences lack public normalised degradation datasets.

This is a closed decision. If data of the required kind appears later,
adding a structural-robustness factor would be a **new** decision — not a
reopening of V5.

---

## 8. Uncertainty — Monte Carlo

*(Rewritten in English on 2026-09-03 to reflect the CCRS. N = 1000 and the
±10/20/30 % structure are unchanged.)*

N = 1000 iterations, perturbing the free parameters at ±10 %, ±20 % and
±30 %. Perturbation is uniform across confidence tiers, not tier-dependent —
a tier already encodes confidence at derivation time; varying the
perturbation magnitude by tier as well would test two effects through one
parameter.

Free parameters: the thermal `(w_water, w_heat, w_drought)` triple
(`0.525 / 0.175 / 0.30`, §5.3, since the 2026-09-04 SPEI integration) and the
`EventMultiplier` amplitude `k` (`0.5`, §7.2) — judgment calls rather than
derivations — plus `age_factor`, and any free parameter of the weight matrix
(§6.1) once it is derived. **Not** perturbed: the within-water `ws/sv/iv`
weights (fixed by the WRI category widths, unaffected by the drought
addition), every entry of `FROZEN_BOUNDS` (including `spei`), the
`risk_bands.py` cuts, and the `EventMultiplier` event base (`N_events`
counts, India as `rate_max`).

The CCRS and both per-country band reports are recomputed inside each
iteration, giving a distribution per plant and per country×scenario band
share rather than a point estimate.

---

## 9. Post-data verification items

> Section language note: all items V1–V6 are resolved and rewritten in
> English pointing to their `docs/DECISIONS.md` entries (V1 was resolved,
> then revised; V5 was closed on 2026-09-03 — `fuel_factor` removed). The
> original observation/criterion text is kept beneath each as the record of
> what drove the decision.

These items could not be settled by upfront reasoning. Each had an explicit
decision criterion to apply after the acquisition/processing layer was
rebuilt and the real data inspected. **All six are now resolved;** the CCRS
index design (Section 5) is closed and recorded in `docs/DECISIONS.md`, and
the index code implementing it is written and committed (`src/index/`, see
"Propósito deste documento" above).

**V1 — Age curve for the thermal bucket**
- **Status: RESOLVED, then REVISED.** Closed by `docs/DECISIONS.md` entry
  "Age factor for thermal bucket: fuel-specific curves (V1 closed)"
  (sub-curves per `fuel_type` within thermal; the thermal fusion is kept
  only for the water/heat hazard weights). **Revised 2026-09-03** by the
  follow-up entry "Age factor curves revised with additional literature
  (V1 revision)": coal cross-validated (Sagaf 2020), wind given a verified
  rate (Olauson et al. 2017) replacing a placeholder, solar a plant-level
  rate, bioenergy moved from the coal proxy to a neutral 1.0. The current
  curves — coal/gas/nuclear/bioenergy/wind/solar/hydro/mixed — are the table
  in Section 7.1; use that table, not the original V1 entry, as the live
  reference. **Confirmed final 2026-09-04** (`docs/DECISIONS.md`, "age_factor:
  >=1 multiplier via `2 - retention(age)`, with corrected coal/hydro/wind
  retention curves (final)"): the `≥ 1` sign convention, the coal
  overhaul-cycle sawtooth, wind's fixed 0.4 %/yr rate (the `CF_initial` form
  kept only as dead code) and hydro's 0.55 %/yr (no 0.79 scaling) are the
  current, non-reopened state — Section 7.1 reflects it. Implemented in
  `src/index/age_factor.py`.
- *Original observation (kept as historical context):* distribution of coal
  versus natural gas within the `thermal` bucket per country, in
  `gem_validated_plants_{country}.csv`.
- *Original criterion:* if the coal/gas ratio is homogeneous enough across
  the three countries that an average curve does not invert rankings, a
  documented average curve is acceptable. If the cross-country
  heterogeneity is large enough to invert rankings, the thermal bucket gets
  fuel-specific sub-curves for the age factor only, keeping the fusion in
  the hazard weights.

**V2 — Event factor (replacing the fixed 1.0)**
- **Status: RESOLVED.** See `docs/DECISIONS.md`, entry "Event factor:
  country-level EM-DAT frequency (V2 closed)". Country-level factor, not
  state/district -- sub-national administrative coverage is insufficient
  (50-54% of events, ~30% at adm1).
- *Original observation (kept as historical context):* EM-DAT coverage and
  geocoding for Brazil, Portugal and India -- number of events with a usable
  administrative location versus the total eligible under the inclusion
  criteria.
- *Original criterion:* if coverage is sufficient to build a factor at an
  administrative level (state/district), use that level. If coverage only
  supports the country level, use country. If coverage is insufficient for
  any level, keep 1.0 and declare it as a limitation.

**V3 — SSP3-7.0 as an intermediate scenario**
- **Status: RESOLVED.** See `docs/DECISIONS.md`, entry "Second CMIP6 GCM:
  MIROC6 (V4 closed); SSP3-7.0 added as intermediate scenario (V3 closed)".
  Daily `tasmax` for SSP3-7.0 is on the CDS catalogue for both `gfdl_esm4`
  and MIROC6 over 2041-2070, so it is added as a third scenario for both
  GCMs, paired with the Aqueduct `bau` label.
- *Original check (kept as historical context):* availability of
  `gfdl_esm4` with `ssp370` on the Copernicus CDS (API catalogue query, not
  data analysis). Check the second GCM chosen in V4 as well.
- *Original criterion:* if available for both GCMs, include SSP3-7.0 and
  align it with the already-available Aqueduct `bau` scenario. If available
  for only one GCM, judge whether the misalignment is acceptable or SSP3-7.0
  stays out. Inclusion changes the heat Min-Max pool from 2 to 3 scenarios,
  changing the normalisation denominator for every pixel -- this consequence
  must be weighed in the decision.

**V4 — Choice and coverage of the second GCM**
- **Status: RESOLVED.** See `docs/DECISIONS.md`, entry "Second CMIP6 GCM:
  MIROC6 (V4 closed)". MIROC6 chosen; IPSL-CM6A-LR excluded for missing
  ssp126/ssp585 on the CDS catalogue; CNRM-CM6-1 passed over for its
  `r1i1p1f2` variant, divergent from `gfdl_esm4` (`r1i1p1f1`).
- *Original check (kept as historical context):* which CMIP6 models have
  `ssp126` and `ssp585` available on the Copernicus CDS for the three
  countries, with resolution and period compatible with the existing
  pipeline.
- *Original criterion:* select the model with the greatest structural
  divergence from `GFDL-ESM4` (different convection-parameterisation family
  or hydrological cycle), covering the three countries. If no model covers
  all three at equivalent quality, cover only the highest heat-exposure
  cases and declare the limitation.

**V5 — Fuel factor (`fuel_factor`)**
- **Status: RESOLVED.** See `docs/DECISIONS.md`, entry "fuel_factor removed
  from resilience formula (V5 closed)". `fuel_factor` is removed entirely —
  no bucket receives one and `CCRS_i,s` carries no such term. The per-bucket
  investigation (thermal cooling type, hydro storage/regularisation,
  wind/solar component robustness) found every candidate mechanism either
  not separable from the water/heat hazard weights already captured, or
  lacking public codifiable data for the three countries. The current
  design has only `age_factor` and `EventMultiplier` as multipliers on the
  hazard score (Section 7).
- *Original review target (kept as historical context):* per-technology
  structural-robustness literature for the water and heat hazards,
  independent of SLR.
- *Original criterion:* if defensible values could be derived for every
  bucket (`hydro`, `wind`, `solar`, `thermal`) from water and heat alone,
  keep the factor with the new values; if not, remove it and declare the
  simplification in the manuscript. The "remove it" branch applied.

**V6 — Per-country capacity roll-up base (computable base vs. total capacity)**
- **Status: RESOLVED.** See `docs/DECISIONS.md`, entry "NAES/SCI
  computable-capacity denominator (V6 closed)". Asymmetry of 3.76
  percentage points (Brazil 98.22% / Portugal 99.59% / India 95.83%),
  below the 5-point threshold -- declared as a manuscript footnote, no
  sensitivity check run. Under the CCRS this base is the denominator of the
  per-country "% capacity by risk band" report (Section 5.5); the decision
  is unchanged, only the name "NAES denominator" is superseded.
- *Original observation (kept as historical context):* fraction of GEM
  assets with valid coordinates and a `commissioning_year` over total
  declared capacity, per country.
- *Original criterion:* if the computable fraction is consistently high and
  symmetric across the three countries (difference < 5 percentage points),
  the limitation is declared in a footnote. If the cross-country asymmetry
  is larger, a sensitivity check with an alternative denominator (total
  declared capacity, imputing the country-mean hazard for assets without
  coordinates) is run and reported as a secondary result.

---

## 10. What GEAR does not do (declared scope limits)

*(Translated to English on 2026-09-03; the HeatRiskBand limit was added in
the same pass.)*

These limits are declared in the manuscript, not omitted.

- **SLR:** excluded for lack of a defensible empirical basis for the
  land-based fleet studied. A natural extension once per-technology
  coefficients for coastal flooding and storm surge are available.
- **Planned and under-construction assets:** only operating assets enter the
  main pipeline. Announced or under-construction assets are not included.
- **Transmission and distribution:** generation only. The exposure of
  transmission lines and substations is not modelled.
- **Acute extreme events:** the framework models chronic exposure (2041–2070
  mean conditions). Tail events (single heatwaves, extreme interannual
  droughts) are not captured.
- **GCM bias correction:** the heat rasters use model output directly, with
  no systematic bias correction. Sensitivity to that artifact is partly
  captured by the mandatory second GCM (MIROC6), not eliminated.
- **HeatRiskBand absolute threshold:** there is no published absolute
  threshold that classifies the annual frequency of days above 40 °C into
  risk categories (the literature classifies single-day intensity, WBGT /
  ISO 7243, or the presence/absence of a temperature threshold, not
  cumulative annual frequency; heat-mortality epidemiology deliberately
  avoids fixed cuts because they do not carry across baseline climates).
  `HeatRiskBand` (Section 5.2) therefore uses cuts relative to this study's
  own plant sample (pooled percentiles) and is sensitive to the GCM used
  (~10–100× difference between GFDL-ESM4 and MIROC6 in the underlying
  values). `WaterRiskBand` is not affected — it is cut at absolute
  WRI Aqueduct 4.0 thresholds. Declared limitation, not an implementation
  flaw — it is the state of the art for this indicator.
- **Adaptive capacity:** `age_factor` and `EventMultiplier` capture
  structural characteristics of the asset (age, and the country's disaster
  history) — not the prospective adaptive capacity of operators or
  regulators. The CCRS measures hazard × exposure × `age_factor`, a
  *partial* vulnerability proxy, not the full hazard × exposure ×
  vulnerability triangle.