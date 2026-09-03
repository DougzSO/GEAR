# 03 — Pipeline de dados

Fluxo: downloaders → `data/raw/` → processors de clima → `data/processed/climate/`.
Nada em `data/` está no git.

## Fontes e saídas

| Módulo | Fonte | Credencial | Saída |
|---|---|---|---|
| boundaries | GADM 4.1 nível 0 (geodata.ucdavis.edu) | — | `data/raw/boundaries/gadm/gadm41_{ISO3}.gpkg` |
| coastline | Natural Earth 10m coastline (naciscdn.org) | — | `data/raw/boundaries/natural_earth_coastline/ne_10m_coastline.shp` |
| rivers | Natural Earth 10m rivers | — | `data/raw/boundaries/natural_earth_rivers/ne_10m_rivers_lake_centerlines.shp` |
| cds_tasmax | Copernicus CDS `projections-cmip6`, tasmax diário | `CDS_API_URL`/`CDS_API_KEY` | `data/raw/climate/cds_tasmax/{país}/{modelo}/{cenário}/*.nc`; rasters `data/processed/climate/extreme_heat_days_{país}_{modelo}_{cenário}_{native,1km}.tif`. Área do request e `clip_box` = `_climate_bounds` (união dos bounds GADM com `config.COUNTRY_BBOX_FALLBACK[país]`) |
| aqueduct | WRI Aqueduct 4.0 `future_annual` via GEE | `GEE_PROJECT_ID` (opcional; pula se ausente) | `data/raw/climate/aqueduct/{país}/aqueduct_2050.csv` |
| emdat | EM-DAT Archive, UCLouvain Dataverse (`doi:10.14428/DVN/I0LTPH`) | — | `data/raw/validation/_emdat_archive_raw.xlsx`, `emdat_{país}.csv`; `data/outputs/inspection/emdat_event_counts.csv`, `emdat_coverage.csv` |
| assets_validator | `.xlsx` manual do GEM em `data/raw/assets/` | — | `data/processed/assets/gem_validated_plants_{país}.csv`, `gem_units_detail.csv`, `gem_planned_assets.csv`, `gem_excluded_azores_madeira.csv`, `data/outputs/inspection/gem_validation_report.json` |
| water_stress_processor | `aqueduct_2050.csv` + grade do raster de calor | — | `data/processed/climate/water_stress_{país}_{cenário}_1km.tif` (normalizado) e `water_stress_raw_{país}_{cenário}_1km.tif` (bruto) |
| heat_stress_processor | `extreme_heat_days_{país}_{modelo}_{cenário}_1km.tif` | — | `data/processed/climate/heat_stress_{país}_{modelo}_{cenário}_1km.tif` (normalizado, Min-Max com todos os modelos+cenários do país no mesmo pool; guarda de grade fail-loud antes de agrupar); bruto = o próprio arquivo de entrada (passthrough) |

## Parâmetros fixos (`src/config.py`)

- `COUNTRIES = [Brazil, Portugal, India]`, `COUNTRY_ISO3`.
- `CRS_TARGET = EPSG:4326`, `RESOLUTION_TARGET_DEG = 0.008333` (~1 km nominal).
- `YEAR_TARGET = 2050`, `CMIP6_FUTURE_PERIOD = 2041-01-01 .. 2070-12-31`.
- `CMIP6_SCENARIOS = [ssp126, ssp585]`; `AQUEDUCT_SCENARIOS = [bau, opt, pes]`.
- `CMIP6_SOURCE_ID_CDS = ["gfdl_esm4"]` — **lista**; 2º GCM pendente (V4).
- `EXTREME_HEAT_THRESHOLD_C = 40`.
- `MAINLAND_ONLY_COUNTRIES = {Portugal}`.
- `COUNTRY_BBOX_FALLBACK` — piso de cobertura do download de calor, unido aos
  bounds GADM em `_climate_bounds` (só `cds_tasmax`; `get_country_bounds` e o
  filtro mainland-only não usam). Índia `(67.5, 6.5, 97.5, 37.5)`, Portugal
  `(-9.75, 36.75, -6.0, 43.0)`, Brasil ≈ bounds GADM.

## Dependência entre etapas

`boundaries` primeiro (o `cds_tasmax` e o `aqueduct` usam
`get_country_bounds`/`get_country_geometry`; o `assets_validator` usa
`get_country_bounds` só para o filtro mainland-only de Portugal — degrada com
warning se a fronteira faltar). `climate_downloader` roda os três na ordem
`boundaries → cds_tasmax → aqueduct`.

Depois: `heat_stress_processor` antes de `water_stress_processor` — o
`water` lê um raster `extreme_heat_days_*_1km.tif` como referência de grade
(`_load_reference_grid`). Rodar `water` sem o `heat` processado levanta
`FileNotFoundError` claro.
