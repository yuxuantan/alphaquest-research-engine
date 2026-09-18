# P3 Stage 3: bounded abstract claim extraction

This pilot stops at canonical claims. It implements no evidence-relation or
dossier synthesis, dossier freeze, hypothesis, P2 emission, strategy mechanics,
campaign, backtest, full text/PDF processing, adaptive research, or automatic
model retry. Implementation qualification does not authorize a real run.

## Acquisition permission

The default OpenAlex pilot remains `LOCAL_ONLY`. The owner-authorized policy is
`OPENALEX_STAGE3_PROCESSING_POLICY_V1`: OpenAlex API returned metadata and its
exact deterministic abstract reconstruction may be sent to the OpenAI Responses
API for claim extraction. This does not cover publisher pages, PDFs, DOI targets,
or independently acquired arXiv/SSRN documents.

A new protocol must contain that exact policy identifier in `inclusion_rules`
and use a fresh execution lineage. Before any provider response, the trusted
runner requires its `processing_policy` argument to agree with the protocol.
Search STARTED records bind that frozen protocol. Captures use a distinct trusted
policy actor and are created with `ALLOWED_EXTERNAL_PROCESSOR`; permissions are
never upgraded during completion. The default policy, historical captures, and
terminal capture immutability are unchanged. Extraction accepts only
`GENUINE_ABSTRACT_CAPTURED`; failed and metadata-only acquisitions are skipped.

The original qualification lineage and its `LOCAL_ONLY` archive must not be
processed. Do not rerun it. An unchanged, predeclared reacquisition can use a new
`PRE_RESULT_PROTOCOL`. A result-informed change requires the existing extension
contract and separate acquisition support; this pilot does not broaden Stage 2
admission to extensions or adaptive search.

## Supervised Python entrypoints

The existing development environment includes HTTPX; no new dependency or Agent
SDK is introduced. There is no CLI change. After independent verification and
merge, a separately authorized fresh run can call:

```python
from alphaquest.research.literature.stage2_runner import (
    OPENALEX_STAGE3_PROCESSING_POLICY_V1,
    run_openalex_pilot,
)
from alphaquest.research.literature.stage3_claim_extractor import run_claim_extraction_pilot

# dedicated_root contains a NEW frozen protocol declaring the policy above.
# protocol_sha is its exact canonical revision hash, not the old qualification.
acquisition = run_openalex_pilot(
    dedicated_root,
    protocol_sha,
    processing_policy=OPENALEX_STAGE3_PROCESSING_POLICY_V1,
)
# Only after acquisition is terminal and its evidence has been reviewed:
extraction = run_claim_extraction_pilot(dedicated_root, protocol_sha)
```

The store must be operator-exclusive and contain no P2 emissions. The controller
holds a process lock to prevent concurrent extraction dispatch. It accepts only
the bounded Stage 2 OpenAlex protocol profile. All selected abstract permissions
are checked before any model invocation. Before preparing an individual input,
the controller verifies the exact source chain, artifact sizes/hashes, trusted
capture policy actor, and deterministic OpenAlex reconstruction. Source fields
are untrusted data. No source locator is dereferenced.

## Model boundary

The model receives an in-memory, deterministically serialized request containing
one abstract, minimal immutable source provenance, the protocol question/scope,
and fixed extraction instructions. The HTTP client receives request bytes, not
a repository path. Discovery lanes, other abstracts, trading state, Git history,
and P2 state are omitted.

A fixed POST goes to `https://api.openai.com/v1/responses`, with:

- `model="gpt-5.6-sol"`, `reasoning.effort="medium"`;
- `tools=[]`, `tool_choice="none"`;
- `store=false`, `background=false`, `stream=false`;
- no previous response, conversation, files, agent runtime, or model tools;
- strict `text.format` JSON schema and `truncation="disabled"`;
- at most 8,192 output tokens, 512 KiB request and response bodies;
- 120-second elapsed budget checked between fragments, with bounded blocking I/O
  (5-second connect/pool, 10-second write, 30-second read timeouts).

A blocking read can outlast the elapsed deadline until its read timeout; this is
not a hard process-kill deadline. The transport has no redirects, retries,
proxy/CA environment inheritance, cookie reuse, or content decompression.
Fragment sizes are checked before retention. There is no model-readable filesystem
workspace, Codex CLI, container, MCP, browser, shell, or plugin capability.

The client alone reads `OPENAI_API_KEY`. It sends the credential only in the
Authorization header. Error response bodies, exception text and headers are not
persisted. Canonical records and `codex-io` artifacts contain no credential.
The request ignores endpoint override environment variables. `store=false` is an
API state setting, not a claim about every provider-side retention policy.

The fixed request follows the official
[Responses reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create),
[Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs), and
[model documentation](https://developers.openai.com/api/docs/models/gpt-5.6-sol).
Account access and a real response from this model remain unqualified until the
separately authorized live pilot. The controller rejects a different returned
model ID; there is no model fallback.

## Extraction and relevance

The noncanonical output contains only `relevance`, `relevance_basis_spans`, and
`claims`. Relevance is one of `DIRECTLY_RELEVANT`, `BACKGROUND_RELEVANT`,
`OUT_OF_SCOPE`, or `INSUFFICIENT_CONTEXT`. The last two require zero claims.
Background claims are limited to `METHODOLOGY_FACT`, `LIMITATION`, and `OTHER`;
background is never silently promoted to direct evidence.

Both relevance spans and claims contain `byte_start`, `byte_end`, and `quote`.
Claims additionally contain exactly one existing canonical `source_epistemic_form`.
There are at most five relevance spans and five claims. Extra fields, duplicate
JSON keys, nonfinite numbers, noninteger offsets, duplicate claim spans and
unsupported forms fail closed. Lane membership has no semantic authority.

Every span is a nonempty half-open UTF-8 byte range within the exact retained
abstract. The controller compares bytes and quotation without normalization or
repair, rejects split UTF-8 boundaries, and computes span and locator hashes.
Canonical statements use only `SOURCE_QUOTE` and `PLAIN_TEXT` locations. The
controller also supplies every ID, hash, actor, provenance field and idempotency
key. An invalid item invalidates the whole output before any claim is appended.

These checks prove exact quotation and provenance, not natural-language entailment
or complete coverage. Epistemic classification and relevance are model judgments
requiring independent semantic review before downstream use. The pilot does not
certify causal interpretation, replication relationships, or trading value.

## Attempt lifecycle and artifacts

`CodexTaskAttemptRevisionV1` is reused without schema changes. Its task type,
model and backend fields support bounded external-model execution; no contract
requires a CLI process. This pilot uses `CLAIM_EXTRACTOR` and
`OPENAI_RESPONSES_TOOL_FREE_V1`.

`workspace_manifest_sha256` remains required by that existing contract. Here it
binds an explicit **in-memory input-boundary manifest** with
`filesystem_workspace="NONE"`, exact request/input hashes, empty tools and no
continuation. It does not assert that filesystem materialization occurred.

Content-addressed `codex-io` artifacts retain the exact request, settings,
instructions, logical input manifest, boundary manifest and bounded API response.
The input manifest points to the request hash and exact canonical references.
No temporary path, staging clock or unrelated store head enters these artifacts.

Before API dispatch the controller publishes STARTED. It appends exactly one of:

- SUCCEEDED: complete response with fully validated extraction (zero claims valid);
- INVALID_OUTPUT: malformed, schema-invalid, or byte-invalid extraction;
- FAILED: API error/timeout, refusal or incomplete response;
- ABANDONED_AFTER_CRASH: a later exclusive invocation finds an orphaned STARTED.

A refused or incomplete response is never successful zero-claim evidence. A
permission rejection occurs before model input retention or invocation and
creates no invoked attempt. Invocation errors retain fixed categories only.

After SUCCEEDED, all claims are constructed deterministically and published with
`actor.task_id` bound to that attempt. Store append and persisted reload verify
pilot claims against the preceding successful attempt, its exact manifests,
request/response artifacts, eligible capture, and deterministic claim payload.
Human/local extraction remains on its existing path. This first pilot publishes
revision-one claims only; a future correction workflow needs its own reviewed
scope rather than rewriting pilot output.

A storage failure preserves the valid canonical prefix and stops. SUCCEEDED
records model-output validation, not atomic batch publication. Reentry verifies
fully published outputs but never invokes again. Missing claims after SUCCEEDED
require deterministic/manual reconciliation. Failed or abandoned attempts cannot
automatically retry. Output-artifact or terminal-publication failure may leave
STARTED and likewise requires reconciliation. No generic recovery engine exists.

## Deduplication and noninterference

Deduplication uses work ID, source-version ID, content hash, extracted hash,
extractor ID/version/config hash. Eligible captures are sorted by capture ID;
one representative is processed per exact group. The result lists all capture
appearances. Attempt ID binds that representation and the execution lineage; its immutable
input references bind the exact protocol revision. Administrative protocol
revisions cannot create another model attempt for the same representation.
Reentry reuses the same successful result; it cannot silently change model,
prompt or settings. Unrelated works sharing text remain distinct. Suspected
2001/2003 versions are not merged.

Synthetic differential tests vary unrelated PnL, strategy, trade, result and P2
files while keeping canonical inputs fixed. Request bytes, input/boundary
manifests, and prompt/settings hashes must remain identical. Model responses
need not be deterministic.

## Validation and later qualification

Normal tests use synthetic OpenAlex records and fake Responses transports only:

```bash
python3 -m pytest -q tests/test_literature_stage3_claim_extractor.py tests/test_literature_stage2_openalex.py
make lint
make docs-check
make validate
git diff --check
```

A real acquisition and extraction run is deferred until implementation,
independent audit, merge, and separate run authorization. There is no dossier,
evidence relation, hypothesis, P2, full-text or adaptive-search activation here.
