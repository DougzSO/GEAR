"""Tests for ibtracs_downloader -- path construction, column extraction,
wind-column reconciliation, and honest failure reporting. No NOAA NCEI
access."""

import pandas as pd
import pytest

from src.downloaders import ibtracs_downloader as ib


def test_path_construction(monkeypatch, tmp_path):
    monkeypatch.setattr(ib, "VALIDATION_RAW", tmp_path)
    assert ib.basin_raw_path("SA").name == "_ibtracs_SA_raw.csv"
    assert ib.country_csv_path("Brazil").name == "ibtracs_Brazil.csv"


def _basin_frame():
    # Mirrors the raw CSV's column set (post units-row-skip); WMO_WIND blank
    # for the third row to exercise the USA_WIND fallback.
    return pd.DataFrame(
        {
            "SID": ["A1", "A1", "A2"],
            "SEASON": [2004, 2004, 2010],
            "BASIN": ["SA", "SA", "SA"],
            "NAME": ["CATARINA", "CATARINA", "UNNAMED"],
            "ISO_TIME": ["2004-03-26 00:00:00", "2004-03-26 06:00:00", "2010-01-01 00:00:00"],
            "LAT": [-28.7, -28.9, -25.0],
            "LON": [-42.5, -43.0, -40.0],
            "WMO_WIND": [45, 60, None],
            "USA_WIND": [45, 55, 40],
        }
    )


def test_extract_track_points_keeps_expected_columns_and_max_wind(monkeypatch, tmp_path):
    monkeypatch.setattr(ib, "VALIDATION_RAW", tmp_path)
    monkeypatch.setattr(
        ib.pd, "read_csv", lambda *a, **k: _basin_frame() if "skiprows" in k else pd.DataFrame()
    )

    out = ib.extract_track_points(tmp_path / "basin.csv", "Brazil")

    assert list(out.columns) == ["SID", "SEASON", "NAME", "ISO_TIME", "LAT", "LON", "WIND_KT"]
    assert len(out) == 3
    # row 2: WMO_WIND=60 > USA_WIND=55 -> max is 60
    assert out.loc[1, "WIND_KT"] == 60
    # row 3: WMO_WIND missing -> falls back to USA_WIND=40
    assert out.loc[2, "WIND_KT"] == 40
    assert (tmp_path / "ibtracs_Brazil.csv").exists()


def test_extract_track_points_drops_rows_with_no_coordinates(monkeypatch, tmp_path):
    monkeypatch.setattr(ib, "VALIDATION_RAW", tmp_path)
    frame = _basin_frame()
    frame.loc[0, "LAT"] = None
    monkeypatch.setattr(
        ib.pd, "read_csv", lambda *a, **k: frame if "skiprows" in k else pd.DataFrame()
    )

    out = ib.extract_track_points(tmp_path / "basin.csv", "Brazil")
    assert len(out) == 2


def test_extract_track_points_raises_on_missing_columns(monkeypatch, tmp_path):
    monkeypatch.setattr(ib, "VALIDATION_RAW", tmp_path)
    monkeypatch.setattr(
        ib.pd, "read_csv", lambda *a, **k: pd.DataFrame({"SID": ["A1"]})
    )
    with pytest.raises(RuntimeError, match="missing expected columns"):
        ib.extract_track_points(tmp_path / "basin.csv", "Brazil")


def test_download_reports_error_not_silent(monkeypatch, tmp_path):
    monkeypatch.setattr(ib, "VALIDATION_RAW", tmp_path)

    def _raise(*a, **k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(ib.requests, "get", _raise)
    result = ib.download_basin("SA", overwrite=True)
    assert result["success"] is False
    assert "download_error" in result["reason"]


def test_run_pipeline_reports_per_country_failure_independently(monkeypatch):
    def _fake_download(basin, **k):
        return {"success": basin != "NA", "path": f"/tmp/{basin}.csv", "reason": "x"}

    monkeypatch.setattr(ib, "download_basin", _fake_download)
    monkeypatch.setattr(
        ib, "extract_track_points",
        lambda path, country: pd.DataFrame({"SID": ["A1"], "SEASON": [2020]}),
    )

    report = ib.run_ibtracs_pipeline(["Brazil", "Portugal"])
    assert report["overall_success"] is False  # Portugal's NA basin failed
    assert "n_track_points" in report["extract"]["Brazil"]
    assert "error" in report["extract"]["Portugal"]
