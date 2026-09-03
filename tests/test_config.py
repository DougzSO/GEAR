"""Tests for src/config.py — credential guards and the CMIP6 model list."""

import pytest

from src import config


def test_cmip6_source_id_is_a_list_with_gfdl_only():
    assert isinstance(config.CMIP6_SOURCE_ID_CDS, list)
    assert [m for m in config.CMIP6_SOURCE_ID_CDS if m] == ["gfdl_esm4"]


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
