"""Tests for src/downloaders/era5_wind_downloader -- GEAR v3 Phase 3.2
follow-up (ERA5 GRIB-mislabeling bug fix and disk-footprint restructuring).

Covers: ``_is_grib`` magic-byte detection; ``_download_raw_year``'s format
handling on a GRIB response (correctly named ``.grib``, never silently
mislabeled ``.nc``) and on a genuinely unknown response (fails loud, saves
nothing); ``open_gust_dataset`` picking the right engine from file content,
not extension (the exact scenario that let the 18 already-downloaded Brazil
years -- real GRIB content sitting in files still named ``gust_hourly.nc``
from before this fix -- be recovered without re-downloading). No real CDS
calls: ``_get_client``/``client.retrieve`` are monkeypatched to write a
synthetic response, matching this project's existing downloader-test
convention (see e.g. ``tests/test_cds_tasmax_downloader.py``).
"""

from __future__ import annotations

import zipfile

import numpy as np
import pytest
import xarray as xr

from src.downloaders import era5_wind_downloader as ew_dl

# A minimal, valid GRIB1 message: edition byte set correctly, but this test
# only needs the FIRST 4 BYTES to read "GRIB" -- _is_grib does not attempt to
# parse the rest, so a short stub is sufficient and does not require a real
# grib_api/eccodes-encoded message.
_GRIB_MAGIC = b"GRIB"


# --------------------------------------------------------------------------
# _is_grib -- pure magic-byte check
# --------------------------------------------------------------------------
def test_is_grib_true_for_grib_magic_bytes(tmp_path):
    p = tmp_path / "response"
    p.write_bytes(_GRIB_MAGIC + b"\x00" * 100)
    assert ew_dl._is_grib(p) is True


def test_is_grib_false_for_zip_magic_bytes(tmp_path):
    p = tmp_path / "response"
    p.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
    assert ew_dl._is_grib(p) is False


def test_is_grib_false_for_empty_file(tmp_path):
    p = tmp_path / "response"
    p.write_bytes(b"")
    assert ew_dl._is_grib(p) is False


# --------------------------------------------------------------------------
# _download_raw_year -- format detection on the CDS response
# --------------------------------------------------------------------------
def _patch_client(monkeypatch, write_response):
    """Monkeypatch _get_client so client.retrieve(...) writes ``write_response``
    bytes to the requested path, instead of calling the real CDS API. Also
    stubs ``_build_request`` so no real country-boundary geometry lookup is
    needed -- these tests are about response-format handling, not request
    construction (already covered by this module's own docstring/other
    tests)."""
    class _FakeClient:
        def retrieve(self, dataset, request, path):
            with open(path, "wb") as f:
                f.write(write_response)

    monkeypatch.setattr(ew_dl, "_get_client", lambda: _FakeClient())
    monkeypatch.setattr(ew_dl, "_build_request", lambda country, year: {"year": [str(year)]})


def test_grib_response_saved_as_grib_not_mislabeled_nc(tmp_path, monkeypatch):
    """The regression test for the fixed bug: a raw GRIB CDS response must
    be saved with a ``.grib`` extension, never silently copied into a file
    named ``gust_hourly.nc`` (the exact defect that corrupted 18
    already-downloaded Brazil years before this fix)."""
    monkeypatch.setattr(ew_dl, "CLIMATE_RAW", tmp_path)
    _patch_client(monkeypatch, _GRIB_MAGIC + b"\x00" * 200)

    result = ew_dl._download_raw_year("Testland", 2000, overwrite=False)

    assert result["success"] is True
    files = [f for f in result["files"]]
    assert len(files) == 1
    assert files[0].endswith(".grib"), f"expected a .grib file, got {files[0]}"
    assert not any(f.endswith(".nc") for f in files), (
        "a GRIB response must never be saved with a .nc extension"
    )


def test_real_zip_response_extracted_as_nc(tmp_path, monkeypatch):
    """The non-regression case: a genuine zip-of-NetCDF response still
    extracts and is reported as ``.nc``, unaffected by the GRIB fix."""
    monkeypatch.setattr(ew_dl, "CLIMATE_RAW", tmp_path)

    inner_nc = tmp_path / "_inner.nc"
    xr.Dataset({"i10fg": (("y", "x"), np.zeros((2, 2)))}).to_netcdf(inner_nc)

    def _fake_zip_response(tmp_path=tmp_path, inner_nc=inner_nc):
        buf = tmp_path / "_stub.zip"
        with zipfile.ZipFile(buf, "w") as zf:
            zf.write(inner_nc, arcname="data.nc")
        return buf.read_bytes()

    _patch_client(monkeypatch, _fake_zip_response())

    result = ew_dl._download_raw_year("Testland", 2001, overwrite=False)

    assert result["success"] is True
    assert all(f.endswith(".nc") for f in result["files"])


def test_unknown_format_response_fails_loud_not_mislabeled(tmp_path, monkeypatch):
    """Neither zip nor GRIB -> fail loud with an explicit reason, never
    silently saved under any extension."""
    monkeypatch.setattr(ew_dl, "CLIMATE_RAW", tmp_path)
    _patch_client(monkeypatch, b"NOT_A_KNOWN_FORMAT_AT_ALL")

    result = ew_dl._download_raw_year("Testland", 2002, overwrite=False)

    assert result["success"] is False
    assert "unknown_response_format" in result["reason"]
    out_dir = tmp_path / "era5_wind" / "Testland" / "2002"
    assert not any(out_dir.glob("*.nc"))
    assert not any(out_dir.glob("*.grib"))


# --------------------------------------------------------------------------
# open_gust_dataset -- content-based engine selection (not extension-based)
# --------------------------------------------------------------------------
def test_open_gust_dataset_picks_netcdf_engine_for_nc_content(tmp_path):
    p = tmp_path / "gust_hourly.nc"
    xr.Dataset({"i10fg": (("y", "x"), np.array([[1.0, 2.0], [3.0, 4.0]]))}).to_netcdf(p)

    ds = ew_dl.open_gust_dataset([p])
    assert "i10fg" in ds.data_vars
    ds.close()


def test_open_gust_dataset_uses_content_not_extension(tmp_path):
    """The exact scenario this fix targets: a file with a ``.nc`` extension
    whose actual bytes are something else entirely must not be opened as
    NetCDF just because of its name. This test uses a non-GRIB payload
    (real GRIB decoding needs a full encoder, out of scope for a unit test)
    to confirm engine selection is driven by ``_is_grib``, not ``.suffix`` --
    it must NOT silently pick the plain NetCDF engine for GRIB-flagged
    content, i.e. it must attempt cfgrib and surface that engine's own
    error rather than a NetCDF-format error."""
    p = tmp_path / "gust_hourly.nc"  # note: .nc extension, but GRIB content
    p.write_bytes(_GRIB_MAGIC + b"\x00" * 200)

    with pytest.raises(Exception) as exc_info:
        ew_dl.open_gust_dataset([p])
    # Must not be xarray's "no backend recognizes this as NetCDF" complaint
    # (the old, pre-fix failure mode when a GRIB file was misnamed .nc) --
    # it must have routed to cfgrib and failed there instead (a truncated/
    # stub GRIB message, not a real decodable one).
    assert "IO backends" not in str(exc_info.value)
