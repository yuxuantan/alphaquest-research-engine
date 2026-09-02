# AlphaQuest Research Operating Model

Status: canonical P1 policy

Operating-model policy: `2026-09-02.2`

Introduced against: P0 tag `engine-v0.1.0-p0`, engine contract
`2026.08.14.1`, methodology `2026-08-14.2`

The machine-readable source is
[`config/research_operating_model.yaml`](../../config/research_operating_model.yaml).
The validator is `alphaquest.research.operating_model`. This document explains
that policy; it does not create a second set of state values.

AlphaQuest optimizes the probability that an apparent historical edge survives
unseen live trading. It does not optimize the number, speed, or apparent quality
of historical `PASS` results. Falsification comes first, failures remain durable,
and no later destination or live outcome rewrites an earlier scientific fact.

## Scope and enforcement boundary

P1 defines governance and contracts. It does not build an edge backlog,
literature agents, portfolio optimizer, broker router, live executor, or new data
lane. The policy labels each transition as exactly `EXISTING`,
`EXISTING_PARTIAL`, or `POLICY_ONLY`. Every partial transition declares current
runtime behavior, target behavior, its known gap, and required migration. Every
policy-only transition explicitly disclaims current runtime enforcement.

The policy's canonical identity is its schema, policy version, and policy-content
SHA-256. The engine tag/contract and methodology above are immutable introduction
provenance, not current-version requirements. A later engine or methodology
version does not require a P1 change when operating-model semantics are unchanged.
A semantic operating-model change does require a new policy version and content
hash. Changing P1 definitions does not silently change historical gate thresholds
or rebind old results; semantic methodology changes still follow the independently
versioned methodology process.

### Runtime conformance

Canonical policy, not a legacy compatibility path, is the contract for future
automation. The machine policy records two verified candidate-review gaps:

- current runtime requires candidate reviewer identity to differ from mechanics
  reviewer identity, while canonical P1 permits one human with separate tasks,
  context, and provenance;
- current runtime can let destination-specific account `PASS` contribute to
  candidate creation, while canonical P1 treats account suitability strictly as
  a side axis.

`APPROVE_HISTORICAL_CANDIDATE` is therefore `EXISTING_PARTIAL`. P1 does not
delete those compatibility paths or rewrite prior evidence. Both require future
migration, and neither may satisfy canonical P2/P3 automation.

### Constitutional closure

For this policy version, the 36 transition IDs form an exact set. The validator
binds every ID to its one canonical initiator, `from_stage`, `to_stage`, and—when
present—exact `applicable_stages`. It also binds every transition to an exact
state-effect map. Unknown, additional, missing, or alternate effect fields and
values fail closed, so an otherwise valid transition cannot manufacture state
on another scientific, candidate, forward, portfolio, deployment, or operational
axis. An unknown transition, missing transition, or rewired auxiliary edge also
requires an explicit policy-version, code, and test review.

Ingress to `SHADOW`, `SMALL_LIVE`, and `LIVE` is independently protected:
`AUTHORIZE_DEPLOYMENT`, `PROMOTE_SHADOW_TO_SMALL_LIVE`, and
`PROMOTE_SMALL_LIVE_TO_LIVE` are the only lifecycle ingress transitions.
Monitoring append, safety pause, and retirement remain operational side-axis
events applicable while an instance is shadow, small-live, or live; their
canonical `LIVE -> LIVE` representation never grants lifecycle promotion.

All 16 research objects likewise have exact mutability contracts. An immutable
approval, result, candidate review, assessment, or deployment decision remains
immutable historical evidence when its binding later becomes stale. Currentness
is recomputed on `EVIDENCE_CURRENTNESS` and related decision axes; it blocks
current use or requires a new downstream object, never mutation of the old one.

## Existing-state audit and terminology normalization

The repository already contains most of the required concepts, but they live in
separate bounded services:

- `campaign -> variant -> attempt -> run` lineage, including one immutable run
  per attempt and explicit replication, data refresh, methodology rerun,
  pre-PnL correction/declaration, and rescue attempt kinds;
- run verdicts `PASS`, `FAIL`, and `NEEDS MANUAL REVIEW`;
- registry navigation states `active`, `review_queue`, `candidate`, and `closed`;
- strategy package states `development`, `active`, `deprecated`, `retired`, and
  `quarantined`, separate from certification currentness;
- hash-bound manual mechanics approval before PnL;
- candidate review after a separate red-team task and qualifying historical result;
- append-only forward incubation with `ACTIVE`, `ELIGIBLE_FOR_REVIEW`, `FAILED`,
  `RETIRED`, and `NEEDS MANUAL REVIEW`;
- exact-profile account assessment separated from scientific validity;
- verdict-neutral portfolio analysis;
- a human deployment decision whose current execution capability is explicitly
  `none`;
- append-only monitoring states `HEALTHY`, `ALERT`, and `RETIREMENT_REVIEW`;
- a proposal-only Codex factory whose successful output is
  `VALIDATED_NOT_APPLIED`, never approval or a verdict.

The inconsistencies are naming and scope, not missing historical evidence:

1. “Lifecycle” currently describes campaign navigation, strategy-package
   availability, factory workflow, forward incubation, and account type. These
   answer different questions.
2. `PASS` is used by checks, stages, account assessments, and terminal research
   results. A bare `PASS` therefore needs its axis and bound object.
3. Factory `TERMINAL_PASS` is terminal only for its bound factory result. It is
   not terminal for research, forward incubation, or deployment.
4. Registry `candidate` is a navigation projection after a separately tasked
   review. It does not mean account-suitable, deployable, or tradeable.
5. `FROZEN` describes mutability. It is not a scientific, lifecycle, or
   deployment state.
6. The unqualified word `PROMOTED` is ambiguous and is not canonical for new
   contracts. Every promotion must name its exact transition.
7. The current forward service makes a candidate `ELIGIBLE_FOR_REVIEW`; it does
   not yet create a distinct accepted-forward-review artifact. P1 defines that
   future boundary without altering existing evidence.
8. Current portfolio output is deterministic and verdict-neutral. P1 defines a
   separate portfolio disposition for later orchestration rather than pretending
   `READY_FOR_HUMAN_REVIEW` is acceptance.
9. Current candidate review requires a reviewer identity different from the
   mechanics reviewer and retains a compatibility path where destination-specific
   account `PASS` may contribute to candidate creation. Both are declared
   `EXISTING_PARTIAL` gaps. Canonical P1 supports one human through separated
   task/context/provenance and prohibits account suitability from manufacturing
   Candidate Strategy status. Future automation may not treat either legacy path
   as canonical; runtime migration is required before full-conformance claims.

Compatibility values remain readable and unchanged. P1 normalizes their axis:

| Current term | Canonical interpretation | Preserved meaning |
| --- | --- | --- |
| registry `active` | lifecycle navigation plus active disposition | no terminal campaign decision |
| registry `review_queue` | blocked disposition | missing, ambiguous, or pending evidence |
| registry `candidate` | historical-candidate-review stage | separately reviewed candidate only |
| registry `closed` | abandoned or retired disposition | closure reason remains in source evidence |
| run `PASS/FAIL/NEEDS MANUAL REVIEW` | scientific state | immutable per-run result |
| package lifecycle | implementation state | availability is separate from certification freshness |
| forward statuses | forward state | never scientific or deployment state |
| account `PASS/FAIL/NEEDS MANUAL REVIEW` | account-suitability state | exact profile only |
| deployment decision states | deployment state | decision record; no order-routing capability |
| monitoring statuses | operational state | cannot rewrite research |

## Research object model

The canonical hierarchy is:

```text
observation
  -> hypothesis -> edge family
  -> campaign -> strategy variant -> attempt -> run
  -> historical validation result -> candidate strategy
  -> forward-incubation plan -> forward observations
  -> portfolio candidate -> deployment package -> live strategy instance

historical validation result
  -- scientific PASS + sufficient unseen evidence + exact profile
  -> account-suitability assessment
  -- deployment prerequisite only -> deployment package
```

Objects do not merge merely because they share an identifier or appear on one
screen.

| Object | Meaning and creation | Mutability and owner | Bound evidence and invalidation |
| --- | --- | --- | --- |
| Observation | Source-bound lead, created when a market observation is recorded | Append-only until promoted; human owner | source/capture identity; source failure or tampering invalidates it |
| Hypothesis | Falsifiable causal edge claim, separate from mechanics | Proposal mutable; accepted artifact immutable; human owner | reviewed sources, null, falsifiers, timeline, objectives; retraction, duplication, or causal failure invalidates it |
| Edge family | Related research generations sharing a causal mechanism | Append-only lineage/disposition; human owner | member hashes, budget, failure and revisit history |
| Campaign | One governed test program for one economic edge | Append-only variants/attempts; human owner | campaign definition, fingerprint, duplicate review, objectives, ledger |
| Strategy variant | One value-independent mechanical expression | Frozen after publication; human owner | config, parameter declaration, rationale, certification, predecessor `FAIL` for successors |
| Attempt | One scientific intention to produce at most one run | Pending then immutable; human owner | kind, parent, authored config hashes, reason, author |
| Run | One execution of one attempt | Immutable after completion; deterministic-engine owner | run UID, engine, methodology, config/data hashes, artifacts |
| Mechanics approval | Human implementation-fidelity decision, never profit approval | Immutable and hash-bound; human owner | sample, config/data/implementation/certification hashes; any bound semantic drift stales it |
| Historical validation result | Scientific and objective outcomes under exact identities | Immutable; deterministic-engine owner | ResultBundle, finalization, stages, OOS evidence |
| Candidate strategy | Historically supported result with a separate red-team task and human disposition | Immutable review; currentness recomputed; human owner | candidate review, result, mechanics approval, task context and provenance |
| Forward plan | Frozen true-forward duration, sample, and abandonment contract | Immutable plan plus append-only events; human owner | candidate/config/objective hashes and start time |
| Forward observation | Canonical record of genuinely later paper, shadow, or market evidence | Append-only; AlphaQuest custodian, external source | source identity, event chain, timestamp, attachment and reconciliation |
| Portfolio candidate | Forward-reviewed candidate eligible for interaction analysis | Immutable input binding; human owner | current candidate, forward journal, acceptance-OOS inputs |
| Account-suitability assessment | Independent side-axis exact-profile rule and payoff result | Immutable; deterministic-engine owner | scientific PASS, appropriate unseen evidence, profile/version/hash, trades, costs, seeds, attestations |
| Deployment package | Human-authorized allocation and monitoring contract | Immutable; new package for any change; human owner | candidates, forward evidence, limits, sizing, kill rules |
| Live strategy instance | One externally activated shadow/small-live/live instance | Append-only operations; human owner | deployment hash, instance ID, mode, monitoring journal |

Downstream objects bind upstream bytes. Invalidating an upstream currentness
claim blocks current use; it never edits the old object.

## State model

AlphaQuest must never expose one giant status. Every decision names an axis and
object.

### Research lifecycle stage

The canonical process order is:

```text
DISCOVERY
-> HYPOTHESIS_REVIEW
-> APPROVED_FOR_IMPLEMENTATION
-> IMPLEMENTATION
-> MECHANICS_CAUSAL_REVIEW
-> HISTORICAL_SCREENING
-> FULL_HISTORICAL_VALIDATION
   [record immutable PASS / FAIL / NEEDS MANUAL REVIEW without advancing]
   [PASS + predeclared candidate eligibility only]
-> HISTORICAL_CANDIDATE_REVIEW
-> FORWARD_INCUBATION
-> FORWARD_REVIEW
-> PORTFOLIO_REVIEW
-> ACCOUNT_SUITABILITY_REVIEW
-> DEPLOYMENT_REVIEW
-> SHADOW -> SMALL_LIVE -> LIVE
```

Monitoring is not a research-lifecycle stage. It updates `OPERATIONAL_STATE`
while the instance remains at `SHADOW`, `SMALL_LIVE`, or `LIVE`. Monitoring
evidence can pause or retire an instance, but cannot create or rewrite scientific
validity.

`ACCOUNT_SUITABILITY_REVIEW` names where a current suitability result is required
on the normal deployment path; it does not restrict when the calculation may
run. Account suitability is an independent side axis and may be computed whenever
scientific validity is `PASS`, sufficient appropriate unseen evidence exists, and
an exact profile exists. It writes only account-suitability state. It cannot
create scientific `PASS`, Candidate Strategy, forward or portfolio acceptance,
or deployment authorization.

Lifecycle disposition is independent: `ACTIVE`, `BLOCKED`, `EXHAUSTED`,
`ABANDONED`, `PAUSED`, `RETIRED`, or `SUPERSEDED`. `EXHAUSTED` is an automatic
terminal disposition caused by a predeclared objective rule; `ABANDONED` is a
human scientific disposition. `RETIRED` is also terminal. `PAUSED` is reversible,
and `SUPERSEDED` preserves the old lineage while naming a newer one.

### Independent decision axes

- Scientific: `NOT_EVALUATED`, `EVALUATING`, `PASS`, `FAIL`, or
  `NEEDS_MANUAL_REVIEW`.
- Implementation: `NOT_IMPLEMENTED`, `DEVELOPMENT`, `AWAITING_CERTIFICATION`,
  `CERTIFIED_CURRENT`, `CERTIFICATION_STALE`, `DEPRECATED`, `RETIRED`, or
  `QUARANTINED`.
- Forward: `NOT_STARTED`, `ACTIVE`, `ELIGIBLE_FOR_REVIEW`, `ACCEPTED`, `FAILED`,
  `RETIRED`, or `NEEDS_MANUAL_REVIEW`.
- Portfolio: `NOT_REVIEWED`, `READY_FOR_HUMAN_REVIEW`, `ACCEPTED`, `REJECTED`,
  or `NEEDS_MANUAL_REVIEW`.
- Account suitability: `NOT_ASSESSED`, `PASS`, `FAIL`, or
  `NEEDS_MANUAL_REVIEW` for one exact profile.
- Deployment: `NOT_REVIEWED`, `REVIEW_PENDING`,
  `APPROVED_FOR_MANUAL_DEPLOYMENT`, `REJECTED`, `PAUSED`, `RETIRED`, or
  `NEEDS_MANUAL_REVIEW`.
- Operational: `NOT_RUNNING`, `HEALTHY`, `ALERT`, `RETIREMENT_REVIEW`, `PAUSED`,
  or `STOPPED`.
- Evidence currentness: `CURRENT`, `STALE`, `MISSING`, `HASH_MISMATCH`, or
  `BLOCKED`.

An attempt's scientific state may be terminal while the candidate's lifecycle
continues. Forward `FAILED` does not retroactively change a historical `PASS`;
it blocks downstream promotion and adds contradictory evidence. Operational
`ALERT` does not itself establish scientific `FAIL`; it can force a safety pause
and a human retirement or new-research decision.

Historical verdict recording is not a lifecycle promotion. AlphaQuest records
`PASS`, `FAIL`, or `NEEDS MANUAL REVIEW` immutably while the research remains at
`FULL_HISTORICAL_VALIDATION`. A separate deterministic eligibility transition
may enter `HISTORICAL_CANDIDATE_REVIEW` only for scientific `PASS` with all
predeclared candidate prerequisites. `FAIL` remains evidence for a governed
successor variant, campaign exhaustion or abandonment analysis, and possible
future revisit. `NEEDS MANUAL REVIEW` remains fail-closed; resolution produces
distinct governed evidence and never rewrites the original verdict.

Every human review has explicit non-success paths. Candidate review records
`APPROVED_CURRENT`, `REJECTED`, or `NEEDS_MANUAL_REVIEW`; forward review records
`ACCEPTED`, `FAILED`, or `NEEDS_MANUAL_REVIEW`; portfolio review records
`ACCEPTED`, `REJECTED`, or `NEEDS_MANUAL_REVIEW`. Rejection stays at the current
stage and cannot advance. Manual-review outcomes also set the lifecycle
disposition to `BLOCKED` until governed resolution.

## Actors and authority

The four actor classes are deliberately asymmetric:

- Codex proposes, critiques, implements an explicitly authorized scope, runs
  already authorized deterministic work, and summarizes evidence. It has no
  approval, gate-override, or deployment authority.
- AlphaQuest computes objective facts, validates identities, creates immutable
  evidence, enforces transition prerequisites, and fails closed. It does not
  exercise unrecorded judgment.
- The human owner admits hypotheses, approves interpretations, accepts
  high-information/high-irreversibility transitions, and owns risk. Human
  approval cannot override missing or failed objective prerequisites.
- External systems provide data, time, broker, market, and execution events.
  They are observation sources, not canonical research custodians, and do not
  approve research or deployment.

### Transition authority matrix

“Automatic” means AlphaQuest owns the result once all inputs exist. It never
means that Codex may invent inputs.

| Transition | Initiator | AlphaQuest facts | Human gate | Codex authority | Reversible |
| --- | --- | --- | --- | --- | --- |
| Record research lead | Codex or human task | schema/no mutation | no | unverified proposal only | no; supersede instead |
| Propose hypothesis for review | AlphaQuest from Codex/human proposal | schema, sources, no implementation admission | no | proposal only | no; supersede instead |
| Admit hypothesis | human | fields, hashes, duplicate review | required | propose only | no |
| Start bounded implementation | human-scoped task | catalog/handoff and information boundary | admission already required | implement approved scope | yes before freeze |
| Submit mechanics | Codex or engineer | tests, certification, lane evidence | no | prepare only | yes |
| Approve mechanics | human | all checks/sample/current hashes | required | prohibited | no; stale on change |
| Run historical screening/stages | AlphaQuest | preflight, stages, one-run-per-attempt | no trivial click | request an authored run only | no |
| Record screening failure | AlphaQuest | immutable limited-core/monkey `FAIL`, lineage, search history | no | cannot decide or override | no; bound path ends |
| Open locked acceptance OOS | human | all prior gates, unopened holdout, frozen identities | required | prohibited | no |
| Record historical verdict | AlphaQuest | recomputation and artifact integrity; `PASS`, `FAIL`, or `NEEDS MANUAL REVIEW` | no | cannot decide | no; remains in full validation |
| Enter historical candidate review | AlphaQuest | immutable scientific `PASS`, no unresolved review, predeclared eligibility | no | cannot decide | no |
| Approve historical candidate | human owner after separate red-team task | eligibility, hashes, task/provenance separation | required | cannot approve | no; may stale |
| Reject/block historical candidate | human | current evidence and explicit rejection/manual-review reason | required | cannot approve | no; does not advance |
| Start forward incubation | human | current candidate, plan, start time | required | prohibited | no |
| Append forward observation | AlphaQuest from external source | source identity, chronology, hashes, reconciliation | no | summarize only | no |
| Mark forward eligible | AlphaQuest | days, trades, no failure | no | cannot decide | no; later failure can block |
| Accept forward review | human | current journal and thresholds | required | cannot approve | no |
| Reject/block forward review | human | current journal and explicit rejection/manual-review reason | required | cannot approve | no; does not advance |
| Create portfolio review | AlphaQuest | exact OOS inputs and statistics | no | interpret only | no |
| Record portfolio disposition | human | current inputs | required | propose only | no |
| Reject/block portfolio review | human | current inputs and explicit rejection/manual-review reason | required | cannot approve | no; does not advance |
| Assess account suitability side axis | AlphaQuest | scientific `PASS`, unseen evidence, exact profile, rules | attestations only when external facts require them | request/summarize only | no; does not advance lifecycle |
| Enter deployment review | AlphaQuest | scientific `PASS`; approved/current candidate; forward and portfolio `ACCEPTED`; exact-profile account `PASS`; current certification/evidence | no new click | cannot decide facts | no |
| Authorize deployment | human | same exact positive states plus validated limits, allocation, and kill rules | required | prohibited | authorization can be withdrawn |
| Shadow -> small live -> live | human | current monitoring, limits, authorization | required at each mode change | prohibited | can pause/roll back |
| Append monitoring side-axis state | external/AlphaQuest | chronology, thresholds, alerts in shadow/small-live/live | no per-period approval | analyze only | no |
| Safety pause | AlphaQuest | predeclared hard rule | no | cannot override | yes after human review |
| Retire/re-enable | human | instance and evidence identity | required | cannot decide | retirement terminal; re-enable uses new authorization |
| Stop campaign on predeclared rule | AlphaQuest | objective rule, reason, evidence, complete lineage | no | cannot override/restart | terminal `EXHAUSTED`; revisit is new lineage |
| Discretionarily abandon campaign / edge family | human | complete evidence and scientific rationale | required | propose only | abandonment preserved |
| Revisit failed edge | human | material trigger, old lineage, new identity | required | propose only | new lineage |

## Codex autonomy policy

Codex may autonomously perform bounded, reversible, evidence-preserving work:

- search and read permitted literature, while leaving uncaptured web evidence
  partial and unverified;
- propose and critique hypotheses, estimate feasibility, and prepare unconfirmed
  drafts;
- implement an admitted, bounded mechanics specification and add tests;
- initiate an already-authored attempt only when mechanics approval, preflight,
  identity, and attempt availability pass deterministically;
- run predeclared robustness analysis without changing parameters, windows,
  thresholds, or methodology;
- summarize evidence, diagnose bugs, and identify uncertainty;
- conduct a separate advisory red-team task;
- prepare review packages and analyze forward/live diagnostics.

Codex output never becomes approval merely because it validates against a
schema. Human approval is required for hypothesis admission, mechanics,
locked-acceptance opening, candidate/red-team disposition, forward start and
review, portfolio disposition, deployment, sizing/risk, semantic methodology,
data or implementation changes, discretionary abandonment/revisit, and
retirement or re-enablement. Objective campaign exhaustion, valid forward-event
capture, and routine same-contract data append do not need trivial approval.

Codex is explicitly prohibited from:

- weakening gates, objectives, or account constraints after results;
- moving or reopening OOS/holdout windows after access;
- deleting, hiding, or relabeling failed research or parameter searches;
- rewriting ResultBundles, approvals, trade logs, verdicts, or methodology
  identity;
- approving its own mechanics or red-team output;
- recertifying changed code without classification, tests, version review, and
  the governed certification process;
- authorizing deployment, mode promotion, re-enablement, sizing, or live risk;
- changing account rules or risk limits to rescue a strategy;
- converting missing evidence to `PASS`;
- silently approximating unsupported data or mechanics;
- retrying until `PASS` or resetting search history by renaming objects;
- using live performance to rewrite earlier research.

## Deterministic AlphaQuest authority

AlphaQuest owns exact facts whenever software can decide them: byte hashes,
certification currentness, data/roll/methodology binding, predeclared numerical
gates and campaign stops, immutable scientific verdict recording, PASS-only
historical-candidate eligibility, WFA selection, stitched OOS, Monte Carlo,
sample/calendar sufficiency, one-run-per-attempt, legal prerequisites, artifact
immutability, canonical forward-event capture, routine same-contract data
append validation, stale approval invalidation, portfolio statistics, account
rules, allocation limits, and monitoring/safety rules.

Neither Codex nor a human may override missing or failed objective evidence. A
human may make a named judgment only after objective prerequisites pass—for
example, accepting a falsifiable hypothesis, interpreting reviewed mechanics,
or deciding whether adequate forward evidence warrants deployment risk.

## Separation of duties

Separation is recorded by role and task, not inferred from conversational
intent.

1. Hypothesis generation and implementation are separate. The accepted causal
   hypothesis is frozen before mechanics and parameters. PnL is not a mechanics
   input.
2. Implementation and evaluation are separate. Implementers may not change
   gates, objectives, or data windows. AlphaQuest computes verdicts.
3. Evaluation and red-team review are separate. A promising result requires a
   fresh separately recorded adversarial task with provenance distinct from the
   implementation task. Red-team findings are advisory until a human disposition.
4. Historical validation and forward incubation are separate. Forward events
   must be later than the immutable start, strictly ordered, and content
   addressed. Historical OOS cannot be uploaded as forward evidence.
5. Scientific validity and account suitability are separate. Account
   assessment requires scientific `PASS` and writes only the account axis.
6. Candidate and deployment authorization are separate. A candidate supplies
   evidence but no execution authority.
7. Live observation and research are separate. Live facts may seed a new
   observation or hypothesis but never mutate old lineage.

AlphaQuest is a single-human repository. “Independent” means distinct task and
context, recorded provenance, implementation ownership, deterministic evaluation
ownership, and red-team ownership—not a second human identity. A valid sequence
is Codex implementation task A, deterministic AlphaQuest evaluation, fresh Codex
red-team task B, then the sole human owner's final disposition. Codex still
cannot approve its own work, and neither task nor the human may override an
objective gate. P1 does not add trivial human confirmations to deterministic
checks.

## Attempt and search governance

The immutable hierarchy remains `edge family -> hypothesis -> campaign ->
variant -> attempt -> run`.

- A new variant is a materially distinct, value-independent expression of the
  same accepted edge. It requires the immediately prior variant's current
  mechanics approval and terminal scientific `FAIL`, an unconsumed authorized
  variant slot, and a campaign that is neither `EXHAUSTED` nor `ABANDONED`. It
  must remain within a bounded budget whose identity comes from the governed
  methodology or frozen campaign protocol. P1 does not duplicate that numeric
  limit. Post-OOS tuning in the same lineage is prohibited.
- A new attempt is required for original execution, replication, data refresh,
  methodology rerun, pre-PnL protocol/mechanics/parameter declaration, or
  authorized rescue.
- A “rerun” is a new attempt under the same frozen protocol. It is never another
  run on an old attempt.
- A methodology rerun adopts a distinguishable methodology identity or an
  explicitly governed validation-window change.
- An implementation correction stays in the same variant only before PnL and
  uses a new attempt. After PnL, a semantic mechanics change requires a new
  variant or research generation.
- A new causal mechanism, counterparty, information timeline, or transfer
  mechanism is a new hypothesis. A new name is not.

An `authorized_rescue` exists only when a bounded rescue budget was explicit and
frozen before the relevant results were observed. Missing or exhausted budget
prohibits rescue. Each rescue has a new attempt identity; rescue history is
immutable; naming changes cannot reset budget or history; and rescue cannot
reopen/redefine consumed OOS or change the economic hypothesis in the same
lineage. These rules make retry-until-`PASS` structurally unavailable without P1
hard-coding a methodology-specific count.

Accepted hypotheses, published configs, attempts, runs, searched parameter
spaces, approvals, verdicts, reviews, and abandonment/revisit decisions remain
immutable. Renaming cannot reset budgets, failures, or consumed holdouts.

A limited core-grid, monkey, WFA, Monte Carlo, or acceptance `FAIL` terminates
the bound attempt or variant path. It does not automatically set the campaign to
`EXHAUSTED` while a governed, materially distinct successor remains authorized
and no campaign-level stop rule applies. Conversely, when a predeclared
campaign-level condition is satisfied, AlphaQuest stops the campaign even if an
individual stage outcome alone would not have done so.

## Abandonment and revisit

### Individual campaign

Campaign termination has two paths:

1. **Deterministic stop/exhaustion.** AlphaQuest automatically sets disposition
   `EXHAUSTED` and blocks further attempts only when a predeclared campaign-level
   objective condition is satisfied. Conditions include exhausting the identified
   governed variant, campaign research/search, or fresh-holdout budget;
   campaign-wide opportunity-frequency infeasibility; data/fidelity unavailable
   for the campaign; execution infeasibility applying to the hypothesis or
   mechanical family; or another explicit predeclared campaign-level termination
   contract. A single limited core-grid, monkey, WFA, Monte Carlo, or acceptance
   failure is not such a condition when authorized variant budget remains. A
   valid campaign-level stop requires no human approval click.
2. **Discretionary abandonment.** The human records `ABANDONED` when interpretation
   is required—for example, evaluating materially distinct expressions,
   contradictory causal evidence, unstable neighborhoods, or whether further
   research spending is warranted.

Both paths record the exact reason and bound evidence, block new attempts without
a governed revisit, remove the campaign from active execution surfaces, and
preserve every ledger entry, definition, attempt, run, search, and verdict.

### Edge family

One campaign `FAIL` or `EXHAUSTED` disposition does not prove a family false. The
human-owned family decision considers
whether failed expressions are genuinely independent, whether they test the
same causal mechanism, sample adequacy, data and execution fidelity,
contradictory evidence, external support, and consumed budget/holdouts. Cosmetic
or nearby-parameter failures count as one expression.

Possible dispositions are `CONTINUE`, `LOWER_PRIORITY`, `SUSPEND`, `ABANDON`,
and `REVISITABLE`. Data or execution defects generally support `SUSPEND` or
`REVISITABLE`, not a false scientific conclusion. Repeated adequate independent
failures of the same causal mechanism support `ABANDON`.

### Legitimate revisit

A revisit preserves and links prior failure, requires human approval and a new
lineage identity, and needs a materially new dataset, substantially longer
sample, justified instrument transfer, market-structure change, new execution
data, corrected engine bug, independent academic/exchange evidence, or a
materially different causal mechanism.

“Close result,” threshold tweaking, relabeling, more parameters, reopening
failed OOS, or retry-until-pass are invalid reasons. The revisit record binds the
old lineage, material trigger, new identity, fresh budget, and fresh holdout
plan.

## Change governance

### Methodology

A semantic methodology change includes stage order, decision roles, numerical
gates or floors, sampling/holdout policy, fill causality, promotion rules,
verdict semantics, or artifact lineage. Spelling, explanatory links, and
formatting can be classified non-semantic, but their byte hash still changes and
must be deliberately reviewed.

Codex or the human may propose a change; the human approves it. Semantic changes
increment the methodology version, change the policy hash, add focused tests and
an ADR where causality/stages/lineage change, and run methodology, causal, and
full validation. Old research remains historical evidence under the old
identity. New research uses the new identity. Only research needing a current
decision under the new policy gets an explicit methodology-rerun attempt.

### Data

Every changed dataset byte or semantic contract has a distinguishable hash. Old
results are not destroyed; they remain evidence for the old dataset.

| Change | Identity and rerun | Human/certification consequence |
| --- | --- | --- |
| More rows, same certified source contract | automatic capture, validation, and new content/data identity; no automatic rerun | no human needed to ingest/version; frozen-campaign rebind, locked-boundary change, or new evidence claim remains governed |
| New instrument | new identity and justified new campaign/transfer generation | human review; recertify if support/execution changes |
| Vendor/source change | new identity and data-refresh attempt | human review; recertify if source semantics affect execution |
| Roll methodology | new identity; data or methodology rerun as classified | human review |
| Timestamp repair | new identity; rerun current claims | human review; recertify if availability/entry timing changes |
| Aggressor classification | new identity; rerun dependent results | human review and dependent event-strategy recertification |
| Normalization change | new identity; rerun dependent results | human review; recertify if semantics change |
| New fields | new identity; rerun users of new/recomputed fields | semantics/availability review and dependent logic certification |
| Corrupt-data repair | new identity; rerun current claims | human review |
| Session definition | new identity; rerun dependent results | human review and session-dependent certification |

Routine append is automatic only when vendor/source, schema, normalization,
session, timestamp, roll, and field semantics are unchanged. It preserves the
old dataset and evidence identities. Appended rows cannot silently enter a frozen
OOS, holdout, attempt, run, or evidence binding. Uncertain equivalence is material
and fail-closed.

### Implementation

| Change | Certification/approval | Results and forward consequence |
| --- | --- | --- |
| Comment/docs only | unchanged only if execution bytes and declared files are unchanged | no rerun; all bound hashes must remain current |
| Proven behavior-identical refactor | new byte identity and fresh certification with approved equivalence evidence | old evidence may remain admissible through explicit equivalence lineage; mechanics may remain current or be re-bound; forward may continue |
| Behavior-unchanged bug fix | same proven-equivalence path only when an approved standard establishes unchanged relevant behavior | same conditional evidence reuse and forward continuity |
| Behavior-changing bug fix | new version review, recertification, mechanics approval | new attempt/variant as scope dictates; restart forward from a new candidate |
| Performance-only optimization | same proven-equivalence path; new hash and fresh certification always | no unconditional full scientific rerun after approved equivalence; deployment remains blocked until certification/bindings are current |
| Mechanics change | new version/certification/approval | old results cannot support new mechanics; new variant/generation and attempt; restart forward |
| Dependency semantic change | new hash/version review/certification/approval | old environment evidence preserved; new current evidence and forward path required |

There are two paths. Semantic, failed-equivalence, or uncertain changes stale
certification and mechanics approval, require new evidence as appropriate, and
block forward/deployment currentness. A proven non-semantic path exists only
when an approved deterministic equivalence standard demonstrates unchanged
relevant behavior and records old-to-new lineage. P1 does not claim that this
equivalence-certification capability exists yet. Until it does, the conservative
semantic/uncertain path applies.

## Invalidation cascades

Invalidation makes current use fail closed. It never mutates historical
artifacts.

```text
strategy source change
  -> implementation identity changes
  -> certification stale
  -> classify with an approved deterministic equivalence standard
  -> semantic, failed, or uncertain equivalence stales approval/candidate/forward
  -> execution and promotion blocked until classification/certification are current

proven non-semantic implementation change
  -> fresh certification plus old-to-new equivalence lineage
  -> historical evidence may remain admissible
  -> mechanics approval may remain current or be mechanically re-bound
  -> forward incubation may continue without automatic restart
  -> deployment blocked until certification and all bindings are current

methodology change
  -> old evidence remains valid under old methodology
  -> new research binds new version/hash
  -> selected current decisions use explicit methodology-rerun attempts

material data change
  -> new dataset identity/hash
  -> old results remain bound to old dataset
  -> new claims use data-refresh or new-campaign lineage
  -> approval/candidate bindings do not carry forward

config or parameter change
  -> new config hash
  -> mechanics approval stale
  -> unused new attempt required
  -> candidate, forward, and deployment bindings stale

account profile change
  -> old exact-profile assessment remains historical
  -> new assessment required
  -> dependent deployment package stale
  -> scientific state unchanged

live risk or allocation change
  -> new deployment package and human authorization
  -> old live instance paused or retired
  -> research result unchanged
```

## Human workload

The human reviews high-information or high-irreversibility boundaries, not
deterministic plumbing.

| Automatic | Codex-assisted | Human approval required |
| --- | --- | --- |
| hashes, schemas, identities | source discovery | source/hypothesis admission |
| certification currentness | hypothesis/mechanics proposals | mechanics interpretation |
| preflight and stage gates | authorized code/tests | locked acceptance OOS opening |
| objective campaign exhaustion | evidence and failure summaries | candidate disposition after separate red-team task |
| WFA/OOS/Monte Carlo | separate red-team analysis | forward start/review |
| account/portfolio calculations | review-package preparation | portfolio disposition |
| canonical forward capture/eligibility | forward evidence summaries | deployment, mode, sizing, risk |
| same-contract data append/versioning | forward/live diagnostics | frozen campaign rebind or locked-boundary change |
| stale-approval invalidation | forward/live diagnostics | semantic methodology/data/code changes |
| monitoring alerts/safety pause | | retirement or re-enablement |
| | | discretionary abandonment, edge-family disposition, revisit |

## Non-negotiable shortcuts

The following paths do not exist:

```text
historical PASS -> live
account suitability PASS -> scientific PASS
account suitability PASS -> Candidate Strategy
historical OOS -> forward observation
external event source -> canonical evidence ownership
same-contract appended rows -> frozen OOS/holdout expansion
candidate -> deployment authorization
human approval -> override missing objective evidence
Codex proposal -> approval
live success or failure -> rewritten historical research
```

Validate the canonical policy without running research:

```bash
PYTHONPATH=src python3 -m alphaquest.research.operating_model
PYTHONPATH=src python3 -m pytest -q tests/test_research_operating_model.py
```
