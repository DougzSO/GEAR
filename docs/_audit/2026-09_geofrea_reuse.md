# Auditoria de fatos — dados CMIP6 e reaproveitamento GEAR→GeoFREA

Data: 2026-09-15. Escopo: leitura somente (`src/`, `data/`, `docs/`), mais três consultas de rede real (documentadas na Seção 5) contra a fonte usada pelo pipeline (Copernicus CDS) e, como checagem adicional, o índice ESGF. Objetivo: fechar D5 e D15 com dado verificado. Nenhum commit foi feito.

Anexos consultados: `CLAUDE.md`, `docs/LIMITATIONS.md`, `docs/DECISIONS.md` (5002 linhas — consultado por seções relevantes, não lido linha a linha), mais `src/config.py`, `src/index/hazard_scope.py`, e inspeção direta de `data/raw/climate/`.

**⚠️ Ponto a validar — identificação de "D5" e "D15"**: busca exaustiva em `docs/` (`ARCHITECTURE.md`, `LIMITATIONS.md`, `DECISIONS.md`, `INVENTORY.md`, `PROJECT_STATE_SNAPSHOT.md`, `memory/`, `rework/`) e no restante do repositório não encontrou nenhum rótulo literal `D5` ou `D15` — não existe uma numeração `D<n>` de decisões/itens neste projeto (os únicos esquemas de numeração encontrados são "spec item {F,G,I,J}", "Phase 6 open item {1..6}", e as entradas datadas de `DECISIONS.md`/`LIMITATIONS.md`). Não assumi a que isso se refere — prossegui com o conteúdo literal das Ações 2-5, que são autocontidas e não dependem de identificar D5/D15. Se "D5"/"D15" vierem de um documento externo a este repositório (ex. plano de trabalho do GeoFREA ou anotação pessoal), a correspondência com o conteúdo abaixo precisa ser confirmada pelo autor.

---

## 1. Contexto

Este documento é produzido **no GEAR** (`GEAR_framework/docs/_audit/`), avaliando o que da camada de aquisição/processamento climático deste projeto é reaproveitável para o GeoFREA (projeto irmão, pipeline de aptidão de sítios renováveis). Os dois projetos são independentes; nada aqui foi escrito em `GeoFREA/`.

---

## 2. Dados CMIP6 baixados

Fonte de verdade: `src/config.py` (configuração) cruzado com inspeção direta de `data/raw/climate/` (o que de fato foi baixado) e um `provenance.json` real (metadado de proveniência gravado pelo próprio serviço de subsetting).

| Campo | Valor |
|---|---|
| **GCMs (`CMIP6_SOURCE_ID_CDS`, `config.py:218-221`)** | `gfdl_esm4` (GFDL-ESM4, NOAA-GFDL) e `miroc6` (MIROC6) — lista, não escalar; GFDL-ESM4 deve ficar primeiro (grade de referência para os rasters de água). MIROC6 adicionado por decisão V4 fechada (maior divergência estrutural entre os candidatos com cobertura ssp126/ssp370/ssp585 completa no catálogo CDS). |
| **SSPs (`CMIP6_SCENARIOS`, `config.py:184`)** | `ssp126`, `ssp585`, `ssp370` (SSP3-7.0 adicionado como cenário intermediário; token CDS "experiment" = `ssp1_2_6`/`ssp5_8_5`/`ssp3_7_0`, `config.py:187-191`). |
| **Variáveis baixadas** | `tasmax` (temperatura máxima diária — camada de calor extremo, `cds_tasmax_downloader.py`); `pr` e `tas` (precipitação e temperatura média diárias — insumos do SPEI/seca, `cds_precipitation_downloader.py`, `config.py:236-239`). **Nenhuma variável `rsds` ou `sfcWind` foi baixada como CMIP6** — vento é tratado à parte via ERA5 histórico (ver Seção 4/`LIMITATIONS.md` "Extreme Wind: ERA5 historical baseline, scenario-invariant by design"), e não há camada solar-irradiância (`rsds`) no conjunto de hazards do GEAR. |
| **Frequência** | Diária (`day`), confirmado no ID do dataset original (`c3s-cmip6.ScenarioMIP.NOAA-GFDL.GFDL-ESM4.ssp126.r1i1p1f1.day.tasmax.gr1.v20180701`, `provenance.json` real inspecionado). O SPEI é depois agregado mensalmente dentro de `spei_processor.py` (`_monthly_aggregate`), mas o dado bruto baixado é diário. |
| **Período** | `2041-01-01` a `2070-12-31` (`CMIP6_FUTURE_PERIOD`, `config.py:223` — "a janela 2050"), confirmado no `provenance.json` (`roocs:time`: `"2041/2070"`). **Nenhum período `historical` foi baixado como CMIP6** — confirmado por ausência de qualquer diretório `historical/` em `data/raw/climate/cds_tasmax/` ou `cds_spei/` (só `ssp126`/`ssp370`/`ssp585` existem sob cada país/modelo). |
| **Resolução** | Grade nativa do GCM preservada no arquivo bruto (~1° lat × ~1.25° lon para a grade `gr1` do GFDL-ESM4, per comentário em `config.py:141-143`; resolução nativa exata da grade `gn` do MIROC6 **não documentada no repositório** — não verificado, não estimado aqui). Reamostrada para `RESOLUTION_TARGET_DEG = 0.008333°` (~1 km nominal, `config.py:156`) via `cds_tasmax_downloader.py::_resample_to_1km()`/`_target_grid()`. |
| **Fonte** | Copernicus Climate Data Store (CDS), dataset `projections-cmip6`, via serviço de subsetting ROOCS/Rook (`rook_v1.4.0`) + `clisops v0.18.1` — confirmado literalmente no `provenance.json` (`agent`/`wasAttributedTo`). Acesso via `cdsapi` (biblioteca cliente padrão da Copernicus). |
| **Cobertura confirmada em disco** | 3 países (Brazil/Portugal/India) × 2 GCMs × 3 SSPs = 18 combinações completas para `tasmax`; mesma matriz × 2 variáveis (`pr`,`tas`) = 36 combinações completas para o insumo do SPEI — confirmado por `find` direto em `data/raw/climate/{cds_tasmax,cds_spei}/`, todas com `.downloaded` presente. |

---

## 3. Processadores e alinhamento reaproveitáveis sem dependência de usina (`plant_uid`/GEM)

Busca direta (`grep -c "plant_uid\|GEM\b\|gem_\|Global Integrated Power"`) em todo `src/processors/*.py` e `src/downloaders/*.py`: **todos os arquivos retornaram zero ocorrências, exceto `src/downloaders/assets_validator.py`** (25 ocorrências — esse é, por definição, o módulo de validação do ativo/usina, não um candidato a reaproveitamento sem dependência de planta). Ou seja, toda a camada de aquisição/processamento climático e de contorno geográfico é, estruturalmente, independente de dado de usina — opera só em país/raster/grade.

### 3.1 Alinhamento de grade (arquivo:função)

| Arquivo | Função | Papel |
|---|---|---|
| `src/processors/_common.py` | `_load_reference_grid(country, model=None)` | Carrega a grade de referência (GFDL-ESM4/ssp126, primeiro modelo da lista) sobre a qual todos os rasters de água são rasterizados. |
| `src/processors/_common.py` | `grid_signature(da)` | Assinatura (shape/transform/CRS) de um `xr.DataArray`, usada para checagem de consistência. |
| `src/processors/_common.py` | `assert_consistent_grid(...)` | Levanta `GridMismatchError` se dois rasters não compartilham a mesma grade — guard de integridade reaproveitável tal como está. |
| `src/processors/_common.py` | `load_country_rasters(...)` | Carrega múltiplos rasters de um país já alinhados. |
| `src/downloaders/cds_tasmax_downloader.py` | `_target_grid(country)` | Define a grade-alvo de reamostragem (1 km) por país. |
| `src/downloaders/cds_tasmax_downloader.py` | `_resample_to_1km(da, country)` | Reamostra o raster CMIP6 nativo para a grade-alvo. |
| `src/downloaders/cds_tasmax_downloader.py` | `_climate_bounds(country)` / `_country_area(country)` | Resolve a bbox de download por país (GADM ∪ `COUNTRY_BBOX_FALLBACK`). |
| `src/downloaders/boundaries_downloader.py` | `get_country_geometry(country)` / `get_country_bounds(country)` | Geometria/bbox do país (GADM 4.1), com filtro de "mainland only" (`_apply_mainland_filter`) — equivalente conceitual ao `load_mainland_boundary()` do GeoFREA. |
| `src/downloaders/boundaries_downloader.py` | `download_country_boundary(country, overwrite=False)` | Fetch real do limite GADM por país. |

### 3.2 Processadores de hazard reaproveitáveis (país×modelo×cenário, sem usina)

| Arquivo | Funções-chave | Hazard |
|---|---|---|
| `src/processors/extreme_precipitation_processor.py` | `compute_extreme_precip_days`, `process_country_model_scenario`, `process_all_countries` | Extreme Precipitation (Tier 3, percentil P95, ETCCDI). |
| `src/processors/extreme_wind_processor.py` | `compute_annual_max_for_year`, `compute_mean_annual_max_gust`, `process_country`, `process_all_countries` | Extreme Wind (ERA5, não CMIP6 — ver Seção 4). |
| `src/processors/heat_stress_processor.py` | `process_country_model_scenario`, `process_all_countries` | Extreme Heat (dias acima de 40°C, `tasmax`). |
| `src/processors/spei_processor.py` | `_thornthwaite_pet`, `_spei_from_water_balance`, `compute_drought_frequency`, `process_country_model_scenario` | SPEI/seca (Thornthwaite PET, log-logística). |
| `src/processors/water_stress_processor.py` | `load_aqueduct_basins`, `rasterize_scenario`, `process_country_scenario` | Water Stress (WRI Aqueduct). |
| `src/processors/water_variability_processor.py` | `load_aqueduct_basins`, `rasterize_scenario`, `process_country_scenario` | Water Variability (sv/iv, WRI Aqueduct). |
| `src/downloaders/climate_downloader.py` | `run_climate_pipeline(...)` | Orquestrador único da camada climática — itera país×modelo×cenário, sem nenhuma referência a usina/GEM. |

Todos os nove arquivos acima (mais `cds_precipitation_downloader.py`, `era5_wind_downloader.py`, `cds_tasmax_downloader.py`, `coastline_downloader.py`, `rivers_downloader.py`, `aqueduct_downloader.py`, `emdat_downloader.py`, `ibtracs_downloader.py`) operam em granularidade país/raster — nenhum toma `plant_uid`, DataFrame de usinas, ou qualquer campo do GEM como entrada.

---

## 4. Hazards de solar e eólica em `H_b` (final) e variação por SSP

Fonte: `src/index/hazard_scope.py::APPLICABLE_HAZARDS` (linha 107-112, "Methods Section 3 table" — a definição de escopo final, não um rascunho).

```python
APPLICABLE_HAZARDS = {
    "hydro":   ("ws", "spei", "precip", "sv", "iv"),
    "thermal": ("ws", "heat", "precip"),
    "wind":    ("wind",),
    "solar":   ("heat", "precip", "wind"),
}
```

| Bucket | H_b (hazards) | Varia por SSP? |
|---|---|---|
| **Wind** | `wind` (Extreme Wind, mecanismo de corte por velocidade de turbina IEC) — único hazard do bucket | **Não.** Fonte é ERA5 reanálise histórica (1991-2020), não uma projeção CMIP6/SSP — `Risk_i,h`/RiskBand/contribuição ao PSAE é idêntico nas três colunas de SSP, por design (`docs/LIMITATIONS.md`, "Extreme Wind: ERA5 historical baseline, scenario-invariant by design" — "settled epistemic position, not a placeholder"). |
| **Solar** | `heat` (perda de eficiência do PV), `precip` (alagamento de subestação, mecanismo passou pelo correlation-gate), `wind` (uplift estrutural do tracker, percentil de rajada ERA5, Tier 3 final) | **Parcialmente.** `heat` e `precip` são derivados de CMIP6 (`tasmax`/`pr`, `heat_stress_processor.py`/`extreme_precipitation_processor.py`), então variam pelos 3 SSPs configurados. `wind`, dentro do bucket Solar, usa a **mesma fonte ERA5 histórica** do bucket Wind — **não varia por SSP**, pelo mesmo motivo listado acima. |

**Nuance importante não coberta pela pergunta literal, mas necessária para "fechar com dado verificado"**: `wind` está no `H_b` de ambos os buckets **por definição de escopo** (a tabela acima), mas o `Risk_i,h` contínuo (Equação 1) para `wind` **ainda não está integrado** em `src/index/risk_calculator.py::HAZARD_TERMS` — bloqueado, segundo `docs/LIMITATIONS.md` (entradas de 2026-09-13/2026-09-14), não por falta de dado (a aquisição ERA5 gust está completa para os 3 países, 90/90 arquivos), mas porque a redução `compute_mean_annual_max_gust()` para um raster processado por país ainda não foi rodada. `src/index/hazard_scope.py::PENDING_RISK_I_H_HAZARDS["wind"]` é o registro em código desse gap. Ou seja: `wind` pertence ao `H_b` final (escopo fechado), mas **ainda não produz um valor de `Risk_i,h` real para nenhum país** — um estado diferente de "não varia por SSP", que não deve ser confundido com ele.

---

## 5. GCMs com `rsds`, `tas` e `sfcWind` mensais em historical + 3 SSPs — verificação de rede real

Havia acesso de rede nesta sessão. Verificação feita em **duas fontes independentes**, ambas em 2026-09-15:

**Fonte primária — a mesma usada pelo pipeline (Copernicus CDS, dataset `projections-cmip6`)**: obtido diretamente o arquivo `constraints.json` real que o formulário/cliente `cdsapi` do CDS usa para validar combinações de requisição (`https://cds.climate.copernicus.eu/api/catalogue/v1/collections/projections-cmip6` → link `rel:"constraints"` → objeto CCI2, 540.246 bytes, HTTP 200, sem autenticação). Mapeamento de nomes curtos para os tokens CDS confirmado no próprio arquivo: `rsds` → `surface_downwelling_shortwave_radiation`; `tas` → `near_surface_air_temperature`; `sfcWind` → `near_surface_wind_speed`. Para cada bloco de restrição com `temporal_resolution` incluindo `"monthly"`, verificado se `model` inclui `gfdl_esm4`/`miroc6` e `experiment` inclui `historical`/`ssp1_2_6`/`ssp3_7_0`/`ssp5_8_5`:

| GCM \ Variável (mensal) | `historical` | `ssp126` | `ssp370` | `ssp585` |
|---|---|---|---|---|
| **GFDL-ESM4 — rsds** | disponível | disponível | disponível | disponível |
| **GFDL-ESM4 — tas** | disponível | disponível | disponível | disponível |
| **GFDL-ESM4 — sfcWind** | disponível | disponível | disponível | disponível |
| **MIROC6 — rsds** | disponível | disponível | disponível | disponível |
| **MIROC6 — tas** | disponível | disponível | disponível | disponível |
| **MIROC6 — sfcWind** | disponível | disponível | disponível | disponível |

**Todas as 24 células (2 GCMs × 3 variáveis × 4 experimentos) vieram `disponível`** — nenhuma `indisponível`, nenhuma `não verificado`.

**Fonte secundária, cruzada (ESGF, índice federado que hospeda o CMIP6 original)**: consulta à API de busca ESGF (`esgf-node.llnl.gov/esg-search`, redireciona para `esgf-node.ornl.gov`) para as mesmas 24 combinações (`project=CMIP6&source_id=<gcm>&variable_id=<var>&frequency=mon&experiment_id=<exp>`), retornando `numFound` > 0 em todas as 24 consultas (GFDL-ESM4: 4-12 datasets por combinação; MIROC6: 113-186 por combinação, refletindo múltiplas realizações/versões catalogadas). Confirma independentemente a mesma conclusão da fonte primária.

**Ressalvas explícitas, sem estimar além do verificado**:
- O `constraints.json` do CDS confirma que a **combinação é uma requisição válida no catálogo** — não confirma que uma requisição real completaria com sucesso hoje (o precedente já documentado em `docs/LIMITATIONS.md`, "Wildfire (FWI/EFFIS) deferred", mostra que uma combinação pode aparecer válida no catálogo e ainda assim ter problemas de cobertura real por variante/realização quando a requisição de fato é submetida — humidade relativa diária foi o caso lá, não este).
- A verificação acima checou disponibilidade em nível de `model`/`experiment`/`variable`/`temporal_resolution` — **não** verificou se a variante de realização específica já usada pelo GEAR (`r1i1p1f1`, confirmada no `provenance.json` de `tasmax`) é exatamente a mesma que carrega `rsds`/`sfcWind` mensal para os 24 pares acima; os blocos de `constraints.json` não expõem `member_id` no nível de granularidade consultado aqui. Este ponto específico fica **não verificado**.
- `rsds` e `sfcWind` **não são hazards do GEAR hoje** (Seção 4) — esta verificação é puramente prospectiva, para informar uma decisão do GeoFREA (ou de uma extensão futura do próprio GEAR) sobre viabilidade de dado, não uma confirmação de que o GEAR já usa essas variáveis.

---

**Critério de conclusão**: tabela GCM × SSP × variável (Seção 5) com cada célula em disponível/indisponível/não verificado — preenchida, 24/24 células `disponível`, nenhuma célula deixada em branco. Único arquivo criado é este (`docs/_audit/2026-09_geofrea_reuse.md`, dentro do GEAR); nenhum arquivo de `src/`, `data/` ou `docs/` (fora de `docs/_audit/`) foi modificado, e nada foi escrito em `GeoFREA/`.
