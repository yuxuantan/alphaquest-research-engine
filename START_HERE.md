# Institutional Research Workspace

Use the registry and generated views for routine navigation. Do not browse the generated run store to discover research state.

Open `alphaquest-research.code-workspace` for the curated VS Code surface. It exposes active definitions, the ledger-aware decision workbench, code, tests, configuration, and documentation while excluding archived definitions, immutable evidence, market data, and generated indexes from routine search and file watching.

## Daily Entry Points

- `make help`: list supported repository commands.
- `make tutorial`: execute the isolated synthetic onboarding workflow.
- `make research-workspace`: rebuild the registry, exports, run store, and generated views.
- `alphaquest research status`: show lifecycle and run-verdict counts.
- `alphaquest research search --verdict NEEDS_MANUAL_REVIEW`: list campaigns containing incomplete runs.
- `alphaquest campaign show <campaign_id>`: show definitions and recent runs.
- `alphaquest campaign show <campaign_id> --explain --run <run_uid>`: trace hypothesis, mechanics, data, validation, stages, artifacts, and verdict.
- `views/`: disposable, human-facing working sets.
- `docs/README.md`: role-based documentation index.

## Ownership Boundaries

| Path | Role | Edit policy |
| --- | --- | --- |
| `research/campaigns/active/` | Authored hypotheses currently under research | Human-authored source of truth |
| `research/campaigns/archive/` | Closed authored hypotheses and attempts | Read-only historical source |
| `src/` | Deterministic engine and research controls | Reviewed code |
| `tests/` | Engine, methodology, and regression controls | Reviewed code |
| `data/` | Governed market inputs and caches | Never mix with reports |
| `research/evidence/runs/` | Generated execution evidence | Immutable after run completion |
| `run-store/` | Opaque, date-partitioned run-ID view | Generated compatibility index |
| `catalogs/` | Rebuildable registry and exports | Generated from source and evidence |
| `views/` | Curated navigation | Generated; never authoritative |
| `views/workbench/` | Ledger-aware human action queue | Generated; never authoritative |
| `research_artifacts/` | Durable audits and research decisions | Append-only evidence |

## Verdict Semantics

`candidate` means a run reached a terminal pass in the recorded workflow. It never means ready to trade. Manual due diligence, independent replication, and paper/live incubation remain mandatory.

## New Contributors

Read [CONTRIBUTING.md](CONTRIBUTING.md), [ARCHITECTURE.md](ARCHITECTURE.md), and the [repository tour](docs/getting-started/repository-tour.md) before changing engine or research contracts.

## One Research Workflow

```text
hypothesis -> duplicate-edge review -> exactly five material variants
-> config/mechanics lock -> data-lineage preflight
-> small deterministic mechanics-validation slice
-> lane-correct automated evidence checks
-> hash-bound manual approved_for_testing decision
-> staged performance tests -> frozen final holdout
-> ledger update -> PASS / FAIL / NEEDS MANUAL REVIEW
```

Performance testing is blocked when validation evidence is absent, stale, hash-mismatched, rejected, or from the wrong bar/event lane. See the [worked trace](docs/getting-started/trace-research.md).
