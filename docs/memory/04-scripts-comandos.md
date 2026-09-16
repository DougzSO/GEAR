# 04 — Scripts e comandos

Tudo roda localmente. Ambiente virtual dedicado em `.venv/` na raiz do
projeto (não copiar de outro repositório — paths de venv não são portáveis).

## Setup

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Credenciais em `credentials.local` na raiz (git-ignored). Chaves lidas:
`CDS_API_URL`, `CDS_API_KEY` (obrigatórias para cds_tasmax e
cds_precipitation), `GEE_PROJECT_ID`
(opcional — sem ela o Aqueduct é pulado). GEE também exige um token de
autenticação local (`earthengine authenticate`), não coberto por
`credentials.local`.

## Testes

```
.venv\Scripts\python -m pytest -q
```

Configuração em `pytest.ini` (`pythonpath = .`). Fixtures sintéticas; nenhum
teste faz chamada de rede.

## Downloaders

```
# orquestrador de clima (boundaries + cds_tasmax + aqueduct)
.venv\Scripts\python -m src.downloaders.climate_downloader

# um país/cenário de calor isolado
.venv\Scripts\python -m src.downloaders.cds_tasmax_downloader --country Brazil --scenario ssp126 [--model gfdl_esm4]

# precipitação + temperatura média (pr, tas) para SPEI futuro — mesma matriz
# do cds_tasmax (2 GCMs x 3 cenários x 3 países), espelha cds_tasmax_downloader
# e reusa suas funções de grade. Baixa e valida a série diária bruta; grava
# raster de média do período só como QA (não é insumo do SPEI). Sem processor.
.venv\Scripts\python -m src.downloaders.cds_precipitation_downloader --country Brazil --scenario ssp126 [--model gfdl_esm4]
# matriz completa: import download_all_cds_precipitation(COUNTRIES)

# EM-DAT (download + filtro + contagem/cobertura)
.venv\Scripts\python -m src.downloaders.emdat_downloader

# validação do snapshot GEM (arquivo .xlsx precisa estar em data/raw/assets/)
.venv\Scripts\python -m src.downloaders.assets_validator --discover     # inspeciona colunas
.venv\Scripts\python -m src.downloaders.assets_validator --validate     # pipeline completo
.venv\Scripts\python -m src.downloaders.assets_validator --fuel-distribution
```

`boundaries_downloader`, `coastline_downloader`, `rivers_downloader` não têm
CLI própria — chamados via `climate_downloader` ou importados
(`download_all_boundaries`, `download_coastline`, `download_rivers`).

## Processors de clima

```
# calor: normaliza extreme_heat_days -> heat_stress_{país}_{modelo}_{cenário}_1km.tif
.venv\Scripts\python -m src.processors.heat_stress_processor [--overwrite]

# água: precisa do calor processado antes (referência de grade)
.venv\Scripts\python -m src.processors.water_stress_processor [--overwrite]

# variabilidade sv/iv do Aqueduct: mesma dependência de grade do calor
.venv\Scripts\python -m src.processors.water_variability_processor [--indicators sv iv] [--overwrite]
```

Ordem: `heat_stress_processor` → (`water_stress_processor`,
`water_variability_processor`).

## Processors de clima -- GEAR v3 novos hazards (Fase 2)

```
# chuva extrema: reaproveita o pr ja baixado para SPEI, sem download novo
.venv\Scripts\python -m src.processors.extreme_precipitation_processor [--overwrite]

# vento extremo: baixa ERA5 (rajada horaria 10m) por pais/ano, depois processa
.venv\Scripts\python -m src.downloaders.era5_wind_downloader --country Brazil [--year 1991] [--overwrite]
.venv\Scripts\python -m src.processors.extreme_wind_processor [--countries Brazil] [--overwrite]
```

`era5_wind_downloader` usa as mesmas credenciais `CDS_API_URL`/`CDS_API_KEY`
do `cds_tasmax_downloader`, mas é um dataset CDS diferente
(`reanalysis-era5-single-levels`) e baixa ano a ano (sem eixo de
modelo/cenário) -- rodar sem `--year` baixa o baseline inteiro
(`ERA5_WIND_BASELINE_PERIOD`, 1991-2020, 30 anos x hora). Nenhum dos dois
processors novos está plugado em `risk_calculator.HAZARD_TERMS` ainda
(Fase 2.5/3 pendentes) -- ver `docs/DECISIONS.md`.

## Camada de índice (CCRS-era, RETIRADA — NÃO RODA)

**Todos os comandos abaixo estão quebrados (`ImportError: cannot import name
'ccrs_calculator'`), por design, desde a Fase 1 da reconstrução v3
(2026-09-11) — `ccrs_calculator.py`/`ccrs_report.py` foram deletados, não
depreciados. Mantidos aqui só como registro histórico de como a camada
CCRS-era era operada; não copie/rode.** Ver `docs/memory/02-arquitetura.md`,
bloco "Módulos CCRS-era", e `docs/PROJECT_STATE_SNAPSHOT.md`.

```
# (histórico, quebrado) termo Hazard_{i,s} -> ccrs_hazard.csv
.venv\Scripts\python -m src.index.ccrs_calculator
# (histórico, quebrado) WaterRiskBand + HeatRiskBand -> ccrs_risk_bands.csv
.venv\Scripts\python -m src.index.risk_bands [--heat-gcm gfdl_esm4|miroc6]
# (histórico, quebrado) age_factor -> ccrs_age_factors.csv
.venv\Scripts\python -m src.index.age_factor
# (histórico, quebrado) EventMultiplier_c -> ccrs_event_multipliers.csv
.venv\Scripts\python -m src.index.event_multiplier
# (histórico, quebrado) montagem final CCRS_i,s -> ccrs_final.csv, ccrs_report.md
.venv\Scripts\python -m src.index.ccrs_report
```

## Camada de índice v3 (corrente)

Cada módulo tem seu próprio CLI (`argparse`, `python -m src.index.<módulo>
--help` lista os flags reais — não reproduzidos aqui em detalhe, gap
conhecido, fora do escopo desta tarefa de reconciliação). Ordem de execução:
`risk_calculator` -> `risk_bands` -> `psae` -> `contextual_validators`
(Fase 5, parcial) -> `sensitivity_recompute` (Fase 6, infraestrutura, não a
análise de sensibilidade em si). `hazard_scope.py`, `normalization.py` e
`correlation_gate.py` não têm CLI de produção standalone com esse propósito
final (o gate/normalização são módulos de recomendação, rodados uma vez
contra dado real — ver `docs/DECISIONS.md`). `age_factor.py` (reaproveitado
sem reescrita do CCRS-era) mantém seu CLI original, hoje consumido por
`risk_calculator.compute_risk_by_hazard`, não por um módulo de montagem
separado (que não existe mais).

`event_multiplier` depende de `data/raw/validation/emdat_{país}.csv` já
baixado (`python -m src.downloaders.emdat_downloader`) — não roda o
downloader sozinho.

## Orquestrador central — pipeline completo numa chamada

```
# roda a cadeia inteira em ordem de dependência, computando cada etapa UMA vez
# (processors condicionais -> T1 -> T2/T3 -> T4 -> T5 -> Monte Carlo -> tabelas
# -> figuras -> validação espacial EM-DAT). Objeto _Precomputed do Monte Carlo
# construído uma vez e passado por referência a todos os consumidores.
.venv\Scripts\python -m src.main

# flags
#   --skip-processors     não roda os processors (assume rasters atualizados)
#   --force-processors     re-roda todos os processors com overwrite=True
#   --skip-montecarlo      pula Monte Carlo + a Figura 7 e as tabelas C2/C5
#                          (para iterar mapas rápido)
#   --skip-tables / --skip-figures
#   --countries NAME ...   restringe só as figuras/tabelas (índice + Monte
#                          Carlo sempre rodam full-scope: cortes percentil do
#                          HeatRiskBand, bounds globais e rate_max exigem os 3
#                          países e os 3 cenários)
#   --scenarios opt bau    idem para os cenários de água nas figuras
#   --mc-iterations N      menos iterações Monte Carlo em runs de dev
#   --out-dir PATH
```

Cada `main()` de módulo continua válido para uso isolado/debug — o
orquestrador chama as funções internas diretamente (nunca os CLIs), evitando
recomputar `age_factor`/`event_multiplier`/`risk_bands` ~4×, e o
`_Precomputed` do Monte Carlo 3×. Três ganchos de injeção opcionais o
permitem: `ccrs_calculator.compute_hazard_by_gcm(frames_by_model=)`,
`monte_carlo._Precomputed(hazard_by_model=, band_tables=)`,
`tables.hazard_term_contribution_per_plant(hazard=)` — todos com default
`None` (comportamento inalterado para qualquer chamador existente). Ver item
25 de `05-decisoes-tecnicas.md`.

Figuras 3 e 4 são cópias byte-idênticas de `water_risk_band_pes` /
`heat_risk_band_ssp585` sob a numeração do artigo — o orquestrador faz as
cópias no fim da fase de figuras (antes era passo `cp` manual).

Depende dos três processors de clima já rodados (lê os rasters brutos deles).
`--check-bounds` sai com código 1 se `FROZEN_BOUNDS` divergir dos dados — nesse
caso, revisão manual antes de atualizar a constante (ver
`05-decisoes-tecnicas.md` item 12).

## Custo/tempo observado (2026-09-03, GFDL-ESM4, 3 países)

- GADM: ~450 MB no total (Brasil ~290 MB). Alguns minutos.
- CDS tasmax: fila do CDS + download; observado 1,5–3 min por país×cenário
  (Portugal ~0,57 MB `.nc`, Brasil ~37 MB, Índia ~20 MB) — bem menos que os
  ~200 MB estimados. Área do request = `_climate_bounds` (união bounds GADM +
  `COUNTRY_BBOX_FALLBACK`); Índia/Portugal re-baixados em 2026-09-03 com a
  caixa expandida (Índia 1 km passou de `(3121, 3411)` para `(3721, 3601)`,
  Portugal de `(601, 392)` para `(721, 421)`).
- Aqueduct: 1 chamada GEE + 1 download HTTP por país; segundos a ~1 min.
  42 MB no total (Brasil 31 MB).
- EM-DAT Archive: ~8 MB, um download.
- Processors: segundos por país×cenário; ~275 MB de rasters processados de
  calor + ~150 MB de água (normalizado + bruto).

## results_draft (figuras/tabelas do GEAR_v3_RESULTS_DRAFT.md, 2026-09-15)

`src/reporting/results_draft/` — um módulo por item numerado do draft (16
total, `item01_correlation_gate.py` … `item16_threshold_tier_provenance.py`),
mais `common.py` (loaders de dado real + constantes compartilhadas) e
`run_all.py` (orquestrador). Escreve em `data/outputs/results_draft/`
(estrutura aprovada e registrada em `docs/ARCHITECTURE.md` Seção 11 —
gitignored como o resto de `data/outputs/`, os scripts são o artefato
versionado).

```
.venv\Scripts\python -m src.reporting.results_draft.run_all           # todos os 16
.venv\Scripts\python -m src.reporting.results_draft.run_all --items 7 12
.venv\Scripts\python -m src.index.psae                                 # pré-requisito: gera
                                                                         # psae.csv (não
                                                                         # persistido pelo
                                                                         # src.main pipeline)
```

Cada item lê arquivo(s) real(is) já em `data/outputs/tables/` (ou, para os
itens 8/9, chama `src.index.scenario_discovery.hazard_removal_oat()` /
`correlation_gate_sweep()` ao vivo — módulos reais, sem CSV persistido antes
desta task; execução é barata, sem Monte Carlo). Mapeamento completo
item→fonte real, com filtros/colunas, foi feito manualmente antes de
qualquer código ser escrito (ver `MANIFEST.md` gerado na raiz da árvore de
output — reconstrói o mesmo mapeamento a cada execução).

**Bug pré-existente descoberto ao rodar isto (não corrigido, fora do escopo
desta task):** `src/visualization/_common.py` e mais 8 arquivos (`src/main.py`,
`monte_carlo.py`, `emdat_validation.py`, `charts.py`, `data.py`, `maps.py`,
`tables.py`) importam `from src.index import ccrs_calculator` — esse módulo
não existe mais (renomeado para `risk_calculator.py` em algum commit
anterior sem atualizar os importadores). Confirmado por import direto:
`ModuleNotFoundError: No module named 'src.index.ccrs_calculator'`. Isso
significa que **`python -m src.main` e qualquer `src/visualization/*`
atualmente não rodam**, tal como commitados. `results_draft/common.py`
deliberadamente NÃO importa `src.visualization._common` por causa disso —
reimplementa um helper mínimo de mapa (boundary/marker/save) usando só
`src.config` + `src.downloaders.boundaries_downloader` (que importam
limpos). Ver `06-areas-de-risco.md` para o registro formal deste risco.

Duas dependências declaradas em `requirements.txt` mas ausentes do `.venv`
local foram instaladas durante esta task (`numba`, `SALib`) — drift de
ambiente, não mudança de versão pinada.
