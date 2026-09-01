# AlphaQuest Research Operating Model

Status: canonical P1 policy

Operating-model policy: `2026-09-01.1`

Engine contract: `2026.08.14.1` (unchanged)

Methodology: `2026-08-14.2` (unchanged)

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
lane. The policy labels each transition as `existing`, `existing_partial`, or
`policy_only`. A policy-only transition is a future enforcement contract, not a
claim that runtime orchestration exists today.

The policy has its own version and byte hash. It is separate from methodology.
Changing P1 definitions does not silently change historical gate thresholds or
rebind old results. A semantic operating-model change requires a new policy
version. A semantic methodology change still follows the independently versioned
methodology process.

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
- independent candidate review after a qualifying historical result;
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
4. Registry `candidate` is a navigation projection after independent candidate
   review. It does not mean deployable or tradeable.
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

Compatibility values remain readable and unchanged. P1 normalizes their axis:

| Current term | Canonical interpretation | Preserved meaning |
| --- | --- | --- |
| registry `active` | lifecycle navigation plus active disposition | no terminal campaign decision |
| registry `review_queue` | blocked disposition | missing, ambiguous, or pending evidence |
| registry `candidate` | historical-candidate-review stage | independently reviewed candidate only |
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
  -> portfolio candidate -> account-suitability assessment
  -> deployment package -> live strategy instance
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
| Candidate strategy | Historically supported result with independent review | Immutable review; currentness recomputed; human owner | candidate review, result, mechanics approval, independent reviewer |
| Forward plan | Frozen true-forward duration, sample, and abandonment contract | Immutable plan plus append-only events; human owner | candidate/config/objective hashes and start time |
| Forward observation | Genuinely later paper, shadow, or market evidence | Append-only; external observation source | event chain, timestamp, attachment and reconciliation |
| Portfolio candidate | Forward-reviewed candidate eligible for interaction analysis | Immutable input binding; human owner | current candidate, forward journal, acceptance-OOS inputs |
| Account-suitability assessment | Exact-profile rule and payoff result | Immutable; deterministic-engine owner | profile/version/hash, trades, costs, seeds, attestations |
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
-> HISTORICAL_CANDIDATE_REVIEW
-> FORWARD_INCUBATION
-> FORWARD_REVIEW
-> PORTFOLIO_REVIEW
-> ACCOUNT_SUITABILITY_REVIEW
-> DEPLOYMENT_REVIEW
-> SHADOW -> SMALL_LIVE -> LIVE
-> MONITORING
```

Account assessment may currently be computed earlier, after scientific `PASS`,
to support a destination-specific candidate review. That is an operation on the
account-suitability axis, not a shortcut in lifecycle stage. It still cannot
create scientific validity or deployment authorization.

Lifecycle disposition is independent: `ACTIVE`, `BLOCKED`, `ABANDONED`,
`PAUSED`, `RETIRED`, or `SUPERSEDED`. `ABANDONED` and `RETIRED` are terminal for
that object lineage. `PAUSED` is reversible. `SUPERSEDED` preserves the old
lineage while naming a newer one.

### Independent decision axes

- Scientific: `NOT_EVALUATED`, `EVALUATING`, `PASS`, `FAIL`, or
  `NEEDS_MANUAL_REVIEW`.
- Implementation: `NOT_IMPLEMENTED`, `DEVELOPMENT`, `AWAITING_CERTIFICATION`,
  `CERTIFIED_CURRENT`, `CERTIFICATION_STALE`, `DEPRECATED`, `RETIRED`, or
  `QUARANTINED`.
- Forward: `NOT_STARTED`, `ACTIVE`, `ELIGIBLE_FOR_REVIEW`, `FAILED`, `RETIRED`,
  or `NEEDS_MANUAL_REVIEW`.
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
  They do not approve research or deployment.

### Transition authority matrix

“Automatic” means AlphaQuest owns the result once all inputs exist. It never
means that Codex may invent inputs.

| Transition | Initiator | AlphaQuest facts | Human gate | Codex authority | Reversible |
| --- | --- | --- | --- | --- | --- |
| Record research lead | Codex or human task | schema/no mutation | no | unverified proposal only | no; supersede instead |
| Admit hypothesis | human | fields, hashes, duplicate review | required | propose only | no |
| Start bounded implementation | human-scoped task | catalog/handoff and information boundary | admission already required | implement approved scope | yes before freeze |
| Submit mechanics | Codex or engineer | tests, certification, lane evidence | no | prepare only | yes |
| Approve mechanics | human | all checks/sample/current hashes | required | prohibited | no; stale on change |
| Run historical screening/stages | AlphaQuest | preflight, stages, one-run-per-attempt | no trivial click | request an authored run only | no |
| Open locked acceptance OOS | human | all prior gates, unopened holdout, frozen identities | required | prohibited | no |
| Record historical verdict | AlphaQuest | recomputation and artifact integrity | no | cannot decide | no |
| Approve historical candidate | independent human role | eligibility, hashes, reviewer separation | required | cannot approve | no; may stale |
| Start forward incubation | human | current candidate, plan, start time | required | prohibited | no |
| Append forward observation | external/human capture | chronology, hashes, reconciliation | no per-event approval after confirmation | summarize only | no |
| Mark forward eligible | AlphaQuest | days, trades, no failure | no | cannot decide | no; later failure can block |
| Accept forward review | human | current journal and thresholds | required | cannot approve | no |
| Create portfolio review | AlphaQuest | exact OOS inputs and statistics | no | interpret only | no |
| Record portfolio disposition | human | current inputs | required | propose only | no |
| Assess account suitability | AlphaQuest | scientific `PASS`, profile, rules, simulations | attestations only when external facts require them | request/summarize only | no |
| Authorize deployment | human | all prerequisites, limits, separation | required | prohibited | authorization can be withdrawn |
| Shadow -> small live -> live | human | current monitoring, limits, authorization | required at each mode change | prohibited | can pause/roll back |
| Append monitoring | external/AlphaQuest | chronology, thresholds, alerts | no per-period approval | analyze only | no |
| Safety pause | AlphaQuest | predeclared hard rule | no | cannot override | yes after human review |
| Retire/re-enable | human | instance and evidence identity | required | cannot decide | retirement terminal; re-enable uses new authorization |
| Abandon/revisit | human | complete lineage and allowed trigger | required | propose only | abandonment preserved; revisit is new lineage |

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
data or implementation changes, abandonment/revisit, and retirement or
re-enablement.

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
gates, WFA selection, stitched OOS, Monte Carlo, sample/calendar sufficiency,
one-run-per-attempt, legal prerequisites, artifact immutability, stale approval
invalidation, forward chronology, portfolio statistics, account rules,
allocation limits, and monitoring/safety rules.

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
   separately recorded adversarial task before candidate approval. Red-team
   findings are advisory until a human disposition.
4. Historical validation and forward incubation are separate. Forward events
   must be later than the immutable start, strictly ordered, and content
   addressed. Historical OOS cannot be uploaded as forward evidence.
5. Scientific validity and account suitability are separate. Account
   assessment requires scientific `PASS` and writes only the account axis.
6. Candidate and deployment authorization are separate. A candidate supplies
   evidence but no execution authority.
7. Live observation and research are separate. Live facts may seed a new
   observation or hypothesis but never mutate old lineage.

The repository already enforces distinct recorded identities between mechanics,
candidate, and deployment reviewers. P1 additionally requires a separate
red-team task. It does not add trivial human confirmations to deterministic
checks.

## Attempt and search governance

The immutable hierarchy remains `edge family -> hypothesis -> campaign ->
variant -> attempt -> run`.

- A new variant is a materially distinct, value-independent expression of the
  same accepted edge. It requires the immediately prior variant's current
  mechanics approval and terminal scientific `FAIL`, remains within the
  five-variant maximum, and cannot use post-OOS evidence for tuning.
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

Accepted hypotheses, published configs, attempts, runs, searched parameter
spaces, approvals, verdicts, reviews, and abandonment/revisit decisions remain
immutable. Renaming cannot reset budgets, failures, or consumed holdouts.

## Abandonment and revisit

### Individual campaign

Campaign abandonment is supported when current evidence shows insufficient
opportunity frequency, broad core-grid unprofitability, unstable parameter
neighborhoods, unrealistic execution dependence, inadequate attainable sample,
failure across materially different valid expressions, contradiction of the
economic claim, unavailable fidelity, repeated robustness/unseen failure, or
exhausted budget/fresh holdouts.

Abandonment blocks new attempts without a revisit decision, removes the campaign
from active execution surfaces, and records actor, time, reason, and evidence
hashes. It never deletes ledger entries, definitions, attempts, runs, or
verdicts.

### Edge family

One campaign `FAIL` does not prove a family false. The family decision considers
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
| More rows, same source contract | new dataset version/hash; explicit data-refresh attempt for new evidence | review coverage and holdout effect; recertify only if semantics changed |
| New instrument | new identity and justified new campaign/transfer generation | human review; recertify if support/execution changes |
| Vendor/source change | new identity and data-refresh attempt | human review; recertify if source semantics affect execution |
| Roll methodology | new identity; data or methodology rerun as classified | human review |
| Timestamp repair | new identity; rerun current claims | human review; recertify if availability/entry timing changes |
| Aggressor classification | new identity; rerun dependent results | human review and dependent event-strategy recertification |
| Normalization change | new identity; rerun dependent results | human review; recertify if semantics change |
| New fields | new identity; rerun users of new/recomputed fields | semantics/availability review and dependent logic certification |
| Corrupt-data repair | new identity; rerun current claims | human review |
| Session definition | new identity; rerun dependent results | human review and session-dependent certification |

Uncertain equivalence is material and fail-closed.

### Implementation

| Change | Certification/approval | Results and forward consequence |
| --- | --- | --- |
| Comment/docs only | unchanged only if execution bytes and declared files are unchanged | no rerun; all bound hashes must remain current |
| Proven behavior-identical refactor | new implementation hash; stale then recertify after parity/tests; fresh mechanics approval | old results remain old-identity evidence; new attempt for current evidence; forward path stale |
| Behavior-unchanged bug fix | same fail-closed treatment as refactor | same as refactor |
| Behavior-changing bug fix | new version review, recertification, mechanics approval | new attempt/variant as scope dictates; restart forward from a new candidate |
| Performance-only optimization | new hash, parity proof, recertification, approval | new attempt for current evidence; old evidence preserved |
| Mechanics change | new version/certification/approval | old results cannot support new mechanics; new variant/generation and attempt; restart forward |
| Dependency semantic change | new hash/version review/certification/approval | old environment evidence preserved; new current evidence and forward path required |

The default is semantic change when equivalence is uncertain.

## Invalidation cascades

Invalidation makes current use fail closed. It never mutates historical
artifacts.

```text
strategy source change
  -> implementation identity changes
  -> certification stale
  -> mechanics approval stale
  -> candidate and forward currentness fail
  -> execution and promotion blocked

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
| WFA/OOS/Monte Carlo | evidence and failure summaries | candidate/red-team disposition |
| account/portfolio calculations | separate red-team analysis | forward start/review |
| forward chronology/eligibility | review-package preparation | portfolio disposition |
| stale-approval invalidation | forward/live diagnostics | deployment, mode, sizing, risk |
| monitoring alerts/safety pause | | semantic methodology/data/code changes |
| | | abandonment, revisit, retirement, re-enablement |

## Non-negotiable shortcuts

The following paths do not exist:

```text
historical PASS -> live
account suitability PASS -> scientific PASS
historical OOS -> forward observation
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
