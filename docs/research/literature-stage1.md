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

The checked-in JSON Schemas are generated from the strict runtime contracts:

```bash
PYTHONPATH=src python3 tools/generate_literature_schemas.py
```

## Frozen protocol and completion rules

A protocol declares all seven mandatory lanes, initial queries, ordered
providers, minimum obligations, maximum query/result/capture/byte/time budgets,
capture-selection rule, adaptive-depth budget, and optional saturation rule.
After the first `STARTED` search in a lineage, every methodology-controlling
field is immutable; administrative annotations alone may change. Adaptive
children must remain in the frozen policy and resource envelope.

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

## Recovery sequence

1. Freeze the dossier.
2. Append `PREPARED` with immutable reservations and typed P2 plans. There are
   still zero P2 writes.
3. Append or reconcile logical P2 observations.
4. Recheck the exact prepared P2 revision, lifecycle state, and hypothesis
   links, then create or revise the entry.
5. Compute a self-excluding duplicate snapshot at `before_append_sequence`, so
   later P2 records cannot leak into its universe.
6. Append the receipt and mark the operation `COMPLETED`.

A crash after any step is recoverable from exact task-authored P2 records and
the journal. State changes and payload collisions become conflicts.

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
