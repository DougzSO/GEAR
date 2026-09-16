"""
GEAR_v3_RESULTS_DRAFT.md figure/table generation -- one module per numbered
placeholder in ``docs/rework/GEAR_v3_RESULTS_DRAFT.md`` (16 items total).

Folder-structure decision (author-approved, 2026-09-15): an additive tree at
``src.config.OUTPUT_RESULTS_DRAFT`` (``data/outputs/results_draft/``),
separate from ``OUTPUT_TABLES``/``OUTPUT_MAPS`` -- those paths are read by
``src/main.py`` and every existing ``src/visualization/`` module; this
package never writes there, so the production pipeline's own outputs are
never touched by a run of this package. See ``docs/ARCHITECTURE.md``,
"Results-draft asset tree" for the approved layout and
``docs/_audit/2026-09-15_output_folder_audit_prestep.md`` for the pre-existing
``data/outputs/`` inventory this package's run superseded (old-file removal
is a separate, explicit step -- this package only ever writes new files).

Every item module exposes a single ``run() -> list[common.ManifestEntry]``
that reads real, already-computed production tables from ``data/outputs/tables/``
(or recomputes them from the tracked source module when no CSV is persisted --
named explicitly per item, never silently approximated) and writes its output
under ``OUTPUT_RESULTS_DRAFT / f"{NN}_{slug}"``. ``run_all.py`` calls every
item in order and assembles ``MANIFEST.md``.
"""
