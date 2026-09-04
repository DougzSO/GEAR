"""
Monte Carlo sensitivity analysis for the CCRS (spec item J).

Scope approved by Douglas (this task's brief), unchanged in mechanics from
the pre-SPEI design: N = 1000 iterations per magnitude, three magnitudes
(+/-10 / 20 / 30 %), one full CCRS + band-report recomputation per draw,
independent RNG per country keyed off ``config.RANDOM_SEED``
(reproducible), output as point estimate + percentile CI (2.5 / 50 / 97.5)
per country x scenario x band -- ARCHITECTURE.md Section 8.

--------------------------------------------------------------------------
Perturbed parameters (exactly the three approved groups)
--------------------------------------------------------------------------
A. Thermal bucket water/heat ratio -- uniform relative perturbation
   (+/- magnitude) independently on ``w_water`` and ``w_heat``, then
   renormalised. **Scope note, post-SPEI**: the approved brief predates the
   SPEI integration and only names a 2-way ``w_water``/``w_heat`` pair
   summing to 1. ``ccrs_calculator.BUCKET_WEIGHTS["thermal"]`` is now a
   3-way ``(water, heat, drought)`` triple. This module's reading -- stated
   explicitly, not silently assumed -- is: perturb the water:heat ratio
   only, renormalising water+heat to fill ``1 - w_drought`` while holding
   ``w_drought`` at its production value (0.30, unperturbed, since it is
   not named in the approved scope). *Point to validate with Douglas.*
B. ``age_factor`` retention rates -- coal decay rate drawn **uniformly over
   the literature range** 0.19-0.44 %/yr (Sagaf 2020), not a percentage
   perturbation around the central value; wind rate uniformly over
   0.3-0.5 %/yr; hydro rate uniformly over 0.5-0.6 %/yr. Coal overhaul cycle
   (5 yr) and recovery fraction (70 %) stay fixed. Solar and gas/oil-gas are
   out of scope (solar has no literature range given; gas/oil-gas has no
   rate to perturb) and are held at their production constants.
C. ``EventMultiplier`` amplitude ``k`` (0.5) -- same uniform relative
   mechanism as A.

**Explicitly out of scope** (Douglas's decision, not renegotiated here):
``ccrs_calculator.FROZEN_BOUNDS`` (every term, including the new ``spei``
entry) and every ``risk_bands.py`` cut (``WATER_BAND_CUTS``, the heat
percentile cuts). Both are structural constants locked by their own
regression tests; this module never calls a function that could recompute
or perturb them, and a test asserts they are byte-identical before and
after a full simulation run.

--------------------------------------------------------------------------
RNG design -- independent stream per COUNTRY (not country x scenario)
--------------------------------------------------------------------------
The brief specifies a stream "per country/scenario", mirroring the old
SCI/NAES design (``energy_risk_assessment/src/validation/sensitivity_analysis.py``,
``zlib.crc32`` + ``numpy.random.SeedSequence`` keyed off ``RANDOM_SEED``).
That old design's per-country-scenario draws fed a per-country-scenario
resilience-ceiling recomputation that no longer exists. None of the three
approved parameter groups here are scenario-dependent quantities: a
country's coal-decay-rate uncertainty, thermal water/heat ratio and
``EventMultiplier`` amplitude do not depend on which emissions scenario is
being scored, and the production pipeline applies one ``EventMultiplier_c``
identically across a country's three scenario rows
(``event_multiplier.apply_to_hazard``). Keying an independent stream by
scenario as well would inject non-physical scenario-dependent noise into a
scenario-invariant judgment call, and would silently break that production
invariant inside the simulation.

This module therefore uses **one independent stream per country**
(``zlib.crc32(country) + RANDOM_SEED``, one ``SeedSequence`` spawn key),
reused across that country's water_scenario rows within an iteration. This
still satisfies the mechanical requirement and its test (perturbing one
country's stream never moves another country's draws) and the
reproducibility requirement (same seed -> same sequence), while keeping the
scenario-invariant parameters scenario-invariant inside the simulation too.
*Point to validate with Douglas*, same status as the item-A scope note above.

--------------------------------------------------------------------------
What "recomputing the full CCRS + band report per draw" means here
--------------------------------------------------------------------------
The raster-derived, per-term-transformed inputs (``water_sub``, ``T_heat``,
``T_spei`` -- from ``ccrs_calculator.compute_hazard``, using the frozen,
UNPERTURBED ``FROZEN_BOUNDS``) do not depend on any of the three perturbed
parameter groups, so they are computed **once** (not one raster read per
iteration -- 3000 repeats of the raster I/O in ``compute_hazard`` would be
computationally infeasible, see the timing note below). Every iteration
recomputes, from those fixed inputs, the full chain that DOES depend on the
perturbed parameters: per-plant ``age_factor`` (bucket/fuel retention
curves, vectorised), the per-bucket Hazard weights (thermal only),
``EventMultiplier_c``, and the final ``CCRS = Hazard * age_factor *
EventMultiplier`` product -- exactly the production formula
(``ccrs_report.compute_ccrs``), just vectorised over every draw instead of
called once. This is mathematically identical to re-deriving everything
from scratch each iteration (the fixed inputs are genuinely fixed by
design -- ``FROZEN_BOUNDS`` is out of scope for perturbation), not a
shortcut that skips something the brief asked to vary.

--------------------------------------------------------------------------
Vectorised age_factor -- a tested mirror of src/index/age_factor.py
--------------------------------------------------------------------------
``src/index/age_factor.py``'s ``age_factor()`` is a per-row, per-plant
function (used once, in production, over ~10.8k plants). Calling it
1000 x 3 magnitudes = 3000 times over that many rows in a Python loop is
too slow for this module's iteration count. ``_retention_vector`` below is
a ``numpy``-vectorised re-implementation of the same four retention curves
(hydro linear, wind linear, solar compound, coal sawtooth) plus the mixed-
fuel average, parameterised by a per-country rate array instead of the
fixed module constants. ``test_monte_carlo.py`` cross-checks it against
``age_factor.compute_age_factors()`` at the production (unperturbed) rates,
row for row, to catch any transcription drift between the two
implementations.

--------------------------------------------------------------------------
Band report -- WHICH scalar is reported per band, and why
--------------------------------------------------------------------------
``WaterRiskBand``/``HeatRiskBand`` membership itself does not vary across
draws: both bands are cut on raw, unweighted ``ws``/``sv``/``iv``/``heat``
values (``risk_bands.s_water``, ``risk_bands.heat_percentile_cuts``), which
depend on none of the three perturbed parameter groups (bucket weights,
age_factor rates, EventMultiplier k all apply only inside ``Hazard``/
``CCRS``, never inside the band cut itself). Reporting a percentile CI on
"% capacity in band X" would therefore be a degenerate, zero-width interval
every time -- a correct but uninformative result. Instead, this module
reports the **V6-computable-base, capacity-weighted mean CCRS score**
within each fixed (country, scenario, band) group -- the quantity that
genuinely varies draw to draw under the parameter uncertainty being tested.
Band membership (the grouping key) is taken once from
``risk_bands.compute_bands()``, exactly as production computes it, never
recomputed inside the loop. WaterRiskBand groups are reported on the
primary GCM's CCRS score only (WaterRiskBand is itself GCM-independent);
HeatRiskBand groups are reported per GCM, GFDL-ESM4 and MIROC6 as separate
rows, never blended (ARCHITECTURE.md Section 5.4).

Standalone: ``python -m src.index.monte_carlo`` from the project root.
Writes ``data/outputs/tables/monte_carlo_water_band.csv`` and
``data/outputs/tables/monte_carlo_heat_band.csv``.
"""

from __future__ import annotations

import argparse
import logging
import time
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import COUNTRIES, OUTPUT_TABLES, RANDOM_SEED
from src.index import age_factor
from src.index import ccrs_calculator as ccrs
from src.index import event_multiplier
from src.index import risk_bands
from src.index.ccrs_calculator import PLANT_UID

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Mechanics (ARCHITECTURE.md Section 8, unchanged)
# --------------------------------------------------------------------------
MAGNITUDES = (0.10, 0.20, 0.30)
N_ITERATIONS = 1000
PERCENTILES = (2.5, 50.0, 97.5)

# Literature ranges for the direct-uniform age_factor draws (item B).
COAL_DECAY_RATE_RANGE = (0.0019, 0.0044)   # Sagaf 2020, 0.19-0.44 %/yr
WIND_RATE_RANGE = (0.0030, 0.0050)          # 0.3-0.5 %/yr
HYDRO_RATE_RANGE = (0.0050, 0.0060)         # 0.5-0.6 %/yr


# --------------------------------------------------------------------------
# RNG -- one independent, reproducible stream per country (see module docstring)
# --------------------------------------------------------------------------
def country_rng(country: str, magnitude: float) -> np.random.Generator:
    """Independent RNG stream for one (country, magnitude) pair, keyed off
    ``RANDOM_SEED`` via ``zlib.crc32`` + ``SeedSequence`` (mirrors the old
    SCI/NAES design's stream-derivation pattern). Deterministic: the same
    ``(country, magnitude)`` always yields the same sequence, regardless of
    what other countries/magnitudes are also being simulated."""
    key = zlib.crc32(f"{country}|{magnitude:.2f}".encode("utf-8"))
    seed_sequence = np.random.SeedSequence(RANDOM_SEED, spawn_key=(key,))
    return np.random.default_rng(seed_sequence)


def draw_country_params(country: str, magnitude: float, n: int = N_ITERATIONS) -> dict[str, np.ndarray]:
    """``n`` draws of every perturbed parameter for one country, at one
    magnitude. Item A's thermal water/heat ratio is perturbed and
    renormalised to fill ``1 - w_drought`` (drought held fixed at its
    production value -- see module docstring). Items B/C are direct uniform
    draws (B) or a relative perturbation of the central value (C)."""
    rng = country_rng(country, magnitude)

    base = ccrs.BUCKET_WEIGHTS["thermal"]
    w_drought = base["drought"]
    remaining = 1.0 - w_drought
    raw_water = base["water"] * rng.uniform(1.0 - magnitude, 1.0 + magnitude, size=n)
    raw_heat = base["heat"] * rng.uniform(1.0 - magnitude, 1.0 + magnitude, size=n)
    scale = remaining / (raw_water + raw_heat)
    thermal_water = raw_water * scale
    thermal_heat = raw_heat * scale

    coal_rate = rng.uniform(*COAL_DECAY_RATE_RANGE, size=n)
    wind_rate = rng.uniform(*WIND_RATE_RANGE, size=n)
    hydro_rate = rng.uniform(*HYDRO_RATE_RANGE, size=n)
    event_k = event_multiplier.EVENT_MULTIPLIER_K * rng.uniform(1.0 - magnitude, 1.0 + magnitude, size=n)

    return {
        "thermal_water": thermal_water,
        "thermal_heat": thermal_heat,
        "thermal_drought": np.full(n, w_drought),
        "coal_rate": coal_rate,
        "wind_rate": wind_rate,
        "hydro_rate": hydro_rate,
        "event_k": event_k,
    }


# --------------------------------------------------------------------------
# Vectorised age_factor mirror (see module docstring)
# --------------------------------------------------------------------------
def _coal_retention_vec(age: np.ndarray, decay_rate: np.ndarray) -> np.ndarray:
    """Vectorised mirror of ``age_factor._coal_retention`` -- sawtooth decay
    at ``decay_rate`` (perturbed) within a fixed
    ``age_factor.COAL_OVERHAUL_CYCLE_YEARS``-year cycle,
    ``age_factor.COAL_OVERHAUL_RECOVERY`` recovered at each boundary (both
    fixed -- out of scope, item B)."""
    age = np.asarray(age, "float64")
    decay_rate = np.asarray(decay_rate, "float64")
    cycle = age_factor.COAL_OVERHAUL_CYCLE_YEARS
    recovery = age_factor.COAL_OVERHAUL_RECOVERY
    permanent_loss_per_cycle = (1.0 - recovery) * decay_rate * cycle
    age_nonneg = np.maximum(age, 0.0)
    n_cycles = np.floor(age_nonneg / cycle)
    years_into_cycle = age_nonneg - n_cycles * cycle
    retention = 1.0 - n_cycles * permanent_loss_per_cycle - decay_rate * years_into_cycle
    return np.where(age <= 0, 1.0, retention)


def _retention_vector(
    attrs: pd.DataFrame,
    country_idx: np.ndarray,
    coal_rate_by_country: np.ndarray,
    wind_rate_by_country: np.ndarray,
    hydro_rate_by_country: np.ndarray,
) -> np.ndarray:
    """Per-row ``retention(age) <= 1`` for one Monte Carlo draw, over
    ``attrs`` (one row per ``plant_uid``, columns: ``age``, ``bucket``,
    ``fuel_type``, ``mixed_fuel_type``, ``fuel_types_found``).
    ``country_idx`` is a precomputed ``COUNTRIES``-index per row; the three
    rate arrays are this draw's per-country values (length
    ``len(COUNTRIES)``). Solar and neutral thermal fuels use the fixed
    production constant/curve (out of scope for perturbation)."""
    n = len(attrs)
    age = attrs["age"].to_numpy("float64")
    bucket = attrs["bucket"].to_numpy()
    fuel_type = attrs["fuel_type"].to_numpy()
    mixed = attrs["mixed_fuel_type"].to_numpy()
    fuel_found = attrs["fuel_types_found"].to_numpy()

    coal_rate = coal_rate_by_country[country_idx]
    wind_rate = wind_rate_by_country[country_idx]
    hydro_rate = hydro_rate_by_country[country_idx]

    retention = np.ones(n, dtype="float64")  # neutral default: NaN age, unknown bucket
    valid_age = ~np.isnan(age)

    m_hydro = valid_age & (bucket == "hydro")
    retention[m_hydro] = 1.0 - hydro_rate[m_hydro] * age[m_hydro]

    m_wind = valid_age & (bucket == "wind")
    retention[m_wind] = 1.0 - wind_rate[m_wind] * age[m_wind]

    m_solar = valid_age & (bucket == "solar")
    retention[m_solar] = (1.0 - age_factor.SOLAR_RETENTION_RATE) ** age[m_solar]

    m_thermal_single = valid_age & (bucket == "thermal") & ~mixed
    m_coal = m_thermal_single & (fuel_type == "coal")
    retention[m_coal] = _coal_retention_vec(age[m_coal], coal_rate[m_coal])
    # neutral thermal fuels (oil/gas, nuclear, bioenergy): retention stays 1.0

    m_mixed = valid_age & (bucket == "thermal") & mixed
    for j in np.where(m_mixed)[0]:
        comps = [c.strip() for c in str(fuel_found[j]).split(age_factor._MIXED_SEP) if c.strip()]
        vals = [
            float(_coal_retention_vec(np.array([age[j]]), np.array([coal_rate[j]]))[0])
            if c == "coal" else 1.0
            for c in comps
        ]
        retention[j] = float(np.mean(vals))

    return retention


# --------------------------------------------------------------------------
# Precomputation -- done ONCE, outside the iteration loop (see module docstring)
# --------------------------------------------------------------------------
class _Precomputed:
    """Everything a Monte Carlo draw needs that does NOT depend on the
    perturbed parameters: the frozen-bounds-transformed Hazard inputs (one
    per GCM), plant attributes for age_factor, event counts, fixed risk-band
    labels, and country-index arrays for fast per-draw gathers."""

    def __init__(self) -> None:
        country_to_idx = {c: i for i, c in enumerate(COUNTRIES)}

        self.haz: dict[str, dict[str, np.ndarray]] = {}
        self.band: dict[str, dict[str, np.ndarray]] = {}
        for model in ccrs.configured_models():
            hz = ccrs.compute_hazard(model)  # FROZEN_BOUNDS, unperturbed
            attrs_aligned = hz[[PLANT_UID]].merge(
                _plant_attributes(), on=PLANT_UID, how="left", validate="many_to_one"
            )
            if attrs_aligned["age"].isna().sum() != hz["commissioning_year"].isna().sum():
                raise RuntimeError(
                    "monte_carlo: age attribute alignment mismatch -- "
                    "compute_hazard() and age_factor.load_plant_attributes() "
                    "disagree on which plant_uid have a commissioning_year."
                )
            bt = risk_bands.compute_bands(model)
            banded = hz[[PLANT_UID, "water_scenario"]].merge(
                bt.frame[[PLANT_UID, "water_scenario", "water_risk_band", "heat_risk_band"]],
                on=[PLANT_UID, "water_scenario"], how="left", validate="one_to_one",
            )

            self.haz[model] = {
                "country_idx": hz["country"].map(country_to_idx).to_numpy(),
                "bucket": hz["bucket"].to_numpy(),
                "water_sub": hz["water_sub"].to_numpy("float64"),
                "t_heat": hz["T_heat"].to_numpy("float64"),
                "t_spei": hz["T_spei"].to_numpy("float64"),
                "capacity_mw": hz["capacity_mw"].to_numpy("float64"),
                "computable": hz["commissioning_year"].notna().to_numpy(),
                "country": hz["country"].to_numpy(),
                "water_scenario": hz["water_scenario"].to_numpy(),
                "heat_scenario": hz["heat_scenario"].to_numpy(),
                "age": attrs_aligned["age"].to_numpy("float64"),
                "attrs": attrs_aligned,
            }
            self.band[model] = {
                "water_risk_band": banded["water_risk_band"].to_numpy(),
                "heat_risk_band": banded["heat_risk_band"].to_numpy(),
            }

        events = event_multiplier.load_event_counts(COUNTRIES)
        events["rate"] = events["n_events"] / event_multiplier.EMDAT_ARCHIVE_SPAN_YEARS
        events = events.set_index("country").reindex(COUNTRIES)
        self.event_rate = events["rate"].to_numpy("float64")
        self.event_rate_max = float(self.event_rate.max())

        # Frozen structural constants -- snapshotted for the regression check.
        self.frozen_bounds_snapshot = {k: (dict(v) if isinstance(v, dict) else tuple(v))
                                        for k, v in ccrs.FROZEN_BOUNDS.items()}
        self.water_band_cuts_snapshot = tuple(risk_bands.WATER_BAND_CUTS)


def _plant_attributes() -> pd.DataFrame:
    """Mirrors ``age_factor.load_plant_attributes()``, but ``fuel_type`` /
    ``fuel_types_found`` are filled to a plain-``str`` empty value first:
    both are nullable pandas ``"string"`` dtype (``pd.NA`` for non-thermal /
    non-mixed plants), and ``pd.NA`` inside a ``numpy`` boolean mask raises
    (``TypeError: boolean value of NA is ambiguous``) -- the vectorised path
    needs plain ``object``/``str`` arrays throughout."""
    df = age_factor.load_plant_attributes()
    df = df.copy()
    df["age"] = df["commissioning_year"].map(age_factor.plant_age)
    df["fuel_type"] = df["fuel_type"].fillna("").astype(str)
    df["fuel_types_found"] = df["fuel_types_found"].fillna("").astype(str)
    return df[[PLANT_UID, "age", "bucket", "fuel_type", "mixed_fuel_type", "fuel_types_found"]]


# --------------------------------------------------------------------------
# Per-draw recomputation
# --------------------------------------------------------------------------
def compute_draw_ccrs(pre: _Precomputed, model: str, params_by_country: dict[str, dict], i: int) -> np.ndarray:
    """The full ``CCRS_{i,s}`` array for one GCM, one Monte Carlo draw."""
    h = pre.haz[model]
    country_idx = h["country_idx"]

    coal_rate = np.array([params_by_country[c]["coal_rate"][i] for c in COUNTRIES])
    wind_rate = np.array([params_by_country[c]["wind_rate"][i] for c in COUNTRIES])
    hydro_rate = np.array([params_by_country[c]["hydro_rate"][i] for c in COUNTRIES])
    event_k = np.array([params_by_country[c]["event_k"][i] for c in COUNTRIES])

    retention = _retention_vector(h["attrs"], country_idx, coal_rate, wind_rate, hydro_rate)
    age_factor_arr = 2.0 - np.clip(retention, 0.0, 1.0)

    w_water, w_heat, w_drought = _hazard_weights_by_country(h["bucket"], country_idx, params_by_country, i)

    hazard = (
        np.where(w_water > 0, w_water * h["water_sub"], 0.0)
        + np.where(w_heat > 0, w_heat * h["t_heat"], 0.0)
        + np.where(w_drought > 0, w_drought * h["t_spei"], 0.0)
    )

    event_multiplier_by_country = 1.0 + event_k * (pre.event_rate / pre.event_rate_max)
    event_mult = event_multiplier_by_country[country_idx]

    return hazard * age_factor_arr * event_mult


def _hazard_weights_by_country(bucket: np.ndarray, country_idx: np.ndarray, params_by_country: dict[str, dict], i: int):
    n = len(bucket)
    w_water = np.zeros(n, dtype="float64")
    w_heat = np.zeros(n, dtype="float64")
    w_drought = np.zeros(n, dtype="float64")
    thermal_water = np.array([params_by_country[c]["thermal_water"][i] for c in COUNTRIES])
    thermal_heat = np.array([params_by_country[c]["thermal_heat"][i] for c in COUNTRIES])
    thermal_drought = np.array([params_by_country[c]["thermal_drought"][i] for c in COUNTRIES])
    for b in ccrs.BUCKETS:
        m = bucket == b
        if not m.any():
            continue
        if b == "thermal":
            w_water[m] = thermal_water[country_idx[m]]
            w_heat[m] = thermal_heat[country_idx[m]]
            w_drought[m] = thermal_drought[country_idx[m]]
        else:
            base = ccrs.BUCKET_WEIGHTS[b]
            w_water[m] = base["water"]
            w_heat[m] = base["heat"]
            w_drought[m] = base["drought"]
    return w_water, w_heat, w_drought


# --------------------------------------------------------------------------
# Percentile CI
# --------------------------------------------------------------------------
def percentile_ci(values: np.ndarray, percentiles=PERCENTILES) -> dict[float, float]:
    """``{percentile: value}`` over ``values`` (linear interpolation, same
    convention as ``risk_bands.heat_percentile_cuts``). ``NaN`` for every
    percentile if ``values`` has no finite entry -- a (country, scenario,
    band) group whose every member plant has a structurally NaN CCRS (e.g.
    a thermal plant outside any Aqueduct basin, ``water_sub`` NaN,
    propagating through every draw regardless of the perturbed parameters)
    is a legitimate, informative result, not an error."""
    v = np.asarray(values, "float64")
    v = v[~np.isnan(v)]
    if v.size == 0:
        return {p: float("nan") for p in percentiles}
    return {p: float(np.percentile(v, p)) for p in percentiles}


# --------------------------------------------------------------------------
# Grouped, capacity-weighted mean CCRS per draw -- fast via bincount
# --------------------------------------------------------------------------
def _group_ids(*key_arrays: np.ndarray) -> tuple[np.ndarray, pd.MultiIndex]:
    codes, uniques = pd.factorize(pd.Series(list(zip(*key_arrays))), sort=True)
    index = pd.MultiIndex.from_tuples(uniques)
    return codes, index


def _weighted_group_mean(
    group_ids: np.ndarray, n_groups: int, capacity: np.ndarray, ccrs_vals: np.ndarray,
) -> np.ndarray:
    """Capacity-weighted mean of ``ccrs_vals`` per group, skipping individual
    NaN-``ccrs_vals`` rows the way ``pandas.Series.sum()`` does (never
    letting one NaN row poison its whole group's sum -- ``np.bincount``
    does not skip NaN weights on its own). A finite-``water_sub`` weight
    ``> 0`` propagating NaN for a thermal plant outside any Aqueduct basin
    (``ccrs_calculator.hazard``'s documented behaviour) is expected and
    legitimate here; it must exclude only that plant's row from its group's
    average, not blank out capacity-weighted plants that share its group."""
    finite = ~np.isnan(ccrs_vals)
    num = np.bincount(group_ids[finite], weights=(capacity * ccrs_vals)[finite], minlength=n_groups)
    den = np.bincount(group_ids[finite], weights=capacity[finite], minlength=n_groups)
    with np.errstate(invalid="ignore", divide="ignore"):
        return num / den


def run_simulation(
    magnitude: float, n: int = N_ITERATIONS, pre: "_Precomputed | None" = None,
) -> dict[str, pd.DataFrame]:
    """Run ``n`` Monte Carlo draws at one ``magnitude``. Returns
    ``{"water": DataFrame, "heat": DataFrame}``, each one row per group
    (country x scenario x band[, gcm for heat]) with ``point_estimate`` and
    one column per percentile in ``PERCENTILES``."""
    pre = pre or _Precomputed()
    params_by_country = {c: draw_country_params(c, magnitude, n) for c in COUNTRIES}

    primary_gcm = risk_bands.PRIMARY_GCM
    h = pre.haz[primary_gcm]
    b = pre.band[primary_gcm]
    water_mask = h["computable"] & pd.notna(b["water_risk_band"])
    water_group_ids, water_index = _group_ids(
        h["country"][water_mask], h["water_scenario"][water_mask], b["water_risk_band"][water_mask],
    )
    n_water_groups = len(water_index)
    water_capacity = h["capacity_mw"][water_mask]

    water_draws = np.empty((n, n_water_groups), dtype="float64")
    for i in range(n):
        ccrs_vals = compute_draw_ccrs(pre, primary_gcm, params_by_country, i)[water_mask]
        water_draws[i] = _weighted_group_mean(water_group_ids, n_water_groups, water_capacity, ccrs_vals)

    water_df = _draws_to_ci_frame(water_draws, water_index, ["country", "water_scenario", "water_risk_band"])

    heat_frames = []
    for model in ccrs.configured_models():
        h = pre.haz[model]
        b = pre.band[model]
        heat_mask = h["computable"] & pd.notna(b["heat_risk_band"])
        heat_group_ids, heat_index = _group_ids(
            h["country"][heat_mask], h["heat_scenario"][heat_mask], b["heat_risk_band"][heat_mask],
        )
        n_heat_groups = len(heat_index)
        heat_capacity = h["capacity_mw"][heat_mask]

        heat_draws = np.empty((n, n_heat_groups), dtype="float64")
        for i in range(n):
            ccrs_vals = compute_draw_ccrs(pre, model, params_by_country, i)[heat_mask]
            heat_draws[i] = _weighted_group_mean(heat_group_ids, n_heat_groups, heat_capacity, ccrs_vals)

        frame = _draws_to_ci_frame(heat_draws, heat_index, ["country", "heat_scenario", "heat_risk_band"])
        frame["gcm"] = model
        heat_frames.append(frame)
    heat_df = pd.concat(heat_frames, ignore_index=True)

    return {"water": water_df, "heat": heat_df}


def _draws_to_ci_frame(draws: np.ndarray, index: pd.MultiIndex, key_names: list[str]) -> pd.DataFrame:
    rows = []
    for col, key in enumerate(index):
        ci = percentile_ci(draws[:, col])
        row = dict(zip(key_names, key))
        row["point_estimate"] = ci[50.0]
        for p in PERCENTILES:
            row[f"p{p}"] = ci[p]
        rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Structural-constant regression guard
# --------------------------------------------------------------------------
def assert_structural_constants_untouched(pre: "_Precomputed") -> None:
    """Raise if ``FROZEN_BOUNDS`` or the ``risk_bands`` cuts drifted from the
    snapshot taken before the simulation ran -- these are explicitly out of
    scope for this module (see module docstring)."""
    live_bounds = {k: (dict(v) if isinstance(v, dict) else tuple(v)) for k, v in ccrs.FROZEN_BOUNDS.items()}
    if live_bounds != pre.frozen_bounds_snapshot:
        raise RuntimeError(
            "monte_carlo: ccrs_calculator.FROZEN_BOUNDS changed during the "
            "simulation -- this module must never touch it."
        )
    if tuple(risk_bands.WATER_BAND_CUTS) != pre.water_band_cuts_snapshot:
        raise RuntimeError(
            "monte_carlo: risk_bands.WATER_BAND_CUTS changed during the "
            "simulation -- this module must never touch it."
        )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=N_ITERATIONS)
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_TABLES)
    args = parser.parse_args()

    pre = _Precomputed()
    water_frames, heat_frames = [], []
    t0 = time.perf_counter()
    for magnitude in MAGNITUDES:
        logger.info("running magnitude +/-%.0f%% (n=%d) ...", magnitude * 100, args.n)
        result = run_simulation(magnitude, n=args.n, pre=pre)
        result["water"]["magnitude"] = magnitude
        result["heat"]["magnitude"] = magnitude
        water_frames.append(result["water"])
        heat_frames.append(result["heat"])
    elapsed = time.perf_counter() - t0

    assert_structural_constants_untouched(pre)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    water_out = pd.concat(water_frames, ignore_index=True)
    heat_out = pd.concat(heat_frames, ignore_index=True)
    water_out.to_csv(args.out_dir / "monte_carlo_water_band.csv", index=False)
    heat_out.to_csv(args.out_dir / "monte_carlo_heat_band.csv", index=False)

    logger.info(
        "Monte Carlo done: %d magnitudes x n=%d in %.1fs. Wrote monte_carlo_water_band.csv "
        "(%d rows), monte_carlo_heat_band.csv (%d rows) to %s.",
        len(MAGNITUDES), args.n, elapsed, len(water_out), len(heat_out), args.out_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
