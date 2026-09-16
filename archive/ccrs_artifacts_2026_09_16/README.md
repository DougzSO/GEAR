# CCRS Artifacts — Archived 2026-09-16

Arquivos da metodologia CCRS (bucket-weighted aggregation, indice composto
por planta), superseded por GEAR v3 `Risk_{i,h}` per-hazard
(`docs/DECISIONS.md` [2026-09-11] "GEAR v3 Phase 1: Risk_i,h replaces the
CCRS core (Equation 1)"). Todos os arquivos aqui foram gerados por
`src/main.py` (orquestrador pre-v3, mantido na arvore mas quebrado -- importa
`src/index/ccrs_report.py`, deletado na Fase 1) e/ou por
`src/visualization/maps.py` (deletado, ver `docs/LIMITATIONS.md`,
"2026-09-16 -- Legacy CCRS visualization/sensitivity layer removed").
Nenhum destes arquivos e regeneravel pelo codigo atual sem reconstruir a
camada CCRS deliberadamente removida.

**Nao usar em analises pos-v3.**

## Excecao: `ccrs_age_factors.csv` NAO foi arquivado

`data/outputs/tables/ccrs_age_factors.csv` permanece em
`data/outputs/tables/` apesar do prefixo `ccrs_` -- e um artefato **ativo**,
nao legado: `src/index/age_factor.py` (modulo vivo, e o termo
`Vulnerability_i` do proprio `Risk_i,h` v3, `risk_calculator.py:48-49`)
escreve esse arquivo, e `src/reporting/results_draft/common.py::load_inventory`
(consumido por `item02_riskband_distribution.py` e
`item12_psae_distribution.py`, ambos parte do pipeline de producao atual)
le esse mesmo arquivo do disco. Arquiva-lo quebraria
`results_draft/run_all.py`. O prefixo `ccrs_` no nome e um resquicio de
nomenclatura pre-v3, nao um sinal de que o conteudo seja obsoleto --
renomear o arquivo (e seus 3 pontos de leitura) e uma mudanca de escopo
maior que esta limpeza e nao foi feita aqui.

## Arquivos arquivados

### `tables/`
- `ccrs_event_multipliers.csv` (escrito por `event_multiplier.py`, so lido por `main.py` quebrado)
- `ccrs_final.csv`
- `ccrs_hazard.csv`
- `ccrs_hazard_aged.csv`
- `ccrs_heat_band_capacity_shares.csv`
- `ccrs_report.md`
- `ccrs_risk_bands.csv`
- `ccrs_risk_bands_report.md`
- `ccrs_water_band_capacity_shares.csv`
- `national_ccrs_summary.csv`

### `maps/` (PNG + `pdf/`)
- `Brazil/`, `India/`, `Portugal/`: `ccrs_scenario_delta_gfdl_esm4_opt_vs_pes.{png,pdf}`, `top10_ccrs_breakdown_by_bucket_gfdl_esm4.{png,pdf}`
- `combined/`: `figure5_ccrs_overview_{bau,opt,pes}_gfdl_esm4.{png,pdf}`
- `combined/secondary/`: `ccrs_asset_level_pes_gfdl_esm4.png`, `ccrs_distribution_by_bucket_gfdl_esm4_{bau,opt,pes}.png`, `ccrs_overview_gfdl_esm4_{bau,opt,pes}.png`, `ccrs_scenario_delta_gfdl_esm4_opt_vs_pes.png` (+ `pdf/` equivalentes)

Sucessor funcional: `risk_by_hazard.csv` + `risk_bands.csv` + `psae.csv`
(pipeline `src/orchestrator.py`) + `src/reporting/results_draft/` (camada
de visualizacao v3).
