# Validation Stages

| Stage | Purpose |
| --- | --- |
| Limited core grid | Reject unprofitable, sparse, unstable, or rule-violating combinations quickly |
| Limited monkey | Require separation from randomized entries |
| Walk-forward analysis | Select parameters only on training windows and stitch unseen OOS trades |
| WFA OOS monkey | Stress the stitched OOS path against random entries |
| WFA OOS Monte Carlo | Stress coherent session paths over the frozen horizon and enforce prop lifecycle rules |
| Secondary historical OOS holdout | Test a later untouched historical interval with frozen mechanics |
| Acceptance OOS | Open the locked final holdout only after the strategy is frozen |

Each criterion is repository-owned and classified as either `scientific_validity` or `generic_objective`. Missing data, malformed timestamps, ambiguous fills, incomplete summaries, leakage, insufficient unseen samples, or stale evidence fail scientific validity closed and stop later stages. A generic risk/return objective miss is recorded as generic `FAIL`, but later unseen-evidence stages continue so an exact destination profile can still be assessed.

The staged output therefore has two verdicts. Promotion requires scientific-validity `PASS` plus either generic-objective `PASS` or a separate `PASS` from one hash-bound challenge, funded, or live-account profile. Destination-specific rules, including Apex thresholds, are not generic staged gates.

Before any PnL-bearing stage, Studio freezes a campaign objective contract:
deadline, return/MAR/drawdown limits, minimum WFA windows and trades, Monte
Carlo probability limits, abandonment rules, and true forward-incubation
requirements. Campaign goals may tighten repository policy but cannot weaken
it. The secondary historical holdout is not incubation. Chronological
paper/live observations are append-only and only become eligible for a later
human review; they never auto-approve deployment.

## Mechanics Promotion Gate

Before the limited core grid, a new governance-v2 variant must point to a small deterministic validation evidence directory and a manual `approval.json`.

The bar-lane command is:

```bash
alphaquest campaign validate-mechanics <campaign_id> --variant <variant_id>
```

Generated evidence stays under `research/evidence/runs/`. The durable human decision stays under `research_artifacts/validation_approvals/`. Neither is written into an authored campaign definition.

- `lane: bar` requires non-empty `bar_windows.parquet`.
- `lane: event_replay` requires non-empty `event_transitions.parquet`; bar evidence is never a substitute.
- `validation_checks.parquet` must contain no unresolved errors.
- Automated coverage must include source/config/data identity, costs and forced flatten, trade-log reconciliation, timestamps and entry ordering, trigger/filter conditions, stop/target placement, exit/first-touch logic, and data quality.
- `metadata.json` must match the authored config hash, input-data hash, validation lane, and schema version.
- `approval.json` must record reviewer, timezone-aware timestamp, status `approved_for_testing`, notes, sampled trade IDs, hashes, schema, sampling-policy identity, and all universal sample categories.

The governed sampler selects five deterministic hash-ranked trades, then adds the minimum representatives needed to cover observed directions, canonical entry-order types, exit lifecycles, order amendments, forced flattens, warning codes, and resolved ambiguities. A legacy lane that cannot distinguish its entry-order type is covered explicitly as `unspecified`. Unresolved ambiguities, error-severity automated checks, and missing direction or exit-reason evidence block approval; warning-severity exit-path mismatches add one representative instead. Strategy-specific signal rules are checked across the full evidence set by automated validation; the human sampler does not contain per-strategy branches. A category with no eligible trade remains explicit in the decision rather than silently disappearing.

The promotion gate reads validation artifacts only. It does not call strategy modules, calculate PnL, or modify fills.
