"""
Runs all 16 GEAR_v3_RESULTS_DRAFT.md item modules in order and writes
``data/outputs/results_draft/MANIFEST.md``.

    python -m src.reporting.results_draft.run_all [--items 1 2 3 ...]

Every item module is independent (own inputs, own output subfolder) --
``--items`` re-runs a subset without regenerating the rest. Requires
``data/outputs/tables/psae.csv`` to exist (``python -m src.index.psae``,
not persisted by ``src/main.py``'s own pipeline run) before items
2/3/4/12/13 read PSAE data indirectly via risk_bands (items that read
``psae.csv`` directly fail loudly with an actionable message otherwise, see
``common.load_psae``).
"""

from __future__ import annotations

import argparse
import logging

from src.reporting.results_draft import (
    common,
    item01_correlation_gate as i01,
    item02_riskband_distribution as i02,
    item03_riskband_asset_map as i03,
    item04_extreme_wind_invariant as i04,
    item05_risk_intra_hazard_map as i05,
    item06_risk_topn_table as i06,
    item07_sobol_sensitivity as i07,
    item08_hazard_removal_oat as i08,
    item09_correlation_gate_sweep as i09,
    item10_general_mc_convergence as i10,
    item11_general_mc_bars as i11,
    item12_psae_distribution as i12,
    item13_psae_screening_map as i13,
    item14_validator_overlay as i14,
    item15_normalization_provenance as i15,
    item16_threshold_tier_provenance as i16,
)

logger = logging.getLogger(__name__)

ITEMS = {
    1: i01, 2: i02, 3: i03, 4: i04, 5: i05, 6: i06, 7: i07, 8: i08,
    9: i09, 10: i10, 11: i11, 12: i12, 13: i13, 14: i14, 15: i15, 16: i16,
}


def run(selected: list[int] | None = None) -> list[common.ManifestEntry]:
    selected = selected or sorted(ITEMS)
    entries: list[common.ManifestEntry] = []
    for n in selected:
        mod = ITEMS[n]
        logger.info("item %02d: %s ...", n, mod.SLUG)
        entries.extend(mod.run())
        logger.info("item %02d: %s -- done", n, mod.SLUG)
    return entries


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=int, nargs="+", default=None, choices=sorted(ITEMS),
                         help="run only these item numbers (default: all 16)")
    args = parser.parse_args()

    entries = run(args.items)
    manifest_path = common.write_manifest(entries)
    logger.info("wrote %s (%d entries)", manifest_path, len(entries))
    n_generated = sum(1 for e in entries if e.status.startswith("generated"))
    print(f"\n{n_generated}/{len(entries)} items generated. Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
