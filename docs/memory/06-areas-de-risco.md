# 06 — Áreas de risco

## Cobertura de teste

- **Coberto (fixtures sintéticas, sem rede):** construção de path de saída,
  tratamento de credencial ausente via `require_*()`, iteração multi-modelo
  do `cds_tasmax`, forma do request + reuso das funções de grade e conversão
  de unidade pr/tas do `cds_precipitation` (espelha o `cds_tasmax`),
  simplificação de geometria do Aqueduct; para o
  `assets_validator` — filtro de status, agregação por planta, fuel bucketing
  e exclusão mainland-only; para os processors — pool Min-Max conjunto entre
  cenários e modelos (calor) e entre cenários (água), guarda fail-loud de
  grade do calor com 2 modelos sintéticos, substituição da sentinela WRI 9999
  no bruto e no normalizado, passthrough do bruto de calor, preservação de
  NaN; para o `emdat_downloader` — cobertura lat/lon além de `Location` e
  GADM; para o `ccrs_calculator` — aplicação dos pesos por bucket (um caso
  por bucket), propagação/descarte de NaN por lado do score, separação
  GFDL/MIROC6 em colunas distintas sem blend, exclusão de `wd`, base
  computável V6. 141 testes, todos passando em 2026-09-04.
- **Não coberto:** o caminho real download → arquivo em disco para qualquer
  fonte (nenhum teste toca rede, por decisão — consistente com o padrão de
  testes de processor herdado). A resposta real da API do CDS, do GEE e do
  Dataverse não é exercida por teste; a primeira execução real é a primeira
  verificação de que o formato de request/response ainda bate.
- **`cds_tasmax`:** `_compute_extreme_heat_days` não tem teste com um NetCDF
  sintético — dependeria de montar um dataset xarray com a estrutura exata
  do CMIP6 (dims `time/lat/lon`, longitude 0-360). O
  `test_cds_precipitation_downloader` já usa um dataset sintético desses
  (`_synth_ds`) para testar `_period_mean` e `validate_raw_series` e para
  provar que `_resample_to_1km` é a mesma função do `cds_tasmax` (não uma
  cópia divergente); a lacuna que resta é `_compute_extreme_heat_days` e o
  caminho `.rio.reproject` real.
- **Processors:** `load_aqueduct_basins` (parsing do `.geo` GeoJSON) e a
  rasterização real (`rasterize` do rasterio sobre polígonos de bacia) não
  têm teste isolado — só o caminho `rasterize_scenario` com grade sintética.

## Dependências externas frágeis

- **CDS (`projections-cmip6`):** schema de request já mudou historicamente
  (ver docstring do módulo). Requisições ficam em fila; uma requisição de 30
  anos diários por país×modelo×cenário pode levar horas e ~200 MB. O
  `cds_precipitation_downloader` faz 36 dessas em série (pr + tas × 2 GCMs ×
  3 cenários × 3 países) — job de background longo.
- **GEE:** exige `GEE_PROJECT_ID` **e** um token local de
  `earthengine authenticate` que não passa por `credentials.local`. Sem o
  token, `ee.Initialize` falha e a etapa é marcada como falha de init (não
  "pulada" — "pulada" é só quando falta o `GEE_PROJECT_ID`). O polígono
  GADM nível 0 de Brasil/Índia em cheio (17–20 MB GeoJSON) estoura o limite
  de 10 MB de payload do EE — `simplify(0.05)` é obrigatório. Impacto medido:
  Índia 0 bacias de diferença; Brasil +3 bacias de borda (1 costeira) vs
  quase-nativo (ver `docs/DECISIONS.md`).
- **Dataverse UCLouvain:** o `file_id` do `.xlsx` do EM-DAT muda a cada
  versão publicada; a descoberta por keyword (`emdat_archive`) quebra se o
  EM-DAT renomear o arquivo. `discover_archive_file` levanta erro claro nesse
  caso.
- **GADM:** `geodata.ucdavis.edu` já teve instabilidade no passado; os gpkg
  são grandes (Brasil ~290 MB). Sem checksum publicado — a validação é só
  "abre e não está vazio".
- **Natural Earth (naciscdn.org):** nome do `.shp` dentro do zip é assumido;
  `download_coastline`/`download_rivers` levantam se não encontrarem.

## Hardcode / suposições

- `COLUMN_MAPPING` do `assets_validator` é fixo para o layout do export
  "Global Integrated Power Tracker" de 2026-08-09. Export novo com nomes de
  coluna diferentes → `_apply_mapping` levanta (não preenche NaN). Rodar
  `--discover` antes.
- `MIXED_FUEL_BUCKET_OVERRIDES`: 7 nomes de planta. Planta `mixed_fuel_type`
  nova sem override → `add_fuel_bucket` levanta.
- `FUEL_TYPE_TO_BUCKET`: 8 valores de `Type` do GEM. `Type` novo não mapeado
  → levanta.
- Heurística mainland-only (maior polígono por área) — **precisa conferência
  visual pelo menos uma vez** antes de assumir que pegou o continente certo.
- Filtro de longitude 0-360 → -180/180 no `cds_tasmax` assume nome de coord
  `lon` (não `longitude`).
- `config.COUNTRY_BBOX_FALLBACK` é hardcode calibrado para a grade nativa do
  GFDL-ESM4 (~1° lat, ~1,25° lon) e para o recorte do GADM 4.1 nível 0. O 2º
  GCM (MIROC6, V4 fechado) foi baixado: sua grade nativa ~1,4° deixa só 2
  células de longitude sobre Portugal continental e **34 de 450 usinas
  portuguesas** (faixa costeira Lisboa/Torres Vedras/Lourinhã + Refinaria de
  Sines) caem fora do raster MIROC6, pontuadas só por GFDL-ESM4 (Brasil 12,
  Índia 0). As caixas **não** foram recalibradas para isso — é limitação
  declarada no manuscrito, não bug (`docs/DECISIONS.md`, entrada MIROC6/V4,
  e `analysis/normalization_diagnostics.md`). Uma versão nova do GADM ainda
  poderia exigir recalibrar Índia/Portugal.

## TODOs que bloqueiam fases seguintes

- **Camada de índice (CCRS) — só o termo Hazard escrito em `src/`.**
  `src/index/ccrs_calculator.py` calcula `Hazard_{i,s}` (transformação global
  por termo + pesos por bucket, bounds congelados). V1–V6 todos fechados; o
  desenho está em `docs/ARCHITECTURE.md` Seção 5 e
  `analysis/climate_risk_score_spec.md`. O que ainda falta:
  - código de produção: montagem do `CCRS_i,s` (× `age_factor` ×
    `EventMultiplier`), `age_factor`, `EventMultiplier`, classificadores de
    banda (WaterRiskBand/HeatRiskBand), geradores de relatório, wrapper de
    Monte Carlo;
  - itens ainda em aberto na spec: mapeamento das curvas %/ano do
    `age_factor` para multiplicador ≥ 1 (D), se um termo de SPEI é
    adicionado (F), clip de outlier em sv/iv (I), sensibilidade Monte Carlo
    dos dois parâmetros de julgamento — split térmico e `k` do
    `EventMultiplier` (J). Item G (bounds globais congelados) foi **efetuado**
    para os dados de 2026-09-04 em `FROZEN_BOUNDS`, com trava de regressão;
    ver `05-decisoes-tecnicas.md` item 12 e o ⚠️ Ponto a validar ali.
- **Trava de regressão de bounds depende dos rasters em disco.**
  `test_ccrs_calculator::test_frozen_bounds_match_recomputed_from_data` lê os
  rasters processados; é **pulado com motivo** (não passa em silêncio) se
  ausentes. Num checkout sem `data/processed/` a trava não roda — rodar
  `python -m src.index.ccrs_calculator --check-bounds` depois de reprocessar.
- **Pool de Min-Max de calor: conjunto vs. por-modelo.** MIROC6 (V4 fechado)
  domina a escala normalizada conjunta; o CCRS contorna isso consumindo o
  raster **bruto** de calor. Manter o pool conjunto ou voltar a por-modelo
  no raster normalizado standalone segue como questão de desenho em aberto
  (`docs/DECISIONS.md`, entrada de normalização de calor). `_assert_consistent_grid`
  já falha alto (`GridMismatchError`) se rasters a agrupar divergirem em
  grade.
- **SPEI:** os 36 downloads de pr/tas (2 GCMs × 3 cenários × 3 países) estão
  **concluídos** — 36/36 `.nc` validados, série diária 2041–2070 completa
  (GFDL-ESM4 `n=10950` noleap, MIROC6 `n=10957`), 72 rasters QA de média do
  período gravados (`logs/spei_download_report.json`). `spei_processor`
  **não** implementado — SPEI é cálculo de série temporal completa, não
  média de período, e é meta separada a definir.

## Limitações metodológicas herdadas (declarar no manuscrito — ver `ARCHITECTURE.md`)

*(Parágrafo em inglês; V1–V6 todos fechados, arquitetura CCRS.)*

Heat still without bias-correction/ensemble weighting — the mandatory second
GCM (MIROC6, V4) is the mitigation on record, downloaded and processed
(2 GCMs × 3 scenarios); GFDL-ESM4 is the primary GCM for every cited CCRS
figure and MIROC6 a sensitivity panel, never a 50/50 blend
(`ARCHITECTURE.md` §5.4). Aqueduct sentinel basins substituted by
`country_max`. The `Status == operating` filter caps the most recent
commissioning year, feeding `age_factor`. `event_factor` becomes
`EventMultiplier_c` — a per-country EM-DAT frequency multiplier on the CCRS
score (V2), `1 + 0.5·(rate_c/rate_max)`. `fuel_factor` removed entirely
(V5 closed). `HeatRiskBand` has no published absolute threshold and uses
sample-relative percentile cuts, GCM-sensitive — declared limitation
(`ARCHITECTURE.md` §10).
