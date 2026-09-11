"""Camada de índice do GEAR.

Em reconstrução para a metodologia GEAR v3
(``docs/rework/GEAR_v3_methodology_nature_format.md``,
``docs/rework/GEAR_v3_work_plan.md``): o índice único CCRS (Climate Change
Risk Score) é retirado -- ``src/index/risk_calculator.py`` computa
``Risk_i,h`` por hazard (Equação 1, Fase 1, fechada -- ver
``docs/DECISIONS.md``). Módulos ainda não migrados para a v3
(``risk_bands.py``, ``monte_carlo.py``, ``event_multiplier.py`` como núcleo
de Hazard/Risk) permanecem no repositório mas não são mais alcançáveis a
partir de ``risk_calculator.py`` -- aguardam as Fases 3/4/5/6 do plano.
"""
