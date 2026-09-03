# GEAR Framework — INVENTORY.md

## Propósito deste documento

Descreve o que existe na camada de aquisição e processamento do repositório
anterior — verificado contra o código real. É um documento factual: registra
o que o código faz, quais dados produz, quais limitações foram observadas, e
quais decisões de design estão embutidas nos módulos reaproveitáveis. Não
contém decisões metodológicas abertas; essas pertencem ao `ARCHITECTURE.md`.

---

## Resumo executivo

| Bloco | Arquivos | Baixa de | Reaproveitamento |
|---|---|---|---|
| `src/downloaders/` | 10 `.py` + `__init__` | GADM, Natural Earth, Copernicus CDS, WRI Aqueduct (via GEE), IPCC AR6 SLP (via GEE), EM-DAT Dataverse, GEM (manual), ANEEL, DGEG | Direto — ver flags por módulo |
| `src/processors/` (clima) | `water_stress_processor.py`, `heat_stress_processor.py` | — (consomem `data/raw` e `data/processed`) | Interface estável; normalização Min-Max por país embutida |
| `src/processors/coastal_distance.py` | 1 | — | **Não portado** — dependia do hazard SLR, fora do escopo ativo |
| `assets_validator.py` | 1 (em `downloaders/`) | Não baixa — lê snapshot manual do GEM | Agregação por planta reaproveitável; coluna renomeada (ver Seção de ativos) |
| Testes desta camada | 3 arquivos, 23 testes | — | Cobrem `water_stress_processor` (10), `heat_stress_processor` (5), `slr_stress_processor` (7, fora de escopo — não portados); downloaders e `assets_validator` sem cobertura |
| Dado em disco | `data/raw` ~796 MB · `data/processed` ~1,9 GB | — | Reaproveitável como está; nada está no git (`.gitignore`) |

Parâmetros globais fixos nesta camada (`src/config.py`):
`COUNTRIES = [Brazil, Portugal, India]`, `YEAR_TARGET = 2050`,
`CRS_TARGET = EPSG:4326`, `RESOLUTION_TARGET_DEG = 0.008333` (~1 km),
`CMIP6_SCENARIOS = [ssp126, ssp585]`, `AQUEDUCT_SCENARIOS = [bau, opt, pes]`.

---

## O que não está incluído (exclusão explícita)

| Fora de escopo | Motivo |
|---|---|
| `src/sci/` (`risk_extraction.py`, `resilience.py`, `sci_index.py`, `naes.py`, `article_section_analysis.py`) | Cálculo de índice, resiliência, NAES — reescritos do zero |
| `src/validation/` (`sensitivity_analysis.py`, `emdat_validation.py`) | Monte Carlo, validação EM-DAT |
| `src/weights/` (`calibrated_weights.py`) | Pesos por par combustível–perigo |
| `src/visualization/` (`maps.py`, `tables.py`, `validation_figures.py`, `validation_tables.py`) | Figuras e tabelas do artigo |
| `src/ahp/` | Removido do repositório; método AHP/Saaty descartado |
| `main.py` | Orquestração antiga |
| `src/inspection/` (`*_qa.py`, `gem_osm_cross_check.py`) | QA e diagnóstico; não é aquisição de dado do pipeline principal |
| `src/processors/slr_stress_processor.py` | SLR fora do escopo ativo; módulo não portado |
| `src/processors/coastal_distance.py` | Dependia do hazard SLR; não portado |
| `src/downloaders/slr_downloader.py` | SLR fora do escopo ativo; não portado |
| `src/downloaders/power_downloader.py` | Gerava baseline histórico de temperatura sem uso a jusante; não portado |
| Testes dos módulos acima | Cobrem código fora de escopo |

**Nota sobre `emdat_downloader.py`:** o downloader de EM-DAT (aquisição do
snapshot do Dataverse) **está incluído** — é aquisição de dado bruto. Apenas
a validação cruzada EM-DAT (`src/validation/emdat_validation.py`) está fora.

**Nota sobre `src/inspection/`:** os CSVs em `data/raw/assets/osm/` são
gerados por `src/inspection/gem_osm_cross_check.py`, classificado como QA.
ANEEL e DGEG são fontes complementares, não integradas ao pipeline principal.
Nenhum dos três é reaproveitado como etapa de aquisição.

---

## Dependência compartilhada obrigatória: `src/config.py`

Todos os módulos fazem `from src.config import ...`. `config.py` não está
em `src/downloaders/` nem `src/processors/`, mas nenhum deles roda sem ele.
Deve ser portado junto (ou reescrito) na reconstrução.

| Constante | Valor | Lida por |
|---|---|---|
| `BASE_DIR`, `DATA_DIR`, `RAW_DIR`, `PROCESSED_DIR`, `OUTPUT_DIR` | Derivados de `Path(__file__)` | Todos |
| `CLIMATE_RAW`, `CLIMATE_PROCESSED`, `ASSETS_RAW`, `ASSETS_PROCESSED`, `BOUNDARIES_RAW`, `VALIDATION_RAW`, `OUTPUT_INSPECTION`, `OUTPUT_MAPS`, `LOG_DIR` | Subpastas de `data/` | Todos |
| `COUNTRIES` | `["Brazil", "Portugal", "India"]` | Todos |
| `COUNTRY_ISO3` | `{Brazil: BRA, Portugal: PRT, India: IND}` | boundaries, cds_tasmax, emdat |
| `COUNTRY_BBOX_FALLBACK` | Bboxes aproximados por país | cds_tasmax, boundaries |
| `MAINLAND_ONLY_COUNTRIES` | `{"Portugal"}` — exclui Açores/Madeira | boundaries, assets_validator |
| `CRS_TARGET` | `"EPSG:4326"` | Processors |
| `RESOLUTION_TARGET_DEG` | `0.008333` (~1 km) | cds_tasmax, processors |
| `YEAR_TARGET` | `2050` | Processors e downloaders de clima |
| `CMIP6_SCENARIOS` | `["ssp126", "ssp585"]` | heat |
| `CMIP6_SCENARIO_TO_CDS_EXPERIMENT` | `{ssp126: ssp1_2_6, ssp585: ssp5_8_5}` | cds_tasmax |
| `CMIP6_SOURCE_ID_CDS` | `"gfdl_esm4"` — modelo único; segundo GCM será adicionado | cds_tasmax |
| `CMIP6_FUTURE_PERIOD` | `("2041-01-01", "2070-12-31")` — janela "2050" | cds_tasmax |
| `AQUEDUCT_SCENARIOS` | `["bau", "opt", "pes"]` | aqueduct, water_stress_processor |
| `AQUEDUCT_TO_SSP_LABEL` | `{opt: SSP1-2.6, bau: SSP3-7.0, pes: SSP5-8.5}` | aqueduct, water_stress_processor (apenas rótulo) |
| `AQUEDUCT_SCENARIO_FOR_CMIP6` | `{ssp126: opt, ssp585: pes}` | Usado a jusante; `bau` não tem contrapartida em calor (ver Limitações) |
| `AQUEDUCT_FC_ID` | `"WRI/Aqueduct_Water_Risk/V4/future_annual"` | aqueduct |
| `GADM_BASE_URL` | `https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg` | boundaries |
| `POWER_BASE_URL` | Removido — `power_downloader.py` não portado | — |
| `ANEEL_CKAN_BASE_URL` | `https://dadosabertos.aneel.gov.br/api/3/action` | aneel_downloader |
| `DGOVPT_API_BASE_URL` | `https://dados.gov.pt/api/1` | dgeg_downloader |
| `EMDAT_ARCHIVE_PERSISTENT_ID` / `EMDAT_DATAVERSE_API_BASE` | `doi:10.14428/DVN/I0LTPH` / `https://dataverse.uclouvain.be/api` | emdat_downloader |
| `RANDOM_SEED` | `42` | Monte Carlo — fora do escopo desta camada |
| Credenciais + `require_*()` | Ver seção de credenciais | aqueduct, cds_tasmax, emdat |

`config.py` carrega `credentials.local` no import via
`load_dotenv(CREDENTIALS_FILE)` (`src/config.py:37`).

---

## `src/downloaders/`

| Arquivo | O que baixa | Fonte / API | Saída | Credencial |
|---|---|---|---|---|
| `__init__.py` | — (marcador de pacote, vazio) | — | — | — |
| `boundaries_downloader.py` | Fronteira nacional nível 0 (GeoPackage) por país | GADM 4.1 | `data/raw/boundaries/gadm/gadm41_{ISO3}.gpkg` | Nenhuma |
| `coastline_downloader.py` | Linha de costa global (shapefile) | Natural Earth 10m physical/coastline | `data/raw/boundaries/natural_earth_coastline/ne_10m_coastline.shp` | Nenhuma |
| `rivers_downloader.py` | Rios e centerlines global (shapefile) | Natural Earth 10m physical/rivers_lake_centerlines | `data/raw/boundaries/natural_earth_rivers/ne_10m_rivers_lake_centerlines.shp` | Nenhuma |
| `cds_tasmax_downloader.py` | tasmax diário por país × cenário; produz raster de contagem de dias com tasmax > 40 °C | Copernicus CDS, `projections-cmip6`, modelo `gfdl_esm4`, `ssp1_2_6`/`ssp5_8_5`, 2041–2070, run `r1i1p1f1` | `data/raw/climate/cds_tasmax/{país}/{cenário}/`; raster em `data/processed/climate/extreme_heat_days_*_{1km,native}.tif` | `CDS_API_URL`, `CDS_API_KEY` |
| `aqueduct_downloader.py` | Estresse hídrico por bacia, formato largo | WRI Aqueduct 4.0 via Google Earth Engine | `data/raw/climate/aqueduct/{país}/aqueduct_2050.csv` | `GEE_PROJECT_ID` — etapa pulada se ausente |
| `emdat_downloader.py` | Snapshot de eventos de desastre 1900–2024 | EM-DAT Archive, UCLouvain Dataverse, snapshot 2026-04-30 | `data/raw/validation/_emdat_archive_raw.xlsx`, `emdat_{país}.csv` | Nenhuma |
| `assets_validator.py` | Não baixa — lê export manual do GEM (`.xlsx`), valida e agrega | GEM Global Integrated Power Tracker, export manual | `data/processed/assets/*.csv`, `gem_validation_report.json` | Nenhuma |
| `aneel_downloader.py` | Registro por usina do Brasil (SIGA) — complementar, não integrado ao pipeline principal | ANEEL Dados Abertos (CKAN) | `data/raw/assets/aneel/{...}.csv` | Nenhuma |
| `dgeg_downloader.py` | 4 datasets de centrais elétricas de Portugal — complementar, não integrado | DGEG via dados.gov.pt → WFS | `data/raw/assets/dgeg/{...}.csv` | Nenhuma |
| `climate_downloader.py` | Orquestrador da camada de clima — chama boundaries + cds_tasmax + aqueduct | — | `logs/climate_pipeline_report_*.json` | Herdadas |

**Módulos removidos em relação ao repositório anterior:**
`slr_downloader.py` (SLR fora do escopo ativo) e `power_downloader.py`
(baseline NASA POWER sem uso a jusante) não são portados.

**Não há downloader de OSM em `src/downloaders/`.** Os CSVs em
`data/raw/assets/osm/` são gerados por `src/inspection/gem_osm_cross_check.py`,
classificado como QA, fora do escopo de aquisição.

---

## `src/processors/` — camadas de clima

Os dois processors ativos têm a mesma interface: leem o dado bruto,
calculam min/max por país, e emitem **(a)** raster normalizado 0–1 e
**(b)** raster do valor físico bruto, ambos na grade de referência.

Contrato de saída: `dict` com chaves `{"success", "path", "reason",
"raw_path", "raw_units", "raw_kind"}`. Cache: não reescreve se ambos os
rasters já existem e `overwrite=False`.

### `water_stress_processor.py`

- **Input:** `aqueduct_2050.csv` (coluna `{cenário}50_ws_x_r`); grade de
  referência; geometria de bacias.
- **Normalizado:** `water_stress_{país}_{cenário}_1km.tif`, 0–1 por país.
- **Bruto:** `water_stress_raw_{país}_{cenário}_1km.tif`, unidade
  `consumption_to_availability_ratio` (valores observados até ~30 na Índia).
- **Pool min/max:** os 3 cenários Aqueduct juntos (`bau`, `opt`, `pes`).
- **Limitação observada:** bacias com sentinela WRI (`RAW_SENTINEL_VALUE =
  9999.0`) são excluídas do cálculo de máximo e substituídas por
  `country_max` **em ambos os outputs, inclusive o raster bruto**. A Índia
  é o país com mais bacias sentinela. O raster bruto de água não é
  completamente neutro entre países; isso afeta o NAES diretamente e deve
  ser tratado como limitação declarada no manuscrito.

### `heat_stress_processor.py`

- **Input:** `extreme_heat_days_{país}_{cenário}_1km.tif`, produzido pelo
  `cds_tasmax_downloader.py`.
- **Normalizado:** 0–1 por país.
- **Bruto:** passthrough por referência direta ao arquivo de entrada —
  reaproveitar o bruto de calor significa depender de
  `cds_tasmax_downloader.py`, não de um processor separado.
- **Unidade do bruto:** `days_per_year_with_tasmax_gt_40C` (observado 0–173,
  Índia SSP5-8.5).
- **Pool min/max:** os 2 cenários CMIP6 juntos.
- **Limitação observada:** um único GCM (`GFDL-ESM4`), um run (`r1i1p1f1`),
  resolução nativa ~100 km reamostrada por vizinho mais próximo para ~1 km
  nominal. Sem bias-correction, sem ensemble, sem quantificação de incerteza
  de modelo. Um segundo GCM será adicionado como sensitivity check
  obrigatório (ver `ARCHITECTURE.md`).

### `slr_stress_processor.py` — não portado

Implementado, testado e funcional no repositório anterior. Excluído do
escopo ativo porque SLR foi retirado da metodologia (ver `ARCHITECTURE.md`,
Seção 3). O módulo não é portado para o novo repositório.

---

## `src/downloaders/assets_validator.py`

- **Input:** `.xlsx` do GEM, localizado por padrão de nome, lido com
  `openpyxl`.
- **Pipeline:** filtra por `Status == "operating"` → filtra países →
  agrega por planta → aplica bucket de combustível → remove Açores/Madeira
  de Portugal (`MAINLAND_ONLY_COUNTRIES`).
- **`aggregate_by_plant`:** chave = país + nome normalizado + coordenada
  arredondada a `DUPLICATE_COORD_TOLERANCE_DEG = 0.0009` (~100 m).
  `capacity_mw` = soma das unidades. `commissioning_year` = mínimo entre
  unidades (unidade mais antiga). `fuel_type` divergente entre unidades →
  `None` + `mixed_fuel_type = True`.
- **`add_fuel_bucket`:** adiciona `fuel_type_bucket` ∈
  `{hydro, wind, solar, thermal}`. Carvão e outros termoeléctricos estão
  fusionados no bucket `thermal`. 7 plantas com overrides manuais por nome.
  A coluna era nomeada `fuel_type_ahp_bucket` no repositório anterior;
  renomeada para remover acoplamento ao método AHP, descartado.
- **Output:** `gem_validated_plants_{país}.csv`, `gem_units_detail.csv`,
  `gem_planned_assets.csv`, `gem_excluded_azores_madeira.csv`,
  `gem_validation_report.json`.
- **Limitação observada:** apenas ativos `Status == "operating"` entram no
  pipeline. O ano de comissionamento mais recente fica limitado à data do
  export do GEM (2025), o que restringe o teto observado da curva de
  resiliência. Isso é uma consequência do filtro de status, não um bug, e
  deve ser declarado explicitamente no manuscrito.

---

## Testes

`tests/`, framework `unittest`. Testes ativos desta camada:
`test_water_stress_processor.py` (10 testes),
`test_heat_stress_processor.py` (5 testes).
`test_slr_stress_processor.py` (7 testes) e
`test_coastal_distance.py` (8 testes) cobrem módulos fora de escopo e não
são portados.

**Lacunas conhecidas:** nenhum downloader tem teste unitário;
`assets_validator.py` não tem teste (agregação por planta, filtro de status
e bucket de combustível não cobertos); `heat_stress_processor.py` só testa
o processor, não o caminho completo download → raster com dado real. Todos
os testes de processor rodam sobre fixtures sintéticas.

---

## Credenciais e variáveis de ambiente

Fluxo: `credentials.local` (gitignored) → `load_dotenv()` em
`src/config.py:37` → `os.getenv(...)` → funções `require_*()` que levantam
erro com instrução acionável se a variável estiver ausente.

| Variável | Usada por | Obrigatória |
|---|---|---|
| `GEE_PROJECT_ID` | `aqueduct_downloader.py` | Não — etapa pulada se ausente |
| `CDS_API_URL` / `CDS_API_KEY` | `cds_tasmax_downloader.py` | Sim |
| `EARTHDATA_USERNAME` / `EARTHDATA_PASSWORD` | Nenhum downloader ativo — reservado | Não |
| `EMDAT_PORTAL_EMAIL` / `EMDAT_PORTAL_PASSWORD` | Nenhum caminho ativo — downloader usa Dataverse aberto | Não |

Nenhuma chave de API está hardcoded em qualquer módulo. Todo segredo passa
por `credentials.local` → `config.py`.

---

## Dependências (bibliotecas)

Python 3.11.9. Ambiente virtual não existia no repositório anterior —
a reconstrução cria um `.venv` dedicado.

**Efetivamente usadas por esta camada:**
`numpy`, `pandas`, `xarray`, `rioxarray`, `rasterio`, `geopandas`,
`shapely`, `pyproj` (transitivo), `earthengine-api`, `cdsapi`,
`netcdf4`/`h5netcdf`, `requests`, `openpyxl`, `tqdm`, `python-dotenv`.

**Presentes no `requirements.txt` anterior mas não portadas:**
`earthaccess`, `nasapower`, `osmnx`, `beautifulsoup4`, `scipy`,
`scikit-learn`, `seaborn`, `contextily`, `cartopy`, `pyyaml`,
`google-api-python-client`, `oauth2client` — serão reavaliadas quando os
módulos que as consomem forem reescritos.

---

## Dados em disco (repositório anterior — referência de volume)

Nada está no git. Volumes do repositório anterior:

| Diretório | Volume | Conteúdo principal |
|---|---|---|
| `data/raw/` | ~796 MB | GADM 432 MB, CDS tasmax 208 MB, Aqueduct 42 MB, ANEEL 15 MB, EM-DAT 8,6 MB, DGEG 7,7 MB |
| `data/processed/climate/` | ~1,9 GB | 21 rasters normalizados + rasters brutos por hazard |
| `data/processed/assets/` | ~19 MB | CSVs de plantas validadas por país |

A reconstrução gera seus próprios arquivos. Os volumes acima são referência,
não herança — os arquivos físicos não são copiados do repositório anterior.

---

## Decisões de design embutidas nos módulos reaproveitáveis

Estas decisões estão implementadas no código existente. Algumas têm
implicações metodológicas relevantes para o índice; todas devem ser
declaradas no manuscrito.

| # | Decisão | Onde está | Implicação |
|---|---|---|---|
| 1 | Normalização Min-Max por país, dentro do processor | `water_stress_processor.py`, `heat_stress_processor.py` | Output 0–1 responde "ranking dentro do país". Para o NAES, a entrada correta é sempre o raster bruto, nunca o normalizado. |
| 2 | Bacias sentinela de água recebem `country_max` no raster bruto | `water_stress_processor.py` | `water_stress_raw` não é completamente neutro entre países; Índia é o país mais afetado. |
| 3 | Calor: resolução nominal de 1 km, modelo único | `cds_tasmax_downloader.py` | Resolução nativa ~100 km; reamostragem por vizinho mais próximo. Um segundo GCM será adicionado como sensitivity check. |
| 4 | Bruto de calor é passthrough do downloader | `heat_stress_processor.py` | Reaproveitar o raster bruto de calor depende de `cds_tasmax_downloader.py`. |
| 5 | Pool de min/max inclui todos os cenários do hazard | Ambos os processors | Água usa 3 cenários; calor usa 2. Incluir SSP3-7.0 em calor mudaria o denominador de normalização de todos os pixels já processados. |
| 6 | `aggregate_by_plant`: `commissioning_year` = mínimo entre unidades | `assets_validator.py` | A unidade mais antiga define o ano da planta; planta com unidades de idades muito distintas tem seu ano subestimado. |
| 7 | Apenas `Status == "operating"` entra no pipeline | `assets_validator.py` | Ano de comissionamento mais recente limitado à data do export do GEM (2025); afeta o teto observado da curva de resiliência. |
| 8 | Grade de referência = camada de calor | Ambos os processors | Trocar a fonte ou resolução de calor força reprocessar água. |
| 9 | `config.py` é ponto único de acoplamento | `src/config.py` | Não é possível portar downloaders ou processors sem portar (ou reescrever) `config.py`. |
| 10 | GEM é snapshot manual, sem API | `assets_validator.py` | Sem reprodutibilidade automática; o snapshot deve ser versionado e datado explicitamente no manuscrito. |