"""
GEAR v3 Phase 6 -- partial-recomputation pipeline for Sobol/Monte Carlo draws.

This module implements ONLY the recomputation-cost fix ``PHASE6_DESIGN.md``
Section 4.2 already proposed, and does not itself run Sobol, sample from
SALib, or resolve any of Phase 6's three still-open items (RNG granularity,
RiskBand percentile-cut Sobol-dimension grouping, ``psae_complete=False``
treatment under a sensitivity statistic) -- see ``docs/DECISIONS.md``, "GEAR
v3 Phase 6: partial-recomputation pipeline (raster caching + perturbed-chain
recompute)".

--------------------------------------------------------------------------
Why this exists -- the measured problem
--------------------------------------------------------------------------
A naive "call ``risk_calculator.compute_risk()`` fully, once per Saltelli
draw" approach was measured at ~29.7s per draw (3 countries, both GCMs) --
projecting to ~79 days at ``D=6``, ``N_0=16000``
(``N_0 * (2D + 2) = 16000 * 14 = 224000`` evaluations). Not viable. The
expensive step is raster I/O + nearest-pixel sampling
(``risk_calculator.sample_raster`` / ``sample_terms``,
``risk_bands.sample_hazard_terms``) -- and it is invariant under every
Sobol/Monte-Carlo parameter this project has identified (``PHASE6_DESIGN.md``
Section 1): raw hazard values sampled from a raster do not depend on
``age_factor`` retention rates or RiskBand percentile-cut choices. Only two
downstream, cheap, array-arithmetic chains depend on the perturbed
parameters:

* ``age_factor`` -> ``risk_calculator.transform_term``/``risk_i_h`` ->
  ``Risk_{i,h}`` (Equation 1).
* RiskBand Tier 3 percentile cuts -> ``risk_bands.classify_hazard`` ->
  ``RiskBand_{i,h}`` -> ``psae.compute_psae`` -> ``PSAE_i`` (Equation 2).

This module therefore separates a one-time, expensive PRECOMPUTE step
(``precompute``, raster sampling only, held in memory) from a cheap,
repeatable RECOMPUTE step (``recompute_risk_by_hazard`` /
``recompute_risk_bands`` / ``recompute_draw``) that a future Sobol driver
calls once per draw -- mirroring the retired ``monte_carlo.py``'s own
"fixed inputs computed once, perturbed chain recomputed per draw" structure
(its module docstring, "What recomputing the full CCRS + band report per
draw means"), adapted to the current (post-CCRS) ``age_factor`` ->
``RiskBand`` -> ``PSAE`` chain.

--------------------------------------------------------------------------
Two independent downstream chains, not one
--------------------------------------------------------------------------
``Risk_{i,h}`` (``risk_calculator``) and ``RiskBand_{i,h}``/``PSAE_i``
(``risk_bands``/``psae``) are separate quantities with separate inputs --
confirmed in ``docs/DECISIONS.md`` (the Phase 3.3 entry's correction) and by
direct code read: ``RiskBand_{i,h}`` classifies each hazard's RAW sampled
value directly (never ``Risk_i,h``, never ``age_factor``-weighted), so
``age_factor`` perturbation affects ``Risk_i,h`` only, and RiskBand
percentile-cut perturbation affects ``RiskBand``/``PSAE`` only. This module
keeps that separation -- ``recompute_risk_by_hazard`` and
``recompute_risk_bands`` are independent functions, each cheap on its own,
combinable per draw by ``recompute_draw``.

--------------------------------------------------------------------------
No duplicate reimplementation of the production chain, one necessary
exception
--------------------------------------------------------------------------
Every step that does not need to vary per draw calls the existing,
already-tested public function directly (``risk_calculator.transform_term``,
``risk_calculator.risk_i_h``, ``risk_calculator.exposure_capacity_mw``,
``risk_bands.percentile_band_cuts``, ``risk_bands._bandize``,
``risk_bands.classify_hazard``, ``psae.compute_psae``) -- none of those are
reimplemented here. The one necessary exception is ``age_factor``'s
retention curves: ``age_factor.age_factor()`` is a scalar, per-row function
that reads its rate constants from MODULE-LEVEL GLOBALS
(``WIND_RELATIVE_RATE`` etc.), not from parameters, so it cannot be called
with a perturbed rate without either monkeypatching module globals (not
draw-parallel-safe) or a vectorised mirror parameterised by rate arrays.
The retired ``monte_carlo.py`` already established the precedent for this
exact situation (its own ``_retention_vector``/``_coal_retention_vec``,
documented as "a ``numpy``-vectorised re-implementation of the same four
retention curves... cross-checked against ``age_factor.compute_age_factors()``
... row for row, to catch any transcription drift"). ``retention_vector``/
``age_factor_vector`` below follow the identical pattern for the current
(post-CCRS) curve set, with the identical cross-check test
(``tests/test_sensitivity_recompute.py``,
``test_age_factor_vector_matches_age_factor_compute_age_factors_at_nominal_rates``).
``monte_carlo.py`` itself is not imported -- it is currently broken
(retired ``ccrs_calculator`` import, pre-existing, unrelated to this task).

Standalone: no ``main()`` -- this module is a library used by a future
Sobol/OAT driver (Phase 6.2/6.3, not built here) and by
``tests/test_sensitivity_recompute.py``'s correctness/timing checks.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.index import age_factor
from src.index import hazard_scope as hs
from src.index import psae
from src.index import risk_bands as rb
from src.index import risk_calculator as rc

logger = logging.getLogger(__name__)

PLANT_UID = rc.PLANT_UID

# --------------------------------------------------------------------------
# age_factor -- vectorised mirror (see module docstring for why this one
# exception to "call the existing function" exists). Parameterised by every
# continuous rate PHASE6_DESIGN.md Section 1.1 names as a Sobol candidate,
# whether or not that candidate's perturbation range is characterized yet --
# this module does not decide ranges, only supports the mechanism.
# --------------------------------------------------------------------------
def _coal_retention_vec(
    age: np.ndarray, decay_rate, cycle_years: float, recovery_fraction: float,
) -> np.ndarray:
    """Vectorised mirror of ``age_factor._coal_retention`` -- sawtooth decay
    at ``decay_rate`` (perturbable) within a ``cycle_years``-year cycle,
    ``recovery_fraction`` recovered at each boundary (both also
    perturbable, unlike the retired ``monte_carlo.py``'s version which held
    them fixed -- Section 1.1 flags both as open, not out of scope)."""
    age = np.asarray(age, "float64")
    decay_rate = np.asarray(decay_rate, "float64")
    permanent_loss_per_cycle = (1.0 - recovery_fraction) * decay_rate * cycle_years
    age_nonneg = np.maximum(age, 0.0)
    n_cycles = np.floor(age_nonneg / cycle_years)
    years_into_cycle = age_nonneg - n_cycles * cycle_years
    retention = 1.0 - n_cycles * permanent_loss_per_cycle - decay_rate * years_into_cycle
    return np.where(age <= 0, 1.0, retention)


def _prepare_age_factor_attrs() -> pd.DataFrame:
    """Plant attributes ``age_factor``'s retention curves need, in
    numpy-safe (no ``pd.NA``) form -- mirrors the retired ``monte_carlo.py``'s
    ``_plant_attributes()`` fillna pattern (nullable pandas ``"string"``
    dtype / ``pd.NA`` inside a numpy boolean mask raises
    ``TypeError: boolean value of NA is ambiguous``)."""
    df = age_factor.load_plant_attributes().copy()
    df["age"] = df["commissioning_year"].map(age_factor.plant_age)
    df["bucket"] = df["bucket"].astype(str)
    df["fuel_type"] = df["fuel_type"].fillna("").astype(str)
    df["fuel_types_found"] = df["fuel_types_found"].fillna("").astype(str)
    df["mixed_fuel_type"] = df["mixed_fuel_type"].astype(bool)
    return df


def retention_vector(
    attrs: pd.DataFrame,
    *,
    coal_decay_rate: float | None = None,
    wind_relative_rate: float | None = None,
    hydro_retention_rate: float | None = None,
    solar_retention_rate: float | None = None,
    coal_overhaul_cycle_years: float | None = None,
    coal_overhaul_recovery: float | None = None,
) -> np.ndarray:
    """Per-row ``retention(age) <= 1``, one draw's worth, over ``attrs``
    (``_prepare_age_factor_attrs()``'s shape). Every rate defaults to the
    current ``age_factor`` module constant when omitted, so a call with no
    overrides reproduces the nominal (unperturbed) production curve exactly.
    Gas/oil-gas/nuclear/bioenergy (``age_factor.NEUTRAL_THERMAL_FUELS``) have
    no rate to perturb -- fixed at retention 1.0, same as production."""
    coal_decay_rate = age_factor.COAL_DECAY_RATE if coal_decay_rate is None else coal_decay_rate
    wind_relative_rate = age_factor.WIND_RELATIVE_RATE if wind_relative_rate is None else wind_relative_rate
    hydro_retention_rate = age_factor.HYDRO_RETENTION_RATE if hydro_retention_rate is None else hydro_retention_rate
    solar_retention_rate = age_factor.SOLAR_RETENTION_RATE if solar_retention_rate is None else solar_retention_rate
    cycle = age_factor.COAL_OVERHAUL_CYCLE_YEARS if coal_overhaul_cycle_years is None else coal_overhaul_cycle_years
    recovery = age_factor.COAL_OVERHAUL_RECOVERY if coal_overhaul_recovery is None else coal_overhaul_recovery

    n = len(attrs)
    age = attrs["age"].to_numpy("float64")
    bucket = attrs["bucket"].to_numpy()
    fuel_type = attrs["fuel_type"].to_numpy()
    mixed = attrs["mixed_fuel_type"].to_numpy()
    fuel_found = attrs["fuel_types_found"].to_numpy()

    known_buckets = {"hydro", "wind", "solar", "thermal"}
    valid_age = ~np.isnan(age)
    bad_bucket = valid_age & ~np.isin(bucket, list(known_buckets))
    if bad_bucket.any():
        raise ValueError(
            f"retention_vector: unknown fuel_type_bucket(s) "
            f"{sorted(set(bucket[bad_bucket]))}"
        )

    retention = np.ones(n, dtype="float64")  # neutral default: NaN age, neutral fuels
    m_hydro = valid_age & (bucket == "hydro")
    retention[m_hydro] = 1.0 - hydro_retention_rate * age[m_hydro]

    m_wind = valid_age & (bucket == "wind")
    retention[m_wind] = 1.0 - wind_relative_rate * age[m_wind]

    m_solar = valid_age & (bucket == "solar")
    retention[m_solar] = (1.0 - solar_retention_rate) ** age[m_solar]

    m_thermal_single = valid_age & (bucket == "thermal") & ~mixed
    m_coal = m_thermal_single & (fuel_type == "coal")
    retention[m_coal] = _coal_retention_vec(age[m_coal], coal_decay_rate, cycle, recovery)

    m_thermal_other = m_thermal_single & (fuel_type != "coal")
    m_unknown = m_thermal_other & ~np.isin(fuel_type, list(age_factor.NEUTRAL_THERMAL_FUELS))
    if m_unknown.any():
        raise ValueError(
            f"retention_vector: unknown thermal fuel_type(s) "
            f"{sorted(set(fuel_type[m_unknown]))} (known: 'coal' + "
            f"{sorted(age_factor.NEUTRAL_THERMAL_FUELS)})"
        )
    # m_thermal_other & known-neutral rows: retention stays 1.0 (already
    # initialized) -- oil/gas, nuclear, bioenergy carry no rate to perturb.

    m_mixed = valid_age & (bucket == "thermal") & mixed
    for j in np.where(m_mixed)[0]:
        comps = [c.strip() for c in str(fuel_found[j]).split(age_factor._MIXED_SEP) if c.strip()]
        if not comps:
            raise ValueError(
                f"retention_vector: mixed-fuel plant at row {j} has an empty "
                f"fuel_types_found"
            )
        vals = []
        for c in comps:
            if c == "coal":
                vals.append(float(_coal_retention_vec(
                    np.array([age[j]]), coal_decay_rate, cycle, recovery,
                )[0]))
            elif c in age_factor.NEUTRAL_THERMAL_FUELS:
                vals.append(1.0)
            else:
                raise ValueError(
                    f"retention_vector: unknown thermal fuel_type {c!r} in "
                    f"mixed-fuel plant at row {j}"
                )
        retention[j] = float(np.mean(vals))

    return retention


def age_factor_vector(attrs: pd.DataFrame, **rate_overrides) -> np.ndarray:
    """``age_factor``'s ``2 - clip(retention, 0, 1)`` conversion, vectorised.
    NaN age -> retention 1.0 -> ``age_factor`` 1.0, matching
    ``age_factor.NEUTRAL_AGE_FACTOR`` exactly (no separate branch needed)."""
    retention = retention_vector(attrs, **rate_overrides)
    return 2.0 - np.clip(retention, 0.0, 1.0)


# --------------------------------------------------------------------------
# Precompute -- the expensive, perturbation-INVARIANT step. Raster I/O and
# nearest-pixel sampling only; done ONCE, held in memory.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class PrecomputedInputs:
    """Raw, perturbation-invariant inputs a draw needs, sampled once.

    ``hazard_by_model``: ``{model: risk_calculator.sample_terms(model)}``,
    filtered to ``risk_calculator.BUCKETS`` and index-reset -- exactly what
    ``compute_risk_by_hazard`` samples internally, cached instead of
    re-sampled. Feeds the ``Risk_{i,h}`` (Equation 1) chain.

    ``band_samples_by_model``: ``{model: risk_bands.sample_hazard_terms(model)}``,
    filtered to ``hazard_scope.APPLICABLE_HAZARDS`` buckets -- exactly what
    ``compute_risk_bands`` samples internally, cached instead of re-sampled.
    Feeds the ``RiskBand_{i,h}``/``PSAE_i`` (Equation 2) chain. Kept as a
    SEPARATE cache from ``hazard_by_model`` rather than unified: the two
    production sampling functions already exist independently (different
    missing-raster fallback behaviour, slightly different term/column sets)
    and reconciling them into one shared sampling path is out of this
    task's scope (not asked for, and would itself need its own correctness
    verification against both production paths).

    ``attrs``: plant attributes for the vectorised ``age_factor`` chain
    (``_prepare_age_factor_attrs()``'s shape).
    """

    hazard_by_model: dict[str, pd.DataFrame] = field(default_factory=dict)
    band_samples_by_model: dict[str, pd.DataFrame] = field(default_factory=dict)
    attrs: pd.DataFrame = field(default_factory=pd.DataFrame)


def precompute(models: list[str] | None = None) -> PrecomputedInputs:
    """Run every raster read/sample ONCE. Expensive (~30s scale, dominated by
    raster I/O) -- call once per session/process, never per draw."""
    models = models or rc.configured_models()

    hazard_by_model = {}
    for model in models:
        df = rc.sample_terms(model)
        hazard_by_model[model] = df[df["bucket"].isin(rc.BUCKETS)].reset_index(drop=True)

    band_samples_by_model = {}
    for model in models:
        df = rb.sample_hazard_terms(model)
        band_samples_by_model[model] = df[df["bucket"].isin(hs.APPLICABLE_HAZARDS)].reset_index(drop=True)

    attrs = _prepare_age_factor_attrs()

    return PrecomputedInputs(
        hazard_by_model=hazard_by_model,
        band_samples_by_model=band_samples_by_model,
        attrs=attrs,
    )


# --------------------------------------------------------------------------
# Recompute -- the cheap, perturbation-SENSITIVE chain. No raster I/O.
# --------------------------------------------------------------------------
def recompute_risk_by_hazard(
    pre: PrecomputedInputs,
    model: str,
    *,
    bounds: dict[str, object] | None = None,
    rate_overrides: dict[str, float] | None = None,
) -> pd.DataFrame:
    """``Risk_{i,h}`` for one draw, one GCM -- ``risk_calculator.
    compute_risk_by_hazard``'s exact arithmetic (``transform_term``,
    ``exposure_capacity_mw``, ``risk_i_h``, ``FROZEN_BOUNDS``), fed from the
    cached ``pre.hazard_by_model[model]`` instead of a fresh
    ``sample_terms(model)`` call, and from the vectorised, perturbable
    ``age_factor_vector`` instead of ``age_factor.compute_age_factors()``.

    With ``bounds=None`` and ``rate_overrides=None`` (nominal draw), this
    must reproduce ``risk_calculator.compute_risk_by_hazard(model)``
    numerically identically -- see
    ``test_recompute_risk_by_hazard_matches_production_at_nominal_values``.
    """
    bounds = bounds or rc.FROZEN_BOUNDS
    rate_overrides = rate_overrides or {}

    df = pre.hazard_by_model[model]
    af_values = age_factor_vector(pre.attrs, **rate_overrides)
    af_series = pd.Series(af_values, index=pre.attrs[PLANT_UID].to_numpy())

    merged = df.copy()
    merged["age_factor"] = merged[PLANT_UID].map(af_series)
    missing = int(merged["age_factor"].isna().sum())
    if missing:
        raise ValueError(
            f"recompute_risk_by_hazard: {missing} rows have no age_factor "
            f"after mapping pre.attrs onto pre.hazard_by_model[{model!r}] -- "
            f"the two caches are out of sync with each other."
        )

    exposure_mw = rc.exposure_capacity_mw(merged["capacity_mw"].to_numpy("float64"))

    parts = []
    for term in rc.HAZARD_TERMS:
        lo, hi = rc._term_bounds(term, model, bounds)
        h_i_h = rc.transform_term(term, merged[term].to_numpy("float64"), lo, hi)
        vulnerability = merged["age_factor"].to_numpy("float64")
        risk = rc.risk_i_h(h_i_h, exposure_mw, vulnerability)

        part = merged[[PLANT_UID, "country", "plant_name", "lat", "lon",
                        "water_scenario", "heat_scenario", "bucket",
                        "capacity_mw", "commissioning_year"]].copy()
        part["model"] = model
        part["hazard_term"] = term
        part["hazard_i_h"] = h_i_h
        part["exposure_mw"] = exposure_mw
        part["age_factor"] = vulnerability
        part["risk_i_h"] = risk
        parts.append(part)

    out = pd.concat(parts, ignore_index=True)
    key = [PLANT_UID, "water_scenario", "hazard_term"]
    dup = int(out.duplicated(key).sum())
    if dup:
        raise RuntimeError(f"recompute_risk_by_hazard produced {dup} duplicate {key} rows.")
    return out


def recompute_risk(
    pre: PrecomputedInputs,
    models: list[str] | None = None,
    *,
    bounds: dict[str, object] | None = None,
    rate_overrides: dict[str, float] | None = None,
) -> pd.DataFrame:
    """``Risk_{i,h}`` for one draw, every configured GCM -- mirrors
    ``risk_calculator.compute_risk``."""
    models = models or rc.configured_models()
    return pd.concat(
        [recompute_risk_by_hazard(pre, m, bounds=bounds, rate_overrides=rate_overrides)
         for m in models],
        ignore_index=True,
    )


def recompute_risk_bands(
    pre: PrecomputedInputs,
    model: str,
    *,
    percentile_overrides: dict[tuple[str, str], tuple[float, ...]] | None = None,
) -> rb.RiskBandTable:
    """``RiskBand_{i,h}`` for one draw, one GCM -- fed from the cached
    ``pre.band_samples_by_model[model]`` instead of a fresh
    ``sample_hazard_terms(model)`` call. Only Tier 3 (``kind="percentile"``)
    specs are perturbable, keyed by ``(hazard, bucket)`` in
    ``percentile_overrides``; Tier 1 (``absolute``/``binary``) specs call
    ``risk_bands.classify_hazard`` directly, unperturbed, identical to
    production (this task's scope: RiskBand *percentile cuts* are the named
    Sobol candidate, Section 1.2 -- Tier 1 structural cutoffs are not).

    With ``percentile_overrides=None`` (nominal draw), this must reproduce
    ``risk_bands.compute_risk_bands(model)`` numerically identically -- see
    ``test_recompute_risk_bands_matches_production_at_nominal_values``.
    """
    percentile_overrides = percentile_overrides or {}
    df = pre.band_samples_by_model[model]

    percentile_cuts: dict[tuple[str, str], dict] = {}
    parts = []
    for bucket, hazards in hs.APPLICABLE_HAZARDS.items():
        bucket_df = df[df["bucket"] == bucket]
        if bucket_df.empty:
            continue
        for hazard in hazards:
            spec = rb.THRESHOLD_REGISTRY[(hazard, bucket)]
            raw = bucket_df[hazard].to_numpy("float64")

            if spec.kind == "percentile":
                pooled = df[hazard].to_numpy("float64")
                percentiles = percentile_overrides.get((hazard, bucket), spec.percentiles)
                try:
                    info = rb.percentile_band_cuts(pooled, percentiles)
                except ValueError as exc:
                    logger.warning(
                        "skipping (%s, %s): %s -- no finite pooled sample.",
                        hazard, bucket, exc,
                    )
                    bands = np.full(raw.shape, None, dtype=object)
                    info = None
                else:
                    bands = rb._bandize(raw, info["band_cuts"], spec.labels)
            else:
                result = rb.classify_hazard(hazard, bucket, raw, pooled_values=None)
                bands, info = result.bands, result.percentile_info

            if info is not None:
                percentile_cuts[(hazard, bucket)] = info

            part = bucket_df[[PLANT_UID, "country", "plant_name", "bucket",
                               "water_scenario", "heat_scenario"]].copy()
            part["model"] = model
            part["hazard_term"] = hazard
            part["hazard_label"] = hs.HAZARD_LABELS[hazard]
            part["tier"] = spec.tier
            part["provisional"] = spec.provisional
            part["raw_value"] = raw
            part["risk_band"] = bands
            parts.append(part)

    out = pd.concat(parts, ignore_index=True)[rb.RISK_BAND_OUTPUT_COLUMNS]
    key = [PLANT_UID, "water_scenario", "hazard_term", "bucket"]
    dup = int(out.duplicated(key).sum())
    if dup:
        raise RuntimeError(f"recompute_risk_bands produced {dup} duplicate {key} rows.")
    return rb.RiskBandTable(frame=out, percentile_cuts=percentile_cuts, model=model)


class DrawResult:
    """One draw's full output -- both independent chains (see module
    docstring), for a future Sobol/OAT driver to reduce into whatever
    summary statistic Phase 6 eventually settles on (not decided here)."""

    __slots__ = ("risk_by_hazard", "risk_bands", "psae")

    def __init__(self, risk_by_hazard: pd.DataFrame, risk_bands: rb.RiskBandTable, psae_table: psae.PSAETable):
        self.risk_by_hazard = risk_by_hazard
        self.risk_bands = risk_bands
        self.psae = psae_table


def recompute_draw(
    pre: PrecomputedInputs,
    model: str,
    *,
    bounds: dict[str, object] | None = None,
    rate_overrides: dict[str, float] | None = None,
    percentile_overrides: dict[tuple[str, str], tuple[float, ...]] | None = None,
) -> DrawResult:
    """One full draw, one GCM: both chains, no raster I/O. The unit a future
    Sobol driver calls once per Saltelli sample."""
    risk_by_hazard = recompute_risk_by_hazard(
        pre, model, bounds=bounds, rate_overrides=rate_overrides,
    )
    risk_band_table = recompute_risk_bands(
        pre, model, percentile_overrides=percentile_overrides,
    )
    psae_table = psae.compute_psae(risk_band_table)
    return DrawResult(risk_by_hazard, risk_band_table, psae_table)


# --------------------------------------------------------------------------
# Timing harness -- real measurement, not a projection (task requirement).
# --------------------------------------------------------------------------
def time_n_draws(pre: PrecomputedInputs, model: str, n: int, seed: int = 20260914) -> dict:
    """Run ``n`` real draws of ``recompute_draw`` with small random jitter on
    every perturbable rate/percentile-shift parameter (NOT a real Sobol/
    SALib sample -- this module does not implement Sobol; jitter here exists
    only to produce a representative, non-degenerate per-draw cost, not a
    sensitivity result) and return real wall-clock timing.

    Jitter ranges are illustrative magnitudes only (small relative
    perturbations around the nominal constants), not the literature ranges
    PHASE6_DESIGN.md Section 1.1 names -- picking those ranges is Phase 6.2's
    job, still open, not this task's.
    """
    rng = np.random.default_rng(seed)
    elapsed = np.empty(n, dtype="float64")
    for i in range(n):
        rate_overrides = {
            "coal_decay_rate": age_factor.COAL_DECAY_RATE * (1.0 + rng.uniform(-0.1, 0.1)),
            "wind_relative_rate": age_factor.WIND_RELATIVE_RATE * (1.0 + rng.uniform(-0.1, 0.1)),
            "hydro_retention_rate": age_factor.HYDRO_RETENTION_RATE * (1.0 + rng.uniform(-0.1, 0.1)),
            "solar_retention_rate": age_factor.SOLAR_RETENTION_RATE * (1.0 + rng.uniform(-0.1, 0.1)),
        }
        shift = rng.uniform(-5.0, 5.0)
        percentile_overrides = {
            key: tuple(min(max(p + shift, 0.0), 100.0) for p in spec.percentiles)
            for key, spec in rb.THRESHOLD_REGISTRY.items()
            if spec.kind == "percentile"
        }
        t0 = time.perf_counter()
        recompute_draw(
            pre, model,
            rate_overrides=rate_overrides,
            percentile_overrides=percentile_overrides,
        )
        elapsed[i] = time.perf_counter() - t0

    return {
        "n": n,
        "mean_s": float(elapsed.mean()),
        "median_s": float(np.median(elapsed)),
        "min_s": float(elapsed.min()),
        "max_s": float(elapsed.max()),
        "total_s": float(elapsed.sum()),
    }
