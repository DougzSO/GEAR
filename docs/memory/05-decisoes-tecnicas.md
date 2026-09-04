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
