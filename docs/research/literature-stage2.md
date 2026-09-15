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

`plan_publication(store, protocol_revision_sha256, proposals)` obtains the complete
canonical snapshot from the trusted `LiteratureStore` under its shared lock. The
existing loader validates canonical bytes, paths, hashes, global sequence and
ownership, revision chains, and full cross-record semantics before planning.
All protocol revisions and all canonical families remain in the snapshot; an
exact protocol reference does not replace the earlier frozen lane authority.

The loader's global sequence/ownership/revision block is extracted unchanged as
`_validate_canonical_sequence`. The loader still reads/decodes/checks paths and
hashes, sorts, calls that helper, calls `_validate_cross_record_state`, and returns
the records. No validation condition, order, error class, or message is changed.
The helper does not mutate its input. There is no second canonical validator.

Each proposed append extends the complete snapshot, including earlier proposals,
and passes both the same global helper and full cross-record validation. This
checks global record IDs, idempotency ownership, append sequence and predecessor,
revision predecessors, and protocol/search semantics. Unrelated canonical families
remain visible for ownership while retaining their existing semantics. A valid
recoverable completion tail blocks hypothetical appends as it does real writes.
Serial execution policy and exact STARTED/terminal matching are additional checks.
No ranking rule, frozen protocol choice, durability barrier, or schema is changed.

Persisted-state failures, including `LiteratureIntegrityError`, propagate before
proposal classification. Only after a valid snapshot is obtained can intentionally
invalid hypothetical records or unsupported schedules return
`UNSUPPORTED_PUBLICATION_SCHEDULE`, with no steps or capture identities. Unexpected
`TypeError`, `RuntimeError`, and `ValueError` defects propagate. The interleaved F4
example is rejected before source retrieval. Permanent real-store regressions
cover earlier protocol revisions, foreign search ownership, cross-family keys,
hypothetical collisions, rehashed persisted corruption, and interleaved records.

The guarantee is for **planner-approved executions** of the restricted profile,
not all outcomes expressible by canonical P3 contracts. Every approval requires
all prefixes to pass canonical validation. There is no assertion that every
provider response can satisfy the frozen minima or be captured as proposed.

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
validated snapshot's final `snapshot_append_sequence` and
`snapshot_head_record_sha256`. The head binds the entire canonical hash chain;
no search-only hash is presented as store authority. **Any canonical append makes
the plan stale**, including an append in another family. Read fresh state and
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
independent re-audit after the initial F4 audit failed. B1/B2/B3 remediation does
not itself establish independent verification. No live execution is activated by
this module or its tests.
