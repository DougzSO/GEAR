"""
CCRS ``age_factor`` -- the ``>= 1`` asset-condition multiplier on the Hazard
term (``analysis/climate_risk_score_spec.md`` Section 6, ``docs/ARCHITECTURE.md``
Section 7.1; closes spec open item D -- see ``docs/DECISIONS.md``
"[2026-09-04] age_factor: >=1 multiplier via ``2 - retention(age)``, with
corrected coal/hydro/wind retention curves (final)").

--------------------------------------------------------------------------
Sign convention  (``>= 1``, increasing with age -- this is the definitive one)
--------------------------------------------------------------------------
``age_factor = 2 - clip(retention(age), 0, 1)``, so ``age_factor`` lives in
``[1, 2]`` and **rises** with age-driven performance loss -- an older, more
degraded plant is a higher climate risk:

    retention 1.00 (new / no loss)  -> age_factor 1.00
    retention 0.80 (20% lost)       -> age_factor 1.20  (spec Section 6 example)
    retention 0.50                  -> age_factor 1.50

``retention(age) <= 1`` is the technology's capacity / efficiency retention
curve; ``2 - retention`` turns a retention *loss* into a risk *multiplier*.
Every bucket goes through the same conversion, so a neutral retention of 1.0
returns ``age_factor`` exactly 1.0. ``clip(retention, 0, 1)`` bounds
``age_factor`` to ``[1, 2]`` and guards an implausible ``commissioning_year``;
it does not bind on the current data.

A prior session briefly flipped this module to ``age_factor = retention`` in
``[0, 1]`` (older plant -> lower factor). That was based on a mistaken reading
of which document was authoritative and is reverted:
``climate_risk_score_spec.md`` Section 6 / Section 10 item D and
``ARCHITECTURE.md`` Section 5 / Section 7.1 all specify ``age_factor >= 1``,
and that is what this module implements. See ``docs/DECISIONS.md`` for the
full history (three dated entries; only the last is active).

--------------------------------------------------------------------------
Per-technology ``retention(age)``  (age = ``REFERENCE_YEAR - commissioning_year``)
--------------------------------------------------------------------------
    Coal          sawtooth: 0.25 pp/yr decay, 5-yr overhaul cycle, 70% recovery
    Wind          1 - 0.004  * age                    linear (0.4%/yr relative)
    Hydro         1 - 0.0055 * age                    linear (0.55%/yr)
    Solar         (1 - 0.007) ** age                  compound
    Gas / oil-gas 1.0  (age_factor 1.0)   PROVISIONAL -- no literature rate exists
    Nuclear       1.0  (age_factor 1.0)   licensing-governed, not gradual decay
    Bioenergy     1.0  (age_factor 1.0)   coal proxy dropped in the V1 revision
    Mixed fuel    simple average of the component fuels' age_factor

Coal -- the 0.25 pp/yr boiler heat-rate deterioration is from the literature
(IEA/CIAB 2010; Kim & Moon 2012, 500 MW unit; Sagaf 2020, *Journal of Thermal
Engineering* 6(6):247-256, 660 MW unit, 0.19-0.44 %/yr, 0.25 pp/yr central).
No GEM file carries a per-plant overhaul date, so an **assumed** overhaul
schedule is applied: a 5-year cycle, and at the end of each complete cycle
70% of the efficiency loss accumulated during that cycle is recovered (30%
becomes permanent). The result is a sawtooth -- decay within a cycle, a
partial step back up at each cycle boundary. The 5-year cycle and the 70%
recovery fraction are **assumed parameters** (``COAL_OVERHAUL_CYCLE_YEARS``,
``COAL_OVERHAUL_RECOVERY``), a modelling premise in the absence of real
overhaul data -- **not** values taken from the cited sources. They are
provisional and revisable if a per-plant overhaul-history source appears.

Wind -- the ``0.4 %/yr`` relative rate (``WIND_RELATIVE_RATE``, midpoint of
the 0.3-0.5 %/yr range; Olauson, Edstrom & Ryden 2017, *Wind Energy*
20:2049-2053, Swedish fleet; Shin, Ko & Huh 2015, *IJMAIMME* 9:55-59; Byrne,
Astolfi, Castellani & Hewitt 2020, *Energies* 13:2086) is applied uniformly
to every wind plant. The alternative form based on the initial capacity
factor -- ``retention = 1 - 0.0015 * age / CF_initial``, where 0.0015 is the
observed *pp of capacity factor per year* -- is **not wired in**:
``_wind_retention_from_cf_initial`` is dead code kept as an executable record
of the formula. No GEM source carries a capacity factor, there is no runtime
availability check, and ``age_factor`` never calls it. It becomes live only
if a real initial-capacity-factor source is added (e.g. Global Wind Atlas or
manufacturer power curves).

Hydro -- 0.55 %/yr, the midpoint of ARCHITECTURE Section 7.1's "~0.5-0.6 %/yr"
range (Turner et al. 2024, *Nature Communications*). A prior revision scaled
this by 0.79 ("non-water-attributable share"); that factor had no documented
origin and is removed.

--------------------------------------------------------------------------
Missing ``commissioning_year``  (~5.6% of plants)
--------------------------------------------------------------------------
``age`` is undefined -> ``age_factor = 1.0`` (neutral). These rows are
**kept**, flagged (``age_factor_neutralized_missing_year``), and counted per
country in the report -- never dropped. In India this is 9.7% of plants
(vs 1.8% Brazil, 2.4% Portugal), concentrated in wind and solar -- see
``docs/memory/06-areas-de-risco.md``.

--------------------------------------------------------------------------
Identity and application
--------------------------------------------------------------------------
``plant_uid`` (``ccrs_calculator``'s content hash) is the sole plant key.
``age_factor`` is one value per ``plant_uid`` (age does not depend on scenario
or GCM); it **multiplies** every Hazard column and every scenario row of
``data/outputs/tables/ccrs_hazard.csv``. Multiplicative, never summed.

Standalone: ``python -m src.index.age_factor`` from the project root. Writes
``data/outputs/tables/ccrs_age_factors.csv``,
``data/outputs/tables/ccrs_hazard_aged.csv`` and
``data/outputs/tables/age_factor_report.md``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import COUNTRIES, YEAR_TARGET
from src.index import ccrs_calculator as ccrs
from src.index.ccrs_calculator import PLANT_UID

logger = logging.getLogger(__name__)

# The single explicit study-horizon constant (src/config.py). The CCRS hazard
# layer represents the 2041-2070 window by 2050; plant age is age at that
# horizon, consistent with the hazard. Hard-pinned to 2050 by asserts in the
# water processors.
REFERENCE_YEAR = YEAR_TARGET

NEUTRAL_AGE_FACTOR = 1.0

# retention(age) <= 1 rates. age_factor = 2 - clip(retention, 0, 1) -> [1, 2].
WIND_RELATIVE_RATE = 0.004     # /yr, relative, linear -- applied to every wind plant
HYDRO_RETENTION_RATE = 0.0055  # /yr, linear (0.55%/yr; the 0.79 scaling is removed)
SOLAR_RETENTION_RATE = 0.007    # /yr, compound

# Coal: literature decay rate + an ASSUMED overhaul schedule (see module
# docstring). The cycle length and recovery fraction are a modelling premise,
# not values from the cited sources -- provisional, revisable.
COAL_DECAY_RATE = 0.0025         # /yr, 0.25 pp/yr -- Kim & Moon 2012, Sagaf 2020
COAL_OVERHAUL_CYCLE_YEARS = 5    # ASSUMED
COAL_OVERHAUL_RECOVERY = 0.70    # ASSUMED -- fraction of the cycle's loss recovered

# Dead-code wind form, kept for the record only (see _wind_retention_from_cf_initial).
_WIND_CF_DECLINE_PP = 0.0015     # pp of capacity factor /yr -- NOT on the active path

# thermal-bucket fuels that carry no ageing curve -> retention 1.0
NEUTRAL_THERMAL_FUELS = frozenset({"oil/gas", "nuclear", "bioenergy"})
_MIXED_SEP = ";"

HAZARD_CSV = ccrs.OUTPUT_TABLES / "ccrs_hazard.csv"
HAZARD_COLUMNS = ("hazard_gfdl_esm4", "hazard_miroc6")

_ATTR_COLUMNS = [
    PLANT_UID, "country", "plant_name", "capacity_mw", "commissioning_year",
    "bucket", "fuel_type", "mixed_fuel_type", "fuel_types_found",
]


# --------------------------------------------------------------------------
# Retention curves (all <= 1) and the >=1 conversion
# --------------------------------------------------------------------------
def _to_multiplier(retention: float) -> float:
    """``2 - clip(retention, 0, 1)`` -> age_factor in ``[1, 2]``."""
    return 2.0 - min(max(retention, 0.0), 1.0)


def _wind_retention(age: float) -> float:
    """``1 - 0.004 * age`` -- the uniform relative rate for every wind plant."""
    return 1.0 - WIND_RELATIVE_RATE * age


def _wind_retention_from_cf_initial(age: float, cf_initial: float) -> float:
    """DEAD CODE -- not wired into ``age_factor``; kept only as an executable
    record of the initial-capacity-factor form.

    The observed wind-degradation parameter is 0.15 pp of capacity factor per
    year; turning it into a relative retention rate needs the plant's initial
    capacity factor (``retention = 1 - 0.0015 * age / CF_initial``). No GEM
    source carries a capacity factor and there is **no runtime availability
    check** -- ``age_factor`` always uses ``_wind_retention`` (fixed 0.4%/yr).
    Wire this in only when a real ``CF_initial`` source exists (Global Wind
    Atlas, manufacturer power curves). Reachability is asserted in
    ``tests/test_age_factor.py``.
    """
    return 1.0 - _WIND_CF_DECLINE_PP * age / cf_initial


def _hydro_retention(age: float) -> float:
    return 1.0 - HYDRO_RETENTION_RATE * age


def _solar_retention(age: float) -> float:
    return (1.0 - SOLAR_RETENTION_RATE) ** age


def _coal_retention(age: float) -> float:
    """Sawtooth retention: ``COAL_DECAY_RATE`` (0.25 pp/yr) decay within a
    ``COAL_OVERHAUL_CYCLE_YEARS``-year cycle, then ``COAL_OVERHAUL_RECOVERY``
    (70%) of that cycle's accumulated loss recovered at the cycle boundary
    (the rest permanent). Age-only -- the overhaul schedule is assumed, not
    read from data (module docstring)."""
    if age <= 0:
        return 1.0
    permanent_loss_per_cycle = (
        (1.0 - COAL_OVERHAUL_RECOVERY) * COAL_DECAY_RATE * COAL_OVERHAUL_CYCLE_YEARS
    )
    n_cycles = int(age // COAL_OVERHAUL_CYCLE_YEARS)
    years_into_cycle = age - n_cycles * COAL_OVERHAUL_CYCLE_YEARS
    return (
        1.0
        - n_cycles * permanent_loss_per_cycle
        - COAL_DECAY_RATE * years_into_cycle
    )


def _thermal_fuel_retention(fuel: str, age: float) -> float:
    """retention for one non-mixed thermal fuel."""
    if fuel == "coal":
        return _coal_retention(age)
    if fuel in NEUTRAL_THERMAL_FUELS:
        return 1.0
    raise ValueError(
        f"age_factor: thermal fuel_type {fuel!r} has no age curve "
        f"(known: 'coal' + {sorted(NEUTRAL_THERMAL_FUELS)})"
    )


def plant_age(commissioning_year) -> float:
    """Age at the study horizon: ``REFERENCE_YEAR - commissioning_year``.
    Missing year -> ``nan``."""
    if pd.isna(commissioning_year):
        return float("nan")
    return float(REFERENCE_YEAR) - float(commissioning_year)


def age_factor(
    plant_uid,
    fuel_type_bucket,
    age,
    fuel_type=None,
    mixed_fuel_type: bool = False,
    fuel_types_found=None,
) -> float:
    """The ``>= 1`` age multiplier for one plant.

    ``age`` NaN (missing ``commissioning_year``) -> ``NEUTRAL_AGE_FACTOR``
    (1.0). ``plant_uid`` is used only for error messages.
    """
    if pd.isna(age):
        return NEUTRAL_AGE_FACTOR
    age = float(age)
    bucket = str(fuel_type_bucket)

    if bucket == "hydro":
        return _to_multiplier(_hydro_retention(age))
    if bucket == "wind":
        return _to_multiplier(_wind_retention(age))
    if bucket == "solar":
        return _to_multiplier(_solar_retention(age))
    if bucket == "thermal":
        if bool(mixed_fuel_type):
            comps = [c.strip() for c in str(fuel_types_found).split(_MIXED_SEP) if c.strip()]
            if not comps:
                raise ValueError(
                    f"age_factor: mixed-fuel plant {plant_uid!r} has an empty "
                    f"fuel_types_found"
                )
            return float(np.mean([
                _to_multiplier(_thermal_fuel_retention(c, age)) for c in comps
            ]))
        if pd.isna(fuel_type):
            raise ValueError(
                f"age_factor: thermal plant {plant_uid!r} is not flagged "
                f"mixed_fuel_type but has no fuel_type"
            )
        return _to_multiplier(_thermal_fuel_retention(str(fuel_type), age))

    raise ValueError(
        f"age_factor: unknown fuel_type_bucket {bucket!r} (plant {plant_uid!r})"
    )


# --------------------------------------------------------------------------
# Per-plant table
# --------------------------------------------------------------------------
def load_plant_attributes() -> pd.DataFrame:
    """One row per ``plant_uid`` across the three countries, with the columns
    ``age_factor`` needs. ``plant_uid`` is globally unique."""
    df = pd.concat(
        [ccrs.load_plants(c)[_ATTR_COLUMNS] for c in COUNTRIES],
        ignore_index=True,
    )
    if not df[PLANT_UID].is_unique:
        raise ValueError("plant_uid is not unique across countries in load_plants output")
    return df


def compute_age_factors(attributes: pd.DataFrame | None = None) -> pd.DataFrame:
    """``plant_uid`` -> ``age``, ``age_factor``, and the
    missing-``commissioning_year`` flag, one row per plant."""
    df = (load_plant_attributes() if attributes is None else attributes).copy()
    df["age"] = df["commissioning_year"].map(plant_age)
    df["age_factor_neutralized_missing_year"] = df["commissioning_year"].isna()
    df["age_factor"] = [
        age_factor(
            r.plant_uid, r.bucket, r.age,
            fuel_type=r.fuel_type, mixed_fuel_type=r.mixed_fuel_type,
            fuel_types_found=r.fuel_types_found,
        )
        for r in df.itertuples(index=False)
    ]
    return df


# --------------------------------------------------------------------------
# Application to the Hazard term
# --------------------------------------------------------------------------
def apply_to_hazard(
    hazard_csv: Path = HAZARD_CSV,
    age_factors: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Multiply every Hazard column of ``hazard_csv`` by ``age_factor`` per
    ``plant_uid``. Adds ``age``, ``age_factor``, the neutralised flag, and one
    ``{col}_aged`` column per Hazard column. Never sums."""
    hz = pd.read_csv(hazard_csv)
    af = age_factors if age_factors is not None else compute_age_factors()
    af_small = af[[
        PLANT_UID, "age", "age_factor", "age_factor_neutralized_missing_year",
    ]]

    missing = set(hz[PLANT_UID]) - set(af_small[PLANT_UID])
    if missing:
        raise ValueError(
            f"{len(missing)} plant_uid in {hazard_csv.name} have no age_factor "
            f"-- the CSV is stale relative to load_plants. Regenerate it with "
            f"`python -m src.index.ccrs_calculator`."
        )

    out = hz.merge(af_small, on=PLANT_UID, how="left", validate="many_to_one")
    for col in HAZARD_COLUMNS:
        if col in out.columns:
            out[f"{col}_aged"] = out[col] * out["age_factor"]
    return out


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def _curve_label(row) -> str:
    if row.bucket == "thermal":
        if row.mixed_fuel_type:
            return "thermal:mixed"
        return f"thermal:{row.fuel_type}"
    return row.bucket


def build_summary(age_factors: pd.DataFrame) -> str:
    df = age_factors.copy()
    df["curve"] = [_curve_label(r) for r in df.itertuples(index=False)]

    lines: list[str] = ["# age_factor -- summary\n"]
    lines.append(
        f"`age_factor = 2 - clip(retention(age), 0, 1)` in [1, 2], age = "
        f"`{REFERENCE_YEAR} - commissioning_year` (config.YEAR_TARGET). "
        f"Range on this data: {df['age_factor'].min():.4f} .. "
        f"{df['age_factor'].max():.4f}. Every value >= 1; a plant with no "
        f"commissioning_year is neutral at 1.0.\n"
    )

    lines.append("## age_factor by country x curve (min / mean / max, n)\n")
    g = (df.groupby(["country", "curve"])["age_factor"]
         .agg(["min", "mean", "max", "count"]).round(4).reset_index())
    lines.append(g.to_string(index=False) + "\n")

    lines.append("## Wind / coal / hydro / solar -- age_factor per country\n")
    lines.append(
        "Includes plants neutralised for a missing commissioning_year (their "
        "age_factor is exactly 1.0), so a `min` of 1.0 in a curve with a "
        "positive rate means that curve has some year-less plants -- see the "
        "count below.\n"
    )
    focus = {
        "wind": df["bucket"] == "wind",
        "coal": (df["bucket"] == "thermal") & (df["fuel_type"] == "coal"),
        "hydro": df["bucket"] == "hydro",
        "solar": df["bucket"] == "solar",
    }
    rows = []
    for name, mask in focus.items():
        for country in COUNTRIES:
            s = df.loc[mask & (df["country"] == country), "age_factor"]
            if len(s):
                rows.append([name, country, len(s), round(s.min(), 4),
                             round(s.mean(), 4), round(s.max(), 4)])
            else:
                rows.append([name, country, 0, "-", "-", "-"])
    lines.append(pd.DataFrame(
        rows, columns=["curve", "country", "n", "min", "mean", "max"],
    ).to_string(index=False) + "\n")

    lines.append("## Plants neutralised for missing commissioning_year\n")
    miss = (df[df["age_factor_neutralized_missing_year"]]
            .groupby("country").size().reindex(COUNTRIES, fill_value=0))
    for country in COUNTRIES:
        total = int((df["country"] == country).sum())
        n = int(miss[country])
        lines.append(f"- {country}: {n} / {total} plants "
                     f"({n / total * 100:.1f}%) -> age_factor = 1.0\n")
    lines.append(f"- total: {int(miss.sum())} plants\n")
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

    af = compute_age_factors()
    aged = apply_to_hazard(args.hazard_csv, age_factors=af)
    report = build_summary(af)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "ccrs_age_factors.csv").write_text(af.to_csv(index=False), encoding="utf-8")
    aged.to_csv(args.out_dir / "ccrs_hazard_aged.csv", index=False)
    (args.out_dir / "age_factor_report.md").write_text(report, encoding="utf-8")

    logger.info("age_factor: %d plants, range %.4f..%.4f, %d neutralised (missing year)",
                len(af), af["age_factor"].min(), af["age_factor"].max(),
                int(af["age_factor_neutralized_missing_year"].sum()))
    logger.info("wrote ccrs_age_factors.csv, ccrs_hazard_aged.csv, age_factor_report.md to %s",
                args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
