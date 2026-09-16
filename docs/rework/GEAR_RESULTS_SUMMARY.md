# GEAR -- Relatorio de Resultados (dados reais, pipeline v3)

_Gerado em 2026-09-15 a partir dos outputs de producao em `data/outputs/tables/` (GCM primario: GFDL-ESM4; PSAE recomputado nesta extracao via `python -m src.index.psae`, nao existia CSV persistido ate esta execucao)._

Convencao de cenario (fonte: `src/config.py`): **opt = SSP1-2.6**, **bau = SSP3-7.0**, **pes = SSP5-8.5**. `water_scenario` e `heat_scenario` sao pareados 1:1 (opt<->ssp126, bau<->ssp370, pes<->ssp585) -- confirmado nos dados (`risk_bands.csv`).

## 1. Inventario base (demografia dos dados)

- Total de usinas avaliadas (3 paises): **10,808**
- Capacidade total avaliada (3 paises): **723,199.7 MW**

### 1.1 Total por pais

| Pais | N usinas | Capacidade (MW) |
|---|---|---|
| Brazil | 5,275 | 218,286.4 |
| India | 5,083 | 483,110.5 |
| Portugal | 450 | 21,802.8 |

### 1.2 Quebra por tecnologia (bucket)

**Brazil**

| Tecnologia | N usinas | Capacidade (MW) | % usinas do pais | % capacidade do pais |
|---|---|---|---|---|
| Hydro | 194 | 109,667.0 | 3.68% | 50.24% |
| Thermal | 665 | 47,668.2 | 12.61% | 21.84% |
| Solar | 3,290 | 24,906.4 | 62.37% | 11.41% |
| Wind | 1,126 | 36,044.8 | 21.35% | 16.51% |
| **TOTAL** | **5,275** | **218,286.4** | **100.00%** | **100.00%** |

**India**

| Tecnologia | N usinas | Capacidade (MW) | % usinas do pais | % capacidade do pais |
|---|---|---|---|---|
| Hydro | 226 | 51,195.0 | 4.45% | 10.60% |
| Thermal | 513 | 293,621.2 | 10.09% | 60.78% |
| Solar | 3,709 | 99,357.3 | 72.97% | 20.57% |
| Wind | 635 | 38,937.0 | 12.49% | 8.06% |
| **TOTAL** | **5,083** | **483,110.5** | **100.00%** | **100.00%** |

**Portugal**

| Tecnologia | N usinas | Capacidade (MW) | % usinas do pais | % capacidade do pais |
|---|---|---|---|---|
| Hydro | 40 | 7,783.0 | 8.89% | 35.70% |
| Thermal | 19 | 4,733.1 | 4.22% | 21.71% |
| Solar | 166 | 3,532.1 | 36.89% | 16.20% |
| Wind | 225 | 5,754.6 | 50.00% | 26.39% |
| **TOTAL** | **450** | **21,802.8** | **100.00%** | **100.00%** |

## 2. Trajetoria de risco por hazard (Risk_i,h)

Regra aplicada: hazards **nunca** somados -- cada tabela abaixo e um hazard isolado, dentro de um bucket (tecnologia) e pais. `n_missing` = linhas sem `risk_band` atribuido (plant/scenario sem dado; excluidas do denominador de capacidade da tabela, ver coluna `Cobertura`). Extreme Wind (hazard `wind`) e estatico (ERA5, sem SSP) -- confirmado abaixo por checagem direta.

- **Checagem Extreme Wind estatico**: 9151 plantas com hazard `wind`; **0** tiveram `risk_band` diferente entre os 3 cenarios (esperado: 0). Confirmado estatico.

### 2.1 Brazil

**Hydro** (capacidade total do bucket: 109,667.0 MW)

_Hazard: Water Stress (`ws`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 106,067.0 (96.72%) | 1,094.0 (1.00%) | 1,456.0 (1.33%) | 1,050.0 (0.96%) | 0/194 |
| SSP3-7.0 | 105,061.0 (95.80%) | 3,496.0 (3.19%) | 60.0 (0.05%) | 1,050.0 (0.96%) | 0/194 |
| SSP5-8.5 | 105,104.0 (95.84%) | 2,057.0 (1.88%) | 1,456.0 (1.33%) | 1,050.0 (0.96%) | 0/194 |

_Hazard: Drought (SPEI) (`spei`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 105,529.0 (96.23%) | 3,625.0 (3.31%) | 328.0 (0.30%) | 185.0 (0.17%) | 0/194 |
| SSP3-7.0 | 101,021.0 (92.12%) | 4,427.0 (4.04%) | 2,770.0 (2.53%) | 1,449.0 (1.32%) | 0/194 |
| SSP5-8.5 | 83,004.0 (75.69%) | 14,744.0 (13.44%) | 4,511.0 (4.11%) | 7,408.0 (6.75%) | 0/194 |

_Hazard: Extreme Precipitation (`precip`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 58,210.0 (53.08%) | 4,167.0 (3.80%) | 25,001.0 (22.80%) | 22,289.0 (20.32%) | 0/194 |
| SSP3-7.0 | 58,603.0 (53.44%) | 24,963.0 (22.76%) | 5,141.0 (4.69%) | 20,960.0 (19.11%) | 0/194 |
| SSP5-8.5 | 59,798.0 (54.53%) | 6,191.0 (5.65%) | 25,430.0 (23.19%) | 18,248.0 (16.64%) | 0/194 |

_Hazard: Water Seasonal Variability (`sv`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 107,285.0 (97.83%) | 2,322.0 (2.12%) | 0.0 (0.00%) | 60.0 (0.05%) | 0/194 |
| SSP3-7.0 | 107,285.0 (97.83%) | 2,322.0 (2.12%) | 0.0 (0.00%) | 60.0 (0.05%) | 0/194 |
| SSP5-8.5 | 107,285.0 (97.83%) | 2,322.0 (2.12%) | 60.0 (0.05%) | 0.0 (0.00%) | 0/194 |

_Hazard: Water Interannual Variability (`iv`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 106,501.0 (97.11%) | 3,166.0 (2.89%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/194 |
| SSP3-7.0 | 106,501.0 (97.11%) | 3,166.0 (2.89%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/194 |
| SSP5-8.5 | 106,501.0 (97.11%) | 3,166.0 (2.89%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/194 |

**Thermal** (capacidade total do bucket: 47,668.2 MW)

_Hazard: Water Stress (`ws`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 23,895.8 (50.13%) | 20,473.1 (42.95%) | 2,666.9 (5.59%) | 40.1 (0.08%) | 5/665 |
| SSP3-7.0 | 23,905.5 (50.15%) | 19,336.1 (40.56%) | 3,794.2 (7.96%) | 40.1 (0.08%) | 5/665 |
| SSP5-8.5 | 23,539.4 (49.38%) | 19,730.8 (41.39%) | 3,765.6 (7.90%) | 40.1 (0.08%) | 5/665 |

_Hazard: Extreme Heat (`heat`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 47,654.9 (99.97%) | 13.3 (0.03%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/665 |
| SSP3-7.0 | 47,259.2 (99.14%) | 409.0 (0.86%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/665 |
| SSP5-8.5 | 46,903.6 (98.40%) | 764.6 (1.60%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/665 |

_Hazard: Extreme Precipitation (`precip`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 22,092.6 (46.35%) | 9,641.1 (20.23%) | 4,634.1 (9.72%) | 11,300.4 (23.71%) | 0/665 |
| SSP3-7.0 | 20,050.0 (42.06%) | 11,787.9 (24.73%) | 5,907.1 (12.39%) | 9,923.2 (20.82%) | 0/665 |
| SSP5-8.5 | 23,087.6 (48.43%) | 10,348.7 (21.71%) | 4,922.1 (10.33%) | 9,309.8 (19.53%) | 0/665 |

**Solar** (capacidade total do bucket: 24,906.4 MW)

_Hazard: Extreme Heat (`heat`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 24,881.7 (99.90%) | 24.7 (0.10%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/3290 |
| SSP3-7.0 | 24,848.9 (99.77%) | 57.5 (0.23%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/3290 |
| SSP5-8.5 | 24,641.2 (98.94%) | 265.2 (1.06%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/3290 |

_Hazard: Extreme Precipitation (`precip`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 16,757.9 (67.28%) | 7,127.1 (28.62%) | 494.8 (1.99%) | 526.6 (2.11%) | 0/3290 |
| SSP3-7.0 | 18,095.1 (72.65%) | 5,978.0 (24.00%) | 384.7 (1.54%) | 448.6 (1.80%) | 0/3290 |
| SSP5-8.5 | 19,210.4 (77.13%) | 5,025.7 (20.18%) | 276.8 (1.11%) | 393.5 (1.58%) | 0/3290 |

_Hazard: Extreme Wind (`wind`)_

| Cenario | Low MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|
| SSP1-2.6 | 0.0 (0.00%) | 0.0 (0.00%) | 3290/3290 |
| SSP3-7.0 | 0.0 (0.00%) | 0.0 (0.00%) | 3290/3290 |
| SSP5-8.5 | 0.0 (0.00%) | 0.0 (0.00%) | 3290/3290 |

**Wind** (capacidade total do bucket: 36,044.8 MW)

_Hazard: Extreme Wind (`wind`)_

| Cenario | Low MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|
| SSP1-2.6 | 0.0 (0.00%) | 0.0 (0.00%) | 1126/1126 |
| SSP3-7.0 | 0.0 (0.00%) | 0.0 (0.00%) | 1126/1126 |
| SSP5-8.5 | 0.0 (0.00%) | 0.0 (0.00%) | 1126/1126 |

### 2.2 India

**Hydro** (capacidade total do bucket: 51,195.0 MW)

_Hazard: Water Stress (`ws`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 9,948.0 (19.43%) | 18,210.0 (35.57%) | 10,369.0 (20.25%) | 11,319.0 (22.11%) | 7/226 |
| SSP3-7.0 | 7,288.0 (14.24%) | 20,500.0 (40.04%) | 11,356.0 (22.18%) | 10,702.0 (20.90%) | 7/226 |
| SSP5-8.5 | 7,288.0 (14.24%) | 13,801.0 (26.96%) | 17,038.0 (33.28%) | 11,719.0 (22.89%) | 7/226 |

_Hazard: Drought (SPEI) (`spei`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 49,575.0 (96.84%) | 822.0 (1.61%) | 34.0 (0.07%) | 764.0 (1.49%) | 0/226 |
| SSP3-7.0 | 43,816.0 (85.59%) | 4,911.0 (9.59%) | 850.0 (1.66%) | 1,618.0 (3.16%) | 0/226 |
| SSP5-8.5 | 43,781.0 (85.52%) | 6,848.0 (13.38%) | 405.0 (0.79%) | 161.0 (0.31%) | 0/226 |

_Hazard: Extreme Precipitation (`precip`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 34,997.0 (68.36%) | 8,860.0 (17.31%) | 830.0 (1.62%) | 6,508.0 (12.71%) | 0/226 |
| SSP3-7.0 | 42,219.0 (82.47%) | 2,468.0 (4.82%) | 1,124.0 (2.20%) | 5,384.0 (10.52%) | 0/226 |
| SSP5-8.5 | 42,264.0 (82.55%) | 2,423.0 (4.73%) | 1,124.0 (2.20%) | 5,384.0 (10.52%) | 0/226 |

_Hazard: Water Seasonal Variability (`sv`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 39,366.0 (76.89%) | 8,395.0 (16.40%) | 1,827.0 (3.57%) | 258.0 (0.50%) | 7/226 |
| SSP3-7.0 | 36,778.0 (71.84%) | 11,369.0 (22.21%) | 1,441.0 (2.81%) | 258.0 (0.50%) | 7/226 |
| SSP5-8.5 | 36,778.0 (71.84%) | 12,017.0 (23.47%) | 203.0 (0.40%) | 848.0 (1.66%) | 7/226 |

_Hazard: Water Interannual Variability (`iv`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 47,370.0 (92.53%) | 2,096.0 (4.09%) | 380.0 (0.74%) | 0.0 (0.00%) | 7/226 |
| SSP3-7.0 | 48,335.0 (94.41%) | 1,131.0 (2.21%) | 0.0 (0.00%) | 380.0 (0.74%) | 7/226 |
| SSP5-8.5 | 48,522.0 (94.78%) | 944.0 (1.84%) | 380.0 (0.74%) | 0.0 (0.00%) | 7/226 |

**Thermal** (capacidade total do bucket: 293,621.2 MW)

_Hazard: Water Stress (`ws`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 28,300.7 (9.64%) | 78,614.2 (26.77%) | 67,529.7 (23.00%) | 119,176.6 (40.59%) | 0/513 |
| SSP3-7.0 | 26,320.7 (8.96%) | 77,149.7 (26.28%) | 59,283.8 (20.19%) | 130,867.0 (44.57%) | 0/513 |
| SSP5-8.5 | 26,320.7 (8.96%) | 80,242.7 (27.33%) | 62,295.8 (21.22%) | 124,762.0 (42.49%) | 0/513 |

_Hazard: Extreme Heat (`heat`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 93,646.3 (31.89%) | 165,320.2 (56.30%) | 26,560.7 (9.05%) | 8,094.0 (2.76%) | 0/513 |
| SSP3-7.0 | 88,103.3 (30.01%) | 158,019.2 (53.82%) | 32,657.2 (11.12%) | 14,841.5 (5.05%) | 0/513 |
| SSP5-8.5 | 69,529.3 (23.68%) | 142,079.5 (48.39%) | 59,317.2 (20.20%) | 22,695.2 (7.73%) | 0/513 |

_Hazard: Extreme Precipitation (`precip`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 283,902.0 (96.69%) | 2,016.8 (0.69%) | 6,575.0 (2.24%) | 1,127.4 (0.38%) | 0/513 |
| SSP3-7.0 | 284,378.5 (96.85%) | 1,560.3 (0.53%) | 6,826.0 (2.32%) | 856.4 (0.29%) | 0/513 |
| SSP5-8.5 | 283,983.5 (96.72%) | 7,760.3 (2.64%) | 1,021.0 (0.35%) | 856.4 (0.29%) | 0/513 |

**Solar** (capacidade total do bucket: 99,357.3 MW)

_Hazard: Extreme Heat (`heat`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 34,618.2 (34.84%) | 27,595.9 (27.77%) | 12,432.9 (12.51%) | 24,710.3 (24.87%) | 0/3709 |
| SSP3-7.0 | 31,205.1 (31.41%) | 19,388.2 (19.51%) | 16,802.7 (16.91%) | 31,961.3 (32.17%) | 0/3709 |
| SSP5-8.5 | 23,235.5 (23.39%) | 25,899.3 (26.07%) | 16,676.0 (16.78%) | 33,546.5 (33.76%) | 0/3709 |

_Hazard: Extreme Precipitation (`precip`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 93,779.5 (94.39%) | 3,048.1 (3.07%) | 1,855.1 (1.87%) | 674.6 (0.68%) | 0/3709 |
| SSP3-7.0 | 96,232.2 (96.85%) | 954.0 (0.96%) | 1,849.3 (1.86%) | 321.8 (0.32%) | 0/3709 |
| SSP5-8.5 | 96,201.1 (96.82%) | 2,428.0 (2.44%) | 406.4 (0.41%) | 321.8 (0.32%) | 0/3709 |

_Hazard: Extreme Wind (`wind`)_

| Cenario | Low MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|
| SSP1-2.6 | 0.0 (0.00%) | 0.0 (0.00%) | 3709/3709 |
| SSP3-7.0 | 0.0 (0.00%) | 0.0 (0.00%) | 3709/3709 |
| SSP5-8.5 | 0.0 (0.00%) | 0.0 (0.00%) | 3709/3709 |

**Wind** (capacidade total do bucket: 38,937.0 MW)

_Hazard: Extreme Wind (`wind`)_

| Cenario | Low MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|
| SSP1-2.6 | 0.0 (0.00%) | 0.0 (0.00%) | 635/635 |
| SSP3-7.0 | 0.0 (0.00%) | 0.0 (0.00%) | 635/635 |
| SSP5-8.5 | 0.0 (0.00%) | 0.0 (0.00%) | 635/635 |

### 2.3 Portugal

**Hydro** (capacidade total do bucket: 7,783.0 MW)

_Hazard: Water Stress (`ws`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 1,506.0 (19.35%) | 3,050.0 (39.19%) | 2,777.0 (35.68%) | 450.0 (5.78%) | 0/40 |
| SSP3-7.0 | 1,252.0 (16.09%) | 3,304.0 (42.45%) | 2,777.0 (35.68%) | 450.0 (5.78%) | 0/40 |
| SSP5-8.5 | 1,252.0 (16.09%) | 3,304.0 (42.45%) | 2,262.0 (29.06%) | 965.0 (12.40%) | 0/40 |

_Hazard: Drought (SPEI) (`spei`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 7,783.0 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/40 |
| SSP3-7.0 | 0.0 (0.00%) | 7,315.0 (93.99%) | 0.0 (0.00%) | 468.0 (6.01%) | 0/40 |
| SSP5-8.5 | 5,646.0 (72.54%) | 2,137.0 (27.46%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/40 |

_Hazard: Extreme Precipitation (`precip`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 1,080.0 (13.88%) | 508.0 (6.53%) | 0.0 (0.00%) | 6,195.0 (79.60%) | 0/40 |
| SSP3-7.0 | 1,080.0 (13.88%) | 508.0 (6.53%) | 6,195.0 (79.60%) | 0.0 (0.00%) | 0/40 |
| SSP5-8.5 | 1,080.0 (13.88%) | 508.0 (6.53%) | 6,195.0 (79.60%) | 0.0 (0.00%) | 0/40 |

_Hazard: Water Seasonal Variability (`sv`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 7,783.0 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/40 |
| SSP3-7.0 | 7,783.0 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/40 |
| SSP5-8.5 | 7,783.0 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/40 |

_Hazard: Water Interannual Variability (`iv`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 7,783.0 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/40 |
| SSP3-7.0 | 7,268.0 (93.38%) | 515.0 (6.62%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/40 |
| SSP5-8.5 | 7,268.0 (93.38%) | 515.0 (6.62%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/40 |

**Thermal** (capacidade total do bucket: 4,733.1 MW)

_Hazard: Water Stress (`ws`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 859.7 (18.16%) | 2,166.0 (45.76%) | 122.5 (2.59%) | 1,584.9 (33.49%) | 0/19 |
| SSP3-7.0 | 0.0 (0.00%) | 3,025.7 (63.93%) | 122.5 (2.59%) | 1,584.9 (33.49%) | 0/19 |
| SSP5-8.5 | 0.0 (0.00%) | 3,025.7 (63.93%) | 122.5 (2.59%) | 1,584.9 (33.49%) | 0/19 |

_Hazard: Extreme Heat (`heat`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 4,733.1 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/19 |
| SSP3-7.0 | 4,733.1 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/19 |
| SSP5-8.5 | 4,733.1 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/19 |

_Hazard: Extreme Precipitation (`precip`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 2,346.6 (49.58%) | 1,274.0 (26.92%) | 0.0 (0.00%) | 1,112.5 (23.50%) | 0/19 |
| SSP3-7.0 | 2,346.6 (49.58%) | 1,274.0 (26.92%) | 1,112.5 (23.50%) | 0.0 (0.00%) | 0/19 |
| SSP5-8.5 | 3,481.5 (73.56%) | 139.1 (2.94%) | 1,112.5 (23.50%) | 0.0 (0.00%) | 0/19 |

**Solar** (capacidade total do bucket: 3,532.1 MW)

_Hazard: Extreme Heat (`heat`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 3,532.1 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/166 |
| SSP3-7.0 | 3,532.1 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/166 |
| SSP5-8.5 | 3,532.1 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0/166 |

_Hazard: Extreme Precipitation (`precip`)_

| Cenario | Low MW (%) | Medium MW (%) | High MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|---|---|
| SSP1-2.6 | 2,813.5 (79.66%) | 345.9 (9.79%) | 0.0 (0.00%) | 372.7 (10.55%) | 0/166 |
| SSP3-7.0 | 2,813.5 (79.66%) | 345.9 (9.79%) | 372.7 (10.55%) | 0.0 (0.00%) | 0/166 |
| SSP5-8.5 | 2,816.1 (79.73%) | 343.3 (9.72%) | 372.7 (10.55%) | 0.0 (0.00%) | 0/166 |

_Hazard: Extreme Wind (`wind`)_

| Cenario | Low MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|
| SSP1-2.6 | 0.0 (0.00%) | 0.0 (0.00%) | 166/166 |
| SSP3-7.0 | 0.0 (0.00%) | 0.0 (0.00%) | 166/166 |
| SSP5-8.5 | 0.0 (0.00%) | 0.0 (0.00%) | 166/166 |

**Wind** (capacidade total do bucket: 5,754.6 MW)

_Hazard: Extreme Wind (`wind`)_

| Cenario | Low MW (%) | Extreme MW (%) | N sem risk_band / N total |
|---|---|---|---|
| SSP1-2.6 | 0.0 (0.00%) | 0.0 (0.00%) | 225/225 |
| SSP3-7.0 | 0.0 (0.00%) | 0.0 (0.00%) | 225/225 |
| SSP5-8.5 | 0.0 (0.00%) | 0.0 (0.00%) | 225/225 |

## 3. Exposicao sistemica (PSAE)

PSAE_i = fracao de hazards do bucket (H_b) que estao em High/Extreme para a planta i. Classificacao (Tier 3, `src/index/psae.py`): **EXTREME** (PSAE=1.0), **HIGH** (0.5<=PSAE<1.0), **MEDIUM** (0<PSAE<0.5), **LOW** (PSAE=0.0). Linhas `INCOMPLETE` = plant/scenario com >=1 hazard do H_b faltante (complete-case, excluido da classificacao por decisao de projeto).

### 3.1 Brazil

**Hydro** (H_b size = 5)

| Cenario | LOW MW (%) | MEDIUM MW (%) | HIGH MW (%) | EXTREME MW (%) | INCOMPLETE MW (%) |
|---|---|---|---|---|---|
| SSP1-2.6 | 59,467.0 (54.23%) | 50,200.0 (45.77%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP3-7.0 | 81,807.0 (74.60%) | 27,860.0 (25.40%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP5-8.5 | 56,257.0 (51.30%) | 53,410.0 (48.70%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |

**Thermal** (H_b size = 3)

| Cenario | LOW MW (%) | MEDIUM MW (%) | HIGH MW (%) | EXTREME MW (%) | INCOMPLETE MW (%) |
|---|---|---|---|---|---|
| SSP1-2.6 | 29,429.6 (61.74%) | 16,992.4 (35.65%) | 653.9 (1.37%) | 0.0 (0.00%) | 592.3 (1.24%) |
| SSP3-7.0 | 29,470.2 (61.82%) | 15,888.1 (33.33%) | 1,717.6 (3.60%) | 0.0 (0.00%) | 592.3 (1.24%) |
| SSP5-8.5 | 30,272.1 (63.51%) | 15,911.3 (33.38%) | 892.5 (1.87%) | 0.0 (0.00%) | 592.3 (1.24%) |

**Solar** (H_b size = 3)

| Cenario | LOW MW (%) | MEDIUM MW (%) | HIGH MW (%) | EXTREME MW (%) | INCOMPLETE MW (%) |
|---|---|---|---|---|---|
| SSP1-2.6 | 23,876.3 (95.86%) | 1,030.1 (4.14%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP3-7.0 | 24,064.4 (96.62%) | 842.0 (3.38%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP5-8.5 | 24,227.4 (97.27%) | 679.0 (2.73%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |

**Wind** (H_b size = 1)

| Cenario | LOW MW (%) | MEDIUM MW (%) | HIGH MW (%) | EXTREME MW (%) | INCOMPLETE MW (%) |
|---|---|---|---|---|---|
| SSP1-2.6 | 35,776.7 (99.26%) | 0.0 (0.00%) | 0.0 (0.00%) | 268.1 (0.74%) | 0.0 (0.00%) |
| SSP3-7.0 | 35,776.7 (99.26%) | 0.0 (0.00%) | 0.0 (0.00%) | 268.1 (0.74%) | 0.0 (0.00%) |
| SSP5-8.5 | 35,776.7 (99.26%) | 0.0 (0.00%) | 0.0 (0.00%) | 268.1 (0.74%) | 0.0 (0.00%) |

### 3.2 India

**Hydro** (H_b size = 5)

| Cenario | LOW MW (%) | MEDIUM MW (%) | HIGH MW (%) | EXTREME MW (%) | INCOMPLETE MW (%) |
|---|---|---|---|---|---|
| SSP1-2.6 | 21,154.0 (41.32%) | 28,402.0 (55.48%) | 290.0 (0.57%) | 0.0 (0.00%) | 1,349.0 (2.64%) |
| SSP3-7.0 | 20,717.0 (40.47%) | 28,839.0 (56.33%) | 290.0 (0.57%) | 0.0 (0.00%) | 1,349.0 (2.64%) |
| SSP5-8.5 | 15,207.0 (29.70%) | 34,349.0 (67.09%) | 290.0 (0.57%) | 0.0 (0.00%) | 1,349.0 (2.64%) |

**Thermal** (H_b size = 3)

| Cenario | LOW MW (%) | MEDIUM MW (%) | HIGH MW (%) | EXTREME MW (%) | INCOMPLETE MW (%) |
|---|---|---|---|---|---|
| SSP1-2.6 | 100,056.0 (34.08%) | 158,067.0 (53.83%) | 35,498.2 (12.09%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP3-7.0 | 96,611.5 (32.90%) | 148,687.5 (50.64%) | 48,322.2 (16.46%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP5-8.5 | 73,201.3 (24.93%) | 169,892.2 (57.86%) | 50,527.7 (17.21%) | 0.0 (0.00%) | 0.0 (0.00%) |

**Solar** (H_b size = 3)

| Cenario | LOW MW (%) | MEDIUM MW (%) | HIGH MW (%) | EXTREME MW (%) | INCOMPLETE MW (%) |
|---|---|---|---|---|---|
| SSP1-2.6 | 59,660.0 (60.05%) | 39,697.3 (39.95%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP3-7.0 | 48,397.8 (48.71%) | 50,959.5 (51.29%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP5-8.5 | 48,382.2 (48.70%) | 50,975.1 (51.30%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |

**Wind** (H_b size = 1)

| Cenario | LOW MW (%) | MEDIUM MW (%) | HIGH MW (%) | EXTREME MW (%) | INCOMPLETE MW (%) |
|---|---|---|---|---|---|
| SSP1-2.6 | 38,937.0 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP3-7.0 | 38,937.0 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP5-8.5 | 38,937.0 (100.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |

### 3.3 Portugal

**Hydro** (H_b size = 5)

| Cenario | LOW MW (%) | MEDIUM MW (%) | HIGH MW (%) | EXTREME MW (%) | INCOMPLETE MW (%) |
|---|---|---|---|---|---|
| SSP1-2.6 | 623.0 (8.00%) | 7,160.0 (92.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP3-7.0 | 565.0 (7.26%) | 7,218.0 (92.74%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP5-8.5 | 623.0 (8.00%) | 7,160.0 (92.00%) | 0.0 (0.00%) | 0.0 (0.00%) | 0.0 (0.00%) |

**Thermal** (H_b size = 3)

| Cenario | LOW MW (%) | MEDIUM MW (%) | HIGH MW (%) | EXTREME MW (%) | INCOMPLETE MW (%) |
|---|---|---|---|---|---|
| SSP1-2.6 | 2,035.7 (43.01%) | 2,574.9 (54.40%) | 122.5 (2.59%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP3-7.0 | 2,035.7 (43.01%) | 2,574.9 (54.40%) | 122.5 (2.59%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP5-8.5 | 2,035.7 (43.01%) | 2,574.9 (54.40%) | 122.5 (2.59%) | 0.0 (0.00%) | 0.0 (0.00%) |

**Solar** (H_b size = 3)

| Cenario | LOW MW (%) | MEDIUM MW (%) | HIGH MW (%) | EXTREME MW (%) | INCOMPLETE MW (%) |
|---|---|---|---|---|---|
| SSP1-2.6 | 444.6 (12.59%) | 2,714.8 (76.86%) | 372.7 (10.55%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP3-7.0 | 444.6 (12.59%) | 2,714.8 (76.86%) | 372.7 (10.55%) | 0.0 (0.00%) | 0.0 (0.00%) |
| SSP5-8.5 | 444.6 (12.59%) | 2,714.8 (76.86%) | 372.7 (10.55%) | 0.0 (0.00%) | 0.0 (0.00%) |

**Wind** (H_b size = 1)

| Cenario | LOW MW (%) | MEDIUM MW (%) | HIGH MW (%) | EXTREME MW (%) | INCOMPLETE MW (%) |
|---|---|---|---|---|---|
| SSP1-2.6 | 1,115.6 (19.39%) | 0.0 (0.00%) | 0.0 (0.00%) | 4,639.0 (80.61%) | 0.0 (0.00%) |
| SSP3-7.0 | 1,115.6 (19.39%) | 0.0 (0.00%) | 0.0 (0.00%) | 4,639.0 (80.61%) | 0.0 (0.00%) |
| SSP5-8.5 | 1,115.6 (19.39%) | 0.0 (0.00%) | 0.0 (0.00%) | 4,639.0 (80.61%) | 0.0 (0.00%) |

### 3.4 Drivers de PSAE = EXTREME (co-ocorrencia de hazards em High/Extreme)

Para cada bucket, entre os plant x water_scenario classificados PSAE=EXTREME (em qualquer pais/cenario), fracao de vezes que cada hazard do H_b individualmente esteve em High/Extreme (por definicao de EXTREME, TODOS os hazards do bucket estao em High/Extreme simultaneamente -- tabela serve para confirmar consistencia e mostrar contagem absoluta de linhas por bucket).

**Hydro**: nenhuma linha PSAE=EXTREME em nenhum pais/cenario.

**Thermal**: nenhuma linha PSAE=EXTREME em nenhum pais/cenario.

**Wind** -- N linhas plant x scenario com PSAE=EXTREME: 0 (por pais: {})

| Hazard | N vezes High/Extreme | % das linhas EXTREME |
|---|---|---|
| Extreme Wind | 0 | - |

**Solar**: nenhuma linha PSAE=EXTREME em nenhum pais/cenario.

## 4. Teste de sensibilidade e idade (Phase 6 / Sobol)

- Configuracao Sobol: N0 = 1,024 (amostra base Saltelli), N_evals = 15,360, 13 parametros, 4 workers, tempo total = 7238s.
- Cobertura PSAE nas avaliacoes: **99.85%** (994,544,640 / 996,065,280 linhas completas).

### 4.1 Sobol -- variavel de saida: Risk_mean_overall (media global de Risk_i,h)

| Parametro | S1 | S1_conf | ST | ST_conf |
|---|---|---|---|---|
| hydro_retention_rate | 0.4034 | 0.0492 | 0.4046 | 0.0335 |
| coal_decay_rate | 0.1964 | 0.0319 | 0.2068 | 0.0224 |
| coal_overhaul_recovery | 0.1908 | 0.0393 | 0.2003 | 0.0218 |
| upper_tail_padding_fraction | 0.1953 | 0.0352 | 0.1946 | 0.0142 |
| solar_retention_rate | 0.0033 | 0.0046 | 0.0030 | 0.0003 |
| coal_overhaul_cycle_years | 0.0008 | 0.0025 | 0.0010 | 0.0001 |
| wind_relative_rate | 0.0001 | 0.0009 | 0.0001 | 0.0000 |
| spei_percentile_shift | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| precip_percentile_shift | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| heat_percentile_shift | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| sv_percentile_shift | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| iv_percentile_shift | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| wind_percentile_shift | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

### 4.2 Sobol -- variavel de saida: PSAE_mean_overall (media global de PSAE_i)

| Parametro | S1 | S1_conf | ST | ST_conf |
|---|---|---|---|---|
| precip_percentile_shift | 0.4670 | 0.0530 | 0.4675 | 0.0361 |
| heat_percentile_shift | 0.4534 | 0.0590 | 0.4530 | 0.0416 |
| wind_percentile_shift | 0.0774 | 0.0233 | 0.0776 | 0.0062 |
| sv_percentile_shift | 0.0001 | 0.0010 | 0.0002 | 0.0000 |
| spei_percentile_shift | 0.0002 | 0.0010 | 0.0001 | 0.0000 |
| iv_percentile_shift | -0.0000 | 0.0002 | 0.0000 | 0.0000 |
| coal_decay_rate | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| wind_relative_rate | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| hydro_retention_rate | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| solar_retention_rate | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| coal_overhaul_cycle_years | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| coal_overhaul_recovery | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| upper_tail_padding_fraction | 0.0000 | 0.0000 | 0.0000 | 0.0000 |

### 4.3 Amplificacao de risco por idade (age_factor)

`age_factor` multiplica o hazard bruto (ccrs_hazard_aged.csv); valores > 1.0 amplificam o risco. Tabela por pais x tecnologia (media simples, media ponderada por capacidade, e maximo observado).

| Pais | Tecnologia | Age factor medio | Age factor (media ponderada por MW) | Age factor maximo | N plantas |
|---|---|---|---|---|---|
| Brazil | Hydro | 1.3195 | 1.3226 | 1.7480 | 194 |
| India | Hydro | 1.3384 | 1.3028 | 1.7040 | 226 |
| Portugal | Hydro | 1.3564 | 1.3055 | 1.5445 | 40 |
| Portugal | Solar | 1.1882 | 1.1770 | 1.2659 | 166 |
| India | Wind | 1.0830 | 1.0909 | 1.2400 | 635 |
| India | Solar | 1.1784 | 1.1726 | 1.2396 | 3,709 |
| Brazil | Solar | 1.1708 | 1.1606 | 1.2396 | 3,290 |
| Portugal | Wind | 1.1683 | 1.1645 | 1.2320 | 225 |
| Brazil | Wind | 1.1242 | 1.1192 | 1.2120 | 1,126 |
| India | Thermal | 1.0212 | 1.0314 | 1.0675 | 513 |
| Brazil | Thermal | 1.0003 | 1.0025 | 1.0637 | 665 |
| Portugal | Thermal | 1.0000 | 1.0000 | 1.0000 | 19 |

- **Maior age_factor individual observado**: Brazil / Hydro = 1.7480.
- **Maior age_factor medio ponderado por capacidade (amplificacao sistemica do bucket)**: Brazil / Hydro = 1.3226.

### 4.4 Robustez do ranking de exposicao entre paises

Fonte: `national_ccrs_summary.csv` (Monte Carlo, GCM GFDL-ESM4, IC 95%), rank 1 = maior CCRS nacional no cenario. `phase6_general_mc_convergence.json` fornece o mesmo ranking (risk_mean) atraves do processo de convergencia de N draws (100->1600), usado aqui como segunda checagem independente de estabilidade sob reamostragem/perturbacao estocastica -- nao e o OAT de `scenario_discovery.py` (hazard-inclusion / correlation-gate / psae-cutpoint), que nao possui CSV persistido nesta base e nao foi executado nesta extracao.

| Cenario | Rank | Pais | CCRS nacional (mediana MC) | IC 95% |
|---|---|---|---|---|
| SSP3-7.0 | 1 | India | 0.8093 | [0.7409, 0.8814] |
| SSP3-7.0 | 2 | Portugal | 0.3161 | [0.3108, 0.3215] |
| SSP3-7.0 | 3 | Brazil | 0.2743 | [0.2624, 0.2870] |
| SSP1-2.6 | 1 | India | 0.7639 | [0.6994, 0.8316] |
| SSP1-2.6 | 2 | Brazil | 0.2453 | [0.2346, 0.2566] |
| SSP1-2.6 | 3 | Portugal | 0.2361 | [0.2320, 0.2403] |
| SSP5-8.5 | 1 | India | 0.8461 | [0.7746, 0.9212] |
| SSP5-8.5 | 2 | Brazil | 0.3268 | [0.3126, 0.3420] |
| SSP5-8.5 | 3 | Portugal | 0.2979 | [0.2931, 0.3029] |

- Rank 1 (maior CCRS) em todos os 3 cenarios: **India** (estavel nos 3 cenarios).
- Ordem completa: SSP1-2.6 = ['India', 'Brazil', 'Portugal']; SSP3-7.0 = ['India', 'Portugal', 'Brazil']; SSP5-8.5 = ['India', 'Brazil', 'Portugal'].
- Brazil e Portugal trocam de posicao (rank 2/3) entre cenarios; India permanece rank 1 em todos.

**ATENCAO -- metrica diferente, nao comparavel diretamente**: o ranking abaixo (`risk_mean`, de `phase6_general_mc_convergence.json`) usa `risk_i_h` medio ponderado por capacidade (escala nao normalizada, ordens de grandeza de centenas), enquanto a tabela acima usa o CCRS nacional (indice composto normalizado ~0-1). Os dois rankeiam Brazil/India em ordem OPOSTA (`risk_mean` coloca Brazil em 1o lugar nos 3 cenarios) porque medem quantidades distintas -- isto e um resultado real dos dados, nao um erro de transcricao, e deve ser tratado no manuscrito como duas metricas de exposicao com definicoes diferentes, nao como uma contradicao a resolver.


_Checagem de convergencia (`phase6_general_mc_convergence.json`)_: convergiu = True, N convergente = 800, Ns testados = [100, 200, 400, 800, 1600].

| Cenario | Ranking risk_mean N=100 | Ranking risk_mean N=1600 | Estabilidade |
|---|---|---|---|
| SSP1-2.6 | N=100: ['Brazil', 'India', 'Portugal'] | N=1600: ['Brazil', 'India', 'Portugal'] | estavel |
| SSP3-7.0 | N=100: ['Brazil', 'India', 'Portugal'] | N=1600: ['Brazil', 'India', 'Portugal'] | estavel |
| SSP5-8.5 | N=100: ['Brazil', 'India', 'Portugal'] | N=1600: ['Brazil', 'India', 'Portugal'] | estavel |
