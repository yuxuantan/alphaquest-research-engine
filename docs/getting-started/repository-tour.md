# Repository Tour

The filesystem is storage, not the primary research interface. Begin with `views/README.md` or `alphaquest research status`.

## Source Of Truth

- `research/campaigns/active/`: authored hypotheses currently under research.
- `research/campaigns/archive/`: closed hypotheses, configs, rationale, and attempts.
- `src/alphaquest/`: reusable engine, validation, data, and research code.
- `tests/`: executable controls and regressions.
- `config/`: repository-level research policy settings.

## Generated Or Durable Evidence

- `research/evidence/runs/`: generated run evidence; do not hand-edit.
- `run-store/`: opaque run-UID compatibility view.
- `catalogs/`: rebuildable registry and exports.
- `views/`: rebuildable navigation.
- `research_artifacts/`: durable audits and decisions.

## Separate Applications

- `apps/validation_dashboard.py`: visual mechanics-review dashboard.
- `execution_system/`: execution bridge with independent commands and tests. Read its local README before changing it.
