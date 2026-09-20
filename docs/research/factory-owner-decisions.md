# Autonomous factory owner decisions

Status date: 2026-09-20

Observed main: `da6940ef0f5b68ba34f35cf3a27a36b7f190e018`

Stage 3 subject: `03f8bc0999606dd37f0a1e40682f773f874579e2`

Stage 3 pull request: [PR 8](https://github.com/yuxuantan/alphaquest-research-engine/pull/8)

Stage 3 source merge: `da6940ef0f5b68ba34f35cf3a27a36b7f190e018`

This pack records decisions that cannot be supplied by implementation or test
results. It creates no approval, authorization, policy change, backend, model
run, research record, or phase transition. Record an owner choice separately and
bind it to the exact subject and resulting reviewed contract.

## Prepared later decision: Stage 3 backend and cost boundary

The Stage 3 remediation is independently verified, normally merged with exact
parent and tree checks, and qualified by the bounded post-merge offline synthetic
gate. Those engineering preconditions are closed within the audited
dedicated-store scope. Further bounded P3 semantic eligibility, evidence-relation,
dossier, freeze, and P2-projection engineering may proceed with synthetic stores
and fake transports. The backend/cost boundary is deferred until real
qualification becomes the next dependency; this pack records the later options
but makes no choice or authorization.

The current Stage 3 source implements and preserves the fixed direct Responses
API backend. It has no real-model qualification. Its live status is
`NOT_RUN_COST_NOT_AUTHORIZED`; exact account/workspace binding, balance, and
billing guard were not inspected. No credential values or direct API credentials
were inspected.
Historical candidate `1c9f684...` and its reproduced `S3-M1` failure remain
preserved. The remediation closes that finding only for one dedicated,
operator-exclusive store and makes no cross-store anti-shopping claim.

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
do not qualify source merge `da6940e...`, prove model identity or semantics, establish a current
environment, or authorize canonical wiring.

A safe local access inspection recorded `codex login status` only as
`CHATGPT_MANAGED` with exit code zero. It retained no credential value and did
not inspect a direct API credential, submit or list a Cloud task, or invoke a
model. The workstation-local receipt is
`/private/tmp/alphaquest-factory-evidence-20260920/subscription-access-inspection.json`
with SHA-256
`4562fc699c984ed025669bc761ac9864544a6c596ddd53abc16f649461cb7b0a`.
The connected tool catalog and `codex cloud` CLI help expose no Cloud environment
configuration or billing-guard inspection interface, so exact account/workspace
binding, environment controls, and a no-charge billing guard remain unresolved.

A bounded metadata study at
`/private/tmp/alphaquest-factory-evidence-20260920/subscription-account-surface-check.md`
has SHA-256
`ef20ddcc1ccca6042dd0fa1460d257dee76af351bd34ec61f1d78e4913a1c2d0`.
It found that the separate app-server schema exposes account and rate-limit read
methods that could support current account and allowance snapshots, but no method
provides an atomic guarantee that a future Cloud task cannot incur a charge or
proves its environment binding. No account RPC was called; optional or null
fields cannot satisfy the billing gate.

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

No Cloud controller, backend adapter, or backend-specific validator currently
exists. Selecting this option would authorize only the exact bounded pilot after
that implementation and its independent audits pass; this pack does not itself
authorize a task submission.

Before any submission, the owner gate record must supply:

1. The exact Cloud environment ID and UI-verified binding of the observed
   `CHATGPT_MANAGED` CLI session to the exact owner-approved account/workspace and
   private sandbox repository
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

The sandbox repository's tracked inventory must contain exactly the pinned
`schema.json`. The platform and agent environment necessarily add context and
tooling; these remain part of the explicitly changed capability boundary. The
sandbox repository may contain no AlphaQuest source, literature store, real
abstract, campaign, PnL, result, trade, winner, credential value, or historical
evidence. The exact reviewable local fixture bytes are:

- `/private/tmp/alphaquest-stage3-cloud-qualification/c2-prompt.txt`, SHA-256
  `7219fb9fd9c84b24a951519ed77864865cd090233d489409e94a8adf30ad1566`;
- `/private/tmp/alphaquest-stage3-cloud-qualification/c2-input.json`, SHA-256
  `c131e6eb1ffd26db95d7730f7794dab8a47e95c89daf21ff28ddf4915cf76806`;
- `/private/tmp/alphaquest-stage3-cloud-qualification/cloud-repo-inspection/schema.json`, SHA-256
  `2bf50aa1693d8796f78aa30c2cb7f871c5c095fd86775870e061b3c0f11de6ea`.

These files are workstation-local design inputs, not durable repository evidence
or a submission receipt. The pilot must retain the exact repository, tree,
tracked inventory, schema, prompt/input hashes, CLI identity, task ID/status,
diff/result bytes, deterministic validation result, and post-task billing check
without retaining credential or secret values.

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
or canonical backend change is authorized by this document.

## Consequences of no decision

Without an Option B or C authorization, Option A remains in force and real claim
production stays paused. P3 remains incomplete, and P4 cannot treat legacy
Studio source bundles as a substitute for a current P3 dossier freeze.

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
