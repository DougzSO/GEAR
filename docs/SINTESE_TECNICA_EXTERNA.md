# GEAR Framework — Síntese Técnica (para reconstrução do pipeline)

## 1. Fluxo de dados ponta a ponta

`variável climática → RiskBand_{i,h} → PSAE_i → Risk_{i,h}` (as duas cadeias são independentes, nunca misturadas [doc: DECISIONS#2026-09-14 "Phase 6 closure", confirmado por Sobol ΣS1]).

- **Rasters brutos** (Aqueduct água via GEE; CDS CMIP6 `tasmax`/`pr` GFDL-ESM4+MIROC6; SPEI-12; ERA5 gust 1991-2020) → processadores em `src/processors/` → `data/processed/climate/*.tif`.
- **Risk_{i,h}** = `Hazard_{i,h} × Exposure_i × Vulnerability_i` (Exposure=capacidade, Vulnerability=`age_factor`), calculado por hazard, nunca somado entre hazards [código: risk_calculator.py:673 `risk_i_h`, :702 `compute_risk_by_hazard`]. `age_factor = 2 - clip(retention(age),0,1)` [código: age_factor.py:229 `age_factor`, :155 `_to_multiplier`]. Bounds Min-Max globais congelados em `FROZEN_BOUNDS` (heat/spei por GCM) [doc: DECISIONS#"CCRS global Min-Max bounds"]. Saída: [output: data/outputs/tables/risk_by_hazard.csv, 78.497.736 bytes, mod. 2026-09-16 07:12:56 -03].
- **RiskBand_{i,h}**: classificação em bandas (Tier1 absoluto WRI para água; Tier3 percentil amostral para heat/precip/wind/spei) [código: risk_bands.py:378 `classify_hazard`, :330 `percentile_band_cuts`, :490 `compute_risk_bands`]. Saída: [output: data/outputs/tables/risk_bands.csv, mod. 2026-09-16 07:13:23 -03].
- **PSAE_i**: agregação por bucket a partir de RiskBand, `psae_complete=False → NaN` em todo agregado (case completo) [código: psae.py:197 `compute_psae`, :115 `classify_psae_fraction`; doc: DECISIONS#"Phase 4 (PSAE) input mapping... CLOSED, complete-case" 2026-09-14]. Saída: [output: data/outputs/tables/psae.csv, mod. 2026-09-16 07:16:31 -03].
- **Correlation gate** (pré-requisito de `Hazard_{i,h}`, exclui termo redundante por bucket, `|r|≥0.80`) [código: correlation_gate.py:181 `GATE_THRESHOLD=0.80`, :449 `run_gate`]. Saída: [output: data/outputs/tables/correlation_gate.csv, mod. 2026-09-16 11:54:35 -03].
- **EventMultiplier_c** (país, EM-DAT) [código: event_multiplier.py:129 `compute_event_multipliers`] e **contextual validators** (EM-DAT broad-impact + IBTrACS physical-occurrence, camada secundária/screening, não entra em Risk_{i,h}) [código: contextual_validators.py:309 `compute_broad_impact_validation`, :409 `compute_physical_occurrence_validation`]. Saída: [output: data/outputs/tables/contextual_validators.csv, mod. 2026-09-15 07:34:28 -03].
- **Sensibilidade**: Sobol (`sobol_sensitivity.py:354 run_validation`) e Monte Carlo geral (`general_mc.py:163 run_n`, :222 `run_convergence`) sobre as duas cadeias, usando `sensitivity_recompute.py` só como cache de raster (não produz índice) [doc: LIMITATIONS#2026-09-16 "sensitivity_recompute.py ... não é um resultado de sensibilidade"]. Saídas: [output: data/outputs/tables/phase6_sobol_full_n1024.json, mod. 2026-09-15 13:06:27 -03] e [output: data/outputs/tables/phase6_general_mc_convergence.json, mod. 2026-09-15 16:26:29 -03].
- **results_draft/**: 16 itens numerados (`src/reporting/results_draft/item01…16*.py` + `run_all.py`), consumindo os CSVs acima, gravando em `data/outputs/results_draft/{tables,maps,other}/` [output: data/outputs/results_draft/MANIFEST.md, mod. 2026-09-16 11:56].

## 2. Decisões vigentes (Status: active, DECISIONS.md)

86 entradas datadas no total; 78 marcadas `active` (5 explicitamente `superseded`, demais parciais/abertas — ver §5). Amostra com impacto direto nos resultados principais:

- **Correlation gate, |r|≥0.80** (2026-09-12): regra de exclusão por redundância entre termos de hazard. Implementado [código: correlation_gate.py:181]. Afeta resultado principal (define quais termos entram em `Hazard_{i,h}`). [doc: DECISIONS#"GEAR v3 Phase 2.5: pre-registered correlation-gate tie-breaker rule"]
- **age_factor ≥1, `2−retention(age)`, curva coal sawtooth 5 anos/70%** (2026-09-04, final): [código: age_factor.py:5,155,189]. Afeta resultado principal (contribuidor líder de Sobol S1 para `Risk_{i,h}`: hydro_retention_rate=0.4034). [doc: DECISIONS#"age_factor: >=1 multiplier... (final)"]
- **Thermal implementado homogêneo (sem split cooling-type)** (2026-09-11): [código: risk_calculator.py, "GEAR v3 Phase 1.3"]. Afeta resultado (superestima risco hídrico de subconjunto dry-cooled). [doc: DECISIONS#"GEAR v3 Phase 1.3"]
- **spei reclassificado LOG→LIN_TERMS** (2026-09-14): correção de `FROZEN_BOUNDS`. Afeta resultado (recalcula Hazard para todo plant/cenário SPEI). [código: normalization.py; doc: DECISIONS#"spei reclassified from LOG_TERMS to LIN_TERMS"]
- **PSAE complete-case (NaN se qualquer RiskBand ausente)** (2026-09-14): [código: psae.py:197]. Afeta resultado (define cobertura 99,847% no Sobol). [doc: DECISIONS#"Phase 4 (PSAE) input mapping"]
- **Hazard Mapping Proxies Phase 5: Flood→precip, Storm→wind** (2026-09-15, decisão do autor): [código: contextual_validators.py, `EMDAT_DISASTER_TYPE_TO_TERM`]. Não afeta Risk_{i,h}/PSAE (camada secundária). [doc: DECISIONS#"Hazard Mapping Proxies (Phase 5)"]
- **correlation_gate.csv corrigido (bug NaN!=pass) 2026-09-16**: contagem de "12 falhas" era artefato de bug, corrigido para 0 falhas reais. Afeta interpretação do resultado principal do gate. [doc: DECISIONS#"correlation_gate.csv regenerated... NaN-comparison bug and fixed"]
- **Gas/oil-gas age_factor=1.0 pinned, final após busca bibliográfica limitada** (2026-09-11): [código: age_factor.py:209 `_thermal_fuel_retention`]. Não é evidência de ausência de efeito. [doc: DECISIONS#"Gas/oil-gas age_factor: pinned-neutral..."]

Superseded, excluídas por instrução: CCRS/SCI-NAES (substituído por Risk_{i,h}), age_factor `2-retention` v1 (revisado), age_factor `<=1` reversão (não autorizada, revertida).

## 3. Limitações (docs/LIMITATIONS.md, 307 linhas — condensado)

1. **SLR excluído** — sem base empírica defensável por tecnologia; revisitável. [doc: LIMITATIONS#2026-09-03]
2. **Pesos w_water/w_heat/w_drought = julgamento do autor**, não calibração; Tier 3; candidato a Sobol (item J). [doc: LIMITATIONS#2026-09-04]
3. **Campo cooling-technology GEM ausente** → Thermal tratado homogêneo; final salvo novo dado GEM. [doc: LIMITATIONS#2026-09-11; código: risk_calculator.py Thermal]
4. **Campo retrofit/repowering GEM ausente** → ciclo de overhaul do carvão (5 anos/70%) é premissa assumida, não derivada. Workaround: nenhum, revisitável se fonte aparecer. [doc: LIMITATIONS#2026-09-11]
5. **Extreme Precipitation Tier1→Tier3**: HAZUS-MH rejeitado (valores não existem na fonte primária); usa corte percentil P95 (ETCCDI). Final neste tier. [doc: LIMITATIONS#2026-09-11]
6. **Solar Extreme Wind**: sem limiar estrutural Tier1; percentil ERA5 é final, não contingência. [doc: LIMITATIONS#2026-09-11]
7. **Wildfire (FWI/EFFIS) não implementado** — dado de umidade relativa CMIP6 ausente; deferido como SLR. [doc: LIMITATIONS#2026-09-11]
8. **Extreme Wind é invariante a cenário** (baseline histórico ERA5 1991-2020), decisão epistêmica final, não placeholder. [doc: LIMITATIONS#2026-09-11]
9. **Par de GCM (GFDL-ESM4, MIROC6) não cobre o intervalo de ECS do CMIP6** — seleção operacional, não bounding design; documentação retroativa, não reabre V4. [doc: LIMITATIONS#2026-09-11]
10. **Gas/oil-gas age_factor=1.0 pinned final** — ausência de evidência citável. [doc: LIMITATIONS#2026-09-11]
11. **IBTrACS validator = proxy de raio fixo (100 km)**, não campo de vento real por tempestade; pontos sem vento reportado são silenciosamente excluídos. [doc: LIMITATIONS#2026-09-15; código: contextual_validators.py:156,162]
12. **Phase 5 parcial**: landslide/lightning excluídos; mapeamento Flood→precip e Storm→wind é proxy de autor (2026-09-15), não correspondência exata de causa. [doc: LIMITATIONS#2026-09-15 ×2]
13. **HeatRiskBand sem limiar absoluto publicado** — cortes relativos à amostra do estudo, sensível ao GCM (~10–100×). [código: risk_bands.py; doc: ARCHITECTURE §10]
14. **main.py não migrado, quebrado** — sucessor funcional é `results_draft/run_all.py`. [código: src/main.py:73; doc: LIMITATIONS#2026-09-16]
15. **Camada legada de visualização/Monte Carlo (`monte_carlo.py`, `visualization/*.py`) deletada**, sem equivalente v3. [doc: LIMITATIONS#2026-09-16]
16. **`sensitivity_recompute.py` não é resultado de sensibilidade** — só cache de raster. [doc: LIMITATIONS#2026-09-16]

## 4. Resultados principais (números exatos)

- **Sobol** (`sobol_sensitivity.py:354`, N₀=1024, 15.360 avaliações, 7237,5s): Risk_{i,h} top S1/ST: hydro_retention_rate 0,4034/0,4046; coal_decay_rate 0,1964/0,2068; coal_overhaul_recovery 0,1908/0,2003; upper_tail_padding_fraction 0,1953/0,1946; solar_retention_rate 0,0033/0,0030. PSAE_i top: precip_percentile_shift 0,4670/0,4675; heat_percentile_shift 0,4534/0,4530; wind_percentile_shift 0,0774/0,0776. ΣS1≈0,99 (Risk) / ≈0,997 (PSAE), ST≈S1 (aditivo). [output: data/outputs/tables/phase6_sobol_full_n1024.json, 2026-09-15 13:06:27 -03; doc: DECISIONS#"Phase 6 closure" 2026-09-15]
- **Monte Carlo geral** (`general_mc.py`, 9 streams país×cenário, convergido em N=800/stream, confirmado N=1600): ex. Brasil/pes risk_mean=743,260 IC95%[726,678–759,008], psae_mean=0,0403 IC95%[0,0227–0,0574]; Portugal/pes risk_mean=96,532, psae_mean=0,5125; Índia/pes risk_mean=320,975, psae_mean=0,1203 (9 streams completos no output). [output: data/outputs/tables/phase6_general_mc_convergence.json, 2026-09-15 16:26:29 -03]
- **Correlation gate**: 56 linhas (5 pares gated × 3 países × GCM + referência água/seca), 36 pass, 0 falhas reais entre 42 células com veredito (36 pass, 6 report_only — "12 falhas" era bug de comparação NaN, corrigido 2026-09-16), max |decision_r| observado = 0,702079 [output: data/outputs/tables/correlation_gate.csv, 2026-09-16 11:54:35 -03; doc: DECISIONS#"correlation_gate.csv regenerated"]
- **IBTrACS (physical_occurrence, wind)**: fração "Corroborated" — Brasil 16/4416 (0,36%, único evento correlato: furacão Catarina 2004); Índia 1784/4344 (41,07%); Portugal 288/391 (73,66%). Interpretação: densidade de corroboração cresce com exposição ciclônica real da bacia (Atlântico Sul quase nulo vs. Golfo de Bengala/Atlântico Norte). [output: data/outputs/results_draft/tables/validator_overlay_summary.csv; doc: LIMITATIONS#2026-09-15]
- **results_draft**: 80 arquivos gerados nesta execução, 16/16 itens "generated" (0 pendentes), hazards cobertos: ws, spei, precip, sv, iv, heat, wind; última atualização MANIFEST.md 2026-09-16 11:56:16 -03. [output: data/outputs/results_draft/MANIFEST.md]

## 5. Fora de escopo

- **`src/main.py`**: não migrado para v3, quebra em import (`ccrs_calculator`/`ccrs_report` deletados). Sucessor: `src/reporting/results_draft/run_all.py`. Um sucessor não deve tentar "consertar" `main.py` — é decisão final. [código: src/main.py:60-77; doc: LIMITATIONS#2026-09-16]
- **Phase 5/6 parcial**: Phase 5 (contextual validators) cobre só heat/spei/ws (broad-impact) e wind (physical-occurrence); landslide/lightning nunca investigados; Flood/Storm usam proxy de autor não validado por sub-causa. Phase 6 fechado para Sobol/general-MC, mas item aberto: prosa de Discussion sobre `coal_overhaul_recovery` ainda sem arquivo de destino (manuscrito não existe). RNG granularity per-country-scenario (9× custo) permanece decisão aberta não resolvida. [doc: DECISIONS#"Phase 6 (Sensitivity/uncertainty) input mapping" itens abertos; LIMITATIONS#2026-09-15 Phase 5]
- **Citações não verificadas**: Durmayaz & Sogut (2006), thermal-calor, conhecida só via citação secundária — verificação bibliográfica pendente antes da submissão [doc: ARCHITECTURE §6.1 nota]. Al-Khayat & Al-Rasheedi 2024 (wind-calor) — título de periódico "a confirmar na fonte primária" [doc: ARCHITECTURE §6.1].
- **Itens "planned"/"future" citados em ARCHITECTURE.md**: SLR (extensão futura condicionada a coeficientes por tecnologia); Wildfire (condicionado a nova fonte de dado); campo cooling-technology GEM (se surgir); fator de robustez estrutural pós-V5 (se dado aparecer); sensibilidade da matriz de pesos §6.1 (item J do Monte Carlo, ainda não derivado).

## 6. Rastreabilidade

Ver tags inline `[código: arquivo:linha]`, `[doc: DECISIONS#ID]`, `[output: path]` embutidas em cada seção acima; nenhuma alegação numérica desta síntese carece de citação — onde a verificação não foi possível no tempo disponível (ex.: linha exata de `EMDAT_DISASTER_TYPE_TO_TERM` dentro de `contextual_validators.py`), a citação aponta ao nome do símbolo/arquivo sem número de linha, nunca inventado.
