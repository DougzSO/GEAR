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
    ibtracs_downloader.py      IBTrACS v04r01 (NOAA NCEI, sem credencial) -> 1 basin CSV/país (SA/Brasil, NA/Portugal, NI/Índia) -> pontos de trilha por país (Fase 5, 2026-09-15)
    assets_validator.py        NÃO baixa — lê .xlsx manual do GEM -> status/agregação/fuel bucket
    climate_downloader.py      orquestrador: boundaries + cds_tasmax + aqueduct
  processors/          (4) — todos emitem raster 0–1 (Min-Max/país) + acesso ao bruto, mesma grade
    water_stress_processor.py  CSV Aqueduct -> raster normalizado (Min-Max/país, pool bau/opt/pes) + raster bruto; sentinela 9999 -> country_max nos dois
    heat_stress_processor.py   raster extreme_heat_days -> raster normalizado (Min-Max/país, todos os modelos E cenários no mesmo pool: ssp126/ssp370/ssp585 x gfdl_esm4/miroc6); bruto = passthrough do downloader; itera sobre configured_models()
    water_variability_processor.py  CSV Aqueduct sv/iv -> raster normalizado (Min-Max/país, pool bau/opt/pes, SEM log1p) + raster bruto, por indicador; espelha o water_stress_processor, sem sentinela
    spei_processor.py  série diária pr/tas -> SPEI-12 (PET de Thornthwaite, ajuste log-logístico PWM) -> raster de frequência de seca (meses/ano com SPEI-12 <= -1,0), normalizado Min-Max/país como o heat (pool modelos x cenários); item F fechado 2026-09-04
    _common.py         infra compartilhada: _find_aqueduct_csv + _load_reference_grid (water_stress/water_variability); GridMismatchError + assert_consistent_grid + load_country_rasters (heat/spei)
  index/               camada de índice GEAR v3 (reconciliado na Fase 8 — módulos ativos abaixo; os quatro módulos CCRS-era ainda no diretório são retirados/quebrados por design, listados à parte no final deste bloco, nunca descritos como parte da arquitetura corrente)
    risk_calculator.py  Risk_i,h = Hazard_i,h * Exposure_i * Vulnerability_i (Equação 1, Fase 1/2.3/3.3), por hazard, nunca somado entre hazards. Substituiu (não depreciou) ccrs_calculator.py. `LOG_TERMS` = {ws, heat, wind} com `transform_term` `-ln(1-x)` (Fase 3.3); `spei` reclassificado de LOG_TERMS para LIN_TERMS (correção pós-Fase 3.3, Table S3 do artigo confirmou skew baixo); `LIN_TERMS` = {sv, iv, precip, spei}. Ver item 25/27/Fase 3.3.
    hazard_scope.py     tabela H_b por bucket (Fase 3.1) — única fonte de verdade de quais combinações hazard/bucket existem: Hydro (ws,spei,precip,sv,iv) |5|, Thermal (ws,heat,precip) |3|, Wind (wind,) |1|, Solar (heat,precip,wind) |3|. Sem I/O. `PENDING_RISK_I_H_HAZARDS` vazio (wind fechado Fase 2.3/3.3). Ver item 35.
    risk_bands.py       RiskBand_i,h (Fase 3.2) — classificação discreta por hazard/bucket sobre valor bruto (não transformado), lê hazard_scope.APPLICABLE_HAZARDS, nunca classifica combinação fora do H_b (HazardNotApplicableError). THRESHOLD_REGISTRY: Tier 1 absoluto (Water Stress, Extreme Wind/Wind binário) ou Tier 3 percentil (4 cortes, o mais baixo é diagnóstico, os outros 3 limitam as 4 bandas Low/Medium/High/Extreme). Substituiu (deletou) o risk_bands.py antigo (WaterRiskBand/HeatRiskBand, CCRS-era). Ver item 36.
    age_factor.py       multiplicador ≥ 1: age_factor = 2 - clip(retention(age), 0, 1) em [1,2], age = config.YEAR_TARGET(2050) - commissioning_year. Planta velha aumenta o Hazard. Curvas de retenção por fuel_type: coal — dente de serra com overhaul assumido (decai 0,25pp/ano, ciclo de 5 anos, recupera 70% da perda do ciclo ao completar — ciclo e fração são premissa assumida, não da literatura); wind 1-0,004·age uniforme (CF_initial não existe em nenhum arquivo GEM — a forma 1-0,0015·age/CF_initial é código morto, nunca chamada); hydro 1-0,0055·age (sem o fator 0,79); solar (1-0,007)^age; gas/oil-gas = retenção 1,0 → af 1,0 (pinado neutro, confirmado final após busca bibliográfica limitada — não mais "provisório"); nuclear/bioenergy também retenção 1,0. Mixed = média simples dos age_factor. commissioning_year ausente → 1,0 (mantido, sinalizado). Produz UMA coluna age_factor por plant_uid, consumida por risk_calculator.compute_risk_by_hazard (não por um módulo de montagem CCRS, que não existe mais). Reaproveitado sem reescrita desde o CCRS-era. Ver docs/DECISIONS.md 2026-09-04 e 2026-09-11 (pinagem final gas/oil-gas).
    normalization.py    módulo isolado (Fase 2.4) — checagem de normalidade/assimetria real (Fisher-Pearson decisivo, Shapiro-Wilk diagnóstico) por hazard candidato, recomenda direct_minmax (|skew|<=0.5) ou neg_log_minmax (-ln(1-x)); nunca importa de volta em risk_calculator.py. Sua recomendação foi aplicada manualmente à produção pela Fase 3.3 (mudança separada, não automática).
    correlation_gate.py módulo isolado (Fase 2.5) — testa |r| >= 0.80 (GATE_THRESHOLD) para pares candidatos (Extreme Precipitation vs. Water Stress/Drought, sv/iv vs. Water Stress e entre si), com hierarquia de tie-breaker pré-registrada. Rodado contra dado real, todo par passou nas 3 países — resultado alimenta a decisão de H_b da Fase 3.1 (leitura humana, não import automático).
    psae.py              PSAE_i (Fase 4) = fração não-ponderada de hazards do H_b da planta cuja RiskBand é High/Extreme; consome só risk_bands.RiskBandTable.frame (não importa risk_calculator). Complete-case: hazard faltante no H_b -> psae=NaN para aquele plant/water_scenario, h_b_size nunca encolhe, psae_complete/missing_hazards carregam a distinção. compute_psae vetorizado desde 2026-09-14 (pivot + matriz booleana por bucket, ~31x mais rápido que o groupby original, output idêntico verificado).
    contextual_validators.py  validadores contextuais (Fase 5, PARCIAL) — taxonomia de duas classes, três estados (Corroborated/No Record/Not Applicable) por hazard aplicável por ativo. Classe broad-impact (EM-DAT, Seção 7.2): implementada, read-only garantido (nunca realimenta Hazard/RiskBand/PSAE). Classe physical-occurrence (IBTrACS/FIRMS/etc., Seção 7.1): NÃO implementada — nenhuma fonte adquirida, `compute_physical_occurrence_validation()` levanta NotImplementedError explícito, decisão de fonte pendente do autor.
    sensitivity_recompute.py  pipeline de recomputação parcial (Fase 6, infraestrutura) — recomputa só a cadeia age_factor -> RiskBand -> PSAE por draw perturbado, sem reler rasters a cada vez; correctness-verificado contra a produção. NÃO implementa amostragem Sobol/SALib nem roda uma análise de sensibilidade real — isso continua em aberto (granularidade de RNG, agrupamento de dimensão dos cortes percentuais de RiskBand, tratamento de psae_complete=False ainda não decididos). Ver docs/DECISIONS.md, "Phase 6" entries e Phase 8.2.

    Módulos CCRS-era ainda no diretório, quebrados por design desde a Fase 1 (Risk_i,h a substituiu) — nunca parte da arquitetura corrente, mantidos só como histórico/precedente de leitura:
    ccrs_calculator.py / ccrs_report.py   DELETADOS na Fase 1 (não apenas quebrados) — não existem mais no repositório.
    event_multiplier.py  EventMultiplier_c (multiplicador de frequência EM-DAT por país) — não é mais um componente do score; risk_calculator.py's Risk_i,h não o consome. Citado como candidato de insumo futuro para a Fase 5 (validadores), não como parte ativa do núcleo. Ver item 15 de 05-decisoes-tecnicas.md, docs/DECISIONS.md.
    monte_carlo.py       ImportError (importa o ccrs_calculator deletado), confirmado quebrado nesta sessão. Lido só como precedente de mecânica de RNG (country_rng, zlib.crc32+SeedSequence, N_ITERATIONS=1000) para o desenho da Fase 6 — não é a implementação da Fase 6.
    emdat_validation.py  ImportError (mesma causa), CCRS-era, diagnóstico polígono admin-1 x Mann-Whitney U — desenho diferente do validador de três estados da Fase 5 (contextual_validators.py), não reaproveitável como está.
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

## Camada de índice (`src/index/`) — arquitetura corrente v3

`risk_calculator.py` (`Risk_i,h`, Equação 1) consome os rasters **brutos**
(`water_stress_raw_*`, `seasonal_variability_raw_*`,
`interannual_variability_raw_*`, `extreme_heat_days_*`,
`drought_stress_raw_*`, `extreme_precipitation_*`, `extreme_wind_gust_raw_*`)
e `gem_validated_plants_{país}.csv` — não os rasters normalizados por país
dos processors (a normalização de `Hazard_i,h` é global, própria). Reusa os
helpers `raw_raster_path` dos processors e `configured_models()`. Bounds
globais congelados em `FROZEN_BOUNDS` por hazard (inclui `wind` desde a Fase
3.3) com trava de regressão — ver `05-decisoes-tecnicas.md` item 12 (origem,
CCRS-era) e `docs/DECISIONS.md` (fechamentos por hazard, v3).

Ordem lógica (v3): `risk_calculator` (`Risk_i,h`, por hazard, nunca somado)
→ `risk_bands` (`RiskBand_i,h`, classificação sobre valor bruto, lê
`hazard_scope.APPLICABLE_HAZARDS`) → `psae` (`PSAE_i`, fração não-ponderada
de High/Extreme dentro do H_b da planta, consome só `RiskBandTable`) →
`contextual_validators` (Fase 5, PARCIAL — broad-impact/EM-DAT e
physical-occurrence/IBTrACS (`wind` apenas, 2026-09-15) implementados;
FIRMS rejeitado (wildfire fora do hazard set, sem slot em
`APPLICABLE_HAZARDS`); landslide/lightning não investigados — read-only,
nunca realimenta as três etapas anteriores) → `sensitivity_recompute` (Fase 6, infraestrutura de
recomputação parcial, análise Sobol/SALib em si ainda não implementada) →
`visualization/` (Fase 7, NÃO INICIADO para a divisão PSAE/Risk_i,h — o
módulo existente é CCRS-era e está quebrado). Não existe mais um
orquestrador único (`src/main.py` é CCRS-era e está quebrado, ImportError);
cada fase roda via seu próprio CLI (`python -m src.index.<módulo>`).
`normalization.py` e `correlation_gate.py` são módulos de recomendação/
validação isolados (Fase 2.4/2.5), não fazem parte desta cadeia de
dependência direta.

## Mudanças estruturais vs. repositório anterior

Ver `docs/memory/05-decisoes-tecnicas.md` (itens sobre lista de GCM,
paths model-tagged, fuel bucket 5→4, `emdat` só descritivo, orquestrador
sem power/slr, e Min-Max de calor por país com modelos e cenários no mesmo
pool + guarda fail-loud de grade).
