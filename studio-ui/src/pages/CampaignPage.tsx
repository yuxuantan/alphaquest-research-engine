import { useEffect, useMemo, useRef, useState } from "react";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { ApiError, api } from "../api";
import { Icon } from "../components/Icons";
import {
  progressPosition,
  ResearchFlow,
} from "../components/ResearchProgress";
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
  formatMarketDate,
  humanize,
} from "../components/UI";
import { useStudio } from "../state";

const sections = [
  "overview",
  "protocol",
  "mechanics",
  "testing",
  "results",
  "lifecycle",
  "history",
];

export function CampaignPage() {
  const { campaignId = "", section = "overview" } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const current = sections.includes(section) ? section : "overview";
  const [detail, setDetail] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [slowLoading, setSlowLoading] = useState(false);
  const [error, setError] = useState("");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  useEffect(() => {
    setLoading(true);
    setSlowLoading(false);
    setError("");
    const slowTimer = window.setTimeout(() => setSlowLoading(true), 2500);
    api
      .campaign(campaignId)
      .then(setDetail)
      .catch((reason) =>
        setError(
          reason instanceof Error ? reason.message : "Campaign unavailable",
        ),
      )
      .finally(() => {
        window.clearTimeout(slowTimer);
        setLoading(false);
      });
    return () => window.clearTimeout(slowTimer);
  }, [campaignId]);
  if (loading)
    return (
      <div className="page">
        <div className="loading-context">
          <p className="eyebrow">Governed campaign</p>
          <h1>{humanize(campaignId)}</h1>
          <p>Loading immutable attempts, review state, and result indexes…</p>
        </div>
        <Skeleton lines={10} />
        {slowLoading && (
          <Notice tone="info" title="Still assembling campaign evidence">
            Large attempt histories can take a few seconds on first load. The
            worker and any active research continue independently.
          </Notice>
        )}
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
  const workflow = detail.workflow_context || {};
  const campaignProgress =
    detail.research_progress?.campaign || workflow.progress || null;
  const workflowQuery = new URLSearchParams();
  if (workflow.current_attempt_id)
    workflowQuery.set("attempt", workflow.current_attempt_id);
  if (workflow.target_variant_id)
    workflowQuery.set("variant", workflow.target_variant_id);
  const currentQuery = searchParams.toString() || workflowQuery.toString();
  const primaryAction = workflow.primary_action || {};
  const primaryHref =
    primaryAction.section === "reviews"
      ? `/reviews?type=mechanics&campaign=${encodeURIComponent(
          campaignId,
        )}&attempt=${encodeURIComponent(
          primaryAction.attempt_id || workflow.current_attempt_id || "",
        )}&variant=${encodeURIComponent(
          primaryAction.variant_id || workflow.target_variant_id || "",
        )}`
      : `/research/${campaignId}/${primaryAction.section || "overview"}${
          workflowQuery.toString() ? `?${workflowQuery.toString()}` : ""
        }`;
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
        description="Frozen protocol, immutable attempts, mechanics approvals, and scientific evidence for this campaign."
        actions={
          <div className="header-statuses">
            <StatusBadge
              value={workflow.scientific_status || "NEEDS MANUAL REVIEW"}
              kind="scientific"
            />
            <StatusBadge
              value={
                campaign.integrity_status ||
                campaign.workflow_status ||
                "Integrity not verified"
              }
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
      {detail.partial_errors?.length > 0 && (
        <Notice tone="warning" title="Some campaign evidence is unavailable">
          The rest of this campaign remains usable.{" "}
          {detail.partial_errors
            .map(
              (item: any) =>
                `${humanize(item.section)}: ${item.message}`,
            )
            .join(" · ")}
        </Notice>
      )}
      {workflow.current_attempt_id && (
        <Card className="workflow-context-bar">
          <div>
            <p className="eyebrow">Current campaign stage</p>
            <strong>
              {campaignProgress?.current_stage_label || humanize(workflow.stage)}
            </strong>
            <small>
              {progressPosition(campaignProgress)} · driven by sequential variant{" "}
              <strong>{workflow.target_variant_id}</strong>
            </small>
            <small>
              {workflow.current_attempt_label} · exact immutable attempt:{" "}
              <code>{workflow.current_attempt_id}</code>
            </small>
          </div>
          <div className="workflow-context-status">
            <StatusBadge
              value={workflow.scientific_status || "NEEDS MANUAL REVIEW"}
              kind="scientific"
            />
            <Link className="button button-primary" to={primaryHref}>
              {primaryAction.label || detail.recommended_action}
            </Link>
          </div>
        </Card>
      )}
      {!campaign.studio_managed && (
        <Notice tone="warning" title="Developer-managed research">
          {campaign.workflow_blocker ||
            "This source predates complete Studio authoring contracts. Novice actions remain blocked."}
        </Notice>
      )}
      <nav
        className="campaign-tabs"
        aria-label="Campaign sections"
        role="tablist"
      >
        {sections.map((item, index) => (
          <button
            ref={(node) => {
              tabRefs.current[index] = node;
            }}
            className={current === item ? "active" : ""}
            key={item}
            id={`campaign-tab-${item}`}
            role="tab"
            aria-selected={current === item}
            aria-current={current === item ? "page" : undefined}
            aria-controls="campaign-panel"
            tabIndex={current === item ? 0 : -1}
            onKeyDown={(event) => {
              if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
                return;
              event.preventDefault();
              const nextIndex =
                event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? sections.length - 1
                    : (index +
                        (event.key === "ArrowRight" ? 1 : -1) +
                        sections.length) %
                      sections.length;
              const next = sections[nextIndex];
              navigate(
                `/research/${campaignId}/${next}${
                  currentQuery ? `?${currentQuery}` : ""
                }`,
              );
              window.setTimeout(() => tabRefs.current[nextIndex]?.focus());
            }}
            onClick={() =>
              navigate(
                `/research/${campaignId}/${item}${
                  currentQuery ? `?${currentQuery}` : ""
                }`,
              )
            }
          >
            {humanize(item)}
          </button>
        ))}
      </nav>
      <div
        id="campaign-panel"
        role="tabpanel"
        aria-labelledby={`campaign-tab-${current}`}
        tabIndex={0}
      >
        {current === "overview" && <CampaignOverview detail={detail} />}
        {current === "protocol" && (
          <Protocol
            detail={detail}
            onRefresh={() => api.campaign(campaignId, true).then(setDetail)}
          />
        )}
        {current === "mechanics" && <Mechanics detail={detail} />}
        {current === "testing" && (
          <Testing
            key={detail.next_variant?.current_variant_id || "current-variant"}
            detail={detail}
            onRefresh={() => api.campaign(campaignId, true).then(setDetail)}
          />
        )}
        {current === "results" && <Results detail={detail} />}
        {current === "lifecycle" && <Lifecycle detail={detail} />}
        {current === "history" && (
          <History
            detail={detail}
            onRefresh={() => api.campaign(campaignId, true).then(setDetail)}
          />
        )}
      </div>
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
          label="Current gate"
          value={
            detail.research_progress?.campaign?.current_stage_label ||
            humanize(detail.workflow_context?.stage || "Not available")
          }
          detail={`${progressPosition(detail.research_progress?.campaign)} · ${detail.workflow_context?.target_variant_id || "No variant"}`}
        />
      </section>
      <ResearchFlow progress={detail.research_progress?.campaign} />
      <StageMatrix
        rows={matrix}
        variants={detail.research_progress?.variants || []}
      />
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

function StageMatrix({ rows, variants = [] }: { rows: any[]; variants?: any[] }) {
  const progressByVariant = new Map(
    variants.map((item: any) => [item.variant_id, item]),
  );
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
            <span>Workflow stage</span>
            <span>Generic objective verdict</span>
            <span>Operational state</span>
            <span>Next action or stop reason</span>
          </div>
          {rows.map((row: any, index) => {
            const variantId = row.variant || `v0${index + 1}`;
            const progress = progressByVariant.get(variantId) as any;
            return (
              <div className="stage-row" role="row" key={variantId}>
                <strong>
                  {variantId}
                  {progress?.is_current && <small>Current</small>}
                </strong>
                <span className="variant-stage-position">
                  <strong>
                    {progress?.current_stage_label ||
                      humanize(
                        row["first failed or unresolved gate"] ||
                          "Awaiting evidence",
                      )}
                  </strong>
                  <small>{progressPosition(progress)}</small>
                </span>
                <StatusBadge
                  value={row["research verdict"] || row.research_verdict}
                  kind="scientific"
                />
                <StatusBadge
                  value={row["operational state"] || row.operational_state}
                  kind="operational"
                />
                <span>
                  {progress?.next_action ||
                    humanize(
                      row["first failed or unresolved gate"] ||
                        row.first_failed_gate ||
                        row.failed_stage ||
                        "Awaiting evidence",
                    )}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

export function Protocol({
  detail,
  onRefresh,
}: {
  detail: any;
  onRefresh?: () => Promise<any>;
}) {
  const c = detail.campaign || {};
  const protocol = detail.protocol || {};
  const sources = protocol.supporting_sources || [];
  const objectives = protocol.research_objectives || {};
  const destinationContract = protocol.destination_benchmark_contract || {};
  return (
    <div className="protocol-layout">
      <Notice
        tone={protocol.source_identity?.frozen ? "success" : "warning"}
        title="Canonical, read-only research protocol"
      >
        This view is derived from the governed campaign definition and frozen
        strategy specification. It is context for review, not an editable
        summary.
      </Notice>
      <div className="detail-grid">
        <Card>
          <p className="eyebrow">Hypothesis</p>
          <h2>{c.title}</h2>
          <p className="disclosure-lead">
            {protocol.hypothesis || "No governed hypothesis was declared."}
          </p>
        </Card>
        <Card>
          <p className="eyebrow">Market behaviour</p>
          <h3>What should repeat</h3>
          <p>
            {protocol.market_behavior ||
              "No governed market-behaviour statement was declared."}
          </p>
        </Card>
        <Card>
          <p className="eyebrow">Causal mechanism</p>
          <h3>Why the edge may exist</h3>
          <p>
            {protocol.causal_mechanism ||
              "No governed causal mechanism was declared."}
          </p>
        </Card>
        <Card>
          <p className="eyebrow">Market context and holding period</p>
          <h3>{c.instrument || c.symbol || "Futures"} · {c.timeframe}</h3>
          <p>{protocol.market_context || "Market context was not declared."}</p>
          <p>
            <strong>Holding period:</strong>{" "}
            {protocol.holding_period || "Not declared"}
          </p>
        </Card>
      </div>
      <Card>
        <p className="eyebrow">Frozen before PnL</p>
        <h2>Development and risk objectives</h2>
        {objectives.confirmed ? (
          <>
            <p>{objectives.development_goal}</p>
            <dl className="compact-dl">
              <div>
                <dt>Decision deadline</dt>
                <dd>{objectives.development_deadline}</dd>
              </div>
              <div>
                <dt>Annualized return / MAR</dt>
                <dd>
                  {((objectives.minimum_annualized_return_fraction || 0) * 100).toFixed(1)}% / {objectives.minimum_mar}
                </dd>
              </div>
              <div>
                <dt>Maximum drawdown</dt>
                <dd>{((objectives.maximum_drawdown_fraction || 0) * 100).toFixed(1)}%</dd>
              </div>
              <div>
                <dt>WFA evidence</dt>
                <dd>
                  {objectives.minimum_complete_wfa_windows} complete windows · {objectives.minimum_wfa_oos_trades} trades
                </dd>
              </div>
              <div>
                <dt>Monte Carlo</dt>
                <dd>
                  {objectives.monte_carlo_min_runs} paths · {objectives.monte_carlo_horizon_months} months
                </dd>
              </div>
              <div>
                <dt>True forward incubation</dt>
                <dd>
                  {objectives.forward_incubation_min_calendar_days} days · {objectives.forward_incubation_min_trades} trades
                </dd>
              </div>
            </dl>
            <small>
              Objective SHA {String(protocol.source_identity?.research_objectives_sha256 || "missing").slice(0, 16)}
            </small>
          </>
        ) : (
          <>
            <Notice tone="warning" title="Legacy protocol has no frozen objective contract">
              New performance testing is blocked. Objectives may be declared
              only while the current attempt has no performance evidence.
              Studio creates a new immutable child attempt and preserves this
              history unchanged.
            </Notice>
            {protocol.legacy_pre_pnl_action?.available && onRefresh ? (
              <LegacyPrePnlProtocolAction
                campaignId={c.campaign_id}
                action={protocol.legacy_pre_pnl_action}
                onRefresh={onRefresh}
              />
            ) : protocol.legacy_pre_pnl_action?.unavailable_reason ? (
              <p className="error-text">
                {protocol.legacy_pre_pnl_action.unavailable_reason}
              </p>
            ) : null}
          </>
        )}
      </Card>
      {(destinationContract.profiles || []).length > 0 && (
        <Card>
          <p className="eyebrow">Frozen before PnL</p>
          <h2>Destination-specific passing benchmark</h2>
          <Notice tone="info">
            Scientific-validity PASS is mandatory. Generic investment quality
            remains separate; only the exact primary profile can support
            destination-specific candidate approval.
          </Notice>
          <div className="criteria-list">
            {destinationContract.profiles.map((profile: any) => (
              <div key={`${profile.profile_id}@${profile.profile_version}`}>
                <span>
                  <strong>{profile.account_label || profile.profile_id}</strong>
                  <small>
                    {profile.role} · {profile.profile_id}@{profile.profile_version}
                  </small>
                </span>
                <span>
                  <strong>{profile.provider}</strong>
                  <small>{profile.program}</small>
                </span>
                <StatusBadge
                  value={profile.role === "primary" ? "Primary benchmark" : "Comparison"}
                />
              </div>
            ))}
          </div>
          <small>
            Benchmark SHA {String(protocol.source_identity?.destination_benchmark_contract_sha256 || "missing").slice(0, 16)}
          </small>
        </Card>
      )}
      <Card>
        <p className="eyebrow">Signal inputs</p>
        <h2>Information the hypothesis depends on</h2>
        {(protocol.signal_inputs || []).length ? (
          <ul className="disclosure-list">
            {protocol.signal_inputs.map((input: string) => (
              <li key={input}>{input}</li>
            ))}
          </ul>
        ) : (
          <p>No governed signal inputs were declared.</p>
        )}
      </Card>
      <section>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Research basis</p>
            <h2>Supporting sources</h2>
          </div>
        </div>
        <div className="source-grid">
          {sources.map((source: any, index: number) => {
            const href = safeResearchHref(source.link);
            return (
              <Card key={`${source.title}-${index}`}>
                <p className="eyebrow">
                  {source.year || "Year not recorded"} ·{" "}
                  {formatAuthors(source.authors)}
                </p>
                <h3>{source.title || "Untitled source"}</h3>
                <p>{source.relevance || "Relevance was not recorded."}</p>
                <div className="source-links">
                  {href ? (
                    <a href={href} target="_blank" rel="noreferrer">
                      Open source ↗
                    </a>
                  ) : (
                    <span>{source.link || "No external link"}</span>
                  )}
                  {source.doi && <code>DOI {source.doi}</code>}
                </div>
              </Card>
            );
          })}
        </div>
      </section>
      <Card>
        <p className="eyebrow">Known failure modes</p>
        <h2>How the hypothesis or evidence can break</h2>
        {(protocol.known_failure_modes || []).length ? (
          <ul className="disclosure-list">
            {protocol.known_failure_modes.map((item: string) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p>No governed failure modes were declared.</p>
        )}
      </Card>
      <TechnicalDetails>
        <pre>{JSON.stringify(protocol.source_identity || {}, null, 2)}</pre>
      </TechnicalDetails>
    </div>
  );
}

function LegacyPrePnlProtocolAction({
  campaignId,
  action,
  onRefresh,
}: {
  campaignId: string;
  action: any;
  onRefresh: () => Promise<any>;
}) {
  const { data: studioData } = useStudio();
  const defaultDeadline = new Date(Date.now() + 180 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const accountProfiles = (studioData.libraries?.account_profiles || []).filter(
    (item: any) => item.promotable,
  );
  const [primaryProfileKey, setPrimaryProfileKey] = useState("");
  const [comparisonProfileKeys, setComparisonProfileKeys] = useState<string[]>(
    [],
  );
  const [benchmarkCosts, setBenchmarkCosts] = useState<
    Record<string, Record<string, string>>
  >({});
  const [defaultCostObservedAt] = useState(() => {
    const now = new Date();
    return new Date(now.getTime() - now.getTimezoneOffset() * 60_000)
      .toISOString()
      .slice(0, 16);
  });
  const [form, setForm] = useState<Record<string, any>>({
    development_goal:
      "Determine whether this candidate can survive the frozen research protocol.",
    development_deadline: defaultDeadline,
    evaluation_horizon_months: 24,
    minimum_annualized_return_percent: 20,
    minimum_mar: 0.4,
    maximum_drawdown_percent: 10,
    minimum_complete_wfa_windows: 3,
    minimum_wfa_oos_trades: 50,
    minimum_acceptance_oos_trades: 30,
    monte_carlo_min_runs: 8000,
    monte_carlo_horizon_months: 6,
    minimum_net_profit_probability_percent: 70,
    maximum_account_breach_probability_percent: 10,
    forward_incubation_min_calendar_days: 90,
    forward_incubation_min_trades: 30,
    maximum_variants: 5,
    abandonment_rules:
      "Stop when any frozen stage gate fails; do not tune after observing OOS results.",
    retirement_rules:
      "Retire after a live risk breach or sustained degradation beyond the frozen limits.",
    reason:
      "Create a result-invariant pre-PnL objective contract for this legacy attempt while preserving its certified mechanics, parameter space, dataset, execution, and methodology lineage.",
    created_by: studioData.settings?.reviewer_identity || "",
    confirmed: false,
    destination_scope_confirmed: false,
  });
  const update = (key: string, value: any) =>
    setForm((current) => ({ ...current, [key]: value }));
  const objectiveLines = (value: string) =>
    value
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);
  const numericFields = [
    ["evaluation_horizon_months", "Evaluation horizon (months)", 12, 120, 1],
    ["maximum_variants", "Maximum variants", 1, 5, 1],
    ["minimum_annualized_return_percent", "Minimum annualized return (%)", 0.01, 500, 0.01],
    ["minimum_mar", "Minimum MAR", 0.4, 20, 0.01],
    ["maximum_drawdown_percent", "Maximum drawdown (%)", 0.01, 20, 0.01],
    ["minimum_complete_wfa_windows", "Complete WFA windows", 3, 100, 1],
    ["minimum_wfa_oos_trades", "Minimum stitched WFA trades", 50, undefined, 1],
    ["minimum_acceptance_oos_trades", "Minimum final OOS trades", 30, undefined, 1],
    ["monte_carlo_min_runs", "Monte Carlo runs", 8000, 1000000, 1],
    ["monte_carlo_horizon_months", "Stress horizon (months)", 6, 120, 1],
    ["minimum_net_profit_probability_percent", "Minimum profitable paths (%)", 70, 100, 0.1],
    ["maximum_account_breach_probability_percent", "Maximum account breaches (%)", 0, 10, 0.1],
    ["forward_incubation_min_calendar_days", "Forward incubation days", 90, 1095, 1],
    ["forward_incubation_min_trades", "Forward incubation trades", 30, undefined, 1],
  ] as const;
  const profileKey = (profile: any) =>
    `${profile.profile_id}@${profile.version}`;
  const selectedDestinationProfiles = accountProfiles.filter((profile: any) =>
    [primaryProfileKey, ...comparisonProfileKeys].includes(profileKey(profile)),
  );
  const costsFor = (key: string) =>
    benchmarkCosts[key] || {
      evaluation_purchase_price: "",
      activation_fee: "",
      other_upfront_costs: "0",
      cost_observed_at: defaultCostObservedAt,
      cost_source: "",
    };
  const updateCosts = (key: string, field: string, value: string) =>
    setBenchmarkCosts((current) => ({
      ...current,
      [key]: { ...costsFor(key), [field]: value },
    }));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!form.created_by.trim()) {
      setFeedback("Enter the researcher identity before creating the protocol.");
      return;
    }
    if (form.reason.trim().length < 80) {
      setFeedback("Enter a declaration rationale of at least 80 characters.");
      return;
    }
    if (!form.development_goal.trim()) {
      setFeedback("Enter the development goal for this protocol.");
      return;
    }
    if (!form.development_deadline) {
      setFeedback("Choose the protocol decision deadline.");
      return;
    }
    const invalidNumeric = numericFields.find(([key, , min, max]) => {
      const value = Number(form[key]);
      return (
        form[key] === "" ||
        !Number.isFinite(value) ||
        value < min ||
        (max !== undefined && value > max)
      );
    });
    if (invalidNumeric) {
      setFeedback(`Enter a valid value for ${invalidNumeric[1]}.`);
      return;
    }
    if (!objectiveLines(form.abandonment_rules).length) {
      setFeedback("Declare at least one abandonment rule.");
      return;
    }
    if (!objectiveLines(form.retirement_rules).length) {
      setFeedback("Declare at least one retirement rule.");
      return;
    }
    if (!form.confirmed) {
      setFeedback(
        "Confirm that these objectives were chosen before inspecting strategy PnL.",
      );
      return;
    }
    if (!primaryProfileKey) {
      setFeedback("Select one primary prop-firm account benchmark.");
      return;
    }
    if (
      !selectedDestinationProfiles.some(
        (profile: any) => profileKey(profile) === primaryProfileKey,
      )
    ) {
      setFeedback(
        "The selected primary account profile is no longer available. Select it again.",
      );
      return;
    }
    if (!form.destination_scope_confirmed) {
      setFeedback(
        "Confirm that candidate approval is limited to the exact frozen primary account profile.",
      );
      return;
    }
    for (const profile of selectedDestinationProfiles) {
      if (!profile.cost_input_required) continue;
      const values = costsFor(profileKey(profile));
      if (
        (profile.evaluation_price_input_required &&
          values.evaluation_purchase_price === "") ||
        (profile.activation_fee_input_required && values.activation_fee === "") ||
        !values.cost_observed_at ||
        !values.cost_source.trim()
      ) {
        setFeedback(
          `Complete the frozen acquisition costs and source for ${profile.name}.`,
        );
        return;
      }
    }
    setBusy(true);
    setFeedback("");
    try {
      const destinationBenchmarks = selectedDestinationProfiles.map(
        (profile: any) => {
          const key = profileKey(profile);
          const values = costsFor(key);
          const costs = profile.cost_input_required
            ? {
                currency: profile.identity?.currency || "USD",
                evaluation_purchase_price: Number(
                  values.evaluation_purchase_price || 0,
                ),
                activation_fee: Number(values.activation_fee || 0),
                other_upfront_costs: Number(values.other_upfront_costs || 0),
                observed_at: new Date(values.cost_observed_at).toISOString(),
                source: values.cost_source.trim(),
                include_as_replacement_cost: true,
              }
            : null;
          return {
            profile_id: profile.profile_id,
            profile_version: profile.version,
            profile_sha256: profile.profile_sha256,
            role: key === primaryProfileKey ? "primary" : "comparison",
            costs,
            benchmark_acknowledged: true,
          };
        },
      );
      const result = await api.createFollowUp(campaignId, {
        campaign_id: campaignId,
        attempt_kind: "pre_pnl_protocol_declaration",
        parent_attempt_id: action.parent_attempt_id,
        target_variant_id: action.target_variant_id,
        reason: form.reason,
        created_by: form.created_by,
        destination_benchmarks: destinationBenchmarks,
        destination_scope_acknowledged: true,
        research_objectives: {
          schema: "alphaquest.research-objectives/v1",
          development_goal: form.development_goal,
          development_deadline: form.development_deadline,
          evaluation_horizon_months: Number(form.evaluation_horizon_months),
          minimum_annualized_return_fraction:
            Number(form.minimum_annualized_return_percent) / 100,
          minimum_mar: Number(form.minimum_mar),
          maximum_drawdown_fraction:
            Number(form.maximum_drawdown_percent) / 100,
          minimum_complete_wfa_windows: Number(
            form.minimum_complete_wfa_windows,
          ),
          minimum_wfa_oos_trades: Number(form.minimum_wfa_oos_trades),
          minimum_acceptance_oos_trades: Number(
            form.minimum_acceptance_oos_trades,
          ),
          monte_carlo_min_runs: Number(form.monte_carlo_min_runs),
          monte_carlo_horizon_months: Number(
            form.monte_carlo_horizon_months,
          ),
          minimum_net_profit_probability:
            Number(form.minimum_net_profit_probability_percent) / 100,
          maximum_account_breach_probability:
            Number(form.maximum_account_breach_probability_percent) / 100,
          forward_incubation_min_calendar_days: Number(
            form.forward_incubation_min_calendar_days,
          ),
          forward_incubation_min_trades: Number(
            form.forward_incubation_min_trades,
          ),
          maximum_variants: Number(form.maximum_variants),
          abandonment_rules: objectiveLines(form.abandonment_rules),
          retirement_rules: objectiveLines(form.retirement_rules),
          confirmed: true,
        },
      });
      setFeedback(
        `${result.attempt_id} created. Fresh hash-bound mechanics evidence and approval are now required.`,
      );
      await onRefresh();
    } catch (error) {
      const fieldMessages =
        error instanceof ApiError
          ? Object.entries(error.fields).map(
              ([field, message]) => `${field}: ${message}`,
            )
          : [];
      setFeedback(
        fieldMessages.length
          ? `Protocol rejected: ${fieldMessages.join("; ")}`
          : error instanceof Error
            ? error.message
            : "Pre-PnL protocol was not created",
      );
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <div className="inline-actions">
        <Button type="button" onClick={() => setOpen(true)}>
          Create pre-PnL protocol from legacy campaign
        </Button>
      </div>
    );
  }

  return (
    <form className="form-section" onSubmit={submit} noValidate>
      <Notice tone="info" title="Immutable lineage and fresh approval">
        This copies the selected attempt's certified mechanics, parameter grid,
        dataset, and execution into a new attempt. Repository methodology stays
        fixed; declared objectives may only tighten its criteria. The new config
        hash clears inherited evidence references, so the existing mechanics
        approval does not carry forward.
      </Notice>
      <Field label="Development goal">
        <textarea
          rows={2}
          value={form.development_goal}
          onChange={(event) => update("development_goal", event.target.value)}
          required
        />
      </Field>
      <Field label="Decision deadline">
        <input
          type="date"
          value={form.development_deadline}
          onChange={(event) => update("development_deadline", event.target.value)}
          required
        />
      </Field>
      <div className="form-grid three">
        {numericFields.map(([key, label, min, max, step]) => (
          <Field key={key} label={label}>
            <input
              type="number"
              min={min}
              max={max}
              step={step}
              value={form[key]}
              onChange={(event) => update(key, event.target.value)}
              required
            />
          </Field>
        ))}
      </div>
      <div className="form-grid two">
        <Field label="Abandonment rules" hint="One precommitted stop rule per line">
          <textarea rows={3} value={form.abandonment_rules} onChange={(event) => update("abandonment_rules", event.target.value)} required />
        </Field>
        <Field label="Retirement rules" hint="One live degradation or risk rule per line">
          <textarea rows={3} value={form.retirement_rules} onChange={(event) => update("retirement_rules", event.target.value)} required />
        </Field>
      </div>
      <div className="governed-patch">
        <div className="form-section-heading">
          <span>PF</span>
          <div>
            <h2>Pre-PnL prop-firm benchmark</h2>
            <p>
              Freeze one promotion target and optional comparison accounts.
              Scientific-validity PASS remains mandatory; generic investment
              quality is reported separately.
            </p>
          </div>
        </div>
        <Field
          label="Primary account benchmark"
          hint="Only this exact profile may support destination-specific candidate approval."
        >
          <select
            value={primaryProfileKey}
            onChange={(event) => {
              setPrimaryProfileKey(event.target.value);
              setComparisonProfileKeys((current) =>
                current.filter((key) => key !== event.target.value),
              );
            }}
            required
          >
            <option value="">Select a reviewed prop-firm account</option>
            {accountProfiles.map((profile: any) => (
              <option key={profileKey(profile)} value={profileKey(profile)}>
                {profile.name} · v{profile.version}
              </option>
            ))}
          </select>
        </Field>
        <div className="parameter-list">
          {accountProfiles
            .filter((profile: any) => profileKey(profile) !== primaryProfileKey)
            .map((profile: any) => {
              const key = profileKey(profile);
              return (
                <label className="check-card" key={key}>
                  <input
                    type="checkbox"
                    checked={comparisonProfileKeys.includes(key)}
                    onChange={(event) =>
                      setComparisonProfileKeys((current) =>
                        event.target.checked
                          ? [...current, key]
                          : current.filter((item) => item !== key),
                      )
                    }
                  />
                  <span>
                    <strong>{profile.name}</strong>
                    <small>Optional comparison · {profile.profile_id}@{profile.version}</small>
                  </span>
                </label>
              );
            })}
        </div>
        {selectedDestinationProfiles.map((profile: any) => {
          const key = profileKey(profile);
          const costs = costsFor(key);
          const primary = key === primaryProfileKey;
          return (
            <Card key={key} className="account-benchmark-card">
              <div className="card-kicker">
                <div>
                  <p className="eyebrow">
                    {primary ? "Primary passing benchmark" : "Comparison only"}
                  </p>
                  <h3>{profile.name}</h3>
                </div>
                <StatusBadge value={profile.verification_status} />
              </div>
              <p>{profile.description}</p>
              <ul className="disclosure-list">
                {(profile.recommended_tests || []).map((item: string) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              {profile.cost_input_required && (
                <div className="form-grid two">
                  {profile.evaluation_price_input_required && (
                    <Field label="Challenge purchase price">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={costs.evaluation_purchase_price}
                        onChange={(event) =>
                          updateCosts(
                            key,
                            "evaluation_purchase_price",
                            event.target.value,
                          )
                        }
                        required
                      />
                    </Field>
                  )}
                  {profile.activation_fee_input_required && (
                    <Field label="Activation fee">
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={costs.activation_fee}
                        onChange={(event) =>
                          updateCosts(key, "activation_fee", event.target.value)
                        }
                        required
                      />
                    </Field>
                  )}
                  <Field label="Other upfront costs">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={costs.other_upfront_costs}
                      onChange={(event) =>
                        updateCosts(key, "other_upfront_costs", event.target.value)
                      }
                      required
                    />
                  </Field>
                  <Field label="Cost observed at">
                    <input
                      type="datetime-local"
                      value={costs.cost_observed_at}
                      onChange={(event) =>
                        updateCosts(key, "cost_observed_at", event.target.value)
                      }
                      required
                    />
                  </Field>
                  <Field
                    label="Cost source"
                    hint="Official checkout URL, invoice, or recorded quote."
                  >
                    <input
                      value={costs.cost_source}
                      onChange={(event) =>
                        updateCosts(key, "cost_source", event.target.value)
                      }
                      required
                    />
                  </Field>
                </div>
              )}
              <TechnicalDetails>
                <pre>{JSON.stringify(profile.evaluation_policy, null, 2)}</pre>
              </TechnicalDetails>
            </Card>
          );
        })}
        <Link to="/library/accounts">Inspect complete account-rule profiles</Link>
        <label className="check-card">
          <input
            type="checkbox"
            checked={form.destination_scope_confirmed}
            onChange={(event) =>
              update("destination_scope_confirmed", event.target.checked)
            }
          />
          <span>
            <strong>
              I understand approval is limited to the exact frozen primary profile
            </strong>
            <small>
              Comparison accounts cannot support candidate approval. Profile rules,
              versions, hashes, costs, and success requirements become immutable.
            </small>
          </span>
        </label>
      </div>
      <Field label="Researcher identity">
        <input value={form.created_by} onChange={(event) => update("created_by", event.target.value)} required />
      </Field>
      <Field label="Declaration rationale" hint="At least 80 characters; stored in immutable lineage">
        <textarea rows={3} minLength={80} value={form.reason} onChange={(event) => update("reason", event.target.value)} required />
      </Field>
      <label className="check-card">
        <input type="checkbox" checked={form.confirmed} onChange={(event) => update("confirmed", event.target.checked)} />
        <span>
          <strong>I chose these objectives before inspecting strategy PnL</strong>
          <small>The declaration is immutable and result-invariant.</small>
        </span>
      </label>
      {feedback && (
        <div aria-live="polite">
          <Notice tone="warning">{feedback}</Notice>
        </div>
      )}
      <div className="inline-actions">
        <Button type="submit" disabled={busy}>
          {busy ? "Creating…" : "Create immutable protocol attempt"}
        </Button>
        <Button type="button" variant="secondary" disabled={busy} onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

export function Mechanics({ detail }: { detail: any }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const campaign = detail.campaign || {};
  const disclosure = detail.mechanics || {};
  const attempts = disclosure.attempts || [];
  const requestedAttempt = searchParams.get("attempt");
  const selectedAttempt =
    attempts.find((item: any) => item.attempt_id === requestedAttempt) ||
    attempts.find(
      (item: any) => item.attempt_id === disclosure.default_attempt_id,
    ) ||
    attempts.at(-1);
  const requestedVariant = searchParams.get("variant");
  const selectedMechanic =
    selectedAttempt?.variants?.find(
      (item: any) => item.variant_id === requestedVariant,
    ) ||
    selectedAttempt?.variants?.find((item: any) => item.is_attempt_target) ||
    selectedAttempt?.variants?.at(-1);
  function selectAttempt(attemptId: string) {
    const next = attempts.find((item: any) => item.attempt_id === attemptId);
    const variant =
      next?.variants?.find((item: any) => item.is_attempt_target)?.variant_id ||
      next?.variants?.at(-1)?.variant_id ||
      "";
    setSearchParams({ attempt: attemptId, variant });
  }
  function selectVariant(variantId: string) {
    setSearchParams({
      attempt: selectedAttempt?.attempt_id || "",
      variant: variantId,
    });
  }
  if (!selectedAttempt || !selectedMechanic) {
    return (
      <Notice tone="warning" title="Frozen mechanics are unavailable">
        Studio could not resolve a governed immutable attempt configuration for
        this campaign.
      </Notice>
    );
  }
  const approval = selectedMechanic.mechanics_approval || {};
  const approvalErrors = approval.errors || [];
  const awaitingManualReview =
    approval.status === "BLOCKED" &&
    approvalErrors.length > 0 &&
    approvalErrors.every((error: string) =>
      error.toLowerCase().includes("manual approval"),
    );
  const displayedApprovalStatus = awaitingManualReview
    ? "AWAITING MANUAL REVIEW"
    : approval.status || "NEEDS MANUAL REVIEW";
  const approvalTone = approval.status === "APPROVED_FOR_TESTING"
    ? "success"
    : approval.status === "INCLUDED_PREDECESSOR"
      ? "info"
      : "warning";
  const reviewHref = `/reviews?type=mechanics&campaign=${encodeURIComponent(
    campaign.campaign_id,
  )}&attempt=${encodeURIComponent(
    selectedAttempt.attempt_id,
  )}&variant=${encodeURIComponent(selectedMechanic.variant_id)}`;
  return (
    <div className="mechanics-disclosure">
      <Notice
        tone="info"
        title="Canonical, read-only variant mechanics"
      >
        Select the exact immutable attempt and included variant. Approval
        verifies implementation correctness only; it is not profitability or
        trading approval.
      </Notice>
      <Card className="mechanics-selector">
        <div>
          <label htmlFor="mechanics-attempt">Immutable attempt</label>
          <select
            id="mechanics-attempt"
            value={selectedAttempt.attempt_id}
            onChange={(event) => selectAttempt(event.target.value)}
          >
            {attempts.map((attempt: any) => (
              <option key={attempt.attempt_id} value={attempt.attempt_id}>
                {friendlyAttemptLabel(attempt)}
                {attempt.target_variant_id
                  ? ` · targets ${attempt.target_variant_id}`
                  : ""}
              </option>
            ))}
          </select>
          <ExactAttemptIdentity attemptId={selectedAttempt.attempt_id} />
        </div>
        <div>
          <label htmlFor="mechanics-variant">Included variant</label>
          <select
            id="mechanics-variant"
            value={selectedMechanic.variant_id}
            onChange={(event) => selectVariant(event.target.value)}
          >
            {(selectedAttempt.variants || []).map((item: any) => (
              <option key={item.variant_id} value={item.variant_id}>
                {item.variant_id} · {item.title}
                {item.is_attempt_target
                  ? " · attempt target"
                  : " · campaign sequence context"}
              </option>
            ))}
          </select>
        </div>
      </Card>
      <Card>
        <div className="mechanics-title-row">
          <div>
            <p className="eyebrow">
              {selectedMechanic.variant_id} ·{" "}
              {humanize(selectedAttempt.attempt_kind)}
            </p>
            <h2>{selectedMechanic.title}</h2>
            <p className="attempt-id">{selectedAttempt.attempt_id}</p>
          </div>
          <StatusBadge value={displayedApprovalStatus} />
        </div>
        <Notice tone={approvalTone} title="Mechanics approval status">
          {awaitingManualReview
            ? "Mechanics evidence exists, but no hash-bound reviewer approval has been recorded. Complete the exact fixed-default sample review before performance testing."
            : approval.note}
          {approvalErrors.length > 0 && (
            <ul>
              {approvalErrors.map((error: string) => (
                <li key={error}>{presentApprovalRequirement(error)}</li>
              ))}
            </ul>
          )}
        </Notice>
        {awaitingManualReview && selectedMechanic.is_attempt_target && (
          <Link className="button button-primary mechanics-review-action" to={reviewHref}>
            Review governed sampled trades
          </Link>
        )}
        <p className="eyebrow">How this variant expresses the edge</p>
        <p className="disclosure-lead">
          {selectedMechanic.expresses_edge ||
            "No governed mechanic explanation was declared."}
        </p>
        <div className="button-row">
          <Link className="button button-secondary" to={reviewHref}>
            Open exact mechanics review
          </Link>
          <Link
            className="button button-ghost"
            to={`/research/${campaign.campaign_id}/testing`}
          >
            Open testing
          </Link>
        </div>
      </Card>
      <div className="mechanics-rule-grid">
        <RuleCard title="Entry rule" body={selectedMechanic.rules?.entry} />
        <RuleCard title="Stop-loss rule" body={selectedMechanic.rules?.stop} />
        <RuleCard
          title="Target and time-exit rules"
          body={selectedMechanic.rules?.target_and_time_exit}
        />
        <Card>
          <p className="eyebrow">Forced flatten</p>
          <h3>
            {selectedMechanic.rules?.forced_flatten?.flatten_time ||
              "Not declared"}{" "}
            {selectedMechanic.rules?.forced_flatten?.timezone || ""}
          </h3>
          <dl className="compact-dl">
            <DisclosureValue
              label="Latest entry"
              value={
                selectedMechanic.rules?.forced_flatten?.latest_entry_time
              }
            />
            <DisclosureValue
              label="Latest flat"
              value={selectedMechanic.rules?.forced_flatten?.latest_flat_time}
            />
            <DisclosureValue
              label="Overnight"
              value={
                selectedMechanic.rules?.forced_flatten?.overnight_allowed
                  ? "Allowed"
                  : "Prohibited"
              }
            />
          </dl>
        </Card>
      </div>
      {(selectedMechanic.entry_criteria || []).length > 0 && (
        <Card>
          <p className="eyebrow">Entry-criterion audit</p>
          <h2>Why every condition exists</h2>
          <p className="disclosure-lead">
            A condition belongs here only if it expresses the frozen hypothesis,
            preserves causality, or prevents an uneconomic fill. Calibration
            choices are labelled as hypotheses rather than established facts.
          </p>
          <div className="mechanics-criteria-list">
            {selectedMechanic.entry_criteria.map(
              (item: any, index: number) => (
                <div key={`${item.criterion}-${index}`}>
                  <div>
                    <strong>{item.criterion}</strong>
                    <StatusBadge value={item.support || "Unclassified"} />
                  </div>
                  <p>{item.reason}</p>
                </div>
              ),
            )}
          </div>
        </Card>
      )}
      <div className="detail-grid">
        <Card>
          <p className="eyebrow">Causal availability</p>
          <h2>When inputs become usable</h2>
          <p>
            {selectedMechanic.causal_availability ||
              "No governed causal-availability rationale was declared."}
          </p>
        </Card>
        <Card>
          <p className="eyebrow">Session and timeframe rationale</p>
          <h2>
            {selectedMechanic.session_and_timeframe?.timeframe || "Event"} ·{" "}
            {selectedMechanic.session_and_timeframe?.session_start || "?"}–
            {selectedMechanic.session_and_timeframe?.session_end || "?"}{" "}
            {selectedMechanic.session_and_timeframe?.timezone || ""}
          </h2>
          <p>{selectedMechanic.session_and_timeframe?.rationale}</p>
        </Card>
      </div>
      <div className="detail-grid">
        <ParameterCard
          title="Fixed defaults"
          eyebrow="Exact executable values"
          values={selectedMechanic.fixed_defaults || {}}
        />
        <ParameterCard
          title={`Declared parameter grid · ${
            selectedMechanic.parameter_combination_count || 1
          } combination${
            selectedMechanic.parameter_combination_count === 1 ? "" : "s"
          }`}
          eyebrow="Predeclared tuning scope"
          values={selectedMechanic.parameter_grid || {}}
          empty="No tunable parameters; the frozen defaults are the single combination."
        />
      </div>
      {selectedMechanic.workload_forecast && (
        <Card>
          <div className="card-kicker">
            <p className="eyebrow">Runtime and storage planning</p>
            <StatusBadge value={selectedMechanic.workload_forecast.workload_class} />
          </div>
          <h2>
            {selectedMechanic.workload_forecast.parameter_combinations} parameter combinations ·{" "}
            {selectedMechanic.workload_forecast.minimum_wfa_windows} minimum WFA windows ·{" "}
            {selectedMechanic.workload_forecast.monte_carlo_paths} Monte Carlo paths
          </h2>
          <p>{selectedMechanic.workload_forecast.limitations}</p>
        </Card>
      )}
      {selectedMechanic.material_difference && (
        <Card>
          <p className="eyebrow">Material difference from predecessor</p>
          <h2>Why this is a genuinely different mechanic</h2>
          <p>{selectedMechanic.material_difference}</p>
        </Card>
      )}
      {selectedMechanic.predecessor && (
        <Card>
          <p className="eyebrow">Predecessor failure evidence</p>
          <h2>
            {selectedMechanic.predecessor.variant_id} ·{" "}
            {selectedMechanic.predecessor.verdict}
          </h2>
          <p>{selectedMechanic.predecessor.failure_analysis}</p>
          <dl className="compact-dl">
            <DisclosureValue
              label="Frozen result"
              value={selectedMechanic.predecessor.result_path}
            />
            <DisclosureValue
              label="Result SHA-256"
              value={selectedMechanic.predecessor.result_sha256}
              code
            />
          </dl>
        </Card>
      )}
      <Card>
        <p className="eyebrow">Certification identity</p>
        <h2>
          {selectedMechanic.certification?.strategy_id || "Not certified"} · v
          {selectedMechanic.certification?.implementation_version || "?"}
        </h2>
        <dl className="compact-dl">
          <DisclosureValue
            label="Implementation SHA-256"
            value={selectedMechanic.certification?.implementation_sha256}
            code
          />
          <DisclosureValue
            label="Manifest SHA-256"
            value={selectedMechanic.certification?.manifest_sha256}
            code
          />
          <DisclosureValue
            label="Config SHA-256"
            value={selectedMechanic.config_sha256}
            code
          />
          <DisclosureValue
            label="Mechanic signature"
            value={selectedMechanic.mechanic_signature}
            code
          />
        </dl>
      </Card>
      {selectedMechanic.known_failure_modes && (
        <Notice tone="warning" title="Variant-specific failure modes">
          {selectedMechanic.known_failure_modes}
        </Notice>
      )}
    </div>
  );
}

function RuleCard({ title, body }: { title: string; body?: string }) {
  return (
    <Card>
      <p className="eyebrow">{title}</p>
      <p>{body || "No governed rule rationale was declared."}</p>
    </Card>
  );
}

function ParameterCard({
  title,
  eyebrow,
  values,
  empty = "No values were declared.",
}: {
  title: string;
  eyebrow: string;
  values: Record<string, any>;
  empty?: string;
}) {
  const entries = Object.entries(values);
  return (
    <Card>
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      {entries.length ? (
        <dl className="parameter-list">
          {entries.map(([key, value]) => (
            <div key={key}>
              <dt>{humanize(key.replace("event.params.", ""))}</dt>
              <dd>{formatDisclosureValue(value)}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p>{empty}</p>
      )}
    </Card>
  );
}

function DisclosureValue({
  label,
  value,
  code = false,
}: {
  label: string;
  value: any;
  code?: boolean;
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{code ? <code>{value || "Not declared"}</code> : value || "Not declared"}</dd>
    </div>
  );
}

function formatDisclosureValue(value: any): string {
  if (Array.isArray(value)) return value.join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  if (typeof value === "boolean") return value ? "True" : "False";
  return String(value ?? "Not declared");
}

function formatAuthors(value: any): string {
  return Array.isArray(value) ? value.join(", ") : String(value || "Author not recorded");
}

function safeResearchHref(value: any): string | null {
  const text = String(value || "");
  return /^https?:\/\//i.test(text) ? text : null;
}

function presentApprovalRequirement(value: string): string {
  if (value === "declared manual approval_path does not exist") {
    return "A hash-bound manual approval has not been recorded yet.";
  }
  return value.replaceAll("_", " ");
}

export function Testing({
  detail,
  onRefresh,
}: {
  detail: any;
  onRefresh: () => Promise<any>;
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const campaign = detail.campaign || {};
  const workflow = detail.workflow_context || {};
  const attempts = detail.attempts || [
    { attempt_id: "original", attempt_kind: "original" },
  ];
  const currentVariant =
    workflow.target_variant_id ||
    detail.next_variant?.current_variant_id ||
    [...(detail.stage_matrix || [])]
      .reverse()
      .find((row: any) => row.variant || row.variant_id)?.variant ||
    [...(detail.stage_matrix || [])]
      .reverse()
      .find((row: any) => row.variant || row.variant_id)?.variant_id ||
    "";
  const defaultAttempt =
    [...attempts]
      .reverse()
      .find((item: any) =>
        attemptVariantIds(item, detail.mechanics_approval).includes(
          currentVariant,
        ),
      ) || attempts.at(-1);
  const [attempt, setAttempt] = useState(
    searchParams.get("attempt") ||
      workflow.current_attempt_id ||
      defaultAttempt?.attempt_id ||
      "original",
  );
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState("");
  const selectedAttempt =
    attempts.find((item: any) => item.attempt_id === attempt) ||
    defaultAttempt;
  const selectedVariants = attemptVariantIds(
    selectedAttempt,
    detail.mechanics_approval,
  );
  const requestedVariant = searchParams.get("variant");
  const includesCurrentVariant =
    Boolean(currentVariant) && selectedVariants.includes(currentVariant);
  const targetVariant =
    (requestedVariant && selectedVariants.includes(requestedVariant)
      ? requestedVariant
      : "") ||
    selectedAttempt?.target_variant_id ||
    (includesCurrentVariant ? currentVariant : selectedVariants.at(-1)) ||
    "unknown variant";
  const mechanicsGate = detail.mechanics_approval?.[attempt] || {
    all_approved: false,
    approved_count: 0,
    required_count: detail.campaign?.variant_count || 1,
  };
  const targetGate = (mechanicsGate.variants || []).find(
    (item: any) => item.variant_id === targetVariant,
  );
  const reviewProgress = targetGate?.review_progress || {};
  const hasReviewableEvidence =
    Boolean(reviewProgress.evidence_available) &&
    Number(reviewProgress.sampled_count || 0) > 0;
  const finalizationRecoveryRequired =
    attempt === workflow.current_attempt_id &&
    (detail.stage_matrix || []).some(
      (row: any) =>
        String(row.variant || row.variant_id || "") === targetVariant &&
        String(row["operational state"] || row.operational_state || "") ===
          "FAILED_OPERATIONAL" &&
        String(
          row["first failed or unresolved gate"] ||
            row.first_failed_or_unresolved_gate ||
            "",
        ) === "result_bundle_v2_finalization",
    );
  const finalizedResult =
    detail.attempt_results?.[attempt]?.[targetVariant] || null;
  function selectAttempt(value: string) {
    setAttempt(value);
    const nextAttempt =
      attempts.find((item: any) => item.attempt_id === value) || defaultAttempt;
    const nextTarget =
      attemptVariantIds(nextAttempt, detail.mechanics_approval).at(-1) ||
      currentVariant;
    const next = new URLSearchParams(searchParams);
    next.set("attempt", value);
    if (nextTarget) next.set("variant", nextTarget);
    setSearchParams(next, { replace: true });
  }
  async function queue(kind: "mechanics" | "run") {
    setBusy(kind);
    setFeedback("");
    try {
      const result =
        kind === "mechanics"
          ? await api.queueMechanics(campaign.campaign_id, attempt)
          : await api.queueRun(campaign.campaign_id, attempt);
      const job = result.jobs?.[0];
      const state = job?.operational_state;
      if (state === "RUNNING" || state === "CANCEL_REQUESTED") {
        setFeedback(
          `Campaign Variant Run ${job.job_id} is already ${state.toLowerCase().replaceAll("_", " ")}. Open Jobs to follow it.`,
        );
      } else {
        setFeedback(
          `${result.jobs?.length || 0} ${targetVariant} job queued. Open Jobs to follow its progress; repeated submission is idempotent.`,
        );
      }
      await onRefresh();
    } catch (reason) {
      setFeedback(
        reason instanceof Error ? reason.message : "Submission blocked",
      );
    } finally {
      setBusy("");
    }
  }
  async function recoverFinalization() {
    setBusy("recovery");
    setFeedback("");
    try {
      const result = await api.recoverFinalization(
        campaign.campaign_id,
        attempt,
      );
      setFeedback(
        `Finalization recovered without rerunning PnL. The hash-valid result is ${result.research_verdict}. Open Results to inspect it.`,
      );
      await onRefresh();
    } catch (reason) {
      setFeedback(
        reason instanceof Error ? reason.message : "Finalization recovery blocked",
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
          <select
            aria-label="Attempt identity"
            value={attempt}
            onChange={(e) => selectAttempt(e.target.value)}
          >
            {attempts.map((item: any) => (
              <option key={item.attempt_id} value={item.attempt_id}>
                {attemptOptionLabel(
                  item,
                  currentVariant,
                  detail.mechanics_approval,
                )}
              </option>
            ))}
          </select>
          <ExactAttemptIdentity attemptId={attempt} />
        </FieldLike>
        <Notice
          tone={includesCurrentVariant ? "info" : "warning"}
          title={`Selected attempt targets ${targetVariant}`}
        >
          {selectedVariants.length > 0
            ? `Frozen variants included: ${selectedVariants.join(", ")}. `
            : "The frozen variant list is unavailable. "}
          {includesCurrentVariant
            ? `The actions below run only the last/current variant, ${targetVariant}.`
            : `This is a historical attempt and does not contain the campaign's current variant, ${currentVariant}.`}
        </Notice>
        <Link
          className="button button-secondary"
          to={`/research/${campaign.campaign_id}/mechanics?attempt=${encodeURIComponent(
            attempt,
          )}&variant=${encodeURIComponent(targetVariant)}`}
        >
          View exact frozen mechanics · {targetVariant}
        </Link>
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
          {finalizationRecoveryRequired ? (
            <>
              <Notice tone="warning" title="Research finished; publication did not">
                Studio found preserved reporting for this exact reserved attempt.
                Recovery verifies the frozen config plus every recorded runner and
                reporting hash, then republishes only the ledger and indexes. It
                never invokes the backtest runner.
              </Notice>
              <Button
                onClick={() => void recoverFinalization()}
                disabled={Boolean(busy)}
              >
                {busy === "recovery"
                  ? "Verifying and recovering…"
                  : `Recover finalized evidence · ${targetVariant}`}
              </Button>
            </>
          ) : finalizedResult ? (
            <>
              <Notice tone="info" title="This immutable attempt is finalized">
                The hash-valid result is {finalizedResult.research_verdict || finalizedResult.verdict}.
                A completed attempt cannot be rerun in place.
              </Notice>
              <Link
                className="button button-primary"
                to={`/research/${campaign.campaign_id}/results?attempt=${encodeURIComponent(
                  attempt,
                )}&variant=${encodeURIComponent(targetVariant)}`}
              >
                View finalized result · {targetVariant}
              </Link>
            </>
          ) : (
            <>
              {hasReviewableEvidence && !mechanicsGate.all_approved ? (
                <Link
                  className="button button-primary"
                  to={`/reviews?type=mechanics&campaign=${encodeURIComponent(
                    campaign.campaign_id,
                  )}&attempt=${encodeURIComponent(attempt)}&variant=${encodeURIComponent(
                    targetVariant,
                  )}`}
                >
                  Review {reviewProgress.sampled_count} sampled trades ·{" "}
                  {targetVariant}
                </Link>
              ) : (
                <Button
                  onClick={() => void queue("mechanics")}
                  disabled={Boolean(busy)}
                >
                  {busy === "mechanics"
                    ? "Queuing…"
                    : `Generate mechanics evidence · ${targetVariant}`}
                </Button>
              )}
              {mechanicsGate.all_approved ? (
                <Button
                  variant="secondary"
                  onClick={() => void queue("run")}
                  disabled={Boolean(busy)}
                >
                  {busy === "run"
                    ? "Queuing…"
                    : `Run full test suite · ${targetVariant}`}
                </Button>
              ) : (
                <Notice tone="warning" title="Performance testing remains hidden">
                  {hasReviewableEvidence
                    ? `${reviewProgress.unreviewed_count || 0} sampled trade review${
                        Number(reviewProgress.unreviewed_count || 0) === 1 ? "" : "s"
                      } remain before the hash-bound mechanics decision.`
                    : `${targetVariant} needs mechanics evidence, then a hash-bound manual review using fixed default parameters. The universal sampler contains five deterministic hash-ranked entries (or all if fewer exist) plus the minimum trades needed to cover observed execution lifecycles, warning codes, and resolved ambiguities; duplicate selections are counted once.`}
                </Notice>
              )}
            </>
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

export function attemptVariantIds(
  attempt: any,
  mechanicsApproval: Record<string, any> = {},
): string[] {
  const bindings = Array.isArray(attempt?.dataset_bindings)
    ? attempt.dataset_bindings
    : [];
  const fromBindings: string[] = bindings
    .map((item: any) => String(item?.variant_id || ""))
    .filter(Boolean);
  if (fromBindings.length > 0) return [...new Set(fromBindings)];
  const gateVariants = mechanicsApproval?.[attempt?.attempt_id]?.variants;
  if (!Array.isArray(gateVariants)) return [];
  const fromGate: string[] = gateVariants
    .map((item: any) => String(item?.variant_id || ""))
    .filter(Boolean);
  return [...new Set(fromGate)];
}

export function attemptOptionLabel(
  attempt: any,
  currentVariant: string,
  mechanicsApproval: Record<string, any> = {},
): string {
  const variants = attemptVariantIds(attempt, mechanicsApproval);
  const scope =
    variants.length === 1
      ? `${variants[0]} only`
      : variants.length > 1
        ? variants.join(" + ")
        : "variant scope unavailable";
  const target = variants.at(-1);
  const relationship =
    target && target === currentVariant
      ? `targets ${target}`
      : target
        ? `historical ${target}`
        : "target unknown";
  return `${friendlyAttemptLabel(attempt)} · ${scope} · ${relationship}`;
}

export function friendlyAttemptLabel(attempt: any): string {
  const kind = humanize(attempt?.attempt_kind || "Original");
  const created = String(attempt?.created_at || "");
  const day = created.length >= 10 ? created.slice(0, 10) : "date not recorded";
  const attemptId = String(attempt?.attempt_id || "original");
  const suffix =
    attemptId === "original" ? "original" : attemptId.slice(-8);
  return `${kind} · ${day} · ${suffix}`;
}

function ExactAttemptIdentity({ attemptId }: { attemptId: string }) {
  return (
    <span className="exact-identity">
      <span>
        Exact ID <code>{attemptId}</code>
      </span>
      <button
        type="button"
        className="copy-id"
        aria-label={`Copy exact attempt ID ${attemptId}`}
        title="Copy exact attempt ID"
        onClick={() => void navigator.clipboard?.writeText(attemptId)}
      >
        Copy
      </button>
    </span>
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
  const activeAttemptId = String(
    detail.workflow_context?.current_attempt_id || "",
  );
  const activeVariantId = String(
    detail.workflow_context?.target_variant_id || state.current_variant_id || "",
  );

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

  if (!state.eligible) {
    if (
      detail.workflow_context?.stage === "mechanics_evidence" &&
      activeAttemptId &&
      activeVariantId
    ) {
      return (
        <Card className="form-section">
          <Notice
            tone="info"
            title={`${activeVariantId} is frozen and ready for mechanics evidence`}
          >
            Sequential variants stay under their governed attempt identity. No
            separate follow-up attempt is required before mechanics validation.
          </Notice>
          <Link
            className="button button-primary"
            to={`/research/${encodeURIComponent(
              campaign.campaign_id,
            )}/testing?attempt=${encodeURIComponent(
              activeAttemptId,
            )}&variant=${encodeURIComponent(activeVariantId)}`}
          >
            Generate mechanics evidence · {activeVariantId}
          </Link>
        </Card>
      );
    }
    return (
      <details className="locked-secondary-action">
        <summary>Next variant is locked</summary>
        <p>
          A genuinely different mechanic is available only after the current
          variant receives a completed manual mechanics decision and a terminal
          scientific FAIL.
        </p>
        <small>
          {(state.blockers || ["The current governed workflow must finish first."]).join(
            " · ",
          )}
        </small>
      </details>
    );
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

export function VerdictDecisionMatrix({
  scientificValidity,
  genericVerdict,
  accountEvaluations = [],
  evidenceErrors = [],
}: {
  scientificValidity: string;
  genericVerdict: string;
  accountEvaluations?: any[];
  evidenceErrors?: unknown[];
}) {
  const verificationErrors = Array.isArray(evidenceErrors)
    ? evidenceErrors
    : evidenceErrors
      ? [evidenceErrors]
      : [];
  const accountPass = accountEvaluations.some(
    (item: any) => String(item.verdict).toUpperCase() === "PASS",
  );
  const evidenceVerdict = verificationErrors.length
    ? "NEEDS MANUAL REVIEW"
    : "PASS";
  const nextAction =
    scientificValidity === "FAIL"
      ? "Reject this variant or, after reviewed terminal failure, prepare one materially different successor."
      : scientificValidity !== "PASS" || evidenceVerdict !== "PASS"
        ? "Resolve the evidence or governance blocker before promotion."
        : genericVerdict === "PASS"
          ? "Open independent candidate review. PASS remains candidate-only."
          : accountPass
            ? "Open profile-scoped candidate review for the passing frozen account contract."
            : "Do not promote. Generic objectives failed and no destination-specific PASS exists.";
  const rows = [
    {
      label: "Scientific validity",
      value: scientificValidity,
      detail: scientificValidity === "PASS"
        ? "Causal, data, mechanics, and robustness evidence passed."
        : "Promotion remains closed at the scientific gate.",
    },
    {
      label: "Generic objectives",
      value: genericVerdict,
      detail: genericVerdict === "PASS"
        ? "The frozen generic return and risk objectives passed."
        : "The frozen generic destination was not achieved.",
    },
    {
      label: "Named account destination",
      value: accountEvaluations.length ? (accountPass ? "PASS" : "FAIL") : "NOT ASSESSED",
      detail: accountEvaluations.length
        ? `${accountEvaluations.length} hash-bound account assessment(s).`
        : "Optional unless a specific account destination was declared.",
    },
    {
      label: "Evidence integrity",
      value: evidenceVerdict,
      detail: verificationErrors.length
        ? `${verificationErrors.length} verification error(s) require review.`
        : "The finalized result exposed no verification errors.",
    },
    {
      label: "Deployment authorization",
      value: "NOT AUTHORIZED",
      detail: "Backtest and candidate review never submit orders or authorize deployment.",
    },
  ];
  return (
    <Card className="verdict-decision-matrix">
      <div className="card-kicker">
        <div>
          <p className="eyebrow">Authoritative decision summary</p>
          <h2>What passed, what failed, and what happens next</h2>
        </div>
      </div>
      <div className="verdict-matrix" role="table" aria-label="Final verdict matrix">
        {rows.map((row) => (
          <div className="verdict-matrix-row" role="row" key={row.label}>
            <strong>{row.label}</strong>
            <StatusBadge value={row.value} kind="scientific" />
            <span>{row.detail}</span>
          </div>
        ))}
      </div>
      <Notice tone={scientificValidity === "FAIL" ? "danger" : scientificValidity === "PASS" ? "info" : "warning"} title="Exact next action">
        {nextAction}
      </Notice>
    </Card>
  );
}

export function Results({ detail }: { detail: any }) {
  const { data: studioData, refresh: refreshStudio } = useStudio();
  const [searchParams, setSearchParams] = useSearchParams();
  const rows = detail.stage_matrix || [];
  const attempts = detail.attempts || [];
  const workflow = detail.workflow_context || {};
  const [attemptResults, setAttemptResults] = useState(
    detail.attempt_results || {},
  );
  const [accountEvaluations, setAccountEvaluations] = useState<any[]>(
    detail.account_evaluations || [],
  );
  const [resultsLoading, setResultsLoading] = useState(
    Boolean(detail.campaign?.campaign_id),
  );
  const [resultsError, setResultsError] = useState("");
  const accountProfiles = studioData.libraries?.account_profiles || [];
  const frozenDestinationProfiles =
    detail.protocol?.destination_benchmark_contract?.profiles || [];
  const assessmentAccountProfiles = frozenDestinationProfiles.length
    ? accountProfiles.filter((profile: any) =>
        frozenDestinationProfiles.some(
          (item: any) =>
            item.profile_id === profile.profile_id &&
            item.profile_version === profile.version,
        ),
      )
    : accountProfiles;
  const frozenPrimaryProfile = frozenDestinationProfiles.find(
    (item: any) => item.role === "primary",
  );
  const [assessmentOpen, setAssessmentOpen] = useState(false);
  const [assessmentProfileKey, setAssessmentProfileKey] = useState(
    frozenPrimaryProfile
      ? `${frozenPrimaryProfile.profile_id}@${frozenPrimaryProfile.profile_version}`
      : "",
  );
  const [assessmentCosts, setAssessmentCosts] = useState({
    evaluation_purchase_price: "",
    activation_fee: "",
    other_upfront_costs: "0",
    cost_observed_at: new Date().toISOString().slice(0, 16),
    cost_source: "",
  });
  const [assessmentAttestations, setAssessmentAttestations] = useState<string[]>([]);
  const [assessmentBusy, setAssessmentBusy] = useState(false);
  const [assessmentFeedback, setAssessmentFeedback] = useState("");
  const [assessmentJobId, setAssessmentJobId] = useState("");
  useEffect(() => {
    const campaignId = detail.campaign?.campaign_id;
    if (!campaignId) return;
    setResultsLoading(true);
    api
      .campaignResults(campaignId)
      .then((value) => {
        setAttemptResults(value.attempt_results || {});
        setAccountEvaluations(value.account_evaluations || []);
        setResultsError(
          (value.partial_errors || [])
            .map((item: any) => item.message)
            .join(" · "),
        );
      })
      .catch((reason) =>
        setResultsError(
          reason instanceof Error
            ? reason.message
            : "Historical results are unavailable",
        ),
      )
      .finally(() => setResultsLoading(false));
  }, [detail.campaign?.campaign_id]);
  const initialAttempt =
    searchParams.get("attempt") ||
    workflow.current_attempt_id ||
    attempts.at(-1)?.attempt_id ||
    "original";
  const [selectedAttemptId, setSelectedAttemptId] = useState(initialAttempt);
  const selectedAttempt =
    attempts.find((item: any) => item.attempt_id === selectedAttemptId) ||
    attempts.at(-1) ||
    {};
  const exactResults = attemptResults[selectedAttemptId] || {};
  const attemptVariants = [
    ...new Set([
      ...attemptVariantIds(selectedAttempt, detail.mechanics_approval),
      ...Object.keys(exactResults),
    ]),
  ];
  const [selected, setSelected] = useState(
    searchParams.get("variant") ||
      workflow.target_variant_id ||
      attemptVariants.at(-1) ||
      "v01",
  );
  const result = exactResults[selected] || {};
  const latestFinalized = [...attempts]
    .reverse()
    .flatMap((attempt: any) =>
      Object.keys(attemptResults[attempt.attempt_id] || {}).map(
        (variantId) => ({
          attemptId: String(attempt.attempt_id),
          attempt,
          variantId,
        }),
      ),
    )[0];
  const hasExactResult = Boolean(exactResults[selected]);
  const exactAccountEvaluations = accountEvaluations.filter(
    (item: any) =>
      String(item.source_attempt_id || item.attempt_id || "") === selectedAttemptId &&
      String(item.variant_id || "") === selected,
  );
  const selectedAssessmentProfile = accountProfiles.find(
    (item: any) => `${item.profile_id}@${item.version}` === assessmentProfileKey,
  );
  const frozenAssessmentProfile = frozenDestinationProfiles.find(
    (item: any) =>
      `${item.profile_id}@${item.profile_version}` === assessmentProfileKey,
  );
  useEffect(() => {
    if (!assessmentJobId) return;
    const timer = window.setInterval(() => {
      api.jobs().then(async (raw) => {
        const jobs = Array.isArray(raw) ? raw : raw.jobs || [];
        const job: any = jobs.find((item: any) => item.job_id === assessmentJobId);
        const state = String(job?.operational_state || job?.state || "");
        if (!["SUCCEEDED", "FAILED_OPERATIONAL", "BLOCKED", "CANCELLED"].includes(state)) return;
        window.clearInterval(timer);
        setAssessmentJobId("");
        setAssessmentBusy(false);
        if (state === "SUCCEEDED") {
          const refreshed = await api.campaignResults(detail.campaign?.campaign_id, true);
          setAccountEvaluations(refreshed.account_evaluations || []);
          setAssessmentFeedback(
            `Account assessment completed with ${job.research_verdict || job.result?.research_verdict || "a governed"} verdict.`,
          );
          setAssessmentOpen(false);
          await refreshStudio();
        } else {
          setAssessmentFeedback(job?.error || job?.blocked_reason || `Account assessment ended ${state}.`);
        }
      }).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [assessmentJobId, detail.campaign?.campaign_id, refreshStudio]);

  async function queueAccountAssessment(event: React.FormEvent) {
    event.preventDefault();
    if (!selectedAssessmentProfile) {
      setAssessmentFeedback("Select a governed account profile.");
      return;
    }
    setAssessmentBusy(true);
    setAssessmentFeedback("");
    try {
      const costsAreFrozen = Boolean(frozenAssessmentProfile);
      const costRequired =
        !costsAreFrozen && selectedAssessmentProfile.cost_input_required === true;
      const evaluationPriceRequired =
        selectedAssessmentProfile.evaluation_price_input_required === true;
      const result = await api.queueAccountAssessment(detail.campaign?.campaign_id, {
        attempt_id: selectedAttemptId,
        variant_id: selected,
        profile_id: selectedAssessmentProfile.profile_id,
        profile_version: selectedAssessmentProfile.version,
        evaluation_purchase_price: !costsAreFrozen && evaluationPriceRequired
          ? Number(assessmentCosts.evaluation_purchase_price)
          : null,
        activation_fee:
          !costsAreFrozen && selectedAssessmentProfile.activation_fee_input_required
          ? Number(assessmentCosts.activation_fee)
          : null,
        other_upfront_costs: costsAreFrozen
          ? 0
          : Number(assessmentCosts.other_upfront_costs || 0),
        cost_observed_at: costRequired
          ? new Date(assessmentCosts.cost_observed_at).toISOString()
          : null,
        cost_source: costRequired ? assessmentCosts.cost_source.trim() : null,
        manual_attestations: assessmentAttestations,
      });
      setAssessmentJobId(result.job.job_id);
      setAssessmentFeedback(
        `Queued ${selectedAssessmentProfile.name}. Studio is running ${Number(selectedAssessmentProfile.evaluation_policy?.monte_carlo_runs || 0).toLocaleString()} profile-specific paths.`,
      );
      await refreshStudio();
    } catch (error) {
      setAssessmentBusy(false);
      setAssessmentFeedback(error instanceof Error ? error.message : "Account assessment was not queued");
    }
  }
  const verdict =
    result["research verdict"] ||
    result.research_verdict ||
    result.verdict ||
    "PENDING";
  const scientificValidity =
    result.scientific_validity_verdict || "NEEDS MANUAL REVIEW";
  const criteria = result.stage_criteria || [];
  const metrics = result.metrics || {};
  const artifactPreviews = result.artifact_previews || {};
  const coreGrid = result.core_grid_inspection || {};
  const coreGridRows =
    artifactPreviews.parameter_neighbors?.preview_rows || [];
  const defaultIteration = coreGrid.available
    ? String(coreGrid.default_run_id)
    : "";
  const [selectedIteration, setSelectedIteration] =
    useState(defaultIteration);
  useEffect(() => {
    setSelectedIteration(defaultIteration);
  }, [selected, result.run_id, defaultIteration]);
  function selectAttempt(value: string) {
    const attempt =
      attempts.find((item: any) => item.attempt_id === value) || {};
    const variants = [
      ...new Set([
        ...attemptVariantIds(attempt, detail.mechanics_approval),
        ...Object.keys(attemptResults[value] || {}),
      ]),
    ];
    const nextVariant = variants.at(-1) || "v01";
    setSelectedAttemptId(value);
    setSelected(nextVariant);
    const next = new URLSearchParams(searchParams);
    next.set("attempt", value);
    next.set("variant", nextVariant);
    setSearchParams(next, { replace: true });
  }
  function selectVariant(value: string) {
    setSelected(value);
    const next = new URLSearchParams(searchParams);
    next.set("attempt", selectedAttemptId);
    next.set("variant", value);
    setSearchParams(next, { replace: true });
  }
  function selectFinalizedResult(attemptId: string, variantId: string) {
    setSelectedAttemptId(attemptId);
    setSelected(variantId);
    const next = new URLSearchParams(searchParams);
    next.set("attempt", attemptId);
    next.set("variant", variantId);
    setSearchParams(next, { replace: true });
  }
  const selectedIterationRow = coreGridRows.find(
    (row: any) => String(row.run_id) === selectedIteration,
  );
  const inspectingDeclaredDefault =
    Boolean(defaultIteration) && selectedIteration === defaultIteration;
  const displayedMetrics =
    selectedIterationRow && !inspectingDeclaredDefault
      ? coreGridIterationMetrics(
          selectedIterationRow,
          coreGrid.parameter_columns || [],
        )
      : metrics;
  const metricsHeading = coreGrid.available
    ? inspectingDeclaredDefault
      ? "Declared-default fixed-config metrics"
      : `Iteration ${selectedIteration} summary metrics`
    : "Required metrics";
  const requiredAssessmentAttestations =
    selectedAssessmentProfile?.rules?.manual_attestations_required || [];
  const assessmentCostsComplete = selectedAssessmentProfile
    ? Boolean(frozenAssessmentProfile) ||
      ((!selectedAssessmentProfile.evaluation_price_input_required ||
        assessmentCosts.evaluation_purchase_price !== "") &&
      (!selectedAssessmentProfile.cost_input_required ||
        (assessmentCosts.cost_observed_at !== "" &&
          assessmentCosts.cost_source.trim() !== "")) &&
      (!selectedAssessmentProfile.activation_fee_input_required ||
        assessmentCosts.activation_fee !== ""))
    : false;
  const assessmentAttestationsComplete = requiredAssessmentAttestations.every(
    (item: string) => assessmentAttestations.includes(item),
  );
  return (
    <>
      <section className="result-detail">
          <div className="result-toolbar">
            <div>
              <p className="eyebrow">Exact immutable evidence</p>
              <h2>Inspect governed result</h2>
            </div>
            <FieldLike label="Attempt">
              <select
                aria-label="Result attempt"
                value={selectedAttemptId}
                onChange={(event) => selectAttempt(event.target.value)}
              >
                {[...attempts].reverse().map((attempt: any) => (
                  <option key={attempt.attempt_id} value={attempt.attempt_id}>
                    {attemptOptionLabel(
                      attempt,
                      workflow.target_variant_id || "",
                      detail.mechanics_approval,
                    )}
                  </option>
                ))}
              </select>
              <ExactAttemptIdentity attemptId={selectedAttemptId} />
            </FieldLike>
            <FieldLike label="Variant">
              <select
                aria-label="Variant result"
                value={selected}
                onChange={(e) => selectVariant(e.target.value)}
              >
                {attemptVariants.map((variant: string) => (
                  <option key={variant} value={variant}>
                    {variant}
                  </option>
                ))}
              </select>
            </FieldLike>
          </div>
          <Notice tone={hasExactResult ? "info" : "warning"}>
            Showing only evidence from the selected immutable attempt for{" "}
            <strong>{selected}</strong>. Results from another attempt are never
            substituted.
          </Notice>
          {resultsError && (
            <Notice tone="warning" title="Some historical results are unavailable">
              {resultsError}
            </Notice>
          )}
          {resultsLoading ? (
            <Card>
              <Skeleton lines={5} />
            </Card>
          ) : !hasExactResult ? (
            <EmptyState
              icon="chart"
              title={`No finalized performance result for ${selected}`}
              body="This exact attempt has not produced a complete, hash-valid ResultBundleV2. Complete its current mechanics workflow before testing; historical results remain available by selecting their original attempt."
              action={
                <div className="empty-state-actions">
                  {latestFinalized &&
                    (latestFinalized.attemptId !== selectedAttemptId ||
                      latestFinalized.variantId !== selected) && (
                      <Button
                        variant="secondary"
                        onClick={() =>
                          selectFinalizedResult(
                            latestFinalized.attemptId,
                            latestFinalized.variantId,
                          )
                        }
                      >
                        View latest finalized · {latestFinalized.variantId}
                      </Button>
                    )}
                  {selectedAttemptId === workflow.current_attempt_id && (
                    <Link
                      className="button button-primary"
                      to={`/research/${detail.campaign?.campaign_id}/testing?attempt=${encodeURIComponent(
                        selectedAttemptId,
                      )}&variant=${encodeURIComponent(selected)}`}
                    >
                      Open current testing workflow
                    </Link>
                  )}
                </div>
              }
            />
          ) : (
            <>
          <VerdictDecisionMatrix
            scientificValidity={scientificValidity}
            genericVerdict={verdict}
            accountEvaluations={exactAccountEvaluations}
            evidenceErrors={result.errors || result.verification_errors || []}
          />
          {exactAccountEvaluations.length === 0 ? (
            <Notice tone="warning" title="No account-specific suitability verdict">
              This scientific result has not been replayed against a hash-bound
              challenge, funded, or live-account profile. It is not a universal
              tradeability decision.
            </Notice>
          ) : (
            <Card>
              <div className="card-kicker">
                <div>
                  <p className="eyebrow">Destination-specific evidence</p>
                  <h3>Account suitability</h3>
                </div>
                <span>{exactAccountEvaluations.length} governed assessment(s)</span>
              </div>
              <div className="criteria-list">
                {exactAccountEvaluations.map((item: any) => (
                  <div key={item.assessment_id}>
                    <span>
                      <strong>{item.profile_name || item.profile_id}</strong>
                      <small>
                        {item.profile_id}@{item.profile_version}
                      </small>
                    </span>
                    <span className="criterion-comparison">
                      <strong>
                        Closure risk: {displayMetric(item.probability_account_closed)}
                      </strong>
                      <small>
                        First payout: {displayMetric(item.probability_first_payout)} · Net
                        payout after costs: {displayMetric(item.expected_net_payout_after_costs)}
                      </small>
                    </span>
                    <StatusBadge value={item.verdict} kind="scientific" />
                    <small>
                      {scientificValidity === "PASS" && item.verdict === "PASS"
                        ? "Eligible for profile-scoped candidate review"
                        : "Not eligible for promotion"}
                    </small>
                  </div>
                ))}
              </div>
              <Notice tone="info">
                Account verdicts are separate from generic investment quality. Passing one
                profile does not imply suitability for another account, and scientific
                validity must still pass.
              </Notice>
            </Card>
          )}
          <Card>
            <div className="card-kicker">
              <div>
                <p className="eyebrow">Governed destination replay</p>
                <h3>Assess this result for a specific account</h3>
              </div>
              <Button
                variant="secondary"
                onClick={() => setAssessmentOpen((current) => !current)}
              >
                {assessmentOpen ? "Close assessment" : "Run account assessment"}
              </Button>
            </div>
            <p>
              Replay this exact finalized result against one reviewed challenge,
              funded-account, or live-account contract. The assessment does not
              change the strategy verdict or source attempt.
            </p>
            {assessmentFeedback && (
              <Notice tone={assessmentJobId ? "info" : "warning"}>
                {assessmentFeedback}
              </Notice>
            )}
            {assessmentOpen && (
              <form className="governed-patch" onSubmit={queueAccountAssessment}>
                <div className="form-grid two">
                  <Field
                    label="Account rule profile"
                    hint="Profiles are versioned and hash-bound to the assessment."
                  >
                    <select
                      value={assessmentProfileKey}
                      onChange={(event) => {
                        setAssessmentProfileKey(event.target.value);
                        setAssessmentAttestations([]);
                      }}
                    >
                      <option value="">Select a reviewed profile</option>
                      {assessmentAccountProfiles.map((profile: any) => (
                        <option
                          key={`${profile.profile_id}@${profile.version}`}
                          value={`${profile.profile_id}@${profile.version}`}
                        >
                          {profile.name} · {humanize(profile.phase)} · v{profile.version}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <div className="account-assessment-profile-link">
                    <span>Need the full rule contract?</span>
                    <Link to="/library/accounts">Inspect account rules</Link>
                  </div>
                </div>
                {selectedAssessmentProfile && (
                  <>
                    <Notice tone="info" title={selectedAssessmentProfile.name}>
                      {selectedAssessmentProfile.summary ||
                        `${humanize(selectedAssessmentProfile.phase)} profile ${selectedAssessmentProfile.profile_id}@${selectedAssessmentProfile.version}`}
                    </Notice>
                    {frozenAssessmentProfile && (
                      <Notice tone="success" title="Pre-PnL benchmark inputs are frozen">
                        Studio will reuse the hash-bound profile and acquisition
                        costs declared before performance testing. This assessment
                        cannot substitute current or more favorable checkout values.
                      </Notice>
                    )}
                    {!frozenAssessmentProfile &&
                      (selectedAssessmentProfile.cost_input_required ||
                      selectedAssessmentProfile.activation_fee_input_required) && (
                      <div className="form-grid two">
                        {selectedAssessmentProfile.evaluation_price_input_required && (
                          <Field
                            label="Challenge purchase price"
                            hint="Use the amount paid, after current discounts."
                          >
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              value={assessmentCosts.evaluation_purchase_price}
                              onChange={(event) =>
                                setAssessmentCosts((current) => ({
                                  ...current,
                                  evaluation_purchase_price: event.target.value,
                                }))
                              }
                            />
                          </Field>
                        )}
                        {selectedAssessmentProfile.activation_fee_input_required && (
                          <Field label="Activation fee">
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              value={assessmentCosts.activation_fee}
                              onChange={(event) =>
                                setAssessmentCosts((current) => ({
                                  ...current,
                                  activation_fee: event.target.value,
                                }))
                              }
                            />
                          </Field>
                        )}
                        <Field label="Other upfront costs">
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={assessmentCosts.other_upfront_costs}
                            onChange={(event) =>
                              setAssessmentCosts((current) => ({
                                ...current,
                                other_upfront_costs: event.target.value,
                              }))
                            }
                          />
                        </Field>
                        {selectedAssessmentProfile.cost_input_required && (
                          <>
                            <Field label="Cost observed at">
                              <input
                                type="datetime-local"
                                value={assessmentCosts.cost_observed_at}
                                onChange={(event) =>
                                  setAssessmentCosts((current) => ({
                                    ...current,
                                    cost_observed_at: event.target.value,
                                  }))
                                }
                              />
                            </Field>
                            <Field
                              label="Cost source"
                              hint="Official URL, invoice, or checkout reference."
                            >
                              <input
                                value={assessmentCosts.cost_source}
                                onChange={(event) =>
                                  setAssessmentCosts((current) => ({
                                    ...current,
                                    cost_source: event.target.value,
                                  }))
                                }
                              />
                            </Field>
                          </>
                        )}
                      </div>
                    )}
                    {requiredAssessmentAttestations.length > 0 && (
                      <fieldset className="forward-rule-list">
                        <legend>Confirm current rule interpretation</legend>
                        {requiredAssessmentAttestations.map((item: string) => (
                          <label key={item}>
                            <input
                              type="checkbox"
                              checked={assessmentAttestations.includes(item)}
                              onChange={(event) =>
                                setAssessmentAttestations((current) =>
                                  event.target.checked
                                    ? [...current, item]
                                    : current.filter((value) => value !== item),
                                )
                              }
                            />
                            <span>{humanize(item)}</span>
                          </label>
                        ))}
                      </fieldset>
                    )}
                    <Button
                      type="submit"
                      disabled={
                        assessmentBusy ||
                        !assessmentCostsComplete ||
                        !assessmentAttestationsComplete
                      }
                    >
                      {assessmentBusy
                        ? "Assessing exact evidence…"
                        : "Queue governed assessment"}
                    </Button>
                  </>
                )}
              </form>
            )}
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
                    <span className="criterion-comparison">
                      {isSkippedCriterion(item) ? (
                        <>
                          <strong>Not run</strong>
                          <small>{item.reason || "A prior gate stopped the sequence."}</small>
                        </>
                      ) : (
                        <>
                          <strong>Observed: {displayMetric(item.actual)}</strong>
                          <small>
                            Required: {item.operator || ""}{" "}
                            {displayMetric(item.threshold)}
                          </small>
                        </>
                      )}
                    </span>
                    <StatusBadge
                      value={isSkippedCriterion(item) ? "Not run" : item.result}
                      kind={isSkippedCriterion(item) ? undefined : "scientific"}
                    />
                  </div>
                ))}
              </div>
            </Card>
          )}
          {coreGrid.available && coreGridRows.length > 0 && (
            <Card className="core-grid-inspector">
              <div className="card-kicker">
                <div>
                  <p className="eyebrow">Core-grid inspection</p>
                  <h3>Inspect one parameter iteration</h3>
                </div>
                <StatusBadge
                  value={
                    inspectingDeclaredDefault
                      ? "Declared defaults"
                      : `Iteration ${selectedIteration}`
                  }
                />
              </div>
              <FieldLike label="Core-grid iteration">
                <select
                  aria-label="Core-grid iteration"
                  value={selectedIteration}
                  onChange={(event) =>
                    setSelectedIteration(event.target.value)
                  }
                >
                  {coreGridRows.map((row: any) => (
                    <option key={String(row.run_id)} value={String(row.run_id)}>
                      {coreGridIterationLabel(
                        row,
                        coreGrid.parameter_columns || [],
                        coreGrid.default_run_id,
                      )}
                    </option>
                  ))}
                </select>
              </FieldLike>
              {selectedIterationRow && (
                <dl className="core-grid-parameters">
                  {(coreGrid.parameter_columns || []).map((name: string) => (
                    <div key={name}>
                      <dt>{humanize(name.split(".").at(-1) || name)}</dt>
                      <dd>{displayMetric(selectedIterationRow[name])}</dd>
                    </div>
                  ))}
                </dl>
              )}
              <Notice tone="info">
                This selector changes inspection metrics only. The scientific
                verdict and profitable-iteration gate above remain based on all{" "}
                {coreGrid.iteration_count} hash-bound grid combinations.
              </Notice>
              {!coreGrid.iteration_reports_retained &&
                !inspectingDeclaredDefault && (
                  <Notice tone="warning">
                    This run retained summary metrics for every iteration, but
                    not per-iteration trade logs or equity curves. The reporting
                    evidence below remains scoped to the declared-default fixed
                    configuration.
                  </Notice>
                )}
            </Card>
          )}
          {Object.keys(displayedMetrics).length > 0 && (
            <Card>
              <h3>{metricsHeading}</h3>
              {coreGrid.available && (
                <p className="metric-scope">
                  {inspectingDeclaredDefault
                    ? `Frozen strategy defaults, corresponding to grid iteration ${defaultIteration}.`
                    : "Hash-bound summary row from the limited core grid."}
                </p>
              )}
              <div className="metrics-table">
                {Object.entries(displayedMetrics).map(
                  ([name, value]: [string, any]) => (
                    <div key={name}>
                      <span>{humanize(name)}</span>
                      <strong>{displayMetric(value)}</strong>
                      {value?.reason && <small>{value.reason}</small>}
                    </div>
                  ),
                )}
              </div>
            </Card>
          )}
          {Object.keys(artifactPreviews).length > 0 && (
            <ResultArtifactEvidence
              previews={artifactPreviews}
              campaignId={detail.campaign?.campaign_id}
              attemptId={selectedAttemptId}
              variantId={selected}
              parameterColumns={coreGrid.parameter_columns || []}
              declaredDefaultOnly={
                coreGrid.available &&
                !coreGrid.iteration_reports_retained &&
                !inspectingDeclaredDefault
              }
            />
          )}
          <TechnicalDetails>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </TechnicalDetails>
            </>
          )}
        </section>
      <section className="result-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Campaign-level history</p>
            <h2>Latest finalized result per variant</h2>
          </div>
        </div>
        <StageMatrix rows={rows} />
      </section>
    </>
  );
}

function coreGridIterationLabel(
  row: any,
  parameterColumns: string[],
  defaultRunId: string | number,
): string {
  const prefix =
    String(row.run_id) === String(defaultRunId)
      ? `Declared defaults — iteration ${row.run_id}`
      : `Iteration ${row.run_id}`;
  const parameters = parameterColumns.map((name) => {
    const label = humanize(name.split(".").at(-1) || name);
    return `${label} ${displayMetric(row[name])}`;
  });
  return [prefix, ...parameters].join(" · ");
}

function isSkippedCriterion(item: any): boolean {
  const actual =
    item?.actual && typeof item.actual === "object"
      ? item.actual.value
      : item?.actual;
  return String(actual || "").toLowerCase() === "skipped";
}

function coreGridIterationMetrics(
  row: any,
  parameterColumns: string[],
): Record<string, any> {
  const excluded = new Set([
    "run_id",
    ...parameterColumns,
    "signals_generated",
    "entries_opened",
    "trades_closed",
    "entry_rejections_total",
    "reject_missing_stop",
    "reject_target_already_reached",
    "reject_position_sizing",
    "reject_daily_risk_lockout",
    "reject_apex_latest_entry_time",
    "reject_event_no_trade_window",
  ]);
  return Object.fromEntries(
    Object.entries(row).filter(([name]) => !excluded.has(name)),
  );
}

export function ResultArtifactEvidence({
  previews,
  campaignId,
  attemptId,
  variantId,
  declaredDefaultOnly = false,
  parameterColumns = [],
}: {
  previews: Record<string, any>;
  campaignId?: string;
  attemptId?: string;
  variantId?: string;
  declaredDefaultOnly?: boolean;
  parameterColumns?: string[];
}) {
  const curves = ["equity_curve", "drawdown_curve"];
  const tables = [
    "yearly",
    "monthly",
    "entry_session",
    "side",
    "parameter_neighbors",
    "wfa_stitched_oos",
    "monte_carlo_summary",
    "wfa_windows",
    "monte_carlo_bands",
    "parameter_surface",
    "losing_streaks",
    "performance_statistics",
  ];
  return (
    <section className="artifact-evidence">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Hash-verified ResultBundleV2 evidence</p>
          <h2>Declared-default robustness and breakdowns</h2>
        </div>
        {campaignId && attemptId && variantId && (
          <div className="report-actions">
            <button
              type="button"
              className="button button-secondary"
              onClick={() => window.print()}
            >
              Print report
            </button>
            <a
              className="button button-primary"
              href={api.resultReportUrl(campaignId, attemptId, variantId)}
              download
            >
              Download due-diligence ZIP
            </a>
          </div>
        )}
      </div>
      {declaredDefaultOnly && (
        <Notice tone="warning">
          These curves and breakdowns do not change with the selected grid
          iteration because per-iteration reports were not retained.
        </Notice>
      )}
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
            {item.available && campaignId && attemptId && variantId && (
              <a
                className="artifact-download"
                href={api.resultArtifactUrl(
                  campaignId,
                  attemptId,
                  variantId,
                  name,
                )}
                download
              >
                Download CSV
              </a>
            )}
          </Card>
        ))}
      </div>
      <TradeExplorer
        tradeList={previews.trade_list}
        excursions={previews.mfe_mae}
        campaignId={campaignId}
        attemptId={attemptId}
        variantId={variantId}
      />
      <div className="result-curve-grid">
        {curves.map((name) => (
          <ResultCurve key={name} name={name} preview={previews[name]} />
        ))}
        <ResultCurve name="rolling_metrics" preview={previews.rolling_metrics} />
      </div>
      <DistributionExplorer
        pnl={previews.pnl_distribution}
        duration={previews.duration_distribution}
      />
      <div className="result-curve-grid">
        <ExcursionScatter preview={previews.mfe_mae} />
        <MonteCarloBandChart preview={previews.monte_carlo_bands} />
      </div>
      <ParameterHeatmap
        preview={previews.parameter_surface}
        parameterColumns={parameterColumns}
      />
      <div className="result-breakdown-stack">
        {tables.map((name) => (
          <ResultPreviewTable key={name} name={name} preview={previews[name]} />
        ))}
      </div>
    </section>
  );
}

function TradeExplorer({
  tradeList,
  excursions,
  campaignId,
  attemptId,
  variantId,
}: {
  tradeList: any;
  excursions: any;
  campaignId?: string;
  attemptId?: string;
  variantId?: string;
}) {
  const [query, setQuery] = useState("");
  const [side, setSide] = useState("all");
  const [outcome, setOutcome] = useState("all");
  const [exitReason, setExitReason] = useState("all");
  const [sort, setSort] = useState("sequence");
  const [minimumPnl, setMinimumPnl] = useState("");
  const [maximumPnl, setMaximumPnl] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const rows = tradeList?.preview_rows || [];
  const exitReasons: string[] = [
    ...new Set<string>(
      rows
        .map((row: any) => String(row.exit_reason || "").trim())
        .filter(Boolean),
    ),
  ].sort();
  const filtered = rows
    .filter((row: any) => {
      const matchesQuery = JSON.stringify(row)
        .toLowerCase()
        .includes(query.toLowerCase());
      const matchesSide =
        side === "all" || String(row.direction || "").toLowerCase() === side;
      const pnl = Number(row.net_pnl);
      const matchesOutcome =
        outcome === "all" ||
        (outcome === "winner" && pnl > 0) ||
        (outcome === "loser" && pnl < 0) ||
        (outcome === "breakeven" && pnl === 0);
      const matchesExit =
        exitReason === "all" || String(row.exit_reason || "") === exitReason;
      const matchesMinimum =
        minimumPnl === "" || (Number.isFinite(pnl) && pnl >= Number(minimumPnl));
      const matchesMaximum =
        maximumPnl === "" || (Number.isFinite(pnl) && pnl <= Number(maximumPnl));
      return (
        matchesQuery &&
        matchesSide &&
        matchesOutcome &&
        matchesExit &&
        matchesMinimum &&
        matchesMaximum
      );
    })
    .sort((left: any, right: any) => {
      if (sort === "pnl_desc") return Number(right.net_pnl) - Number(left.net_pnl);
      if (sort === "pnl_asc") return Number(left.net_pnl) - Number(right.net_pnl);
      if (sort === "latest")
        return String(right.exit_timestamp || right.exit_time || "").localeCompare(
          String(left.exit_timestamp || left.exit_time || ""),
        );
      return Number(left.trade_id || 0) - Number(right.trade_id || 0);
    });
  const selected =
    rows.find((row: any) => String(row.trade_id) === selectedId) ||
    filtered[0];
  const excursion = (excursions?.preview_rows || []).find(
    (row: any) => String(row.trade_id) === String(selected?.trade_id),
  );
  if (!tradeList)
    return null;
  return (
    <Card className="trade-explorer">
      <div className="card-kicker">
        <div>
          <p className="eyebrow">Result explorer</p>
          <h3>Search trades and inspect execution</h3>
        </div>
        <StatusBadge
          value={tradeList.available ? `${tradeList.rows} trades` : "Unavailable"}
        />
      </div>
      {!tradeList.available ? (
        <Notice tone="warning">{tradeList.reason}</Notice>
      ) : (
        <>
          <div className="result-explorer-controls">
            <FieldLike label="Search trade">
              <input
                value={query}
                placeholder="Trade ID, exit reason, timestamp…"
                onChange={(event) => setQuery(event.target.value)}
              />
            </FieldLike>
            <FieldLike label="Side">
              <select value={side} onChange={(event) => setSide(event.target.value)}>
                <option value="all">All sides</option>
                <option value="long">Long</option>
                <option value="short">Short</option>
              </select>
            </FieldLike>
            <FieldLike label="Outcome">
              <select value={outcome} onChange={(event) => setOutcome(event.target.value)}>
                <option value="all">All outcomes</option>
                <option value="winner">Winners</option>
                <option value="loser">Losers</option>
                <option value="breakeven">Breakeven</option>
              </select>
            </FieldLike>
            <FieldLike label="Exit reason">
              <select value={exitReason} onChange={(event) => setExitReason(event.target.value)}>
                <option value="all">All exit reasons</option>
                {exitReasons.map((reason) => (
                  <option key={reason} value={reason}>{humanize(reason)}</option>
                ))}
              </select>
            </FieldLike>
            <FieldLike label="Minimum PnL">
              <input
                type="number"
                value={minimumPnl}
                onChange={(event) => setMinimumPnl(event.target.value)}
                placeholder="No minimum"
              />
            </FieldLike>
            <FieldLike label="Maximum PnL">
              <input
                type="number"
                value={maximumPnl}
                onChange={(event) => setMaximumPnl(event.target.value)}
                placeholder="No maximum"
              />
            </FieldLike>
            <FieldLike label="Sort">
              <select value={sort} onChange={(event) => setSort(event.target.value)}>
                <option value="sequence">Trade sequence</option>
                <option value="latest">Latest first</option>
                <option value="pnl_desc">PnL · high to low</option>
                <option value="pnl_asc">PnL · low to high</option>
              </select>
            </FieldLike>
            <span className="result-filter-count">{filtered.length} matching trades</span>
          </div>
          <div className="trade-explorer-layout">
            <div className="trade-list" role="list" aria-label="Hash-bound trades">
              {filtered.slice(0, 200).map((row: any, index: number) => (
                <button
                  type="button"
                  role="listitem"
                  className={
                    String(selected?.trade_id) === String(row.trade_id)
                      ? "selected"
                      : ""
                  }
                  key={`${row.trade_id}-${index}`}
                  onClick={() => setSelectedId(String(row.trade_id))}
                >
                  <span>
                    <strong>Trade {displayMetric(row.trade_id)}</strong>
                    <small>
                      {humanize(row.direction || "unknown")} ·{" "}
                      {row.exit_reason ? humanize(row.exit_reason) : "exit not labelled"}
                    </small>
                  </span>
                  <strong
                    className={
                      Number(row.net_pnl) >= 0 ? "metric-positive" : "metric-negative"
                    }
                  >
                    {displayMetric(row.net_pnl)}
                  </strong>
                </button>
              ))}
              {!filtered.length && <p>No trades match these filters.</p>}
            </div>
            <ResultTradeChart
              trade={selected}
              excursion={excursion}
              campaignId={campaignId}
              attemptId={attemptId}
              variantId={variantId}
            />
          </div>
          {tradeList.truncated && (
            <Notice tone="info">
              The browser list is a deterministic preview. Download the complete
              hash-bound CSV for exhaustive filtering.
            </Notice>
          )}
        </>
      )}
    </Card>
  );
}

function retainedFiniteNumber(value: any): number | null {
  if (value === null || value === undefined || value === "" || typeof value === "boolean")
    return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export function ResultTradeChart({
  trade,
  excursion,
  campaignId,
  attemptId,
  variantId,
}: {
  trade: any;
  excursion: any;
  campaignId?: string;
  attemptId?: string;
  variantId?: string;
}) {
  if (!trade)
    return <Notice tone="warning">Select a trade to inspect it.</Notice>;
  const levels = [
    ["Entry", trade.entry_price, "#285e75"],
    ["Stop", trade.stop_price, "#a3342c"],
    ["Target", trade.target_price, "#18724d"],
    ["Exit", trade.exit_price, "#5d4b8a"],
  ].flatMap(([label, value, color]) => {
    const numeric = retainedFiniteNumber(value);
    return numeric === null ? [] : [[label, numeric, color] as [string, number, string]];
  });
  const values = levels.map(([, value]) => value);
  const observedLow = values.length ? Math.min(...values) : 0;
  const observedHigh = values.length ? Math.max(...values) : 1;
  const observedSpread = Math.max(observedHigh - observedLow, 0.25);
  const padding = Math.max(observedSpread * 0.12, 0.25);
  const low = observedLow - padding;
  const high = observedHigh + padding;
  const spread = high - low;
  const y = (value: number) => 24 + ((high - value) * 192) / spread;
  const sortedLevels = [...levels].sort((left, right) => right[1] - left[1]);
  const labelY = new Map(
    sortedLevels.map(([label], index) => [
      label,
      sortedLevels.length === 1
        ? y(sortedLevels[0][1])
        : 28 + (index * 184) / (sortedLevels.length - 1),
    ]),
  );
  const entryTime = Date.parse(String(trade.entry_timestamp || ""));
  const exitTime = Date.parse(String(trade.exit_timestamp || ""));
  const durationMinutes =
    Number.isFinite(entryTime) && Number.isFinite(exitTime) && exitTime >= entryTime
      ? (exitTime - entryTime) / 60000
      : null;
  return (
    <div className="result-trade-chart">
      <div>
        <p className="eyebrow">Trade {displayMetric(trade.trade_id)}</p>
        <h4>Execution-level summary</h4>
        <small>
          This chart uses retained trade fields; it does not invent an intratrade
          bar path. Use Mechanics Review for governed event replay.
        </small>
      </div>
      {levels.length ? (
        <svg viewBox="0 0 640 240" role="img" aria-label="Trade price levels">
          {levels.map(([label, value, color]) => (
            <g key={label}>
              <line
                data-level={label}
                x1="20"
                x2="440"
                y1={y(value)}
                y2={y(value)}
                stroke={color}
                strokeDasharray="8 5"
              />
              <circle cx="440" cy={y(value)} r="3" fill={color} />
              <line
                x1="440"
                x2="470"
                y1={y(value)}
                y2={labelY.get(label)}
                stroke={color}
                strokeWidth="1"
              />
              <text x="478" y={(labelY.get(label) || 0) + 4} fill={color}>
                {label} {displayMetric(value)}
              </text>
            </g>
          ))}
        </svg>
      ) : (
        <Notice tone="warning">Entry and exit price fields were not retained.</Notice>
      )}
      <dl className="core-grid-parameters">
        <div>
          <dt>MAE</dt>
          <dd>{displayMetric(excursion?.mae)}</dd>
        </div>
        <div>
          <dt>MFE</dt>
          <dd>{displayMetric(excursion?.mfe)}</dd>
        </div>
        <div>
          <dt>Duration</dt>
          <dd>
            {durationMinutes !== null
              ? `${durationMinutes.toFixed(1)} min`
              : "Not retained"}
          </dd>
        </div>
      </dl>
      {campaignId && attemptId && variantId && trade.trade_id != null && (
        <Link
          className="button button-secondary trade-replay-link"
          to={`/reviews?type=mechanics&campaign=${encodeURIComponent(
            campaignId,
          )}&attempt=${encodeURIComponent(attemptId)}&variant=${encodeURIComponent(
            variantId,
          )}&trade=${encodeURIComponent(String(trade.trade_id))}`}
        >
          Open this trade in mechanics replay
        </Link>
      )}
    </div>
  );
}

function DistributionExplorer({ pnl, duration }: { pnl: any; duration: any }) {
  const charts = [
    ["PnL distribution", pnl],
    ["Trade-duration distribution", duration],
  ] as const;
  return (
    <div className="result-curve-grid">
      {charts.map(([title, preview]) => {
        const rows = preview?.preview_rows || [];
        const max = Math.max(...rows.map((row: any) => Number(row.count) || 0), 1);
        return (
          <Card className="distribution-chart" key={title}>
            <div className="card-kicker">
              <h3>{title}</h3>
              <small>{preview?.available ? `${preview.rows} bins` : "Unavailable"}</small>
            </div>
            {!preview?.available ? (
              <Notice tone="warning">{preview?.reason || "Evidence unavailable"}</Notice>
            ) : (
              <div className="histogram" aria-label={title}>
                {rows.map((row: any, index: number) => (
                  <span
                    key={index}
                    title={`${displayMetric(row.bin_start)}–${displayMetric(row.bin_end)}: ${row.count}`}
                    style={{ height: `${Math.max(3, (Number(row.count) / max) * 100)}%` }}
                  />
                ))}
              </div>
            )}
          </Card>
        );
      })}
    </div>
  );
}

function ExcursionScatter({ preview }: { preview: any }) {
  const rows = (preview?.preview_rows || []).filter(
    (row: any) =>
      Number.isFinite(Number(row.mae)) || Number.isFinite(Number(row.mfe)),
  );
  return (
    <Card className="result-curve-card">
      <div className="card-kicker">
        <h3>MAE / MFE by trade</h3>
        <small>{preview?.available ? `${preview.rows} trades` : "Unavailable"}</small>
      </div>
      {!preview?.available || !rows.length ? (
        <Notice tone="warning">
          {preview?.reason || "Excursion fields were not retained."}
        </Notice>
      ) : (
        <svg viewBox="0 0 760 220" role="img" aria-label="MAE and MFE scatter plot">
          {rows.map((row: any, index: number) => {
            const x = 20 + (index * 720) / Math.max(rows.length - 1, 1);
            const extent = Math.max(
              ...rows.flatMap((item: any) => [
                Math.abs(Number(item.mae) || 0),
                Math.abs(Number(item.mfe) || 0),
              ]),
              1,
            );
            const center = 110;
            const maeY = center + (Math.abs(Number(row.mae) || 0) * 85) / extent;
            const mfeY = center - (Math.abs(Number(row.mfe) || 0) * 85) / extent;
            return (
              <g key={`${row.trade_id}-${index}`}>
                {Number.isFinite(Number(row.mae)) && (
                  <circle cx={x} cy={maeY} r="3.5" fill="#a3342c" />
                )}
                {Number.isFinite(Number(row.mfe)) && (
                  <circle cx={x} cy={mfeY} r="3.5" fill="#18724d" />
                )}
              </g>
            );
          })}
          <line x1="18" x2="742" y1="110" y2="110" stroke="#9aa7a8" />
          <text x="24" y="28" fill="#18724d">MFE</text>
          <text x="24" y="205" fill="#a3342c">MAE</text>
        </svg>
      )}
    </Card>
  );
}

function MonteCarloBandChart({ preview }: { preview: any }) {
  const rows = preview?.preview_rows || [];
  const numericColumns = (preview?.columns || []).filter(
    (column: string) =>
      column !== "sequence" &&
      rows.some((row: any) => Number.isFinite(Number(row[column]))),
  );
  const values = rows.flatMap((row: any) =>
    numericColumns.map((column: string) => Number(row[column])).filter(Number.isFinite),
  );
  if (!preview?.available || !rows.length || numericColumns.length < 2)
    return (
      <Card className="result-curve-card">
        <h3>Monte Carlo probability bands</h3>
        <Notice tone="warning">
          {preview?.reason || "Path quantiles were not retained."}
        </Notice>
      </Card>
    );
  const low = Math.min(...values);
  const high = Math.max(...values);
  const spread = Math.max(high - low, 1e-9);
  const colors = ["#a3342c", "#285e75", "#18724d", "#7c3aed"];
  return (
    <Card className="result-curve-card">
      <div className="card-kicker">
        <h3>Monte Carlo probability bands</h3>
        <small>{numericColumns.join(" · ")}</small>
      </div>
      <svg viewBox="0 0 760 220" role="img" aria-label="Monte Carlo probability bands">
        {numericColumns.slice(0, 4).map((column: string, series: number) => {
          const points = rows
            .map((row: any, index: number) => {
              const value = Number(row[column]);
              if (!Number.isFinite(value)) return null;
              const x = 18 + (index * 724) / Math.max(rows.length - 1, 1);
              const y = 18 + ((high - value) * 184) / spread;
              return `${x},${y}`;
            })
            .filter(Boolean)
            .join(" ");
          return (
            <polyline
              key={column}
              points={points}
              fill="none"
              stroke={colors[series]}
              strokeWidth={series === 1 ? "3" : "2"}
            />
          );
        })}
      </svg>
    </Card>
  );
}

function parameterHeatmapLabel(name: string): string {
  const withoutPrefix = name.includes(".params.")
    ? name.split(".params.").at(-1) || name
    : name;
  return humanize(withoutPrefix.replaceAll(".", "_"));
}

function parameterHeatmapKey(value: any): string {
  return `${typeof value}:${String(value)}`;
}

function parameterHeatmapValues(rows: any[], name: string): any[] {
  const seen = new Set<string>();
  return rows.flatMap((row) => {
    const value = row[name];
    const key = parameterHeatmapKey(value);
    if (value === null || value === undefined || seen.has(key)) return [];
    seen.add(key);
    return [value];
  });
}

function parameterHeatmapReference(metric: string): number {
  return metric === "profit_factor" ? 1 : 0;
}

function parameterHeatmapTone(
  value: number,
  reference: number,
): "negative" | "neutral" | "positive" {
  if (value < reference) return "negative";
  if (value > reference) return "positive";
  return "neutral";
}

function parameterHeatmapColor(
  value: number,
  low: number,
  high: number,
  reference: number,
): string {
  if (value === reference) return "var(--surface-2)";
  if (value < reference) {
    const span = Math.max(reference - low, Number.EPSILON);
    const intensity = Math.min(1, Math.max(0, (reference - value) / span));
    return `color-mix(in srgb, #a3342c ${Math.round(18 + intensity * 62)}%, #ffffff)`;
  }
  const span = Math.max(high - reference, Number.EPSILON);
  const intensity = Math.min(1, Math.max(0, (value - reference) / span));
  return `color-mix(in srgb, #18724d ${Math.round(18 + intensity * 62)}%, #ffffff)`;
}

export function ParameterHeatmap({
  preview,
  parameterColumns = [],
}: {
  preview: any;
  parameterColumns?: string[];
}) {
  if (!preview)
    return null;
  const rows = preview.preview_rows || [];
  const columns = preview.columns || [];
  const metric = [
    "net_profit_after_costs",
    "net_profit",
    "profit_factor",
    "expectancy",
    "expectancy_r",
  ].find((name) => columns.includes(name));
  const declaredParameters = parameterColumns.filter((name) =>
    columns.includes(name),
  );
  const inferredParameters = columns.filter((name: string) =>
    /(^|\.)params\./.test(name),
  );
  const parameters = declaredParameters.length
    ? declaredParameters
    : inferredParameters;
  const xName = parameters[0];
  const yName = parameters[1];
  const finiteRows = rows.filter((row: any) =>
    Number.isFinite(Number(row[metric || ""])),
  );
  const values = finiteRows.map((row: any) => Number(row[metric || ""]));
  const low = values.length ? Math.min(...values) : 0;
  const high = values.length ? Math.max(...values) : 0;
  const reference = parameterHeatmapReference(metric || "");
  const xValues = xName ? parameterHeatmapValues(finiteRows, xName) : [];
  const yValues = yName
    ? parameterHeatmapValues(finiteRows, yName)
    : [null];
  const cells = new Map<string, any>(
    finiteRows.map((row: any) => [
      `${parameterHeatmapKey(row[xName])}|${yName ? parameterHeatmapKey(row[yName]) : ""}`,
      row,
    ]),
  );
  const allBelowReference = values.length > 0 && high < reference;
  const allAboveReference = values.length > 0 && low > reference;
  const referenceLabel = metric === "profit_factor" ? "1.0" : "zero";
  return (
    <Card className="parameter-heatmap">
      <div className="card-kicker">
        <div>
          <p className="eyebrow">Parameter stability</p>
          <h3>Parameter heatmap</h3>
        </div>
        <small>{metric ? humanize(metric) : "Metric unavailable"}</small>
      </div>
      {!preview.available || !metric || !xName || !finiteRows.length ? (
        <Notice tone="warning">
          {preview.reason || "At least one parameter and a performance metric are required."}
        </Notice>
      ) : parameters.length > 2 ? (
        <Notice tone="warning">
          A two-axis heatmap cannot faithfully display {parameters.length} parameter
          dimensions. Inspect the hash-verified parameter surface table below.
        </Notice>
      ) : (
        <>
          <div className="heatmap-axis-summary">
            <span><strong>Columns:</strong> {parameterHeatmapLabel(xName)}</span>
            {yName && <span><strong>Rows:</strong> {parameterHeatmapLabel(yName)}</span>}
          </div>
          <div className="heatmap-legend" aria-label="Heatmap color scale">
            <span className="heatmap-legend-negative" />
            <small>Below {referenceLabel}</small>
            <span className="heatmap-legend-neutral" />
            <small>{referenceLabel}</small>
            <span className="heatmap-legend-positive" />
            <small>Above {referenceLabel}</small>
          </div>
          {(allBelowReference || allAboveReference) && (
            <p
              className={`heatmap-scale-note ${allBelowReference ? "negative" : "positive"}`}
            >
              All displayed {humanize(metric).toLowerCase()} results are {allBelowReference ? `below ${referenceLabel}` : `above ${referenceLabel}`}.
            </p>
          )}
          <div className="heatmap-scroll">
            <div
              className="heatmap-matrix"
              role="table"
              aria-label={`${humanize(metric)} by ${parameterHeatmapLabel(xName)}${yName ? ` and ${parameterHeatmapLabel(yName)}` : ""}`}
              style={{
                gridTemplateColumns: `${yName ? "minmax(150px, max-content) " : ""}repeat(${xValues.length}, minmax(110px, 1fr))`,
              }}
            >
              <div className="heatmap-matrix-row" role="row">
                {yName && (
                  <div className="heatmap-axis-corner" role="columnheader">
                    Row / column
                  </div>
                )}
                {xValues.map((xValue) => (
                  <div
                    className="heatmap-column-header"
                    role="columnheader"
                    key={parameterHeatmapKey(xValue)}
                  >
                    {displayMetric(xValue)}
                  </div>
                ))}
              </div>
              {yValues.map((yValue) => (
                <div
                  className="heatmap-matrix-row"
                  role="row"
                  key={yName ? parameterHeatmapKey(yValue) : "single-row"}
                >
                  {yName && (
                    <div className="heatmap-row-header" role="rowheader">
                      {displayMetric(yValue)}
                    </div>
                  )}
                  {xValues.map((xValue) => {
                    const cell = cells.get(
                      `${parameterHeatmapKey(xValue)}|${yName ? parameterHeatmapKey(yValue) : ""}`,
                    );
                    if (!cell)
                      return (
                        <div
                          className="heatmap-cell unavailable"
                          role="cell"
                          key={parameterHeatmapKey(xValue)}
                          aria-label={`${parameterHeatmapLabel(xName)} ${displayMetric(xValue)}${yName ? `, ${parameterHeatmapLabel(yName)} ${displayMetric(yValue)}` : ""}: unavailable`}
                        >
                          —
                        </div>
                      );
                    const value = Number(cell[metric]);
                    const tone = parameterHeatmapTone(value, reference);
                    const label = `${parameterHeatmapLabel(xName)} ${displayMetric(xValue)}${yName ? ` · ${parameterHeatmapLabel(yName)} ${displayMetric(yValue)}` : ""} · ${humanize(metric)} ${displayMetric(value)}`;
                    return (
                      <div
                        className="heatmap-cell"
                        role="cell"
                        data-tone={tone}
                        key={parameterHeatmapKey(xValue)}
                        style={{
                          background: parameterHeatmapColor(
                            value,
                            low,
                            high,
                            reference,
                          ),
                        }}
                        title={label}
                        aria-label={label}
                      >
                        <strong>{displayMetric(value)}</strong>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </Card>
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
  const yKey =
    name === "equity_curve"
      ? "equity"
      : name === "rolling_metrics"
        ? "rolling_net_pnl"
        : "drawdown";
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

function PromotionChecklist({
  detail,
  records,
}: {
  detail: any;
  records: any[];
}) {
  const workflow = detail.workflow_context || {};
  const campaignId = String(detail.campaign?.campaign_id || workflow.campaign_id || "");
  const attemptId = String(workflow.current_attempt_id || "original");
  const variantId = String(workflow.target_variant_id || "v01");
  const result =
    detail.attempt_results?.[attemptId]?.[variantId] ||
    detail.latest_results?.[variantId] ||
    {};
  const [governance, setGovernance] = useState<any>({
    candidates: [],
    decisions: [],
  });
  useEffect(() => {
    let cancelled = false;
    Promise.all([api.lifecycleCandidates(), api.deploymentDecisions()])
      .then(([candidates, decisions]) => {
        if (!cancelled) {
          setGovernance({
            candidates: candidates.items || [],
            decisions: decisions.items || [],
          });
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [campaignId, attemptId, variantId]);
  const candidate = governance.candidates.find(
    (item: any) =>
      item.campaign_id === campaignId &&
      item.variant_id === variantId &&
      item.attempt_id === attemptId,
  );
  const forward = records.find(
    (item) => item.variant_id === variantId && item.attempt_id === attemptId,
  );
  const deployment = governance.decisions.find((item: any) => {
    const record = item.decision || item;
    return (record.candidates || []).some(
      (selection: any) => selection.candidate_id === candidate?.candidate_id,
    );
  });
  const scientific = String(
    result.scientific_validity_verdict || result.verdict || "PENDING",
  );
  const generic = String(
    result["research verdict"] || result.research_verdict || result.verdict || "PENDING",
  );
  const accountRequired = scientific === "PASS" && generic === "FAIL";
  const profileScoped = String(candidate?.eligibility_basis || "").includes("account");
  const rows = [
    ["Scientific result", scientific, scientific === "PASS" ? "Final hash-valid evidence passed." : "Complete or resolve the governed result."],
    ["Independent candidate review", candidate ? "COMPLETE" : "LOCKED", candidate ? "A different reviewer approved this exact candidate." : "Available only after an eligible PASS result."],
    ["Named account assessment", accountRequired ? (profileScoped ? "COMPLETE" : "REQUIRED") : "NOT REQUIRED", accountRequired ? "Required because generic objectives did not pass." : "Generic-quality PASS does not require an account-specific rescue route."],
    ["True forward incubation", forward?.status || "LOCKED", forward ? `${forward.calendar_days || 0}/${forward.minimum_calendar_days || 0} days · ${forward.trade_count || 0}/${forward.minimum_trades || 0} trades` : "Starts only after independent candidate approval."],
    ["Portfolio review", "CONDITIONAL", "Required only when two or more candidates will share the deployment allocation."],
    ["Human deployment decision", deployment?.status || deployment?.deployment_state || "LOCKED", deployment ? "The recorded decision remains separate from order routing." : "Unlocks after the required forward and portfolio evidence."],
  ];
  return (
    <Card className="promotion-checklist">
      <div className="card-kicker">
        <div>
          <p className="eyebrow">One promotion checklist</p>
          <h2>Candidate to separate manual deployment</h2>
        </div>
        <span>{variantId} · {humanize(attemptId)}</span>
      </div>
      <div className="promotion-checklist-rows">
        {rows.map(([label, state, explanation], index) => (
          <div key={label}>
            <span className="promotion-step-number">{index + 1}</span>
            <span><strong>{label}</strong><small>{explanation}</small></span>
            <StatusBadge value={state} kind="scientific" />
          </div>
        ))}
      </div>
    </Card>
  );
}

function Lifecycle({ detail }: { detail: any }) {
  const campaign = detail.campaign || {};
  const workflow = detail.workflow_context || {};
  const campaignId = String(campaign.campaign_id || workflow.campaign_id || "");
  const targetVariant = String(workflow.target_variant_id || "v01");
  const targetAttempt = String(workflow.current_attempt_id || "original");
  const [records, setRecords] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [createdBy, setCreatedBy] = useState("");
  const [feedback, setFeedback] = useState("");

  async function refresh() {
    setLoading(true);
    try {
      const value = await api.forwardIncubations(campaignId);
      setRecords(value.items || []);
    } catch (reason) {
      setFeedback(
        reason instanceof Error
          ? reason.message
          : "Forward-incubation records are unavailable",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (campaignId) void refresh();
  }, [campaignId]);

  async function start() {
    if (!createdBy.trim()) {
      setFeedback("Enter the researcher responsible for the forward incubation.");
      return;
    }
    setBusy(true);
    setFeedback("");
    try {
      await api.startForwardIncubation({
        campaign_id: campaignId,
        variant_id: targetVariant,
        attempt_id: targetAttempt,
        created_by: createdBy.trim(),
      });
      await refresh();
      setFeedback(
        "Forward incubation started from the current hash-verified candidate. Historical testing remains frozen.",
      );
    } catch (reason) {
      setFeedback(
        reason instanceof Error
          ? reason.message
          : "Forward incubation could not be started",
      );
    } finally {
      setBusy(false);
    }
  }

  const currentExists = records.some(
    (item) =>
      item.variant_id === targetVariant && item.attempt_id === targetAttempt,
  );
  return (
    <div className="lifecycle-layout">
      <Notice tone="info" title="Historical holdout is not forward incubation">
        This journal begins only after an independently approved candidate is
        frozen. It records later paper or shadow observations with durable
        evidence. Reaching the time and trade minimum creates another human
        review task—it never converts the strategy to PASS or sends orders.
      </Notice>
      <PromotionChecklist detail={detail} records={records} />
      <section className="section-heading">
        <div>
          <p className="eyebrow">Post-research candidate lifecycle</p>
          <h2>True forward incubation</h2>
        </div>
      </section>
      {feedback && (
        <Notice
          tone={feedback.includes("started from") ? "success" : "warning"}
        >
          {feedback}
        </Notice>
      )}
      {!currentExists && (
        <Card className="forward-start-card">
          <div>
            <p className="eyebrow">Current exact attempt</p>
            <h3>
              {targetVariant} · {humanize(targetAttempt)}
            </h3>
            <p>
              Start is available only when this attempt has a complete PASS
              result bundle and a current independent approved-candidate review.
            </p>
          </div>
          <Field label="Incubation owner">
            <input
              value={createdBy}
              onChange={(event) => setCreatedBy(event.target.value)}
              placeholder="Researcher name"
            />
          </Field>
          <Button disabled={busy || !campaignId} onClick={() => void start()}>
            {busy ? "Verifying candidate…" : "Start forward incubation"}
          </Button>
        </Card>
      )}
      {loading ? (
        <Card>
          <Skeleton lines={7} />
        </Card>
      ) : records.length === 0 ? (
        <EmptyState
          icon="clock"
          title="No true-forward record yet"
          body="Complete the staged methodology and independent candidate review before starting a paper or shadow incubation."
        />
      ) : (
        <div className="forward-record-list">
          {records.map((record) => (
            <ForwardIncubationCard
              key={`${record.campaign_id}/${record.variant_id}/${record.attempt_id}`}
              record={record}
              onRefresh={refresh}
            />
          ))}
        </div>
      )}
      <PortfolioDeploymentLifecycle campaignId={campaignId} />
    </div>
  );
}

function ForwardIncubationCard({
  record,
  onRefresh,
}: {
  record: any;
  onRefresh: () => Promise<void>;
}) {
  const [mode, setMode] = useState<"observation" | "review" | "retire" | "">("");
  const [actor, setActor] = useState("");
  const [notes, setNotes] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploadReceipt, setUploadReceipt] = useState<any>(null);
  const [reconciliationConfirmed, setReconciliationConfirmed] = useState(false);
  const [trades, setTrades] = useState(0);
  const [netPnl, setNetPnl] = useState(0);
  const [propRuleBreach, setPropRuleBreach] = useState(false);
  const [flattenViolation, setFlattenViolation] = useState(false);
  const [triggeredRules, setTriggeredRules] = useState<string[]>([]);
  const [reviewDecision, setReviewDecision] = useState("continue");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const terminal = ["FAILED", "RETIRED"].includes(String(record.status));
  const thresholds = record.plan?.thresholds || {};
  const daysProgress = Math.min(
    100,
    (Number(record.calendar_days || 0) /
      Math.max(Number(record.minimum_calendar_days || 1), 1)) *
      100,
  );
  const tradesProgress = Math.min(
    100,
    (Number(record.trade_count || 0) /
      Math.max(Number(record.minimum_trades || 1), 1)) *
      100,
  );

  function reset() {
    setMode("");
    setNotes("");
    setFile(null);
    setUploadReceipt(null);
    setReconciliationConfirmed(false);
    setTrades(0);
    setNetPnl(0);
    setPropRuleBreach(false);
    setFlattenViolation(false);
    setTriggeredRules([]);
    setReviewDecision("continue");
  }

  async function upload(): Promise<string> {
    if (!file) throw new Error("Attach the paper/shadow evidence used for this record.");
    if (uploadReceipt?.filename === file.name && uploadReceipt?.upload_token) {
      return uploadReceipt.upload_token;
    }
    return (await api.uploadForwardIncubationEvidence(file)).upload_token;
  }

  async function inspectEvidence(nextFile: File | null) {
    setFile(nextFile);
    setUploadReceipt(null);
    setReconciliationConfirmed(false);
    if (!nextFile) return;
    setBusy(true);
    setFeedback("");
    try {
      const receipt = await api.uploadForwardIncubationEvidence(nextFile);
      setUploadReceipt(receipt);
      const reconciliation = receipt.reconciliation;
      if (reconciliation?.usable) {
        setTrades(Number(reconciliation.trade_count_delta));
        setNetPnl(Number(reconciliation.net_pnl_delta));
        if (reconciliation.prop_rule_breach !== null) {
          setPropRuleBreach(Boolean(reconciliation.prop_rule_breach));
        }
        if (reconciliation.forced_flatten_violation !== null) {
          setFlattenViolation(Boolean(reconciliation.forced_flatten_violation));
        }
      }
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "Evidence could not be inspected");
    } finally {
      setBusy(false);
    }
  }

  async function submitObservation() {
    if (!actor.trim() || !notes.trim()) {
      setFeedback("Researcher identity and observation notes are required.");
      return;
    }
    if (file?.name.toLowerCase().endsWith(".csv")) {
      if (!uploadReceipt?.reconciliation?.usable) {
        setFeedback("Resolve the CSV reconciliation blockers before recording this observation.");
        return;
      }
      if (!reconciliationConfirmed) {
        setFeedback("Confirm the CSV-derived trade count, P&L, and breach interpretation.");
        return;
      }
    }
    setBusy(true);
    setFeedback("");
    try {
      const uploadToken = await upload();
      await api.appendForwardObservation(
        record.campaign_id,
        record.variant_id,
        record.attempt_id,
        {
          recorded_by: actor.trim(),
          notes: notes.trim(),
          upload_token: uploadToken,
          trade_count_delta: trades,
          net_pnl_delta: netPnl,
          prop_rule_breach: propRuleBreach,
          forced_flatten_violation: flattenViolation,
          triggered_abandonment_rules: triggeredRules,
        },
      );
      await onRefresh();
      reset();
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "Observation was rejected");
    } finally {
      setBusy(false);
    }
  }

  async function submitReview() {
    if (!actor.trim() || !notes.trim()) {
      setFeedback("Reviewer identity and review notes are required.");
      return;
    }
    setBusy(true);
    setFeedback("");
    try {
      const uploadToken = await upload();
      await api.reviewForwardIncubation(
        record.campaign_id,
        record.variant_id,
        record.attempt_id,
        {
          reviewer: actor.trim(),
          notes: notes.trim(),
          upload_token: uploadToken,
          decision: reviewDecision,
        },
      );
      await onRefresh();
      reset();
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "Review was rejected");
    } finally {
      setBusy(false);
    }
  }

  async function retire() {
    if (!actor.trim() || !notes.trim()) {
      setFeedback("Retiring a candidate requires an identity and reason.");
      return;
    }
    setBusy(true);
    setFeedback("");
    try {
      await api.retireForwardIncubation(
        record.campaign_id,
        record.variant_id,
        record.attempt_id,
        { retired_by: actor.trim(), reason: notes.trim() },
      );
      await onRefresh();
      reset();
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "Retirement was rejected");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="forward-record-card">
      <div className="card-kicker">
        <div>
          <p className="eyebrow">Immutable forward record</p>
          <h3>
            {record.variant_id} · {humanize(record.attempt_id)}
          </h3>
        </div>
        <StatusBadge value={record.status} kind="scientific" />
      </div>
      {record.errors?.length > 0 && (
        <Notice tone="danger" title="Forward evidence failed integrity checks">
          {record.errors.join(" · ")}
        </Notice>
      )}
      {record.status === "ELIGIBLE_FOR_REVIEW" && (
        <Notice tone="warning" title="Thresholds met—not approved for deployment">
          A human may now review the full forward journal. Eligibility is not a
          scientific PASS, deployment approval, or authorization to route orders.
        </Notice>
      )}
      <section className="metric-grid campaign-metrics">
        <Metric
          label="Elapsed calendar days"
          value={`${record.calendar_days} / ${record.minimum_calendar_days}`}
          detail={`${daysProgress.toFixed(0)}% of the frozen minimum`}
        />
        <Metric
          label="Forward trades"
          value={`${record.trade_count} / ${record.minimum_trades}`}
          detail={`${tradesProgress.toFixed(0)}% of the frozen minimum`}
        />
        <Metric
          label="Recorded net P&L"
          value={displayMetric(record.net_pnl)}
          detail="Observation journal total; not historical OOS"
        />
        <Metric
          label="Evidence events"
          value={record.event_count || 0}
          detail="Append-only and hash chained"
        />
      </section>
      {!terminal && !record.errors?.length && (
        <div className="forward-actions">
          <Button
            variant="secondary"
            onClick={() => setMode(mode === "observation" ? "" : "observation")}
          >
            Record observation
          </Button>
          <Button
            variant="secondary"
            onClick={() => setMode(mode === "review" ? "" : "review")}
          >
            Record human review
          </Button>
          <Button
            variant="danger"
            onClick={() => setMode(mode === "retire" ? "" : "retire")}
          >
            Retire candidate
          </Button>
        </div>
      )}
      {feedback && <Notice tone="warning">{feedback}</Notice>}
      {mode && (
        <div className="governed-patch forward-event-form">
          <div className="form-grid two">
            <Field label={mode === "review" ? "Reviewer identity" : "Researcher identity"}>
              <input value={actor} onChange={(event) => setActor(event.target.value)} />
            </Field>
            {mode !== "retire" && (
              <Field
                label="Evidence attachment"
                hint="CSV, JSON, Markdown, Parquet, PDF, image, or text. Studio copies it into content-addressed local storage."
              >
                <input
                  type="file"
                  accept=".csv,.json,.md,.parquet,.pdf,.png,.jpg,.jpeg,.txt"
                  onChange={(event) => void inspectEvidence(event.target.files?.[0] || null)}
                />
              </Field>
            )}
          </div>
          {uploadReceipt?.reconciliation && mode === "observation" && (
            <Card className="forward-reconciliation-preview">
              <div className="card-kicker">
                <div>
                  <p className="eyebrow">Calculated from attached CSV</p>
                  <h3>Forward-journal reconciliation</h3>
                </div>
                <StatusBadge
                  value={uploadReceipt.reconciliation.usable ? "READY FOR CONFIRMATION" : "BLOCKED"}
                  kind="scientific"
                />
              </div>
              <dl className="compact-dl">
                <div><dt>Trade rows</dt><dd>{uploadReceipt.reconciliation.trade_count_delta ?? "Unresolved"}</dd></div>
                <div><dt>Net P&L</dt><dd>{displayMetric(uploadReceipt.reconciliation.net_pnl_delta)}</dd></div>
                <div><dt>Prop-rule breach</dt><dd>{uploadReceipt.reconciliation.prop_rule_breach === null ? "Confirm manually" : uploadReceipt.reconciliation.prop_rule_breach ? "Yes" : "No"}</dd></div>
                <div><dt>Forced-flatten violation</dt><dd>{uploadReceipt.reconciliation.forced_flatten_violation === null ? "Confirm manually" : uploadReceipt.reconciliation.forced_flatten_violation ? "Yes" : "No"}</dd></div>
              </dl>
              {uploadReceipt.reconciliation.blockers?.length > 0 && (
                <Notice tone="danger" title="Reconciliation blocked">
                  {uploadReceipt.reconciliation.blockers.join(" · ")}
                </Notice>
              )}
              {uploadReceipt.reconciliation.warnings?.length > 0 && (
                <Notice tone="warning" title="Human confirmation still required">
                  {uploadReceipt.reconciliation.warnings.join(" · ")}
                </Notice>
              )}
              {uploadReceipt.reconciliation.usable && (
                <label className="confirmation compact">
                  <input
                    type="checkbox"
                    checked={reconciliationConfirmed}
                    onChange={(event) => setReconciliationConfirmed(event.target.checked)}
                  />
                  <span><Icon name="check" /></span>
                  <div>
                    <strong>I confirm this deterministic reconciliation</strong>
                    <small>The CSV is not appended until I confirm the calculated totals and any manually reviewed flags.</small>
                  </div>
                </label>
              )}
            </Card>
          )}
          <Field label={mode === "retire" ? "Retirement reason" : "Evidence notes"}>
            <textarea
              rows={3}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </Field>
          {mode === "observation" && (
            <>
              <div className="form-grid two">
                <Field label="New trades in this attachment">
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={trades}
                    disabled={Boolean(uploadReceipt?.reconciliation?.usable)}
                    onChange={(event) => setTrades(Number(event.target.value))}
                  />
                </Field>
                <Field label="Net P&L in this attachment">
                  <input
                    type="number"
                    step="any"
                    value={netPnl}
                    disabled={Boolean(uploadReceipt?.reconciliation?.usable)}
                    onChange={(event) => setNetPnl(Number(event.target.value))}
                  />
                </Field>
              </div>
              <label className="confirmation compact">
                <input
                  type="checkbox"
                  checked={propRuleBreach}
                  onChange={(event) => setPropRuleBreach(event.target.checked)}
                />
                <span>!</span>
                <div>
                  <strong>A prop-rule breach occurred</strong>
                  <small>This immediately makes the incubation a scientific failure.</small>
                </div>
              </label>
              <label className="confirmation compact">
                <input
                  type="checkbox"
                  checked={flattenViolation}
                  onChange={(event) => setFlattenViolation(event.target.checked)}
                />
                <span>!</span>
                <div>
                  <strong>A forced-flatten violation occurred</strong>
                  <small>This immediately makes the incubation a scientific failure.</small>
                </div>
              </label>
              {(thresholds.abandonment_rules || []).length > 0 && (
                <fieldset className="forward-rule-list">
                  <legend>Triggered predeclared abandonment rules</legend>
                  {(thresholds.abandonment_rules || []).map((rule: string) => (
                    <label key={rule}>
                      <input
                        type="checkbox"
                        checked={triggeredRules.includes(rule)}
                        onChange={(event) =>
                          setTriggeredRules((current) =>
                            event.target.checked
                              ? [...current, rule]
                              : current.filter((item) => item !== rule),
                          )
                        }
                      />
                      <span>{rule}</span>
                    </label>
                  ))}
                </fieldset>
              )}
            </>
          )}
          {mode === "review" && (
            <Field label="Review decision">
              <select
                value={reviewDecision}
                onChange={(event) => setReviewDecision(event.target.value)}
              >
                <option value="continue">Continue incubation</option>
                <option value="fail">Fail candidate</option>
                <option value="needs_manual_review">Needs manual review</option>
              </select>
            </Field>
          )}
          <div className="forward-actions">
            <Button
              disabled={busy}
              variant={mode === "retire" ? "danger" : "primary"}
              onClick={() =>
                void (mode === "observation"
                  ? submitObservation()
                  : mode === "review"
                    ? submitReview()
                    : retire())
              }
            >
              {busy ? "Verifying and recording…" : `Record ${mode}`}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={reset}>
              Cancel
            </Button>
          </div>
        </div>
      )}
      <TechnicalDetails>
        <pre>{JSON.stringify(record, null, 2)}</pre>
      </TechnicalDetails>
    </Card>
  );
}

function PortfolioDeploymentLifecycle({ campaignId }: { campaignId: string }) {
  const { data: studioData } = useStudio();
  const [candidates, setCandidates] = useState<any[]>([]);
  const [reviews, setReviews] = useState<any[]>([]);
  const [decisions, setDecisions] = useState<any[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [minimumCommonSessions, setMinimumCommonSessions] = useState(20);
  const [portfolioReviewId, setPortfolioReviewId] = useState("");
  const [requestedContracts, setRequestedContracts] = useState<Record<string, number>>({});
  const [accountLabel, setAccountLabel] = useState("Manual deployment review");
  const [maximumTotalContracts, setMaximumTotalContracts] = useState(3);
  const [maximumContractsPerCandidate, setMaximumContractsPerCandidate] = useState(1);
  const [maximumDailyLoss, setMaximumDailyLoss] = useState(1000);
  const [maximumDrawdown, setMaximumDrawdown] = useState(2500);
  const [reviewer, setReviewer] = useState(
    studioData.settings?.reviewer_identity || "",
  );
  const [decision, setDecision] = useState("NEEDS MANUAL REVIEW");
  const [decisionNotes, setDecisionNotes] = useState("");
  const [rollbackCriteria, setRollbackCriteria] = useState(
    "Pause manual deployment after any monitoring ALERT and investigate before resuming.",
  );
  const [killCriteria, setKillCriteria] = useState(
    "Open a retirement review when a frozen retirement threshold is reached.",
  );
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState("");
  const [loading, setLoading] = useState(true);

  async function refreshGovernance() {
    setLoading(true);
    try {
      const [candidateValue, reviewValue, decisionValue] = await Promise.all([
        api.lifecycleCandidates(),
        api.portfolioReviews(),
        api.deploymentDecisions(),
      ]);
      const candidateRows = candidateValue.items || [];
      setCandidates(candidateRows);
      setReviews(reviewValue.items || []);
      setDecisions(decisionValue.items || []);
      setRequestedContracts((current) => ({
        ...Object.fromEntries(candidateRows.map((item) => [item.candidate_id, 1])),
        ...current,
      }));
    } catch (reason) {
      setFeedback(
        reason instanceof Error
          ? reason.message
          : "Portfolio and deployment governance is unavailable",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshGovernance();
  }, []);

  function toggleCandidate(candidateId: string) {
    setSelected((current) =>
      current.includes(candidateId)
        ? current.filter((item) => item !== candidateId)
        : [...current, candidateId],
    );
  }

  async function createPortfolioReview() {
    if (selected.length < 2) {
      setFeedback("Portfolio review requires at least two approved candidates.");
      return;
    }
    setBusy("portfolio");
    setFeedback("");
    try {
      const value = await api.createPortfolioReview({
        candidate_ids: selected,
        minimum_common_sessions: minimumCommonSessions,
      });
      await refreshGovernance();
      setPortfolioReviewId(value.review_id || value.review?.review_id || "");
      setFeedback("A hash-bound portfolio review was created for human inspection.");
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "Portfolio review was rejected");
    } finally {
      setBusy("");
    }
  }

  async function createDeploymentDecision() {
    if (!selected.length || !reviewer.trim() || !decisionNotes.trim()) {
      setFeedback(
        "Select candidates and enter the human reviewer plus substantive decision notes.",
      );
      return;
    }
    const chosen = candidates.filter((item) => selected.includes(item.candidate_id));
    const instrumentLimits = Object.fromEntries(
      [...new Set(chosen.map((item) => String(item.instrument || "")))].filter(Boolean).map(
        (instrument) => [instrument, maximumContractsPerCandidate],
      ),
    );
    setBusy("deployment");
    setFeedback("");
    try {
      await api.createDeploymentDecision({
        candidates: chosen.map((item) => ({
          candidate_id: item.candidate_id,
          attempt_id: item.attempt_id,
          requested_contracts: requestedContracts[item.candidate_id] || 1,
        })),
        portfolio_review_id: chosen.length > 1 ? portfolioReviewId || null : null,
        account_limits: {
          account_label: accountLabel,
          maximum_total_contracts: maximumTotalContracts,
          maximum_contracts_per_candidate: maximumContractsPerCandidate,
          instrument_contract_limits: instrumentLimits,
          maximum_daily_loss_currency: maximumDailyLoss,
          maximum_total_drawdown_currency: maximumDrawdown,
        },
        rollback_criteria: nonblankLines(rollbackCriteria),
        kill_criteria: nonblankLines(killCriteria),
        monitoring_thresholds: {
          daily_loss_alert_currency: Math.min(maximumDailyLoss, maximumDailyLoss * 0.8),
          drawdown_alert_currency: Math.min(maximumDrawdown, maximumDrawdown * 0.7),
          retirement_review_drawdown_currency: Math.min(
            maximumDrawdown,
            maximumDrawdown * 0.95,
          ),
          losing_streak_alert: 3,
          retirement_review_losing_streak: 5,
          rolling_window_trades: 20,
          minimum_rolling_expectancy_currency: 0,
          maximum_average_slippage_per_contract: 25,
        },
        reviewer: reviewer.trim(),
        decision,
        decision_notes: decisionNotes.trim(),
      });
      await refreshGovernance();
      setFeedback(
        "The human deployment decision was recorded. Studio has not submitted an order or changed an allocation.",
      );
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "Deployment decision was rejected");
    } finally {
      setBusy("");
    }
  }

  const relevantCandidates = candidates.filter(
    (item) => item.campaign_id === campaignId || selected.includes(item.candidate_id),
  );
  return (
    <section className="portfolio-lifecycle">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Diversification and controlled promotion</p>
          <h2>Portfolio and deployment review</h2>
        </div>
      </div>
      <Notice tone="warning" title="A decision record is not an execution bridge">
        Portfolio analysis uses only current acceptance-OOS evidence. Deployment
        approval requires completed forward incubation and remains a human
        authorization for a separate manual process. This service cannot submit
        orders, change allocations, or retire a strategy automatically.
      </Notice>
      {feedback && (
        <Notice
          tone={feedback.includes("created") || feedback.includes("recorded") ? "success" : "warning"}
        >
          {feedback}
        </Notice>
      )}
      {loading ? (
        <Card>
          <Skeleton lines={7} />
        </Card>
      ) : candidates.length === 0 ? (
        <EmptyState
          icon="shield"
          title="No approved candidates available"
          body="At least one independently approved, hash-valid candidate is required. Portfolio analysis requires two."
        />
      ) : (
        <>
          <Card className="portfolio-candidate-card">
            <div className="card-kicker">
              <div>
                <p className="eyebrow">Exact candidate evidence</p>
                <h3>Select strategies to compare</h3>
              </div>
              <StatusBadge value={`${selected.length} selected`} />
            </div>
            <div className="portfolio-candidate-list">
              {candidates.map((item) => (
                <label
                  key={item.candidate_id}
                  className={item.campaign_id === campaignId ? "current-campaign" : ""}
                >
                  <input
                    type="checkbox"
                    checked={selected.includes(item.candidate_id)}
                    onChange={() => toggleCandidate(item.candidate_id)}
                  />
                  <span>
                    <strong>
                      {humanize(item.campaign_id)} · {item.variant_id}
                    </strong>
                    <small>
                      {item.instrument} · {humanize(item.attempt_id)} · run {item.run_id}
                    </small>
                  </span>
                  <code>{String(item.result_bundle_sha256 || "").slice(0, 12)}</code>
                </label>
              ))}
            </div>
            <div className="forward-actions">
              <Field label="Minimum common OOS sessions">
                <input
                  type="number"
                  min="2"
                  step="1"
                  value={minimumCommonSessions}
                  onChange={(event) => setMinimumCommonSessions(Number(event.target.value))}
                />
              </Field>
              <Button
                disabled={busy === "portfolio" || selected.length < 2}
                onClick={() => void createPortfolioReview()}
              >
                {busy === "portfolio" ? "Analyzing exact OOS logs…" : "Create portfolio review"}
              </Button>
            </div>
          </Card>
          {reviews.length > 0 && (
            <Card>
              <div className="card-kicker">
                <h3>Immutable portfolio reviews</h3>
                <StatusBadge value={`${reviews.length} reviews`} />
              </div>
              <div className="governance-record-list">
                {reviews.map((item) => {
                  const review = item.review || item;
                  const analysis = review.analysis || item.analysis || {};
                  return (
                    <label key={review.review_id || item.review_id}>
                      <input
                        type="radio"
                        name="portfolio-review"
                        checked={portfolioReviewId === (review.review_id || item.review_id)}
                        onChange={() => setPortfolioReviewId(review.review_id || item.review_id)}
                      />
                      <span>
                        <strong>{review.candidates?.length || item.candidate_count || 0} candidates</strong>
                        <small>
                          {analysis.common_session_count || "—"} common sessions · max |correlation| {displayMetric(analysis.maximum_pairwise_absolute_pnl_correlation)} · combined drawdown {displayMetric(analysis.combined_max_drawdown)}
                        </small>
                      </span>
                      <StatusBadge value={item.status || review.status || "NEEDS MANUAL REVIEW"} />
                    </label>
                  );
                })}
              </div>
            </Card>
          )}
          <details className="advanced-settings deployment-decision-form">
            <summary>Record a human deployment decision</summary>
            <Card>
              <Notice tone="info">
                An APPROVE decision will be rejected unless every selected
                candidate has a current `ELIGIBLE_FOR_REVIEW` forward journal,
                the requested allocation is within limits, and a multi-strategy
                selection binds the exact portfolio review above.
              </Notice>
              <div className="form-grid two">
                <Field label="Account / evaluation label">
                  <input value={accountLabel} onChange={(event) => setAccountLabel(event.target.value)} />
                </Field>
                <Field label="Human reviewer">
                  <input value={reviewer} onChange={(event) => setReviewer(event.target.value)} />
                </Field>
                <Field label="Maximum total contracts">
                  <input type="number" min="1" step="1" value={maximumTotalContracts} onChange={(event) => setMaximumTotalContracts(Number(event.target.value))} />
                </Field>
                <Field label="Maximum contracts per candidate">
                  <input type="number" min="1" step="1" value={maximumContractsPerCandidate} onChange={(event) => setMaximumContractsPerCandidate(Number(event.target.value))} />
                </Field>
                <Field label="Maximum daily loss" hint="Currency units from the governing account rules.">
                  <input type="number" min="1" step="any" value={maximumDailyLoss} onChange={(event) => setMaximumDailyLoss(Number(event.target.value))} />
                </Field>
                <Field label="Maximum total drawdown">
                  <input type="number" min="1" step="any" value={maximumDrawdown} onChange={(event) => setMaximumDrawdown(Number(event.target.value))} />
                </Field>
              </div>
              {relevantCandidates.filter((item) => selected.includes(item.candidate_id)).map((item) => (
                <Field key={item.candidate_id} label={`${humanize(item.campaign_id)} · ${item.variant_id} requested contracts`}>
                  <input
                    type="number"
                    min="1"
                    step="1"
                    value={requestedContracts[item.candidate_id] || 1}
                    onChange={(event) =>
                      setRequestedContracts((current) => ({
                        ...current,
                        [item.candidate_id]: Number(event.target.value),
                      }))
                    }
                  />
                </Field>
              ))}
              <Field label="Rollback criteria" hint="One frozen rule per line.">
                <textarea rows={3} value={rollbackCriteria} onChange={(event) => setRollbackCriteria(event.target.value)} />
              </Field>
              <Field label="Kill / retirement-review criteria" hint="One frozen rule per line.">
                <textarea rows={3} value={killCriteria} onChange={(event) => setKillCriteria(event.target.value)} />
              </Field>
              <Field label="Decision">
                <select value={decision} onChange={(event) => setDecision(event.target.value)}>
                  <option value="NEEDS MANUAL REVIEW">Needs manual review</option>
                  <option value="REJECT">Reject</option>
                  <option value="APPROVE">Approve for separate manual deployment</option>
                </select>
              </Field>
              <Field label="Decision notes">
                <textarea rows={4} value={decisionNotes} onChange={(event) => setDecisionNotes(event.target.value)} />
              </Field>
              <Button disabled={busy === "deployment"} onClick={() => void createDeploymentDecision()}>
                {busy === "deployment" ? "Revalidating lifecycle evidence…" : "Record deployment decision"}
              </Button>
            </Card>
          </details>
        </>
      )}
      {decisions.length > 0 && (
        <div className="deployment-record-list">
          {decisions.map((item) => (
            <DeploymentDecisionCard
              key={item.decision_id || item.decision?.decision_id}
              summary={item}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function DeploymentDecisionCard({ summary }: { summary: any }) {
  const decision = summary.decision || summary;
  const decisionId = String(decision.decision_id || summary.decision_id || "");
  const [monitoring, setMonitoring] = useState<any>(null);
  const [file, setFile] = useState<File | null>(null);
  const [recordedBy, setRecordedBy] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  const approved =
    (decision.deployment_state || summary.status) === "APPROVED_FOR_MANUAL_DEPLOYMENT";

  async function refresh() {
    if (!decisionId || !approved) return;
    try {
      setMonitoring(await api.deploymentMonitoring(decisionId));
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "Monitoring evidence is unavailable");
    }
  }

  useEffect(() => {
    void refresh();
  }, [decisionId, approved]);

  async function append() {
    if (!file || !recordedBy.trim() || !notes.trim()) {
      setFeedback("Attach a monitoring trade CSV and enter the recorder plus notes.");
      return;
    }
    setBusy(true);
    setFeedback("");
    try {
      const upload = await api.uploadDeploymentMonitoringEvidence(file);
      setMonitoring(
        await api.appendDeploymentMonitoring(decisionId, {
          upload_token: upload.upload_token,
          recorded_by: recordedBy.trim(),
          notes: notes.trim(),
        }),
      );
      setFile(null);
      setNotes("");
    } catch (reason) {
      setFeedback(reason instanceof Error ? reason.message : "Monitoring record was rejected");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="deployment-record-card">
      <div className="card-kicker">
        <div>
          <p className="eyebrow">Human deployment decision</p>
          <h3>{decision.account_limits?.account_label || "Governed allocation"}</h3>
        </div>
        <StatusBadge
          value={decision.deployment_state || summary.status || "NEEDS MANUAL REVIEW"}
          kind="scientific"
        />
      </div>
      <p>{decision.decision_notes || summary.decision_notes}</p>
      <small>
        {decision.candidates?.length || summary.candidate_count || 0} candidates ·
        execution capability: none · order submission permitted: false
      </small>
      {monitoring && (
        <Notice
          tone={monitoring.status === "HEALTHY" ? "success" : "warning"}
          title={`Monitoring: ${humanize(monitoring.status)}`}
        >
          {monitoring.event_count || 0} immutable periods. Alerts: {monitoring.triggered_alerts?.join(" · ") || "none"}.
        </Notice>
      )}
      {feedback && <Notice tone="warning">{feedback}</Notice>}
      {approved && (
        <div className="governed-patch forward-event-form">
          <div className="form-grid two">
            <Field
              label="New live/paper trade CSV"
              hint="Required columns are checked server-side; the file is copied into governed content-addressed storage."
            >
              <input type="file" accept=".csv" onChange={(event) => setFile(event.target.files?.[0] || null)} />
            </Field>
            <Field label="Recorder identity">
              <input value={recordedBy} onChange={(event) => setRecordedBy(event.target.value)} />
            </Field>
          </div>
          <Field label="Monitoring notes">
            <textarea rows={3} value={notes} onChange={(event) => setNotes(event.target.value)} />
          </Field>
          <Button disabled={busy} onClick={() => void append()}>
            {busy ? "Hashing and evaluating…" : "Append monitoring period"}
          </Button>
        </div>
      )}
      <TechnicalDetails>
        <pre>{JSON.stringify({ decision: summary, monitoring }, null, 2)}</pre>
      </TechnicalDetails>
    </Card>
  );
}

function nonblankLines(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function History({
  detail,
  onRefresh,
}: {
  detail: any;
  onRefresh: () => Promise<any>;
}) {
  const { data: studioData } = useStudio();
  const summaryAttempts = detail.attempts || [];
  const [attempts, setAttempts] = useState<any[]>(summaryAttempts);
  const [attemptsLoading, setAttemptsLoading] = useState(true);
  const [attemptsError, setAttemptsError] = useState("");
  const [attemptDetails, setAttemptDetails] = useState<Record<string, any>>({});
  const [loadingAttemptIds, setLoadingAttemptIds] = useState<Set<string>>(
    new Set(),
  );
  const campaign = detail.campaign || {};
  const currentAttemptId =
    detail.workflow_context?.current_attempt_id ||
    attempts.at(-1)?.attempt_id ||
    "";
  const latestAttemptId =
    detail.workflow_context?.latest_attempt_id ||
    attempts.at(-1)?.attempt_id ||
    "";
  const [expandedAttempts, setExpandedAttempts] = useState<Set<string>>(
    () => new Set(),
  );
  const workflowStage = String(detail.workflow_context?.stage || "");
  const mechanicsWorkflowActive = [
    "mechanics_evidence",
    "mechanics_review",
  ].includes(workflowStage);
  const recommendedParent =
    currentAttemptId || recommendedParentAttempt(attempts);
  const [creating, setCreating] = useState(false);
  const [options, setOptions] = useState<any>(null);
  const [optionsState, setOptionsState] = useState<
    "idle" | "loading" | "ready" | "failed"
  >("idle");
  const [optionsError, setOptionsError] = useState("");
  const [optionsRetry, setOptionsRetry] = useState(0);
  const [parent, setParent] = useState(recommendedParent);
  const [kind, setKind] = useState("replication");
  const [reason, setReason] = useState("");
  const [createdBy, setCreatedBy] = useState(
    studioData.settings?.reviewer_identity || "",
  );
  const [datasetId, setDatasetId] = useState("");
  const [targetVariant, setTargetVariant] = useState("v01");
  const [parameterKey, setParameterKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [refreshCertification, setRefreshCertification] = useState(false);
  const [eventGridValues, setEventGridValues] = useState<Record<string, string>>({});
  const [authorizedBy, setAuthorizedBy] = useState("");
  const [mechanicsStartDate, setMechanicsStartDate] = useState("");
  const [mechanicsEndDate, setMechanicsEndDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState("");
  useEffect(() => {
    if (!campaign.campaign_id) return;
    setAttemptsLoading(true);
    api
      .campaignAttempts(campaign.campaign_id)
      .then((value) => {
        if (value.attempts?.length) setAttempts(value.attempts);
        setAttemptsError(
          (value.partial_errors || [])
            .map((item: any) => item.message)
            .join(" · "),
        );
      })
      .catch((reason) =>
        setAttemptsError(
          reason instanceof Error
            ? reason.message
            : "Detailed attempt lineage is unavailable",
        ),
      )
      .finally(() => setAttemptsLoading(false));
  }, [campaign.campaign_id]);
  async function loadAttemptDetail(attemptId: string) {
    if (
      !campaign.campaign_id ||
      attemptDetails[attemptId] ||
      loadingAttemptIds.has(attemptId)
    )
      return;
    setLoadingAttemptIds((current) => new Set(current).add(attemptId));
    try {
      const value = await api.campaignAttempt(
        campaign.campaign_id,
        attemptId,
      );
      setAttemptDetails((current) => ({
        ...current,
        [attemptId]: value.attempt,
      }));
    } catch (reason) {
      setAttemptsError(
        reason instanceof Error
          ? reason.message
          : "Attempt dataset lineage is unavailable",
      );
    } finally {
      setLoadingAttemptIds((current) => {
        const next = new Set(current);
        next.delete(attemptId);
        return next;
      });
    }
  }
  function toggleAttempt(attemptId: string) {
    const expanding = !expandedAttempts.has(attemptId);
    setExpandedAttempts((current) => {
      const next = new Set(current);
      if (next.has(attemptId)) next.delete(attemptId);
      else next.add(attemptId);
      return next;
    });
    if (expanding) void loadAttemptDetail(attemptId);
  }

  useEffect(() => {
    if (!creating || !campaign.campaign_id) return;
    let active = true;
    setOptions(null);
    setOptionsError("");
    setOptionsState("loading");
    api
      .followUpOptions(campaign.campaign_id, parent)
      .then((value) => {
        if (!active) return;
        setOptions(value);
        setOptionsState("ready");
        const currentKind = (value.attempt_kinds || []).find(
          (item: any) => item.value === kind,
        );
        if (currentKind && currentKind.available === false) {
          setKind(
            (value.attempt_kinds || []).find(
              (item: any) => item.available !== false,
            )?.value || "replication",
          );
        }
        if (value.datasets?.[0]?.dataset_id)
          setDatasetId((current) => current || value.datasets[0].dataset_id);
        const variants = Object.keys(value.parameters || {});
        const selectedVariant = variants.includes(targetVariant)
          ? targetVariant
          : variants[0] || "v01";
        setTargetVariant(selectedVariant);
        const currentWindow =
          value.mechanics_validation_windows?.[selectedVariant] || {};
        setMechanicsStartDate(currentWindow.start_date || "");
        setMechanicsEndDate(currentWindow.end_date || "");
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
      .catch((error) => {
        if (!active) return;
        setOptionsError(
          error instanceof Error
            ? error.message
            : "Follow-up choices unavailable",
        );
        setOptionsState("failed");
      });
    return () => {
      active = false;
    };
  }, [creating, campaign.campaign_id, parent, optionsRetry]);

  const parameters = options?.parameters?.[targetVariant] || [];
  const selectedParameter = parameters.find(
    (item: any) => `${item.component}|${item.parameter_path}` === parameterKey,
  );
  const eventDeclarations =
    options?.event_parameter_declarations?.[targetVariant] || [];
  const attemptKinds = options?.attempt_kinds || [];
  const selectedKind = attemptKinds.find((item: any) => item.value === kind);
  const parentChoices = options?.parent_attempts || attempts;
  const selectedParent =
    parentChoices.find((item: any) => item.attempt_id === parent) ||
    options?.selected_parent;
  const reasonMinimum = options?.reason_min_length || 80;
  const creationBlockers = [
    ...(!createdBy.trim() ? ["Enter the researcher identity."] : []),
    ...(reason.trim().length < reasonMinimum
      ? [
          `Add ${reasonMinimum - reason.trim().length} more character${
            reasonMinimum - reason.trim().length === 1 ? "" : "s"
          } to the scientific reason.`,
        ]
      : []),
  ];
  function selectVariant(value: string) {
    setTargetVariant(value);
    const currentWindow =
      options?.mechanics_validation_windows?.[value] || {};
    setMechanicsStartDate(currentWindow.start_date || "");
    setMechanicsEndDate(currentWindow.end_date || "");
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
      if (kind === "replication") value.target_variant_id = targetVariant;
      if (kind === "data_refresh") value.dataset_id = datasetId;
      if (kind === "methodology_rerun") {
        value.mechanics_validation_window = {
          variant_id: targetVariant,
          start_date: mechanicsStartDate,
          end_date: mechanicsEndDate,
        };
      }
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
        value.target_variant_id = targetVariant;
        if (
          kind === "pre_pnl_mechanics_correction" &&
          refreshCertification
        ) {
          value.refresh_certification = true;
        } else {
          if (!selectedParameter)
            throw new Error(
              "Select one governed mechanics parameter to change.",
            );
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
      }
      if (kind === "rescue") value.authorized_by = authorizedBy;
      const result = await api.createFollowUp(campaign.campaign_id, value);
      await onRefresh();
      const refreshedAttempts = await api.campaignAttempts(
        campaign.campaign_id,
        true,
      );
      setAttempts(refreshedAttempts.attempts || []);
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
            variant="secondary"
            onClick={() => {
              setCreating((value) => {
                if (!value) {
                  setParent(recommendedParent);
                  setOptionsState("idle");
                  setOptionsError("");
                }
                return !value;
              });
              setFeedback("");
            }}
          >
            {creating ? "Cancel" : "Create explicit follow-up"}
          </Button>
        )}
      </div>
      {mechanicsWorkflowActive && (
        <Notice tone="info" title="Recovery follow-ups remain available">
          Current sequential work does not need a follow-up. The active scope is{" "}
          <code>{currentAttemptId}</code> /{" "}
          <code>{detail.workflow_context?.target_variant_id}</code>. Continue in{" "}
          <Link
            to={`/research/${encodeURIComponent(
              campaign.campaign_id,
            )}/testing?attempt=${encodeURIComponent(
              currentAttemptId,
            )}&variant=${encodeURIComponent(
              detail.workflow_context?.target_variant_id || "",
            )}`}
          >
            Testing
          </Link>{" "}
          for mechanics evidence. Create a follow-up only for an explicit
          replication, data replacement, methodology rerun, eligible pre-PnL
          correction, or authorized rescue.
        </Notice>
      )}
      {feedback && (
        <Notice
          tone={feedback.includes("created as") ? "success" : "warning"}
        >
          {feedback}
        </Notice>
      )}
      {attemptsError && (
        <Notice tone="warning" title="Detailed lineage is partially unavailable">
          {attemptsError}
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
          {optionsState === "loading" ? (
            <Skeleton lines={5} />
          ) : optionsState === "failed" ? (
            <div className="action-stack">
              <Notice tone="warning" title="Follow-up choices could not be loaded">
                {optionsError || "The local service did not return governed follow-up choices."}
              </Notice>
              <div className="inline-actions">
                <Button
                  type="button"
                  onClick={() => setOptionsRetry((value) => value + 1)}
                >
                  Retry
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setCreating(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : optionsState === "ready" && options ? (
            <form onSubmit={submitFollowUp}>
              <Notice tone="info" title="Two choices, two different jobs">
                <strong>Follow-up type</strong> controls what this new attempt is
                allowed to change. <strong>Parent attempt</strong> is the exact
                frozen strategy, data, parameters, and methodology state that
                will be copied. The newest attempt is not always the correct
                parent.
              </Notice>
              <FollowUpDecisionGuide
                kinds={attemptKinds}
                selected={kind}
                onSelect={(value) => {
                  setKind(value);
                  if (value !== "pre_pnl_mechanics_correction")
                    setRefreshCertification(false);
                }}
              />
              <div className="follow-up-parent-section">
                <Field
                  label="Parent attempt"
                  hint={selectedKind?.parent_rule}
                >
                  <select value={parent} onChange={(e) => setParent(e.target.value)}>
                    {parentChoices.map((item: any) => (
                      <option key={item.attempt_id} value={item.attempt_id}>
                        {friendlyAttemptLabel(item)}
                        {item.recommended ? " · Recommended current leaf" : ""}
                        {item.child_count
                          ? ` · ${item.child_count} existing ${
                              item.child_count === 1 ? "child" : "children"
                            }`
                          : ""}
                      </option>
                    ))}
                  </select>
                </Field>
                <ParentAttemptGuide
                  parent={selectedParent}
                  kind={selectedKind}
                />
              </div>
              <Field
                label="Scientific reason"
                hint={`${reason.trim().length}/${reasonMinimum} characters minimum. Explain why this attempt is warranted without tuning to observed PnL.`}
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
              {kind === "replication" && (
                <Notice tone="info" title="Exact replication">
                  This creates a new immutable attempt with unchanged strategy
                  mechanics, data, parameter space, and methodology. For an
                  interrupted run, state that the prior attempt ended
                  operationally and that no observed PnL is being used to
                  change the strategy.
                </Notice>
              )}
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
              {kind === "methodology_rerun" && (
                <div className="governed-patch">
                  <Notice
                    tone="info"
                    title="Fixed mechanics-review methodology"
                  >
                    Every strategy uses the latest 10 eligible sessions from
                    its governed dataset, its declared default parameters, and
                    the same deterministic five-trade review sample. The dates
                    below are calculated by policy and cannot be edited.
                  </Notice>
                  <Field label="Target variant">
                    <select
                      value={targetVariant}
                      onChange={(e) => selectVariant(e.target.value)}
                    >
                      {Object.keys(options.mechanics_validation_windows || {}).map(
                        (value) => <option key={value}>{value}</option>,
                      )}
                    </select>
                  </Field>
                  <dl className="definition-list compact">
                    <div>
                      <dt>Selection rule</dt>
                      <dd>Latest 10 eligible sessions</dd>
                    </div>
                    <div>
                      <dt>Materialized window</dt>
                      <dd>
                        {mechanicsStartDate || "Unavailable"} through{" "}
                        {mechanicsEndDate || "Unavailable"}
                      </dd>
                    </div>
                  </dl>
                </div>
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
                  <Notice
                    tone="warning"
                    title={
                      refreshCertification
                        ? "Publish a recertified implementation"
                        : "One explicit reviewed change"
                    }
                  >
                    {refreshCertification
                      ? "Use this only after source logic was tested and recertified. The new implementation identity is frozen without changing scalar defaults, and fresh mechanics approval remains mandatory."
                      : "The source attempt is never edited. This new attempt records the old and new scalar values and repeats mechanics approval for every currently declared variant."}
                  </Notice>
                  {kind === "pre_pnl_mechanics_correction" && (
                    <label className="confirmation compact">
                      <input
                        type="checkbox"
                        checked={refreshCertification}
                        onChange={(event) =>
                          setRefreshCertification(event.target.checked)
                        }
                      />
                      <span>✓</span>
                      <div>
                        <strong>Publish the current certified implementation</strong>
                        <small>
                          Select this when source logic changed but reviewed fixed
                          parameter values did not.
                        </small>
                      </div>
                    </label>
                  )}
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
                    {!refreshCertification && (
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
                    )}
                  </div>
                  {!refreshCertification && (
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
                  )}
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
                {creationBlockers.length > 0 && (
                  <Notice tone="warning" title="Complete required fields">
                    {creationBlockers.join(" ")}
                  </Notice>
                )}
                <Button
                  type="submit"
                  disabled={busy || creationBlockers.length > 0}
                >
                  {busy ? "Running preflight…" : "Preflight and create attempt"}
                </Button>
              </div>
            </form>
          ) : null}
        </Card>
      )}
      {attemptsLoading ? (
        <Card>
          <Skeleton lines={6} />
        </Card>
      ) : attempts.length === 0 ? (
        <EmptyState
          icon="clock"
          title="Only the original protocol exists"
          body="Use Create explicit follow-up for a governed replication, data refresh, methodology rerun, correction, or authorized rescue."
        />
      ) : (
        <div className="timeline">
          {[...attempts].reverse().map((item: any, index: number) => {
            const attemptId = String(item.attempt_id || "original");
            const displayItem = attemptDetails[attemptId] || item;
            const expanded = expandedAttempts.has(attemptId);
            const includedVariantIds = attemptVariantIds(
              item,
              detail.mechanics_approval,
            );
            const targetVariant =
              attemptId === "original"
                ? item.target_variant_id || includedVariantIds.at(-1)
                : item.target_variant_id || includedVariantIds.at(-1);
            const parentAttempt = attempts.find(
              (candidate: any) =>
                candidate.attempt_id === item.parent_attempt_id,
            );
            return (
            <Card key={item.attempt_id || index}>
              <span className="timeline-marker">
                {attempts.length - index}
              </span>
              <div>
                <button
                  className="attempt-summary"
                  aria-expanded={expanded}
                  onClick={() => toggleAttempt(attemptId)}
                >
                  <span>
                    <small>
                      Attempt {attempts.length - index}
                      {targetVariant ? ` · ${targetVariant}` : ""}
                    </small>
                    <strong>{friendlyAttemptLabel(item)}</strong>
                  </span>
                  <span className="attempt-summary-badges">
                    {attemptId === currentAttemptId && (
                      <StatusBadge value="Active work" />
                    )}
                    {attemptId === latestAttemptId &&
                      attemptId !== currentAttemptId && (
                        <StatusBadge value="Latest historical attempt" />
                    )}
                    <StatusBadge value={item.attempt_kind || "Original"} />
                    <Icon name="chevron" />
                  </span>
                </button>
                {expanded && (
                  <div className="attempt-expanded">
                <p>
                  {item.reason ||
                    "Original frozen protocol and evidence identity."}
                </p>
                <dl className="compact-dl attempt-identity">
                  <div>
                    <dt>Exact attempt ID</dt>
                    <dd><code>{attemptId}</code></dd>
                  </div>
                  <div>
                    <dt>Parent</dt>
                    <dd>
                      {parentAttempt
                        ? friendlyAttemptLabel(parentAttempt)
                        : item.parent_attempt_id || "None"}
                    </dd>
                  </div>
                  <div>
                    <dt>Created</dt>
                    <dd>{formatDate(item.created_at)}</dd>
                  </div>
                </dl>
                {loadingAttemptIds.has(attemptId) && (
                  <div className="attempt-lineage-loading">
                    <Skeleton lines={3} />
                  </div>
                )}
                {displayItem.dataset_lineage_error && (
                  <Notice tone="danger" title="Dataset lineage unavailable">
                    {displayItem.dataset_lineage_error}
                  </Notice>
                )}
                {[...(displayItem.dataset_bindings || [])]
                  .sort(
                    (left: any, right: any) =>
                      Number(right.variant_id === targetVariant) -
                      Number(left.variant_id === targetVariant),
                  )
                  .map((binding: any) => (
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
                          {formatMarketDate(binding.coverage_start)} →{" "}
                          {formatMarketDate(binding.coverage_end)}
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
                        <dt>Recorded source hash</dt>
                        <dd>
                          {binding.source_sha256 ? (
                            <code>{binding.source_sha256}</code>
                          ) : (
                            "Not recorded"
                          )}
                        </dd>
                      </div>
                      <div className="hash-row">
                        <dt>Currently verified input-data hash</dt>
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
                )}
              </div>
            </Card>
            );
          })}
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
  return `${start ? formatMarketDate(start) : "Unknown"} → ${
    end ? formatMarketDate(end) : "Unknown"
  }`;
}

export function FollowUpDecisionGuide({
  kinds,
  selected,
  onSelect,
}: {
  kinds: any[];
  selected: string;
  onSelect: (value: string) => void;
}) {
  const active = kinds.find((item: any) => item.value === selected);
  return (
    <div className="follow-up-decision-guide">
      <div
        className="follow-up-kind-grid"
        role="radiogroup"
        aria-label="Follow-up type"
      >
        {kinds.map((item: any) => (
          <button
            key={item.value}
            type="button"
            role="radio"
            aria-checked={item.value === selected}
            className={item.value === selected ? "selected" : ""}
            disabled={item.available === false}
            onClick={() => onSelect(item.value)}
          >
            <strong>{item.label}</strong>
            <span>{item.summary}</span>
            {item.available === false && (
              <small>{item.unavailable_reason || "Unavailable"}</small>
            )}
          </button>
        ))}
      </div>
      {active && (
        <div className="follow-up-kind-explanation" aria-live="polite">
          <p>
            <strong>Use when:</strong> {active.use_when}
          </p>
          <p>
            <strong>Avoid when:</strong> {active.do_not_use_when}
          </p>
          {active.impact_preview && (
            <div className="follow-up-impact-grid">
              {(["changes", "preserves", "invalidates"] as const).map((key) => (
                <div key={key}>
                  <strong>{humanize(key)}</strong>
                  <ul>
                    {(active.impact_preview[key] || []).map((item: string) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ParentAttemptGuide({
  parent,
  kind,
}: {
  parent: any;
  kind: any;
}) {
  if (!parent) return null;
  return (
    <div
      className={`parent-attempt-guide ${
        parent.branch_warning ? "parent-attempt-warning" : ""
      }`}
    >
      <div>
        <p className="eyebrow">Selected frozen source</p>
        <strong>{parent.attempt_id}</strong>
        <span>{parent.lineage_label || humanize(parent.attempt_kind)}</span>
      </div>
      <p>
        {kind?.parent_rule ||
          "The new attempt copies this exact frozen state before applying the selected governed change."}
      </p>
      {parent.reason && <small>Why it exists: {parent.reason}</small>}
      {parent.branch_warning && (
        <Notice tone="warning" title="You are creating a separate branch">
          {parent.branch_warning}
        </Notice>
      )}
    </div>
  );
}

function recommendedParentAttempt(attempts: any[]): string {
  const parents = new Set(
    attempts
      .map((item: any) => item.parent_attempt_id)
      .filter(Boolean),
  );
  return (
    [...attempts]
      .reverse()
      .find((item: any) => !parents.has(item.attempt_id))?.attempt_id ||
    "original"
  );
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
