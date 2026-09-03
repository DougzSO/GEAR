"""Tests for emdat_downloader — path construction, country/disaster-type
filtering, geocoding-coverage counts, and honest failure reporting.
No Dataverse access."""

import pandas as pd
import pytest

from src import config
from src.downloaders import emdat_downloader as em


def test_path_construction(monkeypatch, tmp_path):
    monkeypatch.setattr(em, "VALIDATION_RAW", tmp_path)
    assert em.archive_path().name == "_emdat_archive_raw.xlsx"
    assert em.country_csv_path("Brazil").name == "emdat_Brazil.csv"


def _archive_frame():
    return pd.DataFrame(
        {
            "ISO": ["BRA", "BRA", "PRT", "IND", "USA", "IND"],
            "Country": ["Brazil", "Brazil", "Portugal", "India", "United States", "India"],
            "Disaster Type": ["Flood", "Earthquake", "Drought", "Storm", "Flood", "Extreme temperature"],
            "Location": ["Bahia", "Acre", None, "Odisha", "Texas", "Bihar, Assam"],
            "Start Year": [2001, 2002, 2003, 2004, 2005, 2006],
            "GADM Admin Units": ['[{"adm1":"x"}]', None, None, '[{"adm1":"y"}]', None, None],
            "Latitude": [-12.5, None, None, 20.3, None, None],
            "Longitude": [-41.7, None, None, 85.8, None, None],
        }
    )


def test_filter_and_split_applies_iso_and_type_filters(monkeypatch, tmp_path):
    monkeypatch.setattr(em, "VALIDATION_RAW", tmp_path)
    monkeypatch.setattr(em.pd, "read_excel", lambda *a, **k: _archive_frame())

    out = em.filter_and_split_by_country(tmp_path / "archive.xlsx")

    # BRA Earthquake dropped (type filter); USA dropped (country filter)
    assert sorted(out["Brazil"]["Disaster Type"]) == ["Flood"]
    assert out["Portugal"].empty is False and list(out["Portugal"]["Disaster Type"]) == ["Drought"]
    assert sorted(out["India"]["Disaster Type"]) == ["Extreme temperature", "Storm"]
    assert (tmp_path / "emdat_Brazil.csv").exists()


def test_coverage_report_counts_location_and_gadm(monkeypatch, tmp_path):
    monkeypatch.setattr(em, "OUTPUT_INSPECTION", tmp_path)
    frames = {
        "India": _archive_frame().query("ISO == 'IND'"),
    }
    cov = em.coverage_report(frames).set_index("country")
    assert cov.loc["India", "n_events"] == 2
    assert cov.loc["India", "n_with_location_text"] == 2
    assert cov.loc["India", "n_with_gadm_admin_units"] == 1
    # lat/lon is a distinct, smaller figure: only the Storm/Odisha row has both
    assert cov.loc["India", "n_with_latlon"] == 1
    assert cov.loc["India", "pct_with_latlon"] == 50.0


def test_download_reports_discovery_failure_not_silent(monkeypatch, tmp_path):
    monkeypatch.setattr(em, "VALIDATION_RAW", tmp_path)

    def _raise(**kwargs):
        raise RuntimeError("dataset structure changed")

    monkeypatch.setattr(em, "discover_archive_file", _raise)
    result = em.download_emdat_archive(overwrite=True)
    assert result["success"] is False
    assert "discovery_error" in result["reason"]


def test_run_pipeline_stops_when_download_fails(monkeypatch):
    monkeypatch.setattr(
        em, "download_emdat_archive", lambda **k: {"success": False, "reason": "x"}
    )
    report = em.run_emdat_pipeline()
    assert report["overall_success"] is False
    assert "event_counts" not in report


def test_require_portal_credentials_raises(monkeypatch):
    monkeypatch.setattr(config, "EMDAT_PORTAL_EMAIL", None)
    monkeypatch.setattr(config, "EMDAT_PORTAL_PASSWORD", None)
    with pytest.raises(config.MissingCredentialError):
        config.require_emdat_portal_credentials()
