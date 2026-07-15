# Validation Stages

| Stage | Purpose |
| --- | --- |
| Limited core grid | Reject unprofitable, sparse, unstable, or rule-violating combinations quickly |
| Limited monkey | Require separation from randomized entries |
| Walk-forward analysis | Select parameters only on training windows and stitch unseen OOS trades |
| WFA OOS monkey | Stress the stitched OOS path against random entries |
| WFA OOS Monte Carlo | Estimate drawdown, concentration, and ruin distributions |
| Simulated incubation | Test a later untouched interval with frozen mechanics |
| Acceptance OOS | Open the locked final holdout only after the strategy is frozen |

Every stage is fail-closed. Missing data, malformed timestamps, ambiguous fills, incomplete summaries, or stale evidence produce failure or manual review rather than promotion.

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
- `approval.json` must record reviewer, timezone-aware timestamp, status `approved_for_testing`, notes, sampled trade IDs, hashes, schema, and all risk-based sample categories.

The mandatory categories are first and last trades, deterministic random trades, best and worst trades, forced flattens, same-bar ambiguity, warnings, and strategy-specific edge cases. A category with no eligible trade remains explicit in the decision rather than silently disappearing.

The promotion gate reads validation artifacts only. It does not call strategy modules, calculate PnL, or modify fills.
