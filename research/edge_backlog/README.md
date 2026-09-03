# Canonical Edge Backlog

This directory is the version-controlled source of truth for pre-hypothesis
research discovery records. Canonical JSON is stored under:

- `observations/<observation_id>/revisions/`
- `entries/<entry_id>/revisions/`
- `entries/<entry_id>/decisions/`
- `entries/<entry_id>/links/`

Files are append-only and hash-bound. Do not hand-edit, replace, or delete them.
Use `alphaquest edge-backlog` so closed schemas, actor classes, revision chains,
references, duplicate snapshots, lifecycle intervals, and causal chronology are
validated inside the cross-process backlog transaction before an exclusive
write. The lock itself lives in derived runtime storage, not in this canonical
directory.

The backlog is not a strategy list and cannot create a scientific verdict,
admit a hypothesis, create an edge family or campaign, promote a candidate, or
authorize deployment. See [the Edge Backlog guide](../../docs/research/edge-backlog.md).
