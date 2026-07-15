# Validation And Campaign-Governance Promotion Gate

Date: 2026-07-15

## Decision

New campaign scaffolds use governance contract v2. They require exactly five initial variants, a structured economic-edge fingerprint, a ledger-backed duplicate-edge review, material variant distinctions, at most one explicit rescue per failed variant, and lane-correct mechanics-validation approval before staged performance testing.

The approval is a read-only promotion contract over exported evidence. It binds the reviewer decision to the authored-config hash, input-data hash, validation schema, lane, and deterministic risk-based trade sample. Event-replay strategies require canonical event transitions; bar windows cannot satisfy that lane.

## Consequences

- Historical definitions and verdicts are not rewritten. Missing modern evidence is reported as `NEEDS MANUAL REVIEW`.
- Performance runners fail before creating new results when an opted-in gate is missing, stale, rejected, or mismatched.
- Earlier variants must complete mechanics approval before a later variant can run.
- Validation export and review cannot change fills or PnL because the gate only reads completed artifacts.
- Generated run cards and registry rows remain navigation; manifests, snapshots, hashes, decisions, and terminal summaries remain authoritative.
