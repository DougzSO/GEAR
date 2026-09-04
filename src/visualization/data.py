"""
In-memory data assembly for the CCRS visualization module.

Every function here recomputes from ``src/index/*`` directly --
``ccrs_calculator``, ``age_factor``, ``event_multiplier``, ``risk_bands`` --
never from a cached CSV in ``data/outputs/tables/``. This matters because
those CSVs can be stale relative to the current methodology (e.g. computed
before the SPEI drought term was integrated into the Hazard formula, see
``docs/DECISIONS.md`` "[2026-09-04] SPEI drought term added to Hazard") --
a figure built from a stale CSV would silently show the wrong numbers.

``ccrs_report.compute_ccrs()`` is deliberately **not** called here: its
default ``hazard_csv`` parameter reads
``data/outputs/tables/ccrs_hazard.csv`` from disk. Instead, this module
calls ``ccrs_report.assemble_ccrs`` directly -- the disk-free core
``compute_ccrs`` itself delegates to (see that function's docstring and
``docs/memory/05-decisoes-tecnicas.md`` item 20's 2026-09-04 addendum,
an engineering decision, not methodology). There is exactly one implementation of the
Hazard x age_factor x EventMultiplier join/multiply logic in the codebase;
this module and ``compute_ccrs`` are two different callers of it, not two
implementations that happen to agree.

``risk_bands.compute_bands`` and ``ccrs_report.attach_risk_bands`` /
``compute_water_band_shares`` / ``compute_heat_band_shares`` /
``missing_commissioning_year_table`` ARE reused directly: none of them read
a CSV -- they recompute from the rasters / take an in-memory frame.
"""

from __future__ import annotations

import pandas as pd

from src.index import age_factor
from src.index import ccrs_calculator as ccrs
from src.index import event_multiplier
from src.index import risk_bands
from src.index.ccrs_calculator import PLANT_UID
from src.index.ccrs_report import (
    CCRS_COLUMNS,
    assemble_ccrs,
    attach_risk_bands,
    compute_heat_band_shares,
    compute_water_band_shares,
)
from src.index.risk_bands import PRIMARY_GCM, BandTable


def load_band_tables() -> dict[str, BandTable]:
    return {gcm: risk_bands.compute_bands(gcm) for gcm in ccrs.configured_models()}


def load_ccrs_final(
    hazard_wide: pd.DataFrame | None = None,
    age_factors: pd.DataFrame | None = None,
    event_multipliers: pd.DataFrame | None = None,
    bands: dict[str, BandTable] | None = None,
) -> pd.DataFrame:
    """The full per-plant, per-scenario CCRS frame every figure pulls from:
    ``ccrs_{gcm}`` columns, ``water_risk_band``, ``heat_risk_band_{gcm}``,
    and ``computable`` (the V6 computable-base flag,
    ``commissioning_year`` present). All arguments are optional in-memory
    overrides for tests -- with none given, everything is recomputed live
    from ``src/index/*``."""
    hz = hazard_wide if hazard_wide is not None else ccrs.compute_hazard_by_gcm()
    af = age_factors if age_factors is not None else age_factor.compute_age_factors()
    em = event_multipliers if event_multipliers is not None else event_multiplier.compute_event_multipliers()
    bands = bands if bands is not None else load_band_tables()

    ccrs_df = assemble_ccrs(hz, af, em)
    final = attach_risk_bands(ccrs_df, bands)
    final["computable"] = final["commissioning_year"].notna()
    return final


def load_age_factors() -> pd.DataFrame:
    return age_factor.compute_age_factors()


def load_event_multipliers() -> pd.DataFrame:
    return event_multiplier.compute_event_multipliers()


def load_water_band_shares(bands: dict[str, BandTable] | None = None) -> pd.DataFrame:
    bands = bands if bands is not None else load_band_tables()
    return compute_water_band_shares(bands)


def load_heat_band_shares(bands: dict[str, BandTable] | None = None) -> pd.DataFrame:
    bands = bands if bands is not None else load_band_tables()
    return compute_heat_band_shares(bands)


def top_n_by_ccrs(final: pd.DataFrame, gcm: str = PRIMARY_GCM, n: int = 10) -> pd.DataFrame:
    """Top-``n`` plants by ``ccrs_{gcm}`` (one row per plant -- the highest
    of its scenario rows), for the Top-N breakdown heatmap (category 11)."""
    col = CCRS_COLUMNS[f"hazard_{gcm}"]
    ranked = final.sort_values(col, ascending=False).drop_duplicates(subset=[PLANT_UID], keep="first")
    return ranked.head(n)
