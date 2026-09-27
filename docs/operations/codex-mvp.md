# Codex research MVP and development skips

The owner changed development scope on 2026-09-27: skip any development stopped
by the platform vulnerability-research safeguard, skip its dependent developments,
record the repercussions, and prioritize end-to-end research through Codex with
minimal human input. This is a scope reduction, not an audit waiver.

The machine-readable development record is
[`config/development_roadmap.json`](../../config/development_roadmap.json).
It is separate from scientific campaign results and `research_ledger.csv`.
Historical P3–P17 phase records remain preserved. The new scope does not complete
those phases or promote their qualification state.

## What is skipped

| Development | Why it is skipped | Repercussion |
| --- | --- | --- |
| Independent review of frozen recorder attempt004, including the static follow-up | Both review attempts terminated with the platform cybersecurity-risk flag and produced no final report | The recorder remains unaccepted; no conclusion about its correctness is established |
| Root acceptance of that recorder | Requires the missing independent report | No accepted recorder source |
| Executor release and actual bounded owner attempt through that recorder | Require accepted recorder source | No recorder-mediated owner execution or current-gate evidence |
| Four final evidence reviews and their consolidation | Require actual execution evidence | No execution-evidence acceptance |
| Recorder-mediated final package and P3 qualification | Require the preceding acceptance chain | Zero gate credit; no P3 completion claim |
| Original P4–P15 and P17 qualification milestones that transitively require P3 completion | Their original sequencing requires that qualification | Full master-roadmap qualification is outside the current MVP completion claim |

The JSON record lists each original downstream qualification milestone separately
with its dependencies and repercussions. Existing product capabilities with no
dependency on the recorder remain eligible for MVP development. The previously
accepted five corrections and completed PR10 equivalence qualification remain
accepted within their original scope. PR10 is a pull request, not roadmap phase P10.

P16 data governance is cross-cutting and has no recorder dependency; it remains
eligible for development. Its original phase status is still `NOT_STARTED`.

The original interruption, candidates, failed reviews, and prepared support request
remain historical evidence. No support request is needed to continue independent
MVP work. Do not retry the flagged work under a different name or approve it by
omitting the blocked review.

## Existing usable workflow

The current product already provides a local Codex proposal worker, typed source
and hypothesis reviews, Studio campaign authoring and publication, mechanics
validation and approval, staged research runs, and finalized reports. See the
[Studio guide](../getting-started/research-studio.md).

The local Codex worker uses subscription authentication. The paid API provider is
outside this work's authorization. Proposal output is `VALIDATED_NOT_APPLIED`;
receiving a proposal does not publish a campaign or grant scientific approval.

An independently verified source supplied through the existing human review path
can support real research under that path's own rules. It is not a recorder-qualified
P3 dossier. Synthetic fixtures may demonstrate engineering behavior but cannot
establish a real scientific result or qualify an upstream source.

## Twelve-hour delivery contract

The owner's subsequent deadline is 2026-09-27 19:04 UTC / 2026-09-28 03:04
Singapore. The target is one supervised end-to-end research workflow operated by
Codex, ending in a **diagnostic pre-acceptance** research report. It is not a fully
autonomous factory or a qualified trading candidate.

Include exactly one instrument, one compatible existing local dataset, one suitable
existing certified strategy lane, and one predeclared variant. Prefer ES if the
approved hypothesis, available data and certified implementation fit it; do not
change the economic hypothesis merely to fit a convenient package. Fixed default
parameters are valid when declared before testing. Never choose the case from PnL.

Codex prepares the research and authoring inputs, presents compact owner review
packs, calls existing services after actual authorization, runs the approved stages,
and explains the diagnostic report. Source verification, implementation admission,
mechanics scope and sampled mechanics approval remain explicit decisions. Group
related questions into a review pack without merging their distinct approvals.

Use the existing campaign CLI's `--no-acceptance` route. Do not use a worker route
that unconditionally schedules acceptance. Locked acceptance data, its missing
canonical authorization bridge, candidate promotion and trading readiness are
outside this timebox. This no-acceptance route always has overall verdict
`NEEDS MANUAL REVIEW`, including when a stage fails. Preserve those failed-stage
outcomes without promoting them to a terminal scientific `FAIL` or `PASS`.
A profitable strategy is not a condition for a successful workflow demonstration.

The campaign CLI writes a stage summary and stage reports; it does not finalize a
`ResultBundleV2`. Codex will produce a separate diagnostic report/index referencing
those exact outputs and their input identities. This report is the MVP deliverable,
not a canonical finalized bundle. Canonical finalization is deferred.

| Elapsed time | Deliverable |
| --- | --- |
| 0–1 hour | Resolve the authoritative integration base; confirm certified lane, local data and owner review path; freeze the exact slice |
| 1–4 hours | Codex-operated runbook and review packs using existing CLI/API/Studio services; only fixes essential to this slice |
| 4–7 hours | Isolated end-to-end fixture demonstration, including approval stops, stale-input rejection and the diagnostic report/index |
| 7–10 hours | Demonstrate the unverified user-supplied case if the inputs and actual owner decisions are available; otherwise disclose the unmet prerequisite and retain the synthetic engineering demonstration |
| 10–12 hours | Fresh independent review, essential fixes, final rerun and concise handoff |

Definition of done: the chosen input reaches an evidence-bound report through
existing governed stages; Codex can explain every step and stop at each human gate;
failures and skips remain visible; rerunning cannot silently overwrite the prior
attempt. Synthetic results are always labelled synthetic and confer no scientific
approval. An unverified user-supplied demonstration is conditional on actual source/data readiness
and owner decisions, not the clock.

Engineering acceptance also requires fresh independent reviews of the frozen
candidate, full local validation after those reviews accept it, and the required
checks on the exact pull-request head. A passing older candidate or a successful
synthetic run does not satisfy those gates for a changed candidate. Keep the
delivery status separate from the diagnostic research verdict.

Deferred by the timebox, **not** by a safeguard:

- Automatic reviewed-research-to-draft/admission and certified-mechanics compilers.
- General frequency/data routing, downloading new data, and paid integrations.
- A persistent automatic transition driver or new UI/dashboard.
- Canonical locked-holdout authorization, acceptance continuation and ResultBundleV2 finalization.
- New custom strategy packages, more variants, and wider instrument coverage.

These cuts reuse the already implemented supervised path. They do not waive any
scientific gate or grant an old proposal the status of an implementation admission.
If an essential development actually triggers the platform safeguard, apply the
skip policy and stop that dependent route; do not rename it into the MVP.

## Human decisions

Codex can prepare compact review packs and execute already authorized mechanical
steps. The owner still supplies or confirms the objective, verifies source content
and claims, admits the hypothesis, resolves substantive duplicate ambiguity,
confirms the mechanics scope, reviews the deterministic mechanics sample, and
authorizes use of locked acceptance data. Missing data and unsupported mechanics
can introduce additional decisions. Never combine these decisions into an implied
blanket approval.

For this MVP, the initial review pack must distinguish source verification,
hypothesis admission, exact implementation admission, dataset and execution-cost
acceptance, and the duplicate decision. Mechanics approval follows generated
evidence and is a separate decision. Locked acceptance remains deferred.

## Recording another safeguard skip

Add or update the exact development unit with its actual trigger and evidence
reference. Include all real dependency edges and explain the effect of losing that
unit. The report must propagate the skip through every descendant, including a
previously implemented descendant whose new qualification needs the skipped work.
Preserve its historical implementation status separately.

Inspect the resolved development graph before choosing the next unit:

```bash
alphaquest factory development-status --project-root . --json
alphaquest factory development-status --project-root . --check-unit mvp_research_admission_bridge
```

The second command checks whether a unit is in scope. It does not certify that its
prerequisites are complete or authorize research execution. Skipped, deferred,
unknown, or invalid units produce a nonzero exit status. The command reads only the
roadmap; it does not open its evidence references or start a worker.
The v1 roadmap supports up to 256 units, dependency chains of up to 64 units, and
4096 resolved skip chains per unit. Larger inputs fail explicitly.

Work that is merely incomplete stays planned; deliberately postponed scope stays
deferred. Neither is a platform safeguard event. A newly proposed alternative is
eligible only if it is actually independent and does not reuse the unaccepted
artifact or claim its missing assurances.

MVP readiness remains **NEEDS MANUAL REVIEW** until the complete path and its
required evidence are demonstrated. Engineering checks are not trading readiness.

## Supervised diagnostic runbook

Use this sequence for one already admitted, published campaign. The commands do
not replace source verification, typed hypothesis review, duplicate review, or
implementation admission. Those decisions must already have been made through
the governed human workflow and remain separately reviewable.

1. Freeze the exact campaign, variant, dataset manifest, source config, and
   attempt identity. Work from the selected project's root directory. Published
   `raw_csv`, `raw_parquet`, output, and evidence paths may be relative to that
   root, so launching the runner from the code checkout can point at the wrong
   data even when preflight passed for the project.
2. Run the separate configuration/data preflight and save its JSON receipt.
   Require `passed: true`, no failures, and the exact frozen config path. The
   `--skip-tests` flag is intentional: repository engineering tests are a
   separate integration/CI gate and should not be recursively launched from
   every disposable research project. Create the diagnostics directory first,
   and require a fresh receipt path so shell redirection cannot replace prior
   evidence. Pin the exact AlphaQuest source checkout and pass the isolated
   project root explicitly; the campaign CLI wrapper otherwise validates against
   the source checkout's project root.

   ```bash
   mkdir -p research_artifacts/mvp_diagnostics
   (
     set -C
     PYTHONPATH=/ABSOLUTE/PATH/TO/ALPHAQUEST/src \
     python -m alphaquest.research.preflight \
       --project-root /ABSOLUTE/PATH/TO/PROJECT \
       --config research/campaigns/active/CAMPAIGN_ID/variants/VARIANT_ID/config.yaml \
       --skip-tests --json \
       > research_artifacts/mvp_diagnostics/ATTEMPT-preflight.json
   )
   ```

   The receipt must say `tests_ran: false`. Run and record the repository's
   applicable engineering checks before integrating code changes; never rewrite
   this receipt to imply those tests ran inside the project preflight.

3. Generate the deterministic mechanics evidence for the frozen variant:

   ```bash
   PYTHONPATH=/ABSOLUTE/PATH/TO/ALPHAQUEST/src \
   python -m alphaquest.cli campaign validate-mechanics CAMPAIGN_ID \
     --variant VARIANT_ID --campaign-root research/campaigns/active
   ```

   A human reviewer must inspect the five deterministic chart samples and all
   required risk cases, record the review annotations, and use the existing
   `MechanicsApprovalService` workflow in Studio. Before any PnL-bearing stage,
   its inspection must report exactly `APPROVED_FOR_TESTING`, with hashes matching
   the frozen source config and input data. Codex may prepare the review pack; it
   cannot make or simulate this decision on an owner-authorized run.
4. From that same project root, run the existing stage module with acceptance
   omitted. Use an absent result-copy path for this attempt:

   ```bash
   test ! -e research_artifacts/mvp_diagnostics/ATTEMPT-stage-summary.json && \
   PYTHONPATH=/ABSOLUTE/PATH/TO/ALPHAQUEST/src \
   python -m alphaquest.run_campaign_stages \
     --config research/campaigns/active/CAMPAIGN_ID/variants/VARIANT_ID/config.yaml \
     --no-acceptance \
     --result-json research_artifacts/mvp_diagnostics/ATTEMPT-stage-summary.json
   ```

   Do not pass `--skip-validation` or `--fast-runtime-defaults`. The diagnostic
   stage module replaces its `--result-json` target, so the explicit absent-path
   check is mandatory for each new attempt. The diagnostic
   reason intentionally lets later pre-acceptance stages run after an earlier
   failure when their own dependencies permit it. Preserve every actual `passed`,
   `failed`, `error`, and `skipped` outcome. The module returns process status 0
   after writing a valid diagnostic summary whose research verdict is
   `NEEDS MANUAL REVIEW`; the `alphaquest campaign run --no-acceptance` wrapper
   instead returns status 1 because its summary's `passed` field is necessarily
   false. Neither status is a scientific verdict.
5. Build the separate, immutable diagnostic index after the run completes:

   ```bash
   PYTHONPATH=/ABSOLUTE/PATH/TO/ALPHAQUEST/src \
   python -m alphaquest.run_mvp_diagnostic \
     --project-root /ABSOLUTE/PATH/TO/PROJECT \
     --run-dir research/evidence/runs/CAMPAIGN_ID/VARIANT_ID/SYMBOL/RUN_ID \
     --preflight-receipt research_artifacts/mvp_diagnostics/ATTEMPT-preflight.json \
     --output research_artifacts/mvp_diagnostics/ATTEMPT-index.json \
     --mode unverified
   ```

   The generator only reads completed evidence and creates the one standalone
   index with exclusive-create semantics. It refuses an output inside the run
   directory. It requires the full pre-acceptance stage order; the separate and
   embedded successful configuration/data preflight receipts for exactly that one
   config and data source; the canonical effective config derived from the exact
   published source; the complete one-variant certified-recipe publication and its
   shared hypothesis, rationale, execution and prop-profile semantics; the
   producer's complete run/manifest fields and canonical results-index entry;
   criteria derived from repository policy and the frozen research objectives,
   with their outcomes recomputed by the producer evaluator; exact stage-specific payloads;
   the selected input hash and frozen parameter grids; retained data-quality
   fields; and the complete engine execution assumptions found in canonical and
   referenced stage artifacts. It also requires the recorded approved mechanics
   gate. It runs the existing read-only technical gate inspector against the exact
   source config and canonical input, compares that report with the gate embedded
   in the run summary, validates the retained bar-lane metadata and its exact
   seven-file artifact map and Parquet record counts, and then uses the shared
   read-only mechanics planner against the retained trades, checks and transitions.
   The approval must exactly match the planner's
   sampling policy, ordered categories, canonical trade IDs, reasons, config and
   data identity, and every sampled trade must have exactly one retained `Correct`
   annotation with non-empty notes. Reviewer and timestamp are preserved as
   recorded fields. The selected input must be one local CSV or
   Parquet bar dataset with a `PASS`
   quality manifest whose execution metadata matches the frozen config and strategy
   specification; and the sole diagnostic reason that acceptance was omitted. It
   validates and hashes every stage-referenced artifact. The staged run did not
   record a historical dataset-manifest file hash, so the index says that explicitly:
   it validates the current manifest against the frozen config and published
   strategy-spec metadata without claiming those manifest bytes existed at run time.
   The inspector and planner checks establish technical and internal evidence
   coherence. They do not authenticate the reviewer, prove that chart inspection
   occurred, confer owner authority, or independently revalidate the human
   approval decision; those assurances remain false in the index.
   Event and multifile sources require a separate binding design and fail closed.
   The index retains raw
   stage failures and always reports `NEEDS MANUAL REVIEW`. It does not run stages,
   grant admission or approval, write a `ResultBundleV2`, promote a candidate, or
   establish source-review assurance.

   The publication must match its declared compiler schema, including the exact
   authoring-manifest fields. The fixed-default replay's engine configuration hash
   must identify the complete effective config, and its subordinate metrics must
   match the canonical replay. Core and WFA stage grids must agree with the
   published parameter space; a stage override cannot introduce another grid.
   Realized optimized WFA windows require complete selected parameters, and each
   OOS trade must match its window's selection. The retained incubation selection
   must agree with the producer's deterministic selection from the WFA results.
   These are consistency checks on retained evidence, not an independent PnL
   recalculation or proof that a selection method has scientific approval.

   New producer run and stage timestamps use timezone-aware UTC. The index rejects
   timestamps without an offset, completion before start, or elapsed durations
   inconsistent with the serialized timestamps by more than `0.000001` seconds.
   Market and
   session timestamps continue to use the configured exchange timezone.

If a run reserves its attempt or writes partial/failure evidence, keep it. Do not
delete, repair, or silently replay the same attempt. Create a fresh governed
follow-up attempt with a new identity after resolving the cause. The report index
also refuses to overwrite a previous index.

If older evidence has ambiguous timestamps or fails a current contract check,
retain its original files and previous reports as historical evidence. Record the
reader's rejection separately and keep the research classification
`NEEDS MANUAL REVIEW`. Do not infer a missing offset from the current host, edit
old timestamps, or recompute historical verdicts to make the index accept them.
A new execution needs its own authorization and identity; a reader rejection alone
does not authorize another performance run. A separately authorized synthetic
demonstration can exercise a corrected producer using unchanged teaching inputs,
fresh simulated fixture-only review records, and explicit no-owner-authority labels.

For an isolated synthetic demonstration, use `--mode synthetic`. The index derives
its warning from explicit structured disclosures in the hash-bound campaign,
source config, approval reviewer and approval notes. It preserves every matched
field with the artifact path and hash. Source-synthetic and simulated-mechanics
warnings are separate: a synthetic dataset does not imply that a recorded human
review was simulated, and an explicitly simulated approval does not verify data
origin. A scripted duplicate/admission label is emitted only when the bound text
actually discloses that fact. Synthetic evidence can demonstrate stops,
stale-input rejection, attempt immutability, stage rejection, and report binding.
It cannot substitute for the real human decisions or support a scientific,
trading-readiness, P3, or promotion claim. For any user-supplied case whose origin
is not established by a separately audited provenance chain, use `--mode
unverified`. That mode never calls the data real and records data-origin,
source-review, implementation-admission, current mechanics-gate and human-authority
verification as false. Positive real-origin classification is outside this bounded
report. `--mode` is a consistency assertion, not the classification source. Any
accepted synthetic, simulated, fixture or no-owner-authority disclosure requires
`synthetic`, even if another field is edited or silent. `synthetic` is rejected when
no selected structured field contains such a disclosure. Historical contracts have
no universal typed origin field, so absence of a warning yields
`UNVERIFIED_ORIGIN`, never a positive real-data claim.
