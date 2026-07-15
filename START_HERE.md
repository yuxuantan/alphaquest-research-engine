# Institutional Research Workspace

Use the registry and generated views for routine navigation. Do not browse the generated run store to discover research state.

## Daily Entry Points

- `make help`: list supported repository commands.
- `make tutorial`: execute the isolated synthetic onboarding workflow.
- `make research-workspace`: rebuild the registry, exports, run store, and generated views.
- `alphaquest research status`: show lifecycle and run-verdict counts.
- `alphaquest research search --verdict NEEDS_MANUAL_REVIEW`: list campaigns containing incomplete runs.
- `alphaquest campaign show <campaign_id>`: show definitions and recent runs.
- `views/`: disposable, human-facing working sets.
- `docs/README.md`: role-based documentation index.

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

## New Contributors

Read [CONTRIBUTING.md](CONTRIBUTING.md), [ARCHITECTURE.md](ARCHITECTURE.md), and the [repository tour](docs/getting-started/repository-tour.md) before changing engine or research contracts.
