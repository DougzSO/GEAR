# GEAR Framework — ARCHITECTURE.md

## Propósito deste documento

Especifica o que o GEAR fará: escopo, índices, pesos, resiliência e
incerteza. As decisões aqui registradas estão tomadas, exceto onde
explicitamente marcadas como **verificação pós-dados** — itens que só
podem ser resolvidos após a reconstrução da camada de aquisição e
processamento e visualização dos dados reais. Nenhum código de índice
deve ser escrito antes desse revisit.

---

## 1. Pergunta de pesquisa

Qual é o nível de exposição ao risco climático do sistema elétrico
nacional — no Brasil, em Portugal e na Índia — e como ele se compara
dentro de cada país e entre os três países, sob trajetórias contrastantes
de emissões?

O produto final é um sinal comparativo interpretável para tomadores de
decisão, reguladores, investidores e atores da sociedade civil — não dados
brutos de hazard.

---

## 2. Escopo

- **Unidade de análise:** planta de geração elétrica individual, agregada
  a partir de registros por unidade.
- **Países:** Brasil, Portugal e Índia — escolhidos por contrastes em mix
  tecnológico, concentração de portfólio e regime hidroclimático.
- **Base de ativos:** Global Energy Monitor Global Integrated Power
  Tracker, snapshot manual versionado e datado. Apenas ativos com
  `Status == "operating"` entram no pipeline.
- **Limiar de capacidade:** os limiares nativos do GEM por tecnologia são
  mantidos sem modificação (hidro 45 MW, eólica 10 MW, solar 20 MW
  utilitário ou 1 MW distribuído). Essa heterogeneidade é declarada
  explicitamente no manuscrito em vez de ser corrigida por um limiar
  uniforme artificial.
- **Cenários de emissão:** SSP1-2.6 e SSP5-8.5 como extremos.
- **Horizonte temporal:** 2041–2070, representado pelo ponto médio 2050.
- **Hazards:** estresse hídrico e calor extremo. SLR está fora do escopo
  ativo (ver Seção 3).

---

## 3. Hazards: estresse hídrico e calor extremo

SLR foi retirado do escopo ativo. A razão não é negar o risco: Brasil e
Índia têm ativos costeiros genuinamente expostos a inundação e ressaca. A
razão é que a frota estudada é esmagadoramente terrestre e interior, e a
base empírica disponível não sustenta coeficientes defensáveis por
tecnologia para esse hazard neste escopo. SLR é declarado no manuscrito
como limite de escopo e trabalho futuro explícito — não omitido
silenciosamente.

Os dois hazards ativos e suas fontes de dado são:

| Hazard | Fonte | Cenários | Unidade bruta |
|---|---|---|---|
| Estresse hídrico | WRI Aqueduct 4.0, via Google Earth Engine | `opt` (SSP1-2.6), `pes` (SSP5-8.5) | `consumption_to_availability_ratio` |
| Calor extremo | Copernicus CDS, CMIP6 `gfdl_esm4` + segundo GCM | `ssp126`, `ssp585` | dias/ano com tasmax > 40 °C |

O cenário Aqueduct `bau` (SSP3-7.0) está disponível nos dados baixados mas
não tem contrapartida em calor nos cenários ativos (SSP1-2.6 e SSP5-8.5).
A inclusão de SSP3-7.0 como cenário intermediário está condicionada à
verificação de disponibilidade do dado de calor correspondente (ver
Verificações pós-dados, item V3).

---

## 4. Segundo GCM — sensitivity check obrigatório

Um único GCM (`GFDL-ESM4`) produz os rasters de calor extremo. Um segundo
modelo CMIP6 é obrigatório como sensitivity check, não opcional. O
`cds_tasmax_downloader.py` e o `config.py` devem suportar pelo menos dois
`source_id` configuráveis para os cenários `ssp126` e `ssp585`.

A escolha do segundo modelo e a decisão de cobrir os três países ou apenas
os casos de maior exposição a calor são verificações pós-dados (item V4).

---

## 5. Arquitetura de índices

Dois outputs, separados e não intercambiáveis.

### 5.1 Spatial Criticality Index (SCI)

Ranking dentro do país. Compara plantas apenas contra outras plantas do
mesmo país.

$$SCI_i = \left(\frac{Risk_i}{Risk_{max,c}}\right)^{1/3}
\times \left(\frac{Capacity_i}{Capacity_{total,c}}\right)^{1/3}
\times \left(1 - Resilience_{norm,i}\right)^{1/3}$$

$$Risk_i = w_{water} \cdot WaterStress_i + w_{heat} \cdot HeatStress_i$$

A média geométrica é usada porque o coeficiente de variação do termo de
participação de capacidade é várias vezes maior que o dos outros dois
termos numa formulação linear, o que faria esse termo dominar a cauda
superior do ranking de forma desproporcional.

$Capacity_{total,c}$ é calculado sobre a base de ativos com SCI
computável (coordenadas válidas e ano de comissionamento disponível),
não sobre a capacidade total declarada do portfólio.

### 5.2 National Aggregate Exposure Score (NAES)

Comparação entre países. Construído inteiramente sobre valores brutos
de hazard — nunca passa pela normalização Min-Max por país que torna o
SCI intrapaís.

$$NAES_{c,s} = \sum_{i \in c}
\left(\frac{Capacity_i}{Capacity_{total,c}}\right)
\times \left(w_{water} \cdot WaterStress^{raw}_{i,s}
+ w_{heat} \cdot HeatStress^{raw}_{i,s}\right)$$

$Capacity_{total,c}$ usa a mesma base computável do SCI, pela mesma
razão: valores brutos de hazard não podem ser produzidos para ativos sem
coordenadas ou ano de comissionamento.

O NAES é recomputado dentro de cada iteração de Monte Carlo, produzindo
uma distribuição por par país–cenário em vez de uma estimativa pontual.

A limitação do raster bruto de água (bacias sentinela substituídas por
`country_max`, Índia mais afetada) é declarada explicitamente no
manuscrito como restrição conhecida do NAES.

---

## 6. Derivação de pesos

Um peso ($w_{water}$, $w_{heat}$) é uma fração adimensional que soma 1
dentro de cada bucket tecnológico. Responde: de toda a sensibilidade
climática desta tecnologia, que fração vem de cada hazard?

O coeficiente da literatura (por exemplo, −0,65 %/°C para sensibilidade
solar ao calor) é evidência usada para derivar essa fração — não a fração
em si.

**Por que uma etapa de conversão é necessária:** os coeficientes
encontrados na literatura não são nativamente comparáveis. Alguns são
taxas marginais (perda percentual por grau de aumento de temperatura).
Outros são outcomes totais sob uma condição já severa (perda percentual
de capacidade sob estresse hídrico agudo). Tratar −0,65 e 85 como números
diretamente comparáveis, ou usar qualquer um deles como valor de peso
diretamente, é um erro de categoria.

**Procedimento — normalização por magnitude projetada:** para cada bucket,
projeta-se o impacto de cada hazard sobre o intervalo esperado do hazard
neste estudo, produzindo uma figura de "impacto total esperado" comparável
por hazard. Coeficientes de taxa marginal (calor, majoritariamente) são
multiplicados por um delta de temperatura de referência fixo por
tecnologia. Coeficientes já totais (água, majoritariamente) são usados
diretamente. As magnitudes resultantes são normalizadas dentro do bucket
para somar 1.

O delta de referência é fixo por tecnologia — não recomputado por país
ou cenário. Variação por país e cenário entra pelos dados de hazard,
não pelos pesos. Isso mantém a matriz de pesos estável e auditável.

### 6.1 Matriz de pesos — estado atual das evidências

| Bucket | Hazard | Coeficiente / intervalo | Tipo | Tier | Fonte |
|---|---|---|---|---|---|
| Hidro | Água | 61–74% de redução de capacidade utilizável sob estresse hídrico | Outcome total sob estresse | 1 | Van Vliet et al. (referência [1] na lista do manuscrito) |
| Hidro | Calor | Sem coeficiente independente — mecanismo (evaporação de reservatório) sobrepõe o canal de estresse hídrico já medido | — | 3, justificado por sobreposição | Turner, S. W. D. et al. Hydropower capacity factors trending down in the United States. *Nature Communications*, 2024; Zhao et al. Evaluating Enhanced Reservoir Evaporation Losses From CMIP6-Based Future Projections in the Contiguous United States. *Earth's Future*, 2023 |
| Eólica | Água | Sem mecanismo físico plausível | — | 3 | — |
| Eólica | Calor | Derating por segurança acima de ~40 °C, resposta em forma de degrau tratada como equivalente linear | Taxa marginal (equivalente linear) | 2 | Al-Khayat, M.; Al-Rasheedi, M. A new method for estimating the annual energy production of wind turbines in hot environments. 2024. *(título do periódico a confirmar na fonte primária)* |
| Solar | Água | Sem mecanismo físico plausível | — | 3 | — |
| Solar | Calor | −0,65 %/K de potência; −0,08 %/K de eficiência de conversão; literatura converge entre −0,3 % e −0,65 %/°C | Taxa marginal | 1 | Radziemska, E. The effect of temperature on the power drop in crystalline silicon solar cells. *Renewable Energy*, v. 28, n. 1, p. 1–12, 2003 |
| Thermal | Água | 81–86% de redução de capacidade utilizável sob estresse hídrico | Outcome total sob estresse | 1 | Van Vliet et al. (mesma fonte que hidro–água) |
| Thermal | Calor | −0,12 %/°C a −0,44 %/°C em eficiência ou produção | Taxa marginal | 1 | Ibrahim, S. M. A.; Attia, S. I. The influence of condenser cooling seawater fouling on the thermal performance of a nuclear power plant. *Annals of Nuclear Energy*, v. 76, p. 421–430, 2015. DOI: 10.1016/j.anucene.2014.10.018; Durmayaz, A.; Sogut, O. S. (2006) *(verificação primária pendente — ver nota abaixo)* |

**Nota — verificação bibliográfica pendente (thermal–calor):** Durmayaz, A.
e Sogut, O. S. (2006) são conhecidos apenas via citação secundária. Os
valores exatos do coeficiente e o título completo do artigo primário
precisam ser verificados antes da submissão do manuscrito. Esta
verificação é uma tarefa bibliográfica, não uma decisão metodológica.

**Decisão confirmada:** eólica–calor é tratada como coeficiente linear
equivalente. A resposta real é em forma de degrau; a simplificação é
declarada explicitamente no manuscrito.

**Decisão confirmada:** carvão e outros termoeléctricos são fusionados no
bucket `thermal` para derivação de pesos de água e calor. O mecanismo
físico é o mesmo (dependência de água de refrigeração e sensibilidade
à temperatura dessa água). A fusão cria uma tensão na curva de idade
da resiliência, tratada na Seção 7.

---

## 7. Fator de resiliência

$$Resilience_i = \max\!\left(
age_{factor,i} \times fuel_{factor,i} \times event_{factor,i},\ 0.1
\right)$$

Normalizado pelo teto empiricamente observado dentro de cada par
país–cenário, recomputado dentro de cada iteração de Monte Carlo.

### 7.1 Fator de idade (`age_factor`)

| Tecnologia | Curva | Fonte |
|---|---|---|
| Eólica | 1,6 %/ano | Literatura existente, retida |
| Solar | 0,6 %/ano | Literatura existente, retida |
| Hidro | ~0,5–0,6 %/ano | Turner, S. W. D. et al. *Nature Communications*, 2024 — declínio cumulativo de 23% em 610 plantas nos EUA entre 1980 e 2022; apenas 21% desse declínio é atribuível à disponibilidade hídrica, mantendo este fator distinto do hazard de estresse hídrico já capturado separadamente |
| Thermal | *Verificação pós-dados — item V1* | Usinas a carvão perdem eficiência com a idade; usinas a gás natural ganham eficiência com a idade no mesmo período (estudo US, 2001–2018) — sinais opostos dentro do bucket fusionado |

### 7.2 Fator de evento (`event_factor`)

Atualmente fixo em 1,0 para todos os ativos (a geocodificação pontual do
EM-DAT cobre apenas 10,7% dos eventos na região de estudo).

Substituição proposta: fator de frequência de eventos por país (ou nível
administrativo mais fino onde o EM-DAT suportar), construído a partir dos
eventos EM-DAT com os critérios padrão de inclusão (≥ 10 mortes,
≥ 100 afetados, ou emergência declarada). Essa substituição troca
granularidade espacial (não diferencia ativos dentro do mesmo país) por
cobertura completa em vez de uma amostra pequena e não representativa.

A confirmação desta substituição é verificação pós-dados (item V2):
depende de avaliar a cobertura e geocodificação real do EM-DAT para
os três países após a reconstrução da camada de aquisição.

### 7.3 Fator de combustível (`fuel_factor`)

Representa diferenças de robustez estrutural por tecnologia não capturadas
pela idade nem pelo hazard diretamente medido. A justificativa original
dos valores deste fator foi construída parcialmente com referência ao SLR,
que está fora do escopo ativo. Os valores precisam ser revisados e
rejustificados exclusivamente a partir dos hazards água e calor, ou o
fator precisa ser removido se essa justificativa não puder ser construída.

Esta revisão é verificação pós-dados (item V5).

---

## 8. Incerteza — Monte Carlo

N = 1.000 iterações, perturbando pesos calibrados e subfatores de
resiliência em magnitudes de ±10 %, ±20 % e ±30 %.

A perturbação é uniforme entre tiers, não tier-dependente. O tier já
codifica o nível de confiança no momento da derivação do peso; variar
também a magnitude de perturbação por tier testaria dois efeitos através
de um único parâmetro.

O NAES é recomputado dentro de cada iteração — seu intervalo de confiança
reflete a mesma incerteza de parâmetros que a métrica de estabilidade de
ranking dos ativos.

---

## 9. Verificações pós-dados

Estes itens não podem ser resolvidos por raciocínio antecipado. Cada um
tem um critério explícito de decisão a ser aplicado após a reconstrução
da camada de aquisição e processamento e visualização dos dados reais.
Nenhum código de índice é escrito antes de todos estarem resolvidos.

**V1 — Curva de idade do bucket thermal**
- **O que observar:** distribuição de carvão versus gás natural dentro do
  bucket `thermal` por país, em `gem_validated_plants_{país}.csv`.
- **Critério:** se a proporção carvão/gás for suficientemente homogênea
  entre os três países para que uma curva média não inverta rankings, uma
  curva média documentada é aceitável. Se a heterogeneidade entre países
  for grande o suficiente para inverter rankings, o bucket thermal recebe
  sub-curvas por combustível específico apenas para o fator de idade,
  mantendo a fusão nos pesos de hazard.

**V2 — Fator de evento (substituição do valor fixo 1,0)**
- **O que observar:** cobertura e geocodificação do EM-DAT para Brasil,
  Portugal e Índia — número de eventos com localização administrativa
  utilizável versus total elegível pelos critérios de inclusão.
- **Critério:** se a cobertura for suficiente para construir um fator por
  nível administrativo (estado/distrito), usar esse nível. Se a cobertura
  suportar apenas o nível país, usar país. Se a cobertura for insuficiente
  para qualquer nível, manter 1,0 e declarar como limitação.

**V3 — SSP3-7.0 como cenário intermediário**
- **O que verificar:** disponibilidade de `gfdl_esm4` com `ssp370` no
  Copernicus CDS (consulta de catálogo de API, não análise de dados).
  Verificar também para o segundo GCM escolhido em V4.
- **Critério:** se disponível para ambos os GCMs, incluir SSP3-7.0 e
  alinhar com o cenário Aqueduct `bau` já disponível. Se disponível para
  apenas um GCM, avaliar se o desalinhamento é aceitável ou se SSP3-7.0
  fica fora. A inclusão altera o pool de min-max de calor de 2 para 3
  cenários, mudando o denominador de normalização de todos os pixels —
  esta consequência deve ser considerada na decisão.

**V4 — Escolha e cobertura do segundo GCM**
- **O que verificar:** quais modelos CMIP6 têm `ssp126` e `ssp585`
  disponíveis no Copernicus CDS para os três países, com resolução e
  período compatíveis com o pipeline existente.
- **Critério:** selecionar o modelo com maior divergência estrutural
  em relação ao `GFDL-ESM4` (diferente família de parametrização de
  convecção ou ciclo hidrológico), cobrindo os três países. Se nenhum
  modelo cobre os três países com qualidade equivalente, cobrir apenas
  os casos de maior exposição a calor e declarar a limitação.

**V5 — Fator de combustível (`fuel_factor`)**
- **O que revisar:** literatura de robustez estrutural por tecnologia
  para os hazards água e calor, independentemente de SLR.
- **Critério:** se valores defensáveis puderem ser derivados para cada
  bucket (`hydro`, `wind`, `solar`, `thermal`) a partir exclusivamente
  de água e calor, o fator é mantido com os novos valores. Se a revisão
  não produzir justificativa defensável, o fator é removido da fórmula
  de resiliência e a simplificação é declarada no manuscrito.

**V6 — Denominador do NAES (base computável vs. capacidade total)**
- **O que observar:** fração de ativos GEM com coordenadas válidas e
  `commissioning_year` disponível sobre a capacidade total declarada,
  por país.
- **Critério:** se a fração computável for consistentemente alta e
  simétrica entre os três países (diferença < 5 pontos percentuais),
  a limitação é declarada em nota de rodapé. Se a assimetria entre
  países for maior, um sensitivity check com denominador alternativo
  (capacidade total declarada, imputando hazard médio do país para
  ativos sem coordenada) é executado e reportado como resultado
  secundário.

---

## 10. O que o GEAR não faz (limites de escopo declarados)

Estes limites são declarados no manuscrito, não omitidos.

- **SLR:** excluído por falta de base empírica defensável para a frota
  terrestre estudada. Extensão natural quando coeficientes por tecnologia
  para inundação costeira e ressaca estiverem disponíveis.
- **Ativos planejados e em construção:** apenas ativos operacionais
  entram no pipeline principal. Ativos anunciados ou em construção não
  são incluídos.
- **Transmissão e distribuição:** apenas geração. A exposição de linhas
  de transmissão e subestações não é modelada.
- **Eventos extremos agudos:** o framework modela exposição crônica
  (condições médias 2041–2070). Eventos de cauda (ondas de calor
  pontuais, secas extremas interanuais) não são capturados.
- **Bias correction do GCM:** os rasters de calor usam a saída do modelo
  diretamente, sem correção de viés sistemático. A sensibilidade a esse
  artefato é parcialmente capturada pelo segundo GCM obrigatório, mas
  não eliminada.
- **Capacidade de adaptação:** o fator de resiliência captura
  características estruturais do ativo (idade, histórico de eventos),
  não capacidade prospectiva de adaptação de operadores ou reguladores.