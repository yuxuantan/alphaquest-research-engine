import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { Icon } from "../components/Icons";
import {
  Button,
  Card,
  EmptyState,
  Field,
  Metric,
  Notice,
  PageHeader,
  Skeleton,
  StatusBadge,
  TechnicalDetails,
  formatDate,
  humanize,
} from "../components/UI";
import { useStudio } from "../state";

const sections = [
  "overview",
  "protocol",
  "mechanics",
  "testing",
  "results",
  "history",
];

export function CampaignPage() {
  const { campaignId = "", section = "overview" } = useParams();
  const navigate = useNavigate();
  const current = sections.includes(section) ? section : "overview";
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    setLoading(true);
    api
      .campaign(campaignId)
      .then(setDetail)
      .catch((reason) =>
        setError(
          reason instanceof Error ? reason.message : "Campaign unavailable",
        ),
      )
      .finally(() => setLoading(false));
  }, [campaignId]);
  if (loading)
    return (
      <div className="page">
        <Skeleton lines={10} />
      </div>
    );
  if (error || !detail)
    return (
      <div className="page page-narrow">
        <Notice tone="danger" title="Campaign unavailable">
          {error}
        </Notice>
        <Link className="button button-secondary" to="/research">
          Return to research
        </Link>
      </div>
    );
  const campaign = detail.campaign || {};
  const matrix = detail.stage_matrix || [];
  const verdicts = matrix.map(
    (row: any) => row["research verdict"] || row.research_verdict || "PENDING",
  );
  return (
    <div className="page campaign-page">
      <Link className="back-link" to="/research">
        ← All research
      </Link>
      <PageHeader
        eyebrow={`${campaign.instrument || campaign.symbol || "Futures"} · ${campaign.timeframe || "Completed bars"}`}
        title={campaign.title || campaignId}
        description={
          detail.recommended_action || "Review the governed campaign state."
        }
        actions={
          <div className="header-statuses">
            <StatusBadge
              value={campaign.workflow_status || campaign.lifecycle || "Active"}
            />
            {verdicts.some((v: string) => v === "PASS") && (
              <StatusBadge
                value="Candidate review required"
                kind="scientific"
              />
            )}
          </div>
        }
      />
      {!campaign.studio_managed && (
        <Notice tone="warning" title="Developer-managed research">
          {campaign.workflow_blocker ||
            "This source predates complete Studio authoring contracts. Novice actions remain blocked."}
        </Notice>
      )}
      <nav className="campaign-tabs" aria-label="Campaign sections">
        {sections.map((item) => (
          <button
            className={current === item ? "active" : ""}
            key={item}
            onClick={() => navigate(`/research/${campaignId}/${item}`)}
          >
            {humanize(item)}
          </button>
        ))}
      </nav>
      {current === "overview" && <CampaignOverview detail={detail} />}{" "}
      {current === "protocol" && <Protocol detail={detail} />}{" "}
      {current === "mechanics" && <Mechanics detail={detail} />}{" "}
      {current === "testing" && (
        <Testing
          detail={detail}
          onRefresh={() => api.campaign(campaignId).then(setDetail)}
        />
      )}{" "}
      {current === "results" && <Results detail={detail} />}{" "}
      {current === "history" && (
        <History
          detail={detail}
          onRefresh={() => api.campaign(campaignId).then(setDetail)}
        />
      )}{" "}
    </div>
  );
}

function CampaignOverview({ detail }: { detail: any }) {
  const matrix = detail.stage_matrix || [];
  const failures = matrix.filter(
    (row: any) => (row["research verdict"] || row.research_verdict) === "FAIL",
  ).length;
  const unresolved = matrix.filter((row: any) =>
    ["PENDING", "NEEDS MANUAL REVIEW"].includes(
      row["research verdict"] || row.research_verdict,
    ),
  ).length;
  return (
    <>
      <section className="metric-grid campaign-metrics">
        <Metric
          label="Frozen variants"
          value={detail.campaign?.variant_count || 0}
          detail="Maximum five, one at a time"
        />
        <Metric
          label="Scientific failures"
          value={failures}
          detail="Stopped at first failed gate"
        />
        <Metric
          label="Unresolved"
          value={unresolved}
          detail="Evidence or review needed"
        />
        <Metric
          label="Attempts"
          value={(detail.attempts || []).length}
          detail="Immutable lineage"
        />
      </section>
      <Card className="next-action-card">
        <span>
          <Icon name="arrow" />
        </span>
        <div>
          <p className="eyebrow">Recommended next action</p>
          <h2>{detail.recommended_action}</h2>
          <p>AlphaQuest never replays or changes an attempt silently.</p>
        </div>
      </Card>
      <StageMatrix rows={matrix} />
      <Card className="candidate-rule">
        <Icon name="shield" />
        <div>
          <strong>PASS means candidate strategy only</strong>
          <p>
            A separately identified reviewer must sign candidate review before
            lifecycle promotion. Paper/live incubation still follows.
          </p>
        </div>
      </Card>
    </>
  );
}

function StageMatrix({ rows }: { rows: any[] }) {
  return (
    <section className="result-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Failure-first evidence</p>
          <h2>Sequential variant stage matrix</h2>
        </div>
      </div>
      {rows.length === 0 ? (
        <EmptyState
          icon="chart"
          title="No staged results yet"
          body="Mechanics evidence and approval must complete before performance testing."
        />
      ) : (
        <div
          className="stage-matrix"
          role="table"
          aria-label="Sequential variant stage matrix"
        >
          <div className="stage-row stage-head" role="row">
            <span>Variant</span>
            <span>Scientific verdict</span>
            <span>Operational state</span>
            <span>First failed or unresolved gate</span>
          </div>
          {rows.map((row: any, index) => (
            <div className="stage-row" role="row" key={row.variant || index}>
              <strong>{row.variant || `v0${index + 1}`}</strong>
              <StatusBadge
                value={row["research verdict"] || row.research_verdict}
                kind="scientific"
              />
              <StatusBadge
                value={row["operational state"] || row.operational_state}
                kind="operational"
              />
              <span>
                {humanize(
                  row["first failed or unresolved gate"] ||
                    row.first_failed_gate ||
                    row.failed_stage ||
                    "Awaiting evidence",
                )}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function Protocol({ detail }: { detail: any }) {
  const c = detail.campaign || {};
  return (
    <div className="detail-grid">
      <Card>
        <p className="eyebrow">Frozen source</p>
        <h2>{c.title}</h2>
        <dl className="compact-dl">
          <div>
            <dt>Market</dt>
            <dd>{c.instrument || c.symbol}</dd>
          </div>
          <div>
            <dt>Timeframe</dt>
            <dd>{c.timeframe}</dd>
          </div>
          <div>
            <dt>Lifecycle</dt>
            <dd>{humanize(c.lifecycle)}</dd>
          </div>
          <div>
            <dt>Ownership</dt>
            <dd>{c.studio_managed ? "Studio managed" : "Developer managed"}</dd>
          </div>
        </dl>
      </Card>
      <Card>
        <p className="eyebrow">Governance state</p>
        <Notice tone={c.studio_managed ? "success" : "warning"}>
          {c.studio_managed
            ? "Authoring manifest and frozen strategy specification are present."
            : c.workflow_blocker || "Manual review required."}
        </Notice>
        <TechnicalDetails>
          <pre>{JSON.stringify(c, null, 2)}</pre>
        </TechnicalDetails>
      </Card>
    </div>
  );
}

function Mechanics({ detail }: { detail: any }) {
  const unresolved = (detail.stage_matrix || []).filter(
    (row: any) =>
      !["PASS", "FAIL"].includes(
        row["research verdict"] || row.research_verdict,
      ),
  );
  return (
    <>
      <Notice
        tone="info"
        title="Mechanics approval is not profitability approval"
      >
        Review verifies that each implementation matches the frozen
        specification and required samples.
      </Notice>
      <div className="variant-review-grid">
        {Array.from({ length: detail.campaign?.variant_count || 0 }, (_, index) => {
          const row = (detail.stage_matrix || [])[index] || {};
          return (
            <Card key={index}>
              <div className="variant-review-head">
                <span>v0{index + 1}</span>
                <StatusBadge
                  value={row["operational state"] || "Not reviewed"}
                />
              </div>
              <h3>Frozen mechanics</h3>
              <p>
                {row["first failed or unresolved gate"] ||
                  "Generate evidence, inspect required samples, and record implementation correctness."}
              </p>
              <Link className="button button-secondary" to="/reviews">
                Open review inbox
              </Link>
            </Card>
          );
        })}
      </div>
      {unresolved.length === 0 && (
        <Notice tone="success">
          Every currently declared variant has terminal scientific evidence.
        </Notice>
      )}
    </>
  );
}

function Testing({
  detail,
  onRefresh,
}: {
  detail: any;
  onRefresh: () => Promise<any>;
}) {
  const campaign = detail.campaign || {};
  const attempts = detail.attempts || [
    { attempt_id: "original", attempt_kind: "original" },
  ];
  const [attempt, setAttempt] = useState(
    attempts.at(-1)?.attempt_id || "original",
  );
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState("");
  const mechanicsGate = detail.mechanics_approval?.[attempt] || {
    all_approved: false,
    approved_count: 0,
    required_count: detail.campaign?.variant_count || 1,
  };
  async function queue(kind: "mechanics" | "run") {
    setBusy(kind);
    setFeedback("");
    try {
      const result =
        kind === "mechanics"
          ? await api.queueMechanics(campaign.campaign_id, attempt)
          : await api.queueRun(campaign.campaign_id, attempt);
      setFeedback(`${result.jobs?.length || 0} current-variant job queued. Repeated submission is idempotent.`);
      await onRefresh();
    } catch (reason) {
      setFeedback(
        reason instanceof Error ? reason.message : "Submission blocked",
      );
    } finally {
      setBusy("");
    }
  }
  return (
    <div className="testing-layout">
      <Card className="form-section">
        <div className="form-section-heading">
          <span>01</span>
          <div>
            <h2>Select immutable attempt</h2>
            <p>Interrupted or completed attempts are never replayed.</p>
          </div>
        </div>
        <FieldLike label="Attempt identity">
          <select value={attempt} onChange={(e) => setAttempt(e.target.value)}>
            {attempts.map((item: any) => (
              <option key={item.attempt_id} value={item.attempt_id}>
                {item.attempt_id} · {humanize(item.attempt_kind || "Original")}
              </option>
            ))}
          </select>
        </FieldLike>
        {feedback && (
          <Notice
            tone={
              feedback.includes("blocked") || feedback.includes("required")
                ? "warning"
                : "success"
            }
          >
            {feedback}
          </Notice>
        )}
        <div className="action-stack">
          <Button
            onClick={() => void queue("mechanics")}
            disabled={Boolean(busy)}
          >
            {busy === "mechanics"
              ? "Queuing…"
              : "Generate mechanics evidence · current variant"}
          </Button>
          {mechanicsGate.all_approved ? (
            <Button
              variant="secondary"
              onClick={() => void queue("run")}
              disabled={Boolean(busy)}
            >
              {busy === "run" ? "Queuing…" : "Run full test suite · current variant"}
            </Button>
          ) : (
            <Notice tone="warning" title="Performance testing remains hidden">
              The current variant needs a hash-bound manual review using fixed default parameters, five deterministic random entries (or all if fewer exist), and all required risk cases before performance testing.
            </Notice>
          )}
        </div>
      </Card>
      <Card className="guardrail-card">
        <Icon name="shield" />
        <h3>Submission guardrails</h3>
        <ul>
          <li>
            Full campaign, data, config, and approval preflight runs first.
          </li>
          <li>Hash drift blocks before attempt reservation.</li>
          <li>Each variant stops at its first scientific failure.</li>
          <li>A later variant unlocks only after the current variant is manually reviewed and scientifically fails.</li>
          <li>Browser closure never stops the local worker.</li>
        </ul>
      </Card>
      <SequentialVariantPanel detail={detail} onRefresh={onRefresh} />
    </div>
  );
}

function SequentialVariantPanel({
  detail,
  onRefresh,
}: {
  detail: any;
  onRefresh: () => Promise<any>;
}) {
  const campaign = detail.campaign || {};
  const state = detail.next_variant || {};
  const [proposal, setProposal] = useState<any>(null);
  const [analysis, setAnalysis] = useState("");
  const [researcher, setResearcher] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function prepare() {
    setBusy(true);
    setMessage("");
    try {
      setProposal(await api.nextVariant(campaign.campaign_id));
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Next variant is blocked");
    } finally {
      setBusy(false);
    }
  }

  async function append() {
    setBusy(true);
    setMessage("");
    try {
      await api.appendNextVariant(campaign.campaign_id, {
        variant: proposal.variant,
        failure_analysis: analysis,
        created_by: researcher,
      });
      setProposal(null);
      setAnalysis("");
      setMessage("The next variant is frozen. Generate mechanics evidence before any performance test.");
      await onRefresh();
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : "Variant creation was blocked");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="form-section">
      <div className="form-section-heading">
        <span>02</span>
        <div>
          <h2>Failure-informed next variant</h2>
          <p>Only a manually reviewed FAIL unlocks another mechanic. The campaign stops after five variants.</p>
        </div>
      </div>
      {!state.eligible && (
        <Notice tone="info">
          {(state.blockers || ["The current variant must finish first."]).join(" · ")}
        </Notice>
      )}
      {message && <Notice tone={message.includes("blocked") ? "warning" : "success"}>{message}</Notice>}
      {state.eligible && !proposal && (
        <Button disabled={busy} onClick={() => void prepare()}>
          {busy ? "Preparing…" : `Prepare ${state.next_variant_id}`}
        </Button>
      )}
      {proposal && (
        <div className="action-stack">
          <Notice tone="warning" title={`${proposal.variant.variant_id} proposed mechanic`}>
            {proposal.variant.mechanic_rationale}
          </Notice>
          <Field
            label="Failure analysis"
            hint={`${analysis.length}/80 characters minimum. Explain what failed and why this remains the same economic edge.`}
          >
            <textarea rows={5} value={analysis} onChange={(event) => setAnalysis(event.target.value)} />
          </Field>
          <Field label="Researcher identity">
            <input value={researcher} onChange={(event) => setResearcher(event.target.value)} />
          </Field>
          <Button disabled={busy || analysis.length < 80 || !researcher.trim()} onClick={() => void append()}>
            {busy ? "Freezing…" : `Confirm and freeze ${proposal.variant.variant_id}`}
          </Button>
        </div>
      )}
    </Card>
  );
}

function Results({ detail }: { detail: any }) {
  const rows = detail.stage_matrix || [];
  const latest = detail.latest_results || {};
  const [selected, setSelected] = useState(rows[0]?.variant || "v01");
  const result =
    latest[selected] || rows.find((row: any) => row.variant === selected) || {};
  const verdict =
    result["research verdict"] ||
    result.research_verdict ||
    result.verdict ||
    "PENDING";
  const criteria = result.stage_criteria || [];
  const metrics = result.metrics || {};
  const artifactPreviews = result.artifact_previews || {};
  return (
    <>
      <StageMatrix rows={rows} />
      {rows.length > 0 && (
        <section className="result-detail">
          <div className="result-toolbar">
            <h2>Inspect governed result</h2>
            <select
              aria-label="Variant result"
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              {rows.map((row: any) => (
                <option key={row.variant} value={row.variant}>
                  {row.variant}
                </option>
              ))}
            </select>
          </div>
          <Card
            className={`verdict-card verdict-${String(verdict).toLowerCase().replaceAll(" ", "-")}`}
          >
            <div>
              <p className="eyebrow">Scientific verdict</p>
              <h2>{verdict}</h2>
            </div>
            <p>
              {verdict === "PASS"
                ? "Candidate strategy only. Independent sign-off and incubation remain required."
                : verdict === "FAIL"
                  ? `Stopped at ${humanize(result.failed_stage || result["first failed or unresolved gate"])}. Review actual versus required evidence before any follow-up.`
                  : "Missing or unresolved evidence must be addressed by the named reviewer."}
            </p>
          </Card>
          {criteria.length > 0 && (
            <Card>
              <h3>Stage criteria · actual versus required</h3>
              <div className="criteria-list">
                {criteria.map((item: any, index: number) => (
                  <div key={index}>
                    <span>
                      <strong>{humanize(item.stage)}</strong>
                      <small>{humanize(item.metric)}</small>
                    </span>
                    <span>
                      {displayMetric(item.actual)} {item.operator || ""}{" "}
                      {displayMetric(item.threshold)}
                    </span>
                    <StatusBadge value={item.result} kind="scientific" />
                  </div>
                ))}
              </div>
            </Card>
          )}
          {Object.keys(metrics).length > 0 && (
            <Card>
              <h3>Required metrics</h3>
              <div className="metrics-table">
                {Object.entries(metrics).map(([name, value]: [string, any]) => (
                  <div key={name}>
                    <span>{humanize(name)}</span>
                    <strong>{displayMetric(value)}</strong>
                    {value?.reason && <small>{value.reason}</small>}
                  </div>
                ))}
              </div>
            </Card>
          )}
          {Object.keys(artifactPreviews).length > 0 && (
            <ResultArtifactEvidence previews={artifactPreviews} />
          )}
          <TechnicalDetails>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </TechnicalDetails>
        </section>
      )}
    </>
  );
}

export function ResultArtifactEvidence({ previews }: { previews: Record<string, any> }) {
  const curves = ["equity_curve", "drawdown_curve"];
  const tables = [
    "yearly",
    "monthly",
    "entry_session",
    "side",
    "parameter_neighbors",
    "wfa_stitched_oos",
    "monte_carlo_summary",
  ];
  return (
    <section className="artifact-evidence">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Hash-verified ResultBundleV2 evidence</p>
          <h2>Robustness and breakdowns</h2>
        </div>
      </div>
      <div className="artifact-inventory">
        {Object.entries(previews).map(([name, item]: [string, any]) => (
          <Card key={name}>
            <span className="artifact-icon">
              <Icon name={curves.includes(name) ? "chart" : "file"} />
            </span>
            <strong>{humanize(name)}</strong>
            <StatusBadge value={item.available ? "Available" : "Unavailable"} />
            <small>
              {item.available
                ? `${item.rows} rows · hash verified`
                : item.reason || "Not supplied"}
            </small>
          </Card>
        ))}
      </div>
      <div className="result-curve-grid">
        {curves.map((name) => (
          <ResultCurve key={name} name={name} preview={previews[name]} />
        ))}
      </div>
      <div className="result-breakdown-stack">
        {tables.map((name) => (
          <ResultPreviewTable key={name} name={name} preview={previews[name]} />
        ))}
      </div>
    </section>
  );
}

function ResultCurve({ name, preview }: { name: string; preview: any }) {
  const rows = preview?.preview_rows || [];
  if (!preview?.available || !rows.length)
    return (
      <Card className="result-curve-card">
        <h3>{humanize(name)}</h3>
        <Notice tone="warning">{preview?.reason || "Evidence unavailable"}</Notice>
      </Card>
    );
  const yKey = name === "equity_curve" ? "equity" : "drawdown";
  const values = rows.map((row: any) => Number(row[yKey])).filter(Number.isFinite);
  if (!values.length) return null;
  const width = 760;
  const height = 220;
  const pad = 18;
  const low = Math.min(...values);
  const high = Math.max(...values);
  const spread = Math.max(high - low, 1e-9);
  const points = rows
    .map((row: any, index: number) => {
      const value = Number(row[yKey]);
      if (!Number.isFinite(value)) return null;
      const x = pad + (index * (width - pad * 2)) / Math.max(rows.length - 1, 1);
      const y = pad + ((high - value) * (height - pad * 2)) / spread;
      return `${x},${y}`;
    })
    .filter(Boolean)
    .join(" ");
  return (
    <Card className="result-curve-card">
      <div className="card-kicker">
        <h3>{humanize(name)}</h3>
        <small>{preview.rows} complete rows · hash verified</small>
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${humanize(name)} chart`}>
        <polyline
          points={points}
          fill="none"
          stroke={name === "equity_curve" ? "#0d5962" : "#a3342c"}
          strokeWidth="3"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="curve-range">
        <span>Low {displayMetric(low)}</span>
        <span>High {displayMetric(high)}</span>
      </div>
    </Card>
  );
}

function ResultPreviewTable({ name, preview }: { name: string; preview: any }) {
  if (!preview)
    return null;
  const rows = preview.preview_rows || [];
  const columns = preview.columns || [];
  return (
    <Card className="result-preview-card">
      <div className="card-kicker">
        <div>
          <p className="eyebrow">{preview.available ? "Hash verified" : "Not available"}</p>
          <h3>{humanize(name)}</h3>
        </div>
        <StatusBadge value={preview.available ? "Available" : "Unavailable"} />
      </div>
      {!preview.available ? (
        <Notice tone="warning">{preview.reason || "Evidence was not supplied."}</Notice>
      ) : (
        <div className="result-preview-table" role="region" aria-label={`${humanize(name)} table`} tabIndex={0}>
          <table>
            <thead>
              <tr>
                {columns.map((column: string) => (
                  <th key={column}>{humanize(column)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row: any, index: number) => (
                <tr key={index}>
                  {columns.map((column: string) => (
                    <td key={column}>{displayMetric(row[column])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {preview.truncated && (
            <small>
              Display is deterministically downsampled from {preview.rows} complete hash-bound rows.
            </small>
          )}
        </div>
      )}
    </Card>
  );
}

function History({
  detail,
  onRefresh,
}: {
  detail: any;
  onRefresh: () => Promise<any>;
}) {
  const { data: studioData } = useStudio();
  const attempts = detail.attempts || [];
  const campaign = detail.campaign || {};
  const [creating, setCreating] = useState(false);
  const [options, setOptions] = useState<any>(null);
  const [parent, setParent] = useState(
    attempts.at(-1)?.attempt_id || "original",
  );
  const [kind, setKind] = useState("replication");
  const [reason, setReason] = useState("");
  const [createdBy, setCreatedBy] = useState(
    studioData.settings?.reviewer_identity || "",
  );
  const [datasetId, setDatasetId] = useState("");
  const [targetVariant, setTargetVariant] = useState("v01");
  const [parameterKey, setParameterKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [eventGridValues, setEventGridValues] = useState<Record<string, string>>({});
  const [authorizedBy, setAuthorizedBy] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");

  useEffect(() => {
    if (!creating || !campaign.campaign_id) return;
    setOptions(null);
    api
      .followUpOptions(campaign.campaign_id, parent)
      .then((value) => {
        setOptions(value);
        if (value.datasets?.[0]?.dataset_id)
          setDatasetId((current) => current || value.datasets[0].dataset_id);
        const variants = Object.keys(value.parameters || {});
        const selectedVariant = variants.includes(targetVariant)
          ? targetVariant
          : variants[0] || "v01";
        setTargetVariant(selectedVariant);
        const first = value.parameters?.[selectedVariant]?.[0];
        setParameterKey(
          first ? `${first.component}|${first.parameter_path}` : "",
        );
        setNewValue(first ? String(first.current_value ?? "") : "");
        const declarations = value.event_parameter_declarations?.[selectedVariant] || [];
        setEventGridValues(
          Object.fromEntries(
            declarations.map((item: any) => [
              item.name,
              (item.selected_values || []).join(", "),
            ]),
          ),
        );
      })
      .catch((error) =>
        setFeedback(
          error instanceof Error
            ? error.message
            : "Follow-up choices unavailable",
        ),
      );
  }, [creating, campaign.campaign_id, parent]);

  const parameters = options?.parameters?.[targetVariant] || [];
  const selectedParameter = parameters.find(
    (item: any) => `${item.component}|${item.parameter_path}` === parameterKey,
  );
  const eventDeclarations =
    options?.event_parameter_declarations?.[targetVariant] || [];
  function selectVariant(value: string) {
    setTargetVariant(value);
    const first = options?.parameters?.[value]?.[0];
    setParameterKey(
      first ? `${first.component}|${first.parameter_path}` : "",
    );
    setNewValue(first ? String(first.current_value ?? "") : "");
    const declarations = options?.event_parameter_declarations?.[value] || [];
    setEventGridValues(
      Object.fromEntries(
        declarations.map((item: any) => [
          item.name,
          (item.selected_values || []).join(", "),
        ]),
      ),
    );
  }
  function selectParameter(value: string) {
    setParameterKey(value);
    const next = parameters.find(
      (item: any) => `${item.component}|${item.parameter_path}` === value,
    );
    setNewValue(next ? String(next.current_value ?? "") : "");
  }
  async function submitFollowUp(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setFeedback("");
    try {
      const mechanics = ["pre_pnl_mechanics_correction", "rescue"].includes(
        kind,
      );
      const value: Record<string, any> = {
        campaign_id: campaign.campaign_id,
        attempt_kind: kind,
        parent_attempt_id: parent,
        reason,
        created_by: createdBy,
      };
      if (kind === "data_refresh") value.dataset_id = datasetId;
      if (kind === "pre_pnl_parameter_declaration") {
        const declaration = Object.fromEntries(
          eventDeclarations
            .filter((item: any) => String(eventGridValues[item.name] || "").trim())
            .map((item: any) => [
              item.name,
              parseParameterGridValues(
                eventGridValues[item.name],
                item.value_type,
              ),
            ]),
        );
        if (!Object.keys(declaration).length)
          throw new Error("Select at least one certified tunable parameter.");
        value.target_variant_id = targetVariant;
        value.parameter_grid = declaration;
      }
      if (mechanics) {
        if (!selectedParameter)
          throw new Error(
            "Select one governed mechanics parameter to change.",
          );
        value.target_variant_id = targetVariant;
        value.mechanic_patches = [
          {
            variant_id: targetVariant,
            component: selectedParameter.component,
            parameter_path: selectedParameter.parameter_path,
            value: parseFollowUpValue(
              newValue,
              selectedParameter.value_type,
            ),
          },
        ];
      }
      if (kind === "rescue") value.authorized_by = authorizedBy;
      const result = await api.createFollowUp(campaign.campaign_id, value);
      await onRefresh();
      setFeedback(
        `${humanize(result.attempt_kind)} created as ${result.attempt_id}. ${result.next_action || "Generate fresh mechanics evidence next."}`,
      );
      setCreating(false);
    } catch (error) {
      setFeedback(
        error instanceof Error ? error.message : "Follow-up was not created",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section>
      <div className="section-heading">
        <div>
          <p className="eyebrow">Immutable lineage</p>
          <h2>Attempts and follow-ups</h2>
        </div>
        {campaign.studio_managed && (
          <Button
            variant={creating ? "secondary" : "primary"}
            onClick={() => {
              setCreating((value) => !value);
              setFeedback("");
            }}
          >
            {creating ? "Cancel" : "Create explicit follow-up"}
          </Button>
        )}
      </div>
      {feedback && (
        <Notice
          tone={feedback.includes("created as") ? "success" : "warning"}
        >
          {feedback}
        </Notice>
      )}
      {creating && (
        <Card className="follow-up-card">
          <div className="form-section-heading">
            <span>+</span>
            <div>
              <h2>Create a new immutable attempt</h2>
              <p>
                Prior definitions and evidence remain untouched. Preflight runs
                before this attempt is installed or added to the ledger.
              </p>
            </div>
          </div>
          {!options ? (
            <Skeleton lines={5} />
          ) : (
            <form onSubmit={submitFollowUp}>
              <div className="form-grid two">
                <Field label="Follow-up type">
                  <select value={kind} onChange={(e) => setKind(e.target.value)}>
                    {(options.attempt_kinds || [])
                      .filter(
                        (item: any) =>
                          item.value !== "rescue" || options.rescue_allowed,
                      )
                      .map((item: any) => (
                        <option key={item.value} value={item.value}>
                          {item.label}
                        </option>
                      ))}
                  </select>
                </Field>
                <Field label="Parent attempt">
                  <select value={parent} onChange={(e) => setParent(e.target.value)}>
                    {attempts.map((item: any) => (
                      <option key={item.attempt_id} value={item.attempt_id}>
                        {item.attempt_id} · {humanize(item.attempt_kind)}
                      </option>
                    ))}
                  </select>
                </Field>
              </div>
              <Field
                label="Scientific reason"
                hint={`${reason.length}/${options.reason_min_length || 80} characters minimum. Explain why this attempt is warranted without tuning to observed PnL.`}
              >
                <textarea
                  rows={4}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  required
                />
              </Field>
              <Field label="Researcher identity">
                <input
                  value={createdBy}
                  onChange={(e) => setCreatedBy(e.target.value)}
                  required
                />
              </Field>
              {kind === "data_refresh" && (
                <Field label="Governed replacement dataset">
                  <select
                    value={datasetId}
                    onChange={(e) => setDatasetId(e.target.value)}
                  >
                    {(options.datasets || []).map((item: any) => (
                      <option key={item.dataset_id} value={item.dataset_id}>
                        {item.dataset_id} · {item.symbol} {item.timeframe} · PASS
                      </option>
                    ))}
                  </select>
                </Field>
              )}
              {kind === "pre_pnl_parameter_declaration" && (
                <div className="governed-patch">
                  <Notice tone="warning" title="Predeclare before performance testing">
                    Blank rows remain fixed at their reviewed defaults. Enter comma-separated values only for parameters you intend to optimize. The reviewed default must be included, and the same grid is used by core and walk-forward analysis.
                  </Notice>
                  <Field label="Target variant">
                    <select
                      value={targetVariant}
                      onChange={(e) => selectVariant(e.target.value)}
                    >
                      {Object.keys(options.event_parameter_declarations || {}).map(
                        (value) => <option key={value}>{value}</option>,
                      )}
                    </select>
                  </Field>
                  <div className="parameter-list">
                    {eventDeclarations.map((item: any) => (
                      <Field
                        key={item.name}
                        label={`${humanize(item.name)} · ${humanize(item.category)}`}
                        hint={
                          item.tunable
                            ? `Fixed default: ${String(item.current_value)}. Leave blank to keep fixed.`
                            : `Locked fixed at ${String(item.current_value)} by certification.`
                        }
                      >
                        <input
                          value={eventGridValues[item.name] || ""}
                          disabled={!item.tunable}
                          placeholder={item.tunable ? "comma-separated grid values" : "fixed"}
                          onChange={(e) =>
                            setEventGridValues((current) => ({
                              ...current,
                              [item.name]: e.target.value,
                            }))
                          }
                        />
                      </Field>
                    ))}
                  </div>
                </div>
              )}
              {["pre_pnl_mechanics_correction", "rescue"].includes(kind) && (
                <div className="governed-patch">
                  <Notice tone="warning" title="One explicit reviewed change">
                    The source attempt is never edited. This new attempt records
                    the old and new scalar values and repeats mechanics approval
                    for every currently declared variant.
                  </Notice>
                  <div className="form-grid two">
                    <Field label="Target variant">
                      <select
                        value={targetVariant}
                        onChange={(e) => selectVariant(e.target.value)}
                      >
                        {Object.keys(options.parameters || {}).map((value) => (
                          <option key={value}>{value}</option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Certified parameter">
                      <select
                        value={parameterKey}
                        onChange={(e) => selectParameter(e.target.value)}
                      >
                        {parameters.map((item: any) => (
                          <option
                            key={`${item.component}|${item.parameter_path}`}
                            value={`${item.component}|${item.parameter_path}`}
                          >
                            {humanize(item.component)} · {item.module} · {item.parameter_path}
                          </option>
                        ))}
                      </select>
                    </Field>
                  </div>
                  <Field
                    label="New reviewed value"
                    hint={`Current: ${String(selectedParameter?.current_value ?? "Not recorded")} · type: ${selectedParameter?.value_type || "unknown"}`}
                  >
                    {selectedParameter?.value_type === "boolean" ? (
                      <select
                        value={newValue}
                        onChange={(e) => setNewValue(e.target.value)}
                      >
                        <option value="true">True</option>
                        <option value="false">False</option>
                      </select>
                    ) : (
                      <input
                        type={
                          ["integer", "number"].includes(
                            selectedParameter?.value_type,
                          )
                            ? "number"
                            : "text"
                        }
                        step={
                          selectedParameter?.value_type === "integer"
                            ? 1
                            : "any"
                        }
                        value={newValue}
                        onChange={(e) => setNewValue(e.target.value)}
                      />
                    )}
                  </Field>
                </div>
              )}
              {kind === "rescue" && (
                <Field label="Authorizer identity">
                  <input
                    value={authorizedBy}
                    onChange={(e) => setAuthorizedBy(e.target.value)}
                    required
                  />
                </Field>
              )}
              <div className="follow-up-actions">
                <Button
                  type="submit"
                  disabled={
                    busy ||
                    !createdBy.trim() ||
                    reason.trim().length < (options.reason_min_length || 80)
                  }
                >
                  {busy ? "Running preflight…" : "Preflight and create attempt"}
                </Button>
              </div>
            </form>
          )}
        </Card>
      )}
      {attempts.length === 0 ? (
        <EmptyState
          icon="clock"
          title="Only the original protocol exists"
          body="Use Create explicit follow-up for a governed replication, data refresh, methodology rerun, correction, or authorized rescue."
        />
      ) : (
        <div className="timeline">
          {attempts.map((item: any, index: number) => (
            <Card key={item.attempt_id || index}>
              <span className="timeline-marker">{index + 1}</span>
              <div>
                <div className="card-kicker">
                  <strong>{item.attempt_id}</strong>
                  <StatusBadge value={item.attempt_kind || "Original"} />
                </div>
                <p>
                  {item.reason ||
                    "Original frozen protocol and evidence identity."}
                </p>
                <small>Parent: {item.parent_attempt_id || "None"}</small>
                {item.dataset_lineage_error && (
                  <Notice tone="danger" title="Dataset lineage unavailable">
                    {item.dataset_lineage_error}
                  </Notice>
                )}
                {(item.dataset_bindings || []).map((binding: any) => (
                  <div
                    className="attempt-dataset-lineage"
                    key={`${item.attempt_id}-${binding.variant_id}`}
                  >
                    <div className="card-kicker">
                      <div>
                        <p className="eyebrow">
                          {binding.variant_id} · Governed dataset
                        </p>
                        <h3>{binding.dataset_id}</h3>
                      </div>
                      <div className="attempt-dataset-badges">
                        <StatusBadge
                          value={binding.quality_verdict || "Unknown"}
                          kind="scientific"
                        />
                        <StatusBadge
                          value={binding.dataset_change || "Unknown"}
                        />
                      </div>
                    </div>
                    <dl className="compact-dl attempt-dataset-details">
                      <div>
                        <dt>Event source</dt>
                        <dd>{humanize(binding.source_type)}</dd>
                      </div>
                      <div>
                        <dt>Bar source</dt>
                        <dd>{humanize(binding.bar_source_type)}</dd>
                      </div>
                      <div>
                        <dt>Coverage</dt>
                        <dd>
                          {formatDate(binding.coverage_start)} →{" "}
                          {formatDate(binding.coverage_end)}
                        </dd>
                      </div>
                      <div>
                        <dt>Dataset relationship</dt>
                        <dd>
                          {binding.dataset_change === "inherited"
                            ? `Inherited from ${item.parent_attempt_id}`
                            : binding.dataset_change === "changed"
                              ? `Changed from ${binding.parent_dataset_id || "parent dataset"}`
                              : humanize(binding.dataset_change)}
                        </dd>
                      </div>
                      <div className="hash-row">
                        <dt>Input-data hash</dt>
                        <dd>
                          {binding.input_data_hash ? (
                            <code>{binding.input_data_hash}</code>
                          ) : (
                            binding.input_data_hash_error || "Not available"
                          )}
                        </dd>
                      </div>
                    </dl>
                    <TestDataWindows
                      windows={binding.test_data_windows || []}
                    />
                    <div className="attempt-dataset-actions">
                      <Link
                        className="button button-secondary"
                        to={`/library/data?dataset=${encodeURIComponent(binding.dataset_id)}`}
                      >
                        Open in Data Library
                      </Link>
                    </div>
                    <TechnicalDetails>
                      <pre>{JSON.stringify(binding, null, 2)}</pre>
                    </TechnicalDetails>
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}

function TestDataWindows({ windows }: { windows: any[] }) {
  if (!windows.length) return null;
  return (
    <section className="attempt-test-windows">
      <div className="card-kicker">
        <div>
          <p className="eyebrow">Attempt-specific evidence scope</p>
          <h3>Test data windows</h3>
        </div>
        <small>Dataset coverage is not the test range.</small>
      </div>
      <div
        className="test-window-table"
        role="region"
        aria-label="Test data windows"
        tabIndex={0}
      >
        <table>
          <thead>
            <tr>
              <th>Test stage</th>
              <th>Input</th>
              <th>Planned window</th>
              <th>Resolved / actual</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {windows.map((window: any) => (
              <tr key={window.stage}>
                <td>
                  <strong>{window.label || humanize(window.stage)}</strong>
                  {window.inherited_from && (
                    <small>
                      From {humanize(window.inherited_from)}
                    </small>
                  )}
                </td>
                <td>
                  {humanize(window.input_kind)}
                  {window.detail && <small>{window.detail}</small>}
                </td>
                <td>{formatPlannedWindow(window)}</td>
                <td>{formatObservedWindow(window)}</td>
                <td>
                  <StatusBadge
                    value={
                      window.status === "actual"
                        ? "Actual recorded"
                        : window.status === "resolved"
                          ? "Resolved"
                          : window.status === "unavailable"
                            ? "Unavailable"
                            : "Planned"
                    }
                    kind={
                      window.status === "unavailable"
                        ? "scientific"
                        : undefined
                    }
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatPlannedWindow(window: any) {
  if (window.train_start || window.test_start) {
    return (
      <span className="window-periods">
        <span>
          Train: {formatWindowRange(window.train_start, window.train_end)}
        </span>
        <span>
          Test: {formatWindowRange(window.test_start, window.test_end)}
        </span>
      </span>
    );
  }
  return formatWindowRange(window.planned_start, window.planned_end);
}

function formatObservedWindow(window: any) {
  if (window.actual_start || window.actual_end) {
    return (
      <span className="window-periods">
        <span>
          Actual: {formatWindowRange(window.actual_start, window.actual_end)}
        </span>
        {(window.actual_sessions ||
          window.actual_windows ||
          window.actual_rows) && (
          <span>
            {window.actual_sessions
              ? `${window.actual_sessions} sessions`
              : window.actual_windows
                ? `${window.actual_windows} WFA windows`
                : `${Number(window.actual_rows).toLocaleString()} rows`}
          </span>
        )}
      </span>
    );
  }
  if (window.resolved_start || window.resolved_end) {
    return `Resolved: ${formatWindowRange(
      window.resolved_start,
      window.resolved_end,
    )}`;
  }
  return "Not run yet";
}

function formatWindowRange(start: any, end: any): string {
  if (!start && !end) return "Not applicable";
  return `${start ? formatDate(start) : "Unknown"} → ${
    end ? formatDate(end) : "Unknown"
  }`;
}

function parseFollowUpValue(
  value: string,
  type: string,
): string | number | boolean | null {
  if (type === "boolean") return value === "true";
  if (type === "integer") {
    const parsed = Number(value);
    if (!Number.isInteger(parsed))
      throw new Error("The selected parameter requires a whole number.");
    return parsed;
  }
  if (type === "number") {
    const parsed = Number(value);
    if (!Number.isFinite(parsed))
      throw new Error("The selected parameter requires a finite number.");
    return parsed;
  }
  if (type === "null") return null;
  return value;
}

function parseParameterGridValues(value: string, type: string) {
  const raw = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (raw.length < 2)
    throw new Error("Every tunable parameter needs at least two comma-separated values.");
  const parsed = raw.map((item) => parseFollowUpValue(item, type));
  if (new Set(parsed.map((item) => `${typeof item}:${String(item)}`)).size !== parsed.length)
    throw new Error("Parameter grid values must be unique.");
  return parsed;
}

function FieldLike({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
    </label>
  );
}
function displayMetric(value: any): string {
  const actual =
    value && typeof value === "object" && "value" in value
      ? value.value
      : value;
  if (actual === null || actual === undefined) return "Undefined";
  if (typeof actual === "number")
    return new Intl.NumberFormat(undefined, {
      maximumFractionDigits: 3,
    }).format(actual);
  return String(actual);
}
