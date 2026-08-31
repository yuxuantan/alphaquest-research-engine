import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { Icon } from "../components/Icons";
import {
  Button,
  Card,
  Field,
  Notice,
  Skeleton,
  StatusBadge,
  TechnicalDetails,
  humanize,
} from "../components/UI";
import { useStudio } from "../state";
import {
  publicationAvailableStrategyPackages,
  strategyPackageLabel,
} from "../strategyAvailability";
import { OBJECTIVE_TEMPLATES } from "../researchObjectives";
export { OBJECTIVE_TEMPLATES } from "../researchObjectives";
import type {
  DatasetSummary,
  DraftView,
  DuplicateMatch,
  DuplicateReview,
  WizardStep,
} from "../types";

const stepDescriptions = [
  "Goals, claim, source, and prior research",
  "Governed bars",
  "Costs and compliance",
  "Causal implementation",
  "Risk and exit expressions",
  "Preflight and immutable freeze",
];

const VISIBLE_STEP_COUNT = 6;

function visibleStepNumber(sourceStep: number): number {
  return sourceStep <= 2 ? 1 : sourceStep - 1;
}

export function WizardPage() {
  const { campaignId = "", step = "1" } = useParams();
  const stepNumber = Math.max(1, Math.min(7, Number(step) || 1));
  const [view, setView] = useState<DraftView | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [dirty, setDirty] = useState(false);
  const { refresh } = useStudio();
  const navigate = useNavigate();
  useEffect(() => {
    setDirty(false);
  }, [campaignId, stepNumber]);
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  useEffect(() => {
    let restoringCancelledNavigation = false;
    const warn = () => {
      if (!dirty || restoringCancelledNavigation) {
        restoringCancelledNavigation = false;
        return;
      }
      if (
        !window.confirm(
          "You have unsaved changes on this step. Leave without saving them?",
        )
      ) {
        restoringCancelledNavigation = true;
        window.history.go(1);
      }
    };
    window.addEventListener("popstate", warn);
    return () => window.removeEventListener("popstate", warn);
  }, [dirty]);
  useEffect(() => {
    setLoading(true);
    setError("");
    api
      .draft(campaignId)
      .then(setView)
      .catch((reason) =>
        setError(
          reason instanceof Error ? reason.message : "Draft unavailable",
        ),
      )
      .finally(() => setLoading(false));
  }, [campaignId]);
  function completed(result: DraftView, next?: number) {
    setDirty(false);
    setView(result);
    void refresh();
    if (next) navigate(`/research/${campaignId}/design/${next}`);
  }
  function guardNavigation(event: ReactMouseEvent<HTMLDivElement>) {
    if (!dirty) return;
    const target = event.target as HTMLElement;
    const link = target.closest("a");
    if (!link) return;
    if (
      !window.confirm(
        "You have unsaved changes on this step. Leave without saving them?",
      )
    ) {
      event.preventDefault();
      event.stopPropagation();
    }
  }
  if (loading)
    return (
      <div className="page wizard-page">
        <Skeleton lines={8} />
      </div>
    );
  if (!view || error)
    return (
      <div className="page page-narrow">
        <Notice tone="danger" title="Draft unavailable">
          {error || "This draft could not be loaded."}
        </Notice>
        <Link className="button button-secondary" to="/research">
          Return to research
        </Link>
      </div>
    );
  const requested = view.steps.find((item) => item.number === stepNumber);
  if (requested && !requested.available)
    return <LockedStep view={view} step={requested} />;
  return (
    <div
      className="wizard-layout"
      onInput={() => setDirty(true)}
      onChange={() => setDirty(true)}
      onClickCapture={guardNavigation}
    >
      <aside className="wizard-sidebar">
        <Link className="back-link" to="/research">
          ← All research
        </Link>
        <div className="wizard-study">
          <span>{view.draft.instrument || "Futures"}</span>
          <div>
            <strong>{view.draft.title || campaignId}</strong>
            <small>{view.draft.timeframe || "Completed bars"}</small>
          </div>
        </div>
        <nav aria-label="Research design steps">
          <ol>
            {view.steps.filter((item) => item.number !== 2).map((item) => {
              const planReview = view.steps.find((candidate) => candidate.number === 2);
              const combinedPlan = item.number === 1;
              const complete = combinedPlan
                ? Boolean(item.complete && planReview?.complete)
                : item.complete;
              const current = combinedPlan
                ? stepNumber <= 2
                : item.number === stepNumber;
              const target = combinedPlan && item.complete && !planReview?.complete ? 2 : item.number;
              return (
              <li key={item.number}>
                <Link
                  aria-current={current ? "step" : undefined}
                  className={`${current ? "current" : ""} ${complete ? "complete" : ""} ${!item.available ? "locked" : ""}`}
                  to={
                    item.available
                      ? `/research/${campaignId}/design/${target}`
                      : `#step-${item.number}`
                  }
                  onClick={(event) => !item.available && event.preventDefault()}
                >
                  <span className="step-marker">
                    {complete ? (
                      <Icon name="check" />
                    ) : !item.available ? (
                      <Icon name="lock" />
                    ) : (
                      visibleStepNumber(item.number)
                    )}
                  </span>
                  <span>
                    <strong>{combinedPlan ? "Research plan" : item.label}</strong>
                    <small>{stepDescriptions[visibleStepNumber(item.number) - 1]}</small>
                  </span>
                </Link>
              </li>
              );
            })}
          </ol>
        </nav>
        <Notice tone="info">
          <strong>Pre-PnL workspace</strong>
          <br />
          No observed performance is used while you design this protocol.
        </Notice>
        <div
          className={`wizard-save-indicator ${dirty ? "unsaved" : "saved"}`}
          role="status"
        >
          <span />
          {dirty ? "Unsaved changes" : "No unsaved changes"}
        </div>
      </aside>
      <div className="wizard-main">
        <div className="mobile-step-progress">
          <span>Step {visibleStepNumber(stepNumber)} of {VISIBLE_STEP_COUNT}</span>
          <div>
            <i style={{ width: `${(visibleStepNumber(stepNumber) / VISIBLE_STEP_COUNT) * 100}%` }} />
          </div>
        </div>
        <div className="wizard-content">
          {stepNumber === 1 && (
            <BriefStep
              view={view}
              onComplete={(result) => completed(result, 2)}
            />
          )}
          {stepNumber === 2 && (
            <DuplicateStep
              view={view}
              onComplete={(result) =>
                completed(
                  result,
                  result.draft.duplicate_review?.conclusion === "distinct"
                    ? 3
                    : undefined,
                )
              }
            />
          )}
          {stepNumber === 3 && (
            <DatasetStep
              view={view}
              onComplete={(result) => completed(result, 4)}
            />
          )}
          {stepNumber === 4 && (
            <ExecutionStep
              view={view}
              onComplete={(result) => completed(result, 5)}
            />
          )}
          {stepNumber === 5 && (
            <MechanicsStep
              view={view}
              onComplete={(result) =>
                completed(
                  result,
                  result.draft.authoring_lane === "engineering_handoff"
                    ? undefined
                    : 6,
                )
              }
            />
          )}
          {stepNumber === 6 && (
            <VariantsStep
              view={view}
              onComplete={(result) => completed(result, 7)}
            />
          )}
          {stepNumber === 7 && (
            <ProtocolStep
              view={view}
              onComplete={(result) => completed(result)}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function StepHeader({
  number,
  title,
  description,
  time,
}: {
  number: number;
  title: string;
  description: string;
  time: string;
}) {
  return (
    <header className="wizard-header">
      <p className="eyebrow">
        Step {number} of {VISIBLE_STEP_COUNT} · About {time}
      </p>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  );
}

function StepFooter({
  back,
  busy,
  label = "Save and continue",
  disabled,
  onNext,
}: {
  back?: number;
  busy: boolean;
  label?: string;
  disabled?: boolean;
  onNext?: () => void;
}) {
  return (
    <div className="sticky-step-footer">
      <div className="save-state">
        <span className={busy ? "saving-dot" : "saved-dot"} />
        {busy ? "Validating and saving…" : "Changes save when you continue"}
      </div>
      <div>
        {back && (
          <Link className="button button-secondary" to={`../${back}`}>
            Back
          </Link>
        )}
        <Button
          type={onNext ? "button" : "submit"}
          onClick={onNext}
          disabled={busy || disabled}
          icon="arrow"
        >
          {busy ? "Saving…" : label}
        </Button>
      </div>
    </div>
  );
}

function FormError({ error }: { error: string }) {
  return error ? (
    <Notice tone="danger" title="This step needs attention">
      {error}
    </Notice>
  ) : null;
}

function BriefStep({ view, onComplete }: StepProps) {
  const { data } = useStudio();
  const legacyAiDraftingEnabled =
    data.settings?.assistant_mode === "legacy_openai_api";
  const draft = view.draft;
  const source = draft.sources?.[0] || {};
  const fp = draft.economic_edge_fingerprint || {};
  const objectives = draft.research_objectives || {};
  const defaultDeadline = new Date(Date.now() + 180 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
  const [form, setForm] = useState({
    development_goal:
      objectives.development_goal ||
      "Determine whether this candidate can survive the frozen research protocol.",
    development_deadline: objectives.development_deadline || defaultDeadline,
    evaluation_horizon_months: objectives.evaluation_horizon_months || 24,
    minimum_annualized_return_percent:
      (objectives.minimum_annualized_return_fraction ?? 0.2) * 100,
    minimum_mar: objectives.minimum_mar ?? 0.4,
    maximum_drawdown_percent:
      (objectives.maximum_drawdown_fraction ?? 0.1) * 100,
    minimum_complete_wfa_windows:
      objectives.minimum_complete_wfa_windows || 3,
    minimum_wfa_oos_trades: objectives.minimum_wfa_oos_trades || 50,
    minimum_acceptance_oos_trades:
      objectives.minimum_acceptance_oos_trades || 30,
    monte_carlo_min_runs: objectives.monte_carlo_min_runs || 8000,
    monte_carlo_horizon_months:
      objectives.monte_carlo_horizon_months || 6,
    minimum_net_profit_probability_percent:
      (objectives.minimum_net_profit_probability ?? 0.7) * 100,
    maximum_account_breach_probability_percent:
      (objectives.maximum_account_breach_probability ?? 0.1) * 100,
    forward_incubation_min_calendar_days:
      objectives.forward_incubation_min_calendar_days || 90,
    forward_incubation_min_trades:
      objectives.forward_incubation_min_trades || 30,
    maximum_variants: objectives.maximum_variants || 5,
    abandonment_rules: (
      objectives.abandonment_rules || [
        "Stop when any frozen stage gate fails; do not tune after observing OOS results.",
      ]
    ).join("\n"),
    retirement_rules: (
      objectives.retirement_rules || [
        "Retire after a live risk breach or sustained degradation beyond the frozen limits.",
      ]
    ).join("\n"),
    objectives_confirmed: objectives.confirmed === true,
    title: draft.title || "",
    edge_family: draft.edge_family || "",
    timeframe: draft.timeframe || "1m",
    hypothesis: draft.hypothesis || "",
    expected_mechanism: draft.expected_mechanism || "",
    holding_horizon: draft.holding_horizon || "Intraday",
    known_failure_modes: (draft.known_failure_modes || []).join("\n"),
    source_title: source.title || "",
    authors: (source.authors || []).join(", "),
    year: source.year || new Date().getFullYear(),
    link: source.link || "",
    doi: source.doi || "",
    relevance: source.relevance || "",
    market_behavior: fp.market_behavior || "",
    signal_inputs: (fp.signal_inputs || []).join(", "),
    market_context: fp.market_context || "RTH futures",
  });
  const [objectiveTemplate, setObjectiveTemplate] = useState<
    keyof typeof OBJECTIVE_TEMPLATES | "custom"
  >(objectives.confirmed ? "custom" : "generic_candidate");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showAi, setShowAi] = useState(false);
  const [aiNotes, setAiNotes] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiStatus, setAiStatus] = useState<any>(null);
  const [aiResult, setAiResult] = useState<any>(null);
  const [aiConfirmed, setAiConfirmed] = useState(false);
  const [pdfInfo, setPdfInfo] = useState<any>(null);
  const [pdfPages, setPdfPages] = useState<number[]>([]);
  const [pdfBusy, setPdfBusy] = useState(false);
  const update = (key: string, value: any) =>
    setForm((old) => ({ ...old, [key]: value }));
  function applyObjectiveTemplate(key: keyof typeof OBJECTIVE_TEMPLATES) {
    const { label: _label, description: _description, ...values } =
      OBJECTIVE_TEMPLATES[key];
    setObjectiveTemplate(key);
    setForm((current) => ({
      ...current,
      ...values,
      objectives_confirmed: false,
    }));
  }
  async function toggleAi() {
    const next = !showAi;
    setShowAi(next);
    if (next && !aiStatus) {
      try {
        setAiStatus(await api.aiStatus());
      } catch (reason) {
        setError(message(reason));
      }
    }
  }
  async function draftWithAi() {
    if (!form.source_title.trim()) {
      setError("Enter the source title before requesting an optional draft.");
      return;
    }
    setAiBusy(true);
    setError("");
    setAiResult(null);
    setAiConfirmed(false);
    try {
      setAiResult(
        await api.suggestResearchBrief({
          campaign_id: view.campaign_id,
          selected_text: aiNotes,
          source_title: form.source_title,
          instrument: draft.instrument,
        }),
      );
    } catch (reason) {
      setError(message(reason));
    } finally {
      setAiBusy(false);
    }
  }
  async function inspectPdf(file: File | undefined) {
    if (!file) return;
    setPdfBusy(true);
    setError("");
    try {
      const result = await api.inspectResearchPdf(file);
      setPdfInfo(result);
      setPdfPages([]);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setPdfBusy(false);
    }
  }
  async function extractPdfPages() {
    if (!pdfInfo || !pdfPages.length) return;
    setPdfBusy(true);
    setError("");
    try {
      const result = await api.extractResearchPdf(
        pdfInfo.upload_token,
        pdfPages,
      );
      setAiNotes(result.selected_text);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setPdfBusy(false);
    }
  }
  function applyAiSuggestion() {
    if (!aiConfirmed || !aiResult?.suggestion) return;
    const suggestion = aiResult.suggestion;
    setForm((current) => ({
      ...current,
      hypothesis: suggestion.hypothesis,
      expected_mechanism: suggestion.expected_mechanism,
      holding_horizon: suggestion.expected_holding_horizon,
      known_failure_modes: [
        ...(suggestion.known_failure_modes || []),
        ...(suggestion.lookahead_risks || []).map(
          (item: string) => `Lookahead risk to resolve: ${item}`,
        ),
      ].join("\n"),
      market_behavior:
        suggestion.economic_edge_fingerprint?.market_behavior ||
        current.market_behavior,
      signal_inputs:
        suggestion.economic_edge_fingerprint?.signal_inputs ||
        current.signal_inputs,
      market_context:
        suggestion.economic_edge_fingerprint?.market_context ||
        current.market_context,
    }));
    setShowAi(false);
    setError("");
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.objectives_confirmed) {
      setError("Confirm the pre-PnL development and risk objectives before continuing.");
      return;
    }
    if (!form.link.trim() && !form.doi.trim()) {
      setError("Provide either a source link or DOI before continuing.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await api.saveBrief(view.campaign_id, {
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
          abandonment_rules: lines(form.abandonment_rules),
          retirement_rules: lines(form.retirement_rules),
          confirmed: true,
        },
        title: form.title,
        edge_family: form.edge_family,
        timeframe: form.timeframe,
        hypothesis: form.hypothesis,
        expected_mechanism: form.expected_mechanism,
        holding_horizon: form.holding_horizon,
        known_failure_modes: lines(form.known_failure_modes),
        source: {
          title: form.source_title,
          authors: csv(form.authors),
          year: Number(form.year),
          link: form.link || null,
          doi: form.doi || null,
          relevance: form.relevance,
        },
        economic_edge_fingerprint: {
          market_behavior: form.market_behavior,
          causal_mechanism: form.expected_mechanism,
          signal_inputs: csv(form.signal_inputs),
          market_context: form.market_context,
          holding_period: form.holding_horizon,
        },
      });
      onComplete(result);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <StepHeader
        number={1}
        time="10 minutes"
        title="Set the goals, then declare the edge"
        description="Freeze useful-success, abandonment, and risk limits before mechanics or performance are visible."
      />
      <FormError error={error} />
      <Card className="form-section">
        <div className="form-section-heading">
          <span>00</span>
          <div>
            <h2>Pre-PnL development contract</h2>
            <p>
              These goals may be stricter than repository policy, never weaker.
              Publication binds them by hash to every variant.
            </p>
          </div>
        </div>
        <div className="objective-template-picker">
          <Field
            label="Objective template"
            hint="Templates only populate repository-safe values. The complete expanded contract is still reviewed and frozen."
          >
            <select
              value={objectiveTemplate}
              onChange={(event) => {
                const value = event.target.value;
                if (value === "custom") {
                  setObjectiveTemplate("custom");
                  return;
                }
                applyObjectiveTemplate(value as keyof typeof OBJECTIVE_TEMPLATES);
              }}
            >
              {Object.entries(OBJECTIVE_TEMPLATES).map(([key, template]) => (
                <option key={key} value={key}>{template.label}</option>
              ))}
              <option value="custom">Custom governed objective</option>
            </select>
          </Field>
          <Notice tone="info">
            {objectiveTemplate === "custom"
              ? "Custom values remain subject to every repository policy floor."
              : OBJECTIVE_TEMPLATES[objectiveTemplate].description}
          </Notice>
        </div>
        <Field label="Development goal">
          <textarea
            rows={2}
            value={form.development_goal}
            onChange={(e) => update("development_goal", e.target.value)}
            required
          />
        </Field>
        <div className="form-grid three">
          <Field label="Decision deadline">
            <input
              type="date"
              value={form.development_deadline}
              onChange={(e) => update("development_deadline", e.target.value)}
              required
            />
          </Field>
          <Field label="Evaluation horizon (months)">
            <input
              type="number"
              min="12"
              value={form.evaluation_horizon_months}
              onChange={(e) => update("evaluation_horizon_months", e.target.value)}
              required
            />
          </Field>
          <Field label="Maximum variants">
            <input
              type="number"
              min="1"
              max="5"
              value={form.maximum_variants}
              onChange={(e) => update("maximum_variants", e.target.value)}
              required
            />
          </Field>
        </div>
        <div className="form-grid three">
          <Field label="Minimum annualized return (%)">
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={form.minimum_annualized_return_percent}
              onChange={(e) =>
                update("minimum_annualized_return_percent", e.target.value)
              }
              required
            />
          </Field>
          <Field label="Minimum MAR">
            <input
              type="number"
              min="0.4"
              step="0.01"
              value={form.minimum_mar}
              onChange={(e) => update("minimum_mar", e.target.value)}
              required
            />
          </Field>
          <Field label="Maximum drawdown (%)">
            <input
              type="number"
              min="0.01"
              max="20"
              step="0.01"
              value={form.maximum_drawdown_percent}
              onChange={(e) => update("maximum_drawdown_percent", e.target.value)}
              required
            />
          </Field>
        </div>
        <details className="advanced-settings objective-policy-details">
          <summary>Review WFA, Monte Carlo, forward, and retirement policy</summary>
        <div className="form-grid three">
          <Field label="Complete WFA windows">
            <input
              type="number"
              min="3"
              value={form.minimum_complete_wfa_windows}
              onChange={(e) => update("minimum_complete_wfa_windows", e.target.value)}
              required
            />
          </Field>
          <Field label="Minimum stitched WFA trades">
            <input
              type="number"
              min="50"
              value={form.minimum_wfa_oos_trades}
              onChange={(e) => update("minimum_wfa_oos_trades", e.target.value)}
              required
            />
          </Field>
          <Field label="Minimum final OOS trades">
            <input
              type="number"
              min="30"
              value={form.minimum_acceptance_oos_trades}
              onChange={(e) =>
                update("minimum_acceptance_oos_trades", e.target.value)
              }
              required
            />
          </Field>
        </div>
        <div className="form-grid three">
          <Field label="Monte Carlo runs">
            <input
              type="number"
              min="8000"
              value={form.monte_carlo_min_runs}
              onChange={(e) => update("monte_carlo_min_runs", e.target.value)}
              required
            />
          </Field>
          <Field label="Stress horizon (months)">
            <input
              type="number"
              min="6"
              value={form.monte_carlo_horizon_months}
              onChange={(e) => update("monte_carlo_horizon_months", e.target.value)}
              required
            />
          </Field>
          <Field label="Minimum profitable paths (%)">
            <input
              type="number"
              min="70"
              max="100"
              step="0.1"
              value={form.minimum_net_profit_probability_percent}
              onChange={(e) =>
                update("minimum_net_profit_probability_percent", e.target.value)
              }
              required
            />
          </Field>
        </div>
        <div className="form-grid three">
          <Field label="Maximum account breaches (%)">
            <input
              type="number"
              min="0"
              max="10"
              step="0.1"
              value={form.maximum_account_breach_probability_percent}
              onChange={(e) =>
                update("maximum_account_breach_probability_percent", e.target.value)
              }
              required
            />
          </Field>
          <Field label="Forward incubation days">
            <input
              type="number"
              min="90"
              value={form.forward_incubation_min_calendar_days}
              onChange={(e) =>
                update("forward_incubation_min_calendar_days", e.target.value)
              }
              required
            />
          </Field>
          <Field label="Forward incubation trades">
            <input
              type="number"
              min="30"
              value={form.forward_incubation_min_trades}
              onChange={(e) =>
                update("forward_incubation_min_trades", e.target.value)
              }
              required
            />
          </Field>
        </div>
        <div className="form-grid two">
          <Field label="Abandonment rules" hint="One precommitted stop rule per line">
            <textarea
              rows={4}
              value={form.abandonment_rules}
              onChange={(e) => update("abandonment_rules", e.target.value)}
              required
            />
          </Field>
          <Field label="Retirement rules" hint="One live degradation or risk rule per line">
            <textarea
              rows={4}
              value={form.retirement_rules}
              onChange={(e) => update("retirement_rules", e.target.value)}
              required
            />
          </Field>
        </div>
        </details>
        <label className="check-card">
          <input
            type="checkbox"
            checked={form.objectives_confirmed}
            onChange={(e) => update("objectives_confirmed", e.target.checked)}
          />
          <span>
            <strong>I confirm these objectives before inspecting strategy PnL</strong>
            <small>
              A later change invalidates downstream draft confirmations and requires a new frozen protocol.
            </small>
          </span>
        </label>
      </Card>
      {legacyAiDraftingEnabled && (
      <Card className="ai-drafting-card">
        <div>
          <span className="ai-drafting-icon">
            <Icon name="spark" />
          </span>
          <div>
            <p className="eyebrow">Optional drafting assistant</p>
            <h2>Structure selected research notes</h2>
            <p>
              Paste only text you choose. AlphaQuest sends no files, market
              data, results, web tools, or execution access.
            </p>
          </div>
        </div>
        <Button type="button" variant="secondary" onClick={() => void toggleAi()}>
          {showAi ? "Close assistant" : "Draft from selected notes"}
        </Button>
        {showAi && (
          <div className="ai-drafting-panel">
            {aiStatus && !aiStatus.configured && (
              <Notice tone="warning" title="AI is not configured">
                Studio works fully without AI. An administrator can add a key
                and pinned model in <Link to="/settings">Settings</Link>.
              </Notice>
            )}
            <Notice tone="info" title="Provider data control">
              {aiStatus?.retention_notice ||
                "Your organization's configured provider retention policy applies. AlphaQuest does not promise zero retention unless that control is enabled."}
              {aiStatus?.model && ` Pinned model: ${aiStatus.model}.`}
            </Notice>
            <Field
              label="Research PDF"
              optional
              hint="PDF parsing and page selection happen locally. The file itself is never sent to the model."
            >
              <input
                type="file"
                accept="application/pdf,.pdf"
                disabled={pdfBusy}
                onChange={(event) =>
                  void inspectPdf(event.target.files?.[0])
                }
              />
            </Field>
            {pdfInfo && (
              <div className="pdf-page-picker">
                <div className="card-kicker">
                  <strong>{pdfInfo.filename}</strong>
                  <small>Select only the pages relevant to this hypothesis.</small>
                </div>
                <div>
                  {pdfInfo.pages.map((page: any) => (
                    <label key={page.index}>
                      <input
                        type="checkbox"
                        checked={pdfPages.includes(page.index)}
                        disabled={!page.characters}
                        onChange={(event) =>
                          setPdfPages((current) =>
                            event.target.checked
                              ? [...current, page.index].sort((a, b) => a - b)
                              : current.filter((value) => value !== page.index),
                          )
                        }
                      />
                      <span>
                        <strong>Page {page.page_number}</strong>
                        <small>
                          {page.characters
                            ? `${page.characters} characters · ${page.preview || "No preview"}`
                            : "No extractable text"}
                        </small>
                      </span>
                    </label>
                  ))}
                </div>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={pdfBusy || !pdfPages.length}
                  onClick={() => void extractPdfPages()}
                >
                  {pdfBusy ? "Extracting locally…" : "Use text from selected pages"}
                </Button>
              </div>
            )}
            <Field
              label="Selected notes or locally extracted PDF text"
              hint="Do not paste market data, run results, secrets, or raw attachments."
            >
              <textarea
                rows={7}
                value={aiNotes}
                onChange={(event) => setAiNotes(event.target.value)}
              />
            </Field>
            <Button
              type="button"
              disabled={aiBusy || !aiStatus?.configured || !aiNotes.trim()}
              onClick={() => void draftWithAi()}
            >
              {aiBusy ? "Validating structured response…" : "Generate untrusted suggestion"}
            </Button>
            {aiResult?.suggestion && (
              <div className="ai-suggestion">
                <Notice tone="warning" title="Review before applying">
                  Model output is untrusted application input. It cannot run
                  code, choose variants, observe PnL, or bypass the seven gates.
                </Notice>
                <dl className="compact-dl">
                  <div>
                    <dt>Hypothesis</dt>
                    <dd>{aiResult.suggestion.hypothesis}</dd>
                  </div>
                  <div>
                    <dt>Mechanism</dt>
                    <dd>{aiResult.suggestion.expected_mechanism}</dd>
                  </div>
                  <div>
                    <dt>Holding horizon</dt>
                    <dd>{aiResult.suggestion.expected_holding_horizon}</dd>
                  </div>
                  <div>
                    <dt>Lookahead risks</dt>
                    <dd>
                      {(aiResult.suggestion.lookahead_risks || []).join("; ")}
                    </dd>
                  </div>
                  <div>
                    <dt>Questions still missing</dt>
                    <dd>
                      {(aiResult.suggestion.missing_questions || []).join("; ") ||
                        "None declared"}
                    </dd>
                  </div>
                </dl>
                <label className="check-card">
                  <input
                    type="checkbox"
                    checked={aiConfirmed}
                    onChange={(event) => setAiConfirmed(event.target.checked)}
                  />
                  <span>
                    <strong>I reviewed this suggestion</strong>
                    <small>
                      I—not the model—accept responsibility for every field I
                      apply to the research declaration.
                    </small>
                  </span>
                </label>
                <Button
                  type="button"
                  disabled={!aiConfirmed}
                  onClick={applyAiSuggestion}
                >
                  Apply reviewed suggestion to form
                </Button>
              </div>
            )}
          </div>
        )}
      </Card>
      )}
      <Card className="form-section">
        <div className="form-section-heading">
          <span>01</span>
          <div>
            <h2>The claim</h2>
            <p>State what should happen and why it should exist.</p>
          </div>
        </div>
        <div className="form-grid two">
          <Field label="Research title">
            <input
              value={form.title}
              onChange={(e) => update("title", e.target.value)}
              required
            />
          </Field>
          <Field
            label="Economic edge family"
            hint="Short classification, such as opening_auction_continuation"
          >
            <input
              value={form.edge_family}
              onChange={(e) => update("edge_family", e.target.value)}
              required
            />
          </Field>
        </div>
        <Field label="Falsifiable hypothesis">
          <textarea
            rows={3}
            value={form.hypothesis}
            onChange={(e) => update("hypothesis", e.target.value)}
            required
          />
        </Field>
        <Field label="Expected causal mechanism">
          <textarea
            rows={4}
            value={form.expected_mechanism}
            onChange={(e) => update("expected_mechanism", e.target.value)}
            required
          />
        </Field>
        <div className="form-grid two">
          <Field label="Expected holding horizon">
            <input
              value={form.holding_horizon}
              onChange={(e) => update("holding_horizon", e.target.value)}
              required
            />
          </Field>
          <Field label="Completed-bar timeframe">
            <select
              value={form.timeframe}
              onChange={(e) => update("timeframe", e.target.value)}
            >
              <option value="1m">1 minute</option>
              <option value="5m">5 minutes</option>
              <option value="15m">15 minutes</option>
            </select>
          </Field>
        </div>
        <Field label="Known failure modes" hint="One condition per line">
          <textarea
            rows={3}
            value={form.known_failure_modes}
            onChange={(e) => update("known_failure_modes", e.target.value)}
            required
          />
        </Field>
      </Card>
      <Card className="form-section">
        <div className="form-section-heading">
          <span>02</span>
          <div>
            <h2>Research source</h2>
            <p>Use a paper, exchange study, or robust practitioner source.</p>
          </div>
        </div>
        <Field label="Source title">
          <input
            value={form.source_title}
            onChange={(e) => update("source_title", e.target.value)}
            required
          />
        </Field>
        <div className="form-grid three">
          <Field label="Authors">
            <input
              value={form.authors}
              onChange={(e) => update("authors", e.target.value)}
              required
            />
          </Field>
          <Field label="Year">
            <input
              type="number"
              min="1900"
              max="2200"
              value={form.year}
              onChange={(e) => update("year", e.target.value)}
              required
            />
          </Field>
          <Field label="DOI (or provide a source link below)">
            <input
              value={form.doi}
              onChange={(e) => update("doi", e.target.value)}
            />
          </Field>
        </div>
        <Field label="Source link (or provide a DOI above)">
          <input
            type="url"
            value={form.link}
            onChange={(e) => update("link", e.target.value)}
          />
        </Field>
        <Field
          label={`Why this source may apply to ${draft.instrument || "this futures market"}`}
        >
          <textarea
            rows={3}
            value={form.relevance}
            onChange={(e) => update("relevance", e.target.value)}
            required
          />
        </Field>
      </Card>
      <Card className="form-section">
        <div className="form-section-heading">
          <span>03</span>
          <div>
            <h2>Economic fingerprint</h2>
            <p>This prevents the same edge returning under another name.</p>
          </div>
        </div>
        <Field label="Market behavior">
          <input
            value={form.market_behavior}
            onChange={(e) => update("market_behavior", e.target.value)}
            required
          />
        </Field>
        <div className="form-grid two">
          <Field label="Signal inputs" hint="Comma separated">
            <input
              value={form.signal_inputs}
              onChange={(e) => update("signal_inputs", e.target.value)}
              required
            />
          </Field>
          <Field label="Market context">
            <input
              value={form.market_context}
              onChange={(e) => update("market_context", e.target.value)}
              required
            />
          </Field>
        </div>
      </Card>
      <Notice
        tone="warning"
        title="Changing this later resets dependent review"
      >
        A change to the claim, source, timeframe, or fingerprint invalidates
        duplicate review and all variant confirmations.
      </Notice>
      <StepFooter busy={busy} />
    </form>
  );
}

function DuplicateStep({ view, onComplete }: StepProps) {
  const previous = view.draft.duplicate_review || {};
  const [matches, setMatches] = useState<DuplicateMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewed, setReviewed] = useState<string[]>(
    previous.reviewed_campaign_ids || [],
  );
  const [conclusion, setConclusion] = useState<DuplicateReview["conclusion"]>(
    previous.conclusion || "needs_review",
  );
  const [rationale, setRationale] = useState(
    previous.substantive_distinction || "",
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [closing, setClosing] = useState(false);
  useEffect(() => {
    api
      .duplicateContext(view.campaign_id)
      .then((value: any) => {
        setMatches(value.matches || []);
        if (value.review) {
          setReviewed(value.review.reviewed_campaign_ids || []);
          setConclusion(value.review.conclusion || "needs_review");
          setRationale(value.review.substantive_distinction || "");
        }
      })
      .catch((reason) => setError(message(reason)))
      .finally(() => setLoading(false));
  }, [view.campaign_id]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.saveDuplicates(view.campaign_id, {
        reviewed_campaign_ids: reviewed,
        conclusion,
        substantive_distinction: rationale,
      });
      onComplete(result);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }
  async function close() {
    setBusy(true);
    try {
      await api.closeDuplicate(view.campaign_id);
      setClosing(false);
      window.location.assign("/research");
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <StepHeader
        number={1}
        time="4 minutes"
        title="Review prior research"
        description="AlphaQuest scans active definitions, archives, and ledger history. You decide whether the economics are genuinely distinct."
      />
      <FormError error={error} />
      <Card className="match-summary">
        <div>
          <span className="match-count">{matches.length}</span>
          <span>possible match{matches.length === 1 ? "" : "es"}</span>
        </div>
        <p>
          {matches.length
            ? "Review every relevant result before declaring a distinct edge."
            : "No deterministic or textual match was found. Record that conclusion explicitly."}
        </p>
      </Card>
      {loading ? (
        <Skeleton lines={4} />
      ) : (
        matches.length > 0 && (
          <div className="match-list">
            {matches.map((match) => (
              <Card
                className={
                  reviewed.includes(match.campaign_id)
                    ? "match-card reviewed"
                    : "match-card"
                }
                key={match.campaign_id}
              >
                <label>
                  <input
                    type="checkbox"
                    checked={reviewed.includes(match.campaign_id)}
                    onChange={(e) =>
                      setReviewed((old) =>
                        e.target.checked
                          ? [...old, match.campaign_id]
                          : old.filter((id) => id !== match.campaign_id),
                      )
                    }
                  />
                  <span className="review-check">
                    <Icon name="check" />
                  </span>
                  <span>
                    <strong>{match.title || match.campaign_id}</strong>
                    <small>
                      {match.lifecycle || match.source || "Historical research"}
                    </small>
                  </span>
                </label>
                <div className="tag-row">
                  <StatusBadge value={match.match_band || match.lifecycle || "Prior research"} />
                  {match.exact_fingerprint && <StatusBadge value="Exact fingerprint" />}
                </div>
                {typeof (match.score ?? match.similarity) === "number" && (
                  <div className="similarity">
                    <span
                      style={{
                        width: `${Math.min(100, Number(match.score ?? match.similarity) * ((match.score ?? match.similarity)! > 1 ? 1 : 100))}%`,
                      }}
                    />
                    <small>Similarity evidence</small>
                  </div>
                )}
                <p>
                  {match.hypothesis ||
                    match.expected_mechanism ||
                    "Review the recorded fingerprint before continuing."}
                </p>
                {match.match_reasons && (
                  <div className="tag-row">
                    {match.match_reasons.map((reason) => (
                      <span key={reason}>{reason}</span>
                    ))}
                  </div>
                )}
                {(match.matched_dimensions || []).length > 0 && (
                  <div className="tag-row" aria-label="Matched economic dimensions">
                    {match.matched_dimensions!.map((dimension) => (
                      <span key={dimension}>{humanize(dimension)}</span>
                    ))}
                  </div>
                )}
              </Card>
            ))}
          </div>
        )
      )}
      <Card className="form-section">
        <div className="form-section-heading">
          <span>02</span>
          <div>
            <h2>Your conclusion</h2>
            <p>This decision becomes part of the immutable research history.</p>
          </div>
        </div>
        <div className="decision-options">
          {[
            [
              "distinct",
              "This idea is economically distinct",
              "Explain the different mechanism—not a renamed configuration.",
            ],
            [
              "duplicate",
              "This duplicates prior work",
              "Close it as FAIL before PnL and preserve the ledger history.",
            ],
            [
              "needs_review",
              "I need another review",
              "Keep the draft open without advancing to data or mechanics.",
            ],
          ].map(([value, label, detail]) => (
            <label
              className={
                conclusion === value
                  ? "decision-card selected"
                  : "decision-card"
              }
              key={value}
            >
              <input
                type="radio"
                name="conclusion"
                value={value}
                checked={conclusion === value}
                onChange={() =>
                  setConclusion(value as DuplicateReview["conclusion"])
                }
              />
              <span>
                <strong>{label}</strong>
                <small>{detail}</small>
              </span>
              <span className="radio-dot" />
            </label>
          ))}
        </div>
        <Field
          label={
            conclusion === "duplicate"
              ? "Why this is the same economic edge"
              : "Substantive economic distinction"
          }
          hint={`${rationale.length}/80 minimum characters`}
        >
          <textarea
            rows={4}
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
            required
          />
        </Field>
        {conclusion === "duplicate" && (
          <Button
            type="button"
            variant="danger"
            disabled={rationale.trim().length < 80}
            onClick={() => setClosing(true)}
          >
            Close before PnL as FAIL
          </Button>
        )}
      </Card>
      {closing && (
        <div
          className="inline-confirm"
          role="alertdialog"
          aria-labelledby="close-title"
        >
          <div>
            <Icon name="warning" />
            <span>
              <strong id="close-title">Close this research as FAIL?</strong>
              <small>
                This appends an immutable ledger event. No backtest will run.
              </small>
            </span>
          </div>
          <div>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setClosing(false)}
            >
              Keep draft
            </Button>
            <Button type="button" variant="danger" onClick={() => void close()}>
              Close as FAIL
            </Button>
          </div>
        </div>
      )}
      <StepFooter
        back={1}
        busy={busy}
        disabled={
          ((conclusion === "distinct" || conclusion === "duplicate") &&
            rationale.trim().length < 80) ||
          (matches.length > 0 && reviewed.length < matches.length)
        }
        label={
          conclusion === "distinct" ? "Save and choose data" : "Save review"
        }
      />
    </form>
  );
}

function DatasetStep({ view, onComplete }: StepProps) {
  const { data } = useStudio();
  const eligible = data.libraries?.datasets || [];
  const draft = view.draft;
  const filtered = eligible.filter(
    (item) =>
      item.symbol === draft.instrument &&
      item.timeframe === draft.timeframe &&
      item.quality_verdict === "PASS",
  );
  const [selected, setSelected] = useState(
    draft.dataset?.dataset_id ||
      (filtered.length === 1 ? filtered[0].dataset_id : ""),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const chosen = filtered.find((item) => item.dataset_id === selected);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onComplete(await api.selectDataset(view.campaign_id, selected));
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <StepHeader
        number={2}
        time="3 minutes"
        title="Choose governed market data"
        description={`Only ${draft.instrument} ${draft.timeframe} bars with a PASS quality verdict can enter this protocol.`}
      />
      <FormError error={error} />
      {filtered.length === 0 ? (
        <Card className="empty-state">
          <span className="empty-icon">
            <Icon name="database" />
          </span>
          <h3>No compatible governed dataset</h3>
          <p>
            Import and validate {draft.instrument} {draft.timeframe} bars in the
            Data library, then return here.
          </p>
          <Link className="button button-secondary" to="/library/data">
            Open data library
          </Link>
        </Card>
      ) : (
        <div className="dataset-choice-grid">
          {filtered.map((item) => (
            <label
              className={
                selected === item.dataset_id
                  ? "dataset-choice selected"
                  : "dataset-choice"
              }
              key={item.dataset_id}
            >
              <input
                type="radio"
                name="dataset"
                value={item.dataset_id}
                checked={selected === item.dataset_id}
                onChange={() => setSelected(item.dataset_id)}
              />
              <div className="dataset-choice-head">
                <span className="dataset-icon">
                  <Icon name="database" />
                </span>
                <StatusBadge
                  value={item.quality_verdict || "Unknown"}
                  kind="scientific"
                />
              </div>
              <strong>{humanize(item.dataset_id)}</strong>
              <span>
                {item.symbol} · {item.timeframe} ·{" "}
                {item.row_count?.toLocaleString() || "—"} rows
              </span>
              <small>
                {item.timezone || "Timezone not shown"} ·{" "}
                {humanize(item.timestamp_semantics)}
              </small>
              <span className="radio-mark">
                <Icon name="check" />
              </span>
            </label>
          ))}
        </div>
      )}
      {chosen && (
        <Card className="quality-summary">
          <div className="quality-head">
            <div>
              <p className="eyebrow">Selected dataset</p>
              <h2>Quality and lineage</h2>
            </div>
            <StatusBadge value={chosen.quality_verdict} kind="scientific" />
          </div>
          <dl>
            <div>
              <dt>Coverage</dt>
              <dd>
                {shortDate(chosen.coverage_start)} →{" "}
                {shortDate(chosen.coverage_end)}
              </dd>
            </div>
            <div>
              <dt>Timestamp meaning</dt>
              <dd>{humanize(chosen.timestamp_semantics)}</dd>
            </div>
            <div>
              <dt>Roll policy</dt>
              <dd>{humanize(chosen.roll_policy)}</dd>
            </div>
            <div>
              <dt>Timezone</dt>
              <dd>{chosen.timezone || "Not recorded"}</dd>
            </div>
          </dl>
          <div
            className="quality-counts"
            aria-label="Dataset validation counts"
          >
            <span>
              <strong>{chosen.dropped_row_count || 0}</strong>Dropped rows
            </span>
            <span>
              <strong>{chosen.gap_count || 0}</strong>Gaps
            </span>
            <span>
              <strong>{chosen.duplicate_count || 0}</strong>Duplicates
            </span>
            <span>
              <strong>{chosen.invalid_ohlc_count || 0}</strong>Invalid OHLC
            </span>
          </div>
          {chosen.research_readiness && (
            <Notice
              tone={chosen.research_readiness.status === "READY" ? "success" : "warning"}
              title={`Research-window forecast: ${humanize(chosen.research_readiness.status)}`}
            >
              {chosen.research_readiness.available_months ?? "Unknown"} months available; approximately{" "}
              {chosen.research_readiness.required_months} required. {chosen.research_readiness.blockers.join(" ")}
              <br />This forecast does not predict signal count or performance.
            </Notice>
          )}
          <TechnicalDetails>
            <pre>{JSON.stringify(chosen, null, 2)}</pre>
          </TechnicalDetails>
        </Card>
      )}
      <StepFooter back={2} busy={busy} disabled={!selected} />
    </form>
  );
}

function ExecutionStep({ view, onComplete }: StepProps) {
  const { data } = useStudio();
  const draft = view.draft;
  const current = draft.execution || {};
  const settings = data.settings || {};
  const currentPrimaryAccount = (current.target_account_profiles || []).find(
    (item: any) => item.role === "primary",
  );
  const defaults =
    draft.instrument === "NQ"
      ? { tick_size: 0.25, point_value: 20, tick_value: 5 }
      : { tick_size: 0.25, point_value: 50, tick_value: 12.5 };
  const [form, setForm] = useState({
    session_start: current.session_start || "09:30:00",
    session_end: current.session_end || "16:00:00",
    latest_entry_time: current.latest_entry_time || "15:45:00",
    flatten_time:
      current.flatten_time || settings.default_flatten_time || "15:55:00",
    latest_flat_time: current.latest_flat_time || "15:56:00",
    contracts: current.contracts || 1,
    tick_size: current.tick_size || defaults.tick_size,
    point_value: current.point_value || defaults.point_value,
    tick_value: current.tick_value || defaults.tick_value,
    commission_per_contract:
      current.commission_per_contract ??
      settings.default_commission_per_contract ??
      2.5,
    slippage_ticks:
      current.slippage_ticks ?? settings.default_slippage_ticks ?? 1,
    initial_balance:
      current.initial_balance || settings.default_initial_balance || 150000,
    prop_profile: current.prop_profile || "configured_local_profile",
    target_account_profile_key: currentPrimaryAccount
      ? `${currentPrimaryAccount.profile_id}@${currentPrimaryAccount.version || ""}`
      : "",
  });
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const update = (k: string, v: any) => setForm((old) => ({ ...old, [k]: v }));
  function restoreGovernedDefaults() {
    setForm((currentForm) => ({
      ...currentForm,
      flatten_time: settings.default_flatten_time || "15:55:00",
      commission_per_contract:
        settings.default_commission_per_contract ?? 2.5,
      slippage_ticks: settings.default_slippage_ticks ?? 1,
      initial_balance: settings.default_initial_balance || 150000,
      tick_size: defaults.tick_size,
      point_value: defaults.point_value,
      tick_value: defaults.tick_value,
    }));
    setConfirmed(false);
  }
  const propProfiles = data.libraries?.prop_profiles || [];
  const accountProfiles = data.libraries?.account_profiles || [];
  const selectedProfile = propProfiles.find(
    (item: any) => item.profile_id === form.prop_profile,
  );
  const selectedAccountProfile = accountProfiles.find(
    (item: any) =>
      `${item.profile_id}@${item.version || ""}` === form.target_account_profile_key,
  );
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { target_account_profile_key, ...legacyExecution } = form;
      const [targetProfileId, targetVersion] = target_account_profile_key
        ? target_account_profile_key.split("@", 2)
        : ["", ""];
      onComplete(
        await api.saveExecution(view.campaign_id, {
          execution: {
            ...legacyExecution,
            overnight_allowed: false,
            target_account_profiles: targetProfileId
              ? [
                  {
                    profile_id: targetProfileId,
                    version: targetVersion || null,
                    role: "primary",
                  },
                ]
              : [],
          },
          roll_policy_confirmed: confirmed,
        }),
      );
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <StepHeader
        number={3}
        time="4 minutes"
        title="Confirm realistic execution"
        description="Set costs, session rules, and mandatory flattening before mechanics are designed."
      />
      <FormError error={error} />
      <Notice
        tone="info"
        title="Governed values inherited once"
      >
        Studio inherited {draft.instrument} constants plus the commission,
        slippage, balance, and flatten defaults from Settings. Confirm the
        resolved contract here; downstream definitions reuse it without asking
        you to type it again.
        <div className="notice-actions">
          <Button type="button" variant="secondary" onClick={restoreGovernedDefaults}>
            Restore governed defaults
          </Button>
        </div>
      </Notice>
      <Card className="form-section">
        <div className="form-section-heading">
          <span>01</span>
          <div>
            <h2>Trading session</h2>
            <p>All times use the governed exchange timezone.</p>
          </div>
        </div>
        <div className="form-grid three">
          <TimeField
            label="Session opens"
            value={form.session_start}
            onChange={(v) => update("session_start", v)}
          />
          <TimeField
            label="Session closes"
            value={form.session_end}
            onChange={(v) => update("session_end", v)}
          />
          <TimeField
            label="Latest new entry"
            value={form.latest_entry_time}
            onChange={(v) => update("latest_entry_time", v)}
          />
          <TimeField
            label="Force flatten"
            value={form.flatten_time}
            onChange={(v) => update("flatten_time", v)}
          />
          <TimeField
            label="Must be flat by"
            value={form.latest_flat_time}
            onChange={(v) => update("latest_flat_time", v)}
          />
        </div>
      </Card>
      <Card className="form-section">
        <div className="form-section-heading">
          <span>02</span>
          <div>
            <h2>Costs and sizing</h2>
            <p>Every metric is reported after these costs.</p>
          </div>
        </div>
        <div className="form-grid three">
          <NumberField
            label="Contracts"
            value={form.contracts}
            onChange={(v) => update("contracts", v)}
            min={1}
          />
          <NumberField
            label="Commission per contract"
            value={form.commission_per_contract}
            onChange={(v) => update("commission_per_contract", v)}
            prefix="$"
          />
          <NumberField
            label="Slippage"
            value={form.slippage_ticks}
            onChange={(v) => update("slippage_ticks", v)}
            suffix="ticks"
          />
          <NumberField
            label="Initial balance"
            value={form.initial_balance}
            onChange={(v) => update("initial_balance", v)}
            prefix="$"
          />
          <Field label="Prop profile">
            <select
              value={form.prop_profile}
              onChange={(e) => update("prop_profile", e.target.value)}
              required
            >
              {propProfiles.map((item: any) => (
                <option key={item.profile_id} value={item.profile_id}>
                  {item.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Target account assessment">
            <select
              value={form.target_account_profile_key}
              onChange={(e) => update("target_account_profile_key", e.target.value)}
            >
              <option value="">No destination selected</option>
              {accountProfiles
                .filter((item: any) => item.promotable)
                .map((item: any) => (
                  <option
                    key={`${item.profile_id}@${item.version}`}
                    value={`${item.profile_id}@${item.version}`}
                  >
                    {item.name}
                  </option>
                ))}
            </select>
          </Field>
        </div>
        {selectedProfile && (
          <Notice tone="info" title={selectedProfile.name}>
            {selectedProfile.description} Challenge target {selectedProfile.challenge_profit_target_pct}% · drawdown limit {selectedProfile.drawdown_limit_pct}% · minimum {selectedProfile.minimum_trading_days} trading days. The complete resolved rules are frozen into every variant config.
          </Notice>
        )}
        {selectedAccountProfile && (
          <Notice tone="warning" title={selectedAccountProfile.name}>
            {selectedAccountProfile.description} Rule version {selectedAccountProfile.version}, effective {selectedAccountProfile.effective_from}. {selectedAccountProfile.evaluation_price_input_required && selectedAccountProfile.activation_fee_input_required ? "A timestamped evaluation checkout price and activation fee will be required for cost-adjusted assessment." : selectedAccountProfile.evaluation_price_input_required ? "A timestamped evaluation checkout price will be required for cost-adjusted assessment." : selectedAccountProfile.activation_fee_input_required ? "A timestamped activation fee will be required for cost-adjusted assessment." : "No separate acquisition-cost input is required."}
          </Notice>
        )}
        <details className="advanced-settings">
          <summary>Review instrument constants</summary>
          <dl className="compact-dl instrument-constants">
            <div><dt>Tick size</dt><dd>{form.tick_size}</dd></div>
            <div><dt>Point value</dt><dd>${form.point_value}</dd></div>
            <div><dt>Tick value</dt><dd>${form.tick_value}</dd></div>
          </dl>
          <small>
            Instrument constants are certified together; tick value must equal
            tick size × point value.
          </small>
        </details>
      </Card>
      <Card className="execution-summary">
        <Icon name="shield" />
        <div>
          <p className="eyebrow">Plain-language protocol</p>
          <p>
            Trade{" "}
            <strong>
              {form.contracts} {draft.instrument} contract
              {form.contracts === 1 ? "" : "s"}
            </strong>{" "}
            from {form.session_start} to {form.session_end}; stop new entries at{" "}
            {form.latest_entry_time}; flatten at {form.flatten_time}; charge $
            {form.commission_per_contract} plus {form.slippage_ticks} tick
            {form.slippage_ticks === 1 ? "" : "s"} slippage. No overnight
            positions.
          </p>
        </div>
      </Card>
      <label className="confirmation">
        <input
          type="checkbox"
          checked={confirmed}
          onChange={(e) => setConfirmed(e.target.checked)}
        />
        <span>
          <Icon name="check" />
        </span>
        <div>
          <strong>I reviewed the dataset’s contract roll policy</strong>
          <small>
            {humanize(draft.dataset?.roll_policy)} · changing data or execution
            later invalidates mechanics confirmation.
          </small>
        </div>
      </label>
      <StepFooter back={3} busy={busy} disabled={!confirmed} />
    </form>
  );
}

function MechanicsStep({ view, onComplete }: StepProps) {
  const draft = view.draft;
  const [lane, setLane] = useState(draft.authoring_lane || "certified_recipe");
  const [recipe, setRecipe] = useState(
    draft.certified_recipe || "opening_range_breakout",
  );
  const [confirmed, setConfirmed] = useState(false);
  const [eventStrategies, setEventStrategies] = useState<any[]>([]);
  const [eventStrategy, setEventStrategy] = useState(draft.event_strategy || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [rule, setRule] = useState({
    feature: "close",
    lag: 0,
    conditionType: "cross",
    direction: "above",
    rollingFunction: "mean",
    window: 20,
    operator: "gt",
    threshold: 0,
    tuneThreshold: false,
    thresholdValues: "-3, -2, -1, 0, 1, 2, 3, 4",
    lower: 0,
    upper: 1,
    inclusive: true,
    signals: "both",
    secondFilter: false,
    filterFeature: "volume",
    filterOperator: "gt",
    filterThreshold: 0,
    booleanGroup: "all",
    signalStartTime: draft.execution?.session_start || "09:30:00",
    signalEndTime: draft.execution?.latest_entry_time || "15:45:00",
    maxTradesPerDay: 1,
    rthOnly: true,
  });
  const [handoff, setHandoff] = useState({
    reason_unsupported: "",
    causal_timeline: "",
    required_data_granularity: "Tick-by-tick event replay",
    fill_and_ambiguity_rules: "",
    required_module_contract: "",
    required_tests: "",
    proposed_mechanics: "",
  });
  useEffect(() => {
    api
      .libraries()
      .then((result) => {
        const packages = publicationAvailableStrategyPackages(
          result.modules || [],
        );
        setEventStrategies(packages);
        if (!eventStrategy && packages.length) setEventStrategy(packages[0].name);
      })
      .catch(() => setEventStrategies([]));
  }, []);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      let result: DraftView;
      if (lane === "certified_recipe")
        result = await api.saveRecipe(view.campaign_id, { recipe, confirmed });
      else if (lane === "visual_completed_bar_rule")
        result = await api.saveRule(view.campaign_id, {
          rule: buildRule(rule, draft.timeframe || "1m"),
        });
      else if (lane === "certified_event_replay")
        result = await api.saveEventStrategy(view.campaign_id, {
          strategy_id: eventStrategy,
          confirmed,
        });
      else
        result = await api.saveHandoff(view.campaign_id, {
          ...handoff,
          causal_timeline: lines(handoff.causal_timeline),
          fill_and_ambiguity_rules: lines(handoff.fill_and_ambiguity_rules),
          required_module_contract: lines(handoff.required_module_contract),
          required_tests: lines(handoff.required_tests),
          proposed_mechanics: lines(handoff.proposed_mechanics),
        });
      onComplete(result);
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }
  const lanes = [
    {
      id: "certified_recipe",
      icon: "shield" as const,
      title: "Certified recipe",
      body: "Use audited completed-bar modules with known timing and compatibility.",
    },
    {
      id: "visual_completed_bar_rule",
      icon: "methods" as const,
      title: "Visual bar rule",
      body: "Build a bounded causal comparison without code or arbitrary expressions.",
    },
    {
      id: "certified_event_replay",
      icon: "clock" as const,
      title: "Certified event strategy",
      body: "Select versioned event-replay code whose source hash and required tests are current.",
    },
    {
      id: "engineering_handoff",
      icon: "file" as const,
      title: "Engineering handoff",
      body: "Intrabar, order-flow, event replay, or custom features—never approximated.",
    },
  ];
  const visualFeatures = Array.from(
    new Set([
      "open",
      "high",
      "low",
      "close",
      "volume",
      ...((draft.dataset?.certified_features || []) as string[]),
    ]),
  );
  return (
    <form onSubmit={submit}>
      <StepHeader
        number={4}
        time="5 minutes"
        title="Choose how the idea becomes mechanics"
        description="Only representations that preserve the frozen hypothesis and causal timing may proceed."
      />
      <FormError error={error} />
      <div className="lane-grid">
        {lanes.map((item) => (
          <label
            className={lane === item.id ? "lane-card selected" : "lane-card"}
            key={item.id}
          >
            <input
              type="radio"
              name="lane"
              value={item.id}
              checked={lane === item.id}
              onChange={() => setLane(item.id)}
            />
            <span className="lane-icon">
              <Icon name={item.icon} />
            </span>
            <strong>{item.title}</strong>
            <p>{item.body}</p>
            <span className="radio-mark">
              <Icon name="check" />
            </span>
          </label>
        ))}
      </div>
      {lane === "certified_recipe" && (
        <Card className="form-section">
          <div className="form-section-heading">
            <span>01</span>
            <div>
              <h2>Select one edge recipe</h2>
              <p>The entry edge remains fixed as later variants are added one at a time.</p>
            </div>
          </div>
          <div className="recipe-list">
            {[
              [
                "opening_range_breakout",
                "Opening-range breakout",
                "Trades a completed-bar break after the opening range becomes known.",
              ],
              [
                "calendar_session_bias",
                "Calendar session bias",
                "Expresses a predeclared weekday/session tendency at the next bar open.",
              ],
              [
                "daily_tsm_close_to_close",
                "Daily trend · close to close",
                "Uses causal daily time-series momentum from completed sessions.",
              ],
              [
                "daily_tsm_volatility_normalized",
                "Daily trend · volatility normalized",
                "Scales the completed-session trend by prior realized volatility.",
              ],
              [
                "daily_tsm_short_term_alignment",
                "Daily trend · short-term alignment",
                "Requires long- and short-horizon completed trends to agree.",
              ],
            ].map(([value, title, body]) => (
              <label
                className={
                  recipe === value ? "recipe-row selected" : "recipe-row"
                }
                key={value}
              >
                <input
                  type="radio"
                  name="recipe"
                  value={value}
                  checked={recipe === value}
                  onChange={() => setRecipe(value)}
                />
                <span>
                  <strong>{title}</strong>
                  <small>{body}</small>
                </span>
                <span className="radio-dot" />
              </label>
            ))}
          </div>
          <label className="confirmation compact">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            <span>
              <Icon name="check" />
            </span>
            <div>
              <strong>This recipe represents the frozen hypothesis</strong>
              <small>
                Variants may change risk and exit mechanics, not substitute
                another edge.
              </small>
            </div>
          </label>
        </Card>
      )}
      {lane === "visual_completed_bar_rule" && (
        <Card className="form-section rule-builder">
          <div className="form-section-heading">
            <span>01</span>
            <div>
              <h2>Build a bounded causal rule</h2>
              <p>
                Current or lagged certified fields only. No eval, future windows,
                negative lags, or session-final values.
              </p>
            </div>
          </div>
          <div className="form-grid three">
            <Field label="Condition">
              <select
                value={rule.conditionType}
                onChange={(e) =>
                  setRule({
                    ...rule,
                    conditionType: e.target.value,
                    ...(e.target.value === "range" && rule.signals === "both"
                      ? { signals: "long" }
                      : {}),
                  })
                }
              >
                <option value="cross">Crosses a prior rolling value</option>
                <option value="comparison">Compares with a threshold</option>
                <option value="range">Falls inside a range</option>
              </select>
            </Field>
            <Field label="Completed-bar feature">
              <select
                value={rule.feature}
                onChange={(e) => setRule({ ...rule, feature: e.target.value })}
              >
                {visualFeatures.map((feature) => (
                  <option key={feature}>{feature}</option>
                ))}
              </select>
            </Field>
            <Field
              label="Feature lag"
              hint="0 is the just-completed bar; positive values use older bars."
            >
              <input
                type="number"
                min="0"
                max="512"
                value={rule.lag}
                onChange={(e) =>
                  setRule({ ...rule, lag: Number(e.target.value) })
                }
              />
            </Field>
          </div>
          {rule.conditionType === "cross" && (
            <div className="form-grid three visual-condition-card">
              <Field label="Crossing direction">
                <select
                  value={rule.direction}
                  onChange={(e) =>
                    setRule({ ...rule, direction: e.target.value })
                  }
                >
                  <option value="above">Crosses above once</option>
                  <option value="below">Crosses below once</option>
                </select>
              </Field>
              <Field label="Prior rolling transform">
                <select
                  value={rule.rollingFunction}
                  onChange={(e) =>
                    setRule({ ...rule, rollingFunction: e.target.value })
                  }
                >
                  {['mean', 'sum', 'min', 'max', 'std'].map((value) => (
                    <option key={value}>{value}</option>
                  ))}
                </select>
              </Field>
              <Field label="Rolling window">
                <input
                  type="number"
                  min="2"
                  max="256"
                  value={rule.window}
                  onChange={(e) =>
                    setRule({ ...rule, window: Number(e.target.value) })
                  }
                />
              </Field>
            </div>
          )}
          {rule.conditionType === "comparison" && (
            <div className="visual-condition-card">
              <div className="form-grid two">
                <Field label="Comparison">
                  <select
                    value={rule.operator}
                    onChange={(e) =>
                      setRule({ ...rule, operator: e.target.value })
                    }
                  >
                    <option value="gt">Greater than</option>
                    <option value="gte">Greater than or equal</option>
                    <option value="lt">Less than</option>
                    <option value="lte">Less than or equal</option>
                  </select>
                </Field>
                <Field label="Threshold">
                  <input
                    type="number"
                    step="any"
                    value={rule.threshold}
                    onChange={(e) =>
                      setRule({ ...rule, threshold: Number(e.target.value) })
                    }
                  />
                </Field>
              </div>
              <label className="check-card compact-check">
                <input
                  type="checkbox"
                  checked={rule.tuneThreshold}
                  onChange={(e) =>
                    setRule({ ...rule, tuneThreshold: e.target.checked })
                  }
                />
                <span>
                  <strong>Predeclare a threshold grid</strong>
                  <small>
                    Freeze 8–20 unique values now; never select them from
                    observed PnL.
                  </small>
                </span>
              </label>
              {rule.tuneThreshold && (
                <Field label="Threshold values" hint="8–20 comma-separated numbers; include the displayed threshold.">
                  <input
                    value={rule.thresholdValues}
                    onChange={(e) =>
                      setRule({ ...rule, thresholdValues: e.target.value })
                    }
                  />
                </Field>
              )}
            </div>
          )}
          {rule.conditionType === "range" && (
            <div className="visual-condition-card">
              <div className="form-grid two">
                <Field label="Lower bound">
                  <input
                    type="number"
                    step="any"
                    value={rule.lower}
                    onChange={(e) =>
                      setRule({ ...rule, lower: Number(e.target.value) })
                    }
                  />
                </Field>
                <Field label="Upper bound">
                  <input
                    type="number"
                    step="any"
                    value={rule.upper}
                    onChange={(e) =>
                      setRule({ ...rule, upper: Number(e.target.value) })
                    }
                  />
                </Field>
              </div>
              <label className="check-card compact-check">
                <input
                  type="checkbox"
                  checked={rule.inclusive}
                  onChange={(e) =>
                    setRule({ ...rule, inclusive: e.target.checked })
                  }
                />
                <span>
                  <strong>Include boundary values</strong>
                </span>
              </label>
            </div>
          )}
          <label className="check-card compact-check">
            <input
              type="checkbox"
              checked={rule.secondFilter}
              onChange={(e) =>
                setRule({ ...rule, secondFilter: e.target.checked })
              }
            />
            <span>
              <strong>Add a second completed-bar filter</strong>
              <small>Combine both clauses with an audited Boolean group.</small>
            </span>
          </label>
          {rule.secondFilter && (
            <div className="form-grid four visual-condition-card">
              <Field label="Filter feature">
                <select
                  value={rule.filterFeature}
                  onChange={(e) =>
                    setRule({ ...rule, filterFeature: e.target.value })
                  }
                >
                  {visualFeatures.map((feature) => (
                    <option key={feature}>{feature}</option>
                  ))}
                </select>
              </Field>
              <Field label="Filter comparison">
                <select
                  value={rule.filterOperator}
                  onChange={(e) =>
                    setRule({ ...rule, filterOperator: e.target.value })
                  }
                >
                  <option value="gt">Greater than</option>
                  <option value="lt">Less than</option>
                </select>
              </Field>
              <Field label="Filter threshold">
                <input
                  type="number"
                  step="any"
                  value={rule.filterThreshold}
                  onChange={(e) =>
                    setRule({ ...rule, filterThreshold: Number(e.target.value) })
                  }
                />
              </Field>
              <Field label="Boolean group">
                <select
                  value={rule.booleanGroup}
                  onChange={(e) =>
                    setRule({ ...rule, booleanGroup: e.target.value })
                  }
                >
                  <option value="all">All conditions</option>
                  <option value="any">Any condition</option>
                </select>
              </Field>
            </div>
          )}
          <Field label="Trade directions">
            <select
              value={rule.signals}
              onChange={(e) => setRule({ ...rule, signals: e.target.value })}
            >
              {rule.conditionType !== "range" && (
                <option value="both">Symmetric long and short</option>
              )}
              <option value="long">Long only</option>
              <option value="short">Short only</option>
            </select>
          </Field>
          <div className="form-grid three">
            <Field label="Signal start">
              <input
                type="time"
                step="1"
                value={rule.signalStartTime}
                onChange={(e) =>
                  setRule({ ...rule, signalStartTime: e.target.value })
                }
              />
            </Field>
            <Field label="Signal end">
              <input
                type="time"
                step="1"
                value={rule.signalEndTime}
                onChange={(e) =>
                  setRule({ ...rule, signalEndTime: e.target.value })
                }
              />
            </Field>
            <Field label="Maximum trades per day">
              <input
                type="number"
                min="1"
                max="20"
                value={rule.maxTradesPerDay}
                onChange={(e) =>
                  setRule({ ...rule, maxTradesPerDay: Number(e.target.value) })
                }
              />
            </Field>
          </div>
          <label className="check-card compact-check">
            <input
              type="checkbox"
              checked={rule.rthOnly}
              onChange={(e) =>
                setRule({ ...rule, rthOnly: e.target.checked })
              }
            />
            <span>
              <strong>Use regular-session completed bars only</strong>
            </span>
          </label>
          <div className="causal-timeline">
            <div>
              <span>
                <Icon name="chart" />
              </span>
              <strong>Bar closes</strong>
              <small>All features final</small>
            </div>
            <Icon name="arrow" />
            <div>
              <span>
                <Icon name="methods" />
              </span>
              <strong>Rule evaluates</strong>
              <small>Missing means false</small>
            </div>
            <Icon name="arrow" />
            <div>
              <span>
                <Icon name="clock" />
              </span>
              <strong>Next bar opens</strong>
              <small>Earliest legal entry</small>
            </div>
          </div>
        </Card>
      )}
      {lane === "certified_event_replay" && (
        <Card className="form-section">
          <div className="form-section-heading">
            <span>01</span>
            <div>
              <h2>Select a certified strategy package</h2>
              <p>
                Publication binds the campaign to this implementation version
                and source hash. A later code change invalidates mechanics approval.
              </p>
            </div>
          </div>
          {eventStrategies.length ? (
            <div className="recipe-list">
              {eventStrategies.map((item) => (
                <label
                  className={
                    eventStrategy === item.name
                      ? "recipe-row selected"
                      : "recipe-row"
                  }
                  key={item.name}
                >
                  <input
                    type="radio"
                    name="event-strategy"
                    checked={eventStrategy === item.name}
                    onChange={() => setEventStrategy(item.name)}
                  />
                  <span>
                    <strong>
                      {strategyPackageLabel(item) || humanize(item.name)}
                    </strong>
                    <small>
                      Implementation v{item.implementation_version} ·{" "}
                      {item.strategy_description || item.summary}
                    </small>
                  </span>
                  <span className="radio-dot" />
                </label>
              ))}
            </div>
          ) : (
            <Notice tone="warning" title="No current certification">
              Finish the engineering handoff, required tests, registration, and
              strategy certification before selecting this lane.
            </Notice>
          )}
          <label className="confirmation compact">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              disabled={!eventStrategy}
            />
            <span><Icon name="check" /></span>
            <div>
              <strong>This certified implementation represents the frozen hypothesis</strong>
              <small>Mechanics review still must pass before any performance stage.</small>
            </div>
          </label>
        </Card>
      )}
      {lane === "engineering_handoff" && (
        <>
          <Notice tone="warning" title="NEEDS MANUAL REVIEW">
            This lane creates a durable specification and blocks performance
            submission until an engineer certifies the implementation.
          </Notice>
          <Card className="form-section">
            <Field label="Why completed bars are insufficient">
              <textarea
                rows={3}
                value={handoff.reason_unsupported}
                onChange={(e) =>
                  setHandoff({ ...handoff, reason_unsupported: e.target.value })
                }
                required
              />
            </Field>
            <Field label="Causal timeline" hint="One event per line">
              <textarea
                rows={4}
                value={handoff.causal_timeline}
                onChange={(e) =>
                  setHandoff({ ...handoff, causal_timeline: e.target.value })
                }
                required
              />
            </Field>
            <Field label="Required data granularity">
              <input
                value={handoff.required_data_granularity}
                onChange={(e) =>
                  setHandoff({
                    ...handoff,
                    required_data_granularity: e.target.value,
                  })
                }
                required
              />
            </Field>
            <Field label="Fill and ambiguity rules" hint="One rule per line">
              <textarea
                rows={3}
                value={handoff.fill_and_ambiguity_rules}
                onChange={(e) =>
                  setHandoff({
                    ...handoff,
                    fill_and_ambiguity_rules: e.target.value,
                  })
                }
                required
              />
            </Field>
            <Field
              label="Required module contract"
              hint="One requirement per line"
            >
              <textarea
                rows={3}
                value={handoff.required_module_contract}
                onChange={(e) =>
                  setHandoff({
                    ...handoff,
                    required_module_contract: e.target.value,
                  })
                }
                required
              />
            </Field>
            <Field label="Required tests" hint="One test per line">
              <textarea
                rows={3}
                value={handoff.required_tests}
                onChange={(e) =>
                  setHandoff({ ...handoff, required_tests: e.target.value })
                }
                required
              />
            </Field>
            <Field
              label="Initial proposed variant mechanic"
              hint="Exactly one per line"
            >
              <textarea
                rows={5}
                value={handoff.proposed_mechanics}
                onChange={(e) =>
                  setHandoff({ ...handoff, proposed_mechanics: e.target.value })
                }
                required
              />
            </Field>
          </Card>
        </>
      )}
      <StepFooter
        back={4}
        busy={busy}
        disabled={
          (lane === "certified_recipe" || lane === "certified_event_replay") &&
          (!confirmed || (lane === "certified_event_replay" && !eventStrategy))
        }
        label={
          lane === "engineering_handoff"
            ? "Create engineering handoff"
            : "Save mechanics lane"
        }
      />
    </form>
  );
}

function VariantsStep({ view, onComplete }: StepProps) {
  const [variants, setVariants] = useState<any[]>(view.draft.variants || []);
  const [catalog, setCatalog] = useState<any[]>([]);
  const [eventGridDrafts, setEventGridDrafts] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState(0);
  const [loading, setLoading] = useState(!variants.length);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    api
      .variants(view.campaign_id)
      .then((result) => {
        const loaded = result.variants || [];
        setVariants(loaded);
        setCatalog(result.catalog || []);
        setEventGridDrafts(
          Object.fromEntries(
            loaded.flatMap((variant: any) =>
              Object.entries(variant.event_parameter_grid || {}).map(
                ([name, values]: [string, any]) => [
                  `${variant.variant_id}:${name}`,
                  (values || []).join(", "),
                ],
              ),
            ),
          ),
        );
      })
      .catch((reason) => setError(message(reason)))
      .finally(() => setLoading(false));
  }, [view.campaign_id]);
  const update = (key: string, value: any) =>
    setVariants((old) =>
      old.map((item, index) =>
        index === selected
          ? {
              ...item,
              [key]: value,
              ...(key === "confirmed" ? {} : { confirmed: false }),
            }
          : item,
      ),
    );
  const updateBinding = (kind: "stop" | "target", value: any) =>
    setVariants((old) =>
      old.map((item, index) =>
        index === selected
          ? { ...item, [kind]: value, confirmed: false }
          : item,
      ),
    );
  const updateEventParam = (name: string, value: any) =>
    setVariants((old) =>
      old.map((item, index) =>
        index === selected
          ? {
              ...item,
              entry: {
                ...item.entry,
                params: {
                  ...item.entry.params,
                  mechanics: { ...item.entry.params?.mechanics, [name]: value },
                },
              },
              confirmed: false,
            }
          : item,
      ),
    );
  const current = variants[selected] || {};
  const allConfirmed =
    variants.length === 1 && variants.every((v) => v.confirmed);
  async function save() {
    setBusy(true);
    setError("");
    try {
      const prepared = variants.map((variant) => {
        if (view.draft.authoring_lane !== "certified_event_replay") return variant;
        const module = catalog.find((item) => item.name === variant.entry?.module);
        const grid = Object.fromEntries(
          Object.entries(module?.strategy_parameters || {}).flatMap(
            ([name, spec]: [string, any]) => {
              const raw = eventGridDrafts[`${variant.variant_id}:${name}`] || "";
              return raw.trim()
                ? [[name, parseParameterGridValues(raw, spec.value_type)]]
                : [];
            },
          ),
        );
        return { ...variant, event_parameter_grid: grid };
      });
      onComplete(await api.saveVariants(view.campaign_id, prepared));
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <StepHeader
        number={5}
        time="8 minutes"
        title="Confirm the first expression"
        description="Freeze only the initial mechanic now. A different expression may be proposed later only after this one is manually reviewed and fails."
      />
      <FormError error={error} />
      {loading ? (
        <Skeleton lines={8} />
      ) : (
        <>
          <Card className="variant-matrix">
            <div className="matrix-header">
              <span>Variant</span>
              <span>Entry edge</span>
              <span>Stop</span>
              <span>Target</span>
              <span>Status</span>
            </div>
            {variants.map((item, index) => (
              <button
                className={
                  selected === index ? "matrix-row selected" : "matrix-row"
                }
                key={item.variant_id || index}
                onClick={() => setSelected(index)}
              >
                <span>
                  <b>{item.variant_id || `v0${index + 1}`}</b>
                  {item.title || `Variant ${index + 1}`}
                </span>
                <span>{humanize(item.entry?.module)}</span>
                <span>{humanize(item.stop?.module)}</span>
                <span>{humanize(item.target?.module)}</span>
                <span>
                  <StatusBadge
                    value={item.confirmed ? "Confirmed" : "Needs review"}
                  />
                </span>
              </button>
            ))}
          </Card>
          {current && (
            <Card className="variant-editor">
              <div className="variant-editor-head">
                <div>
                  <p className="eyebrow">Initial variant · 1 of 1</p>
                  <h2>{current.title || `Variant ${selected + 1}`}</h2>
                </div>
              </div>
              <div className="mechanic-strip">
                <div>
                  <span>Frozen entry</span>
                  <strong>{humanize(current.entry?.module)}</strong>
                </div>
                <Icon name="arrow" />
                <div>
                  <span>Risk invalidation</span>
                  <strong>{humanize(current.stop?.module)}</strong>
                </div>
                <Icon name="arrow" />
                <div>
                  <span>Exit</span>
                  <strong>{humanize(current.target?.module)}</strong>
                </div>
              </div>
              <div className="form-grid two">
                <Field label="Variant title">
                  <input
                    value={current.title || ""}
                    onChange={(e) => update("title", e.target.value)}
                  />
                </Field>
                <Field
                  label="How this mechanic expresses the edge"
                  hint="Describe why this causal entry, invalidation, and exit implement the hypothesis. Later variants are not designed now."
                >
                  <input
                    value={current.material_difference || ""}
                    onChange={(e) =>
                      update("material_difference", e.target.value)
                    }
                  />
                </Field>
              </div>
              {view.draft.authoring_lane === "certified_event_replay" ? (
                <div className="variant-mechanics-editor">
                  <Notice tone="warning" title="Fixed defaults and predeclared tunables">
                    A blank parameter-space field means the reviewed value is fixed. To tune a certified parameter, enter its complete comma-separated grid and include the reviewed default. Core and walk-forward analysis will use the same frozen space.
                  </Notice>
                  <div className="parameter-list">
                    {Object.entries(
                      catalog.find((item) => item.name === current.entry?.module)
                        ?.strategy_parameters || {},
                    ).map(([name, spec]: [string, any]) => (
                      <div className="governed-patch" key={name}>
                        <div className="form-grid two">
                          <Field
                            label={`${humanize(name)} · fixed value`}
                            hint={spec.description}
                          >
                            <input
                              type={["integer", "number"].includes(spec.value_type) ? "number" : "text"}
                              step={spec.value_type === "integer" ? 1 : "any"}
                              disabled={!spec.studio_editable}
                              value={String(current.entry?.params?.mechanics?.[name] ?? spec.default)}
                              onChange={(event) =>
                                updateEventParam(
                                  name,
                                  parseCertifiedParameterValue(event.target.value, spec.value_type),
                                )
                              }
                            />
                          </Field>
                          <Field
                            label="Optimization values"
                            hint={
                              spec.tunable
                                ? `Leave blank to keep fixed. Budget category: ${humanize(spec.category)}.`
                                : "Locked fixed by the certified implementation contract."
                            }
                          >
                            <input
                              disabled={!spec.tunable}
                              placeholder={spec.tunable ? "e.g. 250, 300, 400" : "fixed"}
                              value={eventGridDrafts[`${current.variant_id}:${name}`] || ""}
                              onChange={(event) => {
                                setEventGridDrafts((old) => ({
                                  ...old,
                                  [`${current.variant_id}:${name}`]: event.target.value,
                                }));
                                update("confirmed", false);
                              }}
                            />
                          </Field>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
              <div className="variant-mechanics-editor">
                <div className="form-grid two">
                  <Field label="Stop-loss mechanic">
                    <select
                      value={current.stop?.module || "points_from_entry"}
                      onChange={(event) =>
                        updateBinding(
                          "stop",
                          defaultBinding(
                            "stop",
                            event.target.value,
                            view.draft,
                          ),
                        )
                      }
                    >
                      <option value="points_from_entry">
                        Points from entry
                      </option>
                      <option value="percent_from_entry">
                        Percent from entry
                      </option>
                      <option value="fixed_dollar_per_contract">
                        Fixed dollars per contract
                      </option>
                    </select>
                  </Field>
                  <Field label="Target / exit mechanic">
                    <select
                      value={current.target?.module || "fixed_r"}
                      onChange={(event) =>
                        updateBinding(
                          "target",
                          defaultBinding(
                            "target",
                            event.target.value,
                            view.draft,
                          ),
                        )
                      }
                    >
                      <option value="fixed_r">Fixed R multiple</option>
                      <option value="cost_adjusted_fixed_r">
                        Cost-adjusted fixed R
                      </option>
                    </select>
                  </Field>
                </div>
                <div className="form-grid two">
                  <BindingParameters
                    title="Stop settings"
                    binding={current.stop}
                    onChange={(binding) => updateBinding("stop", binding)}
                  />
                  <BindingParameters
                    title="Target settings"
                    binding={current.target}
                    onChange={(binding) => updateBinding("target", binding)}
                  />
                </div>
                <small className="parameter-note">
                  Changing a mechanic or fixed value clears this variant’s
                  confirmation. Advanced parameter grids remain predeclared and
                  are validated on save.
                </small>
              </div>
              )}
              <Field label="Why these mechanics express the edge">
                <textarea
                  rows={3}
                  value={current.mechanic_rationale || ""}
                  onChange={(e) => update("mechanic_rationale", e.target.value)}
                />
              </Field>
              <details className="advanced-settings">
                <summary>
                  Review timing, stop, target, and session rationales
                </summary>
                <div className="form-grid two">
                  <Field label="Entry timing rationale">
                    <textarea
                      rows={3}
                      value={current.entry_rationale || ""}
                      onChange={(e) =>
                        update("entry_rationale", e.target.value)
                      }
                    />
                  </Field>
                  <Field label="Stop-loss rationale">
                    <textarea
                      rows={3}
                      value={current.stop_rationale || ""}
                      onChange={(e) => update("stop_rationale", e.target.value)}
                    />
                  </Field>
                  <Field label="Target and exit rationale">
                    <textarea
                      rows={3}
                      value={current.target_rationale || ""}
                      onChange={(e) =>
                        update("target_rationale", e.target.value)
                      }
                    />
                  </Field>
                  <Field label="Timeframe and session rationale">
                    <textarea
                      rows={3}
                      value={current.timeframe_session_rationale || ""}
                      onChange={(e) =>
                        update("timeframe_session_rationale", e.target.value)
                      }
                    />
                  </Field>
                </div>
              </details>
              <label className="confirmation">
                <input
                  type="checkbox"
                  checked={Boolean(current.confirmed)}
                  onChange={(e) => update("confirmed", e.target.checked)}
                />
                <span>
                  <Icon name="check" />
                </span>
                <div>
                  <strong>
                    I confirm this mechanic before performance testing
                  </strong>
                  <small>
                    This is implementation confirmation—not profitability
                    approval.
                  </small>
                </div>
              </label>
            </Card>
          )}
        </>
      )}
      <StepFooter
        back={5}
        busy={busy}
        disabled={!allConfirmed}
        label={
          allConfirmed
            ? "Save the confirmed initial variant"
            : `${variants.filter((v) => v.confirmed).length} of 1 confirmed`
        }
        onNext={() => void save()}
      />
    </div>
  );
}

function ProtocolStep({ view, onComplete }: StepProps) {
  const draft = view.draft;
  const [frozen, setFrozen] = useState(Boolean(draft.frozen));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [published, setPublished] = useState(false);
  const navigate = useNavigate();
  const checks = [
    [
      "Source and hypothesis",
      Boolean(
        draft.sources?.length && draft.hypothesis && draft.expected_mechanism,
      ),
    ],
    ["Duplicate review", draft.duplicate_review?.conclusion === "distinct"],
    ["Governed dataset", draft.dataset?.quality_verdict === "PASS"],
    ["Execution rules", Boolean(draft.execution)],
    [
      "Certified mechanics",
      [
        "certified_recipe",
        "visual_completed_bar_rule",
        "certified_event_replay",
      ].includes(
        draft.authoring_lane,
      ),
    ],
    [
      "Initial variant confirmed",
      draft.variants?.length === 1 &&
        draft.variants.every((v: any) => v.confirmed),
    ],
  ];
  async function publish() {
    setBusy(true);
    setError("");
    try {
      if (!frozen) {
        const result = await api.freeze(view.campaign_id);
        setFrozen(true);
        onComplete(result);
      }
      await api.publish(view.campaign_id);
      setPublished(true);
      window.setTimeout(
        () => navigate(`/research/${view.campaign_id}/overview`),
        900,
      );
    } catch (reason) {
      setError(message(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <StepHeader
        number={6}
        time="5 minutes"
        title="Review and publish the frozen protocol"
        description="One action runs strict validation, freezes the exact contract, and publishes transactionally. A later data or mechanics change still requires an explicit governed follow-up."
      />
      <FormError error={error} />
      {published && (
        <Notice tone="success" title="Campaign published">
          The immutable initial-variant source tree passed preflight. Opening the
          campaign workspace…
        </Notice>
      )}
      <Card className="protocol-hero">
        <div>
          <p className="eyebrow">Falsifiable claim</p>
          <h2>{draft.title}</h2>
          <p>{draft.hypothesis}</p>
        </div>
        <div>
          <StatusBadge value={frozen ? "Frozen" : "Preflight review"} />
          <span>
            {draft.instrument} · {draft.timeframe}
          </span>
        </div>
      </Card>
      <div className="protocol-grid">
        <Card>
          <p className="eyebrow">Economic mechanism</p>
          <p>{draft.expected_mechanism}</p>
          <dl className="compact-dl">
            <div>
              <dt>Holding horizon</dt>
              <dd>{draft.holding_horizon}</dd>
            </div>
            <div>
              <dt>Data</dt>
              <dd>{humanize(draft.dataset?.dataset_id)}</dd>
            </div>
            <div>
              <dt>Mechanics</dt>
              <dd>
                {humanize(draft.certified_recipe || draft.authoring_lane)}
              </dd>
            </div>
          </dl>
        </Card>
        <Card>
          <p className="eyebrow">Execution</p>
          <dl className="compact-dl">
            <div>
              <dt>Session</dt>
              <dd>
                {draft.execution?.session_start}–{draft.execution?.session_end}
              </dd>
            </div>
            <div>
              <dt>Last entry</dt>
              <dd>{draft.execution?.latest_entry_time}</dd>
            </div>
            <div>
              <dt>Forced flat</dt>
              <dd>{draft.execution?.flatten_time}</dd>
            </div>
            <div>
              <dt>Costs</dt>
              <dd>
                ${draft.execution?.commission_per_contract} +{" "}
                {draft.execution?.slippage_ticks} ticks
              </dd>
            </div>
            <div>
              <dt>Overnight</dt>
              <dd>Prohibited</dd>
            </div>
          </dl>
        </Card>
      </div>
      <Card className="protocol-variants">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Frozen candidate set</p>
            <h2>One predeclared initial variant</h2>
          </div>
          <Link to="../6">Review variants</Link>
        </div>
        {(draft.variants || []).map((variant: any, index: number) => (
          <div className="protocol-variant" key={variant.variant_id || index}>
            <span>{variant.variant_id || `v0${index + 1}`}</span>
            <strong>{variant.title}</strong>
            <span>
              {humanize(variant.stop?.module)} →{" "}
              {humanize(variant.target?.module)}
            </span>
            <Icon name="check" />
          </div>
        ))}
      </Card>
      <Card className="preflight-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Publication preflight</p>
            <h2>All required gates</h2>
          </div>
          <span>
            {checks.filter(([, ready]) => ready).length} of {checks.length}{" "}
            ready
          </span>
        </div>
        <div className="preflight-list">
          {checks.map(([label, ready]) => (
            <div key={String(label)}>
              <span className={ready ? "check-positive" : "check-pending"}>
                <Icon name={ready ? "check" : "warning"} />
              </span>
              <strong>{label}</strong>
              <span>{ready ? "Ready" : "Needs attention"}</span>
            </div>
          ))}
        </div>
      </Card>
      {!frozen ? (
        <label className="confirmation final-confirm">
          <input
            type="checkbox"
            checked={confirm}
            onChange={(e) => setConfirm(e.target.checked)}
          />
          <span>
            <Icon name="lock" />
          </span>
          <div>
            <strong>Freeze this research protocol</strong>
            <small>
              I understand that changing data, mechanics, parameter space, or
              execution requires a new governed attempt.
            </small>
          </div>
        </label>
      ) : (
        <Notice tone="success" title="Protocol frozen">
          The strict draft and current mechanic are immutable. Publication
          rechecks duplicates, hashes, data, and campaign preflight.
        </Notice>
      )}
      <StepFooter
        back={6}
        busy={busy}
        disabled={(!frozen && !confirm) || published}
        label="Review and publish governed campaign"
        onNext={() => void publish()}
      />
    </div>
  );
}

function LockedStep({ view, step }: { view: DraftView; step: WizardStep }) {
  const first = view.steps.find((item) => !item.complete);
  return (
    <div className="page page-narrow">
      <Notice tone="warning" title={`${step.label} is locked`}>
        Complete {first?.label || "the prior steps"} first. AlphaQuest will not
        silently skip a governance gate.
      </Notice>
      <Link
        className="button button-primary"
        to={`/research/${view.campaign_id}/design/${first?.number || 1}`}
      >
        Go to next required step
      </Link>
    </div>
  );
}

interface StepProps {
  view: DraftView;
  onComplete: (result: DraftView) => void;
}
function lines(value: string): string[] {
  return value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}
function csv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
function message(reason: unknown): string {
  return reason instanceof ApiError || reason instanceof Error
    ? reason.message
    : "The governed action was rejected.";
}
function parseParameterGridValues(value: string, type: string) {
  const raw = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (raw.length < 2)
    throw new Error("Every tunable parameter needs at least two comma-separated values.");
  const parsed = raw.map((item) => {
    if (type === "integer") {
      const number = Number(item);
      if (!Number.isInteger(number)) throw new Error("Integer grids require whole numbers.");
      return number;
    }
    if (type === "number") {
      const number = Number(item);
      if (!Number.isFinite(number)) throw new Error("Numeric grids require finite numbers.");
      return number;
    }
    if (type === "boolean") {
      if (!['true', 'false'].includes(item.toLowerCase()))
        throw new Error("Boolean grids accept only true or false.");
      return item.toLowerCase() === "true";
    }
    return item;
  });
  if (new Set(parsed.map((item) => `${typeof item}:${String(item)}`)).size !== parsed.length)
    throw new Error("Parameter grid values must be unique.");
  return parsed;
}
function parseCertifiedParameterValue(value: string, type: string) {
  if (type === "integer") {
    const parsed = Number(value);
    if (!Number.isInteger(parsed)) throw new Error("This parameter requires a whole number.");
    return parsed;
  }
  if (type === "number") {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) throw new Error("This parameter requires a finite number.");
    return parsed;
  }
  if (type === "boolean") return value === "true";
  return value;
}
function shortDate(value?: string): string {
  return value ? new Date(value).toLocaleDateString() : "Not recorded";
}
function TimeField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Field label={label}>
      <input
        type="time"
        step="1"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </Field>
  );
}
function NumberField({
  label,
  value,
  onChange,
  min = 0,
  prefix,
  suffix,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  prefix?: string;
  suffix?: string;
}) {
  return (
    <Field label={label}>
      <div className="affixed-input">
        {prefix && <span>{prefix}</span>}
        <input
          type="number"
          min={min}
          step="any"
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
        />
        {suffix && <span>{suffix}</span>}
      </div>
    </Field>
  );
}
export function buildRule(value: Record<string, any>, timeframe: string) {
  const feature = {
    source: "feature",
    name: String(value.feature),
    lag: Number(value.lag),
  };
  const tunables: any[] = [];
  let primary: any;
  if (value.conditionType === "cross") {
    primary = {
      type: "cross",
      direction: value.direction,
      left: feature,
      right: {
        source: "rolling",
        feature: value.feature,
        function: value.rollingFunction,
        window: Number(value.window),
        lag: 1,
        min_periods: Number(value.window),
      },
    };
  } else if (value.conditionType === "comparison") {
    let right: any = { source: "constant", value: Number(value.threshold) };
    if (value.tuneThreshold) {
      const values = String(value.thresholdValues)
        .split(",")
        .map((item) => Number(item.trim()))
        .filter((item) => Number.isFinite(item));
      if (values.length < 8 || values.length > 20)
        throw new Error("A threshold grid requires 8–20 finite values.");
      if (new Set(values).size !== values.length)
        throw new Error("Threshold grid values must be unique.");
      if (!values.includes(Number(value.threshold)))
        throw new Error("The displayed threshold must be in its frozen grid.");
      right = { source: "tunable", name: "primary_threshold" };
      tunables.push({
        name: "primary_threshold",
        value_type: "number",
        values,
        default: Number(value.threshold),
      });
    }
    primary = {
      type: "comparison",
      operator: value.operator,
      left: feature,
      right,
    };
  } else {
    if (!(Number(value.lower) < Number(value.upper)))
      throw new Error("The lower range bound must be below the upper bound.");
    primary = {
      type: "range",
      value: feature,
      lower: { source: "constant", value: Number(value.lower) },
      upper: { source: "constant", value: Number(value.upper) },
      inclusive: Boolean(value.inclusive),
    };
  }
  const combined = combineRuleFilter(primary, value, false);
  const mirrored = combineRuleFilter(mirrorRule(primary), value, true);
  const minutes = Number(String(timeframe).replace(/m$/, ""));
  if (!String(timeframe).endsWith("m") || !Number.isFinite(minutes))
    throw new Error("Visual rules require a completed minute-bar timeframe.");
  return {
    schema: "alphaquest.bar-rule/v1",
    long_rule: value.signals === "short" ? null : combined,
    short_rule:
      value.signals === "both"
        ? mirrored
        : value.signals === "short"
          ? combined
          : null,
    tunables,
    rth_only: Boolean(value.rthOnly),
    signal_start_time: normalizeRuleTime(value.signalStartTime),
    signal_end_time: normalizeRuleTime(value.signalEndTime),
    bar_interval_minutes: minutes,
    max_trades_per_day: Number(value.maxTradesPerDay),
  };
}

function combineRuleFilter(primary: any, value: Record<string, any>, mirror: boolean) {
  if (!value.secondFilter) return primary;
  let operator = value.filterOperator;
  if (mirror) operator = operator === "gt" ? "lt" : "gt";
  return {
    type: value.booleanGroup === "any" ? "any" : "all",
    conditions: [
      primary,
      {
        type: "comparison",
        operator,
        left: { source: "feature", name: value.filterFeature, lag: 0 },
        right: { source: "constant", value: Number(value.filterThreshold) },
      },
    ],
  };
}

function mirrorRule(condition: any): any {
  const mirrored = JSON.parse(JSON.stringify(condition));
  if (mirrored.type === "cross")
    mirrored.direction = mirrored.direction === "above" ? "below" : "above";
  else if (mirrored.type === "comparison")
    mirrored.operator =
      ({ gt: "lt", gte: "lte", lt: "gt", lte: "gte" } as Record<
        string,
        string
      >)[mirrored.operator] || mirrored.operator;
  else if (mirrored.type === "range")
    return { type: "not", condition: mirrored };
  return mirrored;
}

function normalizeRuleTime(value: unknown): string {
  const text = String(value || "");
  return /^\d{2}:\d{2}$/.test(text) ? `${text}:00` : text;
}

const contextParameters = new Set([
  "tick_size",
  "tick_value",
  "commission_per_contract",
  "slippage_ticks",
  "bar_interval_minutes",
  "rth_start",
  "rth_end",
  "last_entry_time",
]);

function BindingParameters({
  title,
  binding,
  onChange,
}: {
  title: string;
  binding: any;
  onChange: (binding: any) => void;
}) {
  const editable = Object.entries(binding?.params || {}).filter(
    ([name, value]) =>
      !contextParameters.has(name) && typeof value === "number",
  );
  return (
    <fieldset className="binding-parameters">
      <legend>{title}</legend>
      {editable.length === 0 ? (
        <p>All values are bound to the frozen execution protocol.</p>
      ) : (
        editable.map(([name, value]) => (
          <NumberField
            key={name}
            label={humanize(name)}
            value={Number(value)}
            onChange={(next) =>
              onChange({
                ...binding,
                params: { ...binding.params, [name]: next },
                parameter_grid: {},
              })
            }
          />
        ))
      )}
    </fieldset>
  );
}

function defaultBinding(
  kind: "stop" | "target",
  module: string,
  draft: Record<string, any>,
) {
  const execution = draft.execution || {};
  if (kind === "stop") {
    if (module === "percent_from_entry")
      return {
        module,
        params: { stop_pct: 0.002, round_to_tick: true },
        parameter_grid: {},
      };
    if (module === "fixed_dollar_per_contract")
      return {
        module,
        params: {
          dollars_per_contract: 250,
          tick_value: execution.tick_value || 12.5,
          round_to_tick: true,
        },
        parameter_grid: {},
      };
    return {
      module: "points_from_entry",
      params: { stop_points: 10, round_to_tick: true },
      parameter_grid: {},
    };
  }
  if (module === "cost_adjusted_fixed_r")
    return {
      module,
      params: {
        target_r_multiple: 2,
        tick_size: execution.tick_size || 0.25,
        tick_value: execution.tick_value || 12.5,
        commission_per_contract: execution.commission_per_contract || 0,
        slippage_ticks: execution.slippage_ticks || 0,
        round_to_tick: true,
      },
      parameter_grid: {},
    };
  return {
    module: "fixed_r",
    params: { target_r_multiple: 2 },
    parameter_grid: {},
  };
}
