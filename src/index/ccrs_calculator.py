"""
CCRS — termo ``Hazard_{i,s}`` por planta, cenário e GCM.

Este módulo calcula **apenas** o termo de hazard do Climate Change Risk Score
(``docs/ARCHITECTURE.md`` Seção 5.1, ``analysis/climate_risk_score_spec.md``
Seção 2):

    Hazard_{i,s} = w_water[bucket]·water_sub_{i,s} + w_heat[bucket]·Tlog(heat_{i,s})

    water_sub_{i,s} = 0.4164·Tlog(ws) + 0.2505·Tlin(sv) + 0.3331·Tlin(iv)

O score completo ``CCRS_{i,s} = Hazard_{i,s} × age_factor_i × EventMultiplier_c``
**não** é montado aqui: o mapeamento das curvas %/ano do ``age_factor`` para um
multiplicador ≥ 1 é o item aberto D da spec (``ARCHITECTURE.md`` Seção 10) —
ponto de parada, não lacuna a preencher sozinho. ``EventMultiplier_c`` tem forma
fechada (Seção 7.2) mas também é aplicado na etapa de montagem, fora deste
módulo. Bandas de risco (WaterRiskBand / HeatRiskBand) são outra etapa.

--------------------------------------------------------------------------
Os quatro termos de hazard e o que NÃO são
--------------------------------------------------------------------------
``ws``, ``sv`` e ``iv`` são os **três indicadores WRI Aqueduct 4.0** de risco
hídrico, não precipitação nem SPEI:

* ``ws``  — *water stress*: razão retirada/disponibilidade (coluna
  ``{cenário}50_ws_x_r`` do Aqueduct), rasterizada por
  ``src/processors/water_stress_processor.py`` (sentinela WRI 9999 já
  substituída pelo ``country_max`` real no raster ``water_stress_raw_*``).
* ``sv``  — *seasonal variability*: coeficiente de variação intra-anual da
  oferta de água azul (coluna ``{cenário}50_sv_x_r``), rasterizado por
  ``src/processors/water_variability_processor.py`` (raster
  ``seasonal_variability_raw_*``).
* ``iv``  — *interannual variability*: coeficiente de variação interanual da
  mesma oferta (coluna ``{cenário}50_iv_x_r``), mesmo processor (raster
  ``interannual_variability_raw_*``).

Não há termo de precipitação/SPEI no CCRS atual: um termo de seca (SPEI) é o
item aberto F da spec — os downloads de ``pr``/``tas`` já existem
(``cds_precipitation_downloader``) mas nenhum ``spei_processor`` foi escrito,
e ``sv``/``iv`` **não** substituem esse termo (medem variabilidade da oferta,
não déficit hídrico climático).

* ``heat`` — média de dias/ano com tasmax > 40 °C (``extreme_heat_days_*``,
  passthrough do ``cds_tasmax_downloader``), por GCM.

``wd`` (*water depletion*) é **excluído** do cálculo: o Spearman plant-level
``ws × wd`` é 0.98–0.998 nos três países
(``analysis/aqueduct_indicator_correlation.md``), então ``wd`` não carrega
informação de ranking independente de ``ws``. Incluir os dois duplicaria o
canal de nível de estresse hídrico. ``ws`` é mantido (indicador-título do WRI,
já no pipeline); ``wd`` é descartado.

--------------------------------------------------------------------------
Transformações e bounds
--------------------------------------------------------------------------
* ``Tlog(x) = MinMax(log1p(x))`` — aplicada a ``ws`` e ``heat`` (skew direito
  severo em nível de planta).
* ``Tlin(x) = MinMax(x)``          — aplicada a ``sv`` e ``iv`` (quase
  simétricas; log1p sobre-corrigiria e poderia inverter a ordem).
* **Bounds globais**: um par ``(min, max)`` por termo, agrupando os 3 países ×
  3 cenários (nunca por país, nunca por cenário). Essa é a propriedade que faz
  um CCRS de 0.4 significar a mesma exposição em Lisboa e em Chennai.
  - ``ws``/``sv``/``iv``: os rasters de água não dependem do GCM, então há um
    único par por termo, agrupando as plantas que interceptam alguma bacia.
  - ``heat``: um par **por GCM**. As magnitudes de MIROC6 rodam ~10–100× as do
    GFDL-ESM4; agrupar os dois num bound só seria um blend inter-modelo. Ver
    "GCM" abaixo.
* Os bounds são **congelados** em ``FROZEN_BOUNDS`` (item aberto G da spec:
  "constante fixa e documentada, não recomputada por rodada"). ``main`` e o
  cálculo padrão usam os valores congelados; ``compute_global_bounds`` os
  recalcula a partir dos dados em disco. ``tests/test_ccrs_calculator.py``
  compara os dois e **falha** se divergirem — atualizar ``FROZEN_BOUNDS``
  exige revisão manual explícita.

--------------------------------------------------------------------------
Pesos por bucket tecnológico (``ARCHITECTURE.md`` Seção 5.3, fechado)
--------------------------------------------------------------------------
    bucket    w_water  w_heat
    hydro      1.00     0.00   (calor já dentro do estresse hídrico via evaporação de reservatório)
    thermal    0.75     0.25   (Van Vliet água ~ordem de grandeza acima da taxa marginal de calor)
    wind       0.00     1.00   (sem mecanismo hídrico físico plausível)
    solar      0.00     1.00   (idem)

Para ``wind``/``solar`` todo o lado da água — ``ws``, ``sv`` E ``iv`` — zera
junto. Os pesos internos ``(0.4164, 0.2505, 0.3331)`` vêm da largura das
categorias WRI Aqueduct 4.0 (``w_k ∝ 1/τ_k``, spec §8.1), não da matriz de
magnitude da Seção 6.1.

--------------------------------------------------------------------------
GCM (``ARCHITECTURE.md`` Seção 5.4)
--------------------------------------------------------------------------
GFDL-ESM4 é o valor primário de toda figura citada do CCRS. MIROC6 é painel de
sensibilidade, mantido em campo/coluna separado — **nunca** média nem blend
50/50 com GFDL-ESM4. ``compute_hazard_by_gcm`` devolve uma coluna
``hazard`` por GCM lado a lado, sem combiná-las.

--------------------------------------------------------------------------
Capacidade
--------------------------------------------------------------------------
Capacidade não entra em ``Hazard_{i,s}`` nem em ``CCRS_{i,s}`` — só no
roll-up por país (``ARCHITECTURE.md`` Seção 5.5). Este módulo não agrega
capacidade; ``computable_base`` está aqui só para que qualquer roll-up futuro
use a base computável do V6 (coordenada válida + ``commissioning_year``),
nunca ``capacity_mw`` diretamente.

Standalone: ``python -m src.index.ccrs_calculator`` a partir da raiz do
projeto. Lê os rasters brutos processados e
``gem_validated_plants_{país}.csv``; escreve
``data/outputs/tables/ccrs_hazard.csv``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol

from src.config import (
    AQUEDUCT_SCENARIO_FOR_CMIP6,
    ASSETS_PROCESSED,
    COUNTRIES,
    OUTPUT_TABLES,
)
from src.downloaders.cds_tasmax_downloader import configured_models
from src.processors.heat_stress_processor import raw_raster_path as heat_raw_path
from src.processors.water_stress_processor import raw_raster_path as ws_raw_path
from src.processors.water_variability_processor import raw_raster_path as var_raw_path

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Termos e transformações
# --------------------------------------------------------------------------
HAZARD_TERMS = ("ws", "heat", "sv", "iv")
LOG_TERMS = frozenset({"ws", "heat"})   # log1p → Min-Max
LIN_TERMS = frozenset({"sv", "iv"})     # Min-Max linear

# ``wd`` (water depletion) fica de fora: redundante de ranking com ``ws``
# (Spearman 0.98–0.998, analysis/aqueduct_indicator_correlation.md).
EXCLUDED_INDICATORS = ("wd",)

# Cenários Aqueduct (lado da água) e o cenário CMIP6 pareado (lado do calor),
# pela identidade SSP de config.AQUEDUCT_SCENARIO_FOR_CMIP6.
WATER_SCENARIOS = ("opt", "bau", "pes")
WATER_TO_HEAT = {ws: hs for hs, ws in AQUEDUCT_SCENARIO_FOR_CMIP6.items()}

# --------------------------------------------------------------------------
# Pesos internos do water_sub — largura das categorias WRI Aqueduct 4.0
# (spec §8.1). w_k ∝ 1/τ_k, τ_k = limiar High → Extremely-High do indicador.
# --------------------------------------------------------------------------
WRI_TOP_THRESHOLD = {"ws": 0.80, "sv": 1.33, "iv": 1.00}


def _derive_within_water_weights() -> dict[str, float]:
    inv = {k: 1.0 / WRI_TOP_THRESHOLD[k] for k in ("ws", "sv", "iv")}
    total = sum(inv.values())
    return {k: inv[k] / total for k in ("ws", "sv", "iv")}


WITHIN_WATER_WEIGHTS = _derive_within_water_weights()

# Valores publicados na spec §8.1 / ARCHITECTURE.md §5.1. A derivação acima
# deve reproduzi-los — trava contra edição acidental de WRI_TOP_THRESHOLD.
_PUBLISHED_WITHIN_WATER = {"ws": 0.4164, "sv": 0.2505, "iv": 0.3331}
assert all(
    abs(WITHIN_WATER_WEIGHTS[k] - _PUBLISHED_WITHIN_WATER[k]) < 5e-5
    for k in _PUBLISHED_WITHIN_WATER
), f"within-water weights {WITHIN_WATER_WEIGHTS} divergem da spec §8.1"

# --------------------------------------------------------------------------
# Pesos água/calor por bucket tecnológico (ARCHITECTURE.md §5.3, fechado).
# --------------------------------------------------------------------------
BUCKETS = ("hydro", "thermal", "wind", "solar")
BUCKET_WEIGHTS = {
    "hydro":   {"water": 1.00, "heat": 0.00},
    "thermal": {"water": 0.75, "heat": 0.25},
    "wind":    {"water": 0.00, "heat": 1.00},
    "solar":   {"water": 0.00, "heat": 1.00},
}
assert all(
    abs(w["water"] + w["heat"] - 1.0) < 1e-12 for w in BUCKET_WEIGHTS.values()
), "w_water + w_heat deve somar 1 por bucket"

# --------------------------------------------------------------------------
# Bounds globais congelados (item aberto G da spec).
#
# Derivados de compute_global_bounds() sobre os dados em disco no snapshot
# abaixo. NÃO editar à mão sem revisão manual explícita: o teste de regressão
# em tests/test_ccrs_calculator.py recalcula e compara, e falha se divergir.
# Formato: bounds RAW (pré-log1p) (min, max). Tlog aplica log1p a dado e bound.
#   - ws/sv/iv: um par por termo (rasters de água independem do GCM).
#   - heat:     um par por GCM (MIROC6 ~10–100× GFDL; nunca no mesmo pool).
# --------------------------------------------------------------------------
BOUNDS_DATA_SNAPSHOT = "2026-09-04"
FROZEN_BOUNDS: dict[str, object] = {
    "ws": (3.3699998880365456e-07, 29.883182525634766),
    "sv": (0.060949064791202545, 1.6313080787658691),
    "iv": (0.1379709094762802, 2.4342257976531982),
    "heat": {
        "gfdl_esm4": (0.0, 159.89999389648438),
        "miroc6": (0.0, 274.20001220703125),
    },
}


class BoundsRegressionError(RuntimeError):
    """Recomputo dos bounds globais divergiu de ``FROZEN_BOUNDS``.

    Não é para ser silenciado. Se os dados em disco mudaram de propósito
    (novo país, novo cenário, reprocessamento de raster), atualize
    ``FROZEN_BOUNDS`` e ``BOUNDS_DATA_SNAPSHOT`` **deliberadamente**, com o
    diff de números registrado no commit — nunca deixe o teste recalcular e
    aceitar em silêncio.
    """


# --------------------------------------------------------------------------
# Rasters e amostragem
# --------------------------------------------------------------------------
def raster_path(term: str, country: str, water_scenario: str, model: str) -> Path:
    """Caminho do raster BRUTO processado para um termo/país/cenário(/GCM).

    ``model`` só é usado por ``heat``; os rasters de água ignoram-no.
    """
    if term == "ws":
        return ws_raw_path(country, water_scenario)
    if term == "sv":
        return var_raw_path(country, water_scenario, "sv")
    if term == "iv":
        return var_raw_path(country, water_scenario, "iv")
    if term == "heat":
        return heat_raw_path(country, model, WATER_TO_HEAT[water_scenario])
    raise ValueError(
        f"termo desconhecido {term!r} (esperado um de {HAZARD_TERMS}; "
        f"{EXCLUDED_INDICATORS} é excluído do CCRS por design)"
    )


def sample_raster(path: Path, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    """Amostra de vizinho mais próximo do raster em cada (lon, lat). Pontos
    fora da grade ou sobre nodata voltam como NaN."""
    with rasterio.open(path) as src:
        band = src.read(1).astype("float64")
        nod = src.nodata
        if nod is not None and not np.isnan(nod):
            band[band == nod] = np.nan
        rows, cols = rowcol(src.transform, np.asarray(lons), np.asarray(lats))
        rows, cols = np.asarray(rows), np.asarray(cols)
        h, w = band.shape
        inside = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)
        out = np.full(np.shape(lons), np.nan, dtype="float64")
        out[inside] = band[rows[inside], cols[inside]]
    return out


def load_plants(country: str) -> pd.DataFrame:
    """Plantas validadas do país: ``plant_name``, ``lon``/``lat``,
    ``capacity_mw``, ``commissioning_year`` e ``bucket`` (de
    ``fuel_type_bucket``). Todas têm coordenada (V6)."""
    df = pd.read_csv(ASSETS_PROCESSED / f"gem_validated_plants_{country}.csv")
    return pd.DataFrame({
        "country": country,
        "plant_name": df["plant_name"].astype("string"),
        "lon": pd.to_numeric(df["lon"], errors="coerce"),
        "lat": pd.to_numeric(df["lat"], errors="coerce"),
        "capacity_mw": pd.to_numeric(df["capacity_mw"], errors="coerce"),
        "commissioning_year": pd.to_numeric(df["commissioning_year"], errors="coerce"),
        "bucket": df["fuel_type_bucket"].astype("string"),
    })


def sample_terms(model: str) -> pd.DataFrame:
    """Uma linha por (país, planta, cenário de água) com os quatro valores
    BRUTOS de termo amostrados para ``model`` no lado do calor."""
    parts = []
    for country in COUNTRIES:
        plants = load_plants(country)
        lons = plants["lon"].to_numpy("float64")
        lats = plants["lat"].to_numpy("float64")
        for water_scen in WATER_SCENARIOS:
            part = plants.copy()
            part["water_scenario"] = water_scen
            part["heat_scenario"] = WATER_TO_HEAT[water_scen]
            for term in HAZARD_TERMS:
                part[term] = sample_raster(
                    raster_path(term, country, water_scen, model), lons, lats
                )
            parts.append(part)
    return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------
# Transformações e bounds
# --------------------------------------------------------------------------
def transform_term(term: str, raw: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """``Tlog`` para ws/heat, ``Tlin`` para sv/iv. ``lo``/``hi`` são bounds
    BRUTOS; para ``Tlog`` o log1p é aplicado a dado e bound antes do Min-Max.
    Domínio degenerado (``hi <= lo``) → zeros."""
    raw = np.asarray(raw, "float64")
    if term in LOG_TERMS:
        x, a, b = np.log1p(raw), np.log1p(lo), np.log1p(hi)
    elif term in LIN_TERMS:
        x, a, b = raw, float(lo), float(hi)
    else:
        raise ValueError(f"termo desconhecido {term!r}")
    if b <= a:
        return np.zeros_like(x)
    return np.clip((x - a) / (b - a), 0.0, 1.0)


def compute_global_bounds(models: list[str] | None = None) -> dict[str, object]:
    """Recalcula os bounds globais a partir dos rasters em disco.

    Sobre as linhas com bucket tecnológico conhecido, países e cenários
    agrupados:

    * ``ws``/``sv``/``iv``: um par ``(min, max)`` por termo, sobre as plantas
      cujo termo é finito (interceptam alguma bacia). Os rasters de água
      independem do GCM — amostrar com qualquer GCM configurado dá o mesmo
      resultado; ``models[0]`` é usado por conveniência.
    * ``heat``: um par por GCM, sobre as plantas cujo ``heat`` é finito para
      aquele GCM.

    Estrutura idêntica a ``FROZEN_BOUNDS``.
    """
    models = models or configured_models()
    frames = {m: sample_terms(m) for m in models}
    frames = {m: f[f["bucket"].isin(BUCKETS)] for m, f in frames.items()}

    def _minmax(frame: pd.DataFrame, term: str) -> tuple[float, float]:
        col = frame.loc[frame[term].notna(), term].to_numpy("float64")
        return float(col.min()), float(col.max())

    water = frames[models[0]]
    out: dict[str, object] = {t: _minmax(water, t) for t in ("ws", "sv", "iv")}
    out["heat"] = {m: _minmax(f, "heat") for m, f in frames.items()}
    return out


def _bounds_close(a: dict[str, object], b: dict[str, object], atol: float = 1e-4) -> bool:
    if set(a) != set(b):
        return False
    for term in ("ws", "sv", "iv"):
        if not np.allclose(a[term], b[term], atol=atol, rtol=0):
            return False
    heat_a, heat_b = a["heat"], b["heat"]
    if set(heat_a) != set(heat_b):
        return False
    return all(
        np.allclose(heat_a[m], heat_b[m], atol=atol, rtol=0) for m in heat_a
    )


def assert_frozen_bounds_current(models: list[str] | None = None) -> dict[str, object]:
    """Recalcula e compara com ``FROZEN_BOUNDS``; levanta
    ``BoundsRegressionError`` se divergir. Devolve os bounds recalculados."""
    live = compute_global_bounds(models)
    if not _bounds_close(live, FROZEN_BOUNDS):
        raise BoundsRegressionError(
            "bounds recalculados divergem de FROZEN_BOUNDS "
            f"(snapshot {BOUNDS_DATA_SNAPSHOT}).\n  congelado: {FROZEN_BOUNDS}\n"
            f"  recalculado: {live}\n"
            "Revisão manual obrigatória antes de atualizar a constante."
        )
    return live


def _term_bounds(term: str, model: str, bounds: dict[str, object]) -> tuple[float, float]:
    if term == "heat":
        return tuple(bounds["heat"][model])  # type: ignore[index]
    return tuple(bounds[term])  # type: ignore[return-value]


# --------------------------------------------------------------------------
# Hazard
# --------------------------------------------------------------------------
def water_sub(t_ws: np.ndarray, t_sv: np.ndarray, t_iv: np.ndarray) -> np.ndarray:
    """``0.4164·Tlog(ws) + 0.2505·Tlin(sv) + 0.3331·Tlin(iv)`` — sobre os
    termos já transformados. NaN se algum termo for NaN."""
    w = WITHIN_WATER_WEIGHTS
    return w["ws"] * np.asarray(t_ws) + w["sv"] * np.asarray(t_sv) + w["iv"] * np.asarray(t_iv)


def hazard(bucket: np.ndarray, water_sub_val: np.ndarray, t_heat: np.ndarray) -> np.ndarray:
    """``w_water[bucket]·water_sub + w_heat[bucket]·Tlog(heat)``.

    Um lado com peso 0 é descartado antes da multiplicação, então um
    ``water_sub`` NaN não contamina ``wind``/``solar`` (nem o ``heat`` NaN
    contamina ``hydro``). Onde o lado tem peso > 0, um NaN propaga — a planta
    fica sem hazard nesse cenário, o comportamento correto.
    """
    bucket = np.asarray(bucket, dtype=object)
    w_water = np.array([BUCKET_WEIGHTS[b]["water"] if b in BUCKET_WEIGHTS else np.nan
                        for b in bucket], dtype="float64")
    w_heat = np.array([BUCKET_WEIGHTS[b]["heat"] if b in BUCKET_WEIGHTS else np.nan
                       for b in bucket], dtype="float64")
    water_sub_val = np.asarray(water_sub_val, "float64")
    t_heat = np.asarray(t_heat, "float64")

    # Só multiplica onde o peso é > 0: o lado zerado nunca toca um NaN, e o
    # lado com peso propaga NaN normalmente (planta sem hazard nesse cenário).
    water_part = np.zeros(len(w_water), dtype="float64")
    heat_part = np.zeros(len(w_heat), dtype="float64")
    mw = w_water > 0.0
    mh = w_heat > 0.0
    water_part[mw] = w_water[mw] * water_sub_val[mw]
    heat_part[mh] = w_heat[mh] * t_heat[mh]
    out = water_part + heat_part
    # bucket desconhecido → NaN (não deveria acontecer: sample já filtra)
    out[np.isnan(w_water) | np.isnan(w_heat)] = np.nan
    return out


def compute_hazard(model: str, bounds: dict[str, object] | None = None) -> pd.DataFrame:
    """``Hazard_{i,s}`` por planta × cenário para um GCM.

    Uma linha por (país, planta, cenário) com bucket conhecido. Colunas:
    identificação, ``bucket``, ``capacity_mw``, ``commissioning_year``, os
    quatro termos transformados ``T_*``, ``water_sub``, ``hazard``, ``model``.
    Usa ``FROZEN_BOUNDS`` por padrão.
    """
    bounds = bounds or FROZEN_BOUNDS
    df = sample_terms(model)
    df = df[df["bucket"].isin(BUCKETS)].reset_index(drop=True)

    tt = {}
    for term in HAZARD_TERMS:
        lo, hi = _term_bounds(term, model, bounds)
        tt[term] = transform_term(term, df[term].to_numpy("float64"), lo, hi)

    ws_sub = water_sub(tt["ws"], tt["sv"], tt["iv"])
    haz = hazard(df["bucket"].to_numpy(), ws_sub, tt["heat"])

    out = df[[
        "country", "plant_name", "water_scenario", "heat_scenario",
        "bucket", "capacity_mw", "commissioning_year",
    ]].copy()
    for term in HAZARD_TERMS:
        out[f"T_{term}"] = tt[term]
    out["water_sub"] = ws_sub
    out["hazard"] = haz
    out["model"] = model
    return out


def compute_hazard_by_gcm(
    models: list[str] | None = None, bounds: dict[str, object] | None = None
) -> pd.DataFrame:
    """``Hazard`` de cada GCM lado a lado, uma coluna ``hazard_{model}`` por
    GCM — **nunca** combinadas. GFDL-ESM4 é a coluna primária; MIROC6 é
    painel de sensibilidade (``ARCHITECTURE.md`` §5.4).
    """
    models = models or configured_models()
    key = ["country", "plant_name", "water_scenario", "heat_scenario", "bucket",
           "capacity_mw", "commissioning_year"]
    merged: pd.DataFrame | None = None
    for m in models:
        h = compute_hazard(m, bounds=bounds)[key + ["hazard"]].rename(
            columns={"hazard": f"hazard_{m}"}
        )
        merged = h if merged is None else merged.merge(h, on=key, how="outer")
    return merged


# --------------------------------------------------------------------------
# Base computável (V6) — para qualquer roll-up de capacidade futuro
# --------------------------------------------------------------------------
def computable_base(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra para a base computável do V6: coordenada válida (todas têm) +
    ``commissioning_year`` presente. Qualquer soma de capacidade no roll-up
    por país (``ARCHITECTURE.md`` §5.5) parte daqui, nunca de ``capacity_mw``
    sobre a frota inteira."""
    return df[df["commissioning_year"].notna()]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-bounds", action="store_true",
        help="recalcula os bounds globais e compara com FROZEN_BOUNDS; não escreve nada",
    )
    parser.add_argument("--out", type=Path, default=OUTPUT_TABLES / "ccrs_hazard.csv")
    args = parser.parse_args()

    if args.check_bounds:
        try:
            live = assert_frozen_bounds_current()
        except BoundsRegressionError as exc:
            logger.error(str(exc))
            return 1
        logger.info("bounds congelados conferem com os dados (%s): %s",
                    BOUNDS_DATA_SNAPSHOT, live)
        return 0

    wide = compute_hazard_by_gcm()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(args.out, index=False)
    logger.info("escrito %s (%d linhas planta×cenário)", args.out, len(wide))

    haz_cols = [c for c in wide.columns if c.startswith("hazard_")]
    for c in haz_cols:
        s = wide[c].dropna()
        logger.info("%s: n=%d, p50=%.4f, p95=%.4f, max=%.4f",
                    c, len(s), s.median(), s.quantile(0.95), s.max())
    base = computable_base(wide)
    logger.info("base computável (commissioning_year presente): %d / %d linhas",
                len(base), len(wide))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
