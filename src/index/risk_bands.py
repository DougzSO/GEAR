"""
GEAR v3 Phase 3.2 -- ``RiskBand_{i,h}`` threshold classification per hazard
(``docs/rework/GEAR_v3_methodology_nature_format.md`` Section 4;
``docs/rework/GEAR_v3_work_plan.md`` Phase 3.2).

Replaces the retired CCRS-era ``src/index/risk_bands.py`` (``WaterRiskBand``/
``HeatRiskBand``, imported the now-deleted ``ccrs_calculator``) exactly as
Phase 1 replaced ``ccrs_calculator.py`` with ``risk_calculator.py`` --
deleted, not deprecated, because the two-axis Water/Heat band design cannot
express ``RiskBand_{i,h}`` (one band per hazard, per Section 4's tier table),
not a data-shape this module happens to also produce.

--------------------------------------------------------------------------
Scope -- classification only
--------------------------------------------------------------------------
This module answers one question per plant/hazard/bucket: which discrete
band does ``Hazard_{i,h}`` alone fall into. It does **not**:

* touch ``normalization.py``'s transform recommendation or
  ``risk_calculator.FROZEN_BOUNDS``/``transform_term`` (Phase 3.3's job,
  Section 4.2) -- classification here runs on RAW physical values, the same
  values ``correlation_gate.py`` reads, never the Min-Max-normalized
  ``Hazard_{i,h}`` term;
* compute ``Risk_{i,h}`` (Equation 1, continuous, ``risk_calculator.py``);
* compute PSAE (Equation 2, Phase 4) -- no aggregation across a bucket's
  ``H_b`` happens here, only the per-hazard label PSAE will later count.

Only classifies a hazard for a bucket where ``src/index/hazard_scope.py``'s
``APPLICABLE_HAZARDS`` (Phase 3.1, single source of truth) marks it
applicable -- ``classify_hazard`` raises ``HazardNotApplicableError``
otherwise, never returns a silent default band.

--------------------------------------------------------------------------
Band scheme -- 4 bands everywhere a 4th percentile cut exists, no 5th label
--------------------------------------------------------------------------
Section 4 gives four hazard/bucket rows a **4-percentile** Tier 3 cutoff set
(P50/P75/P90/P95 for Extreme Heat/Drought/Extreme Precipitation-family
hazards; P75/P90/P95/P99 for Solar's Extreme Wind) while the framework
overview names exactly **4 bands** (Low/Medium/High/Extreme). Four cuts
naturally bound 5 zones -- author-decided (2026-09-12), rather than silently
picked: the **lowest** percentile of each 4-cut set is reported as a
diagnostic statistic only (``percentile_band_cuts``'s
``diagnostic_percentile``/``diagnostic_value``) and is **not** a band
boundary; the remaining 3 cuts bound the 4 canonical labels. Inventing a 5th
label ("Very High") to use every cut literally was considered and rejected:
it would inflate the band structure to accommodate an implementation detail,
the same category of move already rejected once for HAZUS-MH depth-cutoffs
(Section 4). See ``docs/DECISIONS.md``, "GEAR v3 Phase 3.2: RiskBand_i,h
threshold classification, consolidated tier/threshold table".

Tier 1 hazards need no such rule: Water Stress's WRI Aqueduct cutoffs
(0.1/0.4/0.8) are exactly 3 absolute cuts already, and Wind-bucket Extreme
Wind's single IEC cut-out speed is a genuine binary split (``Low``/
``Extreme`` only -- the same compressed 2-label scheme Section 6 already
names for Wind's PSAE, reused here rather than inventing a second one).

--------------------------------------------------------------------------
Consolidated tier/threshold table (this module's ``THRESHOLD_REGISTRY``)
--------------------------------------------------------------------------
    Hazard                  Bucket    Tier  Basis
    ----------------------  --------  ----  --------------------------------
    Water Stress            Hydro     1     WRI Aqueduct cutoffs 0.1/0.4/0.8
    Water Stress            Thermal   1     same (not bucket-specific)
    Drought (SPEI)          Hydro     3     pooled P75/P90/P95 of months/yr
                                            SPEI<=-1.0 (P50 diagnostic)
    Extreme Precipitation   Hydro     3     pooled P75/P90/P95 of days/yr
    Extreme Precipitation   Thermal   3     pr>local-P95 (P50 diagnostic;
    Extreme Precipitation   Solar     3     same cuts, bucket-invariant raw)
    Extreme Heat            Thermal   3     pooled P75/P90/P95 of days/yr
                                            tasmax>40C (P50 diagnostic)
    Extreme Heat            Solar     3     SAME cuts as Thermal -- Tier 1
                                            PV efficiency-loss-per-degree
                                            threshold closed FINAL as Tier 3
                                            (2026-09-12 bounded literature
                                            search: no single defensible
                                            cutoff exists, module-technology
                                            variance >2x, no per-plant PV
                                            technology field in GEM, PV
                                            derating is continuous not a
                                            step-function). Not provisional
                                            -- see THRESHOLD_REGISTRY note.
    Seasonal Variability     Hydro    3     pooled P75/P90/P95 of raw sv;
                                            no Section 4 entry (sv is
                                            outside Section 2's checklist) --
                                            assigned by extension of the
                                            same no-Tier-1-source percentile
                                            convention, added alongside the
                                            Phase 3.1 H_b correction that
                                            put sv in Hydro (Phase 2.5
                                            confirmed it as gate-passed).
    Interannual Variability  Hydro    3     same as Seasonal Variability
    Extreme Wind             Wind     1     IEC turbine cut-out ~25 m/s,
                                            binary (Low / Extreme)
    Extreme Wind             Solar    3     pooled P90/P95/P99 of ERA5 mean
                                            annual max gust (P75 diagnostic),
                                            final per Phase 0.4, not a
                                            placeholder

Extreme Heat/Solar was a provisional Tier 3 fallback as of Phase 3.2's
initial close; closed FINAL (not provisional) by a Phase 3.2 follow-up
bounded literature search, 2026-09-12 -- see ``docs/DECISIONS.md``, "GEAR
v3 Phase 3.2 follow-up: Solar Extreme Heat Tier 1 PV threshold -- bounded
search closed, Tier 3 confirmed final".

--------------------------------------------------------------------------
Percentile pooling convention
--------------------------------------------------------------------------
Percentile cuts are computed live from the CURRENT plant sample (never
frozen like ``FROZEN_BOUNDS``) -- Section 4 states these are "sample-relative
percentile cutoffs, explicitly not absolute physical thresholds", so a
RiskBand built from them is not comparable across runs whose sample changes
(``TIER3_COMPARABILITY_WARNING`` states this verbatim in every report).
Pooling is **global** (every configured bucket's plants, all three
countries, all three water/heat scenarios) for every percentile-based
hazard -- consistent with ``risk_calculator.compute_global_bounds``'s own
pooling convention -- never restricted to only the bucket(s) currently being
classified: the physical intensity distribution of a raster does not depend
on which bucket happens to have a plant on a given pixel.
``heat``/``spei``/``precip`` are GCM-dependent (magnitudes are not
model-comparable, ``risk_calculator.GCM_DEPENDENT_TERMS``) and are pooled
PER GCM, never blended -- ``compute_risk_bands(model=...)`` selects one GCM
at a time, defaulting to the primary GCM (GFDL-ESM4), mirroring the retired
module's ``HeatRiskBand`` convention.

Standalone: ``python -m src.index.risk_bands`` from the project root. Writes
``data/outputs/tables/risk_bands.csv`` (long format, one row per plant x
water_scenario x hazard_term) and
``data/outputs/tables/risk_bands_report.md``.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd

from src.config import COUNTRIES, OUTPUT_TABLES
from src.downloaders.cds_tasmax_downloader import configured_models
from src.index import hazard_scope as hs
from src.index import risk_calculator as rc
from src.processors.extreme_precipitation_processor import raw_raster_path as precip_raw_path
from src.processors.extreme_wind_processor import (
    IEC_TURBINE_CUTOUT_SPEED_MS,
    SOLAR_GUST_PERCENTILES,
)
from src.processors.extreme_wind_processor import raw_raster_path as wind_raw_path

logger = logging.getLogger(__name__)

PLANT_UID = rc.PLANT_UID
PRIMARY_GCM = "gfdl_esm4"
assert PRIMARY_GCM == configured_models()[0], (
    f"PRIMARY_GCM={PRIMARY_GCM!r} is no longer configured_models()[0]="
    f"{configured_models()[0]!r}"
)

# --------------------------------------------------------------------------
# Band labels
# --------------------------------------------------------------------------
BAND_LABELS = ("Low", "Medium", "High", "Extreme")
WIND_BUCKET_BAND_LABELS = ("Low", "Extreme")

# --------------------------------------------------------------------------
# Percentile sets (Section 4). GENERIC_TIER3_PERCENTILES covers every
# percentile-based hazard EXCEPT Solar's Extreme Wind, which keeps its own
# distinct P75/P90/P95/P99 set (imported from extreme_wind_processor, never
# redefined here -- the "one raw layer, threshold logic as a parameter"
# rule that module's own docstring states applies just as much to this
# module reusing its constant).
# --------------------------------------------------------------------------
GENERIC_TIER3_PERCENTILES = (50.0, 75.0, 90.0, 95.0)
WIND_SOLAR_TIER3_PERCENTILES = tuple(SOLAR_GUST_PERCENTILES)

# --------------------------------------------------------------------------
# Tier 1 absolute constants
# --------------------------------------------------------------------------
WATER_STRESS_TIER1_CUTS = (0.1, 0.4, 0.8)  # WRI Aqueduct category cutoffs, Section 4
WIND_BUCKET_TIER1_CUTOFF_MS = IEC_TURBINE_CUTOUT_SPEED_MS  # 25.0, imported not redefined

TIER3_COMPARABILITY_WARNING = (
    "RiskBands built from a Tier 3 percentile cut are sample-relative and "
    "are NOT comparable across runs whose plant sample, scenario pool, or "
    "GCM differs from the current data snapshot (Methods Section 4). Tier 1 "
    "RiskBands (Water Stress; Extreme Wind, Wind bucket) use fixed absolute "
    "cutoffs and ARE stable across runs."
)


class HazardNotApplicableError(ValueError):
    """Raised when ``classify_hazard``/``compute_risk_bands`` is asked to
    classify a (hazard, bucket) combination outside
    ``hazard_scope.APPLICABLE_HAZARDS`` (Phase 3.1's H_b table). Never
    silently skipped or defaulted to a band."""


# --------------------------------------------------------------------------
# Threshold registry -- the per-(hazard, bucket) tier/threshold assignment.
# Keys are exactly the (hazard, bucket) pairs hazard_scope.APPLICABLE_HAZARDS
# names; validated 1:1 against it at import time below.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ThresholdSpec:
    hazard: str
    bucket: str
    tier: int
    kind: str  # "absolute" | "binary" | "percentile"
    cuts: tuple[float, ...] | None = None            # "absolute" / "binary"
    percentiles: tuple[float, ...] | None = None      # "percentile"
    labels: tuple[str, ...] = BAND_LABELS
    provisional: bool = False
    note: str = ""


_PRECIP_NOTE = (
    "days/year pr > local P95 wet-day threshold; HAZUS-MH rejected as Tier 1 "
    "(structurally incompatible depth-damage curves, Section 4). Bucket-"
    "invariant raw indicator -- same pooled cuts used for Hydro/Thermal/Solar."
)

THRESHOLD_REGISTRY: dict[tuple[str, str], ThresholdSpec] = {
    ("ws", "hydro"): ThresholdSpec(
        "ws", "hydro", tier=1, kind="absolute", cuts=WATER_STRESS_TIER1_CUTS,
        note="WRI Aqueduct 4.0 category cutoffs <0.1/0.1-0.4/0.4-0.8/>0.8 (Section 4).",
    ),
    ("ws", "thermal"): ThresholdSpec(
        "ws", "thermal", tier=1, kind="absolute", cuts=WATER_STRESS_TIER1_CUTS,
        note="same absolute cutoffs as Hydro -- ws is not bucket-specific.",
    ),
    ("spei", "hydro"): ThresholdSpec(
        "spei", "hydro", tier=3, kind="percentile", percentiles=GENERIC_TIER3_PERCENTILES,
        note="months/year SPEI-12<=-1.0; no Tier 1 source linking SPEI to "
             "generation impact (Section 4). P50 diagnostic only.",
    ),
    ("precip", "hydro"): ThresholdSpec(
        "precip", "hydro", tier=3, kind="percentile", percentiles=GENERIC_TIER3_PERCENTILES,
        note=_PRECIP_NOTE,
    ),
    ("precip", "thermal"): ThresholdSpec(
        "precip", "thermal", tier=3, kind="percentile", percentiles=GENERIC_TIER3_PERCENTILES,
        note=_PRECIP_NOTE,
    ),
    ("precip", "solar"): ThresholdSpec(
        "precip", "solar", tier=3, kind="percentile", percentiles=GENERIC_TIER3_PERCENTILES,
        note=_PRECIP_NOTE,
    ),
    ("heat", "thermal"): ThresholdSpec(
        "heat", "thermal", tier=3, kind="percentile", percentiles=GENERIC_TIER3_PERCENTILES,
        note="days/year tasmax>40C; cooling-water-temperature Tier 1 rejected "
             "as a mismatched-mechanism threshold against the ambient-air "
             "tasmax variable actually modeled (Section 4). P50 diagnostic only.",
    ),
    ("heat", "solar"): ThresholdSpec(
        "heat", "solar", tier=3, kind="percentile", percentiles=GENERIC_TIER3_PERCENTILES,
        provisional=False,
        note="FINAL, not provisional (closed 2026-09-12 by a bounded "
             "literature/datasheet search, docs/DECISIONS.md 'GEAR v3 Phase "
             "3.2 follow-up: Solar Extreme Heat Tier 1 PV threshold -- "
             "bounded search closed, Tier 3 confirmed final'): no single "
             "defensible Tier 1 cutoff exists. Manufacturer Pmax temperature "
             "coefficients vary >2x by module technology (c-Si ~-0.3 to "
             "-0.5%/degC; CdTe ~-0.21%/degC; CIGS ~-0.2 to -0.45%/degC) and "
             "GEM records no module-technology field per plant (the same "
             "category of gap as Thermal's absent cooling-technology field, "
             "Section 3.2); IEC 61215/61730 measure/certify a "
             "manufacturer-specific coefficient rather than mandate one, and "
             "IEC 61730's 98th-percentile-operating-temperature<=70degC limit "
             "is a module safety qualification, not a performance-loss risk "
             "threshold, and does not convert to an ambient-air days/year "
             "metric without an irradiance/wind-dependent NOCT-style offset "
             "this pipeline does not model. No peer-reviewed study was found "
             "translating a temperature coefficient into a days/year-above-X "
             "risk threshold for utility-scale PV the way Thermal's 40degC "
             "cutoff is sourced -- PV derating is continuous in temperature "
             "deviation from 25degC STC, not a step-function, so a "
             "categorical Tier 1 cutoff does not map onto it the way a "
             "turbine cut-out speed or a fixed engineering limit does. "
             "Falls back permanently to the SAME pooled heat-day percentile "
             "cuts as Thermal (heat's raw indicator does not vary by bucket).",
    ),
    ("sv", "hydro"): ThresholdSpec(
        "sv", "hydro", tier=3, kind="percentile", percentiles=GENERIC_TIER3_PERCENTILES,
        note="No Section 4 entry (sv is outside Section 2's five-hazard "
             "checklist). Assigned Tier 3 by extension of the same "
             "no-Tier-1-source percentile convention used for Drought/"
             "Extreme Precipitation -- author-confirmed 2026-09-12, added "
             "alongside the Phase 3.1 H_b correction that put sv in Hydro "
             "(Phase 2.5 confirmed it gate-passed, |r|<=0.702).",
    ),
    ("iv", "hydro"): ThresholdSpec(
        "iv", "hydro", tier=3, kind="percentile", percentiles=GENERIC_TIER3_PERCENTILES,
        note="same rationale and percentile set as Seasonal Variability (sv).",
    ),
    ("wind", "wind"): ThresholdSpec(
        "wind", "wind", tier=1, kind="binary", cuts=(WIND_BUCKET_TIER1_CUTOFF_MS,),
        labels=WIND_BUCKET_BAND_LABELS,
        note="IEC turbine cut-out design speed ~25 m/s (~90 km/h), "
             "site-independent (Section 4; extreme_wind_processor."
             "WIND_BUCKET_THRESHOLD_SPEC). Binary: only Low/Extreme are "
             "reachable with a single cutoff -- reuses Section 6's compressed "
             "Wind PSAE label pair rather than inventing a second one.",
    ),
    ("wind", "solar"): ThresholdSpec(
        "wind", "solar", tier=3, kind="percentile", percentiles=WIND_SOLAR_TIER3_PERCENTILES,
        note="ERA5 mean-annual-max-gust (m/s) pooled P90/P95/P99 (P75 "
             "diagnostic only); final per Phase 0.4 closure, not a "
             "placeholder pending a Tier 1 value (no defensible absolute "
             "structural threshold exists for solar trackers, Section 4).",
    ),
}

_expected_keys = {(h, b) for b, hazards in hs.APPLICABLE_HAZARDS.items() for h in hazards}
if set(THRESHOLD_REGISTRY) != _expected_keys:
    raise AssertionError(
        "THRESHOLD_REGISTRY must have exactly one entry per (hazard, bucket) "
        "pair in hazard_scope.APPLICABLE_HAZARDS -- Phase 3.1's H_b table is "
        "the single source of truth for which combinations exist.\n"
        f"  missing from THRESHOLD_REGISTRY: {_expected_keys - set(THRESHOLD_REGISTRY)}\n"
        f"  extra in THRESHOLD_REGISTRY: {set(THRESHOLD_REGISTRY) - _expected_keys}"
    )


# --------------------------------------------------------------------------
# Pure band arithmetic
# --------------------------------------------------------------------------
def percentile_band_cuts(pooled_values, percentiles: tuple[float, ...] = GENERIC_TIER3_PERCENTILES) -> dict:
    """Every named percentile over the finite pooled sample, plus which of
    them are actual RiskBand boundaries vs. diagnostic-only (see module
    docstring, "Band scheme"). The LOWEST percentile in ``percentiles`` is
    always the diagnostic one; the remaining ones (in ascending order) are
    ``band_cuts``, in the exact order ``_bandize`` needs."""
    finite = np.asarray(pooled_values, "float64")
    finite = finite[~np.isnan(finite)]
    if finite.size == 0:
        raise ValueError("percentile_band_cuts: no finite values in the pooled sample")
    ordered = sorted(percentiles)
    all_cuts = {p: float(np.percentile(finite, p)) for p in ordered}
    diagnostic_p, *band_p = ordered
    return {
        "all_cuts": all_cuts,
        "diagnostic_percentile": diagnostic_p,
        "diagnostic_value": all_cuts[diagnostic_p],
        "band_percentiles": tuple(band_p),
        "band_cuts": tuple(all_cuts[p] for p in band_p),
        "n": int(finite.size),
    }


def _bandize(values, cuts: tuple[float, ...], labels: tuple[str, ...]) -> np.ndarray:
    """Left-closed banding: label i covers ``[edges[i], edges[i+1])``.
    ``len(cuts) == len(labels) - 1`` (3 cuts/4 labels for the standard
    scheme, 1 cut/2 labels for Wind's binary scheme). NaN -> ``None``."""
    if len(cuts) != len(labels) - 1:
        raise ValueError(
            f"_bandize: {len(cuts)} cuts cannot bound {len(labels)} labels "
            f"(need exactly {len(labels) - 1})"
        )
    v = np.asarray(values, "float64")
    edges = [-np.inf, *cuts, np.inf]
    out = np.full(v.shape, None, dtype=object)
    for i, label in enumerate(labels):
        out[(v >= edges[i]) & (v < edges[i + 1])] = label
    out[np.isnan(v)] = None
    return out


class ClassificationResult(NamedTuple):
    spec: ThresholdSpec
    bands: np.ndarray
    cuts_used: tuple[float, ...]
    percentile_info: dict | None


def classify_hazard(
    hazard: str, bucket: str, raw_values, pooled_values=None,
) -> ClassificationResult:
    """``RiskBand_{i,h}`` for one hazard/bucket: dispatches on
    ``THRESHOLD_REGISTRY[(hazard, bucket)].kind``, mirroring
    ``extreme_wind_processor.classify_extreme_wind``'s "one dispatcher, not
    two copy-pasted functions" pattern.

    Raises ``HazardNotApplicableError`` if ``(hazard, bucket)`` is not in
    ``hazard_scope.APPLICABLE_HAZARDS`` (Phase 3.1's H_b table) -- this is
    the guard that keeps a hazard/bucket combination Phase 3.1 marked
    inapplicable from ever getting a RiskBand, silently or otherwise.

    ``pooled_values`` is required (and only used) when the spec is Tier 3
    percentile-based; ``raw_values`` is always the values actually being
    classified (typically the bucket's own plant subset).
    """
    key = (hazard, bucket)
    if key not in THRESHOLD_REGISTRY:
        raise HazardNotApplicableError(
            f"({hazard!r}, {bucket!r}) is not an applicable hazard/bucket "
            f"combination. hazard_scope.APPLICABLE_HAZARDS[{bucket!r}] = "
            f"{hs.APPLICABLE_HAZARDS.get(bucket)!r}. RiskBand is only "
            f"defined for combinations Phase 3.1's H_b table marks "
            f"applicable (Methods Section 3)."
        )
    spec = THRESHOLD_REGISTRY[key]

    if spec.kind in ("absolute", "binary"):
        bands = _bandize(raw_values, spec.cuts, spec.labels)
        return ClassificationResult(spec, bands, spec.cuts, None)

    if spec.kind == "percentile":
        if pooled_values is None:
            raise ValueError(
                f"classify_hazard: ({hazard}, {bucket}) is Tier 3 "
                f"percentile-based -- pooled_values is required."
            )
        info = percentile_band_cuts(pooled_values, spec.percentiles)
        bands = _bandize(raw_values, info["band_cuts"], spec.labels)
        return ClassificationResult(spec, bands, info["band_cuts"], info)

    raise ValueError(f"unknown ThresholdSpec.kind {spec.kind!r}")  # pragma: no cover


# --------------------------------------------------------------------------
# Sampling -- extends risk_calculator's plant/raster infrastructure with the
# two terms it does not yet carry (precip, wind), the same pattern
# correlation_gate.py already uses for precip.
# --------------------------------------------------------------------------
def _sample_raster_or_nan(path: Path, lons: np.ndarray, lats: np.ndarray, context: str) -> np.ndarray:
    """``rc.sample_raster``, but a missing raster file returns all-NaN (with
    a logged warning) instead of crashing the whole classification run --
    e.g. Extreme Wind, whose ERA5 acquisition (Phase 2.3) has not yet
    produced a processed raster for any country as of this task."""
    if not path.exists():
        logger.warning("missing raster for %s: %s -- treating as all-NaN", context, path)
        return np.full(np.shape(lons), np.nan, dtype="float64")
    return rc.sample_raster(path, lons, lats)


def sample_hazard_terms(model: str = PRIMARY_GCM) -> pd.DataFrame:
    """One row per (plant, water_scenario), every hazard term this module
    can classify: ``ws``, ``spei``, ``heat``, ``sv``, ``iv`` (via
    ``risk_calculator.raster_path``), ``precip`` (via
    ``extreme_precipitation_processor``), ``wind`` (via
    ``extreme_wind_processor`` -- no model/scenario axis, resampled once per
    country and broadcast across every water_scenario row). Missing rasters
    come back all-NaN, never a crash (see ``_sample_raster_or_nan``)."""
    parts = []
    for country in COUNTRIES:
        plants = rc.load_plants(country)
        lons = plants["lon"].to_numpy("float64")
        lats = plants["lat"].to_numpy("float64")
        wind_vals = _sample_raster_or_nan(
            wind_raw_path(country), lons, lats, f"wind/{country}",
        )
        for water_scen in rc.WATER_SCENARIOS:
            part = plants.copy()
            part["water_scenario"] = water_scen
            part["heat_scenario"] = rc.WATER_TO_HEAT[water_scen]
            for term in ("ws", "sv", "iv", "heat", "spei"):
                part[term] = _sample_raster_or_nan(
                    rc.raster_path(term, country, water_scen, model), lons, lats,
                    f"{term}/{country}/{water_scen}/{model}",
                )
            part["precip"] = _sample_raster_or_nan(
                precip_raw_path(country, model, rc.WATER_TO_HEAT[water_scen]),
                lons, lats, f"precip/{country}/{water_scen}/{model}",
            )
            part["wind"] = wind_vals
            parts.append(part)
    return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------
# Full pipeline -- one long-format table, every applicable (hazard, bucket)
# combination.
# --------------------------------------------------------------------------
RISK_BAND_OUTPUT_COLUMNS = [
    PLANT_UID, "country", "plant_name", "bucket", "water_scenario",
    "heat_scenario", "model", "hazard_term", "hazard_label", "tier",
    "provisional", "raw_value", "risk_band",
]


class RiskBandTable(NamedTuple):
    frame: pd.DataFrame
    percentile_cuts: dict[tuple[str, str], dict]  # (hazard, bucket) -> percentile_band_cuts() result, Tier 3 only
    model: str


def compute_risk_bands(model: str = PRIMARY_GCM) -> RiskBandTable:
    """``RiskBand_{i,h}`` for every plant, for every (hazard, bucket)
    combination ``hazard_scope.APPLICABLE_HAZARDS`` marks applicable. Long
    format (one row per plant x water_scenario x hazard_term), matching
    ``risk_calculator.compute_risk_by_hazard``'s shape convention so a
    groupby/filter across hazards is always an explicit, visible step."""
    if model not in configured_models():
        raise ValueError(f"model={model!r} is not a configured GCM ({configured_models()})")

    df = sample_hazard_terms(model)
    df = df[df["bucket"].isin(hs.APPLICABLE_HAZARDS)].reset_index(drop=True)

    percentile_cuts: dict[tuple[str, str], dict] = {}
    parts = []
    for bucket, hazards in hs.APPLICABLE_HAZARDS.items():
        bucket_df = df[df["bucket"] == bucket]
        if bucket_df.empty:
            continue
        for hazard in hazards:
            spec = THRESHOLD_REGISTRY[(hazard, bucket)]
            raw = bucket_df[hazard].to_numpy("float64")

            pooled = None
            if spec.kind == "percentile":
                pooled = df[hazard].to_numpy("float64")  # globally pooled, every bucket

            try:
                result = classify_hazard(hazard, bucket, raw, pooled_values=pooled)
            except ValueError as exc:
                logger.warning(
                    "skipping (%s, %s): %s -- no finite pooled sample "
                    "(likely a not-yet-processed raster, e.g. Extreme Wind).",
                    hazard, bucket, exc,
                )
                bands = np.full(raw.shape, None, dtype=object)
                cuts_used: tuple[float, ...] = ()
                info = None
            else:
                bands, cuts_used, info = result.bands, result.cuts_used, result.percentile_info

            if info is not None:
                percentile_cuts[(hazard, bucket)] = info

            part = bucket_df[[PLANT_UID, "country", "plant_name", "bucket",
                               "water_scenario", "heat_scenario"]].copy()
            part["model"] = model
            part["hazard_term"] = hazard
            part["hazard_label"] = hs.HAZARD_LABELS[hazard]
            part["tier"] = spec.tier
            part["provisional"] = spec.provisional
            part["raw_value"] = raw
            part["risk_band"] = bands
            parts.append(part)

    out = pd.concat(parts, ignore_index=True)[RISK_BAND_OUTPUT_COLUMNS]
    key = [PLANT_UID, "water_scenario", "hazard_term", "bucket"]
    dup = int(out.duplicated(key).sum())
    if dup:
        raise RuntimeError(f"compute_risk_bands produced {dup} duplicate {key} rows.")
    return RiskBandTable(frame=out, percentile_cuts=percentile_cuts, model=model)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def build_summary(result: RiskBandTable) -> str:
    frame, cuts, model = result
    lines: list[str] = ["# GEAR v3 RiskBand_i,h -- summary\n"]

    lines.append("## Comparability warning\n")
    lines.append(TIER3_COMPARABILITY_WARNING + "\n")
    if model != PRIMARY_GCM:
        lines.append(
            f"_This run used `{model}` for the GCM-dependent hazards "
            f"(heat/spei/precip) -- the MIROC6 sensitivity panel, on its own "
            f"pooled percentiles. Not the primary-GCM cited figure._\n"
        )

    lines.append("## Consolidated tier/threshold table\n")
    rows = []
    for (hazard, bucket), spec in sorted(THRESHOLD_REGISTRY.items()):
        row = {
            "hazard": hs.HAZARD_LABELS[hazard], "bucket": bucket, "tier": spec.tier,
            "kind": spec.kind, "provisional": spec.provisional,
        }
        if (hazard, bucket) in cuts:
            info = cuts[(hazard, bucket)]
            row["diagnostic_p"] = info["diagnostic_percentile"]
            row["band_cuts"] = ", ".join(f"{v:.4g}" for v in info["band_cuts"])
            row["n"] = info["n"]
        else:
            row["diagnostic_p"] = None
            row["band_cuts"] = ", ".join(f"{v:.4g}" for v in spec.cuts) if spec.cuts else ""
            row["n"] = None
        rows.append(row)
    lines.append(pd.DataFrame(rows).to_string(index=False) + "\n")

    lines.append("## Per-hazard/bucket band distribution\n")
    for (hazard, bucket) in sorted(THRESHOLD_REGISTRY):
        sub = frame[(frame["hazard_term"] == hazard) & (frame["bucket"] == bucket)]
        banded = sub.dropna(subset=["risk_band"])
        if banded.empty:
            lines.append(f"### {hs.HAZARD_LABELS[hazard]} -- {bucket}: no classified rows\n")
            continue
        spec = THRESHOLD_REGISTRY[(hazard, bucket)]
        prov = " (PROVISIONAL)" if spec.provisional else ""
        lines.append(f"### {hs.HAZARD_LABELS[hazard]} -- {bucket} (Tier {spec.tier}{prov})\n")
        dist = banded["risk_band"].value_counts().reindex(spec.labels, fill_value=0)
        lines.append(dist.to_string() + "\n")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", default=PRIMARY_GCM, choices=configured_models(),
        help="GCM for the heat/spei/precip terms (default: the primary GCM, gfdl_esm4)",
    )
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_TABLES)
    args = parser.parse_args()

    result = compute_risk_bands(args.model)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = args.out_dir / "risk_bands.csv"
    result.frame.to_csv(csv_path, index=False)

    report = build_summary(result)
    report_path = args.out_dir / "risk_bands_report.md"
    report_path.write_text(report, encoding="utf-8")

    logger.info("wrote %s (%d rows)", csv_path, len(result.frame))
    logger.info("wrote %s", report_path)
    logger.warning("%s", TIER3_COMPARABILITY_WARNING)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
