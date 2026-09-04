"""
CCRS ``EventMultiplier_c`` -- the country-level disaster-frequency multiplier
on the Hazard term (``analysis/climate_risk_score_spec.md`` Section 7,
``docs/ARCHITECTURE.md`` Section 7.2; V2 closed, spec item C set).

No spec/ARCHITECTURE discrepancy: both give the identical formula, the
identical ``N_events`` base (239 / 38 / 622), and the identical country-level
application (checked before writing this module -- see the module's test
suite and ``docs/DECISIONS.md``).

--------------------------------------------------------------------------
Formula
--------------------------------------------------------------------------
    rate_c            = N_events(c) / EMDAT_ARCHIVE_SPAN_YEARS   (events/yr)
    rate_max          = max_c rate_c                              (India)
    EventMultiplier_c = 1 + EVENT_MULTIPLIER_K * (rate_c / rate_max)

``EVENT_MULTIPLIER_K = 0.5`` (spec Section 7 / ARCHITECTURE Section 7.2, a
judgment-call amplitude, flagged for the not-yet-implemented Monte Carlo
sensitivity of item J -- not re-derived here). ``EMDAT_ARCHIVE_SPAN_YEARS =
124`` (1900-2024, the EM-DAT Archive's covered span) cancels exactly out of
``rate_c / rate_max``, so the ratio reduces to ``N_events(c) /
N_events(India)``; it is kept in the formula because both source documents
state it this way and for interpretability (a "rate" is more legible than a
raw ratio of counts), not because the span changes the result.
``EventMultiplier_c >= 1`` always -- the reference country (the one with
``rate_c == rate_max``, currently India) sits at ``1 + k``, never at 1; no
country is scored *down*.

--------------------------------------------------------------------------
``N_events(c)`` -- no invented normalisation
--------------------------------------------------------------------------
``N_events(c)`` is the row count of ``data/raw/validation/emdat_{country}.csv``
(``emdat_downloader.country_csv_path``) -- the file is **already** filtered to
this country's ISO code and to the four climate-relevant disaster types
(``emdat_downloader.DISASTER_TYPES`` = Drought, Extreme temperature, Flood,
Storm), i.e. it already **is** the "type-filtered eligible EM-DAT event
count" both source documents refer to. No further filtering, weighting, or
per-capacity / per-plant-count normalisation is applied here -- the spec and
ARCHITECTURE are explicit that ``rate_c`` is an events-per-year *national*
rate, not normalised by fleet exposure (ARCHITECTURE Section 8.3 / spec
Section 7 note this choice explicitly and flag it as *not* to be
re-derived). Confirmed on the current data: 239 (Brazil), 38 (Portugal), 622
(India) rows -- exactly the counts published in both documents.

--------------------------------------------------------------------------
Application: country join, multiplicative, never additive
--------------------------------------------------------------------------
``EventMultiplier_c`` is geocoded at **country** granularity only (V2 closed
-- ``docs/DECISIONS.md`` "Event factor: country-level EM-DAT frequency"):
every ``plant_uid`` in country ``c`` gets the same ``EventMultiplier_c``,
joined on the ``country`` column, never on ``plant_uid`` or any finer key.
``apply_to_hazard`` performs this join against a Hazard-shaped CSV (default
``ccrs_hazard.csv``) and **multiplies** every Hazard column by
``event_multiplier`` -- the same multiplicative pattern
``src/index/age_factor.py`` uses for ``age_factor`` (``{col}_x_event``,
mirroring ``{col}_aged``), never summed. The join is validated
many-to-one on ``country`` (one ``event_multiplier`` row per country) with an
explicit row-count guard, so a duplicated or missing country in the
multiplier table cannot silently fan out or drop ``plant_uid`` rows -- the
same discipline ``ccrs_calculator.compute_hazard_by_gcm`` and
``age_factor.apply_to_hazard`` already apply on their own join keys.

The full ``CCRS_i,s = Hazard_i,s * age_factor_i * EventMultiplier_c``
assembly (combining all three factors into one column) is **not** done here
-- that is the separate, not-yet-written assembly module. This module proves
and tests the EventMultiplier join/multiply step in isolation, the same way
``age_factor.apply_to_hazard`` proves the age-factor step in isolation.

--------------------------------------------------------------------------
Regression fixture
--------------------------------------------------------------------------
Values recomputed against the fixture logged in ``docs/DECISIONS.md`` /
``analysis/climate_risk_score_spec.md`` Section 7 (Brazil 1.192, Portugal
1.031, India 1.500): Brazil 1.192122, Portugal 1.030547, India 1.500000 --
differences 0.000122 / 0.000453 / 0.000000, all well under the 0.01
acceptance threshold (the fixture values are 3-decimal roundings of these).
Accepted; the test fixture uses the full-precision recomputed values.

Standalone: ``python -m src.index.event_multiplier`` from the project root.
Writes ``data/outputs/tables/ccrs_event_multipliers.csv``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from src.config import COUNTRIES, OUTPUT_TABLES
from src.downloaders import emdat_downloader
from src.index import ccrs_calculator as ccrs

logger = logging.getLogger(__name__)

# Judgment-call amplitude (spec Section 7 / ARCHITECTURE Section 7.2). Not
# re-derived here -- flagged for the not-yet-implemented Monte Carlo
# sensitivity check (spec item J).
EVENT_MULTIPLIER_K = 0.5

# EM-DAT Archive covered span, 1900-2024 (emdat_downloader module docstring).
# Cancels exactly out of rate_c / rate_max; kept for interpretability and to
# match the source documents' formula verbatim.
EMDAT_ARCHIVE_SPAN_YEARS = 124

HAZARD_CSV = ccrs.OUTPUT_TABLES / "ccrs_hazard.csv"
HAZARD_COLUMNS = ("hazard_gfdl_esm4", "hazard_miroc6")


# --------------------------------------------------------------------------
# N_events and rate_c
# --------------------------------------------------------------------------
def load_event_counts(countries: list[str] = COUNTRIES) -> pd.DataFrame:
    """``N_events(c)`` per country: the row count of the already
    type/ISO-filtered ``emdat_{country}.csv``. No further filtering here."""
    rows = []
    for country in countries:
        path = emdat_downloader.country_csv_path(country)
        n = len(pd.read_csv(path))
        rows.append({"country": country, "n_events": n})
    return pd.DataFrame(rows)


def compute_event_multipliers(countries: list[str] = COUNTRIES) -> pd.DataFrame:
    """``country`` -> ``n_events``, ``rate``, ``event_multiplier``, one row
    per country. ``rate_max`` is the maximum ``rate`` among ``countries``."""
    df = load_event_counts(countries)
    df["rate"] = df["n_events"] / EMDAT_ARCHIVE_SPAN_YEARS
    rate_max = df["rate"].max()
    df["event_multiplier"] = 1.0 + EVENT_MULTIPLIER_K * (df["rate"] / rate_max)
    return df


# --------------------------------------------------------------------------
# Application to the Hazard term
# --------------------------------------------------------------------------
def apply_to_hazard(
    hazard_csv: Path = HAZARD_CSV,
    multipliers: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Join ``event_multiplier`` onto every row of ``hazard_csv`` by
    ``country`` and multiply every Hazard column by it. Adds
    ``n_events``, ``rate``, ``event_multiplier``, and one ``{col}_x_event``
    column per Hazard column. Never sums.

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
            f"apply_to_hazard: row count changed {before} -> {len(out)} after "
            f"the country join -- the multiplier table must have exactly one "
            f"row per country (duplicate country rows would cross-join and "
            f"inflate plant_uid rows)."
        )

    for col in HAZARD_COLUMNS:
        if col in out.columns:
            out[f"{col}_x_event"] = out[col] * out["event_multiplier"]
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_TABLES)
    args = parser.parse_args()

    em = compute_event_multipliers()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    em.to_csv(args.out_dir / "ccrs_event_multipliers.csv", index=False)

    for r in em.itertuples(index=False):
        logger.info("%s: n_events=%d, rate=%.4f/yr, EventMultiplier=%.4f",
                    r.country, r.n_events, r.rate, r.event_multiplier)
    logger.info("wrote ccrs_event_multipliers.csv to %s", args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
