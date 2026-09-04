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
  fechadas**; o que falta é o código de produção em `src/` (não escrito) e
  alguns itens em aberto na spec (mapeamento do `age_factor` para
  multiplicador, termo de SPEI, constantes de transformação congeladas,
  clip de outlier sv/iv, sensibilidade Monte Carlo).

## Estado atual (2026-09-03)

Reconstrução da camada de aquisição e processamento de clima concluída
(etapas 1 e 2 de 2):

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
- `tests/`: cobertura unitária dos 9 downloaders, do `assets_validator` e
  dos 3 processors. 122 testes, todos passando.
- Não portados: `slr_downloader`, `power_downloader`, `aneel_downloader`,
  `dgeg_downloader`, `slr_stress_processor`, `coastal_distance` (ver
  `docs/INVENTORY.md`).
- **Não escrito:** o código do CCRS em `src/` (score, bandas, `age_factor`,
  `EventMultiplier`, Monte Carlo, geradores de relatório). V1–V6 estão todos
  fechados; o bloqueio agora é implementação + itens em aberto da spec.

## Onde está cada tipo de decisão

| Assunto | Documento |
|---|---|
| Metodologia do artigo (CCRS), V1–V6 (todos fechados), limites de escopo | `docs/ARCHITECTURE.md` |
| Spec fechada do CCRS + itens ainda em aberto (A–J) | `analysis/climate_risk_score_spec.md` |
| O que veio do repositório anterior e como | `docs/INVENTORY.md` |
| Log datado de fonte de dado / endpoint / resolução / cenário | `docs/DECISIONS.md` |
| Como o código funciona, como rodar, riscos de engenharia | `docs/memory/` |
