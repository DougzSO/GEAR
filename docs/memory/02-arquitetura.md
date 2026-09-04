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
tests/                 pytest; fixtures sintéticas, sem chamada de API real
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

## Mudanças estruturais vs. repositório anterior

Ver `docs/memory/05-decisoes-tecnicas.md` (itens sobre lista de GCM,
paths model-tagged, fuel bucket 5→4, `emdat` só descritivo, orquestrador
sem power/slr, e Min-Max de calor por país com modelos e cenários no mesmo
pool + guarda fail-loud de grade).
