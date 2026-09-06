"""
Isolated single-step probes for the CCRS assembly -- NOT production code.

``age_factor`` and ``EventMultiplier_c`` each multiply the Hazard term on
their own join key (``plant_uid`` / ``country``). The production pipeline
never applies them one at a time: ``src/index/ccrs_report.py``'s
``assemble_ccrs`` is the single source of truth for the full
``CCRS_{i,s} = Hazard_{i,s} * age_factor_i * EventMultiplier_c`` product.

The two functions here apply exactly one factor to a Hazard-shaped frame, so
a test can assert that step's join is multiplicative, never summed, and
never duplicates or drops ``plant_uid`` rows. They live under ``tests/`` so
nothing reads them as part of the pipeline. The file name is deliberately
not ``test_*`` -- pytest does not collect it; ``tests/test_age_factor.py``
and ``tests/test_event_multiplier.py`` import these helpers.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.index import ccrs_calculator as ccrs
from src.index.age_factor import compute_age_factors
from src.index.ccrs_calculator import PLANT_UID
from src.index.event_multiplier import compute_event_multipliers

HAZARD_CSV = ccrs.OUTPUT_TABLES / "ccrs_hazard.csv"
HAZARD_COLUMNS = ("hazard_gfdl_esm4", "hazard_miroc6")


def age_factor_apply_to_hazard(
    hazard_csv: Path = HAZARD_CSV,
    age_factors: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Multiply every Hazard column of ``hazard_csv`` by ``age_factor`` per
    ``plant_uid``. Adds ``age``, ``age_factor``, the neutralised flag, and one
    ``{col}_aged`` column per Hazard column. Never sums."""
    hz = pd.read_csv(hazard_csv)
    af = age_factors if age_factors is not None else compute_age_factors()
    af_small = af[[
        PLANT_UID, "age", "age_factor", "age_factor_neutralized_missing_year",
    ]]

    missing = set(hz[PLANT_UID]) - set(af_small[PLANT_UID])
    if missing:
        raise ValueError(
            f"{len(missing)} plant_uid in {hazard_csv.name} have no age_factor "
            f"-- the CSV is stale relative to load_plants. Regenerate it with "
            f"`python -m src.index.ccrs_calculator`."
        )

    out = hz.merge(af_small, on=PLANT_UID, how="left", validate="many_to_one")
    for col in HAZARD_COLUMNS:
        if col in out.columns:
            out[f"{col}_aged"] = out[col] * out["age_factor"]
    return out


def event_multiplier_apply_to_hazard(
    hazard_csv: Path = HAZARD_CSV,
    multipliers: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Join ``event_multiplier`` onto every row of ``hazard_csv`` by
    ``country`` and multiply every Hazard column by it. Adds ``n_events``,
    ``rate``, ``event_multiplier``, and one ``{col}_x_event`` column per
    Hazard column. Never sums.

    Country-level join only -- every ``plant_uid`` in a country gets the same
    multiplier. Fails loud (not a silent drop or fan-out) if the join would
    change the row count, or if any country in ``hazard_csv`` has no
    multiplier.
    """
    hz = pd.read_csv(hazard_csv)
    em = multipliers if multipliers is not None else compute_event_multipliers()
    em_small = em[["country", "n_events", "rate", "event_multiplier"]]

    missing = set(hz["country"]) - set(em_small["country"])
    if missing:
        raise ValueError(
            f"{len(missing)} countries in {hazard_csv.name} have no "
            f"EventMultiplier: {sorted(missing)}. Extend `countries` passed "
            f"to compute_event_multipliers()."
        )

    before = len(hz)
    out = hz.merge(em_small, on="country", how="left", validate="many_to_one")
    if len(out) != before:
        raise RuntimeError(
            f"event_multiplier_apply_to_hazard: row count changed {before} -> "
            f"{len(out)} after the country join -- the multiplier table must "
            f"have exactly one row per country (duplicate country rows would "
            f"cross-join and inflate plant_uid rows)."
        )

    for col in HAZARD_COLUMNS:
        if col in out.columns:
            out[f"{col}_x_event"] = out[col] * out["event_multiplier"]
    return out
