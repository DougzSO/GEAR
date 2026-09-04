# 01 — Visão geral

Pipeline Python de dados geoespaciais/climáticos para o artigo GEAR (risco
climático de infraestrutura de geração elétrica em Brasil, Portugal e Índia).
Roda localmente, sem frontend, sem CI.

## Fases

- **Camada de aquisição/processamento (herdada, reconstruída):** downloaders
  de fronteiras, clima (calor extremo e estresse hídrico), eventos EM-DAT, e
  validação/agregação do snapshot manual do GEM. Detalhe da herança em
  `docs/INVENTORY.md`.
- **Camada de índice (reconstruída do zero, ainda não iniciada):** o
  Climate Change Risk Score (CCRS) — score numérico único por planta e
  cenário (`Hazard_i,s × age_factor × EventMultiplier`), duas bandas de
  risco (WaterRiskBand absoluto WRI, HeatRiskBand relativo à amostra),
  pesos água/calor por bucket tecnológico, e Monte Carlo. Substitui o
  desenho SCI/NAES + resiliência de 3 fatores original. Especificação em
  `docs/ARCHITECTURE.md` Seção 5 e `analysis/climate_risk_score_spec.md`.
  As verificações pós-dados V1–V6 (`ARCHITECTURE.md` Seção 9) estão **todas
  fechadas**. Já escritos: `src/index/ccrs_calculator.py` (termo
  `Hazard_{i,s}`), `src/index/risk_bands.py` (WaterRiskBand + HeatRiskBand),
  `src/index/age_factor.py` (multiplicador `≥ 1`, `2 - retention(age)`),
  `src/index/event_multiplier.py` (multiplicador `≥ 1` por país,
  `1 + 0,5·rate_c/rate_max`), `src/index/ccrs_report.py` (montagem final:
  `CCRS_i,s = Hazard × age_factor × EventMultiplier`, produto só, nunca soma;
  relatório de % capacidade por banda + contingência + ressalvas de dado).
  Falta: Monte Carlo. Itens em aberto na spec: SPEI F, clip de outlier sv/iv
  I, Monte Carlo J.
  Fechados na implementação: G (bounds congelados, `FROZEN_BOUNDS`), D
  (`age_factor = 2 - clip(retention(age), 0, 1)` ∈ `[1,2]`, convenção `≥ 1`
  confirmada como definitiva — `docs/DECISIONS.md` 2026-09-04, entrada final)
  e C (`EventMultiplier_c` implementado sem divergência spec/ARCHITECTURE).

## Estado atual (2026-09-04)

Camada de aquisição e processamento de clima concluída; camada de índice
iniciada (termo Hazard do CCRS):

- `src/config.py` reescrito.
- `src/downloaders/` (9): `boundaries_downloader`, `coastline_downloader`,
  `rivers_downloader`, `cds_tasmax_downloader`, `cds_precipitation_downloader`
  (pr/tas diário para um termo de SPEI futuro; espelha o `cds_tasmax`),
  `aqueduct_downloader`, `emdat_downloader`, `assets_validator`,
  `climate_downloader`.
- `src/processors/` (3): `water_stress_processor` (normalizado + bruto,
  Min-Max por país, sentinela WRI 9999 substituída por `country_max`),
  `heat_stress_processor` (normalizado Min-Max por país com modelos **e**
  cenários no mesmo pool; guarda fail-loud de grade; bruto = passthrough do
  output do downloader; itera sobre todo `source_id`),
  `water_variability_processor` (sv/iv do Aqueduct → raster normalizado +
  bruto, Min-Max por país sobre os 3 cenários, sem log1p; espelha o
  `water_stress_processor`).
- `src/index/` (5): `ccrs_calculator` (termo `Hazard_{i,s}`; bounds globais
  congelados + trava de regressão; pesos água/calor por bucket; GFDL/MIROC6
  separados); `risk_bands` (WaterRiskBand cortes absolutos WRI + HeatRiskBand
  percentis GFDL-ESM4, colunas separadas, nunca um score único); `age_factor`
  (multiplicador `≥ 1`, `age_factor = 2 - clip(retention(age), 0, 1)` ∈
  `[1,2]`, multiplica o Hazard por `plant_uid`; coal com overhaul assumido
  dente-de-serra; wind uniforme 0,4%/ano, sem branch de `CF_initial`);
  `event_multiplier` (multiplicador `≥ 1` por país,
  `EventMultiplier_c = 1 + 0,5·rate_c/rate_max`, `rate_c = N_events(c)/124`,
  join por `country`, multiplica o Hazard); `ccrs_report` (T1×T2×T3: monta
  `CCRS_i,s` por `plant_uid`×`water_scenario`, um par de colunas por GCM
  `ccrs_gfdl_esm4`/`ccrs_miroc6`; junta as bandas de T4; relatório de %
  capacidade por WaterRiskBand/HeatRiskBand por país/cenário/GCM + tabela de
  contingência reaproveitada de `risk_bands.contingency_table`).
- `tests/`: cobertura unitária dos 9 downloaders, do `assets_validator`, dos
  3 processors, do `ccrs_calculator`, do `risk_bands`, do `age_factor`, do
  `event_multiplier` e do `ccrs_report`. 210 testes, todos passando.
- Não portados: `slr_downloader`, `power_downloader`, `aneel_downloader`,
  `dgeg_downloader`, `slr_stress_processor`, `coastal_distance` (ver
  `docs/INVENTORY.md`).
- **Ainda não escrito:** Monte Carlo. Os três fatores multiplicativos, as
  bandas de risco e a montagem final do `CCRS_i,s`: **feitos**. V1–V6 todos
  fechados; itens da spec ainda abertos: F, I, J. Fechados na implementação:
  G, D (`age_factor ≥ 1`, `2 - retention(age)`, convenção confirmada como
  definitiva pelo autor — `docs/DECISIONS.md` 2026-09-04) e C
  (`EventMultiplier_c`, sem divergência entre spec e ARCHITECTURE).

## Onde está cada tipo de decisão

| Assunto | Documento |
|---|---|
| Metodologia do artigo (CCRS), V1–V6 (todos fechados), limites de escopo | `docs/ARCHITECTURE.md` |
| Spec fechada do CCRS + itens ainda em aberto (A–J) | `analysis/climate_risk_score_spec.md` |
| O que veio do repositório anterior e como | `docs/INVENTORY.md` |
| Log datado de fonte de dado / endpoint / resolução / cenário | `docs/DECISIONS.md` |
| Como o código funciona, como rodar, riscos de engenharia | `docs/memory/` |
