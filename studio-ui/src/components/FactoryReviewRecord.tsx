import type { CodexTaskRecord } from "../types";
import { Notice } from "./UI";

export function ProposalValue({ value }: { value: unknown }) {
  if (value === undefined) return <span className="review-missing">Not provided</span>;
  if (value === null) return <span className="review-missing">None declared</span>;
  if (Array.isArray(value)) {
    if (!value.length) return <span>None declared</span>;
    return <ul>{value.map((item, index) => <li key={index}><ProposalValue value={item} /></li>)}</ul>;
  }
  if (typeof value === "object") {
    return <dl>{Object.entries(value as Record<string, unknown>).map(([key, item]) => (
      <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd><ProposalValue value={item} /></dd></div>
    ))}</dl>;
  }
  return <span>{String(value)}</span>;
}

export function FactoryReviewIdentity({ task }: { task: CodexTaskRecord }) {
  const validation = task.proposal_validation;
  return (
    <details className="factory-review-identity">
      <summary>Exact proposal version</summary>
      <dl>
        <dt>Proposal ID</dt><dd>{String(validation?.proposal_id || "Unavailable")}</dd>
        <dt>Proposal SHA-256</dt><dd>{String(validation?.payload_sha256 || "Unavailable")}</dd>
        <dt>Validation SHA-256</dt><dd>{String(validation?.validation_sha256 || "Unavailable")}</dd>
      </dl>
      <p>A review applies to this proposal and its recorded inputs. Changed inputs require fresh review through the existing service.</p>
    </details>
  );
}

export function FactoryReviewReceipt({ task }: { task: CodexTaskRecord }) {
  const receipt = task.structured_review;
  if (!receipt) return null;
  if (receipt.status === "INTEGRITY_ERROR") {
    return <Notice tone="warning" title="Review receipt unavailable">The stored evidence could not be verified. Keep this proposal blocked and reconcile the evidence before continuing.</Notice>;
  }
  return (
    <section className="factory-review-receipt" aria-label="Saved review receipt">
      <h4>Saved review receipt</h4>
      <dl>
        <dt>Decision</dt><dd>{receipt.decision || receipt.status}</dd>
        <dt>Review ID</dt><dd>{receipt.review_id || "Unavailable"}</dd>
        <dt>Recorded by</dt><dd>{receipt.reviewer || "Unavailable"}</dd>
        <dt>Recorded at</dt><dd>{receipt.recorded_at || "Unavailable"}</dd>
        <dt>Review notes</dt><dd>{receipt.notes || "Unavailable"}</dd>
      </dl>
      <p>This decision is stored by AlphaQuest. Reopening Studio reads the same record. It does not authorize performance testing.</p>
      <details>
        <summary>Receipt evidence and exact version</summary>
        <dl>
          <dt>Proposal ID</dt><dd>{receipt.proposal_id || "Unavailable"}</dd>
          <dt>Proposal SHA-256</dt><dd>{receipt.proposal_payload_sha256 || "Unavailable"}</dd>
          <dt>Validation SHA-256</dt><dd>{receipt.proposal_validation_sha256 || "Unavailable"}</dd>
          <dt>Artifact SHA-256</dt><dd>{receipt.artifact_sha256 || "Unavailable"}</dd>
        </dl>
        {receipt.artifact && <>
          <a download={`review-${task.task_id}.json`} href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(receipt.artifact, null, 2))}`}>Download review artifact (JSON)</a>
          <pre>{JSON.stringify(receipt.artifact, null, 2)}</pre>
        </>}
      </details>
    </section>
  );
}
