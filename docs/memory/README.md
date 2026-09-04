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
`src/config.py`, 9 downloaders (inclui `cds_precipitation_downloader` para
um termo de SPEI futuro), 3 processors de clima (calor, água, variabilidade
sv/iv). Camada de índice: `src/index/ccrs_calculator.py` calcula o termo
`Hazard_{i,s}` (transformação global por termo com bounds congelados + trava
de regressão, pesos água/calor por bucket, GFDL-ESM4 e MIROC6 separados);
`src/index/risk_bands.py` calcula WaterRiskBand (cortes absolutos WRI fixos)
e HeatRiskBand (percentis p25/p75/p95 de GFDL-ESM4) como colunas separadas,
nunca um score único; `src/index/age_factor.py` calcula o multiplicador de
idade `≥ 1` (`age_factor = 2 - clip(retention(age), 0, 1)` ∈ `[1,2]` —
convenção confirmada como definitiva pelo autor, item D fechado,
`docs/DECISIONS.md` 2026-09-04; coal com overhaul assumido dente-de-serra,
wind uniforme 0,4%/ano sem `CF_initial`) e multiplica o Hazard por
`plant_uid`. 189 testes. As
verificações pós-dados V1–V6 (`ARCHITECTURE.md` Seção 9) estão **todas
fechadas**; o CCRS substitui SCI/NAES. Falta a montagem do `CCRS_i,s`
(Hazard × age_factor × EventMultiplier), `EventMultiplier`, Monte Carlo e
relatórios per-country.
