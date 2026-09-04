"""
CCRS -- final per-plant assembly and the per-country capacity-share report.

This is the first module to join every term: ``Hazard_{i,s}`` (T1,
``ccrs_calculator.py``), ``age_factor_i`` (T2, ``age_factor.py``, the ``>= 1``
``2 - retention(age)`` convention) and ``EventMultiplier_{country(i)}`` (T3,
``event_multiplier.py``, country-level), plus ``WaterRiskBand`` /
``HeatRiskBand`` (T4, ``risk_bands.py``) for the capacity-share and
contingency reporting. It does not recompute any of those four modules'
logic -- it reads their public functions and joins the results.

--------------------------------------------------------------------------
Step 0 -- consistency check (done before writing this module)
--------------------------------------------------------------------------
Compared ``analysis/climate_risk_score_spec.md`` Section 2 (formula block)
against ``docs/ARCHITECTURE.md`` Section 5.1 (formula block, line 120), the
per-country capacity roll-up (spec Section 8.5 vs ARCHITECTURE Section 5.5),
and the primary-GCM-vs-sensitivity-panel rule (spec Section 8.6 vs
ARCHITECTURE Section 5.4). **No discrepancy found**: both documents give the
identical assembly formula (``CCRS_i,s = Hazard_i,s * age_factor_i *
EventMultiplier_i``, product only, never a sum), the identical capacity base
(the V6 computable base, never raw ``capacity_mw``), the identical two-shares
rule ("% capacity in water band" and "% capacity in heat band", reported side
by side, never summed into one number), and the identical GCM rule
(GFDL-ESM4 the headline figure for every quoted "% of installed capacity in
band ..." result, MIROC6 always a sensitivity panel beside it, never
blended). T1's Hazard formula, T2's ``age_factor >= 1`` convention and T3's
``EventMultiplier`` formula were each already checked against both documents
in their own tasks (see their module docstrings and ``docs/DECISIONS.md``);
this task rechecks only the assembly-level formula and the reporting rules
that are new to this module.

--------------------------------------------------------------------------
Multiplicative assembly -- product only, never a sum
--------------------------------------------------------------------------
``compute_ccrs`` computes, per ``(plant_uid, water_scenario)`` row and for
every configured GCM's Hazard column side by side::

    CCRS_{i,s} = Hazard_{i,s} * age_factor_i * EventMultiplier_{country(i)}

``age_factor_i`` is GCM- and scenario-independent (one value per
``plant_uid``, T2); ``EventMultiplier_{country(i)}`` is plant- and
scenario-independent (one value per country, T3); ``Hazard_{i,s}`` is per
``(plant_uid, water_scenario, GCM)`` (T1). Both multipliers are joined onto
the Hazard table -- ``age_factor`` on ``plant_uid``, ``EventMultiplier`` on
``country`` -- and every join is validated (``merge(..., validate=...)``)
plus an explicit row-count guard, so neither join can silently duplicate or
drop a ``plant_uid`` row. Multiplication is commutative, so the order the
three factors are written in does not change the result; the code multiplies
them in the order the spec states the formula (Hazard, then age_factor, then
EventMultiplier). Nothing here is ever summed.

--------------------------------------------------------------------------
Capacity -- V6 computable base only, asserted, never raw ``capacity_mw``
--------------------------------------------------------------------------
Every capacity total in this module goes through ``capacity_sum``, which
**asserts** every input row already has a ``commissioning_year`` (i.e. is
already the V6 computable base, ``ccrs_calculator.computable_base``) before
summing ``capacity_mw``. This is a hard ``AssertionError`` if violated --
never a log-and-continue -- so a future edit that tries to sum
``capacity_mw`` straight off the raw fleet (or off
``gem_validated_plants_*.csv``) fails loudly at the first call, not silently
downstream in a report number.

--------------------------------------------------------------------------
Report contents
--------------------------------------------------------------------------
``build_summary`` writes, in one Markdown report:

* ``risk_bands.HEAT_BAND_WARNING`` verbatim (T4) -- HeatRiskBand is not
  comparable across runs with a different scenario/GCM pool; WaterRiskBand
  is stable.
* The wind ``age_factor`` fallback note (T2) -- ``CF_initial`` does not exist
  in any GEM file, so every wind plant uses the uniform 0.4%/yr relative
  retention rate.
* The per-country missing-``commissioning_year`` fraction (T2) -- these
  plants carry a neutral ``age_factor`` (1.0) and are kept, never dropped;
  India's ~9.7% (vs Brazil ~1.8%, Portugal ~2.4%) is the largest.
* % of V6-computable-base capacity in each ``WaterRiskBand`` (GCM-independent
  -- reported once per country x water_scenario, not duplicated per GCM,
  since the value is identical either way) and each ``HeatRiskBand`` (per
  country x heat_scenario x GCM -- GFDL-ESM4 the headline figure, MIROC6 the
  sensitivity panel, its own rows, never blended). A ``"NO_BAND"`` row per
  group covers plants with no finite term value (outside any Aqueduct basin
  or heat raster cell), so ``capacity_share`` sums to exactly 1.0 within
  every group.
* The ``WaterRiskBand x HeatRiskBand`` contingency table, reusing
  ``risk_bands.contingency_table`` (T4) directly -- not reimplemented here --
  once per GCM (primary + sensitivity panel). A cross-tabulation, never a
  single combined score.
* An informational CCRS-score distribution summary (p50/p95/max per GCM
  column) -- not a capacity share, just a sanity sample of the assembled
  score.

--------------------------------------------------------------------------
Identity
--------------------------------------------------------------------------
``plant_uid`` (``ccrs_calculator``'s content hash) is the sole plant key in
every join, groupby and output column here -- never ``plant_name`` or a
positional index (the T1 lesson).

Standalone: ``python -m src.index.ccrs_report`` from the project root. Writes
``data/outputs/tables/ccrs_final.csv``,
``data/outputs/tables/ccrs_water_band_capacity_shares.csv``,
``data/outputs/tables/ccrs_heat_band_capacity_shares.csv`` and
``data/outputs/tables/ccrs_report.md``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from src.index import age_factor
from src.index import ccrs_calculator as ccrs
from src.index import event_multiplier
from src.index import risk_bands
from src.index.ccrs_calculator import PLANT_UID
from src.index.risk_bands import (
    HEAT_BAND_WARNING,
    HEAT_RISK_BANDS,
    PRIMARY_GCM,
    WATER_RISK_BANDS,
    BandTable,
)

logger = logging.getLogger(__name__)

HAZARD_CSV = ccrs.OUTPUT_TABLES / "ccrs_hazard.csv"

# Hazard column -> CCRS column, one pair per configured GCM (mirrors
# age_factor.HAZARD_COLUMNS / event_multiplier.HAZARD_COLUMNS).
CCRS_COLUMNS = {"hazard_gfdl_esm4": "ccrs_gfdl_esm4", "hazard_miroc6": "ccrs_miroc6"}

WIND_FALLBACK_NOTE = (
    f"age_factor for wind uses a uniform {age_factor.WIND_RELATIVE_RATE:.1%}/yr "
    f"relative retention rate for every wind plant (age_factor.WIND_RELATIVE_RATE). "
    f"CF_initial (initial capacity factor) does not exist in any GEM file for any "
    f"of the 1986 wind plants across the three countries, so the CF_initial-based "
    f"form (age_factor._wind_retention_from_cf_initial) is dead code and is never "
    f"called -- see src/index/age_factor.py and docs/DECISIONS.md 2026-09-04."
)


# --------------------------------------------------------------------------
# Capacity -- V6 computable base only, asserted
# --------------------------------------------------------------------------
def capacity_sum(df: pd.DataFrame) -> float:
    """Sum ``capacity_mw`` over ``df`` -- only valid if ``df`` is already
    limited to the V6 computable base (every row has a ``commissioning_year``).

    Fails loud (``AssertionError``, never a log line) if a row without
    ``commissioning_year`` -- i.e. outside the computable base -- reaches
    here: callers must pass ``ccrs_calculator.computable_base(df)`` in first,
    never the raw fleet or ``capacity_mw`` straight off
    ``gem_validated_plants_*.csv`` (``ARCHITECTURE.md`` Section 5.5, spec
    Section 8.5, closed V6 decision).
    """
    assert df["commissioning_year"].notna().all(), (
        "capacity_sum: received rows with a missing commissioning_year -- "
        "capacity must be summed over ccrs_calculator.computable_base(df), "
        "never over the raw fleet or capacity_mw directly."
    )
    return float(df["capacity_mw"].sum())


# --------------------------------------------------------------------------
# Multiplicative assembly
# --------------------------------------------------------------------------
def assemble_ccrs(
    hazard_wide: pd.DataFrame,
    age_factors: pd.DataFrame | None = None,
    event_multipliers: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """``CCRS_{i,s} = Hazard_{i,s} * age_factor_i * EventMultiplier_{country(i)}``,
    per ``(plant_uid, water_scenario)`` row, for every configured GCM's
    Hazard column (``ccrs_{gcm}``). Multiplicative only -- never summed.

    This is the **core, disk-free** assembly step -- ``hazard_wide`` must
    already be an in-memory frame (``ccrs_calculator.compute_hazard_by_gcm()``,
    or whatever a caller already has loaded); this function never reads or
    writes a file. It is the single source of truth for the CCRS
    multiplicative chain: ``compute_ccrs`` below (disk-facing, T5's public
    CLI/library entry point) and ``src/visualization/data.py`` (the
    visualization module's in-memory data layer, which cannot use
    ``compute_ccrs`` because its default reads
    ``data/outputs/tables/ccrs_hazard.csv`` -- a cached file that can be
    stale relative to the current methodology, e.g. pre-SPEI-integration)
    both call this one function -- neither re-implements the join/multiply
    logic. Engineering decision (not methodology), see
    ``docs/memory/05-decisoes-tecnicas.md`` item 20's 2026-09-04 addendum.

    ``age_factor`` joins on ``plant_uid`` (T2); ``EventMultiplier`` joins on
    ``country`` (T3). Both joins are ``validate="many_to_one"`` plus an
    explicit row-count guard: a stale/duplicate multiplier table or a country
    with no ``EventMultiplier`` fails loud instead of silently corrupting the
    row count.
    """
    af = age_factors if age_factors is not None else age_factor.compute_age_factors()
    em = event_multipliers if event_multipliers is not None else event_multiplier.compute_event_multipliers()

    af_small = af[[PLANT_UID, "age", "age_factor", "age_factor_neutralized_missing_year"]]
    em_small = em[["country", "n_events", "rate", "event_multiplier"]]

    missing_af = set(hazard_wide[PLANT_UID]) - set(af_small[PLANT_UID])
    if missing_af:
        raise ValueError(
            f"{len(missing_af)} plant_uid in the Hazard frame have no "
            f"age_factor -- stale relative to load_plants. Regenerate the "
            f"Hazard frame with `ccrs_calculator.compute_hazard_by_gcm`."
        )
    missing_em = set(hazard_wide["country"]) - set(em_small["country"])
    if missing_em:
        raise ValueError(
            f"{len(missing_em)} countries in the Hazard frame have no "
            f"EventMultiplier: {sorted(missing_em)}."
        )

    before = len(hazard_wide)
    out = hazard_wide.merge(af_small, on=PLANT_UID, how="left", validate="many_to_one")
    out = out.merge(em_small, on="country", how="left", validate="many_to_one")
    if len(out) != before:
        raise RuntimeError(
            f"assemble_ccrs: row count changed {before} -> {len(out)} after "
            f"the age_factor/EventMultiplier joins -- one of the multiplier "
            f"tables must have a duplicate key."
        )

    # Multiplicative assembly, written in the order the spec states the
    # formula (Hazard x age_factor x EventMultiplier). Multiplication is
    # commutative, so this order is not load-bearing; never summed.
    for hazard_col, ccrs_col in CCRS_COLUMNS.items():
        if hazard_col in out.columns:
            out[ccrs_col] = out[hazard_col] * out["age_factor"] * out["event_multiplier"]
    return out


def compute_ccrs(
    hazard_csv: Path = HAZARD_CSV,
    age_factors: pd.DataFrame | None = None,
    event_multipliers: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Disk-facing wrapper around ``assemble_ccrs`` -- reads ``hazard_csv``
    and delegates every bit of join/multiply logic to it. Contains no
    assembly logic of its own; kept as the public T5 entry point (CLI,
    ``main()`` below, and any existing caller) for backward compatibility."""
    hz = pd.read_csv(hazard_csv)
    return assemble_ccrs(hz, age_factors, event_multipliers)


def attach_risk_bands(
    ccrs_df: pd.DataFrame,
    band_tables: dict[str, BandTable] | None = None,
) -> pd.DataFrame:
    """Join ``water_risk_band`` (GCM-independent, T4) and one
    ``heat_risk_band_{gcm}`` column per configured GCM onto ``ccrs_df``,
    keyed by ``(plant_uid, water_scenario)``.

    ``water_risk_band`` is taken from the primary-GCM ``BandTable`` only -- it
    does not depend on ``heat_gcm`` (T4's ``compute_bands``), so joining it a
    second time from the MIROC6 ``BandTable`` would just repeat identical
    values. Every join is ``validate="one_to_one"``: both ``ccrs_df`` and
    each band frame are exactly one row per ``(plant_uid, water_scenario)``.
    """
    tables = band_tables if band_tables is not None else {
        gcm: risk_bands.compute_bands(gcm) for gcm in ccrs.configured_models()
    }
    key = [PLANT_UID, "water_scenario"]
    before = len(ccrs_df)

    out = ccrs_df.merge(
        tables[PRIMARY_GCM].frame[key + ["water_risk_band"]],
        on=key, how="left", validate="one_to_one",
    )
    for gcm, bt in tables.items():
        out = out.merge(
            bt.frame[key + ["heat_risk_band"]].rename(
                columns={"heat_risk_band": f"heat_risk_band_{gcm}"}),
            on=key, how="left", validate="one_to_one",
        )
    if len(out) != before:
        raise RuntimeError(
            f"attach_risk_bands: row count changed {before} -> {len(out)} "
            f"after the band joins."
        )
    return out


# --------------------------------------------------------------------------
# Capacity-share reporting
# --------------------------------------------------------------------------
def band_capacity_shares(
    frame: pd.DataFrame, band_col: str, bands, group_cols: list[str],
) -> pd.DataFrame:
    """% of V6-computable-base installed capacity in each label of
    ``bands``, grouped by ``group_cols`` (e.g. ``["country",
    "water_scenario"]`` or ``["country", "heat_scenario", "gcm"]``).

    Rows with no band (``band_col`` is ``None``/NaN -- a plant outside any
    Aqueduct basin or heat raster cell) are excluded from the banded rows but
    kept in the group's capacity denominator, reported as a ``"NO_BAND"``
    row -- so ``capacity_share`` sums to exactly 1.0 within every group
    (band shares alone sum to 1.0 minus the no-band fraction).
    """
    base = ccrs.computable_base(frame)
    rows = []
    for keys, g in base.groupby(group_cols, dropna=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        key_dict = dict(zip(group_cols, keys))
        total_cap = capacity_sum(g)
        banded = g.dropna(subset=[band_col])
        banded_cap = capacity_sum(banded) if len(banded) else 0.0
        for b in bands:
            cap = capacity_sum(banded[banded[band_col] == b]) if len(banded) else 0.0
            rows.append({
                **key_dict, "band": b, "capacity_mw": cap,
                "capacity_share": cap / total_cap if total_cap else 0.0,
            })
        no_band_cap = total_cap - banded_cap
        rows.append({
            **key_dict, "band": "NO_BAND", "capacity_mw": no_band_cap,
            "capacity_share": no_band_cap / total_cap if total_cap else 0.0,
        })
    return pd.DataFrame(rows)


def compute_water_band_shares(band_tables: dict[str, BandTable]) -> pd.DataFrame:
    """% capacity by WaterRiskBand, per country x water_scenario. Taken from
    the primary-GCM BandTable only -- WaterRiskBand does not depend on GCM."""
    return band_capacity_shares(
        band_tables[PRIMARY_GCM].frame, "water_risk_band", WATER_RISK_BANDS,
        ["country", "water_scenario"],
    )


def compute_heat_band_shares(band_tables: dict[str, BandTable]) -> pd.DataFrame:
    """% capacity by HeatRiskBand, per country x heat_scenario x GCM -- one
    GCM's own rows beside the other's, never blended."""
    frames = []
    for gcm, bt in band_tables.items():
        f = bt.frame.copy()
        f["gcm"] = gcm
        frames.append(f)
    combined = pd.concat(frames, ignore_index=True)
    return band_capacity_shares(
        combined, "heat_risk_band", HEAT_RISK_BANDS,
        ["country", "heat_scenario", "gcm"],
    )


def missing_commissioning_year_table(af: pd.DataFrame) -> pd.DataFrame:
    """Per-country count/fraction of plants neutralised for a missing
    ``commissioning_year`` (T2's ``age_factor_neutralized_missing_year``)."""
    rows = []
    for country in ccrs.COUNTRIES:
        sub = af[af["country"] == country]
        n = int(sub["age_factor_neutralized_missing_year"].sum())
        total = len(sub)
        rows.append({
            "country": country, "missing_commissioning_year": n,
            "total_plants": total, "fraction": n / total if total else 0.0,
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def build_summary(
    af: pd.DataFrame,
    water_shares: pd.DataFrame,
    heat_shares: pd.DataFrame,
    band_tables: dict[str, BandTable],
    ccrs_final: pd.DataFrame,
) -> str:
    """Human-readable report. Emits ``risk_bands.HEAT_BAND_WARNING`` verbatim,
    the wind fallback note, and the missing-``commissioning_year`` fraction,
    plus the capacity-share and contingency tables."""
    lines: list[str] = ["# CCRS -- final assembly summary\n"]

    lines.append("## Comparability warning (inherited from T4/risk_bands)\n")
    lines.append(HEAT_BAND_WARNING + "\n")

    lines.append("## Data caveats carried into this report (from T2/age_factor)\n")
    lines.append(WIND_FALLBACK_NOTE + "\n")
    lines.append(
        "Plants with a missing commissioning_year get a neutral age_factor "
        "(1.0) and are kept, never dropped:\n"
    )
    lines.append(missing_commissioning_year_table(af).to_string(index=False) + "\n")

    lines.append("## Multiplicative assembly\n")
    lines.append(
        "CCRS_i,s = Hazard_i,s * age_factor_i * EventMultiplier_country(i), "
        "computed for every configured GCM's Hazard column side by side "
        "(never blended). Multiplicative only, never summed -- see "
        "compute_ccrs().\n"
    )

    lines.append("## % capacity by WaterRiskBand (V6 computable base; GCM-independent)\n")
    lines.append(water_shares.to_string(index=False) + "\n")

    lines.append("## % capacity by HeatRiskBand (V6 computable base, per GCM)\n")
    lines.append(
        "GFDL-ESM4 is the primary GCM for this headline figure; MIROC6 is "
        "shown beside it as the sensitivity panel, its own rows, never "
        "blended (ARCHITECTURE.md Section 5.4).\n"
    )
    lines.append(heat_shares.to_string(index=False) + "\n")

    lines.append(
        "## WaterRiskBand x HeatRiskBand -- auxiliary contingency table "
        "(never a single combined score)\n"
    )
    for gcm, bt in band_tables.items():
        label = "primary" if gcm == PRIMARY_GCM else "sensitivity panel"
        lines.append(f"### {gcm} ({label}) -- row counts\n")
        lines.append(risk_bands.contingency_table(bt.frame, "count").to_string() + "\n")

    lines.append("## CCRS score -- informational distribution (not a capacity share)\n")
    for col in CCRS_COLUMNS.values():
        if col in ccrs_final.columns:
            s = ccrs_final[col].dropna()
            lines.append(
                f"- {col}: n={len(s)}, p50={s.median():.4f}, "
                f"p95={s.quantile(0.95):.4f}, max={s.max():.4f}\n"
            )

    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hazard-csv", type=Path, default=HAZARD_CSV)
    parser.add_argument("--out-dir", type=Path, default=ccrs.OUTPUT_TABLES)
    args = parser.parse_args()

    af = age_factor.compute_age_factors()
    em = event_multiplier.compute_event_multipliers()
    ccrs_df = compute_ccrs(args.hazard_csv, age_factors=af, event_multipliers=em)

    band_tables = {gcm: risk_bands.compute_bands(gcm) for gcm in ccrs.configured_models()}
    final = attach_risk_bands(ccrs_df, band_tables)

    water_shares = compute_water_band_shares(band_tables)
    heat_shares = compute_heat_band_shares(band_tables)
    report = build_summary(af, water_shares, heat_shares, band_tables, final)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    final.to_csv(args.out_dir / "ccrs_final.csv", index=False)
    water_shares.to_csv(args.out_dir / "ccrs_water_band_capacity_shares.csv", index=False)
    heat_shares.to_csv(args.out_dir / "ccrs_heat_band_capacity_shares.csv", index=False)
    (args.out_dir / "ccrs_report.md").write_text(report, encoding="utf-8")

    logger.info(
        "wrote ccrs_final.csv (%d rows, %d unique plant_uid), capacity-share "
        "tables, ccrs_report.md to %s",
        len(final), final[PLANT_UID].nunique(), args.out_dir,
    )
    logger.warning("%s", HEAT_BAND_WARNING)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
