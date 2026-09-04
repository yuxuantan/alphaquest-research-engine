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

Full validation also requires every record file to be the exact canonical JSON
bytes for its validated model followed by one newline. Duplicate-review
candidates are validated against exact historical entry, decision-chain, and
link-chain prefixes; historical-index candidates embed their complete strict
derived record so later index rebuilds do not erase the review binding.

Economic observation and entry prose is intentionally narrow: every token must
belong to the positively admitted, versioned P2 economic vocabulary. Arbitrary
free text is rejected because it could encode strategy mechanics through
paraphrase; expanding the vocabulary requires a reviewed contract change.

The backlog is not a strategy list and cannot create a scientific verdict,
admit a hypothesis, create an edge family or campaign, promote a candidate, or
authorize deployment. See [the Edge Backlog guide](../../docs/research/edge-backlog.md).
