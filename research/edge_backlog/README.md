# Canonical Edge Backlog

This directory is the version-controlled source of truth for pre-hypothesis
research discovery records. Canonical JSON is stored under:

- `observations/<observation_id>/revisions/`
- `entries/<entry_id>/revisions/`
- `entries/<entry_id>/decisions/`
- `entries/<entry_id>/links/`

Files are append-only and hash-bound. Every record carries a globally unique,
gap-free `append_sequence` allocated from validated records under the existing
exclusive lock; it is the authoritative equal-timestamp and historical-prefix
order. Do not hand-edit, replace, or delete these files.
Use `alphaquest edge-backlog` so closed schemas, actor classes, revision chains,
references, duplicate snapshots, lifecycle intervals, and causal chronology are
validated inside the cross-process backlog transaction before an exclusive
write. The lock itself lives in derived runtime storage, not in this canonical
directory.

Full validation also requires every record file to be the exact canonical JSON
bytes for its validated model followed by one newline. Duplicate-review
candidates are regenerated as the complete ranked universe at the reviewing
decision's append sequence. Historical input is re-extracted from the exact
immutable repository commit bound by the decision, and each historical
candidate embeds its strict derived record, so later index rebuilds do not
erase the review binding. Review reads the immutable Git tree directly and
ignores the optional derived cache. Explicit cache validation and replacement
still require every current or prior derived row to match an approved source,
actual file-byte hash, source kind/row, and the shared source-specific
extraction.

In Git repositories every observation revision, entry revision, decision, and
link remains provisional record material until its exact canonical path and
blob are committed. Full validation requires each path's unique first reachable
appearance to contain its expected canonical `100644` blob and every reachable
descendant to retain the same path, mode, type, and bytes. HEAD, the Git index,
and the working tree must retain every anchored record, so whole-object or
collection deletion cannot hide history or permit sequence reuse. Delete/re-add
history cannot establish a new anchor. Decisions additionally require
source-commit ancestry and an equal historical universe in the introduction
parent. Commit timestamps grant no ordering authority. A wholesale rewrite
before the first Git anchor cannot be detected cryptographically.

Observation statements and conflicts are unrestricted, source-bound memory and
grant no P1 or strategy authority. Canonical entry identity is instead limited
to the immutable taxonomy under `contracts/`: a classified entry contains only
closed economic codes, while a `NEEDS_CLASSIFICATION` entry contains no concept
payload or fingerprint. Entry IDs are opaque and engine-generated. The initial
taxonomy-local instruments are only `ES` and `NQ`; unsupported instruments
remain observation memory pending an owner-reviewed additive extension.

Taxonomy labels and recall aliases are derived matcher material. Fingerprints
contain stable taxonomy ID and selected codes, not taxonomy version, taxonomy
hash, labels, or aliases. Every entry revision still binds the exact taxonomy
ID/version/SHA used to validate it.

Production taxonomy authority is pinned to
`research/edge_backlog/contracts`. The directory and each version file are read
once per backlog transaction through repository-rooted, no-follow descriptors;
symlinks, special files, executable files, unexpected names, and concurrent
mixed snapshots fail closed. Published taxonomy files have one byte
representation: compact UTF-8 JSON,
sorted object keys, declared array order, and exactly one final LF. Taxonomy
references hash that complete file byte sequence; fingerprint hashes remain
newline-free. Additive versions cannot introduce invariants triggered by old
codes or remove any prohibited category.

The backlog is not a strategy list and cannot create a scientific verdict,
admit a hypothesis, create an edge family or campaign, promote a candidate, or
authorize deployment. See [the Edge Backlog guide](../../docs/research/edge-backlog.md).
