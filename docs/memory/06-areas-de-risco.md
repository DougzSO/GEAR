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
  GADM; para o `ccrs_calculator` — pesos por bucket, propagação/descarte de
  NaN por lado do score, separação GFDL/MIROC6 sem blend, exclusão de `wd`,
  base computável V6, estabilidade do `plant_uid` (reembaralhar/remover linha),
  ausência de cross-join no merge por-GCM; para o `risk_bands` — cortes
  absolutos do WaterRiskBand (limites exatos + valor por faixa), p25/p75/p95
  do HeatRiskBand em amostra sintética, HeatRiskBand só GFDL-ESM4 (nunca
  MIROC6/blend), chave `plant_uid`, ausência de score único combinando as
  bandas, aviso literal de não-comparabilidade no relatório; para o
  `age_factor` — um caso por bucket (incl. gas/nuclear/bioenergy neutros),
  convenção `>= 1` / clip `[1,2]`, `REFERENCE_YEAR == YEAR_TARGET`, coal
  (decaimento dentro de um ciclo, recuperação parcial no limite do ciclo,
  múltiplos ciclos), wind uniforme 0,4%/ano + checagem de inalcançabilidade do
  branch morto de `CF_initial` (inspeção de `inspect.getsource`), mixed fuel,
  `commissioning_year` ausente, aplicação multiplicativa por `plant_uid`,
  guarda de CSV desatualizado; para o `event_multiplier` — os 3 países contra
  a fixture de regressão, `rate_max`/`>= 1`, join por `country` sem duplicar
  nem derrubar linha de `plant_uid` (reembaralhamento de contagem por
  planta), guarda contra país ausente e contra país duplicado na tabela de
  multiplicadores (`MergeError` do `validate="many_to_one"`). 201 testes,
  todos passando em 2026-09-04.
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

- **Camada de índice (CCRS) — Hazard, bandas de risco, age_factor e
  EventMultiplier escritos.** `ccrs_calculator.py` (Hazard), `risk_bands.py`
  (Water/HeatRiskBand), `age_factor.py` (multiplicador `≥ 1`),
  `event_multiplier.py` (multiplicador `≥ 1` por país). V1–V6 todos
  fechados. O que ainda falta:
  - código de produção: **montagem do `CCRS_i,s` = Hazard × age_factor ×
    EventMultiplier** numa coluna única (os três fatores já existem
    isoladamente, com `apply_to_hazard` provando o join/multiplicação de cada
    um), relatórios per-country de share de capacidade por banda, wrapper de
    Monte Carlo;
  - itens ainda em aberto na spec: termo de SPEI (F), clip de outlier em sv/iv
    (I), sensibilidade Monte Carlo do split térmico e do `k` do
    `EventMultiplier` (J). Fechados na implementação: G (bounds congelados,
    `FROZEN_BOUNDS` + trava, item 12), **D** (`age_factor ≥ 1`,
    `2 - retention(age)`, convenção confirmada como definitiva pelo autor —
    `docs/DECISIONS.md` 2026-09-04, entrada final; ver item 14 de
    `05-decisoes-tecnicas.md` para o histórico das três entradas) e **C**
    (`EventMultiplier_c`, sem divergência entre spec e ARCHITECTURE — item 15
    de `05-decisoes-tecnicas.md`).
- **`age_factor` wind — sem branch de `CF_initial`, código morto verificado.**
  `CF_initial` (fator de capacidade inicial) não existe em nenhum arquivo GEM
  (confirmado nas 1986 usinas: BR 1126 / PT 225 / IN 635). `age_factor` usa
  `1 - 0,004·age` uniformemente, sem condicional nem checagem em runtime. A
  forma `1 - 0,0015·age/CF_initial` (`_wind_retention_from_cf_initial`) é
  código morto de fato — nunca chamada por `age_factor` nem por qualquer
  função no seu caminho ativo, verificado por inspeção de `inspect.getsource`
  em `test_wind_cf_initial_formula_exists_but_is_dead_code`, e `age_factor`
  não aceita mais `cf_initial` como argumento. Fica pronta para uma fonte real
  de fator de capacidade (Global Wind Atlas, dado de fabricante).
- **`age_factor` coal — overhaul assumido (dente de serra), parâmetro
  estimado.** Sem dado real de overhaul por planta no GEM. A curva decai
  0,25 pp/ano (`COAL_DECAY_RATE`, literatura) dentro de um ciclo de
  `COAL_OVERHAUL_CYCLE_YEARS = 5` anos; ao completar o ciclo, recupera
  `COAL_OVERHAUL_RECOVERY = 70%` da perda acumulada naquele ciclo (30% fica
  permanente). **O ciclo de 5 anos e os 70% são premissa assumida, não
  extraída de Kim & Moon (2012) / Sagaf (2020)** (essas fontes só dão a taxa
  de 0,25 pp/ano) — marcado provisório/estimado, revisável se surgir dado real
  de overhaul.
- **`age_factor` gas/oil-gas é provisório.** Sem taxa na literatura dos docs →
  pinado em 1,0. Revisitar se surgir fonte. `docs/DECISIONS.md` marca o status
  como provisório.
- **Índia: 9,7% das plantas sem `commissioning_year`** (494/5083, vs BR 1,8% e
  PT 2,4%) → rodam com `age_factor = 1,0` neutro. Não é bug de parsing (o
  mesmo código lê BR/PT sem problema; hydro/thermal da Índia leem bem). A
  falta concentra-se em **wind (258) e solar (172), zero hydro** — provável
  cobertura incompleta de metadados de comissionamento do GEM p/ renováveis
  indianas. Capacidade mediana das plantas sem ano: 24 MW. ~1 em cada 10
  plantas indianas no CCRS carrega idade neutra por falta de dado. Declarar
  no manuscrito. As linhas são **mantidas** e sinalizadas
  (`age_factor_neutralized_missing_year`), nunca excluídas.
- **`age_factor` depende de `ccrs_hazard.csv` estar atualizado.**
  `apply_to_hazard` levanta `ValueError` se algum `plant_uid` do CSV não tiver
  `age_factor` (CSV gerado com esquema de `plant_uid` antigo). Regerar com
  `python -m src.index.ccrs_calculator`.
- **Trava de regressão de bounds depende dos rasters em disco.**
  `test_ccrs_calculator::test_frozen_bounds_match_recomputed_from_data` lê os
  rasters processados; é **pulado com motivo** (não passa em silêncio) se
  ausentes. Num checkout sem `data/processed/` a trava não roda — rodar
  `python -m src.index.ccrs_calculator --check-bounds` depois de reprocessar.
- **HeatRiskBand não é comparável entre rodadas.** Cortes p25/p75/p95
  dependem do pool de amostra (GFDL-ESM4, 3 cenários) — reprocessar rasters de
  calor, mudar cenário/GCM ou o conjunto de plantas move os cortes
  silenciosamente. `risk_bands.HEAT_BAND_WARNING` avisa disso em todo
  relatório. WaterRiskBand não tem esse problema (cortes absolutos fixos). Não
  há trava de regressão de cortes de HeatRiskBand — por design, os cortes são
  amostrais, não uma constante a congelar.
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
