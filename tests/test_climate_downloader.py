"""Tests for the climate acquisition orchestrator — step selection, nested
status summarisation, and the skipped-vs-failed distinction. No network."""

import pytest

from src.downloaders import climate_downloader as cl


def test_unknown_step_raises():
    with pytest.raises(ValueError):
        cl.run_climate_pipeline(steps=["boundaries", "does_not_exist"])


def test_iter_leaf_status_walks_nested_report():
    report = {
        "Brazil": {"m1": {"ssp126": {"success": True}, "ssp585": {"success": False}}},
        "India": {"success": True},
    }
    leaves = list(cl._iter_leaf_status(report))
    assert len(leaves) == 3
    assert sum(s["success"] for s in leaves) == 2


def test_skipped_true_only_for_gee_not_configured():
    all_skipped = {"Brazil": {"success": False, "reason": "gee_not_configured"}}
    one_real_failure = {"Brazil": {"success": False, "reason": "download_error: 500"}}
    assert cl._skipped(all_skipped) is True
    assert cl._skipped(one_real_failure) is False


def test_pipeline_marks_skipped_aqueduct_as_overall_success(monkeypatch, tmp_path):
    monkeypatch.setattr(cl, "LOG_DIR", tmp_path)
    monkeypatch.setattr(cl, "download_all_boundaries", lambda c, overwrite: {
        k: {"success": True, "path": "x"} for k in c
    })
    monkeypatch.setattr(cl, "download_all_aqueduct", lambda c, overwrite: {
        k: {"success": False, "path": None, "reason": "gee_not_configured"} for k in c
    })

    report = cl.run_climate_pipeline(steps=["boundaries", "aqueduct"])
    assert report["overall_success"] is True


def test_pipeline_flags_real_boundary_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(cl, "LOG_DIR", tmp_path)
    monkeypatch.setattr(cl, "download_all_boundaries", lambda c, overwrite: {
        "Brazil": {"success": True, "path": "x"},
        "Portugal": {"success": False, "path": None},
        "India": {"success": True, "path": "x"},
    })
    report = cl.run_climate_pipeline(steps=["boundaries"])
    assert report["overall_success"] is False
