# Campaign Authoring

One campaign represents one economic edge. A normal campaign declares exactly five distinct mechanical variants before PnL is inspected.

Create a scaffold:

```bash
alphaquest campaign new my_campaign --symbol ES --edge-family my_edge
```

Then complete:

- source title, authors, year, and link or DOI
- hypothesis and expected market mechanism
- data availability and timestamp semantics
- lookahead risks
- variant-specific entry, stop, target, timeframe, and session rationale
- parameter limits and total combinations
- commissions, slippage, tick size, point value, and prop rules
- the structured `economic_edge_fingerprint`
- a ledger/campaign-backed `duplicate_edge_review` with a substantive economic distinction
- `variant_distinctions` for exactly five initial variants
- the bar or event-replay `research_metadata.validation_gate` paths
- an explicit `attempt_id`, `attempt_kind`, and `attempt_provenance: authored` for every governance-v2 config

Validate before execution:

```bash
alphaquest campaign validate my_campaign
```

Governance contract v2 rejects any initial variant count other than five. It also rejects missing duplicate-edge review, identical economic fingerprints, duplicate mechanical descriptions, or more than one rescue for a failed variant. Parameter renames, session-window tweaks, and sibling configs are not materially different edges or variants.

For bar strategies, `alphaquest campaign validate-mechanics <campaign_id> --variant <variant_id>` runs the declared 0-to-14-day deterministic slice and exports evidence into the dedicated `backtest-campaigns/.../mechanics_validation/` run. Event-replay strategies must use their canonical event runner so `event_transitions.parquet` is exported; the generic bar command fails closed for that lane. Human approval lives under `research_artifacts/validation_approvals/`, not inside authored definitions.

`alphaquest campaign run` is a performance command. For a governance-v2 definition it will not start until the declared deterministic validation evidence and `approval.json` reconcile to the authored-config hash, validation-slice input-data hash, validation schema, and declared validation lane. The next variant is also blocked until earlier variants in `campaign.yaml` have completed mechanics approval.

Do not silently change mechanics after OOS. An authorized rescue must preserve the edge, be declared as an attempt, and record its parent variant and rationale.

Each governance-v2 attempt may produce at most one staged run. A replication, data refresh, methodology rerun, or rescue must use a new `attempt_id`; non-original attempts also declare `parent_attempt_id`. Completed run directories are immutable and cannot be reused by a later attempt.
