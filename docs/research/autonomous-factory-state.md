# Autonomous research factory state

Status date: 2026-09-20

Snapshot observed at: `2026-09-20T01:53:02Z`

Observed main: `a3a5789ebae5d4509b5c2b764b65592a198b7d0e`

Master request SHA-256: `485c5b68e9df6822b976f819c97afcc721f2d96d4e6360fe492414d012f283f7`

This is an observational coordination snapshot. It is not a policy, runtime
gate, approval, scientific verdict, research artifact, deployment authority, or
phase-completion authority. The machine-readable companion is
[factory-phase-ledger.json](factory-phase-ledger.json). Repository source,
canonical policy, immutable research evidence, independent audits, and exact CI
remain authoritative.

## Current factory state

P0 through P2 are complete. P3 is the earliest incomplete dependency. Main
contains the canonical offline literature layer and the bounded, real-qualified
OpenAlex acquisition pilot. The exact Stage 3 claim-extraction subject is
`1c9f684312f6da1b8e4e48f1a352adddad8c08a0`, two ordinary commits above main
with merge-base `a3a5789ebae5d4509b5c2b764b65592a198b7d0e`. It is unmerged.

The four current audits are consolidated. Correctness and adversarial review
passed; security/reproducibility passed with a local-environment limitation.
Methodology found BLOCKER `S3-M1`, which the root independently reproduced:
identifier-only post-result protocol replacement can redispatch the identical
representation without result-informed provenance. This is a same-store manual-
caller lineage-replacement gap, distinct from the earlier acquisition-binding
defect. No automatic protocol creation, automatic retry, live call, or paid call
occurred.

This snapshot therefore records P3 as `AUDIT_FAILED`. Candidate `1c9f684` must
remain unmerged. Its earlier exact-head CI success and historical remediation
re-audit do not override the current blocker. Root broad validation of the old
candidate was deliberately interrupted after the finding: focused progress
stopped at 327 passes and full progress stopped at 459 passes. Neither is a
completed validation pass. Separate auditor suites remain evidence only within
their stated scopes.

The audit consolidation is workstation-local, non-durable evidence at
`/private/tmp/alphaquest-factory-evidence-20260920/stage3-audit-consolidation.json`
with SHA-256
`cad597703c500e5d12b629b5be8bb1750a605a97f3fb293b082535fe1934b091`.
Its supporting local hashes include methodology report
`68f1c85cb3b0343a383f02fb8ba21d9157f64e374781e017690b734abe97520a`,
methodology probe
`7696aa0fcb2e44c465db7f93a3c6e51f2b569cc148b40e66114994a0b29f0c60`,
root reproduction log
`66171f3544aa4315836799e8a9ebd7c08d1afbd6c52cf3cbae32ee80f63ef6df`,
adversarial report
`a79cf1e8dd8bcf2521233ea201d1799a20ce7b2e9988d3d5c2d7db9f09b6b564`,
and security XML evidence
`8fb94dc003dcb079c391eddbc896a0e9bcd8ce08bc9c765f2ae3834906a5b775`
and `6b1b17d002a9cd870e2564a574cb3796db178983f1335aa610ee49fde66c7573`.
The security result carries a local Python 3.12.5 limitation; reference full
gates require Python 3.12.14.

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
| P0 | Candidate `a9d80d0d...` merged as `b2a5e227...`; tag `engine-v0.1.0-p0` points to that merge. The verified integration base is merge first parent `5ce247c3...`. | Complete engine baseline. This does not approve a strategy or deployment. |
| P1 | Candidate `38b39e782...` merged as `287969b1f...`. | Complete canonical operating model. Its `POLICY_ONLY` and `EXISTING_PARTIAL` entries do not claim downstream runtime completion. |
| P2 | Candidate `ab75c6e7e...` merged as `011d9ff5f...`. | Complete canonical Edge Backlog. It remains pre-hypothesis discovery memory. |

These results are historical evidence. They do not imply that a new audit has
rerun every P0-P2 qualification against the current main tree.

## Partial phases

| Phase | Existing substrate | Missing closure |
| --- | --- | --- |
| P3 | Thirteen canonical literature families, durable store, bounded P2 emission machinery, and the qualified Stage 2 acquisition pilot; unmerged Stage 3 claim extraction. | Remediate `S3-M1` on an ordinary descendant, run fresh independent audits and complete gates, then consider exact integration. Real claim qualification, semantic-review eligibility, relation and dossier production, freeze, bounded P2 projection, and end-to-end proof remain open. |
| P4-P5 | Strict proposal/context/import contracts and human reviewed-hypothesis artifacts. | Exact current P3 dossier-freeze and P2 linkage, one canonical proposal ingress, compact decision pack, and qualified admission. |
| P8-P10 | Deterministic authoring, atomic publication, component certification, and custom engineering handoff. | Mandatory bindings to current P5-P7 outputs and roadmap phase qualification. |
| P11-P12 | Mature mechanics validation, limited core screening, and randomized-entry monkey tests. | End-to-end qualification from the roadmap lineage and a complete accounting handoff. |
| P13-P15 | Red-team policy, candidate review substrate, experiment registry, WFA, Monte Carlo, incubation, and locked acceptance primitives. | Independent survivor-attack orchestration, full search-universe accounting, selection-bias evidence, canonical holdout transition, and end-to-end robustness qualification. |
| P16-P17 | Dataset manifests, hashes, roll/timezone contracts, ES/NQ adapters, and extensive focused tests. | Cross-source invalidation, private-data workstation inventory, universal production/synthetic barrier, approved-market routing, and bounded real ES/NQ factory qualification. |

P6 and P7 are `NOT_STARTED` because the repository has descriptive horizon,
timeframe, required-field, and dataset-quality primitives, but no deterministic
frequency router or cheapest-legitimate-data router.

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

- `S3-M1` is a reproduced methodology BLOCKER. Integration of `1c9f684` is
  prohibited. Engineering must implement the reviewed no-redispatch remedy as
  an ordinary descendant and obtain fresh independent review.
- Any paid direct API qualification requires a separate owner cost decision.
  No key, balance, or entitlement was checked for this snapshot.
- The subscription-backed cloud experiment has no resolved environment or
  integrated backend. Zero submissions prove neither execution nor semantics.
- Historical research inventory preflight findings and the retained expected
  failure for a hash-drifted strategy package require governed lifecycle work;
  they must not be repaired by rewriting frozen evidence.
- P18 research/live parity and every later live/broker phase are outside this
  goal and remain unauthorized.

## Proposed next three implementation slices

1. **Remediate `S3-M1` without rewriting history.** Add one ordinary commit after
   `1c9f684` that enforces the reviewed no-redispatch architecture for identical
   representations across post-result protocol lineages. Preserve the original
   candidate and its failed audit evidence. This engineering remedy is already
   authorized and needs no owner decision.
2. **Re-audit and conditionally integrate the remediated Stage 3 history.** Rerun
   the exact reproduction and permanent regression, focused tests, complete
   validation under the reference environment, and fresh independent audits.
   Only a candidate with no unresolved BLOCKER/HIGH may proceed through ordinary
   PR integration and exact post-merge CI. No real model call is authorized.
3. **After engineering closure, resolve one Stage 3 backend boundary.** Follow
   [factory-owner-decisions.md](factory-owner-decisions.md). The recommended
   option keeps the $0 incremental-cost limit and authorizes a separately
   reviewed subscription-backed feasibility/design study while preserving the
   direct backend's history and regression coverage. No backend becomes
   canonical until an isolated no-research-repository, no-PnL qualification
   passes within the verified cost boundary. The decision pack is prepared but
   should not be presented for choice until `S3-M1` engineering closure.

## Owner gates expected

No owner decision is required for the immediate `S3-M1` engineering remedy or
its fresh audits. The Stage 3 backend/cost choice becomes the next owner gate
only after engineering closure. Routine integration of a remediated exact
history needs no additional approval if all required audits and gates pass.

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

Stage 3 candidate verdict: **FAIL** pending `S3-M1` remediation.

Overall factory verdict: **NEEDS MANUAL REVIEW**.
