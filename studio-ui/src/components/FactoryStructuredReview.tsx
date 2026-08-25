import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { CodexTaskRecord } from "../types";
import { Button, Notice } from "./UI";

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
}: {
  fields: string[];
  selected: string[];
  setSelected: (value: string[]) => void;
}) {
  return (
    <div className="factory-review-checklist">
      {fields.map((field) => (
        <label key={field} className="factory-review-check">
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
}: {
  task: CodexTaskRecord;
  reviewer: string;
  notes: string;
  disabled?: boolean;
  onComplete: (message: string) => Promise<void>;
}) {
  if (task.task_type === "SOURCE_RESEARCH") {
    return <SourceReview task={task} reviewer={reviewer} notes={notes} disabled={disabled} onComplete={onComplete} />;
  }
  if (task.task_type === "HYPOTHESIS_PROPOSAL") {
    return <HypothesisReview task={task} reviewer={reviewer} notes={notes} disabled={disabled} onComplete={onComplete} />;
  }
  if (task.task_type === "MECHANICS_INTENT" && task.proposal?.execution_lane === "ENGINEERING_HANDOFF") {
    return <EngineeringIntentReview task={task} reviewer={reviewer} notes={notes} disabled={disabled} onComplete={onComplete} />;
  }
  return null;
}

function SourceReview({ task, reviewer, notes, disabled, onComplete }: ReviewProps) {
  const claims = useMemo(() => claimsFrom(task), [task.task_id]);
  const [metadataFields, setMetadataFields] = useState<string[]>([]);
  const [contentHash, setContentHash] = useState("");
  const [retractionStatus, setRetractionStatus] = useState<"" | "NOT_RETRACTED" | "CORRECTED">("");
  const [method, setMethod] = useState("");
  const [decisions, setDecisions] = useState<Record<string, "" | "ACCEPT" | "REJECT">>({});
  const [evidenceHashes, setEvidenceHashes] = useState<Record<string, string>>({});
  const [claimNotes, setClaimNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    setMetadataFields([]);
    setContentHash("");
    setRetractionStatus("");
    setMethod("");
    setDecisions({});
    setEvidenceHashes({});
    setClaimNotes({});
    setError("");
  }, [task.task_id]);
  const complete = Boolean(
    reviewer.trim() && notes.trim() && method.trim() && SHA256.test(contentHash) &&
    retractionStatus && metadataFields.length === SOURCE_METADATA_FIELDS.length && claims.length &&
    claims.every((claim) => decisions[claim.claim_id] && claimNotes[claim.claim_id]?.trim() &&
      (decisions[claim.claim_id] === "REJECT" || SHA256.test(evidenceHashes[claim.claim_id] || ""))) &&
    claims.some((claim) => decisions[claim.claim_id] === "ACCEPT"),
  );
  async function submit() {
    if (!complete || !retractionStatus) return;
    setBusy(true);
    setError("");
    try {
      await api.recordFactoryReviewedSource(task.task_id, {
        reviewer: reviewer.trim(),
        notes: notes.trim(),
        verified_metadata_fields: metadataFields,
        content_sha256: contentHash,
        retraction_status: retractionStatus,
        verification_method: method.trim(),
        claim_reviews: claims.map((claim) => ({
          claim_id: claim.claim_id,
          proposed_support: claim.support,
          decision: decisions[claim.claim_id] as "ACCEPT" | "REJECT",
          evidence_sha256: decisions[claim.claim_id] === "ACCEPT"
            ? evidenceHashes[claim.claim_id]
            : null,
          verification_method: method.trim(),
          notes: claimNotes[claim.claim_id].trim(),
        })),
      });
      await onComplete("Source evidence accepted as a separate human-verified artifact. The draft was not changed.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Source review was not stored.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="factory-structured-review">
      <Notice tone="info" title="Verify the source outside Codex">
        Open the original source, capture the exact bytes or document used, and decide every claim. Codex's PARTIAL source status remains unchanged inside the preserved proposal.
      </Notice>
      <label className="field">
        <span className="field-label">Captured source content SHA-256</span>
        <input value={contentHash} onChange={(event) => setContentHash(event.target.value.trim().toLowerCase())} placeholder="64 lowercase hexadecimal characters" />
      </label>
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
      <details>
        <summary>Verify all source identity fields ({metadataFields.length}/{SOURCE_METADATA_FIELDS.length})</summary>
        <FieldChecklist fields={SOURCE_METADATA_FIELDS} selected={metadataFields} setSelected={setMetadataFields} />
      </details>
      {claims.map((claim) => (
        <fieldset key={claim.claim_id} className="factory-claim-review">
          <legend>{claim.claim_id} · {claim.support}</legend>
          <p>{claim.statement}</p>
          <small>{claim.source_location}</small>
          <label className="field">
            <span className="field-label">Human claim decision</span>
            <select value={decisions[claim.claim_id] || ""} onChange={(event) => setDecisions((current) => ({ ...current, [claim.claim_id]: event.target.value as "" | "ACCEPT" | "REJECT" }))}>
              <option value="">Choose</option>
              <option value="ACCEPT">Accept with captured evidence</option>
              <option value="REJECT">Reject claim</option>
            </select>
          </label>
          {decisions[claim.claim_id] === "ACCEPT" && (
            <label className="field">
              <span className="field-label">Claim evidence SHA-256</span>
              <input value={evidenceHashes[claim.claim_id] || ""} onChange={(event) => setEvidenceHashes((current) => ({ ...current, [claim.claim_id]: event.target.value.trim().toLowerCase() }))} placeholder="Hash of the captured excerpt or evidence record" />
            </label>
          )}
          <label className="field">
            <span className="field-label">Claim review notes</span>
            <textarea rows={2} value={claimNotes[claim.claim_id] || ""} onChange={(event) => setClaimNotes((current) => ({ ...current, [claim.claim_id]: event.target.value }))} />
          </label>
        </fieldset>
      ))}
      {!complete && <p className="factory-proposal-requirement">Verify all metadata, enter valid hashes, decide every claim, accept at least one claim, and complete reviewer notes.</p>}
      {error && <Notice tone="warning">{error}</Notice>}
      <Button type="button" disabled={disabled || busy || !complete} onClick={() => void submit()}>ACCEPT REVIEWED SOURCE EVIDENCE</Button>
    </div>
  );
}

function HypothesisReview({ task, reviewer, notes, disabled, onComplete }: ReviewProps) {
  const [fields, setFields] = useState<string[]>([]);
  const [gates, setGates] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const gateNames = ["objective_alignment", "source_claim_alignment", "falsifiability", "information_timeline_no_lookahead", "execution_cost_awareness"];
  useEffect(() => { setFields([]); setGates([]); setError(""); }, [task.task_id]);
  const complete = reviewer.trim() && notes.trim() && fields.length === HYPOTHESIS_FIELDS.length && gates.length === gateNames.length;
  async function submit() {
    if (!complete) return;
    setBusy(true);
    setError("");
    try {
      await api.recordFactoryReviewedHypothesis(task.task_id, {
        reviewer: reviewer.trim(), notes: notes.trim(), reviewed_fields: fields,
        objective_alignment: "PASS", source_claim_alignment: "PASS", falsifiability: "PASS",
        information_timeline_no_lookahead: "PASS", execution_cost_awareness: "PASS",
      });
      await onComplete("The complete hypothesis was accepted as a hash-bound reviewed artifact. No mechanics were approved.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Hypothesis review was not stored.");
    } finally { setBusy(false); }
  }
  return (
    <div className="factory-structured-review">
      <Notice tone="info" title="Review the complete hypothesis contract">Every field below is preserved in the accepted artifact. Acceptance authorizes only a mechanics proposal, never testing.</Notice>
      <details open>
        <summary>Review every hypothesis field ({fields.length}/{HYPOTHESIS_FIELDS.length})</summary>
        <FieldChecklist fields={HYPOTHESIS_FIELDS} selected={fields} setSelected={setFields} />
      </details>
      <details open>
        <summary>Pass every research-quality gate ({gates.length}/{gateNames.length})</summary>
        <FieldChecklist fields={gateNames} selected={gates} setSelected={setGates} />
      </details>
      {!complete && <p className="factory-proposal-requirement">Review every field and pass every gate with reviewer identity and notes.</p>}
      {error && <Notice tone="warning">{error}</Notice>}
      <Button type="button" disabled={disabled || busy || !complete} onClick={() => void submit()}>ACCEPT REVIEWED HYPOTHESIS</Button>
    </div>
  );
}

function EngineeringIntentReview({ task, reviewer, notes, disabled, onComplete }: ReviewProps) {
  const [fields, setFields] = useState<string[]>([]);
  const [gates, setGates] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const gateNames = ["hypothesis_alignment", "unsupported_scope_confirmed", "causal_timeline_reviewed"];
  useEffect(() => { setFields([]); setGates([]); setError(""); }, [task.task_id]);
  const complete = reviewer.trim() && notes.trim() && fields.length === MECHANICS_FIELDS.length && gates.length === gateNames.length;
  async function submit() {
    if (!complete) return;
    setBusy(true);
    setError("");
    try {
      await api.recordFactoryReviewedEngineeringIntent(task.task_id, {
        reviewer: reviewer.trim(), notes: notes.trim(), reviewed_fields: fields,
        hypothesis_alignment: "PASS", unsupported_scope_confirmed: "PASS", causal_timeline_reviewed: "PASS",
      });
      await onComplete("Unsupported mechanics intent accepted for a proposal-only engineering handoff. No code was written or certified.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Engineering-intent review was not stored.");
    } finally { setBusy(false); }
  }
  return (
    <div className="factory-structured-review">
      <Notice tone="warning" title="Engineering handoff only">This review may queue a bounded handoff proposal. It cannot implement code, certify a strategy, publish a variant, or authorize P&amp;L.</Notice>
      <details open><summary>Review every mechanics-intent field ({fields.length}/{MECHANICS_FIELDS.length})</summary><FieldChecklist fields={MECHANICS_FIELDS} selected={fields} setSelected={setFields} /></details>
      <details open><summary>Confirm handoff gates ({gates.length}/{gateNames.length})</summary><FieldChecklist fields={gateNames} selected={gates} setSelected={setGates} /></details>
      {error && <Notice tone="warning">{error}</Notice>}
      <Button type="button" disabled={disabled || busy || !complete} onClick={() => void submit()}>ACCEPT FOR ENGINEERING HANDOFF</Button>
    </div>
  );
}

interface ReviewProps {
  task: CodexTaskRecord;
  reviewer: string;
  notes: string;
  disabled?: boolean;
  onComplete: (message: string) => Promise<void>;
}
