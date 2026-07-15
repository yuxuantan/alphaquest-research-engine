# One Run Per Attempt

Date: 2026-07-15

## Decision

Every governance-v2 attempt may have at most one immutable run. Original variants declare `attempt_id: original`, `attempt_kind: original`, and `attempt_provenance: authored`. Any replication, data refresh, methodology rerun, or authorized rescue uses a new attempt ID and records its parent attempt.

The staged runner refuses to reuse a completed run directory or an attempt ID that already has evidence. The registry also has a unique `(campaign_id, variant_id, attempt_id)` run index, so imported or externally generated duplicate evidence fails closed.

Mechanics validation uses a separate hash-derived `generated_validation` attempt. It cannot consume the authored performance attempt.

## Historical migration

Historical run directories and verdicts remain unchanged. During registry construction, every historical run without explicit authored attempt identity receives a deterministic unique attempt ID derived from its run UID and provenance `inferred_legacy`. Existing supplemental authored definitions remain separately visible as `legacy_authored_definition` records.

Historical summaries without a terminal pass/fail result retain `NEEDS MANUAL REVIEW`; their derived attempt lineage has the same status. Registry status reports attempt provenance, ambiguous-attempt count, and one-run-per-attempt violations.

## Consequences

- An attempt can have zero runs while pending and one run after execution.
- Reruns are new attempts, not additional runs attached to an old attempt.
- Existing evidence and historical verdicts are not rewritten.
- Registry schema version 2 is required for the normalized attempt lineage.
