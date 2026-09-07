# 02 — Arquitetura de `src/`

```
src/
  config.py            dependência compartilhada obrigatória — paths, parâmetros,
                       credenciais, require_*()
  main.py              orquestrador do pipeline completo (python -m src.main): processors
                       condicionais -> T1 -> T2/T3 -> T4 -> T5 -> Monte Carlo -> tabelas
                       -> figuras -> validação espacial EM-DAT. Chama as funções internas
                       (nunca os CLIs), computa cada dependência 1x. Ver 05 item 25.
  downloaders/
    boundaries_downloader.py   GADM 4.1 nível 0; filtro mainland-only; get_country_bounds/geometry
    coastline_downloader.py    Natural Earth 10m coastline (download único global)
    rivers_downloader.py       Natural Earth 10m rivers (download único global)
    cds_tasmax_downloader.py   Copernicus CDS projections-cmip6 -> indicador dias>40C -> raster nativo + 1km
    cds_precipitation_downloader.py  CDS projections-cmip6 pr+tas diário (insumo do SPEI) -> valida série bruta + raster QA de média do período; reusa _climate_bounds / _resample_to_1km do cds_tasmax
    aqueduct_downloader.py     WRI Aqueduct 4.0 future_annual via GEE -> CSV largo por país
    emdat_downloader.py        EM-DAT Archive (Dataverse) -> filtro país/tipo -> contagem + cobertura
    assets_validator.py        NÃO baixa — lê .xlsx manual do GEM -> status/agregação/fuel bucket
    climate_downloader.py      orquestrador: boundaries + cds_tasmax + aqueduct
  processors/          (4) — todos emitem raster 0–1 (Min-Max/país) + acesso ao bruto, mesma grade
    water_stress_processor.py  CSV Aqueduct -> raster normalizado (Min-Max/país, pool bau/opt/pes) + raster bruto; sentinela 9999 -> country_max nos dois
    heat_stress_processor.py   raster extreme_heat_days -> raster normalizado (Min-Max/país, todos os modelos E cenários no mesmo pool: ssp126/ssp370/ssp585 x gfdl_esm4/miroc6); bruto = passthrough do downloader; itera sobre configured_models()
    water_variability_processor.py  CSV Aqueduct sv/iv -> raster normalizado (Min-Max/país, pool bau/opt/pes, SEM log1p) + raster bruto, por indicador; espelha o water_stress_processor, sem sentinela
    spei_processor.py  série diária pr/tas -> SPEI-12 (PET de Thornthwaite, ajuste log-logístico PWM) -> raster de frequência de seca (meses/ano com SPEI-12 <= -1,0), normalizado Min-Max/país como o heat (pool modelos x cenários); item F fechado 2026-09-04
    _common.py         infra compartilhada: _find_aqueduct_csv + _load_reference_grid (water_stress/water_variability); GridMismatchError + assert_consistent_grid + load_country_rasters (heat/spei)
  index/               camada de índice (CCRS), reconstruída do zero
    ccrs_calculator.py  termo Hazard_{i,s} por planta/cenário/GCM: amostra os rasters brutos ws/sv/iv/heat/spei, aplica Tlog/Tlin com bounds globais congelados (FROZEN_BOUNDS), pesos água/calor/seca por bucket. Hazard = w_water·water_sub + w_heat·Tlog(heat) + w_drought·Tlog(spei) (3 termos aditivos desde 2026-09-04). NÃO monta o CCRS completo (age_factor e EventMultiplier são etapas separadas, ver ccrs_report.py) nem as bandas de risco.
    risk_bands.py       WaterRiskBand (cortes absolutos WRI fixos 0,208/0,415/0,667/1,0 sobre S_water = 0,4164·ws_raw + 0,2505·sv_raw + 0,3331·iv_raw) e HeatRiskBand (p25/p75/p95 de extreme_heat_days, GFDL-ESM4 primário, 3 cenários pooled) como colunas SEPARADAS — nunca um score único. Tabela de contingência WaterRiskBand×HeatRiskBand como saída auxiliar. Depende só de ccrs_calculator. Aviso literal de não-comparabilidade do HeatRiskBand em todo relatório gerado.
    age_factor.py       multiplicador ≥ 1: age_factor = 2 - clip(retention(age), 0, 1) em [1,2], age = config.YEAR_TARGET(2050) - commissioning_year. Planta velha aumenta o Hazard. Curvas de retenção por fuel_type: coal — dente de serra com overhaul assumido (decai 0,25pp/ano, ciclo de 5 anos, recupera 70% da perda do ciclo ao completar — ciclo e fração são premissa assumida, não da literatura); wind 1-0,004·age uniforme (CF_initial não existe em nenhum arquivo GEM — a forma 1-0,0015·age/CF_initial é código morto, nunca chamada); hydro 1-0,0055·age (sem o fator 0,79); solar (1-0,007)^age; gas/nuclear/bioenergy = retenção 1,0 → af 1,0 (gas provisório). Mixed = média simples dos age_factor. commissioning_year ausente → 1,0 (mantido, sinalizado). Produz UMA coluna age_factor por plant_uid (não monta o CCRS — isso é ccrs_report.assemble_ccrs; o probe isolado do passo vive em tests/diagnostics/hazard_step_probes.py). Convenção ≥1 confirmada como definitiva pelo autor; spec item D fechado, sem bloco OPEN. Ver docs/DECISIONS.md 2026-09-04 (entrada final).
    event_multiplier.py multiplicador ≥ 1 por país: EventMultiplier_c = 1 + 0,5·(rate_c/rate_max), rate_c = N_events(c)/124 (N_events = linhas de data/raw/validation/emdat_{país}.csv, já filtrado por ISO+tipo — nenhuma normalização inventada), rate_max = maior rate_c entre os países passados (Índia, hoje). Geocodificado só a nível de país (V2 fechado). Produz a tabela compute_event_multipliers (não monta o CCRS — isso é ccrs_report.assemble_ccrs, join por country com merge validate="many_to_one" + guarda de contagem). Sem divergência spec/ARCHITECTURE (item C). Ver docs/DECISIONS.md e item 15 de 05-decisoes-tecnicas.md.
    ccrs_report.py       fonte única da montagem T1×T2×T3: assemble_ccrs -> CCRS_i,s = Hazard_i,s * age_factor_i * EventMultiplier_country(i), produto só (nunca soma), por plant_uid×water_scenario, uma coluna ccrs_{gcm} por GCM. age_factor junta por plant_uid, EventMultiplier por country, os dois com merge validate="many_to_one" + guarda de contagem. compute_ccrs = wrapper que relê ccrs_hazard.csv do disco antes de assemble_ccrs (o round-trip pode diferir ~1 ULP de um chamador em memória — resíduo de precisão, não de lógica; nota no docstring). capacity_sum() faz assert (AssertionError, nunca log) de que a soma de capacidade só roda sobre a base computável V6. Relatório: % capacidade por WaterRiskBand e por HeatRiskBand (GFDL-ESM4 primário + MIROC6 painel, nunca blend), contingência reaproveitada de risk_bands.contingency_table, aviso HEAT_BAND_WARNING verbatim.
    monte_carlo.py       sensibilidade Monte Carlo (spec item J): N=1000 × 3 magnitudes, perturbando razão água/calor do bucket thermal (drought fixo), taxas de age_factor (coal/wind/hydro sobre faixas de literatura) e k do EventMultiplier; FROZEN_BOUNDS e cortes de risk_bands.py explicitamente fora de escopo (trava de regressão). _Precomputed = insumos caros (Hazard + bandas por GCM) construídos 1×; run_country_scenario_draws/_simulation, pairwise_order_stability, full_ranking_distribution para as figuras de rank-stability. Ver item 19.
    emdat_validation.py  validação espacial diagnóstica: polígono admin-1 × termo de Hazard, Mann-Whitney U por país×tipo-de-desastre. NÃO realimenta Hazard/CCRS. Ver item 22.
  visualization/         figuras e tabelas do artigo a partir de src/index/* EM MEMÓRIA (nunca de CSV cacheado)
    data.py            camada de dados: load_ccrs_final / load_band_tables / load_*_shares — chama ccrs_report.assemble_ccrs direto
    _common.py         infra de plotagem: fronteira/território disputado, figsize dinâmico por país, rosa dos ventos, save_figure (PNG dpi=200 + PDF)
    maps.py            mapas geoespaciais (overview, delta de cenário, Water/HeatRiskBand, worst-case, base computável)
    charts.py          figuras não-geoespaciais (Figura 2/6/7, exposição por banda, contribuição dos termos, rank-stability do Monte Carlo)
    tables.py          tabelas-resumo CSV (comparação GCM de calor, contingência, proveniência dos pesos, resumo nacional + IC Monte Carlo)
    diagrams.py        Figura 1 — esquema do pipeline
    emdat_validation.py  a figura box/strip da validação espacial
tests/                 pytest; fixtures sintéticas, sem chamada de API real (exceção: testes de dado real que leem rasters processados, pulados com motivo se ausentes). tests/diagnostics/ = probes não-produção, não coletados
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

Os quatro processors emitem raster 0–1 normalizado (Min-Max) + acesso ao
bruto, na MESMA grade de `extreme_heat_days_*_1km.tif`. `heat` precisa rodar
antes de `water` e de `water_variability` (ambos leem um raster de calor como
referência de grade); `spei` depende só das séries diárias `pr`/`tas`
baixadas. O bruto de calor é o próprio arquivo do downloader (passthrough); o
bruto de água, de variabilidade sv/iv e de seca SPEI são computados/
rasterizados pelos respectivos módulos antes do Min-Max. `water_variability`
NÃO aplica log1p (sv/iv têm skew baixo) e não tem máquina de sentinela.
`spei` e `heat` compartilham o guard de consistência de grade
(`processors/_common.py`, `GridMismatchError` fail-loud). Domínio de
normalização e tratamento de sentinela: `docs/DECISIONS.md` (entradas de
2026-09-03) e o termo de SPEI 2026-09-04.

## Camada de índice (`src/index/`)

`ccrs_calculator.py` (termo Hazard) consome os rasters **brutos**
(`water_stress_raw_*`, `seasonal_variability_raw_*`,
`interannual_variability_raw_*`, `extreme_heat_days_*`,
`drought_stress_raw_*`) e `gem_validated_plants_{país}.csv` — não os rasters
normalizados por país dos processors (o CCRS tem normalização global
própria). Reusa os helpers `raw_raster_path` dos quatro processors e
`configured_models()`. Bounds globais congelados em `FROZEN_BOUNDS` (inclui
`spei`) com trava de regressão — ver `05-decisoes-tecnicas.md` item 12.
`risk_bands.py`, `age_factor.py` e `event_multiplier.py` dependem de
`ccrs_calculator` (`age_factor` também de `config.YEAR_TARGET`;
`event_multiplier` também de `emdat_downloader`).

Ordem lógica: `ccrs_calculator` (T1) → (`risk_bands` T4, `age_factor` T2,
`event_multiplier` T3) → `ccrs_report` T5 (`assemble_ccrs` monta o `CCRS_i,s`
completo + relatório de % capacidade por banda) → `monte_carlo` (sensibilidade
J, reusa T1/T4 via `_Precomputed`) e `visualization/` (figuras/tabelas,
consomem `assemble_ccrs` e o `_Precomputed` em memória). O orquestrador
`src/main.py` roda essa cadeia inteira computando cada etapa 1× (ver 05 item
25). Itens 13–16, 18–22 e 25 de `05-decisoes-tecnicas.md`.

## Mudanças estruturais vs. repositório anterior

Ver `docs/memory/05-decisoes-tecnicas.md` (itens sobre lista de GCM,
paths model-tagged, fuel bucket 5→4, `emdat` só descritivo, orquestrador
sem power/slr, e Min-Max de calor por país com modelos e cenários no mesmo
pool + guarda fail-loud de grade).
