"""Tests for boundaries_downloader — path construction, failure handling,
mainland filter. No network access."""

import geopandas as gpd
import pytest
import requests
from shapely.geometry import MultiPolygon, Polygon, box

from src.downloaders import boundaries_downloader as bd


def test_boundary_path_uses_iso3():
    assert bd.boundary_path("Brazil").name == "gadm41_BRA.gpkg"
    assert bd.boundary_path("Portugal").as_posix().endswith(
        "raw/boundaries/gadm/gadm41_PRT.gpkg"
    )


def test_download_unknown_country_returns_none():
    assert bd.download_country_boundary("Atlantis") is None


def test_download_returns_none_when_request_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "BOUNDARIES_RAW", tmp_path)

    def _boom(*args, **kwargs):
        raise requests.exceptions.ConnectionError("no network")

    monkeypatch.setattr(bd.requests, "get", _boom)
    assert bd.download_country_boundary("Brazil", overwrite=True) is None


def test_get_country_geometry_raises_when_boundary_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(bd, "BOUNDARIES_RAW", tmp_path)
    with pytest.raises(FileNotFoundError):
        bd.get_country_geometry("India")


def test_mainland_filter_keeps_largest_polygon():
    mainland = box(-9.5, 37.0, -6.2, 42.15)          # ~ continental Portugal
    madeira = box(-17.3, 32.6, -16.6, 32.9)          # small island
    multi = MultiPolygon([mainland, madeira])

    kept = bd._apply_mainland_filter("Portugal", multi)
    assert isinstance(kept, Polygon)
    assert kept.equals(mainland)


def test_mainland_filter_noop_for_other_countries():
    multi = MultiPolygon([box(0, 0, 1, 1), box(2, 2, 3, 3)])
    assert bd._apply_mainland_filter("Brazil", multi) is multi


def test_get_country_bounds_reads_geometry(monkeypatch, tmp_path):
    gpkg = tmp_path / "gadm" / "gadm41_PRT.gpkg"
    gpkg.parent.mkdir(parents=True)
    gpd.GeoDataFrame(
        {"x": [1]}, geometry=[box(-9.5, 37.0, -6.2, 42.15)], crs="EPSG:4326"
    ).to_file(gpkg, layer=bd.GADM_LAYER, driver="GPKG")

    monkeypatch.setattr(bd, "BOUNDARIES_RAW", tmp_path)
    xmin, ymin, xmax, ymax = bd.get_country_bounds("Portugal")
    assert (round(xmin, 1), round(ymin, 1)) == (-9.5, 37.0)
