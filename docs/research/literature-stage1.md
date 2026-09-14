# P3 literature layer: deterministic offline Stage 1

## Boundary

P3 is pre-hypothesis research memory. It can retain source identity, captured
evidence, source-grounded claims, quality descriptors, cross-paper evidence
relationships, a tentative edge dossier, and a deterministic projection into
P2. It does not perform scientific validation, admit a causal hypothesis,
change a P2 human disposition, create `REVISIT_OF`, read PnL artifacts, create
a campaign, or authorize deployment.

Stage 1 is deliberately offline. It has no search-provider client, HTTP
retriever, or autonomous Codex search/extraction implementation. Fixed source
bytes and locally prepared records prove the canonical path. The external-model
workspace function is a fail-closed interface stub and checks processing
permission before any workspace construction.

## Canonical families and storage

The store has exactly 13 families:

| Family | Authority |
| --- | --- |
| `protocols` | frozen methodology and execution-lineage label |
| `searches` | search start and terminal revisions |
| `source-works` | logical work identity |
| `source-versions` | version identity and availability provenance |
| `source-relationships` | additive work/version relationships |
| `captures` | artifact and extractor provenance |
| `claims` | claim revisions with byte-range locator hashes |
| `evidence-relations` | cross-paper contradiction and qualification |
| `dossiers` | supporting/contradicting pre-hypothesis synthesis |
| `dossier-freezes` | immutable input to P2 planning |
| `codex-attempts` | bounded model-task provenance; no live Stage-1 runner |
| `p2-emissions` | recoverable transaction and evidence reservations |
| `p2-emission-receipts` | exact P2 records, snapshot, gaps, and times |

Every record uses canonical UTF-8 JSON with one final LF, a content hash, a
gap-free global append sequence and predecessor hash. Revision families also
have a contiguous object revision and predecessor chain. Writes are exclusive,
no-follow, and idempotency-keyed. Canonical metadata is rooted at
`research/literature`; immutable artifacts are rooted at
`run-store/literature` and addressed by SHA-256.

Persisted records never accept the all-zero construction placeholder. The
trusted writer alone may use construction context while applying model
defaults; it computes the final intent and record hashes and then performs
ordinary strict validation before writing. Loading independently recomputes
every record hash before global or per-object predecessor validation. The
checked-in schemas also reject an all-zero `record_sha256`.

Revision numbers evolve one logical object; they do not rename a different
object into an existing stable ID. The semantic-identity boundary is explicit:

| Revision family | Immutable semantic identity | Permitted evolution |
| --- | --- | --- |
| protocol | execution lineage/kind/parent/result provenance, research question, market scope | methodology before execution; administrative annotation after execution |
| search | protocol/lineage/lane/query/parent/depth/provider/attempt identity | one `STARTED` to terminal outcome transition |
| source work | established strong identifiers, or a retained locator anchor when no strong identifier exists | title, authors, additional locators/identifiers, identity status |
| source version | work ID, version kind, established strong identifiers; label when no strong identifier exists | bound work metadata revision, availability and descriptive metadata |
| source relationship | subject kind/ID, predicate, object kind/ID | evidence, lifecycle status, replacement binding |
| capture | source-version/request/access identity | one `STARTED` to terminal capture outcome |
| claim | intellectual work ID | proposition, reliability and provenance only through the allowed recapture/version transitions below |
| evidence relation | predicate, ordered logical claim IDs, direct/inferred basis | rationale, exact current claim revisions, lifecycle status, replacement binding |
| dossier | protocol logical ID and execution lineage; P2 entry ID once emitted | current claims, relations, descriptors, taxonomy and lifecycle-linked synthesis |
| Codex task attempt | task type, model, settings/prompt/input/workspace hashes, ordered record references, isolation backend | one `STARTED` revision followed by exactly one terminal outcome, or one immutable pre-execution permission rejection |
| P2 emission operation | complete prepared transaction identity and outputs already written at each stage | only the closed forward state machine and its stage-specific derived bindings |

Append APIs and full persisted reload independently enforce the same identity
boundaries. Thus recomputing every record and predecessor hash cannot disguise
semantic migration.

The checked-in JSON Schemas are generated from the strict runtime contracts:

```bash
PYTHONPATH=src python3 tools/generate_literature_schemas.py
```

## Frozen protocol and completion rules

A protocol declares all seven mandatory lanes, initial queries, ordered
providers, minimum obligations, maximum query/result/capture/byte/time budgets,
capture-selection rule, adaptive-depth budget, and optional saturation rule.
The execution-contract hash covers the lineage kind and parent/result
provenance as well as the research scope, rules, lanes, queries, ordered
providers, minima, maxima, selection and saturation policy. After the first
`STARTED` search in a lineage, every non-administrative field is immutable;
administrative annotations and their change reason alone may change. Search
revision 2 accepts only terminal outcome fields and retains the exact revision
1 protocol, lineage, lane, query, parent, depth, provider and provider-attempt
ordinal. Adaptive children must remain in the frozen policy and resource
envelope.

Additional work prompted by observed results uses a distinct lineage labeled
`RESULT_INFORMED_EXTENSION`, with an existing parent lineage and observed
result-set hash. Earlier-lineage searches cannot satisfy its minimums.

Lane completion preserves `execution_status` (`TERMINAL` or `NONTERMINAL`)
separately from `obligation_status` (`SATISFIED`,
`UNSATISFIED_PROVIDER_FAILURE`, or
`UNSATISFIED_RESOURCE_OR_SAFETY_LIMIT`). A dossier is
`COMPLETE_WITHIN_DECLARED_BOUNDS` only when every obligation is satisfied;
otherwise it is `TERMINATED_WITH_DECLARED_GAPS`. A gapped dossier can still
produce a tentative P2 entry when it has a valid current claim. The freeze,
operation, and receipt retain all gaps.

Each terminal search binds the exact stable identities and ranks of inspected
results, the exact selected capture attempts and lane-global selection
ordinals, and a result-set hash over those records. Completion is reconstructed
from every current search in the exact lineage and lane. Provider attempts are
gap-free and follow the frozen order per query; distinct-result and
distinct-capture minima use identities rather than summed counters. Saturation
is accepted only after the minimum obligations and the frozen consecutive
no-new-work criterion are both demonstrated by the canonical query history.
Every capture attempt must name a result inspected by that same search run.
Only `SUCCEEDED` and honestly encoded `PARTIAL` runs contribute results or
captures to completion. Recorded results on a `PARTIAL` run are its explicitly
usable subset. `FAILED` and `ABANDONED_AFTER_CRASH` runs remain auditable but
contribute no result/work identities, captures, query ordering, minima, or
saturation state, and they cannot claim saturation. Saturation is recomputed
from the ordered eligible-run sequence; its sole claimant must be the final
eligible search, even when failed runs occur before, between, or after eligible
runs. Selected attempts have unique, contiguous explicit ordinals, and the
frozen provider-rank, result-rank, locator-hash rule must reproduce that exact
order independently of search-run IDs.

## Source binding and evidence time

P2 source IDs are derived from canonical P3 source-version IDs. P2 publication
state is never part of source-version metadata. The first `PREPARED` operation
instead reserves, under the P3 lock and before any P2 write, one exact
representation: source/version identity, P2 source ID and kind, locator,
capture and terminal revision, content and extracted hashes, evidence time and
basis, relationship-state hash, and owning operation.

The reservation remains immutable even if emission fails, and later operations
repeat it exactly. Byte-identical recapture can prove equivalence and use it;
byte-different content cannot. Concurrent different reservations conflict.
Later relationship corrections do not rewrite earlier receipts.

Source-version revisions remain attached to their original work. Capture
completion uses a closed terminal-field allowlist and cannot change the bound
source-version or retrieval-request identity. Claim append and full reload both
reconstruct the exact work revision to source-version revision to terminal
capture revision chain, including raw-content and extracted-representation
hashes.

One logical claim ID remains anchored to one intellectual work. A recapture of
the same source-version identity may advance that claim only when the content
and extracted bytes are identical. A different source-version identity may
advance it only as `CORRECTED`, when a current `REVISION_OF`,
`PUBLISHED_SUCCESSOR_OF`, or `CORRECTS` relationship connects the new version
to the immediately prior version. Unrelated works or unconnected versions
require a new claim ID. This keeps the claim-derived P2 observation ID tied to
one source-claim history rather than turning it into a generic container.

`evidence_time` is the verified timezone-aware exact public-availability
instant when one exists, otherwise the exact frozen capture timestamp.
DAY/MONTH/YEAR, conflicting, and unknown values never synthesize midnight.
Original value, precision, verification, timezone basis, and provenance remain
in P3; the selected instant and basis remain in the reservation and receipt.

Authoritative `SAME_WORK_AS` and `SAME_VERSION_AS` are human-owned.
Relationship corrections are additive `ACTIVE`, `RETRACTED`, or `SUPERSEDED`
revisions. Source content is always untrusted data. `LOCAL_ONLY`, `UNKNOWN`, and
`PROHIBITED` content is rejected before external-model workspace construction;
hash-bound human/local extraction remains usable when retention permits it.

## P2 lifecycle projection

P3 writes P2 only through `EdgeBacklogStore`:

| Current P2 condition | Deterministic action |
| --- | --- |
| derived `UNREVIEWED`, no hypothesis link | revise the same entry |
| `REVIEWED_CONTINUE`, no hypothesis link | revise it and record the decision SHA made stale |
| current `RESUMED`, no hypothesis link | validate exact resume state, then revise it |
| current `HYPOTHESIS_PROPOSAL` | never revise it; a bound dossier is blocked |
| `REJECTED` or `DUPLICATE` | never revise it; a bound dossier is blocked |
| `SUSPENDED` | block the bound dossier without a replacement |

An unbound dossier aimed at a hypothesis-linked or terminal entry can create a
separate tentative entry for genuinely new material, but P3 never creates the
human `REVISIT_OF` link. Taxonomy mappings are provenance-linked
`SOURCE_STATED` or `ALPHAQUEST_EXPLICIT_INFERENCE`; either can classify an
unambiguous P2 record, and neither is causal proof.

## Corrections and disagreement

A logical P3 claim maps to one logical P2 observation ID. A corrected
source-bound extraction appends both a P3 claim revision and P2 observation
revision. If extraction is invalid with no replacement, the P2 observation
revision preserves the old statement and evidence, adds
`P3_CONFLICT|INVALID_EXTRACTION_WITHDRAWN|...`, and the latest P2 entry stops
using it as motivating/supporting evidence. History remains, contradictory
references cannot disappear, and no unsupported `RESEARCHER_SUMMARY` is made.

Source corrections and retractions use new source-version records, additive
`CORRECTS`/`RETRACTS` relationships, source-bound observations, and conflict
markers. Cross-paper disagreement remains separate observations plus an
`EvidenceRelationRevisionV1`, never a collapsed conflict string.

An evidence-relation ID freezes its predicate, ordered logical claim endpoints,
and source-stated versus AlphaQuest-inferred basis at revision 1. Current
dossiers must bind the exact `ACTIVE` relation head and exact current endpoint
claim revisions at their append prefix. Historical dossiers continue to
validate against their historical prefix, but a historical freeze becomes
stale for new emission when a referenced relation is later revised, retracted,
or superseded. `SUPERSEDED` requires one already-existing `ACTIVE`,
semantically separate replacement relation; missing, self, terminal, and cyclic
replacement paths fail closed.

Current reliability is derived from the latest active relationship state. An
active `RETRACTS` relationship overrides an otherwise `ACTIVE` claim: the
affected P2 observation is revised with a `SOURCE_RETRACTED` marker, it cannot
remain current motivating/supporting evidence, and the captured retraction
notice remains separate source-bound evidence. Existing contradictory
references are retained at their exact historical revisions and the revised
conflicted observation is added rather than replacing that history.

For current use, every logical claim has exactly one head revision. A new
dossier may use a claim as `MOTIVATING` or `SUPPORTING` only when it names that
exact head and the head is currently eligible for positive support. Historical
dossiers and freezes remain immutable and byte-valid after a correction or
withdrawal, but `literature validate` exposes each freeze's separate current
emission eligibility. Preparation and recovery recheck the claim heads, so a
formerly valid freeze becomes `STALE_INELIGIBLE` and cannot emit after its
positive evidence is superseded or invalidated.

Before a correction is prepared, P3 freezes a P2 append prefix and enumerates
every current entry that references the affected exact observation revision.
Eligible entries receive deterministic normal P2 revisions; a stale
`REVIEWED_CONTINUE` decision SHA is preserved. Suspended, terminal, duplicate,
or hypothesis-linked entries are not mutated. Their exact entry revision,
lifecycle state, link-chain hash and inability reason are recorded as
`UNRESOLVED_INVALID_EVIDENCE_DEPENDENCY`, and `literature validate` reports
`operational_status: NEEDS_MANUAL_REVIEW` while structural history remains
valid. A dependency created or revised after preparation makes the operation
conflict instead of permitting incomplete correction.
The operational validator also derives these dependencies directly from the
current logical claim heads and current P2 entries. It reports required or
governance-blocked correction even when no correction operation has yet been
prepared, and returns to `CURRENT_RESEARCH_CLEAN` only after mutable positive
dependencies have actually been revised.

## Recovery sequence

1. Freeze the dossier by supplying only its ID and exact revision hash; every
   authoritative freeze field is derived and copied exactly.
2. Append `PREPARED` with immutable reservations, complete exact observation
   and entry projections, lane gaps, and the reverse-dependency snapshot. There are
   still zero P2 writes.
3. Append or reconcile logical P2 observations.
4. Recheck the exact prepared P2 revision, lifecycle state, and hypothesis
   links, then create or revise the entry.
5. Compute a self-excluding duplicate snapshot at `before_append_sequence`, so
   later P2 records cannot leak into its universe.
6. Validate the exact transaction outputs, durably append and fsync the receipt,
   then durably append and fsync its owning `COMPLETED` revision.

The two final records are separate append-only files; the lock does not make
the pair one filesystem transaction. Persistence has four distinct parts.

**Byte publication.** Each individual P3 canonical record is written completely
and fsynced at a unique path beneath the noncanonical
`run-store/literature/canonical-staging/` directory. Only then is that complete
inode hard-linked at its final canonical path by an atomic same-filesystem
no-replace operation. The P3 writer checks the staging and destination devices
and fails closed if they differ. It never creates the final pathname and then
fills its bytes. The linked inode is fsynced again before directory metadata is
acknowledged.

**Directory-entry durability.** P3 publication does not use the P2
`repository_parent_fd(create=True)` path. Its own no-follow, descriptor-relative
walker retains the descriptor and repository-relative identity of every
canonical ancestor and records which directory entries it created. After the
staging-file fsync, newly created directories and their naming parents are
fsynced bottom-up before the link. After the link and linked-inode fsync,
EVERY successful canonical publication fsyncs the COMPLETE descriptor-opened
ancestry, from the record directory through the repository root, before
staging cleanup and its directory fsync. This applies equally to the first
family record, a new object, and a new revision in an existing object.
Directory existence, the current attempt's created-directory list, and
abandoned staging files never determine the completeness of this barrier.
For example, a prior attempt may have created a directory but failed to open
it before recording its creation; the next append still anchors that directory
and every parent. A directory-fsync failure is not reported as success and
does not delete an already complete final record. Exact retries perform the
same complete ancestry barrier. Stage 1 intentionally accepts the extra fsync
cost rather than inferring durability from process-local creation history.

**Visible versus durable prefix.** Parsing and fully validating canonical
records establishes a visible prefix, not a durable one. Under the exclusive
P3 writer lock, writers first load and structurally/semantically validate the
complete canonical history and check any recoverable completion tail. Retry
conflicts already provable from that locked, validated history are rejected
before unrelated prefix-recovery I/O; integrity failures retain their existing
classification. Before successful acknowledgement or dependent publication,
writers recover EVERY record in authoritative append-sequence order: reopen the
exact canonical path, require byte equality with the validated serialization,
fsync the file, and fsync its complete ancestry through the repository root.
Only then may a successor bind the prefix or an existing canonical operation
be acknowledged. Missing/changed bytes, unsafe reopening, or any required
fsync failure blocks the successor without consuming a canonical sequence.
Malformed history is rejected before durability recovery.

This rule applies to generic append (including immutable freezes and exact
retries), specialized receipt/COMPLETED publication and receipt-tail recovery,
and the emission layer's completed/blocked returns. Receipt-tail recovery
includes the published receipt and does not rerun P2 publication. Newly
published records still require their own complete ancestry barrier; prefix
recovery is additional. Runtime artifacts are not canonical sequence members
and do not participate in canonical-prefix recovery.

Stage 1 maintains no durability frontier, marker, or authoritative in-memory
cache. Each independent transaction conservatively recovers the full validated
prefix, including older non-tail records in sibling objects/families. The
extra fsync cost is intentional. Any future durable-frontier optimization
requires a separate design and audit.

**Ambiguous post-link recovery.** An exact idempotent retry does not return just
because a matching record is visible. After the normal record hash, identity,
family, object, and revision checks, it opens the expected final file without
following links, compares its exact canonical bytes, fsyncs that file, and
fsyncs the complete directory ancestry from the record directory through the
repository root. Receipt-tail reconciliation applies the same barrier to an
already visible receipt before publishing its completion, and a completed-pair
retry barriers both files. A changed-byte collision still fails closed.

**Artifact durability.** Every P3 runtime artifact kind (`artifacts`,
`extracted`, `provider-traces`, and `codex-io`) uses a separate noncanonical
artifact staging area and the same write-completely, file-fsync, same-device,
atomic-no-replace sequence. Publication fsyncs the complete runtime ancestry
bottom-up; this includes runtime parents that may have been created while the
exclusive P3 lock was acquired as well as content-addressed directories created
by the artifact writer. Exact existing bytes receive the same conservative
file-and-complete-ancestry retry barrier.
If an older writer left wrong bytes at an unreferenced digest path, recovery
first hard-links those bytes to a unique quarantine name, durably anchors the
quarantine, removes and fsyncs the wrong final entry, and publishes the intended
bytes. If canonical P3 state references that artifact kind and digest, the
writer reports integrity damage and never replaces the bound evidence.

On the supported Darwin/POSIX platform, process death before the link leaves no
final filename, while process death after the link can expose only the complete
staged bytes. The file and bottom-up directory fsync sequence is the supported
durability barrier; underlying filesystems and storage hardware still define
the ultimate power-loss guarantees of `fsync(2)`. Abandoned staging files are
noncanonical, ignored by history discovery and append sequencing, and may be
garbage-collected rather than promoted. Tests use writer processes terminated
with `os._exit(...)` and separate inspector/retry processes at staging, write,
file-fsync, link, directory-fsync, and staging-cleanup boundaries.

A crash before the receipt is published leaves the valid `SNAPSHOT_BOUND`
state. A crash after `COMPLETED` is published leaves the valid completed state.
The only accepted intermediate state is
`RECOVERABLE_COMPLETION_TAIL`: the receipt is the final global append, owns the
exact current `SNAPSHOT_BOUND` revision, repeats every transaction output, is
unique and unused, and has no `COMPLETED` successor. Any mismatch, other orphan
receipt, partial or malformed record, or later record remains an integrity
failure. Only a fully written, fsynced, and atomically published receipt can
form this tail.

Full P3 validation resolves each written observation and entry binding in P2
and reconstructs the complete duplicate snapshot at the exact prefix,
including the historical universe and ordered candidate bindings. A valid
completion tail therefore reports structurally valid but operationally
`RECOVERABLE_INCOMPLETE_EMISSION`, with the exact operation and receipt
identity; it does not report ordinary `PASS`. Missing P2 authority is an
explicit semantic-dependency failure, never a recoverable or ordinary pass.
Once a binding or snapshot enters the journal it is immutable across later
stages.

Reconciliation reloads and revalidates both stores and every receipt ownership
field, then appends only the deterministic `COMPLETED` successor using the
receipt's existing audit metadata. It never deletes or rewrites the receipt,
creates a second receipt, or restarts P2 publication. While a recoverable tail
exists, all unrelated canonical P3 appends are rejected until that exact
operation is reconciled.

A receipt is not trusted merely because its bytes and referenced snapshot are
valid. Full reload reconstructs ownership from canonical history: every
completed operation owns exactly one receipt, every receipt belongs to exactly
one completed operation, and that receipt binds the operation's immediately
preceding exact `SNAPSHOT_BOUND` revision. Freeze, reservations, observations,
entry, dependency impacts and bindings, duplicate snapshot, gaps, and
operational status must repeat that revision exactly. Except for the narrowly
defined final recoverable tail above, orphans, duplicates, cross-operation
swaps, early receipt bindings, and receipts for older operation revisions are
invalid. Retrying an already completed emission runs this same full ownership
validation, resolves its immediately preceding exact `SNAPSHOT_BOUND` revision,
and compares every unmanaged receipt field with the caller's normalized request
before returning the existing receipt and completion. A changed snapshot,
transaction output, operation, or deterministic key is a hard conflict.

Search, capture, and Codex-attempt start/completion calls check idempotency before
lifecycle rejection. An identical retry, including after reload and for every
Codex terminal or one-shot processing-permission-rejection state, returns the
original canonical record. Reusing a key for changed intent, another object,
family, or phase is a hard conflict and never creates another revision.

## CLI

```bash
alphaquest literature put-artifact --project-root . --kind artifacts --input source.bin
alphaquest literature append work --project-root . --input work.json \
  --actor-id offline-engine --idempotency-key work.example.r1
alphaquest literature list --project-root .
alphaquest literature show work.example.r000001 --project-root .
alphaquest literature validate --project-root .
alphaquest literature prepare-emission freeze.example emission.example \
  --project-root . --actor-id offline-engine --idempotency-key emission.example.prepared
alphaquest literature emit emission.example --project-root . --actor-id offline-engine
alphaquest literature reconcile emission.example --project-root . --actor-id offline-engine
```

No Stage-1 CLI command performs live search, HTTP capture, or autonomous
extraction.
