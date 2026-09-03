"""Tests for aqueduct_downloader — path construction, GEE-not-configured
skip behaviour, and CSV validation. No Earth Engine access."""

import sys
import types

import pandas as pd
import pytest
from shapely.geometry import Point

from src.downloaders import aqueduct_downloader as aq


def test_output_path_has_no_scenario_suffix():
    p = aq.output_path("India", 2050)
    assert p.name == "aqueduct_2050.csv"
    assert p.as_posix().endswith("raw/climate/aqueduct/India/aqueduct_2050.csv")


def test_invalid_year_raises():
    with pytest.raises(ValueError):
        aq.download_aqueduct_gee("India", year=2100)


def test_skips_explicitly_when_gee_not_configured(monkeypatch, tmp_path):
    monkeypatch.setattr(aq, "CLIMATE_RAW", tmp_path)
    monkeypatch.setattr(aq, "GEE_PROJECT_ID", None)
    monkeypatch.setattr(aq, "_gee_ready", None)

    result = aq.download_aqueduct_gee("India", overwrite=True)
    assert result == {"success": False, "path": None, "reason": "gee_not_configured"}


def test_init_gee_returns_false_without_project(monkeypatch):
    monkeypatch.setattr(aq, "GEE_PROJECT_ID", "")
    monkeypatch.setattr(aq, "_gee_ready", None)
    assert aq.init_gee() is False


def _valid_frame():
    return pd.DataFrame(
        {
            "pfaf_id": [1, 2],
            "bau50_ws_x_r": [0.4, 1.1],
            "opt50_ws_x_r": [0.3, 0.9],
            "pes50_ws_x_r": [0.5, 1.4],
        }
    )


def test_validate_csv_accepts_all_scenario_columns(tmp_path):
    path = tmp_path / "aqueduct_2050.csv"
    _valid_frame().to_csv(path, index=False)
    assert aq._validate_csv(path, year=2050) is True


def test_validate_csv_rejects_missing_scenario_column(tmp_path):
    path = tmp_path / "aqueduct_2050.csv"
    _valid_frame().drop(columns=["pes50_ws_x_r"]).to_csv(path, index=False)
    assert aq._validate_csv(path, year=2050) is False


def test_validate_csv_rejects_missing_file(tmp_path):
    assert aq._validate_csv(tmp_path / "nope.csv", year=2050) is False


def test_country_geometry_is_simplified_before_earth_engine(monkeypatch, tmp_path):
    """Brazil/India full-resolution polygons exceed Earth Engine's 10 MB
    inline payload limit; the query must send a simplified polygon."""
    monkeypatch.setattr(aq, "CLIMATE_RAW", tmp_path)
    monkeypatch.setattr(aq, "GEE_PROJECT_ID", "proj")
    monkeypatch.setattr(aq, "_gee_ready", True)

    # ~4000-vertex blob -> simplify() must drop the vertex count hard
    dense = Point(0, 0).buffer(1.0, quad_segs=1000)
    monkeypatch.setattr(aq, "get_country_geometry", lambda c: dense)

    seen = {}

    class _Geom:
        def __init__(self, geojson):
            seen["n_coords"] = len(geojson["coordinates"][0])

    fake_ee = types.SimpleNamespace(
        Geometry=_Geom,
        FeatureCollection=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stop here")),
    )
    monkeypatch.setitem(sys.modules, "ee", fake_ee)

    aq.download_aqueduct_gee("Brazil", overwrite=True)
    assert seen["n_coords"] < len(dense.exterior.coords) / 5
