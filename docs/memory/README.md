# docs/memory — índice

Memória de engenharia de sessão: como o código deste repositório funciona e
como mexer nele. Propósito diferente de `docs/ARCHITECTURE.md` (metodologia
do artigo), `docs/INVENTORY.md` (herança do repositório anterior) e
`docs/DECISIONS.md` (log datado de decisões metodológicas/de fonte de dado).
Leia os quatro, não um no lugar do outro.

## Ordem de leitura

1. [01-visao-geral.md](01-visao-geral.md) — o que é o projeto e em que fase está.
2. [02-arquitetura.md](02-arquitetura.md) — organização real de `src/`.
3. [03-pipeline-dados.md](03-pipeline-dados.md) — fluxo de aquisição, fontes,
   arquivos gerados.
4. [04-scripts-comandos.md](04-scripts-comandos.md) — como rodar cada coisa,
   credenciais, ambiente virtual.
5. [05-decisoes-tecnicas.md](05-decisoes-tecnicas.md) — decisões de engenharia
   (não científicas), formato Contexto/Decisão/Consequências/Arquivos/Status.
6. [06-areas-de-risco.md](06-areas-de-risco.md) — cobertura de teste, hardcode,
   dependências frágeis, TODOs que bloqueiam fases seguintes.

## Regra prática

"Por que esta fonte/critério/número foi escolhido para o artigo" →
`docs/DECISIONS.md` ou `docs/ARCHITECTURE.md`. "Como este script funciona" ou
"onde eu mexo para fazer X" → aqui.

## Estado quando isto foi escrito

2026-09-04. Camadas de aquisição e de processamento de clima reconstruídas:
`src/config.py`, 9 downloaders (inclui `cds_precipitation_downloader` para o
termo de SPEI), 4 processors de clima (calor, água, variabilidade sv/iv,
seca SPEI), com infraestrutura compartilhada em `src/processors/_common.py`
(entrada Aqueduct + grade de referência; guard de consistência de grade). Camada de índice: `src/index/ccrs_calculator.py` calcula o termo
`Hazard_{i,s}` (transformação global por termo com bounds congelados + trava
de regressão, pesos água/calor por bucket, GFDL-ESM4 e MIROC6 separados);
`src/index/risk_bands.py` calcula WaterRiskBand (cortes absolutos WRI fixos)
e HeatRiskBand (percentis p25/p75/p95 de GFDL-ESM4) como colunas separadas,
nunca um score único; `src/index/age_factor.py` calcula o multiplicador de
idade `≥ 1` (`age_factor = 2 - clip(retention(age), 0, 1)` ∈ `[1,2]` —
convenção confirmada como definitiva pelo autor, item D fechado,
`docs/DECISIONS.md` 2026-09-04; coal com overhaul assumido dente-de-serra,
wind uniforme 0,4%/ano sem `CF_initial`) e multiplica o Hazard por
`plant_uid`; `src/index/event_multiplier.py` calcula o multiplicador de
frequência de desastres `≥ 1` por país (`EventMultiplier_c = 1 +
0,5·rate_c/rate_max`, `rate_c = N_events(c)/124` a partir de
`emdat_{país}.csv`, item C sem divergência spec/ARCHITECTURE) e multiplica o
Hazard por `country`, sem duplicar/derrubar `plant_uid`; `src/index/ccrs_report.py`
monta `CCRS_i,s = Hazard × age_factor × EventMultiplier` (produto, nunca
soma, uma coluna `ccrs_{gcm}` por GCM), junta as bandas de T4 e escreve o
relatório de % de capacidade (base computável V6, `capacity_sum` com assert
fail-loud) por `WaterRiskBand`/`HeatRiskBand` por país/cenário/GCM +
contingência (reaproveitada de `risk_bands.contingency_table`) + as
ressalvas de T2/T4 (fallback do wind, fração sem `commissioning_year`,
aviso de não-comparabilidade do HeatRiskBand). `src/processors/spei_processor.py`
calcula o termo de seca (SPEI-12 via Thornthwaite PET) e, desde
2026-09-04, entra no Hazard como terceiro termo aditivo independente
(`w_drought[bucket] * Tlog(spei_freq)`, item F fechado —
`docs/DECISIONS.md` "[2026-09-04] SPEI drought term added to Hazard",
`docs/memory/05-decisoes-tecnicas.md` item 18); `BUCKET_WEIGHTS` passou de
`(w_water, w_heat)` para `(w_water, w_heat, w_drought)` por bucket,
`FROZEN_BOUNDS` ganhou uma entrada `spei` por GCM. `src/index/monte_carlo.py`
implementa a sensibilidade Monte Carlo (item J, escopo aprovado): N=1000 ×
3 magnitudes, perturbando a razão água/calor do bucket thermal (drought
fixo), taxas de `age_factor` (coal/wind/hydro sobre faixas de literatura) e
`EventMultiplier k`, com `FROZEN_BOUNDS`/cortes de `risk_bands.py`
explicitamente fora de escopo — ver
`docs/memory/05-decisoes-tecnicas.md` item 19. `src/visualization/`
(`_common.py`, `data.py`, `maps.py`, `charts.py`, `tables.py`) gera as
figuras/tabelas do CCRS a partir de `src/index/*` em memória, nunca de CSV
cacheado; `ccrs_report.assemble_ccrs()` é o núcleo único de montagem
compartilhado entre `compute_ccrs()` (disco) e `data.py` (memória) — ver
item 20. Revisado em 2026-09-04 (rodada de review de Douglas): sem título
impresso em nenhuma figura, PDFs isolados em `pdf/`, fontes +20%,
categorias 1/3/10 geradas para os 3 cenários de água numa grade país×
cenário, HeatRiskBand reescrito (GFDL-ESM4 apenas, comparação com MIROC6
virou tabela), contingência WaterRiskBand×HeatRiskBand virou barras
empilhadas, Top-N breakdown virou pequeno múltiplo por bucket, EventMultiplier
por país virou tabela (gráfico removido), e cinco tabelas/figuras novas:
CCRS nacional agregado com IC do Monte Carlo, tabela de pesos com
proveniência, contribuição relativa dos termos de Hazard, e tabelas do
Monte Carlo por magnitude — ver item 21. Validação espacial EM-DAT contra
hazard (C6) foi investigada, aprovada e implementada
(`src/index/emdat_validation.py` + `src/visualization/emdat_validation.py`,
polígono admin-1 × termo de Hazard via Mann-Whitney U, diagnóstico, não
realimenta Hazard/CCRS) — ver item 22. 385 testes (2026-09-06; inclui SPEI,
Monte Carlo e as figuras 1–7). As verificações pós-dados V1–V6
(`ARCHITECTURE.md` Seção 9) estão **todas fechadas**; o CCRS substitui
SCI/NAES. A camada de índice está completa exceto relatórios per-country
adicionais.

2026-09-11: Fase 0 do plano de reconstrução GEAR v3
(`docs/rework/GEAR_v3_work_plan.md`) fechada — quatro verificações
bloqueantes (campo de resfriamento GEM, campo de retrofit GEM, classes
FWI/EFFIS, limiares HAZUS-MH, limiar de vento estrutural solar)
concluídas e confirmadas pelo autor. Só documentação/investigação, sem
mudança em `src/` — ver item 26 de
[05-decisoes-tecnicas.md](05-decisoes-tecnicas.md) e `docs/DECISIONS.md`.

2026-09-11: Fase 2.2 do plano GEAR v3 (Wildfire) adiada, não implementada —
sem RH diária no catálogo CDS para gfdl_esm4+miroc6×3-SSP, e o dataset
alternativo ETH Zurich FWI-CMIP6 não cobre GFDL-ESM4 e é estruturalmente
incompatível (indicadores anuais relativos a percentil, não classes EFFIS
absolutas). Tratado como trabalho futuro, mesmo padrão do SLR — valores
das 6 classes EFFIS preservados em
`docs/rework/GEAR_v3_methodology_nature_format.md` Seção 10.1. Ver item 29
de [05-decisoes-tecnicas.md](05-decisoes-tecnicas.md).

2026-09-11: Fase 2.1 do plano GEAR v3 fechada — novo
`src/processors/extreme_precipitation_processor.py` (dias/ano acima do P95
por pixel dos dias úmidos, Tier 3, reaproveita o `pr` já baixado para SPEI).
Não plugado a `risk_calculator.HAZARD_TERMS` ainda (aguarda gate de
correlação Fase 2.5 e Fase 3). 200 testes passando. Ver item 28 de
[05-decisoes-tecnicas.md](05-decisoes-tecnicas.md).

2026-09-11: Fase 1 do plano GEAR v3 fechada — `src/index/ccrs_calculator.py`
/ `ccrs_report.py` deletados (não depreciados), substituídos por
`src/index/risk_calculator.py` (Equação 1, `Risk_i,h`, por hazard, sem
`EventMultiplier`). `risk_bands.py`, `monte_carlo.py`, `main.py` e
`src/visualization/` agora quebrados (aguardam Fases 3/4/6/7) — quebra
esperada e documentada, não mascarada. 189 testes passando fora desses 4
arquivos. `sv`/`iv` (variabilidade da água) sinalizados como hazard em
aberto para a Fase 3. Ver item 27 de
[05-decisoes-tecnicas.md](05-decisoes-tecnicas.md).
