"""Tests for rivers_downloader — path construction, cache skip, explicit
failure when the archive lacks the expected shapefile. No network."""

import io
import zipfile

import pytest

from src.downloaders import rivers_downloader as rd


def test_path_points_at_expected_shapefile():
    p = rd.rivers_path()
    assert p.name == "ne_10m_rivers_lake_centerlines.shp"
    assert p.parent.name == "natural_earth_rivers"


def test_cache_skip_returns_existing(monkeypatch, tmp_path):
    shp = tmp_path / "nr" / "ne_10m_rivers_lake_centerlines.shp"
    shp.parent.mkdir(parents=True)
    shp.write_bytes(b"fake")
    monkeypatch.setattr(rd, "_OUT_DIR", shp.parent)
    monkeypatch.setattr(rd.requests, "get", lambda *a, **k: pytest.fail("network hit"))
    assert rd.download_rivers() == shp


def test_raises_when_zip_has_no_shapefile(monkeypatch, tmp_path):
    monkeypatch.setattr(rd, "_OUT_DIR", tmp_path / "nr")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("notes.txt", "nothing useful")

    class _Resp:
        content = buffer.getvalue()

        def raise_for_status(self):
            pass

    monkeypatch.setattr(rd.requests, "get", lambda *a, **k: _Resp())
    with pytest.raises(FileNotFoundError):
        rd.download_rivers(overwrite=True)
