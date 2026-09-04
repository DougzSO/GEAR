# 02 — Arquitetura de `src/`

```
src/
  config.py            dependência compartilhada obrigatória — paths, parâmetros,
                       credenciais, require_*()
  downloaders/
    boundaries_downloader.py   GADM 4.1 nível 0; filtro mainland-only; get_country_bounds/geometry
    coastline_downloader.py    Natural Earth 10m coastline (download único global)
    rivers_downloader.py       Natural Earth 10m rivers (download único global)
    cds_tasmax_downloader.py   Copernicus CDS projections-cmip6 -> indicador dias>40C -> raster nativo + 1km
    cds_precipitation_downloader.py  CDS projections-cmip6 pr+tas diário (SPEI futuro) -> valida série bruta + raster QA de média do período; reusa _climate_bounds / _resample_to_1km do cds_tasmax
    aqueduct_downloader.py     WRI Aqueduct 4.0 future_annual via GEE -> CSV largo por país
    emdat_downloader.py        EM-DAT Archive (Dataverse) -> filtro país/tipo -> contagem + cobertura
    assets_validator.py        NÃO baixa — lê .xlsx manual do GEM -> status/agregação/fuel bucket
    climate_downloader.py      orquestrador: boundaries + cds_tasmax + aqueduct
  processors/
    water_stress_processor.py  CSV Aqueduct -> raster normalizado (Min-Max/país, pool bau/opt/pes) + raster bruto; sentinela 9999 -> country_max nos dois
    heat_stress_processor.py   raster extreme_heat_days -> raster normalizado (Min-Max/país, todos os modelos E cenários no mesmo pool: ssp126/ssp370/ssp585 x gfdl_esm4/miroc6); bruto = passthrough do downloader; itera sobre configured_models()
    water_variability_processor.py  CSV Aqueduct sv/iv -> raster normalizado (Min-Max/país, pool bau/opt/pes, SEM log1p) + raster bruto, por indicador; espelha o water_stress_processor, sem sentinela
  index/               camada de índice (CCRS), reconstruída do zero
    ccrs_calculator.py  termo Hazard_{i,s} por planta/cenário/GCM: amostra os rasters brutos ws/sv/iv/heat, aplica Tlog/Tlin com bounds globais congelados (FROZEN_BOUNDS), pesos água/calor por bucket. NÃO monta o CCRS completo (age_factor e EventMultiplier são etapas de montagem separadas, ver age_factor.py) nem as bandas de risco.
    risk_bands.py       WaterRiskBand (cortes absolutos WRI fixos 0,208/0,415/0,667/1,0 sobre S_water = 0,4164·ws_raw + 0,2505·sv_raw + 0,3331·iv_raw) e HeatRiskBand (p25/p75/p95 de extreme_heat_days, GFDL-ESM4 primário, 3 cenários pooled) como colunas SEPARADAS — nunca um score único. Tabela de contingência WaterRiskBand×HeatRiskBand como saída auxiliar. Depende só de ccrs_calculator. Aviso literal de não-comparabilidade do HeatRiskBand em todo relatório gerado.
    age_factor.py       multiplicador ≥ 1: age_factor = 2 - clip(retention(age), 0, 1) em [1,2], age = config.YEAR_TARGET(2050) - commissioning_year. Planta velha aumenta o Hazard. Curvas de retenção por fuel_type: coal — dente de serra com overhaul assumido (decai 0,25pp/ano, ciclo de 5 anos, recupera 70% da perda do ciclo ao completar — ciclo e fração são premissa assumida, não da literatura); wind 1-0,004·age uniforme (CF_initial não existe em nenhum arquivo GEM — a forma 1-0,0015·age/CF_initial é código morto, nunca chamada); hydro 1-0,0055·age (sem o fator 0,79); solar (1-0,007)^age; gas/nuclear/bioenergy = retenção 1,0 → af 1,0 (gas provisório). Mixed = média simples dos age_factor. commissioning_year ausente → 1,0 (mantido, sinalizado). Multiplica ccrs_hazard.csv por plant_uid (nunca soma). Convenção ≥1 confirmada como definitiva pelo autor; spec item D fechado, sem bloco OPEN. Ver docs/DECISIONS.md 2026-09-04 (entrada final).
tests/                 pytest; fixtures sintéticas, sem chamada de API real (exceção: o teste de regressão de bounds do ccrs_calculator lê os rasters processados, pulado com motivo se ausentes)
```

## Convenções observadas / mantidas

- **Retorno estruturado, não exceção crua nem sucesso silencioso.** Downloaders
  que podem falhar por rede/credencial retornam
  `{"success", "path", "reason", ...}`. Exceção crua de lib de terceiros
  (cdsapi, requests, ee) é capturada e convertida.
- **`require_*()` levanta `config.MissingCredentialError`** com instrução
  acionável quando um segredo obrigatório falta. Exceção deliberada: Aqueduct
  não levanta — marca a etapa como `gee_not_configured` (pulada, reportada).
- **Cache por existência de arquivo.** Se a saída já existe e `overwrite=False`,
  não rebaixa/reprocessa.
- **Falhar alto.** Coluna essencial ausente, geometria vazia, zip sem shapefile
  → erro explícito, nunca preenche com NaN nem segue adiante.
- **`config.py` é ponto único de acoplamento.** Todo módulo faz
  `from src.config import ...`. Nada roda sem ele.

## Processors — grade e ordem

Os três processors emitem raster 0–1 normalizado (Min-Max) + acesso ao bruto,
na MESMA grade de `extreme_heat_days_*_1km.tif`. `heat` precisa rodar antes de
`water` e de `water_variability` (ambos leem um raster de calor como
referência de grade). O bruto de calor é o próprio arquivo do downloader
(passthrough); o bruto de água e o de variabilidade sv/iv são rasterizados
pelos respectivos módulos antes do Min-Max. `water_variability` NÃO aplica
log1p (sv/iv têm skew baixo) e não tem máquina de sentinela (WRI não usa 9999
para sv/iv). Domínio de normalização e tratamento de sentinela:
`docs/DECISIONS.md` (entradas de 2026-09-03).

## Camada de índice (`src/index/`)

`ccrs_calculator.py` (termo Hazard) consome os rasters **brutos**
(`water_stress_raw_*`, `seasonal_variability_raw_*`,
`interannual_variability_raw_*`, `extreme_heat_days_*`) e
`gem_validated_plants_{país}.csv` — não os rasters normalizados por país dos
processors (o CCRS tem normalização global própria). Reusa os helpers
`raw_raster_path` dos três processors e `configured_models()`. Bounds globais
congelados em `FROZEN_BOUNDS` com trava de regressão — ver
`05-decisoes-tecnicas.md` item 12. `risk_bands.py` e `age_factor.py` dependem
de `ccrs_calculator` (`age_factor` também de `config.YEAR_TARGET`). Ordem
lógica: `ccrs_calculator` → (`risk_bands`, `age_factor`) → montagem do CCRS
(ainda não escrita). Itens 13 e 14 de `05-decisoes-tecnicas.md`.

## Mudanças estruturais vs. repositório anterior

Ver `docs/memory/05-decisoes-tecnicas.md` (itens sobre lista de GCM,
paths model-tagged, fuel bucket 5→4, `emdat` só descritivo, orquestrador
sem power/slr, e Min-Max de calor por país com modelos e cenários no mesmo
pool + guarda fail-loud de grade).
