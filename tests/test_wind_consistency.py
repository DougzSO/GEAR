"""Regression tests for the Extreme Wind data gap closed 2026-09-14.

Between 2026-09-12 and 2026-09-13 ``wind`` had RiskBand coverage
(``hazard_scope.APPLICABLE_HAZARDS``) but no ``Risk_{i,h}`` (Equation 1):
``risk_calculator.HAZARD_TERMS``/``FROZEN_BOUNDS`` did not include it, so
every plant/bucket had a null ``Risk_{i,h}`` for Extreme Wind even though
RiskBand classified it -- see docs/DECISIONS.md, "GEAR v3 wind Risk_i,h
integration: empirical transform result, PENDING_RISK_I_H_HAZARDS closed".

The pure-source tests below pin the closed state directly against the
source-of-truth tables (``risk_calculator.HAZARD_TERMS``/``FROZEN_BOUNDS``,
``hazard_scope.APPLICABLE_HAZARDS``/``PENDING_RISK_I_H_HAZARDS``) so a
regression is caught with no pipeline run required. The real-data tests
below them re-check the same invariant end to end against the generated
output tables, gated on those tables' presence like the rest of the suite
(see ``tests/test_psae.py``'s ``_rasters_present``).
"""

from __future__ import annotations

import os

import pandas as pd
import pytest

from src.index import hazard_scope as hs
from src.index import risk_calculator as rc


# --------------------------------------------------------------------------
# Pure source-of-truth checks -- no I/O, always run
# --------------------------------------------------------------------------
def test_wind_is_a_hazard_term_with_frozen_bounds():
    assert "wind" in rc.HAZARD_TERMS
    assert "wind" in rc.FROZEN_BOUNDS


def test_wind_not_pending_risk_i_h():
    assert "wind" not in hs.PENDING_RISK_I_H_HAZARDS


def test_wind_applicable_to_wind_and_solar_buckets():
    assert hs.APPLICABLE_HAZARDS["wind"] == ("wind",)
    assert "wind" in hs.APPLICABLE_HAZARDS["solar"]


# --------------------------------------------------------------------------
# Real-data checks -- gated on the output tables existing
# --------------------------------------------------------------------------
_TABLES_DIR = os.path.join("data", "outputs", "tables")


def _table_present(name: str) -> bool:
    return os.path.exists(os.path.join(_TABLES_DIR, name))


@pytest.mark.skipif(not _table_present("risk_bands.csv"), reason="risk_bands.csv absent")
def test_wind_in_risk_bands():
    rb = pd.read_csv(os.path.join(_TABLES_DIR, "risk_bands.csv"))
    wind_bands = rb.loc[rb["hazard_term"] == "wind", "risk_band"]
    assert len(wind_bands) > 0
    assert wind_bands.notna().all(), "wind rows must never carry a null risk_band"


@pytest.mark.skipif(not _table_present("risk_by_hazard.csv"), reason="risk_by_hazard.csv absent")
def test_wind_in_risk_by_hazard():
    rh = pd.read_csv(os.path.join(_TABLES_DIR, "risk_by_hazard.csv"))
    wind_risk = rh.loc[rh["hazard_term"] == "wind", "risk_i_h"]
    assert len(wind_risk) > 0
    assert wind_risk.notna().all(), "wind rows must never carry a null risk_i_h"


@pytest.mark.skipif(not _table_present("psae.csv"), reason="psae.csv absent")
def test_psae_wind_bucket_complete():
    ps = pd.read_csv(os.path.join(_TABLES_DIR, "psae.csv"))
    wind_plants = ps.loc[ps["bucket"] == "wind"]
    assert len(wind_plants) > 0
    assert (wind_plants["psae_complete"] == True).all()  # noqa: E712
