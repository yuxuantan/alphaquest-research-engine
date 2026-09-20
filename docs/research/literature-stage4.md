# P3 Stage 4 Slice A: synthetic semantic review

Slice A reviews each exact current Stage 3 pilot claim against its retained
abstract and the exact semantic research context. It derives one advisory value:
`ELIGIBLE_DIRECT`, `ELIGIBLE_CONTEXT_ONLY`, `AMBIGUOUS_EXCLUDED`, or
`INELIGIBLE_EXCLUDED`.

This implementation is an engineering qualification harness. It has no HTTP
client, endpoint, credential lookup, environment lookup, callable client,
fallback model, production CLI, or retry. A fixture response does not prove that
`gpt-5.6-sol` made the judgment. Every receipt, manifest, return value, and loaded
evidence object retains the literal qualification class
`SYNTHETIC_FIXTURE_ONLY`. The production-use helper always rejects this evidence.

## Authority and STOP boundary

The result is P3 advisory provenance. It is not scientific validation, source
identity equivalence, causal interpretation approval, hypothesis admission, P1
approval, P2 admission, dossier creation, permission to test performance, or a
tradeability verdict. Slice A reads no campaign, result, PnL, trade, holdout,
account, or credential state.

The only canonical writes are existing `codex-attempts` records. Noncanonical,
content-addressed `codex-io` artifacts retain settings, prompt, exact requests,
input and boundary manifests, exact synthetic fixture responses, and synthetic
qualification receipts. Slice A does not append or revise claims, source
relationships, evidence relations, dossiers, freezes, P2 objects, hypotheses,
campaigns, mechanics, or results. The 13 canonical families and schemas are
unchanged.

## Exact inputs and stable identity

Admission accepts only a unique current revision-one `ACTIVE` claim produced by
the fixed Stage 3 actor and its exact preceding terminal `SUCCEEDED`
`CLAIM_EXTRACTOR` attempt. The controller independently reconstructs the Stage 3
request, response, deterministic claim payload, OpenAlex acquisition binding,
work, source version, capture, raw bytes, abstract bytes, quote span, and exact
selected protocol. Corrected, withdrawn, retracted, stale, substituted, manual,
or copied-metadata claims fail before semantic-review artifacts are published.

The model-visible input contains only:

- the exact research question, market scope, ordered inclusion rules, and ordered
  exclusion rules;
- exact canonical title and authors plus the complete retained abstract; and
- the claim byte range, exact quote, and source epistemic form.

IDs, hashes, actors, task IDs, lineages, discovery lanes, other claims, prior
outcomes, P2 state, Git state, and trading state remain outside the request.
Source fields are untrusted data.

The semantic subject hash binds source and quote meaning while excluding the
claim ID and administrative metadata. The research-context hash binds the four
semantic protocol fields while excluding protocol and lineage names. The review
context hashes those two values. Its attempt ID is always:

```text
attempt.stage4.semantic.<review_context_sha256>
```

Model, prompt, backend, controller, protocol, lineage, claim-ID, or task-ID
renaming cannot reset this store-wide consumed context.

## Synthetic preparation and execution

The read-only preparation helper exposes the exact request hashes required to
construct the fixture mapping:

```python
from alphaquest.research.literature.stage4_semantic_reviewer import (
    prepare_semantic_review_requests,
    run_semantic_review_synthetic,
)

requests = prepare_semantic_review_requests(dedicated_root, protocol_sha)
# An external qualification harness constructs one exact bounded response byte
# string for every returned request SHA-256.
result = run_semantic_review_synthetic(
    dedicated_root,
    protocol_sha,
    response_by_request_sha256=response_bytes_by_request_sha256,
    qualification_class="SYNTHETIC_FIXTURE_ONLY",
)
```

There is no default response source. Missing, extra, non-string hash keys,
non-byte values, and oversized values fail complete-batch preflight. Zero claims
requires an empty mapping and writes nothing.

Before the first fresh `STARTED`, the controller validates the complete ordered
plan and every existing owner. A later stale input, duplicate owner, receipt
mismatch, orphan, terminal failure, or reserved-dispatch mismatch blocks every
fresh context. It then publishes all fresh fixture bytes, the receipt, and only
then settings, prompt, requests, and receipt-bound manifests. Raw responses exist
only in separate content-addressed artifacts; receipts bind response hash and
byte count.

## Output and advisory derivation

The strict output has exactly three assessments, at most five top-level basis
spans, and at most ten unique methodology descriptors. Every span is an exact
half-open UTF-8 byte range in the retained abstract. Duplicate JSON keys,
nonfinite numbers, booleans or floats in integer fields, extra fields, split UTF-8
boundaries, quote mismatch, duplicate spans, duplicate descriptor kinds, and
invalid descriptor/basis combinations invalidate the entire output.

`EXACTLY_SUPPORTED` requires the claim's own exact quote span. `OVERSTATED` and
`NOT_SUPPORTED` require a basis span. The controller derives advisory use in this
fixed order:

1. exact support + direct relevance + consistent epistemic form becomes
   `ELIGIBLE_DIRECT`;
2. exact support + background relevance + consistent form becomes
   `ELIGIBLE_CONTEXT_ONLY` only for methodology, limitation, or other context;
3. any ambiguity or insufficient context becomes `AMBIGUOUS_EXCLUDED`; and
4. every other valid output becomes `INELIGIBLE_EXCLUDED`.

A valid exclusion is terminal `SUCCEEDED`. It consumes the context and never
requests a human click or retries for a favorable answer.

## Receipts, lifecycle, and reentry

Each receipt freezes the initial canonical head, exact protocol and ordered claim
references, stable batch key, planned contexts and requests, reused successful
owners, and fresh fixture hashes and byte counts. Its initial head is ancestry
provenance, not a requirement that the current head remain equal.

Fresh attempts append `STARTED`, then exactly one terminal revision:

| Status | Response | Failure reason |
| --- | --- | --- |
| `SUCCEEDED` | present | none |
| `INVALID_OUTPUT` | present | `INVALID_SEMANTIC_REVIEW_OUTPUT` |
| `FAILED` | present | `REFUSAL_OR_INCOMPLETE_RESPONSE` |
| `ABANDONED_AFTER_CRASH` | absent | `ORPHANED_ATTEMPT_NO_REDISPATCH` |

One classifier governs runtime and reload. A rehashed status that contradicts
the retained fixture fails validation. Success, valid exclusion, invalid output,
failure, abandonment, and orphan `STARTED` all consume the base context.

All-success reentry requires an empty mapping and writes nothing. Partial
successful progress selects the original frozen receipt despite a newer store
head, reuses completed attempts, and reads remaining fixtures only from retained
receipt bindings. An orphan reentry publishes only abandonment and stops. A
terminal failure is returned unchanged and blocks later progress. Unowned receipt
artifacts are never selected.

For mixed historical success and genuinely fresh contexts, a new receipt binds
each reused owner to its original terminal attempt and receipt. Every fresh
attempt retains its own receipt; the return includes ordered `receipt_refs` and
per-attempt `owning_receipt_sha256` values.

## Synthetic evidence loading

The only loader preserves the synthetic class:

```python
evidence = load_synthetic_semantic_review_evidence(
    store,
    attempt_id,
    required_receipt_sha256=receipt_sha,
)
require_production_semantic_review(evidence)  # always raises LiteratureAuthorityError
```

No generic loader erases or coerces the qualification class. A later real
semantic-review backend and consumer require a separate authorized contract,
implementation, audit, and qualification.

## Validation state

The focused suite uses only synthetic OpenAlex acquisition, fake Stage 3
extraction responses, and retained Stage 4 fixtures:

```bash
PYTHONPATH=src:. python3 -m pytest -q tests/test_literature_stage4_semantic_reviewer.py
PYTHONPATH=src:. python3 -m pytest -q tests/test_literature_stage3_claim_extractor.py
make lint
make docs-check
make validate
git diff --check
```

Passing these checks supports only engineering qualification. Real-model
qualification remains `NOT_RUN_COST_NOT_AUTHORIZED`; P3 remains in progress and
P4 remains blocked.
