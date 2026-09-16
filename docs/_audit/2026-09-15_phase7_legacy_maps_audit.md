# Auditoria — como o GEAR antigo (pré-quebra) estruturava `data/outputs/maps/`

Auditoria de leitura, sem geração/modificação/exclusão de arquivo. Base para
reconstrução da Phase 7 (`docs/ARCHITECTURE.md` §11), não uma reconstrução em
si. Fontes: `src/visualization/_common.py`, `maps.py`, `charts.py`,
`diagrams.py`, `emdat_validation.py` (camada de visualização), `src/index/
emdat_validation.py`, `data/outputs/maps/` (inspeção visual real), `git show
a367672`.

---

## 1. Inventário de scripts geradores, por status

Todos os módulos de `src/visualization/` importam `_common.py`, que por sua
vez tem UM import quebrado: `from src.index.ccrs_calculator import BUCKETS`
(linha 58). `BUCKETS = ("hydro","thermal","wind","solar")` existe
identicamente em `src/index/risk_calculator.py` — corrigir só essa linha
destrava `_common.py` para todo mundo. A partir daí, cada módulo tem seu
próprio status conforme o que MAIS ele importa:

| Módulo | Figuras que gera | Agrupamento | Depende de `ccrs_report.py` (deletado) | Outros imports quebrados/retirados | **Status** |
|---|---|---|---|---|---|
| `src/visualization/_common.py` | (infra, sem figura própria) | — | Não | `BUCKETS` de `ccrs_calculator` → existe em `risk_calculator.py` | **Reaproveitável direto** (1 linha) |
| `src/visualization/diagrams.py` | `figure1_pipeline_overview` (1 arquivo, sem dado real — é um esquemático) | — | Não | Só usa `_common.fs`/`save_figure` | **Reaproveitável direto** (uma vez `_common` corrigido) |
| `src/visualization/maps.py` | 5 categorias (ver §1.1) | por categoria, ver abaixo | **Não** (usa `vdata.load_ccrs_final()`, que por sua vez SIM depende de `ccrs_report`/`ccrs_calculator` — ver `data.py`) | `from src.index.ccrs_calculator import WATER_TO_HEAT` → existe em `risk_calculator.py` (linha 337) | **Reaproveitável com adaptação**: o import próprio conserta fácil, mas todo dado de entrada (`vdata.load_ccrs_final`) vem de um pipeline que não existe mais (ver `data.py` abaixo) — a lógica de DESENHO é reaproveitável, a lógica de CARGA DE DADO não |
| `src/visualization/data.py` | (sem figura própria — carrega `ccrs_final.csv`/etc. para `maps.py`/`charts.py`) | — | **Sim, diretamente**: `vdata.load_ccrs_final()` espera as colunas que `ccrs_report.assemble_ccrs`/`attach_risk_bands` produziam (`ccrs_{gcm}`, `water_risk_band`, `heat_risk_band_{gcm}` — um score CCRS único blendado) | `from src.index import ccrs_calculator as ccrs` | **Bloqueado por dependência morta** — não é só o import; o SCHEMA de dado que ele espera (CCRS blendado água+calor por bucket) foi retirado pela Phase 1 em favor de `RiskBand_i,h` por hazard, nunca somado. Precisa reescrita, não fix de import |
| `src/visualization/charts.py` | 10 figuras/tabelas (ver §1.2) | por figura, ver abaixo | Indiretamente via `vdata` | `from src.index.ccrs_calculator import BUCKETS, PLANT_UID` (existem em `risk_calculator.py`) **+** `from src.index.risk_bands import HEAT_RISK_BANDS, WATER_RISK_BANDS` — **não existem mais em `risk_bands.py` atual** (confirmado por grep; só `PRIMARY_GCM` bate) | **Bloqueado por dependência morta** — mesmo duplamente: import de módulo retirado E de constantes que não têm equivalente 1:1 no schema novo (`WATER_RISK_BANDS`/`HEAT_RISK_BANDS` eram os 2 eixos blendados; o novo é `RiskBand_i,h` por hazard, até 5 por bucket) |
| `src/visualization/tables.py` | tabelas CSV, não mapas — fora do escopo desta auditoria (`data/outputs/tables/`, não `maps/`) | — | Sim (`ccrs_calculator.BUCKET_WEIGHTS`, `_PUBLISHED_WITHIN_WATER` — não localizados em nenhum módulo atual numa checagem rápida) | — | **Bloqueado por dependência morta** (fora do escopo `maps/`, citado por completude) |
| `src/visualization/emdat_validation.py` (viz) | `emdat_spatial_validation.png` | 1 arquivo combinado | Não diretamente | Usa `src.index.emdat_validation` (index layer), que TEM import quebrado (`ccrs.raster_path`) — mas `raster_path` existe idêntico em `risk_calculator.py` | **Reaproveitável com adaptação leve** (1 linha no módulo de índice, assinatura idêntica) |
| `src/index/monte_carlo.py` | (não gera figura, mas `charts.py`/`main.py` dependem dele) | — | Não diretamente, mas lê `ccrs_calculator.FROZEN_BOUNDS` (objeto do módulo retirado) em várias linhas (36, 76, 88, 319, 363, 716-722) | `from src.index import ccrs_calculator as ccrs` | **Bloqueado por dependência morta** — já documentado em `docs/DECISIONS.md` como "dead code today" (linha ~574-581) |
| `src/main.py` | orquestra tudo acima | — | **Sim, diretamente**: `ccrs_report.assemble_ccrs`/`attach_risk_bands`/`compute_water_band_shares`/`compute_heat_band_shares`/`build_summary` (5 chamadas), módulo inteiro deletado, sem substituto | `ccrs_calculator.compute_hazard_by_gcm`, `WATER_SCENARIOS` | **Bloqueado por dependência morta** — não é fixável por rename de import; a etapa T5 inteira do pipeline (docstring do próprio arquivo) não tem mais implementação em lugar nenhum |

**Confirmado por diff real** (`git show a367672 --stat`): o commit
`a367672` (2026-09-11, "Start GEAR v3 rework...") deletou **só**
`src/index/ccrs_calculator.py` (725 linhas) e `src/index/ccrs_report.py`
(490 linhas) + seus dois arquivos de teste — não tocou em `main.py`,
`src/visualization/*`, `monte_carlo.py` ou `emdat_validation.py`. A própria
mensagem do commit declara isso explicitamente: *"Downstream modules that
depended on the retired combined Hazard_i,s (risk_bands.py, monte_carlo.py,
emdat_validation.py, main.py, src/visualization/) are left broken on
purpose -- fixing them requires methodology not yet decided (Phase
3/4/6/7) and is out of scope here."* `risk_bands.py` foi corrigido depois
(Phase 3.2, 2026-09-12) e hoje importa limpo; os outros cinco nunca foram
revisitados.

### 1.1 `maps.py` — as 5 categorias e seu agrupamento real

| Categoria | Função | Agrupamento | Saída |
|---|---|---|---|
| 1 / Figure 5 (overview, bolha colorida por bucket) | `plot_figure5_ccrs_overview` | **1 figura por `water_scenario` × `gcm`**, países lado a lado (via `_render_country_row_figure`) | `combined/figure5_ccrs_overview_{scenario}_{gcm}.png` |
| 1-secundária (PES contínuo) | `plot_ccrs_asset_level_pes_map` | 1 figura fixa (PES), países lado a lado | `combined/secondary/ccrs_asset_level_pes_{gcm}.png` |
| 2 (delta de cenário) | `plot_ccrs_scenario_delta_map` | **dois modos**: `combined=True` → 1 figura, países lado a lado, colorbar diverging compartilhada (Supplementary); `combined=False` (default) → **1 figura POR país** | `combined/secondary/ccrs_scenario_delta_...png` OU `{country}/ccrs_scenario_delta_...png` |
| 3 (WaterRiskBand) | `plot_water_risk_band_map` | **1 figura por `water_scenario`**, países lado a lado | `combined/water_risk_band_{scenario}.png` |
| 4 (HeatRiskBand) | `plot_heat_risk_band_map` | **1 figura por `heat_scenario` (ssp126/370/585)**, países lado a lado, GCM fixo (`PRIMARY_GCM`) | `combined/heat_risk_band_{ssp}.png` |
| 4-secundária (worst-case) | `plot_worst_case_risk_band_map` | 1 figura por cenário, Supplementary | `combined/secondary/worst_case_risk_band_{gcm}_{scenario}.png` |
| 10 (base computável) | `plot_computable_base_map` | **1 figura por `water_scenario`**, países lado a lado | `combined/computable_base_{scenario}.png` |

Ou seja: **4 das 5 categorias de mapa geográfico já usam "1 figura por
cenário, países como subplots"** como padrão-base — a única exceção
estrutural é a categoria 2 (delta), que oferece os dois modos, e o modo
per-country é o efetivamente chamado por `main.py`/`_generate_figures` hoje
(por isso `Brazil/`, `India/`, `Portugal/` têm `ccrs_scenario_delta_*.png`
individuais, não um `combined/`).

### 1.2 `charts.py` — 10 figuras (referência rápida, fora do escopo `maps/` mas citadas em `data/outputs/maps/{country,combined,combined/secondary}`)

`water_heat_combined_risk_bars` e `top_n_ccrs_breakdown_by_bucket`: **1
figura por país** (`OUT_DIR / country / ...`) — os únicos dois arquivos de
`charts.py` que caem nas pastas `Brazil/`, `India/`, `Portugal/`. Todas as
outras 8 vão para `combined/` ou `combined/secondary/` (agregado, sem
variante per-country). Todas bloqueadas por `HEAT_RISK_BANDS`/
`WATER_RISK_BANDS` não existirem mais, além do import de `ccrs_calculator`.

---

## 2. `draw_country_boundary` original — ADM0 vs ADM1, disputa, disclaimer

Lógica exata em `src/visualization/_common.py:238-262` (função
`draw_country_boundary`) + `197-235` (boundary loading/disclaimer):

1. **ADM0** (`get_country_geometry(country)`, de
   `boundaries_downloader.py`) desenha o contorno nacional externo —
   preenchimento `#f5f5f0`, borda preta 0.6pt. Igual em todo país, sem
   distinção de disputa (GADM ADM0 não carrega essa informação).
2. **ADM1** (`load_admin1_boundaries(country)`, camada `ADM_ADM_1` do
   geopackage GADM 4.1) é carregado À PARTE, sempre, para todo país — não é
   opcional nem específico da Índia. `country_has_disputed_admin1(country)`
   testa se ALGUM `GID_1` começa com `"Z"` (convenção GADM para território
   disputado — só a Índia tem isso neste estudo: Jammu & Caxemira, partes
   de Himachal Pradesh/Uttarakhand/Arunachal Pradesh).
3. **Tratamento visual da disputa**: os polígonos ADM1 disputados são
   preenchidos com a MESMA cor do resto do país (nunca deixados vazios —
   "would visually read as excluded", comentário literal do código), mas
   com contorno **tracejado cinza-claro** (`DISPUTED_LINE_COLOR="#bbbbbb"`,
   `DISPUTED_LINE_STYLE="--"`), visualmente distinto das linhas de estado
   normais (cinza `#999999`, sólida, 0.35pt). Confirmado visualmente em
   `data/outputs/maps/combined/water_risk_band_pes.png` (painel Índia): há
   uma área destacada por linha tracejada no norte e no nordeste do país.
4. **Disclaimer de rodapé** (`footer_with_gadm_disclaimer`/
   `GADM_DISCLAIMER_TEXT = "Administrative boundaries per GADM 4.1;
   boundary representation does not imply endorsement."`): a função só
   anexa o texto **se `country_has_disputed_admin1` for verdadeiro para
   pelo menos um dos países da figura** — condição automática, não
   hardcoded para "Índia" por nome. **Porém**: o próprio `maps.py`
   (docstring, "Correction 2", 2026-09-05/06) registra que Douglas **removeu
   esse rodapé de toda figura do artigo como decisão definitiva** em
   2026-09-06 — a função ainda existe e funcionaria, mas nenhuma chamada em
   `maps.py` a invoca mais. Ou seja: no estado final do pipeline antigo, o
   tratamento cartográfico (traço tracejado) ficou, o texto de disclaimer
   saiu.

Isto é relevante para a decisão pendente (task anterior) sobre `results_draft/`:
o próprio autor já tinha decidido, para o pipeline de produção, "traço
tracejado sim, texto de disclaimer não" — não é uma recomendação minha, é o
registro do que já foi decidido antes. Não estou reabrindo nem aplicando essa
decisão a `results_draft/` aqui — só documentando que ela existe, como pedido.

---

## 3. Comparação visual objetiva — `maps/` antigo vs `results_draft/` atual

Amostra inspecionada: `data/outputs/maps/combined/water_risk_band_pes.png`
(antigo) vs `data/outputs/results_draft/03_riskband_asset_map/
riskband_map_brazil_ws.png` e `07_sobol_sensitivity/sobol_sensitivity.png`
(novo, já vistos nesta sessão).

| Aspecto | Antigo (`maps.py`) | Novo (`results_draft/`) |
|---|---|---|
| Paleta de banda | `viridis` sequencial (5 tons contínuos, perceptualmente uniforme) para Water/Heat RiskBand | Paleta categórica fixa manual (`#2a9d8f`/`#e9c46a`/`#f4a261`/`#e63946`) — qualitativa, não perceptualmente ordenada |
| Tamanho do marcador | `sqrt(capacity_mw)` sempre (`marker_sizes`) — tamanho varia visivelmente por planta | Fixo (`s=18`/`s=16`) nos itens 03/13; só 04/05 usam tamanho por capacidade |
| Fronteira administrativa | ADM0 + ADM1 (linhas de estado internas visíveis) | Só ADM0 (contorno externo único, sem subdivisão interna) |
| Território disputado | Tracejado cinza distinto (ADM1 "Z"-prefixado) | Nenhum tratamento (ADM1 não é carregado) |
| Rosa dos ventos | Sim, por painel, canto superior direito, tamanho fixo em polegadas | Ausente |
| Eixos | Tick labels lat/lon visíveis, rótulos "Latitude"/"Longitude" | `ax.set_xticks([])`/`set_yticks([])` — sem eixo, sem rótulo |
| Título de painel | Negrito, "`País (Power Plants=N)`" via `panel_title` | Texto simples via `ax.set_title(ssp_label)` — não reporta N de plantas no painel |
| Legenda | Uma legenda compartilhada por figura, abaixo, sem moldura (`frameon=False`) | Legenda compartilhada, mas combina cor (banda) + forma (bucket) na mesma linha — mais densa |
| Layout multi-painel | `constrained_layout=True` + largura proporcional ao bbox real do país (`aspect_ratio_width`) | Largura fixa por país (`aspect_ratio_width` reimplementado, mesma fórmula, mas sem `constrained_layout`) |
| Resolução | `dpi=200`, PNG+PDF (`save_figure`) | `dpi=200`, só PNG (sem PDF) |
| Escala de cor contínua (Sobol, Risk_i,h) | N/A neste módulo (usa `viridis` em `charts.py` para outras figuras) | `viridis` usado corretamente em `item05` (Risk_i,h) — aqui a paleta JÁ bate com a convenção antiga |

Resumo objetivo: a diferença dominante não é resolução nem nitidez (ambos
200 dpi, ambos matplotlib puro) — é **densidade de informação cartográfica**
(ADM1 + disputa + rosa dos ventos + eixo lat/lon + N de plantas no título,
todos ausentes no novo) e **paleta** (sequencial perceptual vs categórica
manual para bandas ordinais).

---

## 4. Lógica de consolidação por cenário — já existe, não precisa ser criada do zero

Confirmado no código: `src/visualization/maps.py::_render_country_row_figure`
(linhas 138-161) é exatamente essa função — recebe uma lista de países, uma
função de desenho por painel, uma lista de handles de legenda, e um
`out_path`; monta 1 figura com N painéis lado a lado (largura proporcional
ao bbox real de cada país via `aspect_ratio_width`), legenda compartilhada
embaixo, rosa dos ventos por painel adicionada por último. Usada por 4 das 5
categorias de mapa geográfico (Figure 5/overview, WaterRiskBand,
HeatRiskBand, computable-base) — cada uma chamada uma vez por cenário
(`water_scenario` ou `heat_scenario`/SSP conforme a categoria). Categoria 2
(scenario delta) tem sua própria implementação inline equivalente (não
reusa `_render_country_row_figure` literalmente, mas replica o mesmo padrão
manualmente) quando chamada com `combined=True`.

**Esta função em si (`_render_country_row_figure`) não depende de
`ccrs_report`/`ccrs_calculator`** — só de `_common.py` (1 import quebrado,
trivial) e de um DataFrame já pronto (`final`) que o CALLER precisa montar.
A lógica de composição/consolidação é diretamente reaproveitável; o que
falta é a fonte de dado (`vdata.load_ccrs_final`, hoje dependente do schema
CCRS retirado) — exatamente o ponto já identificado na tabela do §1.

---

## Conclusão por item do critério de conclusão

- **Cada script gerador de `data/outputs/maps/` tem status claro**: ver
  tabela §1 — `_common.py` e `diagrams.py` reaproveitáveis diretos;
  `maps.py` e `emdat_validation.py` (viz) reaproveitáveis com adaptação
  (lógica de desenho ok, fonte de dado ou 1 import precisam de trabalho);
  `data.py`, `charts.py`, `tables.py`, `monte_carlo.py`, `main.py`
  bloqueados por dependência morta (schema CCRS blendado retirado, sem
  substituto ainda escrito).
- **Lógica de consolidação por cenário**: confirmada EXISTENTE
  (`_render_country_row_figure`, `maps.py:138-161`), usada por 4 das 5
  categorias de mapa — não precisa ser criada do zero, precisa ser
  realimentada com uma fonte de dado compatível com o schema `RiskBand_i,h`/
  `PSAE_i` atual.

Nenhum arquivo foi gerado, modificado ou apagado nesta auditoria.
