# 05 — Decisões técnicas (engenharia)

Decisões de engenharia, não científicas. Decisões de fonte de dado /
metodologia estão em `docs/DECISIONS.md`; itens de julgamento do autor em
`docs/ARCHITECTURE.md`.

---

## 1. `CMIP6_SOURCE_ID_CDS` é uma lista, não uma string

- **Contexto:** `ARCHITECTURE.md` Seção 4 torna um 2º GCM sensitivity check
  obrigatório. No repositório anterior era `CMIP6_SOURCE_ID_CDS = "gfdl_esm4"`.
- **Decisão:** `config.CMIP6_SOURCE_ID_CDS = ["gfdl_esm4", "miroc6"]`
  (gfdl_esm4 sempre primeiro — grade de referência da água). O
  `cds_tasmax_downloader` itera sobre a lista (`configured_models()`, que
  filtra entradas vazias e levanta se a lista ficar vazia); o
  `cds_precipitation_downloader` reusa `configured_models()`. Paths e
  rasters de saída carregam o id do modelo.
- **Consequences** *(bullet updated to EN):* the raster names carry the
  model id (see item 2) — every processor reads the model-tagged pattern.
  V4 is closed: MIROC6 is in the config and all 2-GCM × 3-scenario heat and
  water rasters have been downloaded and processed (see `docs/DECISIONS.md`).
- **Arquivos:** `src/config.py`, `src/downloaders/cds_tasmax_downloader.py`,
  `src/downloaders/cds_precipitation_downloader.py`,
  `tests/test_cds_tasmax_downloader.py`,
  `tests/test_cds_precipitation_downloader.py`.
- **Status:** Ativa.

## 2. Rasters de calor com id do modelo no nome

- **Contexto:** com >1 GCM, `extreme_heat_days_{país}_{cenário}_1km.tif`
  colidiria entre modelos.
- **Decisão:** `extreme_heat_days_{país}_{modelo}_{cenário}_{native,1km}.tif`
  e `data/raw/climate/cds_tasmax/{país}/{modelo}/{cenário}/`.
- **Consequências:** difere do nome citado em `docs/INVENTORY.md`
  (`extreme_heat_days_*_{1km,native}.tif`, sem modelo). INVENTORY descreve o
  estado antigo; este é o novo. O `heat_stress_processor` (quando reescrito)
  precisa saber o modelo.
- **Arquivos:** `src/downloaders/cds_tasmax_downloader.py`.
- **Status:** Ativa.

## 3. Fuel bucket: 4 categorias, coluna `fuel_type_bucket`

- **Contexto:** repositório anterior tinha 5 buckets
  (`hydro/wind/solar/coal/thermal_other`), coluna `fuel_type_ahp_bucket`,
  acoplada ao método AHP descartado.
- **Decisão:** 4 buckets `{hydro, wind, solar, thermal}` — carvão fundido em
  `thermal` junto com oil/gas, nuclear, bioenergia, geotérmica. Coluna
  `fuel_type_bucket`. 7 overrides manuais por nome para plantas
  `mixed_fuel_type` (todos resolvem para `thermal`).
- **Consequências:** alinha com `ARCHITECTURE.md` Seção 6 (fusão confirmada)
  e `INVENTORY.md` (rename para remover acoplamento ao AHP). A tensão de
  curva de idade dentro do bucket fundido era o item V1 — **fechado**:
  sub-curvas de `age_factor` por `fuel_type`, depois revisadas com
  literatura adicional (ver `docs/DECISIONS.md`, entradas V1). A fusão é
  mantida só para os pesos água/calor por bucket. Também logado em
  `docs/DECISIONS.md`.
- **Arquivos:** `src/downloaders/assets_validator.py`
  (`FUEL_TYPE_TO_BUCKET`, `MIXED_FUEL_BUCKET_OVERRIDES`, `add_fuel_bucket`),
  `tests/test_assets_validator.py`.
- **Status:** Ativa.

## 4. `emdat_downloader` é só aquisição + descrição

- **Contexto:** pedido explícito da etapa — "acquisition only, no validation
  logic".
- **Decisão:** o módulo baixa, filtra por ISO e tipo de desastre, e produz
  contagem por país/tipo/ano e cobertura de geocodificação (`Location` texto
  livre e `GADM Admin Units` estruturado). Nenhuma comparação com hotspots
  de risco, nenhuma geocodificação ponto-a-ponto.
- **Consequences** *(bullet updated to EN):* the fixed `event_factor` 1.0
  is replaced by `EventMultiplier_c` (V2 closed — country-level, not
  state/district). Under the CCRS it is a multiplier on the score, not a
  resilience sub-factor, with the form
  `EventMultiplier_c = 1 + 0.5·(rate_c/rate_max)`, `rate_c = N_events(c)/124`
  (`ARCHITECTURE.md` §7.2, `docs/DECISIONS.md`). It uses `emdat_coverage.csv`
  and `analysis/emdat_coverage_diagnostics.md` as inputs, but the code lives
  in the (not-yet-written) index layer, not here.
- **Arquivos:** `src/downloaders/emdat_downloader.py`.
- **Status:** Ativa.

## 5. Orquestrador de clima sem power/slr

- **Contexto:** `climate_downloader` antigo chamava também
  `power_downloader` e `slr_downloader`, não portados.
- **Decisão:** `ALL_STEPS = ["boundaries", "cds_tasmax", "aqueduct"]`. O
  resumo distingue "pulado por design" (Aqueduct sem `GEE_PROJECT_ID`) de
  "falha real" — Aqueduct pulado não derruba `overall_success`.
- **Arquivos:** `src/downloaders/climate_downloader.py`,
  `tests/test_climate_downloader.py`.
- **Status:** Ativa.

## 6. Constantes ANEEL/DGOVPT retidas, downloaders não

- **Contexto:** a tabela de `config.py` em `INVENTORY.md` lista
  `ANEEL_CKAN_BASE_URL` e `DGOVPT_API_BASE_URL`; os downloaders que as usam
  (`aneel_downloader`, `dgeg_downloader`) não são portados.
- **Decisão:** as constantes ficam em `config.py` com comentário de que os
  consumidores estão fora do escopo desta reconstrução; `POWER_BASE_URL`
  (marcada "Removido" na própria tabela) foi omitida.
- **Consequências:** config inerte até uma decisão futura sobre fontes
  complementares de ativos.
- **Arquivos:** `src/config.py`.
- **Status:** Incerta (inferido — depende de decisão do autor sobre fontes
  complementares).

## 7. Aqueduct: polígono simplificado antes da query GEE

- **Contexto:** o polígono GADM nível 0 de Brasil/Índia em cheio tem
  ~16-19 MB como GeoJSON; passar isso inline para `ee.Geometry` estoura o
  limite de 10 MB de payload da API do Earth Engine — a query falha
  (`Request payload size exceeds the limit`), confirmado em 2026-09-03.
  Portugal (pequeno) passava; Brasil/Índia não.
- **Decisão:** `get_country_geometry(country).simplify(0.05)` (~5 km) antes
  de converter para `ee.Geometry`. Constante
  `aqueduct_downloader.GEOMETRY_SIMPLIFY_TOLERANCE_DEG`.
- **Consequências:** simplificação é obrigatória, não otimização (o polígono
  cru falha na query). Impacto medido em 2026-09-03 (`simplify(0.05)` vs
  `simplify(0.0005)`): Índia 403 bacias nos dois; Brasil 1118 vs 1115 — a
  borda a 0.05 é levemente mais "gorda" e puxa 5 bacias a mais (4 interiores,
  1 costeira, pfaf_id 616707), perde 2 interiores. Efeito pequeno e
  direcional, não nulo. Detalhe completo em `docs/DECISIONS.md`.
- **Arquivos:** `src/downloaders/aqueduct_downloader.py`.
- **Status:** Ativa.

## 8. Ambiente e libs

- **Contexto:** `INVENTORY.md` restringe as libs desta camada.
- **Decisão:** `requirements.txt` só com o que a camada importa + `pytest`.
  `.venv` dedicado na raiz. Versões resolvidas na 1ª instalação (`pip freeze`
  literal, `.venv`, 2026-09-03):

  ```
  cdsapi==0.7.7
  earthengine-api==1.7.42
  geopandas==1.1.4
  h5netcdf==1.8.1
  netCDF4==1.7.4
  numpy==2.4.6
  openpyxl==3.1.5
  pandas==3.0.5
  pyproj==3.7.2
  pytest==9.1.1
  python-dotenv==1.2.3
  rasterio==1.4.4
  requests==2.34.2
  rioxarray==0.19.0
  shapely==2.1.2
  tqdm==4.70.0
  xarray==2026.7.0
  ```

- **Consequências:** pandas 3 / numpy 2 são recentes — atenção a
  `DataFrame.from_records` com `None` virando `NaN` em coluna object
  (visto nos testes do `assets_validator`). `geopandas` 1.x usa `pyogrio`
  como engine de I/O por padrão.
- **Arquivos:** `requirements.txt`, `pytest.ini`.
- **Status:** Ativa.

## 9. Processors de clima — grade compartilhada e ordem

- **Contexto:** os três processors precisam emitir raster na mesma grade
  pixel-a-pixel para a álgebra de mapas da camada de índice (CCRS, ainda
  não escrita em `src/`).
- **Decisão:** `water_stress_processor._load_reference_grid` (e o
  equivalente no `water_variability_processor`) lê
  `extreme_heat_days_{país}_{modelo}_{cenário}_1km.tif` (primeiro modelo
  configurado, ssp126) como referência de grade e rasteriza a água / sv-iv
  nela. Consequência: `heat_stress_processor` tem que rodar antes dos dois.
- **Consequências:** a grade 1 km depende só de bounds do país + resolução
  alvo → idêntica entre modelos e cenários, então qualquer raster de calor
  serve de referência. As decisões de domínio de normalização (Min-Max por
  país para água e para sv/iv; por país com modelos **e** cenários no mesmo
  pool para calor) e de tratamento da sentinela WRI 9999 estão em
  `docs/DECISIONS.md` (metodológicas), não aqui.
- **Arquivos:** `src/processors/water_stress_processor.py`,
  `src/processors/heat_stress_processor.py`,
  `src/processors/water_variability_processor.py`.
- **Status:** Ativa.

## 10. Calor: Min-Max por país, modelos e cenários no mesmo pool

- **Contexto:** o repositório anterior fazia Min-Max por país sobre os 2
  cenários CMIP6 (1 GCM só). Uma revisão intermediária tornou o domínio por
  país **e por modelo**; isso foi revertido para o desenho originalmente
  especificado.
- **Decisão:** `heat_stress_processor.compute_country_minmax(country)` —
  pool conjunto de todos os modelos de `configured_models()` **e** dos 2
  cenários daquele país num único domínio. Nunca combina países. Output
  continua model-tagged (`heat_stress_{país}_{modelo}_{cenário}_1km.tif`),
  mas os arquivos de um país compartilham um `country_min`/`country_max`.
- **Guarda fail-loud:** `_assert_consistent_grid` levanta `GridMismatchError`
  se os rasters a agrupar divergem em shape, resolução/transform ou CRS.
  No-op com 1 modelo; existe para o 2º GCM (V4) falhar alto em vez de
  desalinhar o stack silenciosamente. Testado com 2 modelos sintéticos
  (pool conjunto correto + erro em mismatch de grade).
- **Consequências:** `process_all_countries` itera
  `country → (carrega+valida grade+minmax) → model → scenario`. MIROC6 (V4
  fechado) de fato tem extremos bem acima do GFDL-ESM4 e domina a escala
  normalizada conjunta — por isso o CCRS consome o raster **bruto** de
  calor, não o normalizado por país (ver `analysis/climate_risk_score_spec.md`).
  Manter pool conjunto vs. voltar a por-modelo no raster normalizado
  standalone segue como questão aberta de desenho (V4 fechou a escolha do
  modelo, não este ponto; ver `docs/DECISIONS.md`).
- **Arquivos:** `src/processors/heat_stress_processor.py`,
  `tests/test_heat_stress_processor.py`.
- **Status:** Ativa. Também em `docs/DECISIONS.md`.

## 11. `COUNTRY_BBOX_FALLBACK` passou a ser o piso de cobertura do download de calor

- **Contexto:** `COUNTRY_BBOX_FALLBACK` era código morto — nenhum módulo o lia;
  a área do request CDS e o `clip_box` do `_resample_to_1km` vinham só de
  `get_country_bounds` (bounds da geometria GADM nível 0). Dois efeitos
  encolhiam essa caixa abaixo do território de estudo: (a) GADM nível 0 da
  Índia para em ~33,26 N / ~68,19 E — exclui a maior parte de Jammu &
  Caxemira / Ladaque e o oeste do Kutch, onde há usinas operantes no escopo;
  (b) a grade nativa do GCM (~1° lat, ~1,25° lon) faz *snap* da área pedida
  para dentro, cortando até uma célula na borda norte de Portugal
  continental (usinas ~42,08 N caíam na borda da célula de 42,0).
- **Decisão:** `cds_tasmax_downloader._climate_bounds(country)` retorna a
  união coordenada a coordenada de `get_country_bounds` e
  `config.COUNTRY_BBOX_FALLBACK[country]`; usada tanto para `area` do request
  quanto para o `clip_box`. `COUNTRY_BBOX_FALLBACK` reescrito: Índia
  `(67.5, 6.5, 97.5, 37.5)`, Portugal `(-9.75, 36.75, -6.0, 43.0)` (só
  continente — **não** re-inclui Açores/Madeira). Brasil inalterado
  (`(-73.99, -33.75, -28.84, 5.27)` ≈ bounds GADM → união é no-op).
- **Consequências:** `get_country_bounds` **não** foi tocado — o
  `assets_validator` (filtro mainland-only de Portugal) continua usando os
  bounds GADM crus, como deve. Rasters de calor de Índia e Portugal
  re-baixados e re-processados; o de Brasil não muda. A guarda de grade do
  `heat_stress_processor` é por país, então Brasil em grade antiga e
  Índia/Portugal em grade nova não conflitam.
- **Arquivos:** `src/config.py`, `src/downloaders/cds_tasmax_downloader.py`,
  `tests/test_cds_tasmax_downloader.py`.
- **Status:** Ativa. Também em `docs/DECISIONS.md` (números de cobertura
  antes/depois).

## 12. CCRS — bounds globais congelados e como o Hazard é montado

- **Contexto:** a spec (`analysis/climate_risk_score_spec.md` §4, §8, item
  aberto G) fixa que o Min-Max de cada termo é **global** (3 países × 3
  cenários agrupados) e "constante fixa e documentada, não recomputada por
  rodada". Não havia código; o único precedente era
  `analysis/ccrs_bucket_weighted_distribution.py` (diagnóstico), que calcula
  bounds **por-GCM** sobre linhas casadas nos 4 termos.
- **Decisão** (`src/index/ccrs_calculator.py`):
  - `ws`/`sv`/`iv`: **um** par `(min, max)` por termo. Os rasters de água não
    dependem do GCM; o pool é sobre as plantas (com `fuel_type_bucket`
    conhecido — hoje **todas** as 10 808 plantas validadas) cujo termo é
    finito, 3 países × 3 cenários. Verificado: amostrar com GFDL ou MIROC6 dá
    o mesmo conjunto e os mesmos números (32 301 linhas planta×cenário com
    `ws`/`sv`/`iv` finito; 123 sem — plantas fora de qualquer bacia Aqueduct).
  - `heat`: **um par por GCM** (`gfdl_esm4`, `miroc6` separados). MIROC6 roda
    ~10–100× GFDL; um pool conjunto seria um blend inter-modelo, proibido pela
    §5.4. Alinhado com a regra "GFDL primário, MIROC6 painel de sensibilidade,
    nunca 50/50".
  - Valores gravados em `FROZEN_BOUNDS` (constante do módulo, não em
    `config.py` — é constante da camada de índice, e `config.py` é dependência
    da camada de aquisição). `BOUNDS_DATA_SNAPSHOT = "2026-09-04"`.
  - Trava de regressão: `compute_global_bounds()` recalcula dos rasters;
    `assert_frozen_bounds_current()` / o teste `test_ccrs_calculator` comparam
    e **falham** (`BoundsRegressionError`) se divergir. Atualizar
    `FROZEN_BOUNDS` exige revisão manual explícita com o diff no commit —
    nunca recalcular e aceitar em silêncio.
  - Montagem do Hazard: `w_water[bucket]·water_sub + w_heat[bucket]·Tlog(heat)`,
    `water_sub = 0.4164·Tlog(ws) + 0.2505·Tlin(sv) + 0.3331·Tlin(iv)`. Um lado
    com peso 0 (`hydro` sem calor, `wind`/`solar` sem água) é descartado antes
    da multiplicação, então um termo NaN nesse lado não contamina o score;
    onde o peso é > 0, o NaN propaga (planta sem hazard nesse cenário).
  - `age_factor` (item aberto D) e `EventMultiplier` **não** são aplicados
    aqui — o módulo entrega só o termo Hazard.
  - **Identidade de planta:** `(country, plant_name)` NÃO é única — 429 grupos
    de nome têm vários registros GEM distintos (coordenadas diferentes, mesmo
    nome; 265 desses também compartilham `capacity_mw` + `commissioning_year`).
    Não há identificador nativo do GEM no
    `gem_validated_plants_{país}.csv` — os IDs do GEM (`GEM unit/phase ID`,
    `GEM location ID`) só existem no `gem_units_detail.csv` em grão de unidade
    e não são propagados pela agregação unidade→planta do `assets_validator`.
    `load_plants` então deriva `plant_uid =
    {ISO3}-blake2s(plant_name | lat | lon)` sobre os **tokens de texto crus**
    do CSV (atributos do registro, nunca a posição/ordem na tabela) — hash
    determinístico (`hashlib.blake2s`, 48 bits), estável a reordenação,
    filtragem e reexportação enquanto os três campos não mudarem byte a byte;
    uma edição real de nome/coordenada gera uid novo (correto, é outro
    registro). `(plant_name, lat, lon)` é único nos 3 países hoje; `load_plants`
    levanta `ValueError` se o hash colidir. Esse uid é a chave de merge em
    `compute_hazard_by_gcm`; sem identificador estável o merge por-GCM fazia
    cross-join parcial nos 265 grupos e inflava a saída para 46 998 linhas em
    vez de 32 424 (10 808 plantas × 3 cenários). `compute_hazard_by_gcm`
    levanta `RuntimeError` se restar chave duplicada após o merge.
- **Idioma:** o módulo e o teste estão em inglês — convenção real do código em
  `src/` (docstrings/comentários em inglês, vide `water_variability_processor`,
  `config.py`). `docs/memory/` continua em português.
- **Consequências:** `FROZEN_BOUNDS` fica desatualizado se qualquer raster de
  `ws`/`sv`/`iv`/`heat` for reprocessado ou se países/cenários mudarem — a
  trava de regressão captura isso na próxima execução do teste. O CSV de saída
  (`data/outputs/tables/ccrs_hazard.csv`) traz `plant_uid`, `lat`/`lon` e
  `hazard_gfdl_esm4` / `hazard_miroc6` em colunas separadas, nunca combinadas;
  uma linha por `plant_uid` × cenário.
- **Arquivos:** `src/index/ccrs_calculator.py`,
  `tests/test_ccrs_calculator.py`.
- **Status:** Ativa. Eixo GCM dos bounds (heat por-GCM, água GCM-independente)
  **formalizado** em `docs/DECISIONS.md`, entrada "[2026-09-04] CCRS global
  Min-Max bounds: heat per-GCM, water GCM-independent" — a spec item G não
  detalhava esse eixo; a entrada é a formalização retroativa.

  > ⚠️ Ponto a validar (Douglas): correção — a afirmação anterior de "2
  > plantas/país sem `fuel_type_bucket`" (herdada de um docstring
  > desatualizado de `analysis/ccrs_bucket_weighted_distribution.py`) está
  > **errada**. Nos `gem_validated_plants_{país}.csv` atuais **todas** as
  > plantas mapeiam para um dos 4 buckets — nenhuma planta é excluída do pool
  > por bucket ausente. As únicas exclusões por termo são amostras NaN
  > (planta fora de bacia/raster), que são "sem valor a contribuir", não
  > exclusão de planta.
