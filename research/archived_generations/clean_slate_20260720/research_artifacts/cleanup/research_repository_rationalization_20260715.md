# Research Repository Rationalization

Created: `2026-07-15T06:31:31.631785+00:00`

## Current Truth

- Authored campaigns: `346`
- Registered variants / attempts / runs: `1753` / `1118` / `2535`
- Research ledger rows: `3450`
- Incomplete or interrupted runs: `7`
- Orphaned run summaries: `0`
- Pre-existing uncommitted deletions: `0`
- Registry stale: `False`

The live checkout was inspected directly. Generated snapshots are treated as provenance only, never proof that a run was rerun.

## Artifact Classes And Disk Use

| Class | Objects | MiB |
| --- | ---: | ---: |
| authored research definition | 3731 | 14.7 |
| invariant variant mechanics | 4175 | 0.5 |
| rescue attempt | 3494 | 8.5 |
| generated authoritative evidence | 33286 | 23805.5 |
| compact terminal summary | 8225 | 190.7 |
| reproducible bulk output | 0 | 0.0 |
| generated navigation/projection | 724 | 34.4 |
| cache | 475 | 6900.0 |
| interrupted/incomplete run | 0 | 0.0 |
| superseded duplicate | 0 | 0.0 |
| orphaned or unreferenced object | 0 | 0.0 |
| unknown/manual-review required | 0 | 0.0 |

## Data Lineage And Validation Coverage

- Lineage verdicts: `{"FAIL": 1, "NEEDS MANUAL REVIEW": 2534}`
- Validation coverage: `{"automated_only_manual_missing": 5, "missing": 2530}`
- Runs with incomplete lineage: `2535`

Missing historical evidence is classified as NEEDS MANUAL REVIEW. It is not backfilled and is not treated as proof that old data or mechanics were correct.

## Duplicate, Incomplete, And Orphan Review

- Exact superseded error-run candidates: `0`
- Missing registered run directories: `0`
- Generated campaigns without authored campaign: `0`

## Keep / Archive / Delete / Regenerate Matrix

| Artifact class | Decision | Reason |
| --- | --- | --- |
| authored definitions and invariant mechanics | KEEP | irreplaceable source and mechanics lock |
| source/effective configs, manifests, hashes | KEEP | run provenance and reconciliation |
| terminal summaries, audits, fixed/OOS logs, Monte Carlo summaries | KEEP | compact authoritative evidence |
| interrupted or unknown runs | KEEP + MANUAL REVIEW | evidence until classified |
| views, registry, exports | REGENERATE | rebuildable navigation only |
| superseded but provenance-bearing material | ARCHIVE | preserve lineage while removing from active navigation |
| reproducible bulk payloads and caches | DELETE VIA MANIFEST | reconstructable from retained evidence |
| orphaned, referenced, or unknown objects | MANUAL REVIEW | fail closed; no deletion authority |

## Safe Cleanup Dry Run

- Candidate files/objects: `800`
- Candidate superseded runs: `0`
- Reclaimable MiB: `11.0`

The cleanup manifest records every deletion candidate before apply. Unknown, referenced, or provenance-bearing evidence is excluded.
- Applied cleanup status: `APPLIED`
- Applied files removed: `901`
- Applied reclaimed MiB: `12.1`

## Repository Verdict

At least one run has mismatched or missing declared source evidence.

**FAIL**
