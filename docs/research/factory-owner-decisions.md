# Autonomous factory owner decisions

Status date: 2026-09-20

Observed main: `a3a5789ebae5d4509b5c2b764b65592a198b7d0e`

Stage 3 subject: `1c9f684312f6da1b8e4e48f1a352adddad8c08a0`

This pack records decisions that cannot be supplied by implementation or test
results. It creates no approval, authorization, policy change, backend, model
run, research record, or phase transition. Record an owner choice separately and
bind it to the exact subject and resulting reviewed contract.

## Prepared later decision: Stage 3 backend and cost boundary

Do not request this decision yet. The earlier dependency is the authorized
engineering remediation of reproduced methodology BLOCKER `S3-M1`, followed by
fresh independent audits. This pack remains prepared so the cost/backend choices
are concrete after engineering closure.

The audited Stage 3 subject implements a fixed direct Responses API backend. It
is unmerged and has no real-model qualification. Its live status is
`NOT_RUN_COST_NOT_AUTHORIZED`; credentials, account access, and balance were not
inspected. The consolidated current audit failed because `S3-M1` permits an
identifier-only post-result replacement lineage to redispatch the same
representation without result-informed provenance. Candidate `1c9f684` cannot
be integrated. An ordinary remediation commit and fresh independent re-audit are
required; that engineering work needs no owner approval under the master request.

OpenAI's [billing guidance](https://learn.chatgpt.com/docs/auth) states that API
key use is billed separately from ChatGPT. A ChatGPT subscription therefore does
not authorize or fund a direct API qualification.

The attempted cloud path is not a backend. Local-only receipts identify sandbox
repository `yuxuantan/alphaquest-stage3-inference-sandbox`, commit
`a86c234b27074f149f1da19709f9b3cf503d9505`, backend label
`CHATGPT_CODEX_CLOUD_MANAGED_MODEL_V1`, an unresolved environment, and zero
submissions. The receipt hashes are:

- `dfb8012b6c90efa0f838d202cb2bf64796da1ea8f3cbfd5b6844572c7950035f`
- `a23f4aa42d0cb43885d134f96b519f989ee5468337d773b329e945f9207b44f0`

Those files are workstation-local and are not durable repository evidence. They
do not qualify `1c9f684`, prove model identity or semantics, establish a current
environment, or authorize canonical wiring.

The completed workstation-local design study is
`/private/tmp/alphaquest-factory-evidence-20260920/subscription-boundary-design.md`
with SHA-256
`b4b730645b51573a0036ec87fc6fbdfdecf2d2494c6a72ed5cb55b6473f6db13`.
It is design evidence, not repository authority. Its inspection of documented
Codex surfaces does not establish a tool-free, byte-only equivalent to the
direct backend.

| Capability | Existing direct backend | Inspected Cloud surface |
| --- | --- | --- |
| Input and context | Canonical request bytes only | Task prompt plus repository, environment, and agent context |
| Tools and filesystem | `tools=[]`; no model workspace | Repository-backed agent with terminal capability |
| Model identity | Requested and returned model checked | Provider model identity is not attested by the inspected command surface |
| Response custody | Exact bounded Responses envelope retained | Task status, diff, and result artifact; not the raw provider envelope |
| Retry and state | Controller and transport have fixed no-retry semantics | One assistant attempt does not prove one underlying model request |
| Billing | API-key use is separately billed | Subscription allowance and any credit or overage behavior require an owner-verified guard |

Official references used by the study are OpenAI's
[authentication and billing guidance](https://learn.chatgpt.com/docs/auth),
[Codex pricing](https://learn.chatgpt.com/docs/pricing),
[Codex cloud](https://learn.chatgpt.com/docs/cloud),
[cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environment),
and [agent internet controls](https://learn.chatgpt.com/docs/cloud/internet-access).

### Option A — retain the existing $0 limit and make no submission

**Recommended and current default.** This choice continues without owner
reconfirmation. Keep `NOT_RUN_COST_NOT_AUTHORIZED`, preserve the direct backend
source, history, and regressions, and allow separately audited bug corrections.
Engineering may continue with synthetic fixtures, fake transports, source work,
documentation, and independent audits. No alternate backend may be silently
substituted, and P3 cannot claim real model qualification.

### Option B — authorize one changed-capability Cloud synthetic task

This option accepts a new identity,
`CHATGPT_CODEX_CLOUD_SCHEMA_WORKSPACE_V1`, for a schema-only synthetic pilot. It
does not claim or qualify the direct backend's no-workspace/no-tools semantics.
It requires a separately reviewed controller and validator, a closed backend
selector, and no API fallback. A pass is evidence only for the explicitly
changed agent/workspace boundary; it cannot publish canonical claims or process
real literature.

Before any submission, the owner gate record must supply:

1. The exact Cloud environment ID, ChatGPT-managed account/workspace category,
   and UI-verified binding to private sandbox repository
   `yuxuantan/alphaquest-stage3-inference-sandbox` at exact commit
   `a86c234b27074f149f1da19709f9b3cf503d9505`.
2. Agent internet `Off`; empty setup and maintenance scripts; empty application
   environment-variable and secret-name inventories; and a fresh cache.
3. The UI-observable absence of connected MCP servers, browser/search access,
   external apps, and additional repositories. Any control the product does not
   expose remains an explicit unknown.
4. A verified billing guard showing included allowance remains and no purchased
   credit, shared credit, overage, or incremental charge can be consumed. A
   usage alert alone is insufficient.
5. Authorization for exactly one synthetic task, one assistant attempt, no
   follow-up, no automatic retry, and no canonical use.

The environment may contain only the pinned `schema.json`; it may contain no
AlphaQuest repository, literature store, real abstract, campaign, PnL, result,
trade, winner, credential value, or historical evidence. The pilot must retain
the exact repository/tree/inventory/schema, prompt/input hashes, CLI identity,
task ID/status, diff/result bytes, deterministic validation result, and post-task
billing check without retaining credential or secret values.

The exact pre-submission STOP is
`BLOCKED_OWNER_ENVIRONMENT_OR_BILLING_GATE`: if any owner, environment,
isolation, or billing field is absent, ambiguous, stale, or uninspectable without
reading credential contents, make no submission. After submission, any missing
or ambiguous task ID, timeout, unsuccessful terminal state, identity mismatch,
extra or invalid output, contradictory provenance, or unproven zero spend is
terminal with no retry, repair, alternate environment, local-agent fallback, or
direct-Responses fallback. An unresolved task requires manual reconciliation and
permanent no-redispatch for that synthetic input.

The pilot succeeds only as `QUALIFIED_FOR_CHANGED_BOUNDARY_ONLY` after one task
reaches a successful terminal state, exact sandbox `HEAD` is observed, the diff
adds only one bounded schema-valid `result.json`, deterministic byte-span and
hostile-input checks pass, configured network probes fail, no credential or
local path is disclosed, and the owner confirms no incremental charge or paid
credit use. If equivalent or stricter evidence and PnL isolation cannot be
implemented and independently audited, canonical wiring fails closed.

### Option C — grant an exact capped direct API qualification exception

This is the only inspected route that preserves the existing audited backend
boundary. An authorization must bind the exact integrated merge, backend
`OPENAI_RESPONSES_TOOL_FREE_V1`, model and reasoning settings, account and
credential-provisioning boundary, maximum incremental USD spend, request/body
limits, terminal receipts, a new `PRE_RESULT_PROTOCOL`, dedicated empty store,
fixed OpenAlex profile, zero retries, and a stop at canonical claims.

The current controller processes all eligible representations in a run. Calling
it once does not prove that only one paid model request occurs. Therefore an
"exactly one request" exception also requires a separately frozen and reviewed
bounded protocol/controller that mechanically limits the whole qualification to
one actual provider call. A maximum-request statement is not a substitute for
that enforcement. Historical `LOCAL_ONLY` captures cannot be reused or upgraded,
and the run may create no relation, dossier, P2 record, hypothesis, mechanic,
campaign, backtest, or live action.

No credential check, purchase, API call, Cloud submission, qualification run,
or canonical backend change is authorized by this document. Do not ask the owner
to choose until the ongoing Stage 3 engineering remedy and its qualification
source are ready.

## Consequences of no decision

Without a later backend decision, real claim production remains paused even if
an ordinary `S3-M1` remediation is independently verified and integrated. P3
stays incomplete, and P4 cannot treat legacy Studio source bundles as a
substitute for a current P3 dossier freeze.

## Downstream owner gates

| Gate | Owner action | What it cannot override |
| --- | --- | --- |
| Semantic-review ambiguity | Decide only judgments that a future independent eligibility contract explicitly escalates. The implementation and authority of that contract are not yet defined. | Invalid capture lineage, stale claim heads, malformed output, missing required evidence lanes; this does not invent mandatory human review for every claim. |
| P5 hypothesis admission | Accept one exact dossier-bound, P2-linked economic claim for mechanics work. | Duplicate identity, missing contrary evidence, PnL contamination, absent falsifiers, stale objectives. |
| P11 mechanics interpretation | Approve lane-correct sampled mechanics evidence before any PnL-bearing stage. | Certification drift, failed timing/fill/flatten/no-lookahead checks, missing samples. |
| P15 locked holdout | Authorize the declared one-way holdout opening at its exact gate. | Earlier gate failures, exhausted access budget, post-OOS tuning, stale methodology. |
| Candidate disposition | Decide after a separately recorded independent red-team task. | Missing robustness evidence, unresolved BLOCKER/HIGH findings, immutable FAIL. |
| Semantic change | Authorize reviewed methodology, data, or implementation lineage changes. | Rewriting old evidence or carrying approval across changed hashes. |
| Abandon/revisit | Make the discretionary campaign or edge-family decision. | Deleting failures, resetting trial counts, retry-until-pass. |
| Cost/provider/data purchase | Approve an exact capped external expense or new service. | Hidden fallback, open-ended spend, unreviewed provider semantics. |
| P18 and later | Issue a separate scope authorization. | This P3-P17 goal; no live/broker authority is implied. |

All deterministic AlphaQuest gates remain authoritative. Owner judgment begins
only after required objective evidence exists and cannot convert missing or
failed evidence into a pass.
