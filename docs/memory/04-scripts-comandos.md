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

## Camada de índice (CCRS)

```
# termo Hazard_{i,s} por planta/cenário, GFDL-ESM4 e MIROC6 em colunas
# separadas -> data/outputs/tables/ccrs_hazard.csv
.venv\Scripts\python -m src.index.ccrs_calculator

# só confere os bounds globais congelados contra os rasters em disco (não escreve)
.venv\Scripts\python -m src.index.ccrs_calculator --check-bounds

# WaterRiskBand + HeatRiskBand por planta (colunas separadas) + relatório
# -> data/outputs/tables/ccrs_risk_bands.csv e ccrs_risk_bands_report.md
.venv\Scripts\python -m src.index.risk_bands [--heat-gcm gfdl_esm4|miroc6]
```

`risk_bands` depende dos rasters brutos (via `ccrs_calculator.sample_terms`).
`--heat-gcm miroc6` gera o painel de sensibilidade (percentis do próprio
MIROC6, nunca blend). O relatório sempre traz o aviso literal de que o
HeatRiskBand não é comparável entre rodadas com pool diferente.

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
