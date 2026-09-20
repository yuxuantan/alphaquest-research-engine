# Autonomous research factory state

Status date: 2026-09-20

Snapshot observed at: `2026-09-20T03:41:39Z`

Observed main: `da6940ef0f5b68ba34f35cf3a27a36b7f190e018`

Master request SHA-256: `485c5b68e9df6822b976f819c97afcc721f2d96d4e6360fe492414d012f283f7`

This is an observational coordination snapshot. It is not a policy, runtime
gate, approval, scientific verdict, research artifact, deployment authority, or
phase-completion authority. The machine-readable companion is
[factory-phase-ledger.json](factory-phase-ledger.json). Repository source,
canonical policy, immutable research evidence, independent audits, and exact CI
remain authoritative.

The initial observational candidate `7b53255fa43d8fd173fd1f515baeb5fe5b6e8ee9`
and its ordinary history remain preserved. Its three-report documentation audit
was consolidated as `AUDIT_FAILED` because of findings `LEDGER-C1` and
`LEDGER-M1` through `LEDGER-M3`. The workstation-local consolidation is
`/private/tmp/alphaquest-factory-evidence-20260920/ledger-audit-consolidation.json`
with SHA-256
`a7dcb9bc811c8bc5b2bc8117fdbcf724bb832562b04c3ad0e49fb003bd43777a`.
This revision records the required corrections without rewriting that candidate.

## Current factory state

P0 through P2 are complete. P3 is the earliest incomplete dependency. Main
contains the canonical offline literature layer and the bounded, real-qualified
OpenAlex acquisition pilot. The current Stage 3 remediation subject is
`03f8bc0999606dd37f0a1e40682f773f874579e2`, an ordinary child of failed
candidate `1c9f684312f6da1b8e4e48f1a352adddad8c08a0`, with tree
`c61729beb3847869ae254afd1f28132d342c9076`. [PR 8](https://github.com/yuxuantan/alphaquest-research-engine/pull/8)
merged it normally as `da6940ef0f5b68ba34f35cf3a27a36b7f190e018` with exact parents
`a3a5789e...` and `03f8bc0...`; the merge tree equals the candidate tree.

All four fresh remediation audits completed with no findings. Their local
consolidation is
`/private/tmp/alphaquest-factory-evidence-20260920/remediation-audit-consolidation.json`
with SHA-256
`385bb55244ae9f2211d18184b1e7cc43d56a5d43524fe5e20bbc9d5f4bcee42e`.
Correctness, methodology, adversarial, and security report hashes are
`1622a8213733a9caae576c1614800a403c9574418665fa231c353befac05a4a2`,
`727da41d36a818cd628998fb8878953cfd969053f53a098b2fa910e8fb6268bd`,
`edaf13c785992e7ac256ac6ed2fabb61de71e0edcd3ccacc3bd8ffb01f04c6ce`,
and `47ab6ea2bb6b6eaa3a23b561f4a13f7525e2531a1fdac96b4267c30a58e88e47`.
The remediation closes `S3-M1` only within one dedicated, operator-exclusive
store; it makes no cross-store anti-shopping claim.

The failed `1c9f684` audit remains historical evidence. Its consolidation at
`/private/tmp/alphaquest-factory-evidence-20260920/stage3-audit-consolidation.json`
has SHA-256
`cad597703c500e5d12b629b5be8bb1750a605a97f3fb293b082535fe1934b091`.
It records the original reproduced `S3-M1` BLOCKER and is not rewritten by the
new pass.

Exact-head CI run
[35483830942](https://github.com/yuxuantan/alphaquest-research-engine/actions/runs/35483830942)
passed all seven jobs. The duplicate workflow was reconciled by successful
attempt 2 of run `35483788383`; it did not change the candidate. Post-merge run
[35486747543](https://github.com/yuxuantan/alphaquest-research-engine/actions/runs/35486747543)
is the immutable exact-merge verification pointer. It remained in progress at
this snapshot and must succeed before this ledger candidate is integrated.

The post-merge synthetic receipt has SHA-256
`ca728fb21c45a285355b95db2d41ab4b04d160094f8c170453a149907da6d795`.
It records a fake acquisition-to-claim path, same-attempt reuse, rejection of a
renamed lineage before writes, clean reload, one synthetic model call, zero real
network or paid calls, 49 canonical records, one claim, 14 captures, two attempt
revisions, and zero relation/dossier/freeze/P2 output. This is Stage 3 offline
engineering evidence for the exact merge, not real-model or full-P3
qualification. The pre-merge receipt remains preserved under SHA-256
`ec0ae1d471d1d66b8066d58cc34b8d0390b8f7b25f3adddca5020feeb46e355a`.

P3 remains in progress and is recorded as `INSPECTION` while the next bounded
design contract is reviewed. Engineering integration and offline synthetic
qualification are closed for the claim-extraction slice. Real model qualification
remains `NOT_RUN_COST_NOT_AUTHORIZED`, but that later owner gate does not block
synthetic-only downstream P3 engineering with injected fake transports.

The Stage 3 subject stops at canonical claims. It does not create evidence
relations, dossiers, freezes, P2 records, hypotheses, mechanics, campaigns, or
backtests. Its real direct Responses API qualification is
`NOT_RUN_COST_NOT_AUTHORIZED`; credential availability was not inspected.

The local cloud receipts are available only on the inspection workstation. They
bind unrelated sandbox commit
`a86c234b27074f149f1da19709f9b3cf503d9505`, report zero submissions and an
unresolved environment, and do not establish a live qualification or a current
AlphaQuest backend. Their SHA-256 values are
`dfb8012b6c90efa0f838d202cb2bf64796da1ea8f3cbfd5b6844572c7950035f` and
`a23f4aa42d0cb43885d134f96b519f989ee5468337d773b329e945f9207b44f0`.

## Completed phases

| Phase | Evidence boundary | Result |
| --- | --- | --- |
| P0 | The audited P0-only range is `0d89ab434...a9d80d0d...` and contains seven commits. Candidate `a9d80d0d...` merged as `b2a5e227...`; tag `engine-v0.1.0-p0` points to that merge. Merge first parent `5ce247c3...` is separate integration metadata; its range to the candidate contains eleven commits. | Complete engine baseline. This does not approve a strategy or deployment. |
| P1 | Candidate `38b39e782...` merged as `287969b1f...`. | Complete canonical operating model. Its `POLICY_ONLY` and `EXISTING_PARTIAL` entries do not claim downstream runtime completion. |
| P2 | Candidate `ab75c6e7e...` merged as `011d9ff5f...`. | Complete canonical Edge Backlog. It remains pre-hypothesis discovery memory. |

These results are historical evidence. They do not imply that a new audit has
rerun every P0-P2 qualification against the current main tree.

## Partial capabilities in phases not started

P4 through P17 are `NOT_STARTED`. The table inventories reusable code, policy,
schemas, and tests at the pinned inspection base; inspection of that substrate
does not advance a roadmap phase. P3 alone is in progress and currently
`INSPECTION` pending review of the next bounded synthetic-only design contract.

| Phase | Existing substrate | Missing closure |
| --- | --- | --- |
| P3 | Thirteen canonical literature families, durable store, bounded P2 emission machinery, the qualified Stage 2 acquisition pilot, and merged independently verified Stage 3 remediation candidate `03f8bc0...` with post-merge offline synthetic qualification. | Review and implement the synthetic-only independent semantic eligibility contract, then evidence relations, dossier production/freeze, and bounded P2 projection. Real end-to-end qualification later needs an owner backend/cost decision. |
| P4-P5 | Strict proposal/context/import contracts and human reviewed-hypothesis artifacts. | Exact current P3 dossier-freeze and P2 linkage, one canonical proposal ingress, compact decision pack, and qualified admission. |
| P8-P10 | Deterministic authoring, atomic publication, component certification, and custom engineering handoff. | Mandatory bindings to current P5-P7 outputs and roadmap phase qualification. |
| P11-P12 | Mature mechanics validation, limited core screening, and randomized-entry monkey tests. | End-to-end qualification from the roadmap lineage and a complete accounting handoff. |
| P13-P15 | Red-team policy, candidate review substrate, experiment registry, WFA, Monte Carlo, incubation, and locked acceptance primitives. | Independent survivor-attack orchestration, full search-universe accounting, selection-bias evidence, canonical holdout transition, and end-to-end robustness qualification. |
| P16-P17 | Dataset manifests, hashes, roll/timezone contracts, ES/NQ adapters, and extensive focused tests. | Cross-source invalidation, private-data workstation inventory, universal production/synthetic barrier, approved-market routing, and bounded real ES/NQ factory qualification. |

P6 and P7 illustrate the distinction: the repository has descriptive horizon,
timeframe, required-field, and dataset-quality primitives, but neither phase has
started because no deterministic frequency router or cheapest-legitimate-data
router exists. The ledger's top-level `phase_evidence` map binds every phase
classification to exact commit-and-path pointers while preserving the same ten
fields in every phase row.

## Missing dependencies

1. P3 needs an eligible model-backed claim path before relations and dossiers can
   be qualified on real inputs. Any new backend must have its own reviewed,
   isolated contract; it cannot inherit the direct Responses audit.
2. Model-authored relevance and epistemic labels need a canonical independent
   semantic-review eligibility boundary before downstream synthesis. Its
   implementation and authority are not yet defined; ambiguous judgments must
   fail closed or be escalated to the owner without making every claim a new
   mandatory human gate.
3. P4/P5 must consume one exact current P3 freeze and P2 projection instead of
   treating the existing Studio source-bundle path as equivalent authority.
4. P6 and P7 must freeze timeframe and data-complexity routing before P8 exposes
   PnL-bearing work.
5. P13 and P14 need canonical red-team provenance and complete experiment-
   universe accounting before P15 robustness can produce defensible candidates.
6. P16 data currentness and workstation dependencies must be closed before real
   P8/P17 execution can claim reproducibility.

## Blockers

- Any paid direct API qualification requires a separate owner cost decision.
  No credential values or direct API credentials were inspected.
- The subscription-backed cloud experiment has no resolved environment or
  integrated backend. Exact account/workspace binding and a zero-charge billing
  guard remain unresolved; zero submissions prove neither execution nor semantics.
- Historical research inventory preflight findings and the retained expected
  failure for a hash-drifted strategy package require governed lifecycle work;
  they must not be repaired by rewriting frozen evidence.
- P18 research/live parity and every later live/broker phase are outside this
  goal and remain unauthorized.

## Proposed next three implementation slices

1. **Review, then implement synthetic semantic eligibility.** Use a separate
   `METHODOLOGY_DESCRIPTOR` attempt bound to the exact current claim head,
   acquisition lineage, retained abstract, extraction attempt, and input hashes.
   It must decide entailment, quote support, relevance, epistemic consistency,
   downstream eligibility, and methodology descriptors with fake transport only.
2. **Build synthetic evidence relations and dossiers.** Consume only eligible
   reviewed claim heads, preserve contrary evidence and gaps, bind every derived
   record to its producing attempt, and allow zero eligible claims as a terminal
   no-dossier outcome. Keep real inputs and PnL structurally unavailable.
3. **Freeze and project bounded P2, then stop.** Deterministically freeze one
   exact dossier and exercise the existing recoverable P2 projection with
   synthetic canonical stores. Independently audit and integrate each bounded
   slice. Only after this gate-free work is exhausted should the prepared backend
   and cost decision become the next owner gate. P4 remains `NOT_STARTED`.

## Owner gates expected

No owner decision was required for the completed exact CI, ordinary integration,
ref checks, or post-merge offline synthetic gate. No owner decision is required
now to review and implement bounded post-extraction P3 work using synthetic stores
and fake transports. Option A remains in force without reconfirmation and keeps
real qualification paused. The backend/cost choice becomes an owner gate only
when bounded real qualification is the next dependency.

In the ledger, `owner_decision_required` means that some owner gate remains
necessary before the phase can be complete. P3 is therefore `true` even though
its next synthetic-only design and implementation work requires no owner action.

Later owner gates remain: disposition of semantic-review ambiguities that the
future eligibility contract cannot resolve objectively; hypothesis admission;
mechanics interpretation before PnL; opening a locked holdout; candidate
disposition after independent red-team review;
semantic methodology, data, or implementation changes; discretionary abandon or
revisit; any new monetary cost or data purchase; and every P18+ action.

Human action cannot override missing objective evidence, stale hashes, failed
deterministic gates, immutable verdicts, or exhausted budgets.

## Updating this snapshot

Update the JSON and this page together after exact evidence changes. Preserve
historical results as historical labels. Never advance a phase because code or a
schema exists; record candidate identity, independent audit, ordinary merge,
qualification, open findings, and the next unresolved dependency separately.

Stage 3 slice verdict: **PASS within the audited dedicated-store and offline
synthetic scope; P3 remains in progress and real qualification is deferred**.

Overall factory verdict: **NEEDS MANUAL REVIEW**.
