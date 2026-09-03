# GEAR Framework — ARCHITECTURE.md

## Propósito deste documento

Especifica o que o GEAR fará: escopo, índices, pesos, resiliência e
incerteza. As decisões aqui registradas estão tomadas, exceto onde
explicitamente marcadas como **verificação pós-dados** — itens que só
podem ser resolvidos após a reconstrução da camada de aquisição e
processamento e visualização dos dados reais. Nenhum código de índice
deve ser escrito antes desse revisit.

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
(see Post-data verification items, V3 — RESOLVED). Implementation note:
`config.CMIP6_SCENARIOS` and `config.CMIP6_SOURCE_ID_CDS` still hold the
pre-decision values (`ssp126`/`ssp585`, `gfdl_esm4` only); the third
scenario and MIROC6 are wired in when the index layer is built.

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
fallback. See `docs/DECISIONS.md` and `analysis/gcm_catalog_check.md`. Only
`gfdl_esm4` rasters exist on disk today; the MIROC6 download is part of the
index-layer implementation.

---

## 5. Arquitetura de índices

Dois outputs, separados e não intercambiáveis.

### 5.1 Spatial Criticality Index (SCI)

Ranking dentro do país. Compara plantas apenas contra outras plantas do
mesmo país.

$$SCI_i = \left(\frac{Risk_i}{Risk_{max,c}}\right)^{1/3}
\times \left(\frac{Capacity_i}{Capacity_{total,c}}\right)^{1/3}
\times \left(1 - Resilience_{norm,i}\right)^{1/3}$$

$$Risk_i = w_{water} \cdot WaterStress_i + w_{heat} \cdot HeatStress_i$$

A média geométrica é usada porque o coeficiente de variação do termo de
participação de capacidade é várias vezes maior que o dos outros dois
termos numa formulação linear, o que faria esse termo dominar a cauda
superior do ranking de forma desproporcional.

$Capacity_{total,c}$ é calculado sobre a base de ativos com SCI
computável (coordenadas válidas e ano de comissionamento disponível),
não sobre a capacidade total declarada do portfólio.

### 5.2 National Aggregate Exposure Score (NAES)

Comparação entre países. Construído inteiramente sobre valores brutos
de hazard — nunca passa pela normalização Min-Max por país que torna o
SCI intrapaís.

$$NAES_{c,s} = \sum_{i \in c}
\left(\frac{Capacity_i}{Capacity_{total,c}}\right)
\times \left(w_{water} \cdot WaterStress^{raw}_{i,s}
+ w_{heat} \cdot HeatStress^{raw}_{i,s}\right)$$

$Capacity_{total,c}$ usa a mesma base computável do SCI, pela mesma
razão: valores brutos de hazard não podem ser produzidos para ativos sem
coordenadas ou ano de comissionamento.

O NAES é recomputado dentro de cada iteração de Monte Carlo, produzindo
uma distribuição por par país–cenário em vez de uma estimativa pontual.

A limitação do raster bruto de água (bacias sentinela substituídas por
`country_max`, Índia mais afetada) é declarada explicitamente no
manuscrito como restrição conhecida do NAES.

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
da resiliência, tratada na Seção 7.

---

## 7. Fator de resiliência

$$Resilience_i = \max\!\left(
age_{factor,i} \times fuel_{factor,i} \times event_{factor,i},\ 0.1
\right)$$

Normalizado pelo teto empiricamente observado dentro de cada par
país–cenário, recomputado dentro de cada iteração de Monte Carlo.

### 7.1 Fator de idade (`age_factor`)

| Tecnologia | Curva | Fonte |
|---|---|---|
| Eólica | 1,6 %/ano | Literatura existente, retida |
| Solar | 0,6 %/ano | Literatura existente, retida |
| Hidro | ~0,5–0,6 %/ano | Turner, S. W. D. et al. *Nature Communications*, 2024 — declínio cumulativo de 23% em 610 plantas nos EUA entre 1980 e 2022; apenas 21% desse declínio é atribuível à disponibilidade hídrica, mantendo este fator distinto do hazard de estresse hídrico já capturado separadamente |
| Thermal | *Item V1 — RESOLVIDO: sub-curvas por `fuel_type` (ver Seção 9 e `docs/DECISIONS.md`)* | Usinas a carvão perdem eficiência com a idade; usinas a gás natural ganham eficiência com a idade no mesmo período (estudo US, 2001–2018) — sinais opostos dentro do bucket fusionado |

### 7.2 Event factor (`event_factor`)

(This subsection has been updated to English to reflect the closed V2
decision.)

Historical placeholder: fixed at 1.0 for every asset (EM-DAT point
geocoding covers only ~10.7% of events in the study region).

**RESOLVED (V2):** replaced by a per-country event-frequency factor built
from EM-DAT — **not** a state/district factor. Structured sub-national
administrative data is present for only 50-54% of events per country and
splits low and evenly between adm1/state (~30-37%) and adm2/district
(~18-30%), too sparse to support a defensible finer factor; building one
would drop roughly two-thirds of events from its evidence base. This trades
spatial granularity (assets within one country are not differentiated) for
full coverage instead of a small, unrepresentative sample. See
`docs/DECISIONS.md` and `analysis/emdat_coverage_diagnostics.md`. The exact
form of the country factor (raw count, capacity- or exposure-normalised, or
a rate over the 1900-2024 archive span) is left to the `event_factor`
implementation, once V1-V6 are all closed.

### 7.3 Fator de combustível (`fuel_factor`)

Representa diferenças de robustez estrutural por tecnologia não capturadas
pela idade nem pelo hazard diretamente medido. A justificativa original
dos valores deste fator foi construída parcialmente com referência ao SLR,
que está fora do escopo ativo. Os valores precisam ser revisados e
rejustificados exclusivamente a partir dos hazards água e calor, ou o
fator precisa ser removido se essa justificativa não puder ser construída.

Esta revisão é verificação pós-dados (item V5).

---

## 8. Incerteza — Monte Carlo

N = 1.000 iterações, perturbando pesos calibrados e subfatores de
resiliência em magnitudes de ±10 %, ±20 % e ±30 %.

A perturbação é uniforme entre tiers, não tier-dependente. O tier já
codifica o nível de confiança no momento da derivação do peso; variar
também a magnitude de perturbação por tier testaria dois efeitos através
de um único parâmetro.

O NAES é recomputado dentro de cada iteração — seu intervalo de confiança
reflete a mesma incerteza de parâmetros que a métrica de estabilidade de
ranking dos ativos.

---

## 9. Post-data verification items

> Section language note: items V1–V4 and V6 are resolved and have been
> rewritten in English pointing to their `docs/DECISIONS.md` entries; the
> original observation/criterion text is kept beneath each as the record of
> what drove the decision. **V5 is still open and is left exactly as it was,
> in Portuguese.**

These items could not be settled by upfront reasoning. Each had an explicit
decision criterion to apply after the acquisition/processing layer was
rebuilt and the real data inspected. No index code is written until all are
resolved.

**V1 — Age curve for the thermal bucket**
- **Status: RESOLVED.** See `docs/DECISIONS.md`, entry "Age factor for
  thermal bucket: fuel-specific curves (V1 closed)". Sub-curves per
  `fuel_type` within thermal (coal, gas, nuclear, bioenergy, mixed); the
  thermal fusion is kept only for the water/heat hazard weights.
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

**V5 — Fator de combustível (`fuel_factor`)**
- **O que revisar:** literatura de robustez estrutural por tecnologia
  para os hazards água e calor, independentemente de SLR.
- **Critério:** se valores defensáveis puderem ser derivados para cada
  bucket (`hydro`, `wind`, `solar`, `thermal`) a partir exclusivamente
  de água e calor, o fator é mantido com os novos valores. Se a revisão
  não produzir justificativa defensável, o fator é removido da fórmula
  de resiliência e a simplificação é declarada no manuscrito.

**V6 — NAES denominator (computable base vs. total capacity)**
- **Status: RESOLVED.** See `docs/DECISIONS.md`, entry "NAES/SCI
  computable-capacity denominator (V6 closed)". Asymmetry of 3.76
  percentage points (Brazil 98.22% / Portugal 99.59% / India 95.83%),
  below the 5-point threshold -- declared as a manuscript footnote, no
  sensitivity check run.
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

## 10. O que o GEAR não faz (limites de escopo declarados)

Estes limites são declarados no manuscrito, não omitidos.

- **SLR:** excluído por falta de base empírica defensável para a frota
  terrestre estudada. Extensão natural quando coeficientes por tecnologia
  para inundação costeira e ressaca estiverem disponíveis.
- **Ativos planejados e em construção:** apenas ativos operacionais
  entram no pipeline principal. Ativos anunciados ou em construção não
  são incluídos.
- **Transmissão e distribuição:** apenas geração. A exposição de linhas
  de transmissão e subestações não é modelada.
- **Eventos extremos agudos:** o framework modela exposição crônica
  (condições médias 2041–2070). Eventos de cauda (ondas de calor
  pontuais, secas extremas interanuais) não são capturados.
- **Bias correction do GCM:** os rasters de calor usam a saída do modelo
  diretamente, sem correção de viés sistemático. A sensibilidade a esse
  artefato é parcialmente capturada pelo segundo GCM obrigatório, mas
  não eliminada.
- **Capacidade de adaptação:** o fator de resiliência captura
  características estruturais do ativo (idade, histórico de eventos),
  não capacidade prospectiva de adaptação de operadores ou reguladores.