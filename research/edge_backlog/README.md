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

Published taxonomy files have one byte representation: compact UTF-8 JSON,
sorted object keys, declared array order, and exactly one final LF. Taxonomy
references hash that complete file byte sequence; fingerprint hashes remain
newline-free. Additive versions cannot introduce invariants triggered by old
codes or remove any prohibited category.

The backlog is not a strategy list and cannot create a scientific verdict,
admit a hypothesis, create an edge family or campaign, promote a candidate, or
authorize deployment. See [the Edge Backlog guide](../../docs/research/edge-backlog.md).
