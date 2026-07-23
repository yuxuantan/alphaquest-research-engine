import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
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

type ReviewGroups = {
  items: ReviewTask[];
  mechanics: ReviewTask[];
  candidate: ReviewTask[];
};

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
  const [type, setType] = useState<keyof ReviewGroups>(
    requestedType === "candidate" || requestedType === "items"
      ? requestedType
      : "mechanics",
  );
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
  function chooseType(value: keyof ReviewGroups) {
    setType(value);
    setSearchParams({ type: value }, { replace: true });
  }
  const list = data[type];
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
          count={data.mechanics.length}
          label="Mechanics reviews"
          onClick={() => chooseType("mechanics")}
        />
        <QueueButton
          selected={type === "candidate"}
          icon="shield"
          count={data.candidate.length}
          label="Candidate sign-offs"
          onClick={() => chooseType("candidate")}
        />
        <QueueButton
          selected={type === "items"}
          icon="warning"
          count={data.items.length}
          label="Indexed attention"
          onClick={() => chooseType("items")}
        />
      </div>
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
                    {task.attempt_id || humanize(task.verdict)}
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
                  {item.attempt_id || item.run_id || "Governed evidence"}
                </p>
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
  onClick,
}: {
  selected: boolean;
  icon: "review" | "shield" | "warning";
  count: number;
  label: string;
  onClick: () => void;
}) {
  return (
    <button className={selected ? "selected" : ""} onClick={onClick}>
      <span>
        <Icon name={icon} />
      </span>
      <strong>{count}</strong>
      <small>{label}</small>
    </button>
  );
}

function MechanicsReview({
  item,
  onResolved,
}: {
  item: any;
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
    setFeedback("");
    api
      .mechanicsReview(
        item.campaign_id,
        item.attempt_id || "original",
        item.variant_id,
      )
      .then((value) => {
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
      })
      .catch((reason) =>
        setFeedback(
          reason instanceof Error
            ? reason.message
            : "Evidence detail unavailable",
        ),
      );
  }, [identity]);
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
            Every automated check and required category must be resolved before
            approval.
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
      <TradeEvidence
        evidence={detail.trade_evidence}
        error={detail.trade_evidence_error}
        loading={busy === "evidence"}
      />
      <Card className="review-placeholder">
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
            <div className="form-grid two">
              <Field label="Sampled trade">
                <select
                  value={trade}
                  onChange={(event) => void selectTrade(event.target.value)}
                >
                  {detail.sampled_trade_ids.map((id: unknown) => (
                    <option key={String(id)} value={String(id)}>
                      Trade {String(id)}
                    </option>
                  ))}
                </select>
              </Field>
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
            </div>
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
  const strategyContext = evidence.strategy_context || {};
  const eventLane = evidence.metadata?.validation_lane === "event_replay";
  const evidenceTimeZone = evidence.metadata?.timezone || "America/New_York";
  const traceFields = [
    "aoi_side",
    "aoi_box_low",
    "aoi_box_high",
    "aoi_width_points",
    "aoi_categories",
    "aoi_confluences",
    "aoi_lineage_mode",
    "aoi_exact_fingerprint",
    "aoi_eligible_timestamp",
    "aoi_tap_timestamp",
    "trigger_kind",
    "trigger_value",
    "bubble_qualified_timestamp",
    "order_armed_timestamp",
    "entry_trigger_price",
    "initial_stop_price",
    "risk_points",
    "entry_profile_poc",
    "entry_profile_vah",
    "entry_profile_val",
    "midpoint_activated",
    "midpoint_activated_at",
  ].filter((field) => strategyContext[field] !== undefined && strategyContext[field] !== null);
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
      <div className="trade-facts">
        <EvidenceFact label="Direction" value={trade.direction} />
        <EvidenceFact label="Entry" value={formatEvidenceValue(trade.entry_price)} />
        <EvidenceFact label="Stop" value={formatEvidenceValue(trade.stop_price)} />
        <EvidenceFact label="Target" value={formatEvidenceValue(trade.target_price)} />
        <EvidenceFact label="Exit" value={formatEvidenceValue(trade.exit_price)} />
        <EvidenceFact label="Exit reason" value={trade.exit_reason} />
      </div>
      {transitions.length ? (
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
      ) : (
        <PriceEvidenceChart
          bars={evidence.bars || []}
          trade={trade}
          timeZone={evidenceTimeZone}
        />
      )}
      {traceFields.length > 0 && (
        <EvidenceList
          title="AOI and trigger trace"
          rows={traceFields.map((field) => ({
            label:
              field === "aoi_eligible_timestamp"
                ? "Exact AOI became valid"
                : humanize(field),
            value: formatEvidenceValue(strategyContext[field], evidenceTimeZone),
          }))}
          empty=""
        />
      )}
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
            label: row.check_name || row.description,
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

function EvidenceFact({ label, value }: { label: string; value: unknown }) {
  return (
    <div>
      <small>{label}</small>
      <strong>{formatEvidenceValue(value)}</strong>
    </div>
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
}: {
  bars: any[];
  trade: any;
  timeZone: string;
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
            ? "PASS remains candidate-only"
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
