# Structured research review

Studio uses the existing proposal, reviewed-artifact and mechanics-approval
contracts. A conversation, a checked box before submission, or a successful CI
run is not a saved research decision. Codex may prepare the evidence and carry
out already authorized work; the human supplies the substantive judgments.

## The same review sequence

1. Open **Workflow → Review Codex output**. Use **Recent proposals and saved
   reviews** to choose a pending proposal or reopen a recent recorded review.
   The selector covers the tasks currently returned in the recent-task list;
   it is not an archive browser.
2. Inspect **Exact proposal version**, the source/hypothesis/mechanics field
   values, conflicts and unresolved questions. Values are shown beside their
   acknowledgement controls; the complete validated JSON remains available.
3. Check each required field and criterion. Source review additionally requires
   captured document and accepted-claim hashes, a retraction check, a decision
   for every claim, and each claim's verification method and notes. A rejected
   claim stays in the record; at least one accepted claim is required to proceed.
4. Enter your reviewer identity and notes, then submit the specific acceptance
   action. The configured identity is a local attribution label, not an
   authenticated signature. A hash identifies content, not the human who read it.
5. Read **Saved review receipt**. It includes the decision, reviewer, timestamp,
   notes, proposal/validation/artifact hashes and the complete downloadable JSON
   artifact. Reopening the task retrieves the stored record through the existing
   verification service. Codex should read that record before resuming work.

If evidence is incomplete, leave the form pending. If the proposal should be
closed, use **Dismiss** with a rationale. Dismissal is a routing disposition,
not a scientific FAIL or permission to create a later campaign variant.
There is no new return-for-revision or approval contract: corrections use a new
proposal through the existing workflow, preserving the prior record. Changed
inputs must pass the existing freshness checks; prior acceptance is not copied.

If the save succeeds but refreshing the screen fails, the form says the review
was saved and disables resubmission. Reload Studio to retrieve the receipt.
If the request itself fails, Studio reads back the task and keeps submission
locked. A stored decision opens the receipt flow. An empty readback does not
prove the original write has finished, so it never enables another submission.
Use **Check saved review** to read the task again without issuing another write.
Before sending, a browser delivery marker retains the operation ID and exact
proposal version. It contains no decision or approval and requires working
browser storage. The service also admits one immutable delivery intent per task,
bound to that operation, the proposal/validation hashes, and the exact human
review. This coordinates tabs, browser profiles and the supported loopback
addresses. A task with an admitted delivery remains locked even in a browser
with no local marker.

The first decision **admitted by the service** owns the task. A browser click
whose request has not reached the service cannot reserve that ordering. Another
request may reach the service first; the recorded receipt identifies the actual
saved decision. Conflicting operations or changed human input are rejected.
An exact operation replay can return the original receipt or finish an
interrupted artifact write, retaining its original reviewer, timestamp and hash.
The transport intent itself never permits downstream research: only the existing
verified review artifact does. Existing historical reviews remain authoritative.

**Check saved review** only reads; it never automatically retries a mutation.
Only a successful service write response or a matching stored receipt clears the
local marker. Do not clear browser data to force a retry. If a crash leaves an
admitted intent without a review artifact, reconcile its exact operation and
submitted contents with the service; do not create a replacement decision. This
rare recovery remains an operator task. Empty or failed readback and integrity
errors stay blocked. The UI does not claim that a missing receipt proves failure.

## Decision scope

| Review | Existing record | What the decision permits |
| --- | --- | --- |
| Source verification | `ReviewedSourceEvidenceArtifactV1` with `SourceEvidenceHumanVerificationV1` | Hypothesis proposal using the accepted source claims |
| Hypothesis acceptance | `ReviewedHypothesisArtifactV1` with `HypothesisHumanAcceptanceV1` | Mechanics proposal for that economic hypothesis |
| Unsupported mechanics intent | `ReviewedEngineeringHandoffIntentArtifactV1` | A proposal-only engineering handoff; no implementation or certification |
| Manual mechanics review | `MechanicsApprovalService` and the existing approval JSON | Performance testing only after current evidence and every required sample pass |

Certified-lane mechanics intent still uses the existing human-transfer and
strict authoring/publication route. It is not accepted by the engineering-handoff
form. Source/hypothesis/handoff receipts do not publish a campaign or approve
mechanics, P&L, holdout access, candidate promotion or trading.

For mechanics, open **Reviews → Current mechanics**. An unreviewed trade starts
with no selected status. Check the deterministic five-trade sample (or all if
fewer) plus required risk cases against external charting software, explicitly
choose the status, and record the chart tool, timing observations and
reconciliation reference or discrepancy. Saved annotations are restored when
reopened. Final approval still uses the current config, data, implementation,
certification and sampling-policy bindings enforced by the existing service.

## Preparing the five initial owner decisions

Keep these decisions distinct even when presenting them in one review pack.
Use the following fixed headings for each: **decision requested**, **exact
subject and version**, **evidence**, **uncertainties**, **review criteria**,
**owner decision and rationale**, **stored record**, and **next permitted step**.
Codex fills the factual and evidence sections; unresolved judgments stay pending.

| Initial decision | Evidence to present | Existing route / boundary |
| --- | --- | --- |
| Source verification | Original captured source, metadata, claim locations, direct versus inferred support and contrary evidence | Structured source review above |
| Hypothesis admission | Full economic hypothesis, accepted source bindings, falsifiers, timeline, costs and unresolved questions | Structured hypothesis review above |
| Exact implementation admission | Proposed certified package/version, exact rules and parameter declaration, differences from the source | Explicit owner decision followed by existing strict authoring; hypothesis acceptance alone is insufficient |
| Dataset and execution costs | Exact manifest, coverage, gaps/blackouts and their impact, session/roll assumptions, fees and slippage | Existing dataset/execution authoring and validation; missing impact analysis stays pending |
| Duplicate disposition | Related campaigns, shared economic mechanism, differences, and rationale for distinct/duplicate classification | Existing duplicate review; renamed mechanics do not establish a distinct edge |

This UI improvement does not add the deferred automatic admission/compiler
bridge or turn the narrative real-case pack into typed accepted evidence.
The separate chart-based mechanics review remains required before real P&L.
