import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { Icon } from "../components/Icons";
import { ResultArtifactEvidence } from "./CampaignPage";
import {
  Button,
  Card,
  EmptyState,
  Field,
  Notice,
  PageHeader,
  Skeleton,
  StatusBadge,
  TechnicalDetails,
  humanize,
} from "../components/UI";
import type { ReviewTask } from "../types";
import {
  resolveAdaptiveV18MechanicsComparison,
  resolveFrozenSetup,
  resolveQualifyingFootprint,
  resolveStrategyEvidencePanels,
  type FrozenSetupSummary,
  type MechanicsComparisonSection,
  type QualifyingFootprintRoute,
  type QualifyingFootprintSummary,
} from "../strategyEvidence";

type ReviewGroups = {
  items: ReviewTask[];
  mechanics: ReviewTask[];
  candidate: ReviewTask[];
};

export const REVIEW_QUEUE_HELP = {
  mechanics:
    "Manual trade-by-trade checks that the current attempt follows its frozen entry, exit, and risk rules. Completing this review can unlock performance testing; it does not judge profitability.",
  candidate:
    "Independent human sign-off after a strategy completes the research pipeline with PASS. It promotes a candidate for further incubation; it is not approval for live trading.",
  items:
    "Historical, stale, or incomplete records flagged by the research index for audit and reconciliation. Resolving them does not unblock the current campaign workflow.",
} as const;

export function mechanicsAnnotationFormState(detail: any): {
  status: string;
  notes: string;
} {
  const annotation = detail?.trade_evidence?.annotation;
  const savedStatus = String(annotation?.reviewer_status || "").trim();
  return {
    status: savedStatus || "Correct",
    notes: String(annotation?.reviewer_notes || ""),
  };
}

export function ReviewsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<ReviewGroups>({
    items: [],
    mechanics: [],
    candidate: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestedType = searchParams.get("type");
  const requestedCampaign = searchParams.get("campaign");
  const requestedAttempt = searchParams.get("attempt");
  const requestedVariant = searchParams.get("variant");
  const requestedTrade = searchParams.get("trade");
  const [type, setType] = useState<keyof ReviewGroups>(
    requestedType === "candidate" || requestedType === "items"
      ? requestedType
      : "mechanics",
  );
  const [showMechanicsHistory, setShowMechanicsHistory] = useState(false);
  const [selected, setSelected] = useState(0);
  useEffect(() => {
    api
      .reviews()
      .then(setData)
      .catch((reason) =>
        setError(
          reason instanceof Error ? reason.message : "Reviews unavailable",
        ),
      )
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => setSelected(0), [type]);
  useEffect(() => {
    const requested = searchParams.get("type");
    if (requested === "mechanics" || requested === "candidate" || requested === "items")
      setType(requested);
  }, [searchParams]);
  const currentMechanics = data.mechanics.filter(
    (task: any) => task.is_current_workflow !== false,
  );
  const historicalMechanics = data.mechanics.filter(
    (task: any) => task.is_current_workflow === false,
  );
  const list =
    type === "mechanics"
      ? showMechanicsHistory
        ? historicalMechanics
        : currentMechanics
      : data[type];
  useEffect(() => {
    if (!requestedCampaign || !requestedVariant) return;
    const currentIndex = currentMechanics.findIndex(
      (task) =>
        task.campaign_id === requestedCampaign &&
        task.variant_id === requestedVariant &&
        (!requestedAttempt ||
          (task.attempt_id || "original") === requestedAttempt),
    );
    if (type === "mechanics" && currentIndex >= 0) {
      setShowMechanicsHistory(false);
      setSelected(currentIndex);
      return;
    }
    const historyIndex = historicalMechanics.findIndex(
      (task) =>
        task.campaign_id === requestedCampaign &&
        task.variant_id === requestedVariant &&
        (!requestedAttempt ||
          (task.attempt_id || "original") === requestedAttempt),
    );
    if (type === "mechanics" && historyIndex >= 0) {
      setShowMechanicsHistory(true);
      setSelected(historyIndex);
      return;
    }
    const index = data[type].findIndex(
      (task) =>
        task.campaign_id === requestedCampaign &&
        task.variant_id === requestedVariant,
    );
    if (index >= 0) setSelected(index);
  }, [
    data,
    type,
    requestedCampaign,
    requestedAttempt,
    requestedVariant,
    currentMechanics.length,
    historicalMechanics.length,
  ]);
  function chooseType(value: keyof ReviewGroups) {
    setType(value);
    setSearchParams({ type: value }, { replace: true });
  }
  const item = list[selected] as any;
  return (
    <div className="page review-page">
      <PageHeader
        eyebrow="Governance inbox"
        title="Reviews"
        description="Verify implementation against the frozen specification. Mechanics review is never profitability approval."
      />
      <div className="review-summary">
        <QueueButton
          selected={type === "mechanics"}
          icon="review"
          count={currentMechanics.length}
          label="Current mechanics"
          description={REVIEW_QUEUE_HELP.mechanics}
          onClick={() => chooseType("mechanics")}
        />
        <QueueButton
          selected={type === "candidate"}
          icon="shield"
          count={data.candidate.length}
          label="Candidate sign-offs"
          description={REVIEW_QUEUE_HELP.candidate}
          onClick={() => chooseType("candidate")}
        />
        <QueueButton
          selected={type === "items"}
          icon="warning"
          count={data.items.length}
          label="Indexed attention"
          description={REVIEW_QUEUE_HELP.items}
          onClick={() => chooseType("items")}
        />
      </div>
      {type === "mechanics" && historicalMechanics.length > 0 && (
        <div className="review-scope-switch" aria-label="Mechanics review scope">
          <button
            className={!showMechanicsHistory ? "selected" : ""}
            aria-pressed={!showMechanicsHistory}
            onClick={() => {
              setShowMechanicsHistory(false);
              setSelected(0);
            }}
          >
            Current workflow ({currentMechanics.length})
          </button>
          <button
            className={showMechanicsHistory ? "selected" : ""}
            aria-pressed={showMechanicsHistory}
            onClick={() => {
              setShowMechanicsHistory(true);
              setSelected(0);
            }}
          >
            Historical unresolved ({historicalMechanics.length})
          </button>
        </div>
      )}
      {error && <Notice tone="danger">{error}</Notice>}
      {loading ? (
        <Skeleton lines={8} />
      ) : list.length === 0 ? (
        <EmptyState
          icon="check"
          title="No reviews in this queue"
          body={
            type === "mechanics"
              ? "Mechanics evidence must be generated before sample-bound review appears here."
              : "Only finalized PASS results await independent candidate sign-off."
          }
        />
      ) : (
        <div className="review-workspace">
          <aside className="review-inbox" aria-label="Review tasks">
            {list.map((task: any, index) => (
              <button
                className={
                  selected === index ? "review-task selected" : "review-task"
                }
                key={
                  task.review_id ||
                  task.id ||
                  `${task.campaign_id}-${task.variant_id}-${index}`
                }
                onClick={() => setSelected(index)}
              >
                <span className="review-task-icon">
                  <Icon name={type === "candidate" ? "shield" : "review"} />
                </span>
                <span>
                  <strong>
                    {task.campaign_title ||
                      task.campaign_id ||
                      "Governed review"}
                  </strong>
                  <small>
                    {task.variant_id && `${task.variant_id} · `}
                    {task.attempt_label ||
                      task.attempt_id ||
                      humanize(task.verdict)}
                  </small>
                </span>
                <StatusBadge
                  value={
                    task.ready_for_approval
                      ? "Ready"
                      : task.status || task.verdict || "Needs review"
                  }
                />
              </button>
            ))}
          </aside>
          <section className="review-detail">
            <div className="review-detail-header">
              <div>
                <p className="eyebrow">
                  {type === "candidate"
                    ? "Independent candidate review"
                    : "Mechanics implementation review"}
                </p>
                <h2>
                  {item.campaign_title || item.campaign_id || "Review task"}
                </h2>
                <p>
                  {item.variant_id && `${item.variant_id} · `}
                  {item.attempt_label ||
                    item.run_id ||
                    "Governed immutable evidence"}
                </p>
                {item.attempt_id && (
                  <ExactReviewIdentity attemptId={item.attempt_id} />
                )}
                {item.campaign_id && item.variant_id && (
                  <Link
                    className="inline-link"
                    to={`/research/${item.campaign_id}/mechanics?attempt=${encodeURIComponent(
                      item.attempt_id || "original",
                    )}&variant=${encodeURIComponent(item.variant_id)}`}
                  >
                    View exact frozen variant mechanics →
                  </Link>
                )}
              </div>
              <StatusBadge
                value={
                  item.verdict ||
                  item.status ||
                  (item.ready_for_approval
                    ? "Ready for approval"
                    : "Needs review")
                }
                kind="scientific"
              />
            </div>
            {type === "candidate" ? (
              <CandidateReview
                item={item}
                onResolved={() =>
                  setData((current) => ({
                    ...current,
                    candidate: current.candidate.filter(
                      (entry: any) => entry.review_id !== item.review_id,
                    ),
                  }))
                }
              />
            ) : type === "mechanics" ? (
              <MechanicsReview
                item={item}
                requestedTrade={requestedTrade}
                onResolved={() =>
                  setData((current) => ({
                    ...current,
                    mechanics: current.mechanics.filter(
                      (entry: any) => entry.review_id !== item.review_id,
                    ),
                  }))
                }
              />
            ) : (
              <IndexedAttention item={item} />
            )}
          </section>
        </div>
      )}
    </div>
  );
}

function QueueButton({
  selected,
  icon,
  count,
  label,
  description,
  onClick,
}: {
  selected: boolean;
  icon: "review" | "shield" | "warning";
  count: number;
  label: string;
  description: string;
  onClick: () => void;
}) {
  const helpId = `review-help-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  return (
    <div className={selected ? "review-queue-card selected" : "review-queue-card"}>
      <button aria-pressed={selected} onClick={onClick}>
        <span>
          <Icon name={icon} />
        </span>
        <strong>{count}</strong>
        <small>{label}</small>
      </button>
      <span
        className="review-queue-info"
        tabIndex={0}
        role="img"
        aria-label={`About ${label}`}
        aria-describedby={helpId}
      >
        i
        <span className="review-queue-tooltip" id={helpId} role="tooltip">
          <strong>{label}</strong>
          {description}
        </span>
      </span>
    </div>
  );
}

function MechanicsReview({
  item,
  requestedTrade,
  onResolved,
}: {
  item: any;
  requestedTrade?: string | null;
  onResolved: () => void;
}) {
  const [detail, setDetail] = useState<any>(item);
  const [trade, setTrade] = useState("");
  const [status, setStatus] = useState("Correct");
  const [notes, setNotes] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [decisionNotes, setDecisionNotes] = useState("");
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState("");
  const identity = `${item.campaign_id}:${item.attempt_id || "original"}:${item.variant_id}`;
  useEffect(() => {
    api
      .settings()
      .then((settings) =>
        setReviewer((current) => current || settings.reviewer_identity || ""),
      )
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!item.campaign_id || !item.variant_id) return;
    let cancelled = false;
    setFeedback("");
    async function loadEvidence() {
      try {
        const base = await api.mechanicsReview(
          item.campaign_id,
          item.attempt_id || "original",
          item.variant_id,
        );
        if (cancelled) return;
        const sampled = new Set(
          (base.sampled_trade_ids || []).map((value: unknown) => String(value)),
        );
        const value =
          requestedTrade && sampled.has(requestedTrade)
            ? await api.mechanicsReview(
                item.campaign_id,
                item.attempt_id || "original",
                item.variant_id,
                requestedTrade,
              )
            : base;
        if (cancelled) return;
        setDetail(value);
        setTrade(
          String(
            value.trade_evidence?.trade_id ||
              value.sampled_trade_ids?.[0] ||
              "",
          ),
        );
        const form = mechanicsAnnotationFormState(value);
        setStatus(form.status);
        setNotes(form.notes);
        if (requestedTrade && !sampled.has(requestedTrade)) {
          setFeedback(
            `Trade ${requestedTrade} is outside the deterministic mechanics sample; showing the first governed sample instead.`,
          );
        }
      } catch (reason) {
        if (cancelled) return;
        setFeedback(
          reason instanceof Error
            ? reason.message
            : "Evidence detail unavailable",
        );
      }
    }
    void loadEvidence();
    return () => {
      cancelled = true;
    };
  }, [identity, requestedTrade]);
  async function selectTrade(value: string) {
    setTrade(value);
    setStatus("Correct");
    setNotes("");
    setBusy("evidence");
    setFeedback("");
    try {
      const updated = await api.mechanicsReview(
        item.campaign_id,
        item.attempt_id || "original",
        item.variant_id,
        value,
      );
      setDetail(updated);
      const form = mechanicsAnnotationFormState(updated);
      setStatus(form.status);
      setNotes(form.notes);
    } catch (reason) {
      setFeedback(
        reason instanceof Error ? reason.message : "Trade evidence unavailable",
      );
    } finally {
      setBusy("");
    }
  }
  const sample = detail.sample_progress || {};
  const required = sample.required ?? detail.sampled_trade_ids?.length ?? 0;
  const completed =
    sample.reviewed_correct ??
    Math.max(
      0,
      required -
        (detail.unreviewed_trade_ids?.length || 0) -
        (detail.non_correct_trade_ids?.length || 0),
    );
  const progress = required ? Math.round((completed / required) * 100) : 0;
  const sampledTradeIds: string[] = (detail.sampled_trade_ids || []).map(
    (id: unknown) => String(id),
  );
  const selectedTradeIndex = Math.max(0, sampledTradeIds.indexOf(trade));
  const previousTrade = sampledTradeIds[selectedTradeIndex - 1];
  const nextTrade = sampledTradeIds[selectedTradeIndex + 1];
  const unreviewedTradeIds = new Set(
    (detail.unreviewed_trade_ids || []).map(String),
  );
  const attentionTradeIds = new Set(
    (detail.non_correct_trade_ids || []).map(String),
  );
  const tradeReviewState = (id: string) =>
    unreviewedTradeIds.has(id)
      ? "unreviewed"
      : attentionTradeIds.has(id)
        ? "attention"
        : "correct";
  const tradeReviewLabel = (id: string) => {
    const state = tradeReviewState(id);
    if (state === "correct") return "Correct";
    if (state === "attention") return "Needs attention";
    return "Not reviewed";
  };
  async function saveAnnotation(event: FormEvent) {
    event.preventDefault();
    setBusy("annotation");
    setFeedback("");
    try {
      const updated = await api.annotateMechanics({
        campaign_id: item.campaign_id,
        attempt_id: item.attempt_id || "original",
        variant_id: item.variant_id,
        trade_id: trade,
        evidence_token: detail.trade_evidence_token,
        reviewer_status: status,
        reviewer_notes: notes,
      });
      setDetail(updated);
      const form = mechanicsAnnotationFormState(updated);
      setStatus(form.status);
      setNotes(form.notes);
      setFeedback(`Trade ${trade} review saved.`);
      const unreviewed = (updated.unreviewed_trade_ids || []).map(String);
      const next = (updated.sampled_trade_ids || []).find((id: unknown) =>
        unreviewed.includes(String(id)),
      );
      if (next !== undefined) await selectTrade(String(next));
    } catch (reason) {
      setFeedback(
        reason instanceof Error ? reason.message : "Annotation was not saved",
      );
    } finally {
      setBusy("");
    }
  }
  async function decide(decision: "approve" | "reject") {
    setBusy(decision);
    setFeedback("");
    try {
      const result = await api.decideMechanics({
        campaign_id: item.campaign_id,
        attempt_id: item.attempt_id || "original",
        variant_id: item.variant_id,
        decision,
        reviewer,
        notes: decisionNotes,
      });
      setDetail(result.plan || detail);
      setFeedback(
        decision === "approve"
          ? "Implementation approved for performance testing. Profitability remains unapproved."
          : "Mechanics rejected before performance testing.",
      );
      onResolved();
    } catch (reason) {
      setFeedback(
        reason instanceof Error ? reason.message : "Decision was not recorded",
      );
    } finally {
      setBusy("");
    }
  }
  return (
    <>
      <Notice tone="info" title="What you are approving">
        Only that the implementation matches the frozen specification. No
        profitability judgment belongs in this review.
      </Notice>
      <div className="review-progress-card">
        <div
          className="review-progress-ring"
          style={
            { "--progress": `${progress * 3.6}deg` } as React.CSSProperties
          }
        >
          <span>{progress}%</span>
        </div>
        <div>
          <p className="eyebrow">Required sample</p>
          <h3>
            {completed} of {required || "—"} trades reviewed correctly
          </h3>
          <p>
            The sample starts with five deterministic hash-ranked trades (or
            all trades if fewer exist), then adds only the trades needed to
            cover universal execution lifecycles, warning codes, and resolved
            ambiguities. Duplicate selections are counted once; this attempt
            contains {required || "the governed"} unique sampled trades.
          </p>
        </div>
      </div>
      {(detail.blockers || []).length > 0 && (
        <Notice tone="warning" title="Approval blocked">
          <ul>
            {detail.blockers.map((blocker: string) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
        </Notice>
      )}
      {(detail.sampled_trade_ids || []).length > 0 && (
        <Card className="trade-evidence-selector">
          <div>
            <p className="eyebrow">Trade inspection</p>
            <h3>Select a sampled trade</h3>
            <p>
              The selection controls the frozen evidence and saved annotation
              shown below.
            </p>
          </div>
          <Field label="Sampled trade">
            <select
              aria-label="Sampled trade"
              value={trade}
              disabled={busy === "evidence"}
              onChange={(event) => void selectTrade(event.target.value)}
            >
              {detail.sampled_trade_ids.map((id: unknown) => (
                <option key={String(id)} value={String(id)}>
                  Trade {String(id)} · {tradeReviewLabel(String(id))}
                </option>
              ))}
            </select>
          </Field>
          <div
            className="sample-trade-map"
            aria-label="Sampled trade review status"
          >
            {sampledTradeIds.map((id) => {
              const reviewState = tradeReviewState(id);
              return (
                <button
                  key={id}
                  type="button"
                  className={`${reviewState}${id === trade ? " selected" : ""}`}
                  aria-current={id === trade ? "true" : undefined}
                  aria-label={`Trade ${id}: ${tradeReviewLabel(id)}`}
                  title={`Trade ${id} · ${tradeReviewLabel(id)}`}
                  disabled={busy === "evidence"}
                  onClick={() => void selectTrade(id)}
                >
                  <span aria-hidden="true" />
                  {id}
                </button>
              );
            })}
          </div>
          {(detail.sampling_reasons?.[trade] || []).length > 0 && (
            <div className="sample-selection-reasons">
              <strong>Why trade {trade} is included</strong>
              <ul>
                {detail.sampling_reasons[trade].map((reason: string) => (
                  <li key={reason}>{humanize(reason)}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}
      {sampledTradeIds.length > 0 && (
        <nav className="review-action-bar" aria-label="Sample review navigation">
          <div>
            <strong>
              Trade {selectedTradeIndex + 1} of {sampledTradeIds.length}
            </strong>
            <small>{progress}% of required samples approved correctly</small>
          </div>
          <div>
            <Button
              type="button"
              variant="secondary"
              disabled={!previousTrade || busy === "evidence"}
              onClick={() => previousTrade && void selectTrade(previousTrade)}
            >
              Previous trade
            </Button>
            <Button
              type="button"
              variant="secondary"
              disabled={!nextTrade || busy === "evidence"}
              onClick={() => nextTrade && void selectTrade(nextTrade)}
            >
              Next trade
            </Button>
            <a className="button button-primary" href="#sample-annotation">
              Record review
            </a>
          </div>
        </nav>
      )}
      <TradeEvidence
        evidence={detail.trade_evidence}
        error={detail.trade_evidence_error}
        loading={busy === "evidence"}
      />
      <details className="sample-category-disclosure">
        <summary>
          <span>
            <strong>Why these trades were sampled</strong>
            <small>
              Universal sampler {detail.sampling_policy_version || "policy"} ·{" "}
              {Object.keys(detail.sampling_categories || {}).length} categories
            </small>
          </span>
          <span>Show categories</span>
        </summary>
        <div className="sample-category-grid">
          {Object.entries(detail.sampling_categories || {}).map(
            ([name, ids]: [string, any]) => (
              <Card key={name}>
                <span className="sample-icon">
                  <Icon name="chart" />
                </span>
                <strong>{humanize(name)}</strong>
                <small>
                  {Array.isArray(ids)
                    ? `${ids.length} sampled trade${ids.length === 1 ? "" : "s"}`
                    : "Required sample"}
                </small>
                <StatusBadge value="Evidence generated" />
              </Card>
            ),
          )}
        </div>
      </details>
      <Card className="review-placeholder" id="sample-annotation">
        <div>
          <Icon name="review" />
          <h3>Required sample annotation</h3>
          <p>
            Reconcile each selected trade with the frozen mechanics and
            automated checks before recording a status.
          </p>
        </div>
        {(detail.sampled_trade_ids || []).length ? (
          <form className="annotation-form" onSubmit={saveAnnotation}>
            <Field label="Implementation status">
              <select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
              >
                {[
                  "Correct",
                  "Bug suspected",
                  "Data issue",
                  "Needs deeper review",
                  "False signal",
                  "Exit issue",
                  "Orderflow filter issue",
                ].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </Field>
            <Field label="Review notes">
              <textarea
                rows={3}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </Field>
            <Button
              type="submit"
              disabled={
                busy === "annotation" ||
                !detail.trade_evidence ||
                !detail.trade_evidence_token ||
                String(detail.trade_evidence.trade_id) !== trade
              }
            >
              {busy === "annotation"
                ? "Saving…"
                : "Save annotation and continue"}
            </Button>
          </form>
        ) : (
          <Notice tone="warning">
            No governed sample is available. Generate mechanics evidence first.
          </Notice>
        )}
      </Card>
      <Card className="review-decision-card">
        <h3>Finalize mechanics decision</h3>
        <Field label="Reviewer identity">
          <input
            value={reviewer}
            onChange={(event) => setReviewer(event.target.value)}
          />
        </Field>
        <Field label="Decision notes">
          <textarea
            rows={3}
            value={decisionNotes}
            onChange={(event) => setDecisionNotes(event.target.value)}
          />
        </Field>
        {feedback && (
          <Notice
            tone={
              feedback.includes("not") || feedback.includes("unavailable")
                ? "warning"
                : "success"
            }
          >
            {feedback}
          </Notice>
        )}
        <div className="decision-actions">
          <Button
            variant="danger"
            disabled={!reviewer || !decisionNotes || Boolean(busy)}
            onClick={() => void decide("reject")}
          >
            Reject mechanics
          </Button>
          <Button
            disabled={
              !detail.ready_for_approval ||
              !reviewer ||
              !decisionNotes ||
              Boolean(busy)
            }
            onClick={() => void decide("approve")}
          >
            Approve implementation for testing
          </Button>
        </div>
        {!detail.ready_for_approval && (
          <small>
            Approval unlocks only after every required sample is marked Correct
            and automated blockers are resolved.
          </small>
        )}
      </Card>
      <TechnicalDetails>
        <pre>{JSON.stringify(detail, null, 2)}</pre>
      </TechnicalDetails>
    </>
  );
}

function ExactReviewIdentity({ attemptId }: { attemptId: string }) {
  return (
    <span className="exact-identity review-exact-identity">
      <span>
        Exact ID <code>{attemptId}</code>
      </span>
      <button
        type="button"
        className="copy-id"
        aria-label={`Copy exact attempt ID ${attemptId}`}
        onClick={() => void navigator.clipboard?.writeText(attemptId)}
      >
        Copy
      </button>
    </span>
  );
}

function TradeEvidence({
  evidence,
  error,
  loading,
}: {
  evidence: any;
  error?: string;
  loading: boolean;
}) {
  if (loading) return <Skeleton lines={6} />;
  if (error)
    return (
      <Notice tone="danger" title="Evidence could not be verified">
        {error}. Annotation remains locked.
      </Notice>
    );
  if (!evidence)
    return (
      <Notice tone="warning" title="No inspected evidence">
        Select a governed sampled trade. Annotation stays locked until its
        evidence loads.
      </Notice>
    );
  const trade = evidence.trade || {};
  const transitions = evidence.event_transitions || [];
  const eventLane = evidence.metadata?.validation_lane === "event_replay";
  const evidenceTimeZone = evidence.metadata?.timezone || "America/New_York";
  const entryTimestamp =
    trade.entry_time ??
    trade.entry_timestamp ??
    transitions.find((row: any) =>
      /^(entry_filled|position_opened|trade_opened)$/.test(
        String(row.transition || "").toLowerCase(),
      ),
    )?.timestamp;
  const exitTimestamp =
    trade.exit_time ??
    trade.exit_timestamp ??
    [...transitions]
      .reverse()
      .find((row: any) =>
        /^(trade_closed|position_closed|forced_flatten|exit_filled)$/.test(
          String(row.transition || "").toLowerCase(),
        ),
      )?.timestamp;
  const evidenceIdentityRows = [
    {
      label: "Config SHA-256",
      value: evidence.metadata?.config_hash,
    },
    {
      label: "Input data SHA-256",
      value: evidence.metadata?.input_data_hash,
    },
    {
      label: "Strategy implementation version",
      value: evidence.metadata?.strategy_implementation_version,
    },
    {
      label: "Strategy implementation SHA-256",
      value: evidence.metadata?.strategy_implementation_sha256,
    },
    {
      label: "Certification manifest SHA-256",
      value: evidence.metadata?.strategy_certification_manifest_sha256,
    },
  ].filter(
    (row) => row.value !== null && row.value !== undefined && row.value !== "",
  );
  const strategyPanels = resolveStrategyEvidencePanels(evidence);
  const mechanicsComparison = resolveAdaptiveV18MechanicsComparison(evidence);
  const frozenSetup = resolveFrozenSetup(evidence);
  const qualifyingFootprint = resolveQualifyingFootprint(evidence);
  const hasExplicitTargetEvidence = strategyPanels.some((panel) =>
    panel.rows.some(
      (row) => row.key === "target_1_price" || row.key === "target_2_price",
    ),
  );
  const netPnl = trade.pnl_usd ?? trade.net_pnl;
  const netPnlNumber = Number(netPnl);
  const netPnlTone = Number.isFinite(netPnlNumber)
    ? netPnlNumber > 0
      ? "positive"
      : netPnlNumber < 0
        ? "negative"
        : "neutral"
    : "neutral";
  return (
    <Card className="trade-evidence-card">
      <div className="evidence-heading">
        <div>
          <p className="eyebrow">Frozen implementation evidence</p>
          <h3>Trade {evidence.trade_id}</h3>
          <small className="evidence-timezone">
            All displayed times use {evidenceTimeZone} with an explicit GMT offset.
          </small>
        </div>
        <StatusBadge value={trade.reviewer_status_display || "Unreviewed"} />
      </div>
      <section className="trade-time-summary" aria-label="Trade timing">
        <div className="trade-time-endpoint trade-time-entry">
          <span className="trade-time-marker" aria-hidden="true">
            In
          </span>
          <div>
            <small>Entry timestamp</small>
            <time dateTime={entryTimestamp || undefined}>
              {formatEvidenceValue(entryTimestamp, evidenceTimeZone)}
            </time>
            <span>
              {trade.entry_order_type
                ? `${humanize(trade.entry_order_type)} entry`
                : "Entry fill"}
              {trade.entry_price !== null && trade.entry_price !== undefined
                ? ` · ${formatEvidenceValue(trade.entry_price)}`
                : ""}
            </span>
          </div>
        </div>
        <div className="trade-time-duration">
          <small>Time in trade</small>
          <strong>{formatTradeDuration(entryTimestamp, exitTimestamp)}</strong>
          <span>
            {[trade.contract, trade.session_date].filter(Boolean).join(" · ") ||
              "Session not recorded"}
          </span>
        </div>
        <div className="trade-time-endpoint trade-time-exit">
          <span className="trade-time-marker" aria-hidden="true">
            Out
          </span>
          <div>
            <small>Exit timestamp</small>
            <time dateTime={exitTimestamp || undefined}>
              {formatEvidenceValue(exitTimestamp, evidenceTimeZone)}
            </time>
            <span>
              {trade.exit_reason ? humanize(trade.exit_reason) : "Exit fill"}
              {trade.exit_price !== null && trade.exit_price !== undefined
                ? ` · ${formatEvidenceValue(trade.exit_price)}`
                : ""}
            </span>
          </div>
        </div>
      </section>
      <div className="trade-facts">
        <EvidenceFact label="Direction" value={trade.direction} />
        <EvidenceFact label="Entry" value={formatEvidenceValue(trade.entry_price)} />
        <EvidenceFact label="Stop" value={formatEvidenceValue(trade.stop_price)} />
        {!hasExplicitTargetEvidence && (
          <EvidenceFact label="Target" value={formatEvidenceValue(trade.target_price)} />
        )}
        <EvidenceFact label="Exit" value={formatEvidenceValue(trade.exit_price)} />
        <EvidenceFact label="Exit reason" value={trade.exit_reason} />
        <EvidenceFact
          label="Net P&L (USD · diagnostic only)"
          value={formatUsdPnl(netPnl)}
          tone={netPnlTone}
        />
      </div>
      {frozenSetup && (
        <FrozenSetup summary={frozenSetup} timeZone={evidenceTimeZone} />
      )}
      {qualifyingFootprint && (
        <QualifyingFootprint
          summary={qualifyingFootprint}
          timeZone={evidenceTimeZone}
        />
      )}
      {mechanicsComparison.length > 0 && (
        <MechanicsComparison sections={mechanicsComparison} timeZone={evidenceTimeZone} />
      )}
      <EvidenceDisclosure
        title="Frozen identity and causal feature context"
        description={`${evidenceIdentityRows.length + strategyPanels.reduce((total, panel) => total + panel.rows.length, 0)} immutable evidence fields`}
      >
        <EvidenceList
          title="Frozen evidence identity"
          rows={evidenceIdentityRows.map((row) => ({
            label: row.label,
            value: formatEvidenceValue(row.value),
          }))}
          empty="Frozen evidence identity was not recorded."
        />
        {strategyPanels.map((panel) => (
          <EvidenceList
            key={panel.title}
            title={panel.title}
            rows={panel.rows.map((row) => ({
              label: row.label,
              value: formatEvidenceValue(row.value, evidenceTimeZone),
            }))}
            empty=""
          />
        ))}
      </EvidenceDisclosure>
      <EvidenceReplay
        bars={evidence.bars || []}
        transitions={transitions}
        trade={trade}
        timeZone={evidenceTimeZone}
      />
      {transitions.length ? (
        <EvidenceDisclosure
          title="Complete causal event lifecycle"
          description={`${transitions.length} retained transitions · replay remains visible above`}
        >
          <EvidenceList
            title="Causal event lifecycle"
            rows={transitions.map((row: any) => ({
              label: `${humanize(row.transition || "event")} · event ${formatEvidenceValue(row.event_index)}`,
              value: [
                formatEvidenceValue(row.timestamp, evidenceTimeZone),
                row.price !== null && row.price !== undefined ? `price ${formatEvidenceValue(row.price)}` : null,
                row.stop_price !== null && row.stop_price !== undefined ? `stop ${formatEvidenceValue(row.stop_price)}` : null,
                row.target_price !== null && row.target_price !== undefined ? `target ${formatEvidenceValue(row.target_price)}` : null,
                row.reason,
              ]
                .filter(Boolean)
                .join(" · "),
            }))}
            empty="No causal event transitions were generated."
          />
        </EvidenceDisclosure>
      ) : null}
      <div className={`evidence-panels${eventLane ? " event-evidence-panels" : ""}`}>
        {!eventLane && (
          <EvidenceList
            title="Entry conditions"
            rows={(evidence.condition_checklist || []).map((row: any) => ({
              label: humanize(row.condition),
              value: formatEvidenceValue(row.status),
            }))}
            empty="No condition snapshot was generated."
          />
        )}
        <EvidenceList
          title="Automated checks"
          rows={(evidence.automated_checks || []).map((row: any) => ({
            label: humanize(row.check_name || row.description),
            value: `${String(row.status || "UNKNOWN").toUpperCase()}${
              row.actual !== null && row.actual !== undefined && row.actual !== ""
                ? ` · ${formatAutomatedCheckActual(row.actual)}`
                : ""
            }`,
            status: row.status,
          }))}
          empty="No automated checks were generated."
        />
        {!eventLane && (
          <EvidenceList
            title="Exit path"
            rows={(evidence.exit_path || []).map((row: any) => ({
              label: humanize(row.field),
              value: formatEvidenceValue(row.value, evidenceTimeZone),
            }))}
            empty="No exit-path audit was generated."
          />
        )}
      </div>
      {!eventLane && (evidence.orderflow || []).length > 0 && (
        <EvidenceList
          title="Order-flow reconciliation"
          rows={evidence.orderflow.map((row: any) => ({
            label: row.filter || row.name || row.condition || "Order-flow field",
            value: formatEvidenceValue(
              row.explanation || row.actual || row.status || row.value,
            ),
          }))}
          empty=""
        />
      )}
      <TechnicalDetails>
        <pre>
          {JSON.stringify(
            {
              trade: evidence.trade,
              condition_snapshot: evidence.condition_snapshot,
              strategy_context: evidence.strategy_context,
              event_transitions: evidence.event_transitions,
              exit_audit: evidence.exit_audit,
              annotation: evidence.annotation,
            },
            null,
            2,
          )}
        </pre>
      </TechnicalDetails>
    </Card>
  );
}

function FrozenSetup({
  summary,
  timeZone,
}: {
  summary: FrozenSetupSummary;
  timeZone: string;
}) {
  const burstSize = formatFootprintNumber(summary.burstSize);
  const burstThreshold = formatFootprintNumber(summary.burstThreshold);
  const burstLow = formatFootprintNumber(summary.burstPriceLow);
  const burstHigh = formatFootprintNumber(summary.burstPriceHigh);
  const burstPrice = burstLow === burstHigh ? burstLow : `${burstLow}–${burstHigh}`;
  const hasBurst =
    summary.burstSize !== null &&
    summary.burstSize !== undefined &&
    summary.burstSize !== "";
  return (
    <section className="frozen-setup" aria-labelledby="frozen-setup-heading">
      <div className="frozen-setup-heading">
        <div>
          <p className="eyebrow">Setup at the decision boundary</p>
          <h4 id="frozen-setup-heading">Frozen profile and observed AOI source</h4>
        </div>
        <StatusBadge value={`Edge = ${summary.edgeRole}`} />
      </div>
      <p className="frozen-setup-help">
        These are the immutable profile values used by the trade. The AOI may be
        armed by a large execution, directional delta, a compatible market level,
        or more than one source; the exact observed source is shown below.
      </p>
      <dl className="frozen-setup-grid">
        <div className="frozen-setup-primary">
          <dt>Observed AOI source</dt>
          <dd>{formatEvidenceValue(summary.sourceKinds)}</dd>
        </div>
        <div className="frozen-setup-primary">
          <dt>Exact frozen edge ({summary.edgeRole})</dt>
          <dd>{formatEvidenceValue(summary.edgePrice)}</dd>
        </div>
        <div>
          <dt>Frozen VAH</dt>
          <dd>{formatEvidenceValue(summary.vahPrice)}</dd>
        </div>
        <div>
          <dt>Frozen POC</dt>
          <dd>{formatEvidenceValue(summary.pocPrice)}</dd>
        </div>
        <div>
          <dt>Frozen VAL</dt>
          <dd>{formatEvidenceValue(summary.valPrice)}</dd>
        </div>
        {hasBurst && (
          <>
            <div>
              <dt>Selected 100 ms burst</dt>
              <dd>{burstSize} contracts</dd>
              <small>Required ≥ {burstThreshold}</small>
            </div>
            <div>
              <dt>Burst location</dt>
              <dd>{burstPrice}</dd>
              <small>
                {summary.burstSide
                  ? `Aggressor side ${String(summary.burstSide)}`
                  : "Side not retained"}
              </small>
            </div>
            <div>
              <dt>Burst qualified at</dt>
              <dd>{formatEvidenceValue(summary.burstQualifiedAt, timeZone)}</dd>
            </div>
          </>
        )}
        <div className="frozen-setup-primary">
          <dt>AOI armed / profile frozen at</dt>
          <dd>{formatEvidenceValue(summary.aoiArmedAt, timeZone)}</dd>
        </div>
      </dl>
    </section>
  );
}

function MechanicsComparison({
  sections,
  timeZone,
}: {
  sections: MechanicsComparisonSection[];
  timeZone: string;
}) {
  return (
    <section className="mechanics-comparison" aria-labelledby="mechanics-comparison-heading">
      <div className="mechanics-comparison-heading">
        <div>
          <p className="eyebrow">Implementation review contract</p>
          <h4 id="mechanics-comparison-heading">Configured rule versus observed trade</h4>
          <p>
            Frozen parameters come from the hash-bound variant config. Observed
            values come from this trade&apos;s retained causal strategy trace.
          </p>
        </div>
        <StatusBadge value="v18 evidence" />
      </div>
      <div className="mechanics-comparison-sections">
        {sections.map((section) => (
          <section key={section.title} className="mechanics-comparison-section">
            <div>
              <h5>{section.title}</h5>
              <p>{section.description}</p>
            </div>
            <div className="mechanics-comparison-table" role="table" aria-label={section.title}>
              <div className="mechanics-comparison-row mechanics-comparison-header" role="row">
                <span role="columnheader">Mechanic</span>
                <span role="columnheader">Frozen rule / parameter</span>
                <span role="columnheader">Observed on this trade</span>
              </div>
              {section.rows.map((row) => (
                <div className="mechanics-comparison-row" role="row" key={row.key}>
                  <strong role="cell">{row.label}</strong>
                  <span role="cell">{formatEvidenceValue(row.configured, timeZone)}</span>
                  <span role="cell">{formatEvidenceValue(row.observed, timeZone)}</span>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}

function EvidenceFact({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: unknown;
  tone?: "positive" | "negative" | "neutral";
}) {
  return (
    <div className={`evidence-fact evidence-fact-${tone}`}>
      <small>{label}</small>
      <strong>{formatEvidenceValue(value)}</strong>
    </div>
  );
}

function QualifyingFootprint({
  summary,
  timeZone,
}: {
  summary: QualifyingFootprintSummary;
  timeZone: string;
}) {
  const qualified = summary.routes.filter((route) => route.qualified);
  const outcomeLabel =
    summary.outcome === "qualified"
      ? qualified.length > 1
        ? "Both routes qualified"
        : `${qualified[0]?.label || "Footprint"} qualified`
      : summary.outcome === "not_qualified"
        ? "No route qualified"
        : "Qualification not fully retained";
  return (
    <section className="qualifying-footprint" aria-labelledby="footprint-heading">
      <div className="qualifying-footprint-heading">
        <div>
          <p className="eyebrow">Qualifying footprint</p>
          <h4 id="footprint-heading">Why this value edge became eligible</h4>
          <p>
            The frozen rule is <strong>either route may qualify</strong>. This
            trade retained the observed value and its predeclared threshold for
            each route.
          </p>
        </div>
        <StatusBadge value={outcomeLabel} />
      </div>
      <div className="footprint-rule">
        <span>Qualification rule</span>
        <strong>Large execution</strong>
        <b>OR</b>
        <strong>Top-decile delta</strong>
      </div>
      <div className="footprint-route-grid">
        {summary.routes.map((route) => (
          <FootprintRoute
            key={route.id}
            route={route}
            timeZone={timeZone}
          />
        ))}
      </div>
      <div className="footprint-freeze-context">
        <span>
          <small>Exact frozen edge</small>
          <strong>{formatEvidenceValue(summary.edgePrice)}</strong>
        </span>
        <span>
          <small>Profile frozen at</small>
          <strong>{formatEvidenceValue(summary.frozenAt, timeZone)}</strong>
        </span>
        <span>
          <small>Freeze rule</small>
          <strong>{humanize(summary.definition)}</strong>
        </span>
      </div>
    </section>
  );
}

function FootprintRoute({
  route,
  timeZone,
}: {
  route: QualifyingFootprintRoute;
  timeZone: string;
}) {
  const observed = Number(route.observed);
  const threshold = Number(route.threshold);
  const comparisonAvailable =
    Number.isFinite(observed) && Number.isFinite(threshold);
  const margin = comparisonAvailable ? observed - threshold : null;
  const multiple =
    comparisonAvailable && threshold > 0 ? observed / threshold : null;
  const routeState =
    route.qualified === true
      ? "qualified"
      : route.qualified === false
        ? "not-qualified"
        : "unknown";
  return (
    <article className={`footprint-route footprint-route-${routeState}`}>
      <header>
        <div>
          <span className="footprint-route-dot" aria-hidden="true" />
          <strong>{route.label}</strong>
        </div>
        <span>
          {route.qualified === true
            ? "Qualified"
            : route.qualified === false
              ? "Did not qualify"
              : "Not retained"}
        </span>
      </header>
      <div className="footprint-comparison">
        <span>
          <small>Observed</small>
          <strong>
            {formatFootprintNumber(route.observed)}{" "}
            <em>{route.unit}</em>
          </strong>
        </span>
        <b aria-label="compared with">≥</b>
        <span>
          <small>Required</small>
          <strong>
            {formatFootprintNumber(route.threshold)}{" "}
            <em>{route.unit}</em>
          </strong>
        </span>
      </div>
      {margin !== null && (
        <p className="footprint-margin">
          {margin >= 0 ? "Exceeded" : "Missed"} threshold by{" "}
          <strong>
            {formatFootprintNumber(Math.abs(margin))} {route.unit}
          </strong>
          {multiple !== null
            ? ` · ${multiple.toFixed(2)}× the required value`
            : ""}
        </p>
      )}
      <dl>
        <div>
          <dt>Frozen percentile</dt>
          <dd>{formatFootprintPercentile(route.percentile)}</dd>
        </div>
        <div>
          <dt>Price location</dt>
          <dd>{formatFootprintPriceRange(route)}</dd>
        </div>
        {route.side !== undefined && route.side !== null && route.side !== "" && (
          <div>
            <dt>Recorded side</dt>
            <dd>{String(route.side)}</dd>
          </div>
        )}
        {route.qualifiedAt !== undefined &&
          route.qualifiedAt !== null &&
          route.qualifiedAt !== "" && (
            <div>
              <dt>Qualified at</dt>
              <dd>{formatEvidenceValue(route.qualifiedAt, timeZone)}</dd>
            </div>
          )}
      </dl>
      <small className="footprint-reference">{route.referenceDescription}</small>
    </article>
  );
}

function formatFootprintNumber(value: unknown): string {
  const number = Number(value);
  if (!Number.isFinite(number)) return "Not retained";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 3,
  }).format(number);
}

function formatFootprintPercentile(value: unknown): string {
  const number = Number(value);
  if (!Number.isFinite(number)) return "Not retained";
  const percentage = number <= 1 ? number * 100 : number;
  return `${new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 3,
  }).format(percentage)}th percentile`;
}

function formatFootprintPriceRange(route: QualifyingFootprintRoute): string {
  const low = formatFootprintNumber(route.priceLow);
  const high = formatFootprintNumber(route.priceHigh);
  if (low === "Not retained" && high === "Not retained") return "Not retained";
  if (low === high || high === "Not retained") return low;
  if (low === "Not retained") return high;
  return `${low}–${high}`;
}

function EvidenceDisclosure({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <details className="evidence-disclosure">
      <summary>
        <span>
          <strong>{title}</strong>
          <small>{description}</small>
        </span>
        <span className="disclosure-action">Inspect details</span>
      </summary>
      <div className="evidence-disclosure-body">{children}</div>
    </details>
  );
}

function EvidenceList({
  title,
  rows,
  empty,
}: {
  title: string;
  rows: Array<{ label: string; value: string; status?: string }>;
  empty: string;
}) {
  return (
    <section className="evidence-list">
      <h4>{title}</h4>
      {rows.length ? (
        <div>
          {rows.map((row, index) => (
            <span key={`${row.label}-${index}`}>
              <small>{row.label}</small>
              <strong className={`evidence-${String(row.status || "").toLowerCase()}`}>
                {row.value}
              </strong>
            </span>
          ))}
        </div>
      ) : (
        <p>{empty}</p>
      )}
    </section>
  );
}

function PriceEvidenceChart({
  bars,
  trade,
  timeZone,
  activeTransition,
}: {
  bars: any[];
  trade: any;
  timeZone: string;
  activeTransition?: any;
}) {
  const usable = bars
    .filter(
      (bar) =>
        Number.isFinite(Number(bar.high)) &&
        Number.isFinite(Number(bar.low)) &&
        Number.isFinite(Number(bar.close)),
    )
    .slice(-120);
  if (!usable.length)
    return (
      <Notice tone="warning">
        The governed bar window is missing; price-chart review is unavailable.
      </Notice>
    );
  const reference = [
    ...usable.flatMap((bar) => [Number(bar.high), Number(bar.low)]),
    ...[trade.entry_price, trade.stop_price, trade.target_price, trade.exit_price]
      .map(Number)
      .filter(Number.isFinite),
    ...[activeTransition?.price, activeTransition?.stop_price, activeTransition?.target_price]
      .map(Number)
      .filter(Number.isFinite),
  ];
  const low = Math.min(...reference);
  const high = Math.max(...reference);
  const spread = Math.max(high - low, 0.25);
  const width = 900;
  const height = 300;
  const pad = 24;
  const x = (index: number) =>
    pad + (index * (width - pad * 2)) / Math.max(usable.length - 1, 1);
  const y = (value: number) =>
    pad + ((high - value) * (height - pad * 2)) / spread;
  const candleWidth = Math.max(2, Math.min(8, (width - pad * 2) / usable.length / 1.7));
  const levels = [
    ["Entry", trade.entry_price, "#285e75"],
    ["Stop", trade.stop_price, "#a3342c"],
    ["Target", trade.target_price, "#18724d"],
  ].filter(([, value]) => Number.isFinite(Number(value))) as Array<[
    string,
    number,
    string,
  ]>;
  return (
    <figure className="price-evidence-chart">
      <figcaption>
        <strong>Completed-bar price path</strong>
        <span>
          {formatEvidenceValue(usable[0]?.timestamp, timeZone)} →{" "}
          {formatEvidenceValue(usable.at(-1)?.timestamp, timeZone)}
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Sampled trade completed-bar price chart">
        {levels.map(([label, value, color]) => (
          <g key={label}>
            <line x1={pad} x2={width - pad} y1={y(Number(value))} y2={y(Number(value))} stroke={color} strokeDasharray="8 5" />
            <text x={pad + 4} y={y(Number(value)) - 5} fill={color}>{label} {value}</text>
          </g>
        ))}
        {usable.map((bar, index) => {
          const open = Number.isFinite(Number(bar.open)) ? Number(bar.open) : Number(bar.close);
          const close = Number(bar.close);
          const color = close >= open ? "#18724d" : "#a3342c";
          return (
            <g key={`${bar.timestamp}-${index}`}>
              <line x1={x(index)} x2={x(index)} y1={y(Number(bar.high))} y2={y(Number(bar.low))} stroke={color} />
              <rect x={x(index) - candleWidth / 2} y={Math.min(y(open), y(close))} width={candleWidth} height={Math.max(1.5, Math.abs(y(open) - y(close)))} fill={color} />
            </g>
          );
        })}
        {activeTransition && Number.isFinite(Number(activeTransition.price)) && (
          <g>
            <circle
              cx={x(usable.length - 1)}
              cy={y(Number(activeTransition.price))}
              r="7"
              fill="#7c3aed"
              stroke="#fff"
              strokeWidth="2"
            />
            <text
              x={Math.max(pad, x(usable.length - 1) - 160)}
              y={Math.max(18, y(Number(activeTransition.price)) - 12)}
              fill="#6d28d9"
            >
              {humanize(activeTransition.transition || "event")}
            </text>
          </g>
        )}
      </svg>
    </figure>
  );
}

function EvidenceReplay({
  bars,
  transitions,
  trade,
  timeZone,
}: {
  bars: any[];
  transitions: any[];
  trade: any;
  timeZone: string;
}) {
  const steps = transitions.length
    ? transitions
    : bars.map((bar, index) => ({
        event_index: index,
        timestamp: bar.timestamp,
        transition: "bar_completed",
        price: bar.close,
      }));
  const [step, setStep] = useState(Math.max(0, steps.length - 1));
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    setStep(Math.max(0, steps.length - 1));
    setPlaying(false);
  }, [bars, transitions]);
  useEffect(() => {
    if (!playing || !steps.length) return;
    const timer = window.setInterval(() => {
      setStep((current) => {
        if (current >= steps.length - 1) {
          setPlaying(false);
          return current;
        }
        return current + 1;
      });
    }, 550);
    return () => window.clearInterval(timer);
  }, [playing, steps.length]);
  if (!steps.length && !bars.length)
    return (
      <Notice tone="warning">
        Governed bars and event transitions are missing; replay is unavailable.
      </Notice>
    );
  const active = steps[Math.min(step, steps.length - 1)];
  const activeTime = new Date(String(active?.timestamp || "")).getTime();
  const visibleBars = Number.isFinite(activeTime)
    ? bars.filter(
        (bar) => new Date(String(bar.timestamp || "")).getTime() <= activeTime,
      )
    : bars.slice(0, Math.max(1, step + 1));
  return (
    <section className="evidence-replay">
      <div className="replay-toolbar">
        <div>
          <p className="eyebrow">Native governed replay</p>
          <h4>
            {humanize(active?.transition || "completed bar")} · step{" "}
            {Math.min(step + 1, steps.length)} of {steps.length}
          </h4>
          <small>
            {formatEvidenceValue(active?.timestamp, timeZone)}
            {active?.event_index !== undefined
              ? ` · source event ${formatEvidenceValue(active.event_index)}`
              : ""}
          </small>
        </div>
        <div className="replay-buttons">
          <button type="button" onClick={() => setStep(0)} disabled={step === 0}>
            First
          </button>
          <button
            type="button"
            onClick={() => setStep((value) => Math.max(0, value - 1))}
            disabled={step === 0}
          >
            Previous
          </button>
          <button type="button" onClick={() => setPlaying((value) => !value)}>
            {playing ? "Pause" : "Play"}
          </button>
          <button
            type="button"
            onClick={() => setStep((value) => Math.min(steps.length - 1, value + 1))}
            disabled={step >= steps.length - 1}
          >
            Next
          </button>
        </div>
      </div>
      <input
        className="replay-slider"
        aria-label="Replay step"
        type="range"
        min="0"
        max={Math.max(0, steps.length - 1)}
        value={step}
        onChange={(event) => {
          setPlaying(false);
          setStep(Number(event.target.value));
        }}
      />
      {bars.length ? (
        <PriceEvidenceChart
          bars={visibleBars.length ? visibleBars : bars.slice(0, 1)}
          trade={trade}
          timeZone={timeZone}
          activeTransition={active}
        />
      ) : (
        <EventPricePath transitions={steps.slice(0, step + 1)} timeZone={timeZone} />
      )}
      {active && (
        <dl className="core-grid-parameters">
          {Object.entries(active)
            .filter(
              ([name, value]) =>
                !["timestamp", "transition"].includes(name) &&
                value !== null &&
                value !== undefined &&
                value !== "",
            )
            .slice(0, 12)
            .map(([name, value]) => (
              <div key={name}>
                <dt>{humanize(name)}</dt>
                <dd>{formatEvidenceValue(value, timeZone)}</dd>
              </div>
            ))}
        </dl>
      )}
    </section>
  );
}

function EventPricePath({
  transitions,
  timeZone,
}: {
  transitions: any[];
  timeZone: string;
}) {
  const priced = transitions.filter((row) =>
    Number.isFinite(Number(row.price)),
  );
  if (!priced.length)
    return (
      <Notice tone="warning">
        These governed transitions do not retain prices; the event fields below
        remain available for causal review.
      </Notice>
    );
  const values = priced.map((row) => Number(row.price));
  const low = Math.min(...values);
  const high = Math.max(...values);
  const spread = Math.max(high - low, 0.25);
  const width = 900;
  const height = 240;
  const pad = 24;
  const points = priced
    .map((row, index) => {
      const x =
        pad + (index * (width - 2 * pad)) / Math.max(priced.length - 1, 1);
      const y = pad + ((high - Number(row.price)) * (height - 2 * pad)) / spread;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <figure className="price-evidence-chart">
      <figcaption>
        <strong>Causal trade-event price path</strong>
        <span>
          {formatEvidenceValue(priced[0].timestamp, timeZone)} →{" "}
          {formatEvidenceValue(priced.at(-1).timestamp, timeZone)}
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Causal event price path">
        <polyline points={points} fill="none" stroke="#0d5962" strokeWidth="3" />
        {priced.map((row, index) => {
          const x =
            pad + (index * (width - 2 * pad)) / Math.max(priced.length - 1, 1);
          const y =
            pad + ((high - Number(row.price)) * (height - 2 * pad)) / spread;
          return (
            <circle
              key={`${row.event_index}-${index}`}
              cx={x}
              cy={y}
              r={index === priced.length - 1 ? 6 : 3}
              fill={index === priced.length - 1 ? "#7c3aed" : "#0d5962"}
            />
          );
        })}
      </svg>
    </figure>
  );
}

function formatEvidenceValue(value: unknown, timeZone?: string): string {
  if (value === null || value === undefined || value === "") return "Not recorded";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (timeZone && typeof value === "string" && /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(value)) {
    return formatEvidenceTimestamp(value, timeZone);
  }
  return String(value);
}

export function formatUsdPnl(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not recorded";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "Not recorded";
  const formatted = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Math.abs(amount));
  if (amount > 0) return `+${formatted}`;
  if (amount < 0) return `-${formatted}`;
  return formatted;
}

export function formatEvidenceTimestamp(value: string, timeZone: string): string {
  const normalized = value.replace(" ", "T");
  const instant = new Date(normalized);
  if (Number.isNaN(instant.getTime())) return value;
  const fraction = value.match(/\.(\d+)/)?.[1];
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
    timeZoneName: "shortOffset",
  }).formatToParts(instant);
  const fields = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const subsecond = fraction ? `.${fraction}` : "";
  return `${fields.year}-${fields.month}-${fields.day} ${fields.hour}:${fields.minute}:${fields.second}${subsecond} ${
    fields.timeZoneName || timeZone
  }`;
}

export function formatTradeDuration(
  entryTimestamp: unknown,
  exitTimestamp: unknown,
): string {
  if (!entryTimestamp || !exitTimestamp) return "Not recorded";
  const entry = new Date(String(entryTimestamp).replace(" ", "T")).getTime();
  const exit = new Date(String(exitTimestamp).replace(" ", "T")).getTime();
  if (!Number.isFinite(entry) || !Number.isFinite(exit) || exit < entry) {
    return "Not recorded";
  }
  const totalSeconds = Math.max(0, Math.round((exit - entry) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function formatAutomatedCheckActual(value: unknown): string {
  const text = formatEvidenceValue(value);
  if (/^[a-f0-9]{32,}$/i.test(text)) {
    return `${text.slice(0, 10)}…${text.slice(-8)}`;
  }
  return text.length > 96 ? `${text.slice(0, 93)}…` : text;
}

function CandidateReview({
  item,
  onResolved,
}: {
  item: any;
  onResolved: () => void;
}) {
  const valid = item.valid !== false;
  const [reviewer, setReviewer] = useState("");
  const [decision, setDecision] = useState("needs_manual_review");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const result = item.result_bundle || item;
  const metrics = item.metrics || result.metrics || {};
  const criteria = item.stage_criteria || result.stage_criteria || [];
  const previews = result.artifact_previews || {};
  const destinationSpecific = item.eligibility_basis === "destination_specific_pass";
  useEffect(() => {
    api
      .settings()
      .then((settings) =>
        setReviewer((current) => current || settings.reviewer_identity || ""),
      )
      .catch(() => undefined);
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFeedback("");
    try {
      await api.decideCandidate({
        review_id: item.review_id,
        evidence_token: item.evidence_token,
        reviewer,
        decision,
        notes,
      });
      setFeedback("Independent candidate decision recorded.");
      onResolved();
    } catch (reason) {
      setFeedback(
        reason instanceof Error ? reason.message : "Decision was not recorded",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Notice
        tone={valid ? "warning" : "danger"}
        title={
          valid
            ? destinationSpecific
              ? `Profile PASS remains candidate-only · ${item.account_profile_id}@${item.account_profile_version}`
              : "Generic PASS remains candidate-only"
            : "Finalization is incomplete or hash-invalid"
        }
      >
        {item.verdict_message ||
          item.error ||
          "A separately identified reviewer must inspect the governed evidence before lifecycle promotion."}
      </Notice>
      <Card className="candidate-checklist">
        <h3>Independent sign-off requires</h3>
        <ul>
          {[
            "Scientific-validity PASS",
            destinationSpecific
              ? `PASS for the exact ${item.account_profile_id}@${item.account_profile_version} assessment`
              : "Generic investment-quality PASS",
            "Strict ResultBundleV2 validation",
            "Complete immutable finalization hashes",
            "A reviewer different from the mechanics researcher",
            "Explicit notes and candidate-only wording",
          ].map((label) => (
            <li key={label}>
              <Icon name="check" />
              {label}
            </li>
          ))}
        </ul>
      </Card>
      <Card className="candidate-result-evidence">
        <p className="eyebrow">Authoritative ResultBundleV2</p>
        <h3>Required metrics</h3>
        <div className="metrics-table">
          {Object.entries(metrics).map(([name, value]: [string, any]) => (
            <div key={name}>
              <span>{humanize(name)}</span>
              <strong>{formatEvidenceValue(value?.value ?? value)}</strong>
              {value?.reason && <small>{value.reason}</small>}
            </div>
          ))}
        </div>
      </Card>
      <Card className="candidate-result-evidence">
        <h3>Stage criteria · actual versus required</h3>
        <div className="criteria-list">
          {criteria.map((criterion: any, index: number) => (
            <div key={index}>
              <span>
                <strong>{humanize(criterion.stage)}</strong>
                <small>{humanize(criterion.metric)}</small>
              </span>
              <span>
                {formatEvidenceValue(criterion.actual?.value ?? criterion.actual)} {criterion.operator}{" "}
                {formatEvidenceValue(criterion.threshold?.value ?? criterion.threshold)}
              </span>
              <StatusBadge value={criterion.result} kind="scientific" />
            </div>
          ))}
        </div>
      </Card>
      {Object.keys(previews).length > 0 && (
        <ResultArtifactEvidence previews={previews} />
      )}
      <Card className="review-placeholder">
        <div>
          <Icon name="shield" />
          <h3>Candidate decision</h3>
          <p>
            Sign only after inspecting the finalized result and confirming that
            PASS means candidate strategy only.
          </p>
        </div>
        <form className="candidate-form" onSubmit={submit}>
          <Field label="Independent reviewer identity">
            <input
              value={reviewer}
              onChange={(event) => setReviewer(event.target.value)}
              required
            />
          </Field>
          <Field label="Decision">
            <select
              value={decision}
              onChange={(event) => setDecision(event.target.value)}
            >
              <option value="needs_manual_review">Needs manual review</option>
              <option value="approved_candidate">
                Approve as candidate only
              </option>
              <option value="rejected">Reject candidate</option>
            </select>
          </Field>
          <Field label="Review notes">
            <textarea
              rows={4}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              required
            />
          </Field>
          {feedback && (
            <Notice tone={feedback.includes("recorded") ? "success" : "danger"}>
              {feedback}
            </Notice>
          )}
          <Button
            type="submit"
            disabled={!valid || !item.evidence_token || busy || !reviewer || !notes}
          >
            {busy ? "Recording…" : "Record independent decision"}
          </Button>
        </form>
      </Card>
      <TechnicalDetails>
        <pre>{JSON.stringify(item, null, 2)}</pre>
      </TechnicalDetails>
    </>
  );
}

function IndexedAttention({ item }: { item: any }) {
  return (
    <>
      <Notice tone="warning" title="Responsible next action">
        {item.next_action ||
          item.blocker ||
          item.error ||
          "Inspect preserved evidence and choose an explicit governed follow-up. Never replay this attempt."}
      </Notice>
      <Card className="review-placeholder">
        <Icon name="warning" />
        <h3>
          {humanize(item.operational_state || item.status || "Needs attention")}
        </h3>
        <p>
          Operational state and scientific verdict remain separate. Resolve the
          cited blocker without changing historical evidence.
        </p>
      </Card>
      <TechnicalDetails>
        <pre>{JSON.stringify(item, null, 2)}</pre>
      </TechnicalDetails>
    </>
  );
}
