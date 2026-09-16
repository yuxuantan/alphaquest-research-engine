# Stage 2A: deterministic admission and publication planning

Stage 2 remains blocked. This prerequisite slice addresses F4 scheduling for
an initial restricted executor. It contains no provider client, dispatch,
retrieval, credentials, worker, parsing, retention, or source-byte handling.
No schema change was made; the thirteen canonical families are unchanged.

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
   capture identities and ordinals. This slice uses fake data only; the worker
   does not receive store access.
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
durable F3 reservation, authorization token, or safety approval. F3 remains open.
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

F1 SSRF transport, F2 worker/PnL isolation, F3 dispatch reservation, F5 resource
limits, F6 secret boundaries, and F7 pre-retention authorization remain open.
The dedicated security review is complete with remaining blockers. Owner
activation is pending, and Stage 2 is blocked. F4's bounded candidate requires
independent re-audit after the initial and first-remediation audits failed. B1,
B2, and B3 were independently closed; R1/R2 remediation under approved Model A
still requires independent verification. No live execution is activated by
this module or its tests.
