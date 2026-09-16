"""Tests for src/orchestrator.py.

Covers only ``_band_cuts_frame`` (pure function, no I/O) -- the one piece of
the orchestrator with no prior test coverage. The rest of the orchestrator
(step functions, manifest hashing) drives real upstream pipeline steps and
is exercised by the actual pipeline runs already on disk
(``data/outputs/tables/band_cuts.csv``), not by unit tests here.
"""

from __future__ import annotations

import pandas as pd

from src.index import risk_bands as rb
from src import orchestrator as orch


def test_band_cuts_frame_one_row_per_tier3_hazard_bucket():
    percentile_cuts = {
        ("spei", "hydro"): {
            "diagnostic_percentile": 50.0, "diagnostic_value": 2.51,
            "band_cuts": (2.85, 3.13, 3.34), "n": 32424,
        },
        ("precip", "hydro"): {
            "diagnostic_percentile": 50.0, "diagnostic_value": 5.37,
            "band_cuts": (6.53, 7.73, 8.37), "n": 32424,
        },
    }
    result = rb.RiskBandTable(
        frame=pd.DataFrame(), percentile_cuts=percentile_cuts, model="gfdl_esm4",
    )

    out = orch._band_cuts_frame(result)

    assert len(out) == 2
    assert set(out["hazard_term"]) == {"spei", "precip"}
    assert (out["model"] == "gfdl_esm4").all()
    spei_row = out[out["hazard_term"] == "spei"].iloc[0]
    assert spei_row["bucket"] == "hydro"
    assert spei_row["diagnostic_percentile"] == 50.0
    assert spei_row["band_cuts"] == "2.85, 3.13, 3.34"
    assert spei_row["n"] == 32424


def test_band_cuts_frame_empty_when_no_tier3_hazards_classified():
    result = rb.RiskBandTable(frame=pd.DataFrame(), percentile_cuts={}, model="gfdl_esm4")
    out = orch._band_cuts_frame(result)
    assert out.empty


def test_band_cuts_csv_persisted_on_disk_from_real_pipeline_run():
    from src.config import OUTPUT_TABLES
    path = OUTPUT_TABLES / "band_cuts.csv"
    if not path.exists():
        import pytest
        pytest.skip("band_cuts.csv not yet produced -- run src.orchestrator or src.index.risk_bands' step first")
    df = pd.read_csv(path)
    assert {"hazard_term", "bucket", "model", "diagnostic_percentile", "band_cuts", "n"}.issubset(df.columns)
    assert not df.empty
