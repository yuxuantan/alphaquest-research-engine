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

`plan_publication` replays every proposed STARTED/terminal prefix through the
unchanged canonical search-history validator using a pure adapter exposing
only that validator's two static dependencies. It additionally enforces the
initial execution policy and exact STARTED/terminal identities. It does not
implement an alternative ranking rule, weaken validation, batch terminal
revisions, or write an invalid intermediate state. If any prefix fails, the
entire plan returns `UNSUPPORTED_PUBLICATION_SCHEDULE` with no steps or capture
identities. The interleaved example is rejected at A, before any source retrieval.
Generated parity tests compare approved prefixes with the actual full store
validator; public store append/reload tests cover serial execution and replanning.

The guarantee is for **planner-approved executions** of the restricted profile,
not all outcomes expressible by canonical P3 contracts. Every approval requires
all prefixes to pass canonical validation. There is no assertion that every
provider response can satisfy the frozen minima or be captured as proposed.

## Timing and caller obligations

1. Before dispatch, admit the exact protocol and derive its frozen execution plan.
2. A future trusted caller supplies the complete ordered search-history projection
   from a currently validated canonical snapshot for that exact protocol revision.
   The planner revalidates hashes, search identities, serial order, and search
   prefixes. It cannot establish projection completeness from worker testimony.
3. After the provider search response, normalize bounded inspections and propose
   exact capture-attempt identities and ordinals. This slice uses fake data only.
4. Plan the proposed terminal outcome before retrieving any source body.
5. `CAPTURE_RETRIEVAL_ALLOWED` exposes only the first, already-STARTED search's
   `next_capture_attempts`. Zero attempts authorize no retrieval. Later planned
   pairs are hypothetical: publish the first terminal through the canonical
   store, read fresh history, and replan before any later provider's retrieval.

A plan snapshots terminal bytes and binds the protocol and search-history hashes.
It is an F4 ordering decision for exact known inputs, not a durable authorization
token, dispatch reservation, or safety approval. Do not transplant it to another
history, change selections, or use it after outcome drift. Actual terminal
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
independent audit; no live execution is activated by this module or its tests.
