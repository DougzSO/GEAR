"""Tests for src/config.py — credential guards and the CMIP6 model list."""

import pytest

from src import config


def test_cmip6_source_id_is_a_list_with_gfdl_first():
    # gfdl_esm4 must stay first: water_stress_processor uses
    # configured_models()[0] as the reference grid. miroc6 was added per the
    # closed V4 decision.
    assert isinstance(config.CMIP6_SOURCE_ID_CDS, list)
    models = [m for m in config.CMIP6_SOURCE_ID_CDS if m]
    assert models[0] == "gfdl_esm4"
    assert models == ["gfdl_esm4", "miroc6"]


def test_cmip6_scenarios_carry_ssp370_with_experiment_and_aqueduct_pairing():
    # ssp370 added per the closed V3 decision, paired with Aqueduct "bau".
    assert "ssp370" in config.CMIP6_SCENARIOS
    assert config.CMIP6_SCENARIO_TO_CDS_EXPERIMENT["ssp370"] == "ssp3_7_0"
    assert config.AQUEDUCT_SCENARIO_FOR_CMIP6["ssp370"] == "bau"
    # every heat scenario maps to a CDS experiment and an Aqueduct label
    for scenario in config.CMIP6_SCENARIOS:
        assert scenario in config.CMIP6_SCENARIO_TO_CDS_EXPERIMENT
        assert scenario in config.AQUEDUCT_SCENARIO_FOR_CMIP6


def test_require_cds_api_key_raises_when_absent(monkeypatch):
    monkeypatch.setattr(config, "CDS_API_KEY", None)
    with pytest.raises(config.MissingCredentialError) as exc:
        config.require_cds_api_key()
    assert "CDS_API_KEY" in str(exc.value)


def test_require_cds_api_key_returns_value_when_present(monkeypatch):
    monkeypatch.setattr(config, "CDS_API_KEY", "abc123")
    assert config.require_cds_api_key() == "abc123"


def test_require_gee_project_id_raises_when_absent(monkeypatch):
    monkeypatch.setattr(config, "GEE_PROJECT_ID", "")
    with pytest.raises(config.MissingCredentialError):
        config.require_gee_project_id()


def test_require_emdat_portal_credentials_raises_when_absent(monkeypatch):
    monkeypatch.setattr(config, "EMDAT_PORTAL_EMAIL", None)
    monkeypatch.setattr(config, "EMDAT_PORTAL_PASSWORD", None)
    with pytest.raises(config.MissingCredentialError):
        config.require_emdat_portal_credentials()
