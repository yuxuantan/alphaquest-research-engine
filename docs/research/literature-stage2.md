# Stage 2: restricted OpenAlex pilot and F4 planning

General Stage 2 production activation remains blocked. The owner authorized a
supervised, keyless OpenAlex pilot after F4 passed independent verification and
was merged in `019b51e9cf082d53c9ebc1eb58485b35a726313d`. The pilot implementation
requires independent verification. No schema change was made; the thirteen
canonical families, Stage 1 writer, and F4 policy are unchanged.

## Supervised OpenAlex pilot

Run one frozen seven-lane workflow with:

```bash
alphaquest literature openalex-run --project-root /path/to/dedicated-p3-store \
  --protocol-revision-sha <exact-canonical-protocol-sha256>
```

The only operator inputs are the project root and exact protocol hash. There are
no URL, hostname, arbitrary-query, file, shell, provider, or credential options.
The trusted Python entry point is `stage2_runner.run_openalex_pilot`. Its private
transport injection is solely for offline tests, not an untrusted worker API.

Every lane requires one initial query, one provider (`openalex`),
`minimum_provider_attempts = 1`, `maximum_queries = 1`, `adaptive_max_depth = 0`,
and disabled saturation. Only `PRE_RESULT_PROTOCOL` is admitted. The result cap
is `min(10, maximum_results)` per lane. Inspection and capture minima must fit
that cap; capture attempts are bounded by `maximum_captures`. An impossible
minimum or unsupported protocol fails before STARTED or network dispatch. Frozen
queries are used verbatim; returned provider order becomes rank `1..N`, with
provider rank 1. The prefix is never reranked for supportive conclusions.

Use a dedicated, operator-exclusive P3 store with no P2 emission operations.
The controller validates the complete intrinsic P3 snapshot, then rejects any
emission-bearing store before invoking public writers or transport. This is a
pilot admission restriction, not a change to Model A or Stage 1. It avoids P2
historical reads while preserving full Stage 1 validation at every real append.
Do not move or delete existing evidence to satisfy this restriction. Do not run
other canonical writers concurrently with the pilot. Unexpected canonical
appends during a request make it stop for manual reconciliation.

### Adapter and request contract

`providers/openalex.py` never writes canonical state. The trusted controller
converts its bounded normalized output into existing records. Requests use only
`GET https://api.openalex.org/works`, with `search` equal to the frozen query,
`per_page` equal to the bounded cap, and `select` equal to:

```text
id,doi,display_name,publication_date,authorships,abstract_inverted_index
```

These fields support stable identifiers, citation metadata, unverified public
availability, and abstract reconstruction. No citation counts, OA-location links,
full-text URLs, or popularity-based reranking are needed. Request encoding is
deterministic, with a 4,000-byte URL cap; oversized frozen queries are rejected,
never split or rewritten. This follows OpenAlex's documented
[Works search](https://help.openalex.org/api/searching/) and
[field selection](https://help.openalex.org/api/selecting-fields/) mechanisms.

A fresh HTTPX client makes exactly one request per dispatched lane, with HTTPS
certificate verification enabled, environment trust disabled, redirects disabled,
no cookies carried between requests, no credentials, and only JSON/identity
encoding request headers. No response URL is fetched. Connection timeout is at
most 5 seconds and read timeout at most 10 seconds, tightened for smaller frozen
elapsed budgets. HTTPX's transport has zero connection retries. Only one
connection is allowed; idle connections are not retained.

Streaming raw bytes are bounded by `min(1 MiB, maximum_bytes)` before extending
the buffer. Compressed and non-JSON responses are rejected. A monotonic deadline
is checked between chunks; read timeout still bounds each blocking read. This is
not a general process-wide wall-clock/DNS isolation mechanism. Observed frozen
byte/time overruns are never clamped into false canonical counters: the STARTED
record remains for manual reconciliation when no truthful terminal fits its
frozen budget. No archives, PDFs, browsers, OCR, or HTML parsers are involved.

### Identity, captures, and permission

The adapter validates the JSON envelope, bounded result count, work ID syntax,
DOI shape, metadata types, bounded strings/authorships, and publication date.
Duplicate work/result identities reject the response rather than silently
renumbering provider ranks. Extra response fields have no authority.

The canonical locator is the normalized DOI URL when present, otherwise the
validated OpenAlex work URL; neither is dereferenced. Work identity uses the
existing `SHA256("work|" + locator)` convention, and `SearchResultInspectionV1`
checks the canonical work/locator result hash. AlphaQuest derives search, work,
version, and capture IDs itself. Provider data cannot choose paths, filenames,
actors, append sequences, or hashes.

Selected results create `SourceIdentityRevisionV1`,
`SourceVersionIdentityRevisionV1`, and `SourceCaptureRevisionV1` through
`LiteratureStore`. Identity remains `PROVISIONAL`; publication dates are
`SOURCE_REPORTED_UNVERIFIED`, never invented exact instants. Source versions are
explicitly `OTHER` OpenAlex metadata snapshots, not assertions about a publisher's
paper-version history. The capture retrieval locator is the actual bounded
OpenAlex Works request.

For a valid abstract index, unique integer positions must be contiguous from
zero. Reconstruction joins the exact words by position with ASCII spaces and
encodes UTF-8. It neither invents missing words nor summarizes. Token/position and
text-byte bounds also apply. Genuine abstract captures retain the selected
OpenAlex work's validated selected fields as canonical JSON, plus the deterministic UTF-8
extraction, with hashes and extractor provenance. Missing abstracts yield
`LOCATOR_METADATA_ONLY`. Malformed abstracts yield a `FAILED` selected capture
without retaining evidence bytes; neither case substitutes a later-ranked paper.

OpenAlex describes its API data as
[CC0](https://help.openalex.org/data/how-its-built/). The pilot's retention policy
applies only to data returned directly by OpenAlex: `OPEN_PUBLIC`, local retention
`ALLOWED`, redistribution `ALLOWED`, and external processing `LOCAL_ONLY`.
These are existing contract values. They do not authorize fetching or retaining
publisher content, PDFs, HTML, DOI targets, or OA-location URLs. No LLM or external
model processor is invoked.

### Dispatch, F4, and crash behavior

An ephemeral per-store file lock serializes pilot invocations. It is not a durable
F3 reservation. The canonical STARTED record is persisted before each request.
Before dispatch the controller calls the merged F4 planner with the exact STARTED
step and a zero-capture failure contingency. That hypothetical record is never
published as a fabricated outcome and authorizes no captures. It checks the serial
execution step before the single provider search. Actual normalized results and
capture selections require a new F4 plan before any capture is published.

The controller publishes only the plan's exact first-step captures. Work/version
appends change the snapshot, so it replans immediately before each capture's
retention/publication. After all selected captures, it obtains another fresh plan
and publishes its exact terminal bytes through `finish_search`. Every actual
append still uses the unchanged full validation and durability path. New canonical
state requires fresh planning; no old plan is transplanted to a different step. The pilot searches serially and stops after the
first failed request. Missing result minima remain explicit canonical lane gaps.
A successful provider response does not imply that every lane obligation is met
or that an abstract was available.

Any existing search history in the execution lineage rejects a new invocation.
An orphan STARTED anywhere in the pilot store also blocks it. A deterministic
search ID cannot be regenerated to evade this rule. There are no retries after
429, 5xx, timeout, crash, or ambiguous outcome, and no automatic continuation of a
partly completed workflow. Ordinary bounded provider failures get a FAILED
terminal revision when possible. Internal defects, stale authority, over-budget
outcomes, or interrupted capture publication require manual reconciliation.
Never delete canonical history or mint a fresh search ID to force a retry.

The controller reads only P3 state and storage configuration. Requests and
normalization never consult PnL, campaigns, trade logs, research results, reset
history, or P2 historical universes. Differential tests hold initial P3 bytes and
protocol constant while changing unrelated research files. Tests also forbid P2
store construction, exercise real F4 rejection and snapshot drift, and verify
that concurrent pilot invocations cannot double-dispatch.

### Qualification and limits

Ordinary tests use fake HTTP transports and require no external network. A real
OpenAlex smoke is a separately invoked, bounded single request after local
validation, using disposable state only. It is not a CI requirement or scientific
evidence and must not be written into historical canonical research.

The pilot does not provide general F3 reservation, automatic recovery, generic
SSRF-safe arbitrary URL retrieval, PDFs, HTML, multiple providers, concurrency,
adaptive search, or LLM execution. The live provider corpus can change: request
construction and normalization of the same bytes are deterministic, not a promise
that OpenAlex will return the same results on a later date.

F1 general SSRF transport, F3 general reservations, F5 advanced resource limits,
and F7 general retention policy are deferred. F2 worker/PnL isolation is deferred
to Stage 3; this trusted serial controller is not a worker sandbox. F6 credentials
are not required for this keyless pilot. General Stage 2 production activation
remains blocked, and Stage 3 is not implemented here.

## Audited Stage 2A foundation

## Admission and execution policy

`admit_protocol` in `src/alphaquest/research/literature/stage2_policy.py` accepts
an exact, hash-valid `ResearchProtocolRevisionV1`, including all seven mandatory
lanes. Every lane must have exactly one initial query, `maximum_queries == 1`,
`adaptive_max_depth == 0`, and disabled saturation. Only `PRE_RESULT_PROTOCOL`
is supported. Adaptive execution and `RESULT_INFORMED_EXTENSION` are excluded.

Unsupported protocols remain valid canonical history. Admission rejects their
execution without editing the protocol. These execution restrictions may be
widened only through separately reviewed architecture.

The plan enumerates every lane in its frozen protocol-list order and every
provider in that lane's exact `provider_order`. It cannot skip a provider based
on supportive results, substitute a query, or reorder responses by quality.
External concurrency is one: each provider must terminalize before the next
provider starts. Concurrency is execution policy, not canonical methodology.
Failures remain terminal records. Missing minima remain governed shortfalls;
this planner does not declare a lane scientifically complete or omit gaps.

## Canonical authority and the F4 proof

`finish_search` constructs the terminal search revision; `_append` validates the
new canonical state before publishing it. `_validate_cross_record_state` invokes
`_validate_protocol_search_history`, which calls `_validate_lane_search_proof`.

The latter takes the current revision of each search. Only `SUCCEEDED` and
`PARTIAL` runs contribute eligible inspected results and capture selections.
Provider ranks must match frozen provider order, and result ranks must be
ordered and gap-free inside each provider attempt. Eligible inspections are
sorted by `(provider_rank, result_rank, locator_sha256, result_identity_sha256)`
and deduplicated by stable result identity. That identity binds work and locator,
not the provider. Selected identities must be unique and exactly equal the
beginning of the resulting ordered list. Selection ordinals must be the
lane-global contiguous sequence `1..N` at every terminal append.

With one query and serial providers, new eligible results have a higher
provider rank than every earlier provider's inspections. New identities append
to the deduplicated order; duplicate sightings do not move an earlier identity.
Lexically or hash-earlier locators and overlapping per-provider result ranks
cannot override provider rank. Same-work/different-locator and
same-locator/different-work results are distinct identities. `PARTIAL` has the
same ordering role as success; failed or abandoned runs add no eligible results
and cannot contribute captures. Minima affect obligation satisfaction, not
whether an intermediate search prefix is valid. Maximum budgets still apply.

This preserves an already valid selected prefix, but does **not** make every
possible proposed capture ownership valid. For example, provider A inspects
R1/R2/R3 and selects R1/R3 as ordinals 1/3; provider B inspects R2/R4 and selects
R2/R4 as 2/4. The combined final lane can validate, but neither terminal can
be appended first. The duplicate R2 does not shift ranking: it lets a later
provider propose ownership of a capture whose rank comes from an earlier
inspection. Protocol admission alone is therefore insufficient.

## Approved Model A boundary

The owner approved Model A: F4 approval establishes intrinsic P3 scheduling
validity for the exact complete snapshot and restricted profile. It does not
establish that unrelated downstream P2 or historical operational dependencies
are healthy. An intrinsically valid terminal can still fail full publication
because an unrelated emission's P2/historical dependency is unavailable.

`plan_publication(store, protocol_revision_sha256, proposals)` obtains its complete
snapshot under the trusted store's shared lock through the explicit private
`_load_and_validate_p3_intrinsic_snapshot()` entry point. All protocol revisions
and every canonical family remain present, including emission journals and
receipts. A search projection never supplies authority.

Both loaders reuse `_read_and_validate_p3_records()`: safe canonical-file reading,
decoding, canonical bytes, paths, hashes, sorting, and the unchanged global
`_validate_canonical_sequence`. Intrinsic planning then uses
`_validate_p3_intrinsic_cross_record_state`. It validates protocol/search history,
source provenance, claims/relations, dossiers/freezes, Codex-attempt lifecycle,
exact P3 references, emission transitions, P3-derived reservations, embedded-plan
identity/hash/reliability consistency, embedded binding relationships, and receipt
ownership. An exact recoverable completion tail blocks unrelated append planning;
malformed tail/receipt structure remains a persisted integrity failure.

Prepared reservation derivation is shared with full validation. Intrinsic plan
checks distinguish payload fields determined by P3 from prior statements,
conflicts, and frozen observations that require external P2 authority. No missing
external observation is replaced with `None`, an empty record, or invented data.
Embedded external bindings are assertions, not proof of current P2 existence.

The existing `_load_and_validate()` and `_validate_cross_record_state()` remain
full validation entry points for every existing Stage 1 caller. Full validation
still resolves P2 observations/entries, reconstructs decisions/links/dependencies,
and verifies Git-bound historical duplicate universes. Shared orchestration
preserves their original interleaving and first-error order, including external
lookups before later intrinsic checks. There is no public validation-disable
switch. Publication, durability, contracts, and schemas are unchanged.

Each hypothetical append extends the complete intrinsic snapshot and passes both
global validation and intrinsic cross-record validation. It includes ownership
from unrelated families and earlier hypothetical records. The guarantee is:
planner approval implies intrinsic validity of every proposed prefix. With healthy
external dependencies, equivalent public appends still succeed. With unhealthy
external dependencies, F4 can remain approved while full publication fails.

The trusted controller must satisfy full operational publication requirements;
F4 approval is not a bypass. This slice adds no execution or reservation mechanism.
Actual publication remains subject to the existing locked full validation and
durability barrier.

Persisted intrinsic P3 corruption propagates as `LiteratureIntegrityError` before
proposal classification. Only proposal-controlled `model_validate_json` parsing
normalizes a Pydantic `ValidationError` into `_UnsupportedProposal`. The proposal
loop catches only that explicit classification. Unexpected internal
`ValidationError`, `TypeError`, `RuntimeError`, and `ValueError` propagate, including
errors from global, intrinsic, protocol/search, prepared, and receipt validators.
Rejected schedules expose neither steps nor captures.

Permanent regressions retain B1/B2/B3, restricted-profile admission, interleaved
capture rejection, generated prefix parity, and first-step isolation. Model A
regressions seed unrelated completed emissions, hold P3 bytes and proposals fixed,
and vary research ledgers, campaign/bootstrap state, experiment/reset history,
backtest outputs, Git-bound source state, and P2 corruption. The committed-ledger
case explicitly leaves F4 unchanged while full Stage 1 validation reports
`P2_SEMANTIC_DEPENDENCY_UNAVAILABLE`. External authority and subprocess entry points
are forbidden during instrumented intrinsic planning. Full-path compatibility
regressions assert first exception class/message on multiply-invalid histories.

## Timing and caller obligations

1. Before dispatch, admit the exact protocol and derive its frozen execution plan.
2. Only the trusted AlphaQuest controller loads validated `LiteratureStore` state
   and invokes publication planning. The untrusted provider/worker must **not**
   supply authoritative canonical history or construct a trusted planning context.
   The planner accepts a store and exact protocol hash, not `search_history`.
3. Provider output supplies only bounded external result data. The trusted
   controller converts it to typed proposed records, including exact inspections,
   capture identities and ordinals. The Stage 2A tests use fake data; the provider adapter does not receive store access.
4. Plan the proposed terminal outcome before retrieving any source body.
5. `CAPTURE_RETRIEVAL_ALLOWED` exposes only the first, already-STARTED search's
   `next_capture_attempts`. Zero attempts authorize no retrieval. Later planned
   pairs are hypothetical: publish the first terminal through the canonical
   store, read fresh history, and replan before any later provider's retrieval.

A plan snapshots terminal bytes and binds the protocol hash plus the complete
intrinsically validated snapshot's final `snapshot_append_sequence` and
`snapshot_head_record_sha256`. The head binds the entire canonical hash chain;
no search-only hash is presented as store authority. **Any canonical append makes
the plan stale**, including an append in another P3 family. External P2 or
historical changes alone do not change this F4 snapshot identity under Model A. Read fresh state and
rebuild proposed envelopes before replanning. These fields are evidence, not a
durable F3 reservation, authorization token, or safety approval. General F3 remains deferred for the supervised pilot.
Do not transplant a plan to another history or use it after outcome drift. Actual terminal
publication remains subject to the store's locked, full-history validation and
durability barrier. Intervening canonical writes may require new envelope hashes.
Post-retrieval status/accounting changes require validation again; this planner
does not estimate unknown bytes, meter resources, or preapprove retention.

The duplicate counterexample is observable after provider results and capture
selection are known, before source retrieval. It therefore does not demonstrate
an unavoidable F4 side effect under this architecture. Provider search itself
may already have occurred; durable dispatch accounting remains the separate F3
blocker. A later provider that cannot extend the existing selected prefix is
rejected before retrieving its source bodies. Previously valid terminal records
remain intact.

The initial and first-remediation F4 audits failed. Remediation 2 under the
owner-approved Model A passed independent verification for the restricted profile,
including B1/B2/B3 and R1/R2 closure, and was merged through PR #6. The pilot uses
that unchanged foundation. Its own independent verification remains pending.
General production activation is blocked; no Stage 3 work is authorized here.

### Opt-in fresh Stage 3 acquisition

The default thin pilot remains `LOCAL_ONLY`. A fresh protocol may predeclare
`OPENALEX_STAGE3_PROCESSING_POLICY_V1` in its inclusion rules and invoke
`run_openalex_pilot(..., processing_policy=OPENALEX_STAGE3_PROCESSING_POLICY_V1)`.
The runner rejects a mode/protocol mismatch before provider dispatch. New
captures then record the owner-authorized external-processing permission at
creation; historical captures and the original qualification lineage remain
unchanged. This adds no adaptive queries, providers, full-text acquisition, or
permission-upgrade path. See [Stage 3 claim extraction](literature-stage3.md) for
the exact processing boundary and separately authorized qualification workflow.
