# Campaign Authoring

This is the expert YAML interface. New researchers should use [Research Studio](../getting-started/research-studio.md), which compiles the same authoritative contracts after strict validation. The legacy `alphaquest campaign new` TODO scaffold is retained for engine developers and compatibility; it is not the novice workflow.

One campaign represents one economic edge. A new campaign declares one mechanical variant before PnL is inspected. It may add a materially distinct expression of the same edge only after the immediately prior variant has passed manual mechanics review and received a terminal `FAIL`. The campaign maximum is five variants.

Engine developers may create a legacy scaffold:

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
- `variant_distinctions` for every currently declared variant
- `sequential_variant_history` for each variant after `v01`, binding it to the prior reviewed `FAIL`
- the bar or event-replay `research_metadata.validation_gate` paths
- an explicit `attempt_id`, `attempt_kind`, and `attempt_provenance: authored` for every governed config

Validate before execution:

```bash
alphaquest campaign validate my_campaign
```

Governance contract v3 requires the sequential protocol: one initial variant, one failure-bound lineage record for every later variant, and no more than five total. Contract v2 remains readable only for already-authored five-variant campaigns. Both reject missing duplicate-edge review, identical economic fingerprints, or duplicate mechanical descriptions. Parameter renames, session-window tweaks, and sibling configs are not materially different edges or variants.

For bar strategies, `alphaquest campaign validate-mechanics <campaign_id> --variant <variant_id>` runs the declared deterministic slice and exports evidence into the dedicated `research/evidence/runs/.../mechanics_validation/` run. Event-replay strategies must use their canonical event runner so `event_transitions.parquet` is exported; the generic bar command fails closed for that lane. Human approval lives under `research_artifacts/validation_approvals/`, not inside authored definitions.

`alphaquest campaign run` is a performance command. For a governed definition it will not start until the declared deterministic validation evidence and `approval.json` reconcile to the authored-config hash, validation-slice input-data hash, validation schema, declared validation lane, fixed sample policy, and declared-default parameter mode. A later variant is blocked until the immediately prior variant has both that approval and a complete terminal `FAIL` bundle.

Do not silently change mechanics after OOS. An authorized rescue must preserve the edge, be declared as an attempt, and record its parent variant and rationale.

Each governed attempt may produce at most one staged run. A replication, data refresh, methodology rerun, or rescue must use a new `attempt_id`; non-original attempts also declare `parent_attempt_id`. Completed run directories are immutable and cannot be reused by a later attempt.
