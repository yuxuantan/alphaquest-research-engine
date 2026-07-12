# Institutional Research Workspace

Use the registry and generated views for routine navigation. Do not browse the generated run store to discover research state.

## Daily Entry Points

- `make research-workspace`: rebuild the registry, CSV exports, one cataloged definition index per campaign, and generated views.
- `make research-status`: show campaign lifecycle and run-verdict counts.
- `PYTHONPATH=src python3 tools/research_status.py --state review_queue`: list campaigns requiring review.
- `PYTHONPATH=src python3 tools/research_status.py --campaign <campaign_id>`: show one campaign and its latest runs.
- `views/`: disposable, human-facing working sets.
- `catalogs/exports/`: portable CSV exports of the SQLite registry.

## Ownership Boundaries

| Path | Role | Edit policy |
| --- | --- | --- |
| `campaigns/` | Authored hypotheses, variants, and approved attempts | Human-authored source of truth |
| `src/` | Deterministic engine and research controls | Reviewed code |
| `tests/` | Engine, methodology, and regression controls | Reviewed code |
| `data/` | Governed market inputs and caches | Never mix with reports |
| `backtest-campaigns/` | Generated execution evidence | Immutable after run completion |
| `run-store/` | Opaque, date-partitioned run-ID view | Generated compatibility index |
| `catalogs/` | Rebuildable registry and exports | Generated from source and evidence |
| `views/` | Curated navigation | Generated; never authoritative |
| `research_artifacts/` | Durable audits and research decisions | Append-only evidence |

## Verdict Semantics

`candidate` means a run reached a terminal pass in the recorded workflow. It never means ready to trade. Manual due diligence, independent replication, and paper/live incubation remain mandatory.
