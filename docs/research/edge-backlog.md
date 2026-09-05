# Central Edge Backlog

The Central Edge Backlog is AlphaQuest's durable discovery memory before a
potential economic edge becomes a governed hypothesis or campaign. It conforms
to the [canonical research operating model](research-operating-model.md) and
does not add a P1 scientific object.

## Boundary

The governed sequence remains:

```text
source or market event
  -> OBSERVATION
  -> tentative economic-edge backlog entry
  -> HYPOTHESIS proposal and review
  -> admitted HYPOTHESIS
  -> EDGE_FAMILY and CAMPAIGN
  -> STRATEGY_VARIANT
  -> ATTEMPT
  -> RUN
```

A backlog entry records a possible economic transfer through closed concept
codes: instruments, market behavior, causal mechanism, beneficiaries and cost
bearers, transfer rationale, information categories and availability,
expected effect, broad economic horizon, market context, and source-bound
observations. It does not contain entry/stop/target rules, indicators,
thresholds, parameter grids, exact or cosmetic timeframes, modules, PnL,
scientific verdicts, candidate status, or deployment status. Those mechanics
are structurally absent from the entry contract and remain downstream strategy
variant concerns.

Observation prose is deliberately different: it is faithful source memory,
so its statement and known conflicts accept ordinary economic terminology,
numeric source facts, and even source text that describes mechanics. That
prose is not canonical edge identity, P1 evidence, strategy authorization, or
automatic semantic acceptance. A free-text statement can become entry memory
only through an exact observation-revision reference; it never becomes a
classified concept merely because of its wording.

The canonical files live under `research/edge_backlog/`. SQLite, CSV, Markdown,
the bootstrap index, and future registry views are derived and rebuildable.

## Canonical records

All contracts reject unknown fields, use canonical JSON serialization, and
carry a stable SHA-256 over the complete record except its own hash field. Each
of the four canonical record types also carries one immutable, store-wide
`append_sequence`. The next value is derived from the validated canonical
records while the exclusive cross-process lock is held; there is no counter
file or fifth record type. Full validation requires the values to be globally
unique and exactly gap-free from 1 through the record count, while every
object-local chain must advance in append order.
Full validation reads the raw bytes of every observation, entry, decision, and
link record and requires exact equality with the validated canonical JSON plus
one final newline. Pretty printing, alternate key order, missing or extra final
newlines, and strings that normalize to different canonical bytes fail closed.
Timezone-aware timestamps and exact referenced-record hashes are required.
The committed JSON Schemas provide closed, structural validation for one
record. Cross-record semantics—including source-identity upgrades, chronology,
hash chains, exact references, duplicate canonicalization, suspension state,
and link targets—are enforced by the append API and `edge-backlog validate`;
JSON Schema validation alone is not a complete backlog integrity check.
Entry timestamps cannot precede referenced observations. Decision and link
timestamps cannot precede their bound entry revisions, authorized links cannot
precede their authorizing decisions, and changes after resume cannot be
backdated before `RESUMED`. Equality remains valid inside ordinary revision,
decision, and link chains; source-identity upgrades retain the stricter rule
below. When timestamps are equal, `append_sequence` is the authoritative causal
tie-break and historical-prefix boundary: activity with a lower value is in
scope and activity with a higher value is not.

All validation, current-state reads, duplicate-snapshot construction and stale
comparison, sequence allocation, and exclusive append run under one
cross-process backlog lock in derived runtime storage. Mutations take the lock
before their first validation and revalidate the complete persisted store
again under that lock immediately before the exclusive file creation.

### Observation revisions

An observation is a source-bound lead, not an edge claim. Each evidence
reference declares `HASH_BOUND` or `LOCATOR_ONLY` integrity, and every
observation has at least one evidence reference. `statement_kind` is exactly
`SOURCE_QUOTE`, `FAITHFUL_PARAPHRASE`, or `RESEARCHER_SUMMARY`; it records how
the statement was written and grants no evidence integrity or P1 authority.
A source quote may remain locator-only.

- `HASH_BOUND` requires a valid content or artifact SHA-256.
- `LOCATOR_ONLY` requires a durable locator, claim locator, and evidence time,
  and prohibits a content hash so it cannot masquerade as reviewed evidence.

The same `source_id` may support several claims and observations only while its
source kind, locator, and any captured content hash remain consistent. A
`LOCATOR_ONLY` source may be upgraded once to `HASH_BOUND`; that hash then
remains part of the source identity, and later reuse must supply the same hash.
Every locator-only occurrence must have a `recorded_at` strictly earlier than
the first hash-bound occurrence for that source ID. Equal timestamps are
ambiguous across objects and fail closed.

### Edge-entry revisions

Entry IDs are engine-generated opaque values of the form `edge.<32 lowercase
hex characters>`. They are not content-derived and cannot be supplied by the
caller, so separately captured discoveries do not collide merely because their
initial concepts match. Revision record IDs retain the
`<object_id>.r000001` convention.

Each entry is either `CLASSIFIED` or `NEEDS_CLASSIFICATION`:

- `CLASSIFIED` resolves every required dimension to codes published by its
  exact `taxonomy_ref` and carries the final v1 fingerprint.
- `NEEDS_CLASSIFICATION` carries an explicit closed reason, no economic
  concept payload, and no fingerprint. It remains searchable backlog memory
  and duplicate-recall material without human backlog approval.

There are no `UNKNOWN`, `OTHER`, placeholder, or free-form code fallbacks.
Unsupported instruments or genuinely novel economics remain observations and
`NEEDS_CLASSIFICATION` entries until an owner-reviewed taxonomy extension.
Codex may append classification, reclassification, or declassification
revisions; these are neither human approval nor P1 admission, and the new
revision stales decisions bound to an earlier revision normally.

An entry refers to one or more observations using the closed roles
`MOTIVATING`, `SUPPORTING`, and `CONTRADICTING`. A revision may add evidence,
but cannot silently remove an earlier contradicting reference. Every revision
also fixes `PRE_HYPOTHESIS_BACKLOG_ONLY` and
`NOT_CURRENT_P1_EVIDENCE`.

The complete taxonomy is
`research/edge_backlog/contracts/economic-edge-taxonomy-v1.json`. Each
published version is immutable and byte-bound. Its only accepted file form is
compact UTF-8 JSON with lexicographically sorted object keys, declared array
order preserved, no non-finite numbers or insignificant whitespace, and
exactly one final LF. The taxonomy SHA hashes those exact file bytes, including
the LF; pretty printing, alternate key order, omitted defaulted fields, and
missing or extra newlines fail closed.

Evolution is additive: an existing code, definition, label, invariant, or
prohibited category cannot be changed or removed; recall aliases may be added;
and new codes may be added. A newly added invariant may be triggered only by
codes introduced in that same version, so it cannot retroactively invalidate
a combination of existing codes. A semantic restriction involving an existing
concept requires a new code or owner-reviewed namespace. Old files remain
available. The taxonomy explicitly prohibits technical indicators, numeric
parameters, thresholds or triggers, trade actions, exit/position-sizing/risk
rules, exact or cosmetic timeframes, strategy implementations/modules,
performance/PnL/verdict claims, approval/admission/certification/deployment
claims, and free-form `UNKNOWN`/`OTHER`/`CUSTOM` escape channels. It also
declares each dimension's cardinality, cross-field invariants, unclassified
reasons, and hash rules. The initial taxonomy-local instrument set is exactly
`ES` and `NQ`; there is no runtime-inferred or free-form instrument fallback.

Human-readable labels are derived from the bound taxonomy's display labels and
are non-authoritative. Labels and recall aliases participate only in duplicate
matching and search; they cannot create a fingerprint, classification,
evidence, acceptance, or admission.

The economic fingerprint is SHA-256 over compact canonical JSON without a
trailing newline, containing only
`alphaquest.edge-backlog-fingerprint/v1`, the stable `taxonomy_id`, sorted
instrument codes, and all selected economic concept codes. Taxonomy version,
taxonomy SHA, display labels, and recall aliases are excluded, so additive
taxonomy versions preserve fingerprints for unchanged concepts. The entry
record itself contains the exact taxonomy ID/version/SHA reference, so the
entry revision SHA and every snapshot remain bound to the taxonomy used.

### Human decisions

The human-only operation records `HUMAN_OWNER_RESEARCHER` by construction. The
reviewer ID is provenance, not authentication, and there is no actor-type flag.
Every review binds the exact entry revision and the complete deterministic
duplicate candidate snapshot visible to the reviewer. Each candidate carries
its complete immutable entry or historical-index record SHA-256, plus current
canonical decision and link-chain identities where applicable. Candidate
revision, evidence, disposition, or relevant-link changes stale an earlier
snapshot.

Full validation independently reconstructs every canonical entry that existed
before the reviewing decision's `append_sequence`, selects its exact latest
entry, decision, and link prefixes at that boundary, reruns shared scoring,
filtering, and ranking, and requires exact equality with the complete persisted
candidate list. The bound label, state, matcher material, and other derived
fields must agree, and every record selected into the prefix must have a
`recorded_at` no later than the reviewing decision. A null decision identity is
valid only for an empty prefix. Later revisions, decisions, links, and entries
remain permissible because they fall after the immutable review boundary.

For historical recall, a review binds the full matcher-universe SHA and the
exact Git commit containing the source files used to create it. Full validation
re-extracts the complete universe from that immutable source tree with the same
source-specific parser used by bootstrap, then reruns filtering and ranking.
Each included historical candidate also embeds its complete strict
`HistoricalEdgeIndexRecordV1`. Therefore a later derived-index rebuild does not
erase an earlier binding, an omitted historical candidate is detectable, and a
source commit that is not in the required Git ancestry fails closed. Git author
and committer dates are informational only and never authorize ordering.

In a Git-backed repository, every new decision binds exact clean `HEAD` for the
historical layout and source universe. Until its canonical path and exact blob
are committed, full validation reports `PROVISIONAL`, not `PASS`. After commit,
validation finds the unique first reachable commit where that path existed at
all and requires that first appearance to contain the exact canonical `100644`
blob. The bound source commit must be its ancestor, and the layout and source
universe in the introduction commit's sole parent must equal the binding. Every
reachable descendant must retain the same path, mode, type, and blob; removal,
relocation, rewriting, disappearance/reappearance, or ambiguous merge
introductions fail closed. A later re-add cannot establish a fresh anchor. Git
cannot reveal a wholesale rewrite that occurs before the
provisional file receives its first Git anchor, so that pre-anchor interval is
not cryptographically detectable.

All authoritative P2 Git reads use one non-fetching wrapper with replacement
objects disabled and a sanitized Git environment. Replacement refs, legacy
grafts, alternate object databases, shallow history, partial-clone metadata,
and missing reachable objects fail closed before Git may establish readiness,
replay, ancestry, decision anchoring, path inventory, or cache reachability.
Ambient repository, worktree, index, object, config, namespace, shallow-file,
and replacement-ref redirects are prohibited.

- `REVIEWED_CONTINUE` is optional curation. It is not scientific approval and
  is not required before a later P4 hypothesis proposal.
- `REJECTED` is terminal.
- `DUPLICATE` is terminal and must point to an existing canonical entry present
  in the reviewed snapshot. A rejected or already-duplicate target is invalid;
  canonicalization chains and cycles fail closed.
- `SUSPENDED` is nonterminal and records explicit resume conditions.
- `RESUMED` is a separate immutable human record. Only after it exists may
  Codex append another revision.

Every decision binds an exact historical prefix of the source entry's link
chain. Terminal decisions seal the complete entry-revision and link histories.
While suspended, an entry accepts no revision, link, or review decision other
than the immutable `RESUMED` record; validation rejects forged activity inside
the suspended interval.

`UNRESOLVED` never becomes `DISTINCT_EDGE` automatically.

### Links

The link schema reserves `HYPOTHESIS_PROPOSAL`, `ADMITTED_HYPOTHESIS`,
`EDGE_FAMILY`, `CAMPAIGN`, and `REVISIT_OF`. P2 exposes only two safe store
operations:

- a deterministic `HYPOTHESIS_PROPOSAL` link, which does not require
  `REVIEWED_CONTINUE`;
- a human-governed `REVISIT_OF` link to an exact prior entry revision.

A `REVISIT_OF` link binds its target kind, ID, canonical locator, loaded entry
ID and revision, payload SHA, timestamp, and append sequence as one identity.
Its target revision and optional authorizing decision on that same target entry
must precede the link by timestamp and append order. These invariants use the
same validator before append and during full history validation.

Admission, family, and campaign link operations intentionally have no P2 CLI
surface and remain reserved for P3-P5 transitions. A revisit never changes the
prior disposition, historical outcome, or research budget.

## Actors and authority

Canonical actor classes are exactly:

- `CODEX`
- `HUMAN_OWNER_RESEARCHER`
- `ALPHAQUEST_DETERMINISTIC_ENGINE`
- `EXTERNAL_SYSTEM`

Codex capture/create/revise commands always write `CODEX`. Review and resume
commands always write `HUMAN_OWNER_RESEARCHER`. AlphaQuest computes IDs,
fingerprints, hashes, candidate sets, and structural validity, but cannot
manufacture semantic acceptance. Local provenance strings are not identity
authentication.

## CLI

Prepare a JSON payload containing only user-controlled observation or entry
fields; entry IDs, record IDs, revision numbers, append sequences, actors, timestamps,
fingerprints, and record hashes are managed by AlphaQuest. Capture the created
entry ID from the `create` response before subsequent commands.

```bash
alphaquest edge-backlog capture-observation \
  --input observation.json --actor-id codex-task-id

alphaquest edge-backlog create \
  --input edge-entry.json --actor-id codex-task-id

alphaquest edge-backlog revise edge_id \
  --input edge-entry.json --actor-id codex-task-id

alphaquest edge-backlog list --json
alphaquest edge-backlog search --query "delayed hedging" --json
alphaquest edge-backlog show edge_id --json
alphaquest edge-backlog duplicate-candidates edge_id
```

The duplicate command returns a `snapshot_sha256`. A human owner uses that
exact value when recording a review:

```bash
alphaquest edge-backlog review edge_id \
  --disposition SUSPENDED \
  --duplicate-resolution UNRESOLVED \
  --candidate-snapshot-sha256 <sha256> \
  --reason-code AMBIGUOUS_DUPLICATE \
  --rationale "The related prior edge still requires owner resolution." \
  --revisit-condition "New source evidence resolves the ambiguity." \
  --reviewer-id owner

alphaquest edge-backlog resume edge_id \
  --reason-code NEW_INFORMATION \
  --rationale "The owner reviewed material new source evidence." \
  --reviewer-id owner

alphaquest edge-backlog validate
```

There is no delete, overwrite, hypothesis-admission, campaign-admission, or
deployment command.

## Deterministic duplicate recall

Campaign and backlog adapters use one deterministic scoring, recall-threshold,
match-band, and ranking core without changing legacy campaign behavior. For
two classified entries the backlog adapter matches taxonomy codes and the
frozen display labels/recall aliases from each bound taxonomy. Observation
prose participates in lexical matching only for `NEEDS_CLASSIFICATION`
entries. Source overlap and revisit/link lineage remain universal. Historical
bootstrap rows remain unclassified lexical duplicate-recall material: they
cannot receive structured equality, fingerprint equality, classification, or
P1 authority. No LLM or embedding is an authority. Candidate output remains
advisory until human resolution, and uncertainty stays unresolved.

## Historical bootstrap

```bash
alphaquest edge-backlog bootstrap-index
```

This deterministically rebuilds the optional
`catalogs/edge_backlog_history.jsonl` cache from current campaign definitions,
historical clean-slate definitions and ledgers, the experiment registry, and
research-reset manifests. Every row retains its
source path, source hash, generation, evidence eligibility, raw identifiers,
raw edge/hypothesis/family/fingerprint, outcome, failure reason, and extraction
completeness. Output is fixed to the configured history-index path beneath the
derived catalog root; neither the CLI nor the builder may replace an arbitrary,
canonical, policy, campaign, ledger, evidence, or input-source file.
Every derived row is loaded through the same strict
`HistoricalEdgeIndexRecordV1` contract when the cache is explicitly validated
or rebuilt. Rows reject
wrong schemas, unknown fields, invalid source or record hashes, duplicate IDs
or record hashes, noncanonical JSON/order, missing provenance, and any semantic
promotion beyond `NOT_CURRENT_P1_EVIDENCE`, `DUPLICATE_RECALL_ONLY`, and
`NEEDS_MANUAL_REVIEW`. Historical duplicate candidates repeat those values as
literals and bind `history:<complete-record-sha256>`.

Structural validity is not enough. Record-level provenance validation proves
that one embedded row exactly matches its approved source projection. Explicit
index validation re-extracts every approved current source and requires
record-for-record equality with the complete, canonically ordered index;
missing, extra, duplicated, substituted, or reordered rows fail. Before a row
may enter an explicit cache validation or replacement, its project-relative
`source_path` must be inside the approved historical source inventory, match
the actual file-byte SHA, use the source kind and row convention for that file,
and equal a fresh source-specific extraction.
Campaign YAML, research-ledger CSV, experiment-registry JSONL, and reset
manifest JSON each use one shared parser for generation and verification;
paths outside those configured roots, source substitution, and fabricated
self-hashed provenance fail closed.

An existing configured target is replaceable only when its entire contents
validate as the complete current projection, the exact canonical projection of
a reachable historical commit, or the exact canonical prior-v1 projection of a
reachable historical commit. The closed prior-v1 contract requires complete
canonical bytes, source path/hash/row provenance, deterministic record identity,
strict ordering, and record hashes. A
genuine-but-truncated index, arbitrary self-hashed payload, or other existing
file fails closed.

Duplicate review does not treat the derived cache as historical authority. It
resolves an immutable Git commit, loads the strict
`config/storage_layout.yaml` blob from that same commit, and reconstructs the
complete universe from source blobs in that tree through the shared source
parsers. Missing, malformed, unsupported, or noncanonical committed layouts
fail closed. Commit-bound replay uses lexical repository paths, regular-file
mode, and Git blobs only; it never resolves a source through the current
filesystem. The committed layout and every approved source must be a `100644`
blob. Symlinks, gitlinks, executable modes, malformed or blank blobs, and an
approved source that silently projects zero rows fail closed.

Before current candidates, snapshots, or decisions are returned, HEAD, every
index stage, and the working tree must agree exactly on the authoritative
layout file and complete approved-source inventory. Comparison includes lexical
repository path, source kind, regular-file mode, and byte/blob identity, so
staged-only changes, conflicts, additions, modifications, deletions, renames,
symlinks, modes, malformed sources, and layout changes fail with an instruction
to commit or revert. Unrelated dirty paths remain permitted.

The cache is never read, created, updated, or required by candidate, snapshot,
decision, or persisted-replay paths. Present, absent, malformed, or stale cache
state therefore cannot alter their result. If no cache exists, current review
uses the Git-derived universe directly. Persisted replay reconstructs only its
decision's bound commit, committed layout and source blobs, universe hash, and
append prefix; current source dirt, current cache state, and later legitimate
committed sources cannot invalidate it. Only a source-empty state may use the
canonical empty-universe digest; unresolved source-bearing history never
silently becomes empty. `edge-backlog validate` reports cache presence only;
explicit bootstrap validation/replacement remains the cache-integrity path.

P2 canonical storage is pinned to `research/edge_backlog`; a layout cannot
relocate it. The configured cache and lock locations must be canonical lexical
repository-relative paths. Canonical creation, lock opening, and cache
replacement walk real directories from a repository descriptor, reject
symlinked parents and targets, and use no-follow, exclusive, descriptor-relative
operations so a path substitution cannot redirect a write outside the
repository. Human decisions require a standard complete Git repository;
source-empty non-Git storage remains supported only while it contains no human
decision records.

Legacy scientific verdict and lifecycle/disposition text are retained in
separate fields when both exist; the derived index does not collapse those
axes.

`source_generation` distinguishes current, configured-archive, and clean-slate
archive inputs independently from evidence status. Every row is explicitly
`NOT_CURRENT_P1_EVIDENCE`, `DUPLICATE_RECALL_ONLY`, and
`NEEDS_MANUAL_REVIEW`, even when extraction is complete. The builder never
promotes legacy semantics or invents P1 fields. It creates no canonical
observation, hypothesis, family, or backlog entry and changes no historical
file or verdict.

## Temporary legacy compatibility

The current Studio campaign-first authoring path remains available temporarily
and is not made dependent on the backlog in P2. This is compatibility behavior,
not the target operating model. Literature orchestration is P3, automated
hypothesis formulation is P4, and mandatory pre-PnL campaign linkage is P5.
