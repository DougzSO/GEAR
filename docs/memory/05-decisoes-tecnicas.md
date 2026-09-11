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

## 13. CCRS bandas de risco — `risk_bands.py`

- **Contexto:** o CCRS classifica cada planta com **duas bandas discretas
  independentes** (spec §8, `ARCHITECTURE.md` §5.2). Sem divergência entre
  spec e ARCHITECTURE nos cortes/fórmulas. Precedente de diagnóstico:
  `analysis/water_risk_band_classification.py` e `analysis/ccrs_final_summary.py`.
- **Decisão** (`src/index/risk_bands.py`, depende só de `ccrs_calculator`):
  - **WaterRiskBand:** `S_water = 0,4164·ws_raw + 0,2505·sv_raw + 0,3331·iv_raw`
    (valores **brutos**, `ws_raw` com sentinela já substituída), cortes
    **absolutos fixos** `WATER_BAND_CUTS = (0.208, 0.415, 0.667, 1.0)` — o
    corte de topo publicado é 0,999385, arredondado para 1,0 em
    `ARCHITECTURE.md` §5.2 e usado como 1,0 aqui. Bandas
    `Low / Low-Medium / Medium-High / High / Extremely-High`. Cortes
    **left-closed** (valor exatamente no corte vai para a banda de cima).
    Não dependem de pool nem de GCM → estáveis entre rodadas.
  - **HeatRiskBand:** p25/p75/p95 de `extreme_heat_days` sobre **GFDL-ESM4**
    (`PRIMARY_GCM`, `configured_models()[0]`), pool = toda linha
    `(plant_uid, cenário)` com heat finito, 3 países × 3 cenários juntos.
    Bandas `LOW / MEDIUM / HIGH / EXTREME` (rótulos do precedente
    `ccrs_final_summary.py`). `compute_bands("miroc6")` gera o painel de
    sensibilidade com os percentis do **próprio** MIROC6 — nunca blend
    (`docs/DECISIONS.md`, entrada de bounds per-GCM). Pool de percentil inclui
    as ~123 plantas fora de bacia Aqueduct (têm heat válido) — difere levemente
    do diagnóstico `ccrs_final_summary` (que usou só o conjunto "matched").
  - **Nunca um score único** combinando as duas (spec §8.4/§8.5): saem como
    colunas separadas `water_risk_band` / `heat_risk_band`; a tabela de
    contingência `WaterRiskBand × HeatRiskBand` (`contingency_table`) é
    auxiliar. Rótulos Title-case vs UPPER são conjuntos disjuntos.
  - **Chave de identidade:** `plant_uid` em todo join/groupby/output.
  - **Capacidade:** qualquer share no relatório é sobre a base computável V6
    (`ccrs_calculator.computable_base`).
  - **Aviso literal:** `HEAT_BAND_WARNING` (HeatRiskBand não comparável entre
    rodadas com pool diferente; WaterRiskBand estável) é emitido **verbatim**
    em todo relatório (`build_summary`) e no log da CLI, não só em comentário.
- **Idioma:** módulo e teste em inglês (convenção do `src/`).
- **Arquivos:** `src/index/risk_bands.py`, `tests/test_risk_bands.py`.
- **Status:** Ativa. `EventMultiplier` e a montagem do `CCRS_i,s` numérico
  completo seguem pendentes.

## 14. CCRS `age_factor` — `src/index/age_factor.py` (spec item D fechado, final)

- **Contexto e histórico** (três entradas datadas em `docs/DECISIONS.md`, só a
  última ativa): spec §6 e `ARCHITECTURE.md` §5/§7.1/linha 147 fixam
  `age_factor ≥ 1`, crescente com a perda por idade. (1) Uma primeira
  implementação usou `age_factor = 2 - clip(retention(age), 0, 1)` ∈ `[1,2]` —
  mecanismo certo, curvas de coal/hydro/wind ainda não refinadas. (2) Uma
  sessão seguinte reverteu para `age_factor = retention(age)` ∈ `[0,1]`,
  achando (por premissa equivocada do assistente, não decisão do autor) que a
  prosa `≤ 1` do V1 revision era a convenção autoritativa. **Essa reversão foi
  o erro** — confirmado explicitamente pelo autor (opção b: "spec está
  certa"). (3) Esta entrada restaura `2 - retention` como convenção
  **definitiva** e incorpora as correções de coal/hydro/wind feitas durante a
  janela `≤ 1`.
- **Decisão:** `age_factor = 2 - clip(retention(age), 0, 1)` ∈ `[1, 2]`,
  conversão **uniforme** para todos os buckets (retenção 1,0 → af 1,0).
  `age = REFERENCE_YEAR - commissioning_year`, `REFERENCE_YEAR =
  config.YEAR_TARGET = 2050`.
  - Curvas de retenção:
    - **coal — dente de serra com overhaul assumido**, não mais função simples
      de `age`. Decaimento 0,25 pp/ano (`COAL_DECAY_RATE`; IEA/CIAB 2010,
      Kim & Moon 2012, Sagaf 2020 *J. Thermal Eng.* 6(6):247-256) dentro de um
      ciclo de `COAL_OVERHAUL_CYCLE_YEARS = 5` anos; ao completar o ciclo,
      `COAL_OVERHAUL_RECOVERY = 70%` da perda acumulada naquele ciclo é
      recuperada (30% permanente), reinicia. **O ciclo de 5 anos e os 70% de
      recuperação são premissa assumida, não valor extraído de Kim & Moon ou
      Sagaf** (essas fontes só dão a taxa de decaimento) — marcado
      provisório/estimado, revisável se surgir dado real de overhaul por
      planta. Resultado: af de coal bem mais próximo do neutro que o
      decaimento puro (planta de 40 anos: af ~1,03–1,07, vs ~1,10 sob
      `1-0,0025·age` sem recuperação).
    - **wind — `1 - 0,004·age`, uniforme, sem branch.** Aplicado a **todas**
      as usinas eólicas, sem condicional nem checagem de `CF_initial` em
      runtime. `CF_initial` não existe em nenhum arquivo GEM (confirmado nas
      1986 usinas: BR 1126 / PT 225 / IN 635) — como o branch sempre cairia no
      fallback, a métrica de "fração no fallback" deixou de fazer sentido e
      foi **removida** (`wind_cf_fallback_fraction` não existe mais). A forma
      `1 - 0,0015·age/CF_initial` (`_wind_retention_from_cf_initial`) fica no
      código como **código morto de fato** — definida, documentada, nunca
      chamada por `age_factor` nem por qualquer função no seu caminho ativo,
      verificado por inspeção de código-fonte em
      `test_wind_cf_initial_formula_exists_but_is_dead_code` (checa
      `inspect.getsource` de `age_factor`/`_wind_retention`/
      `compute_age_factors`/`_thermal_fuel_retention` e a assinatura de
      `age_factor`, que não aceita mais `cf_initial`). Fica pronta para uma
      fonte real de fator de capacidade inicial (Global Wind Atlas, dado de
      fabricante) sem mudar fórmula.
    - hydro `1 - 0,0055·age` (0,55 %/ano, ponto médio de "~0,5-0,6 %/ano" da
      §7.1; Turner et al. 2024 *Nat. Commun.*). O fator **0,79** da primeira
      entrada **não foi restaurado** — sem origem documentada.
    - solar `(1-0,007)^age` composto — inalterado nas três entradas.
    - gas/oil-gas, nuclear, bioenergy → retenção 1,0 → af 1,0 (idêntico nas
      duas convenções). **Gas/oil-gas é provisório** (nenhuma taxa na
      literatura dos docs).
  - Mixed fuel (6 plantas, todas thermal): média **simples** dos `age_factor`
    dos componentes de `fuel_types_found`.
  - `commissioning_year` ausente (602 plantas: BR 97 / PT 11 / IN 494):
    `age_factor = 1,0`, linha **mantida**, sinalizada
    (`age_factor_neutralized_missing_year`), contada por país. Concentração da
    Índia (9,7%, wind 258 + solar 172, zero hydro) documentada em
    `06-areas-de-risco.md`.
  - Aplicação inalterada: multiplica cada coluna de Hazard de
    `ccrs_hazard.csv` por `plant_uid`. Multiplicativo, nunca soma. Guarda
    fail-loud se algum `plant_uid` do CSV não tiver `age_factor` (CSV
    desatualizado). Saídas: `ccrs_age_factors.csv`, `ccrs_hazard_aged.csv`,
    `age_factor_report.md`.
- **`load_plants` estendido:** retorna também `fuel_type`, `mixed_fuel_type`,
  `fuel_types_found` (necessário p/ o `fuel_type` dentro do bucket `thermal`).
  Colunas aditivas, sem impacto em `compute_hazard`/`risk_bands`.
- **Distribuição observada (2050), convenção final `[1,2]`:** af global
  **1,0000–1,7480**. hydro tem os maiores (BR mean 1,32, max 1,75 — plantas de
  ~1900); solar ~1,17–1,19; wind ~1,08–1,17; coal agora bem mais próximo do
  neutro que a primeira entrada (~1,03–1,07 em todos os países, por causa da
  recuperação de overhaul assumida). Neutros (gas/nuclear/bioenergy) = 1,0.
- **Item D da spec — fechado, sem bloco OPEN.** `age_factor ≥ 1` é a
  convenção correta e definitiva (confirmado pelo autor). Nada pendente de
  reconciliação de prosa.
- **Idioma:** módulo e teste em inglês.
- **Arquivos:** `src/index/age_factor.py`, `tests/test_age_factor.py`,
  `src/index/ccrs_calculator.py` (`load_plants`).
- **Status:** Ativa. Gas/oil-gas provisório (open). Coal: ciclo de overhaul de
  5 anos / recuperação de 70% é parâmetro assumido e revisável (não é "open"
  no sentido de bloquear item D — é estimativa documentada). `EventMultiplier`
  e a montagem do `CCRS_i,s` completo seguem pendentes.

## 15. CCRS `EventMultiplier_c` — `src/index/event_multiplier.py` (spec item C, sem divergência)

- **Contexto:** spec §7 e `ARCHITECTURE.md` §7.2 dão a mesma fórmula, a mesma
  base de `N_events` (239/38/622) e a mesma aplicação a nível de país — sem
  divergência (checado antes de codar, item 0 da tarefa). Item C da spec já
  estava "Set"; esta é a implementação.
- **Decisão:** `EventMultiplier_c = 1 + EVENT_MULTIPLIER_K·(rate_c/rate_max)`,
  `EVENT_MULTIPLIER_K = 0,5` (parâmetro de julgamento, não re-derivado — item
  J de Monte Carlo, ainda não implementado). `rate_c = N_events(c) /
  EMDAT_ARCHIVE_SPAN_YEARS`, `EMDAT_ARCHIVE_SPAN_YEARS = 124` (1900–2024, span
  do EM-DAT Archive; cancela exatamente na razão `rate_c/rate_max`, mantido só
  por fidelidade aos documentos-fonte e legibilidade). `rate_max` = maior
  `rate_c` entre os países passados (Índia, hoje).
- **`N_events(c)` — sem normalização inventada.** É a contagem de linhas de
  `data/raw/validation/emdat_{país}.csv` (`emdat_downloader.country_csv_path`)
  — o arquivo **já** está filtrado por ISO do país e pelos 4 tipos de desastre
  climáticos (`emdat_downloader.DISASTER_TYPES`), então já É a "contagem
  elegível filtrada por tipo" que spec/ARCHITECTURE citam. Nenhum filtro,
  peso, ou normalização por capacidade/nº de plantas adicional. Confirmado
  contra os dados: 239 (BR) / 38 (PT) / 622 (IN) linhas — batendo exatamente
  com os dois documentos-fonte.
- **Aplicação — join por `country`, multiplicativo, nunca somado.**
  `EventMultiplier_c` é geocodificado só a nível de país (V2 fechado) — todo
  `plant_uid` de um país recebe o mesmo valor. `apply_to_hazard` faz o join em
  `country` (nunca em `plant_uid`), `merge(..., validate="many_to_one")` +
  checagem explícita de contagem de linha (levanta se o join mudar o total —
  guarda contra fan-out por país duplicado na tabela de multiplicadores, ou
  drop por país ausente). Multiplica cada coluna de Hazard
  (`{col}_x_event`), mesmo padrão de `age_factor.apply_to_hazard`
  (`{col}_aged`) — nunca soma.
- **Regressão (fixture antiga BR 1,192 / PT 1,031 / IN 1,500):** recalculado
  BR 1,192122 / PT 1,030547 / IN 1,500000 — diffs 0,000122 / 0,000453 / 0 —
  todas ≤ 0,01 → **aceitas**, fixture do teste usa os valores de precisão
  plena.
- **Não monta o `CCRS_i,s` completo** — só prova/testa o passo de join+
  multiplicação do `EventMultiplier` isoladamente, como `age_factor.py` faz
  para o age factor. A montagem final (produto dos três fatores numa coluna)
  segue como módulo separado, ainda não escrito.
- **Idioma:** módulo e teste em inglês.
- **Arquivos:** `src/index/event_multiplier.py`, `tests/test_event_multiplier.py`.
- **Status:** Ativa. `k = 0,5` é o único parâmetro em aberto para a
  sensibilidade Monte Carlo do item J (spec), não para re-derivação.

## 16. CCRS montagem final — `src/index/ccrs_report.py` (T1×T2×T3, relatório de banda)

- **Contexto:** primeiro módulo a juntar Hazard (T1), age_factor (T2) e
  EventMultiplier (T3) numa coluna só, mais o relatório de % capacidade por
  banda (T4). Checado antes de codar: fórmula de montagem (spec §2 vs
  ARCHITECTURE §5.1), base de capacidade (spec §8.5 vs ARCHITECTURE §5.5) e
  regra de GCM primário/sensibilidade (spec §8.6 vs ARCHITECTURE §5.4) — **sem
  divergência** nos três pontos.
- **Decisão:** `compute_ccrs()` = `CCRS_i,s = Hazard_i,s * age_factor_i *
  EventMultiplier_country(i)`, produto só (nunca soma), por
  `(plant_uid, water_scenario)`, uma coluna `ccrs_{gcm}` por GCM configurado
  (`ccrs_gfdl_esm4`, `ccrs_miroc6`, nunca combinadas). `age_factor` junta por
  `plant_uid` (T2, um valor por planta); `EventMultiplier` junta por
  `country` (T3, um valor por país); os dois `merge(..., validate=
  "many_to_one")` + guarda explícita de contagem de linha — nem duplicam nem
  derrubam `plant_uid`. `attach_risk_bands()` junta `water_risk_band` (só do
  `BandTable` do GCM primário — não depende de GCM, T4) e
  `heat_risk_band_{gcm}` (um por GCM) por `(plant_uid, water_scenario)`,
  `validate="one_to_one"`.
- **Capacidade — assert explícito, fail-loud.** `capacity_sum(df)` levanta
  `AssertionError` (nunca loga e segue) se algum registro de `df` não tiver
  `commissioning_year` — i.e. exige que `df` já seja a base computável V6
  (`ccrs_calculator.computable_base`). Toda soma de capacidade do módulo
  passa por essa função; nunca soma `capacity_mw` direto do fleet bruto.
- **`band_capacity_shares(frame, band_col, bands, group_cols)`** — % de
  capacidade (base V6) por banda, agrupado por `group_cols`. Linhas sem banda
  (planta fora de bacia Aqueduct ou de célula de raster de calor) entram como
  linha `NO_BAND`, então `capacity_share` soma exatamente 1,0 em todo grupo.
  WaterRiskBand: agrupado por `(country, water_scenario)` — **sem** eixo de
  GCM, porque a banda é GCM-independente (T4); reportar "por GCM" duplicaria
  o mesmo número. HeatRiskBand: agrupado por
  `(country, heat_scenario, gcm)` — GFDL-ESM4 linhas ao lado de MIROC6, nunca
  misturadas (ARCHITECTURE §5.4).
- **Contingência WaterRiskBand×HeatRiskBand reaproveitada de T4** —
  `risk_bands.contingency_table()` chamada diretamente, uma vez por GCM
  (primário + painel de sensibilidade); não reimplementada. Verificado por
  inspeção de `inspect.getsource(build_summary)`.
- **Relatório carrega as ressalvas de dado de T2/T4, não só em docs/memory:**
  `risk_bands.HEAT_BAND_WARNING` verbatim; nota do fallback uniforme de wind
  (0,4%/ano, `CF_initial` inexistente em qualquer arquivo GEM, forma
  `_wind_retention_from_cf_initial` código morto); tabela de fração de
  `commissioning_year` ausente por país (Índia ~9,7%, maior que BR ~1,8%/PT
  ~2,4%).
- **Rodada real (2050):** `ccrs_final.csv` — 32.424 linhas, 10.808 `plant_uid`
  únicos × 3 `water_scenario`, batendo exatamente com o esperado (T1). CCRS
  score: `ccrs_gfdl_esm4` p50 0,26 / p95 1,57 / max 1,82; `ccrs_miroc6` p50
  1,03 / p95 1,73 / max 1,85.
- **Idioma:** módulo e teste em inglês.
- **Arquivos:** `src/index/ccrs_report.py`, `tests/test_ccrs_report.py`.
- **Status:** Ativa. Depende de T1–T4, todos commitados. Falta só o wrapper
  de Monte Carlo (item J da spec) para a camada de índice estar completa.

## 17. `analysis/ccrs_final_summary.py` × `src/index/risk_bands.py` nunca batem exatamente — pool do corte de percentil do HeatRiskBand difere

- **Contexto:** T6 (`tests/test_ccrs_integration.py`) comparou a fração
  composta de capacidade da Índia (`WaterRiskBand ∈ {High, Extremely-High}`
  E `HeatRiskBand ∈ {HIGH, EXTREME}`, GFDL-ESM4) entre o diagnóstico antigo
  (`analysis/ccrs_final_summary.py`, 39,2%) e a implementação de produção
  (`src/index/risk_bands.py`, T4). Mesmos dados (rasters/CSVs inalterados
  desde 2026-09-03), resíduo de **~0,05pp** (39,2551% vs 39,2000%,
  denominador "matched") — pequeno, mas não zero.
- **Decisão/achado:** os dois **nunca produzirão exatamente o mesmo número**,
  mesmo sobre dados idênticos, porque o **pool usado para os cortes de
  percentil do HeatRiskBand (p25/p75/p95) é diferente**:
  - `analysis/ccrs_final_summary.py` (via
    `water_risk_band_classification.water_band_frame`): calcula os cortes
    só sobre o pool **"matched"** — linhas onde `ws`, `sv`, `iv` **e** `heat`
    são todos finitos simultaneamente (a mesma planta precisa estar dentro
    de uma bacia Aqueduct **e** dentro de uma célula de raster de calor).
  - `src/index/risk_bands.py` (`compute_bands` → `heat_percentile_cuts`):
    calcula os cortes sobre **todo registro com `heat` finito**,
    independente de `ws`/`sv`/`iv` — inclui as ~54 linhas indianas de
    plantas fora de qualquer bacia Aqueduct mas dentro do raster de calor
    (`WaterRiskBand` fica `None` para essas linhas, mas `HeatRiskBand`
    ainda é atribuído).
  - Isso desloca o corte p75 de `31,1667` (antigo) para `31,0` dias/ano
    (produção) na Índia/GFDL-ESM4 — pequeno o bastante para mover só a
    fração composta, não a ordem de grandeza do resultado.
- **Por que a implementação de produção está certa e não vai mudar:**
  `risk_bands.py` classifica o HeatRiskBand independentemente do
  WaterRiskBand por desenho (bandas são colunas separadas, nunca
  co-dependentes — spec §8.3/T4) — restringir o pool de percentil do calor
  ao subconjunto casado com água misturaria as duas dimensões na hora de
  definir os cortes, o que a arquitetura do CCRS evita deliberadamente. O
  diagnóstico antigo é anterior a essa separação explícita e usa um pool
  mais restrito só porque reaproveitou o frame "matched" que já tinha à mão.
- **Consequências:** o resíduo esperado entre os dois é **~0,05pp**, bem
  dentro da tolerância de **±0,5pp** adotada em T6
  (`tests/test_ccrs_integration.py::test_hazard_band_compound_share_for_india_vs_old_diagnostic_value`).
  Não é o bug de cross-join de T1 (o diagnóstico antigo nunca usa `.merge()`,
  ver a mesma suíte) nem *drift* de dado (dados inalterados desde
  2026-09-03) — é diferença de metodologia, documentada e aceita.
- **Arquivos:** `analysis/ccrs_final_summary.py`,
  `analysis/water_risk_band_classification.py`, `src/index/risk_bands.py`,
  `tests/test_ccrs_integration.py`.
- **Status:** Ativa. Não é um TODO — o diagnóstico antigo não será alterado
  (é histórico/congelado) nem `risk_bands.py` (o pool amplo é o desenho
  correto); o resíduo é permanente e esperado.

---

## 18. CCRS termo de seca (SPEI) integrado ao Hazard — `src/index/ccrs_calculator.py` (spec item F fechado)

- **Contexto:** `src/processors/spei_processor.py` (Step 1, já commitado)
  produzia a camada de seca (SPEI-12, Thornthwaite PET) sem estar ligada ao
  Hazard. Este item fecha o item F: o termo entra na fórmula.
- **Decisão:** `Hazard_i,s` ganha um terceiro termo aditivo independente,
  `w_drought[bucket] * Tlog(spei_freq)`, ao lado de `water_sub` e
  `Tlog(heat)` — não um complemento renormalizado dentro de `water_sub`
  (que é uma quantidade derivada e fechada, spec §8.1, nunca tocada). Ver
  a decisão completa (motivo, pesos por bucket, extensão de
  `FROZEN_BOUNDS`, impacto de comparabilidade) em `docs/DECISIONS.md`,
  entrada "[2026-09-04] SPEI drought term added to Hazard".
- **Impacto de engenharia:** `HAZARD_TERMS`, `LOG_TERMS` ganham `"spei"`;
  novo `GCM_DEPENDENT_TERMS = {"heat", "spei"}` e `FLAT_BOUND_TERMS = {"ws",
  "sv", "iv"}` generalizam `_term_bounds`/`compute_global_bounds`/
  `_bounds_close` (antes hardcoded para "heat" vs. o resto). `hazard()`
  passa a receber `t_spei` como quarto argumento posicional — toda chamada
  existente (`compute_hazard`, testes) foi atualizada. `BUCKET_WEIGHTS` vai
  de `{"water", "heat"}` para `{"water", "heat", "drought"}` por bucket.
- **Pré-requisito rodado nesta tarefa:** os rasters brutos de seca não
  existiam em `data/processed/climate/` antes desta integração (as séries
  diárias `pr`/`tas` já estavam baixadas). Rodado
  `python -m src.processors.spei_processor` para as 3 países × 2 GCMs × 3
  cenários (18 rasters, ~75s) antes de calcular `FROZEN_BOUNDS["spei"]` e
  rodar os testes end-to-end.
- **Arquivos:** `src/index/ccrs_calculator.py`, `tests/test_ccrs_calculator.py`
  (31 testes, incl. `test_water_sub_weights_and_output_unchanged_by_spei_integration`,
  `test_end_to_end_hazard_with_spei_produces_32424_rows_no_duplication`,
  `test_real_gcm_columns_never_blended_with_three_terms`).
- **Status:** Ativa. Spec item F fechado. Suíte completa: 242 testes
  passando (~2m43s).

---

## 19. CCRS Monte Carlo sensitivity — `src/index/monte_carlo.py` (spec item J, escopo aprovado)

- **Contexto:** item J (perturbação Monte Carlo dos parâmetros de
  julgamento do CCRS) implementado sob escopo explicitamente aprovado por
  Douglas: N=1000 iterações × 3 magnitudes (±10/20/30%), 3 parâmetros
  perturbados (razão água/calor do bucket thermal, taxas de retenção de
  `age_factor` para coal/wind/hydro, amplitude `k` do `EventMultiplier`),
  `FROZEN_BOUNDS` e cortes de `risk_bands.py` explicitamente fora de
  escopo.
- **Decisão de engenharia — pré-computação fora do loop:** os termos
  transformados por raster (`water_sub`, `T_heat`, `T_spei`, via
  `ccrs_calculator.compute_hazard`, bounds congelados não perturbados) são
  calculados **uma vez**, não a cada iteração — refazer a leitura de raster
  3000× seria inviável. Cada sorteio recomputa só o que depende dos
  parâmetros perturbados: `age_factor` por planta (versão vetorizada em
  `numpy`, testada contra `age_factor.compute_age_factors()` nas taxas
  centrais), os pesos do bucket thermal, `EventMultiplier_c`, e o produto
  final `CCRS = Hazard × age_factor × EventMultiplier`. Simulação completa
  (N=1000 × 3 magnitudes × 3 países, 2 GCMs): **~2m44s** (46s de
  pré-computação + 116s de cômputo) — viável, sem necessidade de reduzir N.
- **Duas leituras de escopo não cobertas pelo brief original (que antecede
  a integração do SPEI) — sinalizadas explicitamente no docstring do
  módulo, não decididas silenciosamente:**
  - Perturbação do bucket thermal: razão água:calor perturbada e
    renormalizada para preencher `1 - w_drought`, com `w_drought` fixo em
    0.30 (não nomeado no escopo aprovado, que é 2-way e pré-SPEI).
  - RNG independente **por país apenas**, não por país×cenário: nenhum dos
    3 parâmetros aprovados depende de cenário, e a produção aplica um
    `EventMultiplier_c` idêntico nas 3 linhas de cenário do país — um
    stream por cenário injetaria ruído não-físico numa quantidade
    invariante por cenário.
- **Dois bugs encontrados e corrigidos durante a implementação:**
  1. Plantas thermal fora de qualquer bacia Aqueduct (`water_sub` NaN,
     comportamento esperado de `ccrs_calculator.hazard()`) contaminavam o
     `np.bincount` do grupo inteiro (país×cenário×banda) em vez de só
     serem excluídas da média daquele sorteio — `np.bincount` não ignora
     NaN como `pandas.Series.sum()` ignora. Corrigido com
     `_weighted_group_mean`, que filtra linhas NaN antes do bincount.
  2. `None` de `risk_bands._bandize` virava `float('nan')` silenciosamente
     no `.merge()` para anexar as bandas — `nan != None` avalia `True`,
     então o filtro `!= None` deixava passar linhas sem banda. Corrigido
     com `pd.notna()`.
- **Garantia de dado atual:** roda sobre o CCRS pós-integração SPEI —
  recomputado inteiramente em memória via `ccrs_calculator`/`risk_bands`
  (nunca lê `data/outputs/tables/*.csv`, que na época da implementação
  ainda estavam desatualizados/pré-SPEI).
- **Arquivos:** `src/index/monte_carlo.py`, `tests/test_monte_carlo.py`
  (14 testes).
- **Status:** Ativa, aguardando confirmação de Douglas sobre os dois
  pontos de leitura de escopo acima (thermal drought fixo; RNG por país
  vs. país×cenário).

---

## 20. CCRS módulo de visualização — `src/visualization/` (11 categorias, teto de 10 conscientemente estourado)

- **Contexto:** implementação do módulo de figuras do CCRS para o artigo,
  reaproveitando a infraestrutura genérica de
  `energy_risk_assessment/src/visualization/maps.py` (repo antigo):
  tratamento de território disputado (Índia, GIDs `Z`-prefixados),
  figsize dinâmico por bbox real do país, convenção de marcador
  `sqrt(capacity/capacity.max())`, `dpi=200`/PNG+PDF.
- **Decisão registrada — teto de 10 categorias conscientemente estourado
  para 11, por decisão de Douglas:** a investigação inicial (Comando 5,
  antes da integração do SPEI) propôs até 10 categorias de figura mais um
  "bônus" citado como "fora da lista de 10, mas vale reter" — o heatmap
  Top-N CCRS breakdown (linhas = Top-N plantas por `ccrs_gfdl_esm4`,
  colunas = os três fatores multiplicativos: Hazard, `age_factor`,
  `EventMultiplier`). Ao aprovar o escopo desta implementação, Douglas
  incluiu esse item explicitamente na lista de categorias aprovadas
  (item 11), não como sugestão a avaliar depois. **Isto não é desvio de
  escopo** — é a lista efetivamente aprovada; registrado aqui para que uma
  sessão futura não leia "11 categorias" como um excesso não autorizado
  contra um teto de 10 que já não se aplica.
- **Fonte de dado — nunca CSV cacheado:** todo o módulo (`data.py`)
  recomputa em memória via `ccrs_calculator`/`age_factor`/
  `event_multiplier`/`risk_bands`, nunca lê `data/outputs/tables/*.csv`
  (mesmo padrão já adotado em `monte_carlo.py`, pelo mesmo motivo: esses
  CSVs podem estar desatualizados em relação à metodologia corrente, ex.
  pré-integração do SPEI). `ccrs_report.compute_ccrs()` especificamente
  **não é chamado** — seu parâmetro `hazard_csv` lê do disco por padrão.
  **[2026-09-04, correção de duplicação]** a primeira versão deste módulo
  reimplementava a lógica de join/multiplicação
  (`Hazard × age_factor × EventMultiplier`) numa função local
  `data.assemble_ccrs()`, duplicando o que já existia em
  `ccrs_report.compute_ccrs()` — risco real de divergência silenciosa entre
  as duas se uma fosse alterada e a outra não. Corrigido extraindo o núcleo
  de montagem (sem I/O) para `ccrs_report.assemble_ccrs()`;
  `ccrs_report.compute_ccrs()` passou a ser só leitura de CSV + chamada a
  essa função core, e `data.py` importa e chama a MESMA função
  (`from src.index.ccrs_report import assemble_ccrs`) em vez de manter uma
  cópia local. Identidade de objeto travada por teste
  (`tests/test_ccrs_report.py::test_visualization_module_calls_the_same_assemble_ccrs_object`)
  — não são duas implementações que coincidem em resultado, é uma função
  com dois chamadores.
  `risk_bands.compute_bands`, `ccrs_report.attach_risk_bands`,
  `compute_water_band_shares`/`compute_heat_band_shares` são reaproveitados
  diretamente (não leem CSV, recomputam ou recebem frame em memória).
- **Paleta:** `RdBu_r` mantido para o único mapa divergente (delta de
  cenário, item 2) — já apropriado (zero-centrado). Toda paleta sequencial/
  ordinal do repo antigo (`YlOrRd`/`PuBu`/`YlGnBu`) trocada por **viridis**
  (perceptualmente uniforme) — aplicada às bandas de risco ordinais (itens
  3/4/8) e às duas matrizes anotadas (itens 5/11). Paleta categórica de
  bucket (`BUCKET_COLORS`, 4 cores — hydro/thermal/wind/solar, sem `coal`
  separado como no schema antigo de 5 buckets) mantida como paleta
  qualitativa fixa, não sequencial (dado nominal, não ordinal).
- **Nova dependência:** `matplotlib>=3.7.0` adicionado a `requirements.txt`
  (ausente até esta tarefa — camada de visualização não existia antes).
  Instalada versão 3.11.1; `matplotlib.cm.get_cmap` foi removido nessa
  versão, usado `matplotlib.colormaps[name]` (API atual) em
  `_common._ordinal_band_colors`.
- **Estrutura:** `src/visualization/_common.py` (infraestrutura genérica
  reaproveitada), `data.py` (camada de dado em memória), `maps.py`
  (categorias 1/2/3/4/10, geoespaciais), `charts.py` (categorias
  5/6/7/8/9/11). Categorias "Both" (per-country + combined) expostas como
  UMA função com flag `combined: bool` (não um par de funções separadas
  como no repo antigo) — mesma forma de saída (`dict[str, Path]`), menos
  duplicação de código.
- **Arquivos:** `src/visualization/{__init__,_common,data,maps,charts}.py`,
  `tests/test_visualization.py` (17 testes).
- **Status:** Ativa.

## 21. Revisão do módulo de visualização (2026-09-04, rodada de review de Douglas)

- **Contexto:** após a implementação inicial (item 20), Douglas revisou as 11
  figuras geradas e pediu uma rodada de correções/extensões em três blocos:
  Parte A (estilo, aplica a todas as figuras), Parte B (correções pontuais
  por categoria existente), Parte C (novas figuras/tabelas). Todo o módulo
  continua consumindo `src/index/*` em memória, nunca CSV cacheado (regra
  inalterada do item 20).
- **Decisão — Parte A (estilo global):**
  - PDFs isolados: `_common.save_figure` grava o PDF em `<pasta>/pdf/<nome>.pdf`
    em vez de ao lado do PNG (`_common.pdf_path_for`).
  - Nenhuma figura imprime título (`fig.suptitle` removido de todo o
    módulo); o contexto que estava no título virou rodapé
    (`_common.figure_caption_footer(_single)`), sem duplicar a legenda GADM.
    Rótulo por painel (ex. "Brazil (n=...)") foi mantido — é rótulo de
    painel, não título de figura — mas em negrito e com texto
    "Power Plants=N" em vez de "n=N" (`_common.panel_title`).
  - Fontes +20%: `_common.FONT_SCALE = 1.2`, helper `_common.fs(base)` para
    todo `fontsize` explícito, e `plt.rcParams` elevado para os tamanhos
    default (eixo/tick/legenda) que não passam `fontsize` explicitamente.
  - Aproveitamento de espaço: categorias 1/3/10 passaram a usar grade
    país×cenário (ver abaixo) com `constrained_layout=True` e altura de
    linha proporcional ao aspect ratio real do país
    (`maps._combined_grid_figsize`), o mesmo princípio de
    `ccrs_overview_gfdl_esm4_bau` generalizado, corrigindo o espaço em
    branco excessivo do HeatRiskBand antigo.
- **Decisão — B1 (HeatRiskBand, categoria 4):** reescrito para uma figura
  por cenário de calor (chamar `plot_heat_risk_band_map` uma vez por
  `water_scenario`), GFDL-ESM4 apenas, 3 países lado a lado — a antiga
  segunda linha MIROC6 (só ssp370) foi removida. **A comparação GFDL vs.
  MIROC6 foi mantida, como tabela, não descartada**: decisão reportada e
  aceita — `tables.heat_band_gcm_comparison_table` (uma linha por país:
  share de capacidade em HIGH/EXTREME por GCM + diferença), porque a
  pergunta que o segundo painel respondia ("o GCM de sensibilidade diverge
  o bastante do primário para importar") é melhor respondida por um número
  direto do que por comparação visual de dois mapas.
- **Decisão — B2 (categorias 1/3/10):** geradas para os 3 cenários de água
  numa grade único por figura — `combined=True` vira grade países (linha) x
  cenários (coluna); `combined=False` vira 1 país x 3 cenários lado a lado.
  Implementado em `maps._render_scenario_bubble_figure` (categorias 1 e 10,
  reaproveitando `_draw_bubble_panel`) e replicado inline em
  `plot_water_risk_band_map` (categoria 3, `_draw_band_panel`).
- **Decisão — B3 (contingência WaterRiskBand×HeatRiskBand, categoria 5):**
  heatmap substituído por barras empilhadas por país (`charts.
  plot_water_heat_combined_risk_bars`), mesma linguagem visual de
  `capacity_by_risk_band`. As 5×4=20 combinações de banda foram colapsadas
  numa severidade combinada de 4 níveis (`charts._combined_risk_level` —
  rank normalizado máximo entre WaterRiskBand e HeatRiskBand, reagrupado nos
  mesmos 4 rótulos de HeatRiskBand) — simplificação explícita, reportada,
  necessária para não exigir uma legenda de 20 cores ilegível. Tabela
  complementar com os números completos (não colapsados) em
  `tables.water_heat_contingency_capacity_table`.
- **Decisão — B4 (Top-N breakdown, categoria 11):** reescrito de heatmap
  único para pequeno múltiplo com um painel de barras horizontais POR
  bucket (`charts.plot_top_n_ccrs_breakdown_by_bucket`) — nunca mistura
  hydro/thermal/wind/solar no mesmo ranking. Escolha de gráfico justificada
  na docstring da função: nomes de planta são texto longo (barra horizontal
  lê sem rotação, o que um heatmap não escala além de ~15 linhas), e um
  painel por bucket evita competir cor-de-bucket com cor-de-score na mesma
  matriz.
- **Decisão — B5 (figuras "fracas"):** `age_factor_by_bucket`,
  `capacity_by_risk_band` e `ccrs_distribution_by_bucket` MANTIDAS (carregam
  conteúdo metodológico/de resultado real) mas realocadas para
  `combined/secondary/` (`charts.SECONDARY_DIR`);
  `ccrs_distribution_by_bucket` passou a ser gerável para os 3 cenários
  (antes só bau). `plot_event_multiplier_by_country` (categoria 9) foi
  **removida do código**, não apenas realocada — 3 números por país são
  mais bem lidos numa tabela do que num gráfico de 3 barras com duas linhas
  de anotação por barra; substituída por `tables.event_multiplier_table`
  (mesmos números).
- **Decisão — C1/C2 (CCRS nacional agregado com IC):** nova função
  `monte_carlo.run_country_scenario_simulation` (agrupamento só por país x
  cenário, sem banda — reaproveita `compute_draw_ccrs`/
  `_weighted_group_mean` já testados, não é um novo mecanismo de
  perturbação) alimenta `charts.plot_national_ccrs_with_ci` (pontos + barra
  de erro IC 2.5/50/97.5%, GFDL-ESM4 primário) e
  `tables.national_ccrs_summary_table` (mesmos números + ranking).
  **Decisão sobre MIROC6, reportada:** entra no MESMO painel como marcador
  secundário (losango, mais claro, levemente deslocado), não como painel
  separado — resultado central compacto, ao contrário do mapa de
  HeatRiskBand (item B1) que é inerentemente espacial. As 3 magnitudes de
  perturbação aprovadas (±10/20/30%) são agrupadas (pooled) numa única
  distribuição empírica por grupo para esta figura "manchete" — decisão
  explícita para não exigir que o leitor escolha uma magnitude; o detalhe
  por magnitude não se perde, fica na tabela C5.
- **Decisão — C3 (tabela de pesos com proveniência):**
  `tables.hazard_weight_provenance_table` consolida os pesos internos de
  `water_sub` (ws/sv/iv, 0.4164/0.2505/0.3331 — fechado, derivado das
  larguras de categoria do WRI Aqueduct 4.0) e os pesos por bucket
  (water/heat/drought) com a proveniência exatamente como documentada em
  `docs/DECISIONS.md` ("SPEI drought term added to Hazard", 2026-09-04):
  julgamento qualitativo explícito de Douglas, não calibração. Nenhuma
  proveniência foi inventada.
- **Decisão — C4 (contribuição relativa dos termos de Hazard):** nova
  `tables.hazard_term_contribution_table` (participação capacity-weighted
  de water_sub/heat/drought no Hazard final, por país x cenário, a partir de
  `ccrs_calculator.compute_hazard`) + `charts.plot_hazard_term_contribution`
  (barras empilhadas).
- **Decisão — C5 (tabelas do Monte Carlo):** `tables.
  monte_carlo_parameter_summary_table` — país x cenário x magnitude de
  perturbação, ponto + IC — chama `run_country_scenario_simulation` uma vez
  por magnitude (não pooled, ao contrário de C1) para preservar a dimensão
  de magnitude como tabela em vez de colapsá-la.
- **Decisão — C6 (validação espacial EM-DAT), NÃO implementada:**
  investigação de viabilidade feita e reportada antes de qualquer código
  (`tables.C6_INVESTIGATION_NOTE`), conforme exigido. Achado, a partir de
  `data/outputs/inspection/emdat_coverage.csv`: cobertura de Latitude/
  Longitude pontual é 5.3-12.1% dos eventos (Portugal só 2 eventos) —
  insuficiente para sobreposição pontual; cobertura de `GADM Admin Units`
  (nível admin-1, poligonal) é 50.3-52.6% em todos os 3 países — suficiente
  para uma sobreposição poligonal, não pontual. Desenho proposto (não
  codado): atribuir cada evento geocodificado ao(s) polígono(s) admin-1 via
  `GADM Admin Units`, agregar o termo de Hazard relevante por tipo de
  desastre dentro desse polígono, comparar via teste de Mann-Whitney U
  (não paramétrico, N pequeno por país) entre polígonos com e sem evento
  registrado, mostrado como box/strip plot com estatística e p-valor
  anotados — nunca um score único combinado. Ressalvas registradas: ~50% de
  não-cobertura não é amostra aleatória (eventos mais documentados/urbanos
  provavelmente sobrerrepresentados), N=38 de Portugal limita qualquer corte
  por tipo de desastre, formato exato de `GADM Admin Units` (pode cobrir
  múltiplos polígonos/níveis) não verificado, e associação não implica
  causação com 3 países e múltiplos tipos de desastre comparados. Aguardando
  aprovação de Douglas antes de qualquer implementação.
- **Arquivos:** `src/visualization/_common.py`, `maps.py`, `charts.py`
  (reescritos), `src/visualization/tables.py` (novo),
  `src/index/monte_carlo.py` (nova função
  `run_country_scenario_simulation`), `tests/test_visualization.py`
  (reescrito, 35 testes).
- **Status:** Ativa. C6 permanece em aberto (exploratório, aguardando
  decisão de Douglas).

## 22. C6 — validação espacial EM-DAT × Hazard, implementada (2026-09-04)

- **Contexto:** após o achado de viabilidade do item 21 (cobertura GADM
  Admin Units ~50-53%, Lat/Lon pontual 5,3-12,1%), Douglas aprovou o desenho
  proposto e pediu a implementação: agregação de eventos por polígono
  admin-1, comparação do termo de Hazard correspondente via Mann-Whitney U,
  output como box/strip plot com p-valor anotado, nunca um score combinado
  único, e as limitações de cobertura na própria figura, não só no código.
- **Decisão — arquitetura:** camada de dado/estatística em
  `src/index/emdat_validation.py` (não depende de `src/visualization/` —
  reimplementa um loader mínimo de fronteiras admin-1 em vez de importar
  `_common.load_admin1_boundaries`, preservando a direção de dependência
  index → visualization já usada no resto do projeto); camada de figura em
  `src/visualization/emdat_validation.py`. Este módulo é diagnóstico —
  **não** realimenta `Hazard`/`CCRS`.
- **Decisão — mapeamento tipo de desastre → termo de Hazard** (proxy
  disponível, não um match físico perfeito, reportado como ressalva):
  `Extreme temperature → heat`, `Drought → spei`, `Flood → ws` (estresse
  hídrico — escassez, não excesso de água; é o único termo do lado água
  disponível no sistema). `Storm` **excluído**: não existe termo de
  vento/tempestade no CCRS para comparar.
- **Achado não antecipado no relatório de viabilidade:** o campo `GADM
  Admin Units` mistura granularidade por evento — alguns dão GID admin-1
  diretamente (`"gid_1":"BRA.5_1"`), a maioria dá admin-2/município
  (`"gid_2":"BRA.19.68_2"`), alguns só admin-0/país (descartado, grosso
  demais). `emdat_validation._resolve_admin1_gid` trunca qualquer nível
  ≥ 1 para o pai admin-1 (dois primeiros segmentos separados por ponto),
  para que todo evento caia na mesma grade admin-1 que a camada de
  fronteiras da CCRS usa (`GID_1` do `ADM_ADM_1`).
- **Método:** por (país, tipo de desastre) — Storm excluído — média zonal
  (`rasterio.mask`, nodata-safe) do raster bruto do termo mapeado, GFDL-ESM4
  + `water_scenario="bau"` (um campo de referência único; é um diagnóstico,
  não um resultado por cenário), por polígono admin-1; grupo "com evento
  geocodificado" vs. "sem"; teste de Mann-Whitney U bilateral. Um par é
  **pulado, nunca descartado silenciosamente** (`skip_reason` preenchido)
  se algum grupo tiver menos de `MIN_GROUP_SIZE=3` polígonos com valor
  finito.
- **Achado nos dados reais** (`python -m src.index.emdat_validation`,
  9 pares país×tipo testáveis, 2 pulados): Índia mostra associação
  significativa nos 3 tipos — heat p=5,4e-7, flood p=3,3e-3, drought
  p=0,026 (polígonos com evento têm Hazard mediano muito mais alto). Brasil
  não mostra associação significativa em nenhum dos 3 (p entre 0,31 e
  0,98). Portugal: Flood não significativo (p=0,33); **Extreme temperature
  e Drought foram pulados** — Portugal tem evento geocodificado em 18 dos
  18 polígonos admin-1 usados nesses dois tipos (cobertura quase universal,
  não antecipada no relatório de viabilidade), deixando zero polígonos no
  grupo "sem evento" para comparar. Isso não invalida o método — é um
  resultado informativo por si (o país é pequeno o bastante para que quase
  toda unidade admin-1 tenha histórico de algum evento de calor/seca em
  124 anos) e o `skip_reason` reporta exatamente isso.
- **Nova dependência:** `scipy>=1.11.0` (`scipy.stats.mannwhitneyu`),
  primeiro uso desta biblioteca no projeto — adicionada a
  `requirements.txt` conforme já sinalizado no `CLAUDE.md`/item 1 deste
  arquivo ("scipy ... adicionadas quando essa camada for escrita").
- **Ressalvas mantidas na própria figura** (não só no código, conforme
  pedido): rodapé de `plot_emdat_spatial_validation` repete a cobertura
  geocodificada (~50-53%), o caráter de proxy do termo `ws` para Flood, a
  exclusão de Storm, e lista os pares pulados com o motivo.
- **Arquivos:** `src/index/emdat_validation.py` (novo),
  `src/visualization/emdat_validation.py` (novo), `requirements.txt`
  (`scipy`), `src/visualization/tables.py` (`C6_INVESTIGATION_NOTE`
  recebeu um addendum apontando para esta implementação),
  `tests/test_visualization.py` (7 novos testes: parsing de GID misto,
  exclusão de Storm, decisão de pular/testar, figura com resultado
  sintético, ressalvas no rodapé da figura).
- **Status:** Ativa. Resultado é diagnóstico/exploratório — não altera
  `Hazard`/`CCRS`; aguardando decisão de Douglas sobre uso no artigo.

## 23. Numeração de figuras do artigo (Fig 1–7) — rodada 2026-09-05

> Entre o item 22 e esta entrada houve várias rodadas de redesenho de figura
> commitadas mas não documentadas aqui (commits `4579fa7` Fig 1, `3ee85cc`
> worst-case, `936c71e` reference CCRS, `1b0d66c` split Fig 3, `c0b72c0` rank
> stability, `356664b` hazard-term distribution, `17373b2` grid EM-DAT). Esta
> entrada cobre só a rodada de **numeração final** e é a fonte de verdade do
> conjunto Fig 1–7.

- **Contexto:** o rascunho de Results do artigo fixou a numeração das figuras
  principais. Rodada de reorganização: extrair painéis de figuras compostas
  intermediárias para figuras próprias com a numeração do artigo, restringir
  as que o artigo cita a PES apenas, e mover para `combined/secondary/` tudo
  que o rascunho atual **não** cita como figura principal (retido como
  candidato a Suplementar — decisão final de Douglas pendente).
- **Mapeamento de cenário confirmado (fonte única, nenhuma correção
  necessária):** `OPT = SSP1-2.6 = ssp126`, `BAU = SSP3-7.0 = ssp370`,
  `PES = SSP5-8.5 = ssp585`. `src.config.AQUEDUCT_SCENARIO_FOR_CMIP6`
  (`{"ssp126":"opt","ssp370":"bau","ssp585":"pes"}`) é a única fonte;
  `ccrs_calculator.WATER_TO_HEAT` é o inverso exato. Os arquivos
  `heat_risk_band_ssp126/370/585.png` derivam de `heat_scenario` via essa
  tabela — já mapeiam corretamente a opt/bau/pes. Novo teste de trava:
  `test_scenario_mapping_opt_bau_pes_matches_ssp_labels`.
- **Fig 1** — `diagrams.plot_pipeline_overview` → `diagrams/figure1_pipeline_overview.png`. Inalterada.
- **Fig 2** — `charts.plot_figure2_capacity_exposure_by_band` →
  `combined/figure2_capacity_exposure_by_band.png`. Extraída do painel A do
  composto intermediário. 2 painéis: (a) WaterRiskBand (5 níveis nativos),
  (b) HeatRiskBand (4 níveis nativos, GFDL-ESM4). Agregação **nacional**
  (`band_capacity_shares` por `country × water_scenario` / `country ×
  heat_scenario`, **sem** corte por bucket — reverte o corte usado no painel
  A do composto). Eixo X = os 3 cenários apenas; **sem coluna "Historical"**
  (não existe raster de presente no pipeline — confirmado de novo, não
  fabricado). Quase-duplicata de `plot_capacity_by_risk_band` (categoria 8,
  em `secondary/`), mantida de propósito: a categoria 8 é a figura de
  método/referência interna, a Fig 2 é a mesma coisa promovida com o nome do
  artigo — redundância sinalizada, decisão de Douglas se quer resolver.
- **Fig 3 / Fig 4** — **cópias byte-idênticas**, não funções dedicadas.
  `maps.plot_water_risk_band_map(water_scenario="pes")` →
  `combined/water_risk_band_pes.png`, copiado para
  `combined/figure3_water_risk_band_pes.png` (+pdf).
  `maps.plot_heat_risk_band_map(water_scenario="pes")` →
  `combined/heat_risk_band_ssp585.png`, copiado para
  `combined/figure4_heat_risk_band_pes.png` (+pdf). A cópia/rename é passo de
  geração ad-hoc (ver abaixo), não há lógica no código que grave esses nomes.
- **Fig 5 (2026-09-07)** — `maps.plot_figure5_ccrs_overview` →
  `combined/figure5_ccrs_overview_{scenario}_{gcm}.png` (3 cenários, GFDL-ESM4).
  É o mapa da categoria 1 (bolhas coloridas por bucket, anel no top-decil de
  CCRS), varrido pelos 3 cenários de água, promovido a Figura 5 do manuscrito.
  Douglas prefere esse layout ao painel PES único de cor contínua. **Sem
  mudança visual** — só renome do arquivo (`figure5_` prefix, cenário antes do
  GCM) e do papel no artigo. Função renomeada de `plot_ccrs_overview_map`.
- **Mapa asset-level (ex-Fig 5, 2026-09-07)** —
  `maps.plot_ccrs_asset_level_pes_map` (ex-`plot_figure5_ccrs_asset_level_pes`)
  → `combined/secondary/ccrs_asset_level_pes_{gcm}.png`. Mesma estrutura de mapa
  (fronteira, território disputado, marcador ∝ √capacidade, rosa dos ventos),
  mas **cor do marcador = CCRS contínuo** (`SEQUENTIAL_CMAP`/viridis, nunca
  diverging para quantidade sem zero natural), não identidade de bucket. PES
  apenas. **Rebaixado a candidato a Suplementar** — responde a pergunta
  diferente da Fig 5 ("quão severo é o score de cada planta" vs. "qual
  tecnologia está mais exposta"), mantido, não deletado. Thresholds de inclusão
  do GEM (hydro ≥45 MW, wind ≥10 MW, etc.) **já satisfeitos por construção** —
  o GEM Global Integrated Power Tracker só rastreia plantas acima do próprio
  limiar; nenhuma linha em `vdata.load_ccrs_final()` está abaixo. Não há
  filtro de capacidade em `src/index/*` para adicionar nem remover; nada é
  filtrado só para exibição.
- **Fig 6** — `charts.plot_figure6_technology_age_vulnerability_pes` →
  `combined/figure6_technology_age_vulnerability_pes_{gcm}.png`. Painéis B/C
  do composto, **PES apenas**. (a) violin CCRS por bucket tecnológico sob
  PES (já era PES-only na rodada anterior — reportado, não "corrigido", não
  havia bug); (b) scatter idade operacional × `age_factor` por bucket.
  Painel (b) **não** tem filtro de cenário: `age_factor` é por planta e
  invariante a `water_scenario` — "sob PES" não muda nada no painel b.
  Reportado porque o pedido implicava dimensão de cenário nos dois painéis, e
  só um tem.
- **Fig 7** — `charts.plot_figure7_montecarlo_stability_pes` →
  `combined/figure7_montecarlo_stability_pes_{gcm}.png`. **PES apenas**, 2
  painéis **genuinamente separados** (resolve o descasamento legenda/figura
  do painel fundido de 3 cenários): (a) densidade CCRS por país sob PES;
  (b) barras de estabilidade de ranking ordinal (% de sorteios MC em que cada
  país fica 1º/2º/3º). Mesma saída de `mc.run_country_scenario_draws`
  (N=1000, GFDL-ESM4 — **não reaberto**, `ARCHITECTURE.md` Sec. 8), fatiada
  para PES. `FIGURE7_CAPTION` **corrigido** (autorizado por Douglas): a
  versão anterior alegava "structural uncertainties between global
  circulation models (GFDL-ESM4 and MIROC6)" — falso para esta figura, que
  só amostra de GFDL-ESM4. Reescrito para "parametric uncertainty ... under
  GFDL-ESM4, the framework's primary climate model" (os 3 grupos de
  perturbação aprovados, SSP5-8.5). Só texto — `FIGURE7_CAPTION` é constante
  de legenda do manuscrito, **não** renderizada na figura, então a figura no
  disco não precisou ser regerada. `run_country_scenario_draws` continua
  GFDL-ESM4 apenas (pool de MIROC6 fora de escopo).
- **Deletados de vez (não realocados):** `plot_figure3_capacity_vulnerability_profiles`
  (composto 2×2 intermediário), `plot_national_ccrs_with_ci`,
  `plot_capacity_vulnerability_by_bucket_water/_heat` +
  `_capacity_vulnerability_scenario_figure`. `plot_ccrs_rank_probability` /
  `plot_ccrs_rank_density` já não existiam (fundidos em rodada anterior).
- **Movidos para `combined/secondary/` (candidatos a Suplementar, NÃO
  citados no rascunho de Results, decisão final de Douglas pendente):**
  `charts.plot_ccrs_rank_stability` (versão 3 cenários; `charts.SECONDARY_DIR`),
  `charts.plot_hazard_term_contribution_distribution`,
  `maps.plot_worst_case_risk_band_map` (todos os 3 cenários — antes só bau
  no disco), `maps.plot_ccrs_scenario_delta_map(combined=True)` (via
  `maps._secondary_dir()` — função, não constante, para o monkeypatch de
  `OUTPUT_MAPS` dos testes funcionar),
  `emdat_validation.plot_emdat_spatial_validation` (via novo
  `emdat_validation.SECONDARY_DIR`). Nenhuma lógica geradora nem dado
  apagado — só a pasta de output mudou. Os mapas `ccrs_scenario_delta`
  **por país** (`maps/<país>/`) não foram tocados (não fazem parte do
  conjunto `combined/` de figura principal).
- **`_common`:** `FONT_SCALE` 1.2 → 1.32; rosa dos ventos reescrita —
  estrela de 8 pontas, só "N" rotulado, diâmetro físico **fixo em
  polegadas** (`COMPASS_ROSE_SIZE_IN`, não fração de eixo), e a chamada
  `add_compass_rose` movida para um passo final por figura, **depois** da
  legenda/colorbar (senão o bbox lido está desatualizado e a rosa sai com
  tamanhos diferentes entre categorias).
- **`risk_bands.py`:** única mudança é encurtar `WORST_CASE_COMPARABILITY_NOTE`
  (texto na figura) para uma frase — sem mudança de fórmula/lógica.
- **Geração das figuras — sem runner commitado.** Não existe `python -m`
  para "gerar todas as figuras do artigo". Cada figura é gerada importando a
  função `src/visualization/*.plot_*` e chamando-a (as figuras varridas por
  cenário precisam de uma chamada por cenário). Esta rodada usou um script
  descartável (`load_band_tables()` + `load_ccrs_final()` + draws MC
  computados uma vez e passados adiante). Ver `06-areas-de-risco.md`.
- **Ambiente (importante):** o `.venv/` estava **sem `scipy`** (import de
  `charts.py`/`monte_carlo.py` quebrava). `pip install -r requirements.txt`
  puxou **pandas 3.0.5**, que quebra 2 testes: guardas `x is None` em coluna
  object do pandas — o `None` vira `NaN` no pandas 3 (`risk_bands.worst_case_band`
  com fixture sintética, e um teste de `emdat_validation`). Revertido para
  **pandas 2.3.3** (`pip install "pandas<3"`) — baseline em que o projeto foi
  desenvolvido/testado. `requirements.txt` **pinado** em
  `pandas>=2.0.0,<3.0.0` (autorizado por Douglas, 2026-09-05). Migração para
  pandas 3 fica como tarefa futura separada.
- **Arquivos:** `src/visualization/charts.py`, `maps.py`, `_common.py`,
  `emdat_validation.py`, `src/index/risk_bands.py` (só a nota),
  `tests/test_visualization.py` (Fig 2/5/6/7, trava de mapeamento de
  cenário, remoção das figuras deletadas, secondary; ver diff),
  `requirements.txt` (teto `pandas<3`).
- **Status:** Ativa (commitada em `95fa515`, "Renumber the figure set to
  the manuscript's Figure 1-7"). Decisão de quais figuras excedentes viram
  Suplementar: pendente de Douglas.

### 23.1 Ajuste fino de Fig 2/6/7 (2026-09-06)

- **Fig 2:** duas legendas independentes, uma por painel (WaterRiskBand 5
  níveis sob o painel a, HeatRiskBand 4 níveis sob o painel b) — não mais
  uma legenda global "Water: X / Heat: X". Eixo X agrupado por país: 3
  barras (opt/bau/pes, nessa ordem, não alfabética) por bloco de país, com
  vão entre blocos e o nome do país como rótulo em negrito centrado sob o
  bloco (`ax.get_xaxis_transform()`). O painel de calor relabela
  `heat_scenario` (ssp126/370/585) para opt/bau/pes via
  `AQUEDUCT_SCENARIO_FOR_CMIP6` para os dois painéis compartilharem um eixo.
  Helpers `_draw_grouped_band_exposure_panel` / `_band_swatch_handles`
  substituem `_draw_band_exposure_panel` / `_band_and_heat_legend_handles`
  (removidos); `_stacked_bar` (compartilhado com categorias 5/8) **não**
  foi tocado.
- **Fig 6 painel A:** violin KDE trocado por **box+strip** — mesmo idioma de
  `plot_hazard_term_contribution_distribution` (`_draw_box_and_strip`:
  quantis da amostra completa, strip subamostrada acima de
  `STRIP_MAX_POINTS`, `n` real e `n` mostrado por bucket no rótulo do eixo).
  `_draw_violin` e `FIGURE6_VIOLIN_MIN_ROWS` removidos.
  `_draw_technology_violin_panel` → `_draw_technology_exposure_panel`.
- **Fig 6 painel B:** continua scatter (não virou barra agregada). Área do
  marcador ∝ `capacity_mw` (escala √, convenção de bolha do projeto),
  alpha 0.22 para sobreposição, e caixa de texto com a idade operacional
  média ponderada por capacidade por país (Brasil 47 / Portugal 45 / Índia
  42 anos, dado real). **Sem filtro de cenário, por design** — `age_factor`
  é invariante a `water_scenario`; não é correção pendente. `age_factors`
  agora precisa de `capacity_mw` (produção já carrega; fixture sintética
  atualizada).
- **Fig 7:** fundida de 2 painéis em **1 painel único** — curvas de
  densidade CCRS por país sob PES, com a estabilidade de ranking como
  anotação de texto embutida ("India > Brazil > Portugal: 100%", via
  `mc.full_ranking_distribution`), não mais um painel de barras separado
  (alinha com a decisão já tomada para `plot_ccrs_rank_stability`). Eixo X:
  **escala log** (`xscale="log"`, padrão) — Brasil (~0,33) e Portugal
  (~0,30) ficam espremidos contra a borda esquerda numa escala linear
  auto-zoom; o log dá proporção ao low-end e separa os dois. `xscale=
  "linear"` (auto-zoom ao range real, sem 0,2–1,0 fixo) fica disponível
  para comparação. Forma da densidade preservada nas duas — não é a forma
  ponto+IC (já rejeitada). `FIGURE7_CAPTION` reescrito para painel único
  (sem "a,"/"b,").
- **Testes:** `tests/test_visualization.py` — Fig 2 (inalterado, 2 axes),
  Fig 6 (box+strip em vez de violin, tamanho de marcador ∝ capacidade,
  helper renomeado), Fig 7 (`test_figure7_is_a_single_panel`, anotação de
  ranking, ambos os `xscale`). Suíte completa verde (pandas 2.3.3).
- **Status:** Ativa (commitada, "Fine-tune Figures 2, 6
  and 7 after the manuscript review").

### 23.2 Segundo ajuste fino: texto, rosa dos ventos, variantes por cenário (2026-09-06)

- **Fig 2:** títulos de painel passam a "a -- Water Risk Band" / "b -- Heat
  Risk Band" (com espaço, sem o parentético metodológico "(fixed WRI
  Aqueduct 4.0 cuts)" / "(... sample-relative cuts)"). Título de cada
  legenda idem. `pad=12` no título do painel e `bbox_to_anchor` da legenda
  de -0.2 → -0.28 para dar respiro vertical.
- **Fig 6:** eixo Y do painel A passa de "CCRS (gfdl_esm4, PES)" para só
  "CCRS"; eixo Y do painel B de "age_factor ( >= 1 )" para "Age Factor". A
  função `plot_figure6_technology_age_vulnerability_pes` ganhou parâmetro
  `scenario="pes"`; opt/bau geram a mesma estrutura de 2 painéis e vão para
  `combined/secondary/figure6_technology_age_vulnerability_{scenario}_{gcm}`.
  Painel B é idêntico nos três (invariante a cenário, por design).
- **Fig 7:** a **Figure 7 do artigo passa a ser a versão de 3 cenários**
  (`plot_ccrs_rank_stability`), salva em `combined/` com o nome que a
  PES-only tinha (`figure7_montecarlo_stability_pes_{gcm}`) — a referência
  do manuscrito não se move. A antiga PES-only
  (`plot_figure7_montecarlo_stability_pes`) vira peça secundária isolada:
  `combined/secondary/figure7_montecarlo_stability_pes_only_{gcm}`. O
  `ccrs_rank_stability_{gcm}` órfão em secondary/ foi removido. "(gfdl_esm4)"
  saiu do rótulo do eixo X das duas.
  - **Correção final (mesma data):** `plot_ccrs_rank_stability` ganhou
    `xscale="log"` (default), mesmo tratamento da PES-only — os 3 painéis
    opt/bau/pes em escala log no eixo X (Brasil/Portugal deixam de ficar
    espremidos). `FIGURE7_CAPTION` reescrito para a figura de 3 cenários
    (texto-base fornecido por Douglas). Ajuste de precisão na frase final:
    India > (Brasil e Portugal) em 100% dos draws nos 3 cenários, mas a
    ordem Brasil↔Portugal **não** é estável (Brasil à frente em OPT/PES,
    Portugal em BAU) — a legenda afirma robustez só para a divergência
    India-vs-resto e declara a reversão Brasil-Portugal.
- **Rosa dos ventos:** nenhuma mudança de código — `add_compass_rose` já
  produz tamanho/estilo uniforme desde o fix de "final pass" de 2026-09-05
  (o teste `test_compass_rose_is_the_same_physical_size_across_every_map_
  category` já cobre isso). A divergência que Douglas viu eram PNGs velhos
  no disco (opt/ssp126 gerados 09-05 07:45, antes do fix). Resolvido
  regenerando todas as categorias de mapa.
- **Testes:** novos — Fig 2 (títulos/legendas sem parentético, com espaço),
  Fig 6 (eixos Y, variantes opt/bau → secondary), Fig 7
  (`test_fig4_rank_stability_figure` agora afirma nome/pasta de Figure 7
  primária; `test_figure7_pes_only_is_now_a_secondary_piece`; rótulo de eixo
  X sem sufixo de GCM). Vários testes de Fig 7 trocaram
  `monkeypatch OUT_DIR` ↔ `SECONDARY_DIR` por causa da troca de pasta.
- **Status:** Ativa. Nenhum commit nesta sub-rodada — aguardando autorização.

## 24. Limpeza de qualidade de código pré-publicação (2026-09-06)

- **Contexto:** rodada de auditoria de qualidade de código antes da
  publicação/acompanhamento do artigo. Só limpeza — nenhuma decisão de
  fórmula/metodologia reaberta.
- **Decisão / mudanças:**
  1. **Código morto removido.** `data.top_n_by_ccrs()` (sem chamadores; a
     lógica real está em `charts.plot_top_n_ccrs_breakdown_by_bucket`);
     `_common.figure_caption_footer_single/footer_below_artist/
     multi_panel_figsize/single_panel_figsize` (+ constantes
     `SINGLE_PANEL_LEFT/RIGHT`) — herdados do repo antigo, sem chamadores.
  2. **`apply_to_hazard` movido para fora de `src/index/`.** `age_factor` e
     `event_multiplier` só provam o passo de um fator isolado — nunca são
     chamados pelo pipeline real (`ccrs_report.assemble_ccrs` é a fonte
     única). Movidos para `tests/diagnostics/hazard_step_probes.py`
     (`age_factor_apply_to_hazard`, `event_multiplier_apply_to_hazard`), não
     coletado pelo pytest, importado por `test_age_factor.py` /
     `test_event_multiplier.py`. `age_factor.main()` deixa de escrever
     `ccrs_hazard_aged.csv` (artefato diagnóstico que nada consumia); ainda
     escreve `ccrs_age_factors.csv` e `age_factor_report.md`.
  3. **`src/processors/_common.py` criado.** Consolida `_find_aqueduct_csv`
     e `_load_reference_grid` (duplicados quase byte-a-byte entre
     `water_stress_processor` e `water_variability_processor`) e o guard de
     grade `GridMismatchError` + `grid_signature` + `assert_consistent_grid`
     + `load_country_rasters` (duplicados entre `heat_stress_processor` e
     `spei_processor`). Cada processor importa/reexporta do módulo comum;
     `load_country_rasters` recebe o loader por-raster como argumento
     (heat abre o raster do downloader, SPEI o raw que ele mesmo calcula).
     `monte_carlo._retention_vector` / `_coal_retention_vec` /
     `compute_draw_ccrs` **não** tocados — duplicação documentada, com teste
     cross-check, motivada por performance.
  4. **Marcadores "Point to validate" resolvidos.** `monte_carlo.py` (×2:
     perturbação térmica pós-SPEI, RNG por país) e `diagrams.py` (Figure 1
     já aprovada/commitada) — substituídos por nota de decisão fechada.
     `risk_bands.py:242` ("pending approval") corrigido para refletir a
     aprovação de Douglas de 2026-09-05 já registrada logo abaixo (linha
     274) — elimina a contradição interna.
  5. **Comentários/docstrings desatualizados.** ~12 referências a "ainda não
     implementado/escrito" (Monte Carlo, `assemble_ccrs`, `spei_processor`,
     `emdat_validation`, MIROC6/V4) repontadas para os módulos reais;
     narração de reversões de desenvolvimento (convenção de sinal do
     `age_factor`, fator 0.79 do hydro) removida de `age_factor.py` /
     `ccrs_calculator.py` (o histórico fica em `docs/DECISIONS.md`); itens
     de spec marcados "open" (D, G) corrigidos para "closed".
- **Pendente de decisão de Douglas (reportado, não tocado):** `maps.py:37`
  — remoção permanente (ou não) do disclaimer GADM de território disputado
  no rodapé dos mapas.
- **Arquivos:** `src/visualization/{data,_common,diagrams,charts}.py`,
  `src/index/{age_factor,event_multiplier,monte_carlo,ccrs_calculator}.py`,
  `src/processors/{_common (novo),water_stress_processor,
  water_variability_processor,heat_stress_processor,spei_processor}.py`,
  `tests/diagnostics/{__init__,hazard_step_probes}.py` (novos),
  `tests/test_{age_factor,event_multiplier}.py`, `docs/memory/{04,06,README}`.
- **Status:** Ativa. Suíte completa: ver resultado da rodada. Nenhum commit
  — aguardando autorização.

## 25. Orquestrador central `src/main.py` (2026-09-06)

- **Contexto:** rodar o pipeline inteiro exigia ~9 chamadas `python -m`
  separadas, e cada `main()` de módulo recomputa seus próprios insumos:
  `age_factor`/`event_multiplier`/`risk_bands` acabavam rodando ~4× e o
  `monte_carlo._Precomputed` (a reconstrução cara de Hazard + bandas a partir
  dos rasters) 3× — uma em `monte_carlo.main()`, uma em `tables.main()`, uma
  dentro da figura de rank-stability.
- **Decisão:** `src/main.py`, rodado como `python -m src.main` — consistente
  com a convenção `python -m` de todo o resto (o `main.py` de raiz do repo
  antigo era "Orquestração antiga", fora de escopo, `INVENTORY.md`). Orquestra
  na ordem de dependência (processors condicionais → T1 → T2/T3 → T4 → T5 →
  Monte Carlo → tabelas → figuras → validação espacial EM-DAT), computando
  cada dependência **uma vez** e passando os objetos em memória adiante pelos
  parâmetros `*=None` que as funções já expõem, mais **três ganchos de
  injeção** novos, todos opcionais e backward-compatible:
  - `ccrs_calculator.compute_hazard_by_gcm(frames_by_model=)` — empilha
    frames `compute_hazard(m)` já em memória em vez de recomputá-los;
  - `monte_carlo._Precomputed(hazard_by_model=, band_tables=)` — reusa o T1
    e o T4 já computados;
  - `tables.hazard_term_contribution_per_plant(hazard=)` /
    `hazard_term_contribution_table(per_plant=)` — evita recomputar o Hazard
    para as duas figuras C4.
  O CI nacional (C1/C2) é derivado de `run_country_scenario_draws` via
  `main.ci_from_draws` (reproduz `run_country_scenario_simulation` grupo a
  grupo) em vez de uma segunda simulação. Cada `main()` de módulo fica
  intacto para uso isolado; o orquestrador chama as funções internas, nunca
  os CLIs.
- **Escopo dos flags `--countries` / `--scenarios`:** afetam **só** os loops
  de figura/tabela. O índice (T1–T5) e o Monte Carlo sempre rodam full-scope
  — os cortes percentil do HeatRiskBand, os bounds globais e o `rate_max` do
  `EventMultiplier` só estão corretos sobre os 3 países e os 3 cenários.
- **Consequências:** rodar `python -m src.main --skip-processors` do zero
  reproduz `data/outputs/tables/` — 16/18 CSVs byte-idênticos (incl. os do
  Monte Carlo, prova de que a injeção do `_Precomputed` é bit-exata);
  `ccrs_final.csv` difere em 6,66e-16 (1 ulp — o `ccrs_report.main()` relê
  `ccrs_hazard.csv` do disco antes de multiplicar, o orquestrador multiplica
  o frame em memória; mesmo resíduo in-memory-vs-disco de `data.py`);
  `ccrs_age_factors.csv` bit-idêntico nos valores, difere só na quebra de
  linha (`age_factor.main()` grava via `Path.write_text(df.to_csv())`, que
  duplica `\n`→`\r\r\n` no Windows — quirk latente daquele CLI; o
  orquestrador grava `\r\n` limpo via `df.to_csv(path)`).
- **Figuras 3 e 4:** o orquestrador faz as cópias byte-idênticas
  (`water_risk_band_pes`→`figure3_water_risk_band_pes`,
  `heat_risk_band_ssp585`→`figure4_heat_risk_band_pes`, png+pdf) no fim da
  fase de figuras. O mapa HeatRiskBand é **só GFDL-ESM4** (a comparação com
  MIROC6 é a tabela `heat_band_gcm_comparison`, nunca um 2º mapa — o stem do
  arquivo não carrega GCM, então um loop por GCM sobrescreveria silenciosamente).
- **Testes:** `tests/test_main.py` — spies nas funções internas (nunca nos
  CLIs) confirmam: cada etapa de dependência roda 1× (T1/T4 1× por GCM), o
  `_Precomputed` é construído 1×, o mesmo objeto `pre` e o mesmo frame
  `draws` chegam por referência aos 3 consumidores do Monte Carlo (figuras
  de rank-stability, tabela C5, resumo nacional C1/C2), os flags `--skip-*`
  gateiam suas fases, e a cardinalidade dos loops de figura está certa
  (mapa por cenário, não por cenário×GCM).
- **Arquivos:** `src/main.py` (novo), `tests/test_main.py` (novo),
  `src/index/{ccrs_calculator,monte_carlo}.py`,
  `src/visualization/tables.py`, `docs/memory/04`.
- **Status:** Ativa. Nenhum commit — aguardando autorização.

## 26. GEAR v3 rework — Phase 0 blocking verifications fechadas (2026-09-11)

- **Contexto:** `docs/rework/GEAR_v3_work_plan.md` (plano de reconstrução da
  metodologia GEAR v3, ainda não implementado em `src/`) exigia quatro
  verificações bloqueantes antes de qualquer código da Fase 1: campo de
  tecnologia de resfriamento e campo de retrofit/repowering no GEM, classes
  de perigo FWI/EFFIS e limiares de profundidade de inundação HAZUS-MH, e
  limiar de vento estrutural para trackers solares utility-scale.
- **Decisão:** as quatro investigações foram concluídas e confirmadas pelo
  autor; nenhuma implica mudança de código nesta sessão (Fase 0 é
  só-investigação por regra do próprio plano). Achados:
  1. Campo de tecnologia de resfriamento: **não existe** em nenhuma das 52
     colunas do GEM Global Integrated Power Tracker (snapshot
     `20260809`), para nenhum dos três países. Campo mais próximo
     (`Technology`) registra ciclo turbina/caldeira, não sistema de
     resfriamento do condensador.
  2. Campo de retrofit/repowering: **reconfirmado vazio**, sem mudança
     desde o inventário anterior. Família "Conversion" (eventos de
     conversão de combustível) tem ~0 valores não-nulos nos três países.
  3. Classes de perigo FWI/EFFIS: fonte primária (EFFIS/Copernicus,
     base Van Wagner & Pickett 1985) define **6 classes**, não 5 — Low
     (<11.2), Moderate (11.2-21.3), High (21.3-38.0), Very High
     (38.0-50.0), Extreme (50.0-70.0), Very Extreme (>70.0, adicionada
     em junho de 2021). Adotadas as 6 como Tier 1 para Wildfire.
  4. Limiares HAZUS-MH: os valores rascunhados (0,2/0,5/1,5 m) **não
     existem** no manual técnico primário da FEMA — HAZUS-MH usa curvas
     contínuas de profundidade-dano por tipo de ocupação, em pés, não
     cortes categóricos em metros; adicionalmente incompatível com o
     dado `pr` do CMIP6 já usado no pipeline (sem etapa de conversão
     precipitação→profundidade de inundação). Extreme Precipitation
     rebaixada de Tier 1 para Tier 3 (percentil amostral, mesmo método
     de Extreme Heat).
  5. Limiar de vento estrutural para trackers solares: **nenhum valor
     Tier 1 defensável** — ASCE 7 é inerentemente específico de local
     (não uma constante como o cut-out de turbina IEC), e classificações
     de sobrevivência variam por geração de fabricante (~51-60+ m/s
     observado). Fallback ERA5 gust percentile confirmado como **final**
     para Solar, não contingência.
- **Consequências:** `docs/rework/GEAR_v3_work_plan.md` Fase 0 fechada,
  Fase 1 liberada para começar. `docs/rework/GEAR_v3_methodology_nature_
  format.md` Seções 3.1, 3.2 e a tabela de Tier 1/Tier 3 da Seção 4
  reescritas para refletir estado resolvido, não mais "pending". Nenhuma
  mudança em `src/` — os hazards Wildfire e Extreme Precipitation e a
  reestruturação Hazard/Exposure/Vulnerability da v3 ainda não estão
  implementados (Fase 1-3 do plano).
- **Arquivos:** `docs/DECISIONS.md` (cinco novas entradas, 2026-09-11),
  `docs/ARCHITECTURE.md` Seções 7.1 e 7.3 (notas de reconfirmação),
  `docs/rework/GEAR_v3_methodology_nature_format.md`,
  `docs/rework/GEAR_v3_work_plan.md`.
- **Status:** Ativa. Achados são definitivos (verificação contra fonte
  primária), não sujeitos a nova checagem a menos que a fonte primária
  (GEM, EFFIS, FEMA, fabricantes de tracker) publique uma nova versão.

## 27. GEAR v3 Fase 1 — núcleo Risk_i,h substitui CCRS (2026-09-11)

- **Contexto:** Fase 1 do plano de reconstrução v3
  (`docs/rework/GEAR_v3_work_plan.md`) exigia substituir o núcleo
  `Hazard × age_factor × EventMultiplier` (CCRS) pela Equação 1
  (`Risk_i,h = Hazard_i,h × Exposure_i × Vulnerability_i`, por hazard,
  nunca somado entre hazards), remover `EventMultiplier` do núcleo, e
  aplicar o achado da Fase 0 sobre ausência do campo de resfriamento no
  GEM (bucket `thermal` homogêneo).
- **Decisão:** `src/index/ccrs_calculator.py` e `src/index/ccrs_report.py`
  foram **deletados** (não depreciados) e substituídos por
  `src/index/risk_calculator.py`. Principais escolhas:
  - `risk_i_h(hazard_i_h, exposure_mw, vulnerability)` é o produto direto
    da Equação 1, uma linha por hazard — não existe mais um `Hazard_i,s`
    combinado. A infraestrutura de amostragem/transformação/bounds
    (`sample_terms`, `transform_term`, `FROZEN_BOUNDS`, `plant_uid`) foi
    **portada sem alteração** — Fase 1 não mexe em normalização
    (isso é Fase 2.4/2.5, mantido importável, não inlined).
  - Exposure: `exposure_capacity_mw` (MW bruto, única forma aceita por
    `risk_i_h`) vs. `exposure_log10_display` (transform de visualização,
    retorna um array com subtipo `ExposureLog10Display`; `risk_i_h`
    levanta `TypeError` se receber esse tipo — guarda em nível de tipo,
    não só de convenção).
  - `HAZARD_TEMPORAL_WINDOW`: constante nomeada por termo de hazard
    (`ws`/`sv`/`iv` = ponto-estimativa Aqueduct ~2050; `heat`/`spei` =
    janela CMIP6 explícita 2041-2070), em vez de depender de prosa em
    docstring de processor.
  - `EventMultiplier` removido do núcleo (nenhum import, nenhuma
    chamada). `event_multiplier.py` continua existindo, apenas com o
    import de `ccrs_calculator` renomeado para `risk_calculator`
    (mudança mecânica, sem lógica nova) — candidato a validador da Fase
    5, não usado por `risk_calculator.py`.
  - **Sinalizado, não decidido silenciosamente:** `sv`/`iv` (variabilidade
    sazonal/interanual da água) eram combinados com `ws` em um
    `water_sub` composto no núcleo antigo. A metodologia v3 (Seção 2)
    lista só "Water Stress" como hazard — não menciona `sv`/`iv`. Em vez
    de manter o composto antigo ou descartar os dois indicadores em
    silêncio, `risk_calculator.py` computa `sv`/`iv` como hazards
    independentes, rotulados como "não é um hazard da Seção 2 v3,
    pendente da Fase 3" — decisão de inclusão fica para a Fase 3.
  - `thermal` permanece homogêneo (Fase 1.3) — nenhuma bifurcação
    água-de-passagem/seco, já que o campo de resfriamento não existe no
    GEM (achado da Fase 0).
- **Quebra em cascata, esperada e não mascarada:** `src/index/
  risk_bands.py`, `src/index/monte_carlo.py`,
  `src/index/emdat_validation.py`, `src/main.py` e todo
  `src/visualization/` ainda importam símbolos agora deletados
  (`BUCKET_WEIGHTS`, `compute_hazard`, `compute_hazard_by_gcm`, colunas
  `ccrs_{gcm}`) — quebram na importação ou na chamada. Correção desses
  módulos depende de decisões metodológicas ainda não tomadas (Fase 3
  `RiskBand_i,h`, Fase 4 PSAE, Fase 6/7 sensibilidade/visualização); não
  foram remendados nesta tarefa — fazer isso seria antecipar
  metodologia de fases futuras. `age_factor.py` foi atualizado (só o
  import, sem mudança de lógica) e continua funcionando — é a fonte de
  Vulnerability, inalterada.
- **Testes:** `tests/test_ccrs_calculator.py`, `tests/test_ccrs_report.py`,
  `tests/test_ccrs_integration.py` e `tests/diagnostics/
  hazard_step_probes.py` deletados (testavam exclusivamente a montagem
  CCRS retirada). `tests/test_age_factor.py` e
  `tests/test_event_multiplier.py` perderam só os testes de "apply to
  Hazard" (join contra o schema antigo `hazard_{gcm}`/`ccrs_hazard.csv`)
  — os testes da lógica própria de cada módulo continuam. Novo
  `tests/test_risk_calculator.py` (18 testes): Equação 1, guarda de tipo
  do Exposure, ausência de símbolos CCRS retirados, `HAZARD_TEMPORAL_
  WINDOW`, bounds/transforms herdados, `compute_risk_by_hazard` fim a
  fim. Suite completa (exceto os 4 arquivos quebrados listados acima):
  189 testes passando. `python -m src.index.risk_calculator
  --check-bounds` confirmado contra os dados reais em disco (bounds
  inalterados); `python -m src.index.risk_calculator` roda fim a fim
  (324.240 linhas plant×scenario×hazard_term).
- **Arquivos:** `src/index/risk_calculator.py` (novo),
  `src/index/ccrs_calculator.py` / `src/index/ccrs_report.py` (removidos),
  `src/index/age_factor.py`, `src/index/event_multiplier.py`,
  `src/index/__init__.py`, `tests/test_risk_calculator.py` (novo),
  `tests/test_age_factor.py`, `tests/test_event_multiplier.py`,
  `docs/DECISIONS.md`, `docs/ARCHITECTURE.md` Seções 5 e 7.3,
  `docs/rework/GEAR_v3_work_plan.md`.
- **Status:** Ativa. Fases 1.1/1.2/1.4 fechadas. `sv`/`iv` em aberto
  (Fase 3). `risk_bands.py`/`monte_carlo.py`/`main.py`/
  `src/visualization/` quebrados, aguardando Fases 3/4/6/7.

## 28. GEAR v3 Fase 2.1 — processor de Extreme Precipitation (2026-09-11)

- **Contexto:** Fase 2.1 pedia um novo processor de hazard reaproveitando o
  `pr` diário já baixado para o termo SPEI (sem novo download), no mesmo
  padrão de grade unificada dos demais hazards, Tier 3 (Fase 0 já havia
  fechado que HAZUS-MH não é fonte de limiar válida).
- **Decisão:** `src/processors/extreme_precipitation_processor.py` (novo).
  Indicador bruto: média de dias/ano, na janela 2041-2070, com `pr` diário
  acima do limiar P95 **por pixel** dos próprios dias úmidos daquele pixel
  (`pr >= 1 mm/dia`, convenção ETCCDI wet-day; P95 = convenção ETCCDI "very
  wet days"/R95p, Zhang et al. 2011). Reaproveita
  `cds_precipitation_downloader.raw_dir`/`_open_series`/`_pick_var` (mesmos
  usados por `spei_processor` para `pr`) — zero código de download novo.
  Grade: mesmo padrão nativo→resample 1km
  (`cds_tasmax_downloader._resample_to_1km`) → Min-Max por país (modelos e
  cenários pooled juntos) → guarda de grade compartilhada
  (`GridMismatchError`, `_common.py`) — idêntico a `heat_stress_processor`/
  `spei_processor`.
- **Por que percentil-por-pixel, não um mm fixo:** ao contrário do calor
  (limiar físico fixo 40°C), a metodologia v3 não tem limiar absoluto
  defensável para "chuva extrema" neste tier — o Tier 3 da metodologia já
  especifica "percentis de extremos diários de pr". Em vez de aplicar
  percentil só na classificação (RiskBand, Fase 3), o percentil entra um
  nível antes: o próprio limiar "extremo" é derivado por pixel (P95 dos dias
  úmidos daquele pixel), preservando a mesma forma estrutural do indicador
  de calor ("dias/ano acima de um limiar"), só que o limiar é percentual em
  vez de físico fixo.
- **Não plugado ao núcleo, deliberadamente:** `risk_calculator.HAZARD_TERMS`
  e `HAZARD_TEMPORAL_WINDOW` **não** ganharam entrada `precip` — isso é
  decisão da Fase 3, condicionada ao gate de correlação da Fase 2.5 (contra
  Water Stress e Drought). O módulo novo define `PRECIP_TEMPORAL_WINDOW`
  com o mesmo schema de `risk_calculator.HAZARD_TEMPORAL_WINDOW` (asserção
  na importação), mas como constante isolada, não mesclada no dicionário do
  núcleo — mesclar exigiria adicionar `"precip"` a `HAZARD_TERMS` também
  (há um assert que casa os dois conjuntos), o que ligaria o hazard ao
  Risk_i,h antes da hora.
- **Testes:** `tests/test_extreme_precipitation_processor.py` (11 testes) —
  paths, ausência de HAZUS-MH como fonte de limiar, schema do
  `PRECIP_TEMPORAL_WINDOW`, não-mesclagem no núcleo, aritmética do indicador
  (dia de pico conta, pixel seco vira NaN não zero), guarda de grade. Rodado
  fim a fim contra dado real (Brasil, gfdl_esm4 + miroc6, 3 cenários):
  processa, guarda de grade passa, Min-Max por país calculado (min≈0.033,
  max≈16.23 dias/ano). Suite completa: 200 testes passando (fora dos 4
  arquivos quebrados pela Fase 1).
- **Arquivos:** `src/processors/extreme_precipitation_processor.py` (novo),
  `tests/test_extreme_precipitation_processor.py` (novo), `docs/DECISIONS.md`.
- **Status:** Ativa. Camada de raster (bruta + normalizada) apenas — gate de
  correlação (Fase 2.5) e inclusão em tabela de hazard aplicável (Fase 3) em
  aberto.

## 29. GEAR v3 Fase 2.2 — Wildfire adiado, não implementado (2026-09-11)

- **Contexto:** Fase 2.2 pedia um processor de Wildfire (FWI/EFFIS). Nenhum
  processor chegou a ser escrito — a investigação de fonte de dado (pedida
  pelo autor antes de qualquer código) encontrou um bloqueio real dos dois
  lados possíveis.
- **Decisão:** Wildfire sai do checklist ativo de hazards da v3 e vira
  trabalho futuro / limite de escopo declarado — mesmo tratamento já dado
  ao SLR (`docs/ARCHITECTURE.md` Seção 10). Documentação apenas; não há
  código para remover.
- **Achados que sustentam a decisão:**
  1. Catálogo CDS: `near_surface_relative_humidity` (hurs) não existe na
     lista diária do `projections-cmip6` para nenhum modelo. A alternativa
     (`near_surface_specific_humidity` + `sea_level_pressure`, pra derivar
     RH) também falha — `huss` só existe pra gfdl_esm4/ssp126 e
     gfdl_esm4/ssp370, ausente em gfdl_esm4/ssp585 e em miroc6 nos três
     cenários. Ver `analysis/fwi_catalog_check.py` /
     `analysis/fwi_catalog_check.md`.
  2. Dataset global ETH Zurich FWI-CMIP6 (Quilcaille et al. 2023, DOI
     10.3929/ethz-b-000583391), verificado listando o índice central do
     ZIP `fwixd_hursmin.zip` via HTTP Range requests (1318 arquivos, sem
     baixar 1GB) — **zero cobertura GFDL-ESM4** (só GFDL-CM4, modelo
     diferente, e só historical/ssp245/ssp585); e mesmo ignorando isso, o
     dataset só tem indicadores anuais relativos ao percentil 95 do
     período de referência 1850-1900 por célula, não FWI diário nem as
     classes absolutas EFFIS já fechadas na Fase 0 — incompatível
     estruturalmente com a abordagem RiskBand Tier 1 decidida.
- **Consequências:** `docs/rework/GEAR_v3_methodology_nature_format.md`
  Seções 2/3/5 atualizadas (checklist "seis" → "cinco" hazards, tabelas de
  bucket sem Wildfire, gate de correlação sem o par Wildfire); tabela de
  6 classes EFFIS e o argumento FIRMS-não-é-hazard preservados verbatim
  numa nova Seção 10.1 "Deferred hazards / future work", ao lado do SLR —
  citáveis se uma fonte de dado aparecer. `docs/rework/
  GEAR_v3_work_plan.md` Fase 2.2 vira ponteiro de uma linha; Fase 2.5
  perde o par Wildfire do escopo do gate.
- **Arquivos:** `docs/DECISIONS.md`, `docs/rework/
  GEAR_v3_methodology_nature_format.md`, `docs/rework/
  GEAR_v3_work_plan.md`, `analysis/fwi_catalog_check.py`
  (investigação, mantida — não é código de produção).
- **Status:** Ativa. Adiado, não reaberto sem uma fonte de dado nova.

## 30. GEAR v3 Fase 2.3 — processor de Extreme Wind (ERA5, dois consumidores) (2026-09-11)

- **Contexto:** Fase 2.3 pedia um processor de vento extremo via ERA5
  (rajada ou velocidade sustentada 10m/100m), na mesma infraestrutura de
  grade unificada, servindo dois consumidores (bucket Wind, bucket Solar)
  com limiares potencialmente diferentes (Fase 0.4 já havia fechado
  qual limiar cada um usa) — sem duplicar o processor em duas cópias.
- **Decisão:** `src/downloaders/era5_wind_downloader.py` (novo) baixa a
  rajada instantânea horária a 10m (`instantaneous_10m_wind_gust`, dataset
  CDS `reanalysis-era5-single-levels`), um request por país/ano ao longo de
  `ERA5_WIND_BASELINE_PERIOD` (1991-2020) — sem eixo de modelo/cenário
  (ERA5 é um produto único de reanálise, diferente do CMIP6). Reaproveita
  `cds_tasmax_downloader._country_area` para a caixa delimitadora por país
  (mesma caixa dos demais hazards).
  `src/processors/extreme_wind_processor.py` (novo) reduz a série horária
  ao indicador bruto **mean annual maximum gust (m/s)** por pixel — média
  da rajada máxima de cada ano-calendário no período, métrica padrão de
  engenharia de vento para caracterizar rajada extrema —, na mesma grade
  unificada (`cds_tasmax_downloader._resample_to_1km` → Min-Max por país →
  guarda `GridMismatchError` compartilhada). Ao contrário do calor/chuva
  (indicador já embute um limiar, "dias acima de X"), o indicador de vento
  é deliberadamente agnóstico a limiar, porque os dois consumidores aplicam
  métodos de limiar diferentes e não convergentes sobre a mesma grandeza
  física (m/s): `WIND_BUCKET_THRESHOLD_SPEC` (Tier 1, corte fixo IEC ~25
  m/s) e `SOLAR_BUCKET_THRESHOLD_SPEC` (Tier 3, percentis P75/90/95/99 do
  ERA5, método final por fechamento da Fase 0.4) são specs nomeadas
  passadas para um único dispatcher, `classify_extreme_wind(values,
  threshold_spec)` — não duas funções/processors copiados.
- **Confirmação, não suposição, do escopo do gate de correlação:** verificado
  contra `docs/rework/GEAR_v3_methodology_nature_format.md` Seção 2/5 (lidas
  no estado corrente, já com o adiamento de Wildfire do item 29 aplicado) —
  Extreme Wind nunca aparece como candidato do gate em nenhuma versão do
  texto; a Seção 5 lista hoje só Extreme Precipitation como candidato
  (Wildfire saiu do gate junto com seu próprio adiamento, item 29, por razão
  de disponibilidade de dado não relacionada a vento). Extreme Wind
  permanece um hazard dedicado por bucket (Wind/Solar), nunca sujeito ao
  teste \|r\| < 0.80.
- **Aberto, sinalizado e não decidido — período-base do ERA5:** todo outro
  hazard v3 é uma projeção CMIP6 explícita 2041-2070; ERA5 é reanálise
  histórica, sem eixo SSP/GCM e sem horizonte 2050. A metodologia nomeia
  ERA5 como fonte mas não define nem reconcilia um período-base contra o
  enquadramento de meio de século dos outros hazards. `ERA5_WIND_BASELINE_
  PERIOD = (1991-01-01, 2020-12-31)` (normal climatológica OMM de 30 anos
  corrente) é um default de engenharia aqui, não uma decisão verificada na
  Fase 0 — `extreme_wind_processor.WIND_TEMPORAL_WINDOW_IS_PROJECTED =
  False` deixa essa assimetria como flag explícita, não suposição
  enterrada. Pendente confirmação do autor, mesma classe de status da taxa
  de gás do `age_factor` e da questão de granularidade do RNG.
- **Não plugado ao núcleo, deliberadamente:** `risk_calculator.HAZARD_TERMS`
  e `HAZARD_TEMPORAL_WINDOW` não ganharam entrada `wind` — RiskBand (Fase
  3.2) e inclusão na tabela de hazard aplicável (Fase 3.1) ficam para depois.
- **Testes:** `tests/test_extreme_wind_processor.py` (14 testes) — paths,
  aritmética do mean-annual-max (média das rajadas de pico por ano), o
  dispatcher `classify_extreme_wind` para os dois specs de limiar (incluindo
  rejeição de `kind` desconhecido e NaN nunca contado como observação
  válida), schema de `WIND_TEMPORAL_WINDOW` + flag histórico-vs-projetado,
  não-mesclagem no núcleo, guarda de grade compartilhada. Suite completa:
  213 testes passando (14 novos deste item) fora dos 4 arquivos quebrados
  pela Fase 1, 1 skip esperado (dado ERA5 real ausente).
- **Arquivos:** `src/downloaders/era5_wind_downloader.py` (novo),
  `src/processors/extreme_wind_processor.py` (novo),
  `tests/test_extreme_wind_processor.py` (novo), `docs/DECISIONS.md`.
- **Status:** Ativa. Camada de raster (bruta + normalizada) e utilitário de
  classificação parametrizado apenas. RiskBand/inclusão em tabela aplicável
  (Fase 3) e o período-base ERA5 (acima) ficam em aberto.

## 31. GEAR v3 Fase 2.4 — módulo de normalização isolado (FROZEN_BOUNDS, checagem de normalidade/assimetria, tabela de origem) (2026-09-11)

- **Contexto:** Fase 2.4 pedia um módulo próprio (regra de modularidade)
  para a lógica de `FROZEN_BOUNDS`, a checagem de normalidade/assimetria
  (Seção 4.2 da metodologia) que escolhe entre Min-Max direto, log-transform
  e o candidato `f(x) = -ln(1-x)`, e a tabela de origem estruturada dos
  bounds (Seção 4.3) — rodando de forma independente e uniforme para cada
  hazard, incluindo os candidatos novos das Fases 2.1/2.3 (`precip`,
  `wind`) e os termos `sv`/`iv` já flagados como independentes na Fase 1
  (nunca fundidos de volta em Water Stress).
- **Ponto de parada explícito, não decidido sozinho:** a descrição da tarefa
  citava `f(x) = -ln(1-x)` como decisão já confirmada substituindo o
  log-transform antigo, mas nem `docs/rework/GEAR_v3_methodology_nature_
  format.md` Seção 4.2 nem `docs/DECISIONS.md`/`docs/memory/` tinham
  qualquer registro dessa terceira opção — a metodologia só documentava a
  escolha binária (normal → Min-Max direto; assimétrico → log-transform).
  Perguntado ao autor antes de implementar (regra CLAUDE.md Seção 3: decisão
  metodológica não registrada é ponto de parada, não algo que o código
  resolve sozinho). Confirmado pelo autor: seleção em 3 vias por
  normalidade/assimetria, com `-ln(1-x)` substituindo `log1p` **em todo
  lugar**, não só para Extreme Heat — o log1p comprime a cauda superior de
  uma variável assimétrica à direita (justo onde mais precisão é necessária
  para separar uma planta fisicamente extrema de uma moderada); `-ln(1-x)`
  faz o oposto, expande essa cauda (`-> infinito` quando `x -> 1`).
- **Decisão (módulo novo `src/index/normalization.py`):**
  - **Não modifica `risk_calculator.py`.** Importa dele a infraestrutura já
    verificada (`load_plants`, `sample_raster`, `raster_path`, o pareamento
    `WATER_TO_HEAT`, `COUNTRIES`, `BUCKETS`) e o conjunto de 5 termos que já
    computa (`HAZARD_TERMS`) — não recomputa nem sobrescreve o
    `FROZEN_BOUNDS`/`transform_term` existentes ali, que continuam
    log1p-baseados até a Fase 3.3 decidir aplicar a recomendação. Produz uma
    recomendação separada (transform + bounds + tabela de origem), a ser
    aplicada pela Fase 3.3, não por este módulo.
  - **Conjunto de candidatos ampliado, rodado uniformemente:**
    `NORMALIZATION_CANDIDATE_TERMS = risk_calculator.HAZARD_TERMS + ("precip",
    "wind")` = `ws, heat, sv, iv, spei, precip, wind`. `precip` reaproveita
    `extreme_precipitation_processor.raw_raster_path` (dependente de
    GCM/cenário, como heat/spei); `wind` reaproveita
    `extreme_wind_processor.raw_raster_path` (só país, sem eixo de
    modelo/cenário — pooled uma vez, como os termos "flat" da água).
    Wildfire está ausente por construção — hazard adiado (Fase 2.2), não
    parte de nenhum conjunto. `sv`/`iv` passam pela mesma checagem que
    qualquer outro termo (a atribuição de Min-Max linear que carregavam
    desde o `ccrs_calculator.py` retirado nunca foi resultado de uma
    checagem de normalidade — este módulo reavalia do zero).
  - **Checagem de normalidade/assimetria (`normality_check`):** critério
    decisivo é a assimetria de Fisher-Pearson (`scipy.stats.skew`), corte
    `|skew| > 0.5` (convenção Bulmer 1979, "aproximadamente simétrico"),
    engenharia declarada, não valor de literatura específico da variável.
    Shapiro-Wilk (`scipy.stats.shapiro`, subamostrado deterministicamente
    acima de 5000 pontos) é computado e reportado na tabela de origem só
    como diagnóstico — não decide, porque amostras de milhares de pontos de
    dado geofísico real rejeitam normalidade exata quase sempre, mesmo com
    assimetria leve, tornando o teste pouco informativo como portão binário.
  - **Seleção (`select_transform`):** `neg_log_minmax` se assimétrico,
    `direct_minmax` caso contrário — `log1p_minmax` nunca é retornado (só
    existe como `transform_log1p_minmax`, mantido apenas para a tabela de
    origem mostrar o transform pré-redesign de `ws`/`heat`/`spei` como
    registro histórico).
  - **Aritmética de `transform_neg_log_minmax`:** escala preliminar
    `x_scaled = (raw - lo) / (padded_hi - lo)`, com
    `padded_hi = hi + UPPER_TAIL_PADDING_FRACTION * (hi - lo)`,
    `UPPER_TAIL_PADDING_FRACTION = 0.05` (parâmetro de engenharia declarado,
    não citado de fonte alguma — evita que o máximo do pool caia
    exatamente na singularidade `x=1` de `-ln(1-x)`); depois
    `transformed = -ln(1 - x_scaled)`, reescalado por
    `ln(1 + 1/pad)` (fórmula fechada do valor de `transformed` no máximo do
    pool, independente de `lo`/`hi`) para cair em `[0, 1]`.
  - **Tabela de origem (`build_origin_table`):** uma linha por termo (por
    GCM quando o termo depende de GCM), colunas `hazard_term`,
    `hazard_label`, `gcm`, `origin_source`, `data_tier`, `lower_bound_raw`,
    `upper_bound_raw`, `pool_n`, `skewness`, `shapiro_stat`, `shapiro_p`,
    `shapiro_subsampled`, `is_skewed`, `transform_selected`,
    `transform_note`. `data_tier` é uniforme ("empirical, pooled sample
    min/max, not a literature constant") — tier do BOUND em si, distinto do
    tier do limiar de RiskBand (Fase 3.2), que é outra tabela.
- **CLI:** `python -m src.index.normalization` escreve
  `data/outputs/tables/normalization_origin_table.csv`.
- **Testes:** `tests/test_normalization.py` (23 testes, só função pura — sem
  I/O de raster/CSV): conjunto de candidatos (inclui `precip`/`wind`,
  exclui Wildfire), `wind` como termo flat, checagem de normalidade
  (amostra simétrica não flagada, amostra exponencial flagada, Shapiro
  reportado mas não decide, subamostragem determinística acima do teto),
  `select_transform` nunca retorna `log1p_minmax`, aritmética de
  `transform_neg_log_minmax` (extremos 0/1, monotonicidade, nunca sai de
  `[0,1]` para valor fora do pool, domínio degenerado -> zeros, cauda
  superior mais expandida que o log1p retirado), `apply_transform`
  despachando por nome e rejeitando nome desconhecido, schema da tabela de
  origem e consistência `transform_selected` × `is_skewed`, e uma
  confirmação de que `risk_calculator.HAZARD_TERMS`/`FROZEN_BOUNDS`
  permanecem intocados. Suite completa: 236 testes passando fora dos 5
  arquivos quebrados pela Fase 1 (`risk_bands.py`, `monte_carlo.py`,
  `emdat_validation.py`, `main.py`, `test_visualization.py` — este último
  já quebrado antes desta tarefa, importa o `ccrs_calculator` deletado na
  Fase 1; não tocado aqui, fora de escopo da Fase 2.4).
- **Arquivos:** `src/index/normalization.py` (novo),
  `tests/test_normalization.py` (novo), `docs/DECISIONS.md`.
- **Status:** Ativa. Recomendação (transform + bounds + tabela de origem)
  produzida, não aplicada — `risk_calculator.py` continua com seu
  `FROZEN_BOUNDS`/`transform_term` log1p-baseados até a Fase 3.3 decidir
  aplicar a recomendação (explicitamente, incluindo o caso Extreme Heat,
  sem tratamento especial). Inclusão de `sv`/`iv`/`precip`/`wind` no
  conjunto de hazard aplicável por bucket continua em aberto, Fase 3.1.
