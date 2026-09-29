import { useEffect, useMemo, useState } from "react";
import { api, type ReviewDelivery, type SourceReviewReadiness } from "../api";
import type { CodexTaskRecord } from "../types";
import { ProposalValue } from "./FactoryReviewRecord";
import { Button, Notice } from "./UI";
import { CLAIM_VERIFICATION_METHODS, claimVerificationComplete, newClaimVerification,
  serializeClaimVerification, type ClaimVerification } from "../sourceClaimReview";

const SHA256 = /^[a-f0-9]{64}$/;
const SOURCE_METADATA_FIELDS = [
  "title",
  "authors",
  "year",
  "locator",
  "publication_type",
  "venue",
];
const HYPOTHESIS_FIELDS = [
  "hypothesis_id",
  "edge_family_id",
  "instrument",
  "market_behavior",
  "causal_mechanism",
  "counterparty",
  "information_availability_timeline",
  "expected_holding_horizon",
  "null_hypothesis",
  "falsifying_observations",
  "confounders",
  "persistence_rationale",
  "expected_regimes",
  "transaction_cost_sensitivity",
  "capacity_assumptions",
  "required_data_fields",
  "source_bundle_sha256s",
  "source_claim_ids",
  "research_objectives_sha256",
  "unresolved_questions",
];
const MECHANICS_FIELDS = [
  "mechanics_id",
  "hypothesis_id",
  "hypothesis_sha256",
  "variant_id",
  "execution_lane",
  "certified_strategy_id",
  "unsupported_reason",
  "signal_availability",
  "entry_state_machine",
  "entry_timing",
  "invalidation_condition",
  "stop_semantics",
  "target_and_exit_semantics",
  "session_boundaries",
  "reentry_policy",
  "position_limits",
  "required_data_fields",
  "parameters",
  "rationale",
];

const REVIEW_GUIDANCE: Record<string, string> = {
  objective_alignment: "Does this hypothesis answer the frozen research objective?",
  source_claim_alignment: "Do the accepted source claims support the stated mechanism, with inference distinguished from direct evidence?",
  falsifiability: "Could the declared observations reject this hypothesis without changing the rules?",
  information_timeline_no_lookahead: "Is every signal input available before its decision time?",
  execution_cost_awareness: "Are costs, holding horizon and capacity plausible enough to proceed to mechanics design?",
  hypothesis_alignment: "Does this intent express the accepted economic edge?",
  unsupported_scope_confirmed: "Does the unsupported scope require an engineering handoff? This is not certification.",
  causal_timeline_reviewed: "Are signal availability and entry timing explicit and causal?",
};

interface Claim {
  claim_id: string;
  statement: string;
  source_location: string;
  support: "DIRECT" | "CONFLICTING" | "INFERENCE";
}

function claimsFrom(task: CodexTaskRecord): Claim[] {
  const values = task.proposal?.claims;
  if (!Array.isArray(values)) return [];
  return values.flatMap((value) => {
    if (!value || typeof value !== "object") return [];
    const item = value as Record<string, unknown>;
    const support = String(item.support || "");
    if (!["DIRECT", "CONFLICTING", "INFERENCE"].includes(support)) return [];
    return [{
      claim_id: String(item.claim_id || ""),
      statement: String(item.statement || ""),
      source_location: String(item.source_location || ""),
      support: support as Claim["support"],
    }];
  }).filter((item) => item.claim_id);
}

function FieldChecklist({
  fields,
  selected,
  setSelected,
  proposal,
}: {
  fields: string[];
  selected: string[];
  setSelected: (value: string[]) => void;
  proposal?: Record<string, unknown> | null;
}) {
  return (
    <div className="factory-review-checklist">
      {fields.map((field) => (
        <div key={field} className="factory-review-field">
          {proposal && <div className="factory-review-value"><ProposalValue value={proposal[field]} /></div>}
          <label className="factory-review-check">
          <input
            type="checkbox"
            checked={selected.includes(field)}
            onChange={(event) => setSelected(
              event.target.checked
                ? [...selected, field]
                : selected.filter((value) => value !== field),
            )}
          />
          <span>{field.replaceAll("_", " ")}</span>
          </label>
          {REVIEW_GUIDANCE[field] && <p className="factory-review-help">{REVIEW_GUIDANCE[field]}</p>}
        </div>
      ))}
    </div>
  );
}

export function isStructuredReviewTask(task: CodexTaskRecord): boolean {
  if (task.task_type === "SOURCE_RESEARCH" || task.task_type === "HYPOTHESIS_PROPOSAL") {
    return true;
  }
  return task.task_type === "MECHANICS_INTENT" &&
    task.proposal?.execution_lane === "ENGINEERING_HANDOFF";
}

export function FactoryStructuredReview({
  task,
  reviewer,
  notes,
  disabled,
  onComplete,
  onDeliveryPending,
  onSourceCaptureChange,
}: {
  task: CodexTaskRecord;
  reviewer: string;
  notes: string;
  disabled?: boolean;
  onComplete: (message: string) => Promise<void>;
  onDeliveryPending?: (taskId: string) => void;
  onSourceCaptureChange?: () => void;
}) {
  const revision = `${task.task_id}:${task.proposal_validation?.payload_sha256 || ""}:${task.proposal_validation?.validation_sha256 || ""}`;
  if (task.task_type === "SOURCE_RESEARCH") {
    return <SourceReview key={revision} task={task} reviewer={reviewer} notes={notes} disabled={disabled} onComplete={onComplete} onDeliveryPending={onDeliveryPending} onSourceCaptureChange={onSourceCaptureChange} />;
  }
  if (task.task_type === "HYPOTHESIS_PROPOSAL") {
    return <HypothesisReview key={revision} task={task} reviewer={reviewer} notes={notes} disabled={disabled} onComplete={onComplete} onDeliveryPending={onDeliveryPending} />;
  }
  if (task.task_type === "MECHANICS_INTENT" && task.proposal?.execution_lane === "ENGINEERING_HANDOFF") {
    return <EngineeringIntentReview key={revision} task={task} reviewer={reviewer} notes={notes} disabled={disabled} onComplete={onComplete} onDeliveryPending={onDeliveryPending} />;
  }
  return null;
}

function deliveryKey(task: CodexTaskRecord): string {
  return `alphaquest.review-delivery.pending.v1:${task.task_id}`;
}

function deliveryPending(task: CodexTaskRecord): boolean {
  if (task.review_delivery) return true;
  try { return localStorage.getItem(deliveryKey(task)) !== null; }
  catch { return true; }
}

function usePendingReview(task: CodexTaskRecord, onDeliveryPending?: (taskId: string) => void) {
  const [uncertain, setUncertain] = useState(() => deliveryPending(task));
  useEffect(() => {
    const observePending = () => {
      if (deliveryPending(task)) { setUncertain(true); onDeliveryPending?.(task.task_id); }
    };
    observePending();
    window.addEventListener("storage", observePending);
    return () => window.removeEventListener("storage", observePending);
  }, [task.task_id, task.review_delivery, onDeliveryPending]);
  return [uncertain, setUncertain] as const;
}

function beginReviewSubmission(task: CodexTaskRecord, setUncertain: (value: boolean) => void, setError: (value: string) => void): ReviewDelivery | null {
  if (deliveryPending(task)) {
    setUncertain(true);
    setError("An earlier submission has an unresolved outcome. Check the saved review before taking further action.");
    return null;
  }
  const revision = task.proposal_validation;
  if (typeof revision?.proposal_id !== "string" || !revision.proposal_id ||
    typeof revision.payload_sha256 !== "string" || !SHA256.test(revision.payload_sha256) ||
    typeof revision.validation_sha256 !== "string" || !SHA256.test(revision.validation_sha256)) {
    setError("The exact proposal version is unavailable. Reload the task before submitting a review.");
    return null;
  }
  try {
    const delivery: ReviewDelivery = {
      operation_id: crypto.randomUUID(),
      proposal_id: revision.proposal_id,
      payload_sha256: revision.payload_sha256!,
      validation_sha256: revision.validation_sha256!,
    };
    // Advisory delivery marker only. The service pins the exact decision across
    // origins; this marker also preserves uncertainty before server admission.
    localStorage.setItem(deliveryKey(task), JSON.stringify({ task_id: task.task_id, ...delivery }));
    return delivery;
  } catch {
    setUncertain(true);
    setError("Could not retain the submission state in this browser. No decision was sent. Restore browser storage before submitting a review.");
    return null;
  }
}

function markReviewSaved(task: CodexTaskRecord, setSaved: (value: boolean) => void) {
  setSaved(true);
  // Failure to remove a marker can only retain a lock; it cannot grant authority.
  try { localStorage.removeItem(deliveryKey(task)); } catch { /* Remain conservative. */ }
}

async function recoverReviewSubmission(
  task: CodexTaskRecord,
  reason: unknown,
  onComplete: ReviewProps["onComplete"],
  setSaved: (saved: boolean) => void,
  setUncertain: (uncertain: boolean) => void,
  setError: (message: string) => void,
) {
  // A rejected fetch can follow a successful immutable write. Read authority
  // back from the service before either claiming success or enabling a retry.
  setUncertain(true);
  const unknownOutcome = "Could not confirm whether the review was saved. Reload Studio to check the stored task before retrying. Submission remains locked.";
  setError(unknownOutcome);
  try {
    const result = await api.factoryTask(task.task_id);
    const current = "task" in result ? result.task : result;
    if (current.task_id !== task.task_id ||
      current.proposal_validation?.proposal_id !== task.proposal_validation?.proposal_id ||
      current.proposal_validation?.validation_sha256 !== task.proposal_validation?.validation_sha256 ||
      current.proposal_validation?.payload_sha256 !== task.proposal_validation?.payload_sha256 ||
      current.proposal_validation?.status !== "VALIDATED_NOT_APPLIED") return;
    const receipt = current.structured_review;
    const expectedStatus = task.task_type === "SOURCE_RESEARCH" ? "ACCEPTED_FOR_HYPOTHESIS"
      : task.task_type === "HYPOTHESIS_PROPOSAL" ? "ACCEPTED_FOR_MECHANICS" : "ACCEPTED_FOR_ENGINEERING_HANDOFF";
    if (receipt?.status === expectedStatus &&
      typeof task.proposal_validation?.proposal_id === "string" &&
      typeof task.proposal_validation?.validation_sha256 === "string" &&
      receipt.proposal_id === task.proposal_validation.proposal_id &&
      receipt.proposal_validation_sha256 === task.proposal_validation.validation_sha256 &&
      receipt.proposal_payload_sha256 === task.proposal_validation?.payload_sha256) {
      const marker = JSON.parse(localStorage.getItem(deliveryKey(task)) || "null");
      const delivery = current.review_delivery;
      if (!marker || marker.task_id !== task.task_id ||
        typeof marker.operation_id !== "string" || !marker.operation_id ||
        marker.proposal_id !== task.proposal_validation.proposal_id ||
        marker.payload_sha256 !== task.proposal_validation.payload_sha256 ||
        marker.validation_sha256 !== task.proposal_validation.validation_sha256 ||
        delivery?.status !== "COMMITTED" || delivery.operation_id !== marker.operation_id ||
        delivery.proposal_id !== marker.proposal_id || delivery.payload_sha256 !== marker.payload_sha256 ||
        delivery.validation_sha256 !== marker.validation_sha256) {
        setError("A stored review exists, but it could not be matched to this submission. A different submission may have been saved. Reopen the task to inspect its receipt; this submission remains unconfirmed.");
        return;
      }
      markReviewSaved(task, setSaved);
      setError("");
      try {
        await onComplete("A stored review was found for this proposal. Read its receipt before continuing.");
      } catch {
        setError("Review saved, but the screen could not refresh. Reload Studio to read the stored receipt before continuing. Do not resubmit.");
      }
    } else if (receipt === null && !current.proposal_disposition) {
      const message = reason instanceof Error ? reason.message : "Review submission outcome is uncertain.";
      setError(`${message} No stored review is visible yet; the original save may still be finishing. Submission remains locked. Check for the saved review again before taking further action.`);
    }
  } catch {
    setError(unknownOutcome);
  }
}

function ReviewRecovery({ task, onComplete, disabled, setSaved, setUncertain, setError }: {
  task: CodexTaskRecord;
  onComplete: ReviewProps["onComplete"];
  disabled: boolean;
  setSaved: (value: boolean) => void;
  setUncertain: (value: boolean) => void;
  setError: (value: string) => void;
}) {
  const [checking, setChecking] = useState(false);
  async function check() {
    if (checking || disabled) return;
    setChecking(true);
    try {
      await recoverReviewSubmission(task, new Error("Submission outcome is still uncertain."),
        onComplete, setSaved, setUncertain, setError);
    } finally { setChecking(false); }
  }
  return <>
    <Notice tone="warning">A prior review submission needs confirmation from the service. Check the stored record; reopening this form does not authorize another submission.</Notice>
    <Button type="button" variant="secondary" disabled={disabled || checking} onClick={() => void check()}>
      {checking ? "CHECKING SAVED REVIEW…" : "CHECK SAVED REVIEW"}
    </Button>
  </>;
}

function SourceReview({ task, reviewer, notes, disabled, onComplete, onDeliveryPending, onSourceCaptureChange }: ReviewProps) {
  const claims = useMemo(() => claimsFrom(task), [task.proposal]);
  const [metadataFields, setMetadataFields] = useState<string[]>([]);
  const [readiness, setReadiness] = useState<SourceReviewReadiness | null>(null);
  const [readinessError, setReadinessError] = useState("");
  const [selectedCapture, setSelectedCapture] = useState("");
  const [retractionStatus, setRetractionStatus] = useState<"" | "NOT_RETRACTED" | "CORRECTED">("");
  const [method, setMethod] = useState("");
  const [decisions, setDecisions] = useState<Record<string, "" | "ACCEPT" | "REJECT">>({});
  const [notesMustBeCleared, setNotesMustBeCleared] = useState(false);
  useEffect(() => { if (!notes.trim()) setNotesMustBeCleared(false); }, [notes]);
  const [claimVerifications, setClaimVerifications] = useState<Record<string, ClaimVerification>>({});
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [uncertain, setUncertain] = usePendingReview(task, onDeliveryPending);
  const [error, setError] = useState("");
  const legacyRecovery = task.review_delivery?.status === "ADMITTED" &&
    task.review_delivery.artifact_schema === "alphaquest.reviewed-source-evidence/v1" &&
    task.review_delivery.legacy_recovery_available === true;
  useEffect(() => {
    setMetadataFields([]);
    setReadiness(null);
    setReadinessError("");
    setSelectedCapture("");
    setRetractionStatus("");
    setMethod("");
    setDecisions({});
    setClaimVerifications(Object.fromEntries(claimsFrom(task).map((claim) =>
      [claim.claim_id, newClaimVerification()])));
    setError("");
    let current = true;
    api.factorySourceReviewReadiness(task.task_id).then((value) => {
      if (!current) return;
      setReadiness(value);
      const ready = value.options.filter((item) => item.readiness === "READY" &&
        (!legacyRecovery || item.legacy_recovery_match === true));
      if (ready.length === 1) setSelectedCapture(ready[0].capture_revision_sha256);
    }).catch((reason) => {
      if (current) setReadinessError(reason instanceof Error ? reason.message : "Source capture readiness is unavailable.");
    });
    return () => { current = false; };
  }, [task.task_id, legacyRecovery]);
  const readyOptions = readiness?.options.filter((item) => item.readiness === "READY") || [];
  const selectableOptions = readyOptions.filter((item) =>
    !legacyRecovery || item.legacy_recovery_match === true);
  const selectedOption = selectableOptions.find((item) => item.capture_revision_sha256 === selectedCapture);
  const contentHash = selectedOption?.content_sha256 || "";
  const evidenceByClaim = Object.fromEntries((selectedOption?.claim_evidence || []).map((item) => [item.claim_id, item]));
  function setClaimField(claim: Claim, field: keyof ClaimVerification, value: string) {
    setClaimVerifications((current) => ({ ...current, [claim.claim_id]: {
      ...(current[claim.claim_id] || newClaimVerification()), [field]: value,
    } }));
  }
  function selectCapture(value: string) {
    if (value === selectedCapture) return;
    if (selectedCapture) {
      setNotesMustBeCleared(Boolean(notes.trim()));
      onSourceCaptureChange?.();
    }
    setSelectedCapture(value);
    // A decision about one source version must never carry over to another.
    setDecisions({});
    setMetadataFields([]);
    setMethod("");
    setRetractionStatus("");
    setClaimVerifications(Object.fromEntries(claims.map((claim) =>
      [claim.claim_id, newClaimVerification()])));
  }
  const complete = Boolean(
    !notesMustBeCleared && reviewer.trim() && notes.trim() && method.trim() && selectedCapture && SHA256.test(contentHash) &&
    retractionStatus && metadataFields.length === SOURCE_METADATA_FIELDS.length && claims.length &&
    claims.every((claim) => decisions[claim.claim_id] && claimVerificationComplete(claimVerifications[claim.claim_id]) &&
      (decisions[claim.claim_id] === "REJECT" || (evidenceByClaim[claim.claim_id]?.status === "BOUND" &&
        SHA256.test(evidenceByClaim[claim.claim_id]?.evidence_sha256 || "")))) &&
    claims.some((claim) => decisions[claim.claim_id] === "ACCEPT"),
  );
  async function submit() {
    if (!complete || !retractionStatus || busy || saved || uncertain || disabled) return;
    const delivery = beginReviewSubmission(task, setUncertain, setError);
    if (!delivery) return;
    onDeliveryPending?.(task.task_id);
    setBusy(true);
    setError("");
    try {
      await api.recordFactoryReviewedSource(task.task_id, {
        delivery,
        capture_revision_sha256: selectedCapture,
        reviewer: reviewer.trim(),
        notes: notes.trim(),
        verified_metadata_fields: metadataFields,
        retraction_status: retractionStatus,
        verification_method: method.trim(),
        claim_reviews: claims.map((claim) => ({
          claim_id: claim.claim_id,
          proposed_support: claim.support,
          decision: decisions[claim.claim_id] as "ACCEPT" | "REJECT",
          evidence_sha256: decisions[claim.claim_id] === "ACCEPT"
            ? evidenceByClaim[claim.claim_id].evidence_sha256
            : null,
          ...serializeClaimVerification(claimVerifications[claim.claim_id]),
        })),
      });
      markReviewSaved(task, setSaved);
      try {
        await onComplete("Source evidence accepted as a separate human-verified artifact. The draft was not changed.");
      } catch {
        setError("Review saved, but the screen could not refresh. Reload Studio to read the stored receipt before continuing. Do not resubmit.");
      }
    } catch (reason) {
      await recoverReviewSubmission(task, reason, onComplete, setSaved, setUncertain, setError);
    } finally {
      setBusy(false);
    }
  }
  async function recoverLegacy() {
    const admitted = task.review_delivery;
    if (!legacyRecovery || !selectedOption || busy || saved || disabled ||
      typeof admitted?.operation_id !== "string" ||
      typeof admitted.proposal_id !== "string" ||
      typeof admitted.payload_sha256 !== "string" ||
      typeof admitted.validation_sha256 !== "string") return;
    const delivery = {
      operation_id: admitted.operation_id,
      proposal_id: admitted.proposal_id,
      payload_sha256: admitted.payload_sha256,
      validation_sha256: admitted.validation_sha256,
    };
    setBusy(true);
    setUncertain(true);
    setError("");
    onDeliveryPending?.(task.task_id);
    let requestError = "";
    try {
      await api.recoverFactoryAdmittedV1Source(task.task_id, {
        delivery,
        capture_revision_sha256: selectedOption.capture_revision_sha256,
      });
    } catch (reason) {
      requestError = reason instanceof Error ? reason.message : "Legacy recovery outcome is uncertain.";
    }
    try {
      const result = await api.factoryTask(task.task_id);
      const current = "task" in result ? result.task : result;
      const receipt = current.structured_review;
      const retained = current.review_delivery;
      if (current.task_id === task.task_id &&
        receipt?.status === "ACCEPTED_FOR_HYPOTHESIS" &&
        receipt.proposal_id === delivery.proposal_id &&
        receipt.proposal_payload_sha256 === delivery.payload_sha256 &&
        receipt.proposal_validation_sha256 === delivery.validation_sha256 &&
        retained?.status === "COMMITTED" &&
        retained.artifact_schema === "alphaquest.reviewed-source-evidence/v1" &&
        retained.operation_id === delivery.operation_id &&
        retained.proposal_id === delivery.proposal_id &&
        retained.payload_sha256 === delivery.payload_sha256 &&
        retained.validation_sha256 === delivery.validation_sha256) {
        markReviewSaved(task, setSaved);
        setUncertain(false);
        setBusy(false);
        try {
          await onComplete("The previously admitted V1 source review was recovered unchanged. Read its historical receipt before continuing.");
        } catch {
          setError("The V1 review was recovered, but the screen could not refresh. Reload Studio to read the stored receipt; do not resubmit.");
        }
        return;
      }
    } catch {
      // Retain the lock and report the uncertain result below.
    }
    setError(`${requestError || "Could not confirm the recovered receipt."} The admitted V1 operation remains locked; reload Studio and inspect the saved task before retrying recovery.`);
    setBusy(false);
  }
  return (
    <div className="factory-structured-review">
      <Notice tone="info" title="Verify the source outside Codex">
        Select a canonical full-text capture, open that exact document, and decide every claim. Codex's PARTIAL source status remains unchanged inside the preserved proposal.
      </Notice>
      <label className="field">
        <span className="field-label">Canonical full-text capture</span>
        <select aria-label="Canonical full-text capture" value={selectedCapture} onChange={(event) => selectCapture(event.target.value)} disabled={!readiness || selectableOptions.length === 0}>
          <option value="">Choose a compatible captured document</option>
          {selectableOptions.map((item) => (
            <option value={item.capture_revision_sha256} key={item.capture_revision_sha256}>
              {item.title} · {item.version_label} · {item.capture_id}
            </option>
          ))}
        </select>
      </label>
      {readinessError && <Notice tone="warning" title="Capture readiness unavailable">{readinessError}</Notice>}
      {readiness && readyOptions.length === 0 && (
        <Notice tone="warning" title="No compatible full-text capture">
          Source review is blocked until LiteratureStore contains a current, retained full-text capture matching this exact proposal version.
        </Notice>
      )}
      {legacyRecovery && readiness && selectableOptions.length === 0 && readyOptions.length > 0 && (
        <Notice tone="warning" title="No capture matches the admitted V1 document">
          Recovery requires current eligible full-text bytes whose content hash exactly matches the previously admitted V1 decision.
        </Notice>
      )}
      {readiness?.options.filter((item) => item.readiness !== "READY").map((item) => (
        <Notice tone="warning" key={item.capture_revision_sha256} title={`${item.capture_id} is not review-ready`}>
          {item.issues.join(", ")}
        </Notice>
      ))}
      <label className="field">
        <span className="field-label">Captured source content SHA-256</span>
        <input aria-label="Captured source content SHA-256" value={contentHash} readOnly placeholder="Selected capture supplies this hash" />
      </label>
      {!legacyRecovery && <>
      <label className="field">
        <span className="field-label">Human verification method</span>
        <input value={method} onChange={(event) => setMethod(event.target.value)} placeholder="Opened DOI/PDF, checked title/authors/year and captured file bytes" />
      </label>
      <label className="field">
        <span className="field-label">Retraction/correction check</span>
        <select value={retractionStatus} onChange={(event) => setRetractionStatus(event.target.value as typeof retractionStatus)}>
          <option value="">Choose verified status</option>
          <option value="NOT_RETRACTED">Not retracted</option>
          <option value="CORRECTED">Corrected — reviewed corrected version</option>
        </select>
      </label>
      <details open>
        <summary>Verify all source identity fields ({metadataFields.length}/{SOURCE_METADATA_FIELDS.length})</summary>
        <FieldChecklist fields={SOURCE_METADATA_FIELDS} selected={metadataFields} setSelected={setMetadataFields} proposal={task.proposal} />
      </details>
      <section aria-label="Source limitations">
        <h4>Conflicting evidence</h4><ProposalValue value={task.proposal?.conflicting_evidence} />
        <h4>Inference notes</h4><ProposalValue value={task.proposal?.inference_notes} />
      </section>
      {claims.map((claim) => (
        <fieldset key={claim.claim_id} className="factory-claim-review">
          <legend>{claim.claim_id} · {claim.support}</legend>
          <p>{claim.statement}</p>
          <small>{claim.source_location}</small>
          <label className="field">
            <span className="field-label">Human claim decision</span>
            <select value={decisions[claim.claim_id] || ""} onChange={(event) => setDecisions((current) => ({ ...current, [claim.claim_id]: event.target.value as "" | "ACCEPT" | "REJECT" }))}>
              <option value="">Choose</option>
              <option value="ACCEPT" disabled={evidenceByClaim[claim.claim_id]?.status !== "BOUND"}>Accept with captured evidence</option>
              <option value="REJECT">Reject claim</option>
            </select>
          </label>
          {evidenceByClaim[claim.claim_id]?.status === "BOUND" ? (
            <label className="field">
              <span className="field-label">Claim evidence SHA-256</span>
              <input aria-label="Claim evidence SHA-256" value={evidenceByClaim[claim.claim_id].evidence_sha256 || ""} readOnly />
              <small>Bound automatically to the selected capture’s {evidenceByClaim[claim.claim_id].evidence_kind === "EXTRACTED_TEXT" ? "text extraction" : "source document"}. This identifies the evidence; it does not approve the claim.</small>
            </label>
          ) : <Notice tone="warning">This claim’s evidence cannot be bound to the selected capture. Acceptance is unavailable. You may reject the claim or leave the review pending.</Notice>}
          <label className="field">
            <span className="field-label">Claim verification method</span>
            <select value={claimVerifications[claim.claim_id]?.method || ""} onChange={(event) => setClaimField(claim, "method", event.target.value)}>
              <option value="">Choose how you checked this claim</option>
              {Object.entries(CLAIM_VERIFICATION_METHODS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label className="field">
            <span className="field-label">Evidence location</span>
            <input aria-label="Evidence location" placeholder={claim.source_location} value={claimVerifications[claim.claim_id]?.location || ""} onChange={(event) => setClaimField(claim, "location", event.target.value)} />
            <small>Enter the page, section or table you actually checked. The suggested location above is not a human confirmation.</small>
          </label>
          {([
            ["finding", "What I found", "Describe the passage or values you checked."],
            ["rationale", "Decision rationale", "Explain why the evidence supports your accept or reject decision."],
            ["limitations", "Limitations or discrepancies", "Record caveats, conflicts or uncertainty; explicitly state if you found none."],
          ] as const).map(([field, label, placeholder]) => <label className="field" key={field}>
            <span className="field-label">{label}</span>
            <textarea rows={2} value={claimVerifications[claim.claim_id]?.[field] || ""}
              onChange={(event) => setClaimField(claim, field, event.target.value)} placeholder={placeholder} />
          </label>)}
          <details>
            <summary>Claim review notes template</summary>
            <pre>{`Finding: ${claimVerifications[claim.claim_id]?.finding || "[your observation]"}\nDecision rationale: ${claimVerifications[claim.claim_id]?.rationale || "[your reasoning]"}\nLimitations or discrepancies: ${claimVerifications[claim.claim_id]?.limitations || "[your limitations check]"}`}</pre>
          </details>
        </fieldset>
      ))}
      {notesMustBeCleared && <Notice tone="warning">Clear and re-enter the overall review notes for this capture.</Notice>}
      {!complete && <p className="factory-proposal-requirement">Verify all metadata, decide every claim, accept at least one claim with bound evidence, and complete each verification field.</p>}
      </>}
      {uncertain && !saved && !legacyRecovery && <ReviewRecovery task={task} onComplete={onComplete} disabled={busy}
        setSaved={setSaved} setUncertain={setUncertain} setError={setError} />}
      {legacyRecovery && !saved && (
        <>
          <Notice tone="warning" title="Recover the previously admitted V1 review">
            This completes the exact historical decision already retained by the service. It preserves the V1 receipt and does not add V2 capture-binding assurance or create a new human decision.
          </Notice>
          <Button type="button" variant="secondary" disabled={disabled || busy || !selectedOption}
            onClick={() => void recoverLegacy()}>
            {busy ? "RECOVERING ADMITTED V1 REVIEW…" : "RECOVER ADMITTED V1 REVIEW"}
          </Button>
        </>
      )}
      {saved && <Notice tone="info">Review saved. Read the receipt before continuing.</Notice>}
      {error && <Notice tone="warning">{error}</Notice>}
      <Button type="button" disabled={disabled || busy || saved || uncertain || !complete} onClick={() => void submit()}>ACCEPT REVIEWED SOURCE EVIDENCE</Button>
    </div>
  );
}

function HypothesisReview({ task, reviewer, notes, disabled, onComplete, onDeliveryPending }: ReviewProps) {
  const [fields, setFields] = useState<string[]>([]);
  const [gates, setGates] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [uncertain, setUncertain] = usePendingReview(task, onDeliveryPending);
  const [error, setError] = useState("");
  const gateNames = ["objective_alignment", "source_claim_alignment", "falsifiability", "information_timeline_no_lookahead", "execution_cost_awareness"];
  useEffect(() => { setFields([]); setGates([]); setError(""); }, [task.task_id]);
  const complete = reviewer.trim() && notes.trim() && fields.length === HYPOTHESIS_FIELDS.length && gates.length === gateNames.length;
  async function submit() {
    if (!complete || busy || saved || uncertain || disabled) return;
    const delivery = beginReviewSubmission(task, setUncertain, setError);
    if (!delivery) return;
    onDeliveryPending?.(task.task_id);
    setBusy(true);
    setError("");
    try {
      await api.recordFactoryReviewedHypothesis(task.task_id, {
        delivery,
        reviewer: reviewer.trim(), notes: notes.trim(), reviewed_fields: fields,
        objective_alignment: "PASS", source_claim_alignment: "PASS", falsifiability: "PASS",
        information_timeline_no_lookahead: "PASS", execution_cost_awareness: "PASS",
      });
      markReviewSaved(task, setSaved);
      try {
        await onComplete("The complete hypothesis was accepted as a hash-bound reviewed artifact. No mechanics were approved.");
      } catch {
        setError("Review saved, but the screen could not refresh. Reload Studio to read the stored receipt before continuing. Do not resubmit.");
      }
    } catch (reason) {
      await recoverReviewSubmission(task, reason, onComplete, setSaved, setUncertain, setError);
    } finally { setBusy(false); }
  }
  return (
    <div className="factory-structured-review">
      <Notice tone="info" title="Review the complete hypothesis contract">Every field below is preserved in the accepted artifact. Acceptance authorizes only a mechanics proposal, never testing.</Notice>
      <details open>
        <summary>Review every hypothesis field ({fields.length}/{HYPOTHESIS_FIELDS.length})</summary>
        <FieldChecklist fields={HYPOTHESIS_FIELDS} selected={fields} setSelected={setFields} proposal={task.proposal} />
      </details>
      <details open>
        <summary>Pass every research-quality gate ({gates.length}/{gateNames.length})</summary>
        <FieldChecklist fields={gateNames} selected={gates} setSelected={setGates} />
      </details>
      {!complete && <p className="factory-proposal-requirement">Review every field and pass every gate with reviewer identity and notes.</p>}
      {uncertain && !saved && <ReviewRecovery task={task} onComplete={onComplete} disabled={busy}
        setSaved={setSaved} setUncertain={setUncertain} setError={setError} />}
      {saved && <Notice tone="info">Review saved. Read the receipt before continuing.</Notice>}
      {error && <Notice tone="warning">{error}</Notice>}
      <Button type="button" disabled={disabled || busy || saved || uncertain || !complete} onClick={() => void submit()}>ACCEPT REVIEWED HYPOTHESIS</Button>
    </div>
  );
}

function EngineeringIntentReview({ task, reviewer, notes, disabled, onComplete, onDeliveryPending }: ReviewProps) {
  const [fields, setFields] = useState<string[]>([]);
  const [gates, setGates] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [uncertain, setUncertain] = usePendingReview(task, onDeliveryPending);
  const [error, setError] = useState("");
  const gateNames = ["hypothesis_alignment", "unsupported_scope_confirmed", "causal_timeline_reviewed"];
  useEffect(() => { setFields([]); setGates([]); setError(""); }, [task.task_id]);
  const complete = reviewer.trim() && notes.trim() && fields.length === MECHANICS_FIELDS.length && gates.length === gateNames.length;
  async function submit() {
    if (!complete || busy || saved || uncertain || disabled) return;
    const delivery = beginReviewSubmission(task, setUncertain, setError);
    if (!delivery) return;
    onDeliveryPending?.(task.task_id);
    setBusy(true);
    setError("");
    try {
      await api.recordFactoryReviewedEngineeringIntent(task.task_id, {
        delivery,
        reviewer: reviewer.trim(), notes: notes.trim(), reviewed_fields: fields,
        hypothesis_alignment: "PASS", unsupported_scope_confirmed: "PASS", causal_timeline_reviewed: "PASS",
      });
      markReviewSaved(task, setSaved);
      try {
        await onComplete("Unsupported mechanics intent accepted for a proposal-only engineering handoff. No code was written or certified.");
      } catch {
        setError("Review saved, but the screen could not refresh. Reload Studio to read the stored receipt before continuing. Do not resubmit.");
      }
    } catch (reason) {
      await recoverReviewSubmission(task, reason, onComplete, setSaved, setUncertain, setError);
    } finally { setBusy(false); }
  }
  return (
    <div className="factory-structured-review">
      <Notice tone="warning" title="Engineering handoff only">This review may queue a bounded handoff proposal. It cannot implement code, certify a strategy, publish a variant, or authorize P&amp;L.</Notice>
      <details open><summary>Review every mechanics-intent field ({fields.length}/{MECHANICS_FIELDS.length})</summary><FieldChecklist fields={MECHANICS_FIELDS} selected={fields} setSelected={setFields} proposal={task.proposal} /></details>
      <details open><summary>Confirm handoff gates ({gates.length}/{gateNames.length})</summary><FieldChecklist fields={gateNames} selected={gates} setSelected={setGates} /></details>
      {uncertain && !saved && <ReviewRecovery task={task} onComplete={onComplete} disabled={busy}
        setSaved={setSaved} setUncertain={setUncertain} setError={setError} />}
      {saved && <Notice tone="info">Review saved. Read the receipt before continuing.</Notice>}
      {error && <Notice tone="warning">{error}</Notice>}
      <Button type="button" disabled={disabled || busy || saved || uncertain || !complete} onClick={() => void submit()}>ACCEPT FOR ENGINEERING HANDOFF</Button>
    </div>
  );
}

interface ReviewProps {
  task: CodexTaskRecord;
  reviewer: string;
  notes: string;
  disabled?: boolean;
  onDeliveryPending?: (taskId: string) => void;
  onSourceCaptureChange?: () => void;
  onComplete: (message: string) => Promise<void>;
}
