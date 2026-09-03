# 01 — Visão geral

Pipeline Python de dados geoespaciais/climáticos para o artigo GEAR (risco
climático de infraestrutura de geração elétrica em Brasil, Portugal e Índia).
Roda localmente, sem frontend, sem CI.

## Fases

- **Camada de aquisição/processamento (herdada, reconstruída):** downloaders
  de fronteiras, clima (calor extremo e estresse hídrico), eventos EM-DAT, e
  validação/agregação do snapshot manual do GEM. Detalhe da herança em
  `docs/INVENTORY.md`.
- **Camada de índice/peso/resiliência (reconstruída do zero, ainda não
  iniciada):** SCI, NAES, pesos por par combustível–perigo, fator de
  resiliência, Monte Carlo. Especificação em `docs/ARCHITECTURE.md`.
  **Bloqueada** pelas verificações pós-dados V1–V6 (`ARCHITECTURE.md`
  Seção 9) — nenhum código dessa camada até que todas estejam resolvidas.

## Estado atual (2026-09-03)

Reconstrução da camada de aquisição e processamento de clima concluída
(etapas 1 e 2 de 2):

- `src/config.py` reescrito.
- `src/downloaders/`: `boundaries_downloader`, `coastline_downloader`,
  `rivers_downloader`, `cds_tasmax_downloader`, `aqueduct_downloader`,
  `emdat_downloader`, `assets_validator`, `climate_downloader`.
- `src/processors/`: `water_stress_processor` (normalizado + bruto, Min-Max
  por país, sentinela WRI 9999 substituída por `country_max`),
  `heat_stress_processor` (normalizado Min-Max por país com modelos **e**
  cenários no mesmo pool; guarda fail-loud de grade; bruto = passthrough do
  output do downloader; itera sobre todo `source_id`).
- `tests/`: cobertura unitária de todos os downloaders, do `assets_validator`
  e dos dois processors. 86 testes, todos passando.
- Não portados: `slr_downloader`, `power_downloader`, `aneel_downloader`,
  `dgeg_downloader`, `slr_stress_processor`, `coastal_distance` (ver
  `docs/INVENTORY.md`).
- **Não escrito** (bloqueado por V1–V6): qualquer código de índice, peso,
  resiliência, NAES ou Monte Carlo.

## Onde está cada tipo de decisão

| Assunto | Documento |
|---|---|
| Metodologia do artigo, itens OPEN, V1–V6 | `docs/ARCHITECTURE.md` |
| O que veio do repositório anterior e como | `docs/INVENTORY.md` |
| Log datado de fonte de dado / endpoint / resolução / cenário | `docs/DECISIONS.md` |
| Como o código funciona, como rodar, riscos de engenharia | `docs/memory/` |
