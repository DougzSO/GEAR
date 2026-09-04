"""
Drought (SPEI) hazard layer -- turn the raw daily ``pr``/``tas`` series
already downloaded and validated by ``cds_precipitation_downloader`` into a
Thornthwaite-PET-based Standardised Precipitation-Evapotranspiration Index
(SPEI), reduced to a per-pixel drought-frequency raster for the 3 countries x
2 GCMs x 3 scenarios. Mirrors ``heat_stress_processor`` -- the other
GCM/scenario-indexed layer -- more closely than ``water_stress_processor``/
``water_variability_processor``, which are GCM-independent.

--------------------------------------------------------------------------
Scope -- NOT wired into the CCRS Hazard term
--------------------------------------------------------------------------
This module produces the raster layer only, same as every other processor in
this package. It does NOT enter ``src/index/ccrs_calculator.py``'s
``water_sub``/``Hazard`` formula. ``analysis/climate_risk_score_spec.md``
Section 10 item F ("Drought / SPEI term -- whether to add it, and its
weight") is still **Open**: no source of truth (the spec, ``ARCHITECTURE.md``,
``docs/DECISIONS.md``, ``docs/memory/``) assigns SPEI a weight, a position in
``water_sub``/``Hazard``, or says whether adding it changes the existing
``(0.4164, 0.2505, 0.3331)`` ws/sv/iv weights or the frozen global Min-Max
bounds (``ccrs_calculator.FROZEN_BOUNDS``). That is an author decision, not
an engineering one -- see the task report accompanying this module for the
open questions that block wiring it into ``ccrs_calculator.py``.

The method itself (Thornthwaite PET, not Hargreaves) IS settled: decided
because daily ``tasmin`` is absent from the CDS catalogue for
``gfdl_esm4``/``ssp3_7_0`` (``analysis/spei_catalog_check.md``,
``climate_risk_score_spec.md`` Section 3). One PET method across both GCMs.

--------------------------------------------------------------------------
What IS an engineering choice made here (documented, provisional)
--------------------------------------------------------------------------
Spec Section 3 fixes the PET method but not the accumulation timescale, the
drought-frequency summary statistic, or the distribution-fitting procedure --
none of that is in any source of truth. Standard, literature-default choices
are used here, in the same spirit as ``age_factor.py``'s documented
"ASSUMED" parameters (e.g. the coal overhaul cycle):

* **SPEI-12** (``SPEI_ACCUMULATION_MONTHS``, 12-month accumulation) --
  annual accumulation, matching the annual/period framing of every other
  hazard term (heat = days/year; the Aqueduct water terms = an annual
  ratio). Provisional; revisit once the SPEI Hazard-integration decision is
  made, if a different timescale is wanted.
* **Log-logistic fit via probability-weighted moments** (Hosking plotting
  position ``(i - 0.35) / n``), fitted separately per calendar month across
  the 30-year window -- the method in Vicente-Serrano, Begueria &
  Lopez-Moreno (2010, *Journal of Climate* 23(7):1696-1718), the original
  SPEI paper, and its reference ``SPEI`` R package.
* **Drought-frequency raw metric**: mean months/year with SPEI-12 <=
  ``DROUGHT_THRESHOLD`` (-1.0, "moderately dry or worse" per McKee, Doesken &
  Kleist 1993's SPI classification, reused for SPEI by the same 2010 paper).
  Chosen for the same frequency-of-extreme framing as
  ``heat_stress_processor``'s days/year-above-threshold metric.

--------------------------------------------------------------------------
Thornthwaite PET
--------------------------------------------------------------------------
Monthly PET (mm/month) per pixel::

    I  = sum_{m=1}^{12} (max(T_clim[m], 0) / 5) ** 1.514   (heat index, from
                                                             the climatological
                                                             monthly-mean T)
    a  = 6.75e-7*I**3 - 7.71e-5*I**2 + 1.792e-2*I + 0.49239
    PET0[t] = 16 * (10 * T[t] / I) ** a     if T[t] > 0 else 0
    PET[t]  = PET0[t] * K[t]

``T[t]`` is that specific month's actual mean (not the climatology), so PET
varies year to year with real temperature, while ``I``/``a`` are fixed per
pixel from the 30-year climatology -- the standard Thornthwaite convention.
``K[t]`` is the day-length correction ``(N/12)*(NDM/30)``, computed from the
solar declination / sunset-hour-angle formula (Duffie & Beckman 2013,
*Solar Engineering of Thermal Processes*) rather than interpolated from
Thornthwaite's original latitude-banded lookup table -- the same value,
computed analytically instead of read off a table.

--------------------------------------------------------------------------
Log-logistic parameters -- closed form, no new special-function dependency
--------------------------------------------------------------------------
The scale/location formulas need ``Gamma(1+1/beta)*Gamma(1-1/beta)``. Euler's
reflection formula, ``Gamma(z)*Gamma(1-z) = pi/sin(pi*z)``, with ``z =
1/beta`` and ``Gamma(1+1/beta) = (1/beta)*Gamma(1/beta)``, gives a closed
form using only ``sin``::

    Gamma(1+1/beta)*Gamma(1-1/beta) = (1/beta) * pi / sin(pi/beta)

This avoids adding ``scipy`` to this layer's ``requirements.txt`` (currently
scipy-free) for one arithmetic identity.

--------------------------------------------------------------------------
Grid
--------------------------------------------------------------------------
Computed on the native CMIP6 grid (mirrors ``heat_stress_processor`` /
``cds_precipitation_downloader``'s period-mean QA rasters), then resampled by
nearest neighbour onto the country's fixed 1 km grid
(``cds_tasmax_downloader._resample_to_1km``) -- the same corrected grid every
other layer stacks onto. Normalisation is per-country Min-Max, pooling every
configured model and scenario jointly, exactly like ``heat_stress_processor``
(SPEI depends on the GCM, like heat and unlike the Aqueduct water terms).

This module produces the raster layer only. It does not extract per-plant
values or combine hazards.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import rioxarray  # noqa: F401 - registers the .rio accessor
import xarray as xr

from src.config import CLIMATE_PROCESSED, CMIP6_SCENARIOS, COUNTRIES, CRS_TARGET
from src.downloaders.cds_precipitation_downloader import _open_series, _pick_var
from src.downloaders.cds_precipitation_downloader import raw_dir as spei_raw_dir
from src.downloaders.cds_tasmax_downloader import (
    _normalize_longitude,
    _resample_to_1km,
    configured_models,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Provisional engineering choices (see module docstring) -- not a spec F
# decision, revisit only if the eventual Hazard-integration weight decision
# calls for a different timescale/threshold.
# --------------------------------------------------------------------------
SPEI_ACCUMULATION_MONTHS = 12
DROUGHT_THRESHOLD = -1.0  # McKee, Doesken & Kleist 1993 "moderately dry or worse"
RAW_UNITS = "months_per_year_with_spei12_leq_-1.0"

# Unit conversions for the raw CMIP6 variables.
_KELVIN_OFFSET = 273.15
_PR_FLUX_TO_MM_PER_MONTH = 86400.0  # kg m-2 s-1 * 86400 s/day, summed over the
                                    # month's daily steps, = mm of water depth

# Mid-month day-of-year (non-leap reference), for the day-length formula.
_MID_MONTH_DOY = np.array([15, 45, 74, 105, 135, 166, 196, 227, 258, 288, 319, 349], dtype="float64")

# Numerical safety guards (not methodology choices): keep the log-logistic
# shape parameter away from the beta=1 singularity of the closed-form
# Gamma-product identity, and keep the log-logistic CDF away from exactly
# 0/1 before inverting to a normal quantile.
_BETA_MIN = 1.05
_BETA_MAX = 50.0
_Z_MIN = 1e-6
_CDF_EPS = 1e-6
_MIN_FIT_YEARS = 3

# Abramowitz & Stegun (1964, formula 26.2.23) rational approximation for the
# standard normal quantile -- the same approximation the original SPEI method
# (Vicente-Serrano et al. 2010) uses instead of a full inverse-error-function
# call.
_AS_C0, _AS_C1, _AS_C2 = 2.515517, 0.802853, 0.010328
_AS_D1, _AS_D2, _AS_D3 = 1.432788, 0.189269, 0.001308

# Absolute tolerance on the six affine-transform coefficients when comparing
# grids (mirrors heat_stress_processor's guard).
_TRANSFORM_ATOL = 1e-9


class GridMismatchError(ValueError):
    """Raised when the model/scenario rasters that would be pooled into one
    Min-Max domain are not on the same grid (shape, resolution/transform or
    CRS). Fail loud instead of silently misaligning the stack."""


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
def native_raster_path(country: str, model: str, scenario: str) -> Path:
    return CLIMATE_PROCESSED / f"drought_stress_raw_{country}_{model}_{scenario}_native.tif"


def raw_raster_path(country: str, model: str, scenario: str) -> Path:
    """Path to the raw physical drought-frequency layer (months/year with
    SPEI-12 <= -1.0), on the 1 km grid. Computed by this module, not a
    passthrough (unlike ``heat_stress_processor``'s raw layer, which already
    exists as the downloader's output) -- SPEI does not exist until this
    module computes it. Uniform interface with the other processors'
    ``raw_raster_path``."""
    return CLIMATE_PROCESSED / f"drought_stress_raw_{country}_{model}_{scenario}_1km.tif"


def normalized_raster_path(country: str, model: str, scenario: str) -> Path:
    return CLIMATE_PROCESSED / f"drought_stress_{country}_{model}_{scenario}_1km.tif"


# --------------------------------------------------------------------------
# Reading the raw daily series
# --------------------------------------------------------------------------
def _load_daily(country: str, model: str, scenario: str, short_name: str) -> xr.DataArray:
    """Open the raw daily ``pr``/``tas`` series already downloaded by
    ``cds_precipitation_downloader``. Raises ``FileNotFoundError`` if it is
    not on disk yet -- this module never triggers a download itself."""
    nc_dir = spei_raw_dir(country, model, scenario, short_name)
    nc_files = sorted(nc_dir.glob("*.nc"))
    if not nc_files:
        raise FileNotFoundError(
            f"No raw {short_name} .nc files for {country}/{model}/{scenario} "
            f"under {nc_dir}. Run the CDS precipitation downloader "
            f"(cds_precipitation_downloader.download_all_cds_precipitation) first."
        )
    ds = _normalize_longitude(_open_series(nc_files))
    var = _pick_var(ds, short_name)
    return ds[var]


# --------------------------------------------------------------------------
# Monthly aggregation
# --------------------------------------------------------------------------
def _monthly_aggregate(
    pr_da: xr.DataArray, tas_da: xr.DataArray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Aggregate the daily ``pr``/``tas`` series to calendar months.

    Returns ``(pr_mm, tas_c, month_of, n_days, lat)``:

    * ``pr_mm``    -- monthly total precipitation, mm, shape ``(n_months, ny, nx)``
    * ``tas_c``    -- monthly mean temperature, deg C, shape ``(n_months, ny, nx)``
    * ``month_of`` -- calendar month (1-12) of each output step, shape ``(n_months,)``
    * ``n_days``   -- calendar days in that month (this dataset's own
      calendar -- ``noleap`` for GFDL-ESM4, ``standard`` for MIROC6), shape
      ``(n_months,)``
    * ``lat``      -- 1D latitude coordinate, shape ``(ny,)``

    Grouped by ``(year, month)`` directly from the time index rather than
    ``xr.resample`` so this is identical whichever calendar the source uses --
    both a ``pandas.DatetimeIndex`` and an ``xarray`` ``CFTimeIndex`` expose
    vectorised ``.year``/``.month``.
    """
    if pr_da.shape != tas_da.shape:
        raise ValueError(f"pr/tas shape mismatch: {pr_da.shape} vs {tas_da.shape}")
    if not np.array_equal(pr_da["time"].values, tas_da["time"].values):
        raise ValueError(
            "pr and tas daily series have different time axes -- they must "
            "be downloaded together for the same country/model/scenario window."
        )

    time_index = pr_da["time"].to_index()
    years = np.asarray(time_index.year)
    months = np.asarray(time_index.month)
    keys = years * 100 + months
    order = np.unique(keys)  # ascending == chronological (year*100+month is monotonic)

    pr_vals = np.asarray(pr_da.values, dtype="float64")
    tas_vals = np.asarray(tas_da.values, dtype="float64")

    pr_mm = np.empty((len(order), *pr_vals.shape[1:]), dtype="float64")
    tas_c = np.empty((len(order), *tas_vals.shape[1:]), dtype="float64")
    month_of = np.empty(len(order), dtype="int64")
    n_days = np.empty(len(order), dtype="int64")

    for i, key in enumerate(order):
        mask = keys == key
        pr_mm[i] = pr_vals[mask].sum(axis=0) * _PR_FLUX_TO_MM_PER_MONTH
        tas_c[i] = tas_vals[mask].mean(axis=0) - _KELVIN_OFFSET
        month_of[i] = int(key % 100)
        n_days[i] = int(mask.sum())

    lat = np.asarray(pr_da["lat"].values, dtype="float64")
    return pr_mm, tas_c, month_of, n_days, lat


# --------------------------------------------------------------------------
# Thornthwaite PET
# --------------------------------------------------------------------------
def _day_length_hours(lat_deg: np.ndarray, day_of_year: np.ndarray) -> np.ndarray:
    """Mean possible sunshine duration (hours) for each latitude x
    day-of-year, from the solar declination / sunset-hour-angle formula
    (Duffie & Beckman 2013). ``lat_deg`` shape ``(ny,)``, ``day_of_year``
    shape ``(n_months,)`` -> returns shape ``(n_months, ny)``."""
    declination = 0.4093 * np.sin(2.0 * np.pi * day_of_year / 365.0 - 1.405)
    lat_rad = np.deg2rad(lat_deg)
    tan_decl = np.tan(declination)          # (n_months,)
    tan_lat = np.tan(lat_rad)               # (ny,)
    cos_ws = -tan_lat[None, :] * tan_decl[:, None]   # (n_months, ny)
    cos_ws = np.clip(cos_ws, -1.0, 1.0)     # polar day/night guard
    sunset_hour_angle = np.arccos(cos_ws)
    return (24.0 / np.pi) * sunset_hour_angle  # hours, (n_months, ny)


def _thornthwaite_pet(
    tas_c: np.ndarray, month_of: np.ndarray, n_days: np.ndarray, lat: np.ndarray
) -> np.ndarray:
    """Thornthwaite PET (mm/month), shape ``(n_months, ny, nx)``, from monthly
    mean temperature (deg C, shape ``(n_months, ny, nx)``), each step's
    calendar month (1-12) and day count, and the 1D latitude coordinate."""
    # Climatological monthly-mean T per pixel (mean over every year present
    # for that calendar month) -- the fixed per-pixel reference the heat
    # index / exponent are derived from (standard Thornthwaite convention).
    clim = np.stack([tas_c[month_of == m].mean(axis=0) for m in range(1, 13)], axis=0)  # (12, ny, nx)
    clim_pos = np.clip(clim, 0.0, None)
    heat_index = np.sum((clim_pos / 5.0) ** 1.514, axis=0)  # (ny, nx)
    exponent = (
        6.75e-7 * heat_index ** 3
        - 7.71e-5 * heat_index ** 2
        + 1.792e-2 * heat_index
        + 0.49239
    )  # (ny, nx)

    with np.errstate(divide="ignore", invalid="ignore"):
        base = np.where(heat_index[None, :, :] > 0.0, 10.0 * tas_c / heat_index[None, :, :], 0.0)
        base = np.clip(base, 0.0, None)
        pet0 = np.where(tas_c > 0.0, 16.0 * np.power(base, exponent[None, :, :]), 0.0)
    pet0 = np.nan_to_num(pet0, nan=0.0, posinf=0.0, neginf=0.0)

    month_idx0 = month_of - 1
    day_len = _day_length_hours(lat, _MID_MONTH_DOY[month_idx0])  # (n_months, ny)
    k_factor = (day_len / 12.0) * (n_days[:, None] / 30.0)        # (n_months, ny)
    pet = pet0 * k_factor[:, :, None]                              # broadcast over nx
    return pet.astype("float64")


# --------------------------------------------------------------------------
# Rolling accumulation
# --------------------------------------------------------------------------
def _rolling_accumulate(
    D: np.ndarray, month_of: np.ndarray, scale: int
) -> tuple[np.ndarray, np.ndarray]:
    """Trailing ``scale``-month sum of the monthly water balance ``D`` (shape
    ``(n_months, ny, nx)``). Returns ``(D_accum, month_of_accum)``, trimmed to
    drop the first ``scale - 1`` months (no full window before that).
    ``month_of_accum`` is the *ending* month of each window -- the calendar
    month a SPEI-``scale`` value is conventionally indexed by."""
    n_months = D.shape[0]
    if n_months < scale:
        raise ValueError(
            f"_rolling_accumulate: only {n_months} months of data, need at "
            f"least {scale} for a SPEI-{scale} window."
        )
    csum = np.concatenate([np.zeros((1, *D.shape[1:])), np.cumsum(D, axis=0)], axis=0)
    D_accum = csum[scale:] - csum[:-scale]
    month_of_accum = month_of[scale - 1:]
    return D_accum, month_of_accum


# --------------------------------------------------------------------------
# Log-logistic fit (probability-weighted moments) and standardisation
# --------------------------------------------------------------------------
def _fit_loglogistic(
    D_accum: np.ndarray, month_of_accum: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-calendar-month, per-pixel log-logistic fit via probability-
    weighted moments, the method in Vicente-Serrano, Begueria &
    Lopez-Moreno (2010).

    The moments are ``w_s = mean[(1 - F_i)**s * x_i]`` over the ascending
    order statistics, with the Landwehr/Hosking plotting position
    ``F_i = (i - 0.35) / n`` -- the ``(1 - F_i)`` (survival-function) weight
    is the Greenwood et al. (1979) convention the original SPEI paper's
    log-logistic formulas are built on, **not** a weight by ``F_i`` directly;
    using ``F_i`` instead flips the sign of the fitted ``alpha`` and inverts
    the whole SPEI ordering (caught by
    ``tests/test_spei_processor.py::test_spei_preserves_rank_within_a_calendar_month``).

    Returns ``(alpha, beta, gamma)``, each shape ``(12, ny, nx)`` -- one fit
    per calendar month, from that month's samples across every year in the
    accumulated series.
    """
    ny, nx = D_accum.shape[1], D_accum.shape[2]
    alpha = np.empty((12, ny, nx), dtype="float64")
    beta = np.empty((12, ny, nx), dtype="float64")
    gamma = np.empty((12, ny, nx), dtype="float64")

    for m in range(1, 13):
        sample = D_accum[month_of_accum == m]  # (n_years, ny, nx)
        n = sample.shape[0]
        if n < _MIN_FIT_YEARS:
            raise ValueError(
                f"_fit_loglogistic: calendar month {m} has only {n} samples "
                f"(need >= {_MIN_FIT_YEARS}) -- the accumulated series is too "
                f"short for a per-calendar-month log-logistic fit."
            )
        sorted_vals = np.sort(sample, axis=0)
        i = np.arange(1, n + 1, dtype="float64").reshape(-1, 1, 1)
        survival_weight = 1.0 - (i - 0.35) / n  # (1 - F_i), see docstring
        w0 = sorted_vals.mean(axis=0)
        w1 = (sorted_vals * survival_weight).mean(axis=0)
        w2 = (sorted_vals * survival_weight ** 2).mean(axis=0)

        beta_shape = (2.0 * w1 - w0) / (6.0 * w1 - w0 - 6.0 * w2)
        beta_shape = np.clip(beta_shape, _BETA_MIN, _BETA_MAX)

        # Gamma(1+1/beta)*Gamma(1-1/beta) in closed form -- see module
        # docstring ("Log-logistic parameters").
        g1g2 = (1.0 / beta_shape) * (np.pi / np.sin(np.pi / beta_shape))
        alpha_scale = (w0 - 2.0 * w1) * beta_shape / g1g2
        gamma_loc = w0 - alpha_scale * g1g2

        alpha[m - 1] = alpha_scale
        beta[m - 1] = beta_shape
        gamma[m - 1] = gamma_loc

    return alpha, beta, gamma


def _normal_quantile_from_cdf(cdf: np.ndarray) -> np.ndarray:
    """Standard normal quantile from a CDF value, via the Abramowitz &
    Stegun rational approximation (see module-level constants)."""
    p = np.where(cdf <= 0.5, cdf, 1.0 - cdf)
    w = np.sqrt(-2.0 * np.log(p))
    z = w - (_AS_C0 + _AS_C1 * w + _AS_C2 * w ** 2) / (
        1.0 + _AS_D1 * w + _AS_D2 * w ** 2 + _AS_D3 * w ** 3
    )
    return np.where(cdf <= 0.5, -z, z)


def _spei_from_water_balance(
    D_accum: np.ndarray,
    month_of_accum: np.ndarray,
    alpha: np.ndarray,
    beta: np.ndarray,
    gamma: np.ndarray,
) -> np.ndarray:
    """Standard-normal SPEI value for every accumulated month, per pixel,
    using that month's calendar-specific log-logistic fit. Shape matches
    ``D_accum``."""
    spei = np.empty_like(D_accum)
    for m in range(1, 13):
        mask = month_of_accum == m
        x = D_accum[mask]
        a, b, g = alpha[m - 1], beta[m - 1], gamma[m - 1]
        z = np.clip((x - g[None, :, :]) / a[None, :, :], _Z_MIN, None)
        cdf = 1.0 / (1.0 + z ** (-b[None, :, :]))
        cdf = np.clip(cdf, _CDF_EPS, 1.0 - _CDF_EPS)
        spei[mask] = _normal_quantile_from_cdf(cdf)
    return spei


def _drought_frequency(spei: np.ndarray) -> np.ndarray:
    """Mean months/year with SPEI <= ``DROUGHT_THRESHOLD``, shape
    ``(ny, nx)``."""
    return 12.0 * np.mean(spei <= DROUGHT_THRESHOLD, axis=0)


# --------------------------------------------------------------------------
# Full pipeline -> one native-grid raster
# --------------------------------------------------------------------------
def compute_drought_frequency(
    pr_da: xr.DataArray, tas_da: xr.DataArray, scale: int = SPEI_ACCUMULATION_MONTHS
) -> xr.DataArray:
    """Full pipeline: monthly aggregation -> Thornthwaite PET -> water
    balance -> SPEI-``scale`` -> drought-frequency summary. Returns a 2D
    ``(lat, lon)`` ``DataArray`` on the native grid of ``pr_da``/``tas_da``."""
    pr_mm, tas_c, month_of, n_days, lat = _monthly_aggregate(pr_da, tas_da)
    pet = _thornthwaite_pet(tas_c, month_of, n_days, lat)
    D = pr_mm - pet
    D_accum, month_of_accum = _rolling_accumulate(D, month_of, scale)
    alpha, beta, gamma = _fit_loglogistic(D_accum, month_of_accum)
    spei = _spei_from_water_balance(D_accum, month_of_accum, alpha, beta, gamma)
    freq = _drought_frequency(spei)

    out = xr.DataArray(
        freq.astype("float32"), dims=("lat", "lon"),
        coords={"lat": pr_da["lat"], "lon": pr_da["lon"]},
        name="drought_frequency_raw",
    )
    out.attrs.update(
        method=f"SPEI-{scale}, Thornthwaite PET, log-logistic PWM fit "
               f"(Vicente-Serrano, Begueria & Lopez-Moreno 2010)",
        drought_threshold=DROUGHT_THRESHOLD,
        units=RAW_UNITS,
        n_months=int(D.shape[0]),
        n_accumulated_months=int(D_accum.shape[0]),
        note=(
            "NOT wired into the CCRS Hazard term -- climate_risk_score_spec.md "
            "Section 10 item F is open (no weight/position decided). See the "
            "module docstring."
        ),
    )
    return out


def _compute_native(
    country: str, model: str, scenario: str, scale: int = SPEI_ACCUMULATION_MONTHS
) -> xr.DataArray:
    pr_da = _load_daily(country, model, scenario, "pr")
    tas_da = _load_daily(country, model, scenario, "tas")
    da = compute_drought_frequency(pr_da, tas_da, scale=scale)
    da.attrs.update(country=country, model=model, scenario=scenario)
    return da


# --------------------------------------------------------------------------
# Raw layer -- compute once, cache to disk
# --------------------------------------------------------------------------
def ensure_raw_raster(
    country: str, model: str, scenario: str,
    scale: int = SPEI_ACCUMULATION_MONTHS, overwrite: bool = False,
) -> dict:
    """Compute (if not cached) and write the native + 1 km raw drought-
    frequency raster for one country/model/scenario. Idempotent."""
    CLIMATE_PROCESSED.mkdir(parents=True, exist_ok=True)
    native_path = native_raster_path(country, model, scenario)
    raw_path = raw_raster_path(country, model, scenario)

    if raw_path.exists() and not overwrite:
        logger.info("%s/%s/%s: drought-stress raw raster cached, skipping.", country, model, scenario)
        return {"success": True, "path": str(raw_path), "reason": "cached"}

    try:
        native = _compute_native(country, model, scenario, scale=scale)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return {"success": False, "path": None, "reason": f"missing_dependency: {exc}"}

    native = native.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    native = native.rio.write_crs(CRS_TARGET)
    native.rio.to_raster(native_path)

    resampled = _resample_to_1km(native, country)
    resampled.rio.to_raster(raw_path)
    logger.info(
        "%s/%s/%s: native %s %s, raw 1km %s %s",
        country, model, scenario,
        native_path.name, tuple(native.shape),
        raw_path.name, tuple(resampled.shape),
    )
    return {
        "success": True, "path": str(raw_path), "reason": "processed",
        "native_path": str(native_path), "shape": list(resampled.shape),
    }


# --------------------------------------------------------------------------
# Grid guard + Min-Max normalisation (mirrors heat_stress_processor)
# --------------------------------------------------------------------------
def _load_raw_raster(country: str, model: str, scenario: str) -> xr.DataArray:
    path = raw_raster_path(country, model, scenario)
    if not path.exists():
        raise FileNotFoundError(
            f"Drought-stress raw raster not found: {path}. Run "
            f"ensure_raw_raster (or process_all_countries) first."
        )
    da = rioxarray.open_rasterio(path)
    return da.isel(band=0) if "band" in da.dims else da


def _grid_signature(da: xr.DataArray) -> tuple:
    transform = tuple(float(v) for v in tuple(da.rio.transform())[:6])
    return tuple(da.shape), transform, str(da.rio.crs)


def _assert_consistent_grid(country: str, rasters: dict[tuple[str, str], xr.DataArray]) -> None:
    """Fail loudly if the rasters to be pooled disagree on grid shape,
    resolution/transform or CRS. No-op for a single raster."""
    items = list(rasters.items())
    ref_key, ref_da = items[0]
    ref_shape, ref_transform, ref_crs = _grid_signature(ref_da)

    problems: list[str] = []
    for key, da in items[1:]:
        shape, transform, crs = _grid_signature(da)
        if shape != ref_shape:
            problems.append(f"{key} shape {shape} != {ref_shape} {ref_key}")
        elif not np.allclose(transform, ref_transform, rtol=0.0, atol=_TRANSFORM_ATOL):
            problems.append(f"{key} transform {transform} != {ref_transform} {ref_key}")
        if crs != ref_crs:
            problems.append(f"{key} CRS {crs} != {ref_crs} {ref_key}")

    if problems:
        raise GridMismatchError(
            f"{country}: drought-stress rasters to be pooled into one "
            f"Min-Max domain are on inconsistent grids -- joint pooling is "
            f"invalid until this is fixed:\n  " + "\n  ".join(problems)
        )


def _load_country_rasters(
    country: str, models: list[str] | None = None, scenarios: list[str] | None = None,
) -> dict[tuple[str, str], xr.DataArray]:
    models = models or configured_models()
    scenarios = scenarios or CMIP6_SCENARIOS
    rasters = {
        (model, scenario): _load_raw_raster(country, model, scenario)
        for model in models for scenario in scenarios
    }
    _assert_consistent_grid(country, rasters)
    return rasters


def compute_country_minmax(
    country: str,
    models: list[str] | None = None,
    scenarios: list[str] | None = None,
    rasters: dict[tuple[str, str], xr.DataArray] | None = None,
) -> tuple[float, float]:
    """Per-country Min-Max domain: every configured model and scenario of
    this country pooled jointly, never across countries."""
    if rasters is None:
        rasters = _load_country_rasters(country, models, scenarios)

    pooled = []
    for da in rasters.values():
        values = np.asarray(da.values, dtype="float64").ravel()
        pooled.append(values[~np.isnan(values)])

    combined = np.concatenate(pooled)
    country_min, country_max = float(combined.min()), float(combined.max())
    logger.info(
        "%s: normalisation domain (models %s x scenarios %s pooled jointly, "
        "per country): min=%.6g max=%.6g (n=%d).",
        country, sorted({m for m, _ in rasters}), sorted({s for _, s in rasters}),
        country_min, country_max, len(combined),
    )
    return country_min, country_max


def normalize_scenario(
    country: str, model: str, scenario: str,
    country_min: float, country_max: float, da: xr.DataArray | None = None,
) -> xr.DataArray:
    """Per-country Min-Max normalisation of one drought-stress raster against
    the shared country domain. NaN at the source raster's edges propagates,
    never becomes 0."""
    if da is None:
        da = _load_raw_raster(country, model, scenario)
    values = da.values.astype("float64")

    span = country_max - country_min
    if span <= 0:
        normalized = np.where(np.isnan(values), np.nan, 0.0).astype("float32")
    else:
        normalized = np.clip((values - country_min) / span, 0.0, 1.0).astype("float32")

    out = xr.DataArray(
        normalized, dims=da.dims, coords=da.coords, name="drought_stress_normalized",
    ).rio.write_crs(da.rio.crs)
    out.attrs.update(
        source="Thornthwaite-PET SPEI, months/year with SPEI-12 <= -1.0, 1 km grid",
        cmip6_model=model,
        cmip6_scenario=scenario,
        normalization="per-country Min-Max (this country's models and scenarios "
                      "pooled jointly, not across countries)",
        country=country,
        country_min=country_min,
        country_max=country_max,
        note="0 = least drought-prone cell observed in this country (any model, "
             "any scenario); 1 = most. Not comparable in absolute terms across "
             "countries. NaN = outside the country boundary (preserved from source).",
    )
    return out


def process_country_model_scenario(
    country: str, model: str, scenario: str,
    country_min: float, country_max: float,
    da: xr.DataArray | None = None, overwrite: bool = False,
) -> dict:
    """Normalise and write the drought-stress layer for one
    country/model/scenario against the shared country domain. Assumes the
    raw raster is already on disk (``ensure_raw_raster``)."""
    CLIMATE_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = normalized_raster_path(country, model, scenario)
    raw_path = raw_raster_path(country, model, scenario)
    raw_meta = {"raw_path": str(raw_path), "raw_kind": "computed", "raw_units": RAW_UNITS}

    if out_path.exists() and not overwrite:
        logger.info("%s/%s/%s: drought stress already processed, skipping.", country, model, scenario)
        return {"success": True, "path": str(out_path), "reason": "cached", **raw_meta}

    try:
        da_norm = normalize_scenario(country, model, scenario, country_min, country_max, da=da)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return {"success": False, "path": None, "reason": f"missing_dependency: {exc}"}

    da_norm.rio.to_raster(out_path)
    valid = da_norm.values[~np.isnan(da_norm.values)]
    if len(valid):
        logger.info(
            "%s/%s/%s: saved %s - %s, %d valid px, mean=%.3f (raw: %s)",
            country, model, scenario, out_path.name, da_norm.shape, len(valid),
            float(valid.mean()), raw_path.name,
        )
    else:
        logger.warning("%s/%s/%s: saved %s but 0 valid pixels (all NaN).", country, model, scenario, out_path.name)

    return {
        "success": True, "path": str(out_path), "reason": "processed",
        "shape": list(da_norm.shape), **raw_meta,
    }


def process_all_countries(
    countries: list[str] | None = None,
    scenarios: list[str] | None = None,
    models: list[str] | None = None,
    scale: int = SPEI_ACCUMULATION_MONTHS,
    overwrite: bool = False,
) -> dict:
    countries = countries or COUNTRIES
    scenarios = scenarios or CMIP6_SCENARIOS
    models = models or configured_models()

    report = {"normalization_domain": "per_country_models_and_scenarios_pooled", "countries": {}}
    for country in countries:
        raw_status: dict = {}
        all_raw_ok = True
        for model in models:
            raw_status[model] = {}
            for scenario in scenarios:
                status = ensure_raw_raster(country, model, scenario, scale=scale, overwrite=overwrite)
                raw_status[model][scenario] = status
                all_raw_ok = all_raw_ok and status["success"]

        if not all_raw_ok:
            report["countries"][country] = {"success": False, "raw": raw_status}
            continue

        try:
            rasters = _load_country_rasters(country, models, scenarios)
        except FileNotFoundError as exc:
            logger.error(str(exc))
            report["countries"][country] = {"success": False, "reason": f"missing_dependency: {exc}"}
            continue

        country_min, country_max = compute_country_minmax(country, rasters=rasters)
        entry = {"country_min": country_min, "country_max": country_max, "models": {}}
        for model in models:
            entry["models"][model] = {"scenarios": {}}
            for scenario in scenarios:
                entry["models"][model]["scenarios"][scenario] = process_country_model_scenario(
                    country, model, scenario, country_min, country_max,
                    da=rasters[(model, scenario)], overwrite=overwrite,
                )
        report["countries"][country] = entry
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--countries", nargs="+", default=None)
    parser.add_argument("--scenarios", nargs="+", default=None, choices=CMIP6_SCENARIOS)
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    result = process_all_countries(
        countries=args.countries, scenarios=args.scenarios,
        models=args.models, overwrite=args.overwrite,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    ok = all(
        c.get("success", True)
        and all(
            s["success"]
            for m in c.get("models", {}).values()
            for s in m["scenarios"].values()
        )
        for c in result["countries"].values()
    )
    sys.exit(0 if ok else 1)
