"""Tests for coastline_downloader — path construction, cache skip, and
explicit failure when the archive lacks the expected shapefile. No network."""

import io
import zipfile

import pytest

from src.downloaders import coastline_downloader as cd


def test_path_points_at_expected_shapefile():
    p = cd.coastline_path()
    assert p.name == "ne_10m_coastline.shp"
    assert p.parent.name == "natural_earth_coastline"


def test_cache_skip_returns_existing(monkeypatch, tmp_path):
    shp = tmp_path / "natural_earth_coastline" / "ne_10m_coastline.shp"
    shp.parent.mkdir(parents=True)
    shp.write_bytes(b"fake")
    monkeypatch.setattr(cd, "_OUT_DIR", shp.parent)

    called = {"n": 0}
    monkeypatch.setattr(cd.requests, "get", lambda *a, **k: called.__setitem__("n", 1))
    assert cd.download_coastline() == shp
    assert called["n"] == 0


def test_raises_when_zip_has_no_shapefile(monkeypatch, tmp_path):
    monkeypatch.setattr(cd, "_OUT_DIR", tmp_path / "nec")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "no shapefile here")

    class _Resp:
        content = buffer.getvalue()

        def raise_for_status(self):
            pass

    monkeypatch.setattr(cd.requests, "get", lambda *a, **k: _Resp())
    with pytest.raises(FileNotFoundError):
        cd.download_coastline(overwrite=True)
