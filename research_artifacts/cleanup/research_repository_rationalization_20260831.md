# Research Repository Rationalization

Created: `2026-08-31T02:59:06.625841+00:00`

## Current Truth

- Authored campaigns: `1`
- Registered variants / attempts / runs: `4` / `272` / `102`
- Research ledger rows: `211`
- Incomplete or interrupted runs: `100`
- Orphaned run summaries: `9`
- Pre-existing uncommitted deletions: `1`
- Registry stale: `False`

The live checkout was inspected directly. Generated snapshots are treated as provenance only, never proof that a run was rerun.

## Artifact Classes And Disk Use

| Class | Objects | MiB |
| --- | ---: | ---: |
| authored research definition | 402 | 4.4 |
| invariant variant mechanics | 1 | 0.0 |
| rescue attempt | 0 | 0.0 |
| generated authoritative evidence | 5840 | 23509.7 |
| compact terminal summary | 112 | 1.3 |
| reproducible bulk output | 90 | 1.3 |
| generated navigation/projection | 58 | 2.1 |
| cache | 6833 | 6902.3 |
| interrupted/incomplete run | 0 | 0.0 |
| superseded duplicate | 0 | 0.0 |
| orphaned or unreferenced object | 0 | 0.0 |
| unknown/manual-review required | 51087 | 767.0 |

## Data Lineage And Validation Coverage

- Lineage verdicts: `{"NEEDS MANUAL REVIEW": 102}`
- Validation coverage: `{"approved": 8, "automated_only_manual_missing": 29, "missing": 65}`
- Runs with incomplete lineage: `102`

Missing historical evidence is classified as NEEDS MANUAL REVIEW. It is not backfilled and is not treated as proof that old data or mechanics were correct.

## Duplicate, Incomplete, And Orphan Review

- Exact superseded error-run candidates: `0`
- Missing registered run directories: `9`
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

- Candidate files/objects: `7433`
- Candidate superseded runs: `0`
- Reclaimable MiB: `21.6`

The cleanup manifest records every deletion candidate before apply. Unknown, referenced, or provenance-bearing evidence is excluded.
- Applied cleanup status: `not applied`
- Applied files removed: `0`
- Applied reclaimed MiB: `0.0`

## Repository Verdict

Historical lineage and manual validation coverage are incomplete; absence is not treated as proof of correctness.

**NEEDS MANUAL REVIEW**
