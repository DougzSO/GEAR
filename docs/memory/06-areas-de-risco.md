# 06 — Áreas de risco

## Cobertura de teste

- **Coberto (fixtures sintéticas, sem rede):** construção de path de saída,
  tratamento de credencial ausente via `require_*()`, iteração multi-modelo
  do `cds_tasmax`, simplificação de geometria do Aqueduct; para o
  `assets_validator` — filtro de status, agregação por planta, fuel bucketing
  e exclusão mainland-only; para os processors — pool Min-Max conjunto entre
  cenários e modelos (calor) e entre cenários (água), guarda fail-loud de
  grade do calor com 2 modelos sintéticos, substituição da sentinela WRI 9999
  no bruto e no normalizado, passthrough do bruto de calor, preservação de
  NaN; para o `emdat_downloader` — cobertura lat/lon além de `Location` e
  GADM. 86 testes, todos passando em 2026-09-03.
- **Não coberto:** o caminho real download → arquivo em disco para qualquer
  fonte (nenhum teste toca rede, por decisão — consistente com o padrão de
  testes de processor herdado). A resposta real da API do CDS, do GEE e do
  Dataverse não é exercida por teste; a primeira execução real é a primeira
  verificação de que o formato de request/response ainda bate.
- **`cds_tasmax`:** `_compute_extreme_heat_days` e `_resample_to_1km` não têm
  teste com um NetCDF sintético — dependeria de montar um dataset xarray com
  a estrutura exata do CMIP6 (dims `time/lat/lon`, longitude 0-360). Lacuna
  conhecida; adicionar quando houver um `.nc` real pequeno para derivar a
  fixture.
- **Processors:** `load_aqueduct_basins` (parsing do `.geo` GeoJSON) e a
  rasterização real (`rasterize` do rasterio sobre polígonos de bacia) não
  têm teste isolado — só o caminho `rasterize_scenario` com grade sintética.

## Dependências externas frágeis

- **CDS (`projections-cmip6`):** schema de request já mudou historicamente
  (ver docstring do módulo). Requisições ficam em fila; uma requisição de 30
  anos diários por país×modelo×cenário pode levar horas e ~200 MB.
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
  GCM (MIROC6, V4 RESOLVIDO) com grade nativa diferente, ou uma versão nova
  do GADM, pode exigir recalibrar as caixas de Índia e Portugal. A cobertura foi
  verificada contra as coordenadas das usinas GEM (14 Índia + 5 Portugal
  antes fora do raster) — ver `analysis/normalization_diagnostics.md` e a
  entrada datada em `docs/DECISIONS.md`.

## TODOs que bloqueiam fases seguintes

- Second GCM *(passage updated to EN)* — **the V4 model choice is RESOLVED
  (MIROC6, see `docs/DECISIONS.md`)**, but `config.CMIP6_SOURCE_ID_CDS`
  still holds only `gfdl_esm4` — no index code has been written. When
  MIROC6 is added, `heat_stress_processor` already iterates over it
  automatically (new files
  `heat_stress_{country}_{model2}_{scenario}_1km.tif`) and pools the two
  models in the same per-country Min-Max domain; if the second GCM arrives
  on a different grid (bbox/resolution/CRS), `_assert_consistent_grid`
  raises `GridMismatchError` before pooling (fail-loud, not silent).
  Whether to keep the joint pool or revert to per-model normalisation is a
  **separate open question** — the MIROC6 decision closed the choice of
  model, not this design point (see the heat-normalisation entry in
  `docs/DECISIONS.md`). `water_stress_processor` still uses
  `configured_models()[0]` only as a grid reference (grid identical across
  models while the guard passes).
- Toda a camada de índice (SCI/NAES/pesos/resiliência/Monte Carlo) está
  bloqueada por V1–V6 (`ARCHITECTURE.md` Seção 9).

## Limitações metodológicas herdadas (declarar no manuscrito — ver `ARCHITECTURE.md`)

*(Parágrafo atualizado para inglês para refletir V2/V4 fechados.)*

Heat still without bias-correction/ensemble weighting — a second GCM
(MIROC6, V4) is the mitigation on record but is not downloaded yet;
Aqueduct sentinel basins substituted by `country_max`; the
`Status == operating` filter caps the most recent commissioning year;
`event_factor` moves from a fixed 1.0 to a per-country EM-DAT frequency
factor (V2).
