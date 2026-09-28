import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import {
  FactoryStructuredReview,
  isStructuredReviewTask,
} from "../components/FactoryStructuredReview";
import { FactoryReviewIdentity, FactoryReviewReceipt } from "../components/FactoryReviewRecord";
import { Button, Card, Notice, PageHeader, StatusBadge } from "../components/UI";
import { useStudio } from "../state";
import type {
  CodexTaskRecord,
  FactoryNextAction,
  FactoryStatus,
} from "../types";

const ACTIVE_CODEX_STATES = [
  "WAITING_FOR_CODEX",
  "RUNNING",
  "CANCEL_REQUESTED",
];

type SelectableFactoryNextAction =
  | "ABANDON_EDGE"
  | "PROPOSE_SUCCESSOR"
  | "START_NEW_RESEARCH_GENERATION"
  | "STOP_NO_FRESH_HOLDOUT";

interface RankedFactoryNextAction {
  rank: number;
  action: SelectableFactoryNextAction;
  rationale?: string;
}

function rankedNextActions(task: CodexTaskRecord | null): RankedFactoryNextAction[] {
  if (!task) return [];
  const proposalSchema = String(task.proposal?.schema || "");
  if (
    task.task_type !== "NEXT_EXPERIMENT" &&
    task.request?.task_type !== "NEXT_EXPERIMENT" &&
    proposalSchema !== "alphaquest.next-action-ranking-proposal/v1"
  ) return [];
  const recommendations = task.proposal?.recommendations;
  if (!Array.isArray(recommendations)) return [];
  const allowed = new Set<SelectableFactoryNextAction>([
    "ABANDON_EDGE",
    "PROPOSE_SUCCESSOR",
    "START_NEW_RESEARCH_GENERATION",
    "STOP_NO_FRESH_HOLDOUT",
  ]);
  return recommendations.flatMap((value) => {
    if (!value || typeof value !== "object") return [];
    const item = value as Record<string, unknown>;
    const action = String(item.action || "") as SelectableFactoryNextAction;
    const rank = Number(item.rank);
    if (!allowed.has(action) || !Number.isInteger(rank) || rank < 1) return [];
    return [{
      rank,
      action,
      rationale: typeof item.rationale === "string" ? item.rationale : undefined,
    }];
  }).sort((left, right) => left.rank - right.rank);
}

function nextFactoryAction(
  status: FactoryStatus | null,
): FactoryNextAction | null {
  return status?.next_action && typeof status.next_action !== "string"
    ? status.next_action
    : null;
}

function needsHumanReview(action: FactoryNextAction | null): boolean {
  if (!action) return false;
  if (action.requires_human_review) return true;
  const description = [
    action.kind,
    action.label,
    action.detail,
    action.blocked_reason,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return description.includes("human") &&
    (description.includes("review") || description.includes("approval"));
}

function unwrapFactoryTask(
  value: CodexTaskRecord | { task: CodexTaskRecord },
): CodexTaskRecord {
  return "task" in value ? value.task : value;
}

function isValidatedNotApplied(task: CodexTaskRecord | null | undefined) {
  return task?.proposal_validation?.status === "VALIDATED_NOT_APPLIED";
}

const stages = [
  {
    phase: "1 · Define",
    title: "Hypothesis and success contract",
    body: "Declare objectives, research sources, the economic fingerprint, and abandonment rules before P&L is visible.",
    action: "Start new research",
    href: "/research/new",
  },
  {
    phase: "2 · De-duplicate",
    title: "Economic-edge review",
    body: "Review prior campaigns and close renamed duplicates before publication can proceed.",
    action: "Open research",
    href: "/research",
  },
  {
    phase: "3 · Bind inputs",
    title: "Governed data, execution, and target accounts",
    body: "Import or select hash-verified data, realistic costs, session rules, and one or more destination-specific account profiles.",
    action: "Open data library",
    href: "/library/data",
  },
  {
    phase: "4 · Specify mechanics",
    title: "No-code rules or certified packages",
    body: "Use a bounded completed-bar rule, an existing recipe, or a currently certified event-replay strategy package.",
    action: "Open method library",
    href: "/library/methods",
  },
  {
    phase: "5 · Verify mechanics",
    title: "Deterministic evidence and human review",
    body: "Queue the fixed mechanics replay, inspect sampled trades and event transitions, annotate each sample, and approve or reject.",
    action: "Open reviews",
    href: "/reviews?type=mechanics",
  },
  {
    phase: "6 · Test",
    title: "Scientific validity + generic investment quality",
    body: "Run the repository-owned stages through acceptance. Invalid or incomplete evidence stops closed; a generic return-quality miss is recorded but does not stop later unseen-evidence tests.",
    action: "Open campaigns",
    href: "/research",
  },
  {
    phase: "7 · Assess destination",
    title: "Challenge, funded, or live-account suitability",
    body: "After scientific validity passes, replay the exact finalized result against a selected account profile, including current acquisition or replacement costs and required attestations.",
    action: "Inspect account rules",
    href: "/library/accounts",
  },
  {
    phase: "8 · Promote cautiously",
    title: "Candidate review, forward incubation, portfolio, and deployment",
    body: "Promotion requires scientific-validity PASS plus either generic-quality PASS or PASS for one named destination profile. Approval remains candidate-only and profile-scoped.",
    action: "Open candidate reviews",
    href: "/reviews?type=candidate",
  },
];

export function WorkflowPage() {
  const { data, refresh } = useStudio();
  const factoryScopeOptions = Array.from(
    new Map(
      [...data.drafts, ...data.campaigns].map((item) => [
        item.campaign_id,
        item,
      ]),
    ).values(),
  );
  const [repairing, setRepairing] = useState(false);
  const [repairMessage, setRepairMessage] = useState("");
  const [factoryStatus, setFactoryStatus] = useState<FactoryStatus | null>(null);
  const [factoryTasks, setFactoryTasks] = useState<CodexTaskRecord[]>([]);
  const [factoryBusy, setFactoryBusy] = useState(false);
  const [factoryMessage, setFactoryMessage] = useState("");
  const [factoryError, setFactoryError] = useState("");
  const [proposalReviewer, setProposalReviewer] = useState(
    data.settings?.reviewer_identity || "",
  );
  const [proposalNotes, setProposalNotes] = useState("");
  const [proposalReviewError, setProposalReviewError] = useState("");
  const [selectedProposalId, setSelectedProposalId] = useState("");
  const [pendingReviewTasks, setPendingReviewTasks] = useState<Set<string>>(() => new Set());
  const noteReviewDeliveryPending = useCallback((taskId: string) => {
    setPendingReviewTasks((current) => current.has(taskId) ? current : new Set(current).add(taskId));
  }, []);
  const [proposalSelectedAction, setProposalSelectedAction] = useState<
    SelectableFactoryNextAction | ""
  >("");
  const [factoryCampaignId, setFactoryCampaignId] = useState(
    data.drafts[0]?.campaign_id || data.campaigns[0]?.campaign_id || "",
  );
  const [validatedProposalDetail, setValidatedProposalDetail] =
    useState<CodexTaskRecord | null>(null);
  const activeJobs = data.jobs.filter((job) =>
    ["QUEUED", "RUNNING", "CANCEL_REQUESTED"].includes(job.state),
  ).length;
  const diagnostics = data.workspace?.diagnostics || {};
  const actions = data.workflow_actions || [];
  const refreshFactory = useCallback(async () => {
    try {
      const [status, rawTasks] = await Promise.all([
        api.factoryStatus(factoryCampaignId || undefined),
        api.factoryTasks(12),
      ]);
      setFactoryStatus(status);
      setFactoryTasks(Array.isArray(rawTasks) ? rawTasks : rawTasks.tasks);
      setFactoryError("");
    } catch (error) {
      setFactoryError(
        error instanceof Error ? error.message : "Codex factory status is unavailable.",
      );
    }
  }, [factoryCampaignId]);
  const refreshFactoryTasks = useCallback(async () => {
    try {
      const rawTasks = await api.factoryTasks(12);
      const tasks = Array.isArray(rawTasks) ? rawTasks : rawTasks.tasks;
      setFactoryTasks(tasks);
      setFactoryError("");
      if (!tasks.some((task) => ACTIVE_CODEX_STATES.includes(task.state))) {
        setFactoryStatus(await api.factoryStatus(factoryCampaignId || undefined));
      }
    } catch (error) {
      setFactoryError(
        error instanceof Error ? error.message : "Codex factory status is unavailable.",
      );
    }
  }, [factoryCampaignId]);
  useEffect(() => {
    if (
      factoryCampaignId &&
      factoryScopeOptions.some((item) => item.campaign_id === factoryCampaignId)
    ) {
      return;
    }
    setFactoryCampaignId(factoryScopeOptions[0]?.campaign_id || "");
  }, [
    factoryCampaignId,
    factoryScopeOptions.map((item) => item.campaign_id).join("|"),
  ]);
  useEffect(() => {
    void refreshFactory();
  }, [refreshFactory]);
  useEffect(() => {
    const configuredReviewer = data.settings?.reviewer_identity?.trim();
    if (configuredReviewer) {
      setProposalReviewer((current) => current.trim() || configuredReviewer);
    }
  }, [data.settings?.reviewer_identity]);
  const pollingTask = [factoryStatus?.active_task, ...factoryTasks].find(
    (task) => task && ACTIVE_CODEX_STATES.includes(task.state),
  );
  useEffect(() => {
    if (!pollingTask) return;
    const interval = window.setInterval(() => void refreshFactoryTasks(), 2000);
    return () => window.clearInterval(interval);
  }, [pollingTask?.task_id, pollingTask?.state, refreshFactoryTasks]);
  const availability = factoryStatus?.availability;
  const chatGptAuthenticated =
    availability?.authenticated === true &&
    availability.authentication_mode === "CHATGPT";
  const codexAvailable =
    factoryStatus?.enabled === true &&
    availability?.status === "AVAILABLE" &&
    availability.executable_available &&
    chatGptAuthenticated;
  const activeFactoryTask =
    factoryStatus?.active_task ||
    factoryTasks.find((task) => ACTIVE_CODEX_STATES.includes(task.state)) ||
    null;
  const proposalCandidates = [
    ...factoryTasks,
    factoryStatus?.latest_task,
  ].filter((task): task is CodexTaskRecord => Boolean(task));
  const reviewableProposals = proposalCandidates.filter((task, index, all) =>
    isValidatedNotApplied(task) && all.findIndex((other) => other.task_id === task.task_id) === index,
  );
  const validatedProposalSummary =
    reviewableProposals.find((task) => task.task_id === selectedProposalId) ||
    proposalCandidates.find(
      (task) =>
        isValidatedNotApplied(task) &&
        !task.proposal_disposition &&
        !task.structured_review &&
        !task.selected_action,
    ) || proposalCandidates.find((task) => isValidatedNotApplied(task)) || null;
  const rejectedProposalTask =
    proposalCandidates.find(
      (task) =>
        task.proposal_validation?.status === "REJECTED_NOT_APPLIED" &&
        !task.proposal_disposition,
    ) || null;
  useEffect(() => {
    const taskId = validatedProposalSummary?.task_id;
    setProposalNotes("");
    setProposalReviewError("");
    setProposalSelectedAction("");
    setValidatedProposalDetail(null);
    if (!taskId) {
      setValidatedProposalDetail(null);
      return;
    }
    let cancelled = false;
    void api
      .factoryTask(taskId)
      .then((rawTask) => {
        if (cancelled) return;
        const detail = unwrapFactoryTask(rawTask);
        setValidatedProposalDetail(
          isValidatedNotApplied(detail) && detail.proposal ? detail : null,
        );
      })
      .catch((error) => {
        if (cancelled) return;
        setValidatedProposalDetail(null);
        setFactoryError(
          error instanceof Error
            ? error.message
            : "The validated proposal detail is unavailable.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [validatedProposalSummary?.task_id, validatedProposalSummary?.proposal_validation?.payload_sha256,
    validatedProposalSummary?.proposal_validation?.validation_sha256]);
  const validatedProposalTask =
    validatedProposalDetail &&
    validatedProposalDetail.task_id === validatedProposalSummary?.task_id &&
    isValidatedNotApplied(validatedProposalDetail) &&
    validatedProposalDetail.proposal
      ? validatedProposalDetail
      : null;
  const proposalAlreadyDisposed = Boolean(
    validatedProposalTask?.proposal_disposition ||
      validatedProposalTask?.structured_review ||
      validatedProposalTask?.selected_action,
  );
  const selectedTerminalAction = [
    "ABANDON_EDGE",
    "STOP_NO_FRESH_HOLDOUT",
  ].includes(String(validatedProposalTask?.selected_action?.selected_action || ""));
  const terminalCompletionRequired = Boolean(
    selectedTerminalAction && !validatedProposalTask?.selected_action_completion,
  );
  const rankingActions = rankedNextActions(validatedProposalTask);
  const isNextActionRanking = rankingActions.length > 0;
  const isStructuredReview = Boolean(
    validatedProposalTask && isStructuredReviewTask(validatedProposalTask),
  );
  const proposalReviewComplete = Boolean(
    proposalReviewer.trim() &&
      proposalNotes.trim() &&
      (!isNextActionRanking || proposalSelectedAction),
  );
  const proposedNextAction = nextFactoryAction(factoryStatus);
  const humanReviewRequired = needsHumanReview(proposedNextAction);
  const noEligibleAction = proposedNextAction?.eligible === false;
  const runFactoryDisabled =
    factoryBusy ||
    !codexAvailable ||
    Boolean(factoryStatus?.paused) ||
    Boolean(activeFactoryTask) ||
    Boolean(validatedProposalTask && !proposalAlreadyDisposed) ||
    humanReviewRequired ||
    noEligibleAction;
  async function runNextFactoryStep() {
    setFactoryBusy(true);
    setFactoryError("");
    setFactoryMessage("");
    try {
      await api.runNextFactoryStep({
        request_id:
          globalThis.crypto?.randomUUID?.() || `factory-${Date.now()}`,
        ...(proposedNextAction?.campaign_id
          ? { campaign_id: proposedNextAction.campaign_id }
          : {}),
      });
      setFactoryMessage(
        "The next bounded AI task is queued. A local factory worker will process it read-only.",
      );
      await refreshFactory();
    } catch (error) {
      setFactoryError(
        error instanceof Error ? error.message : "The Codex task was not queued.",
      );
    } finally {
      setFactoryBusy(false);
    }
  }
  async function toggleFactoryPause() {
    setFactoryBusy(true);
    setFactoryError("");
    try {
      const status = factoryStatus?.paused
        ? await api.resumeFactory()
        : await api.pauseFactory();
      setFactoryStatus(
        factoryCampaignId
          ? await api.factoryStatus(factoryCampaignId)
          : status,
      );
      setFactoryMessage(
        status.paused ? "New Codex factory work is paused." : "Codex factory work resumed.",
      );
    } catch (error) {
      setFactoryError(
        error instanceof Error ? error.message : "The factory state was not changed.",
      );
    } finally {
      setFactoryBusy(false);
    }
  }
  async function cancelFactoryTask(taskId: string) {
    setFactoryBusy(true);
    setFactoryError("");
    try {
      await api.cancelFactoryTask(taskId);
      setFactoryMessage("Cancellation requested for the active Codex task.");
      await refreshFactory();
    } catch (error) {
      setFactoryError(
        error instanceof Error ? error.message : "Cancellation was not requested.",
      );
    } finally {
      setFactoryBusy(false);
    }
  }
  async function setProposalDisposition(
    taskId: string,
    disposition: "ACKNOWLEDGE" | "DISMISS",
  ) {
    const reviewer = proposalReviewer.trim();
    const notes = proposalNotes.trim();
    if (!reviewer || !notes) {
      setProposalReviewError(
        "Reviewer identity and review notes are required. No disposition was recorded.",
      );
      return;
    }
    setFactoryBusy(true);
    setFactoryError("");
    setFactoryMessage("");
    setProposalReviewError("");
    try {
      await api.setFactoryProposalDisposition(taskId, {
        disposition,
        reviewer,
        notes,
      });
      const [rawTask, status] = await Promise.all([
        api.factoryTask(taskId),
        api.factoryStatus(factoryCampaignId || undefined),
      ]);
      const refreshedTask = unwrapFactoryTask(rawTask);
      setFactoryStatus(status);
      setFactoryTasks((current) =>
        current.map((task) =>
          task.task_id === refreshedTask.task_id ? refreshedTask : task,
        ),
      );
      setValidatedProposalDetail(
        isValidatedNotApplied(refreshedTask) && refreshedTask.proposal
          ? refreshedTask
          : null,
      );
      setProposalNotes("");
      setFactoryMessage(
        disposition === "ACKNOWLEDGE"
          ? "Proposal acknowledged for human transfer. It was not applied and no approval was granted."
          : "Proposal dismissed. It was not applied and no approval was granted.",
      );
    } catch (error) {
      setProposalReviewError(
        error instanceof Error
          ? error.message
          : "The proposal disposition was not recorded.",
      );
    } finally {
      setFactoryBusy(false);
    }
  }
  async function setSelectedNextAction(taskId: string) {
    const reviewer = proposalReviewer.trim();
    const notes = proposalNotes.trim();
    if (!reviewer || !notes || !proposalSelectedAction) {
      setProposalReviewError(
        "Select one ranked action and enter reviewer identity plus review notes. No action was recorded.",
      );
      return;
    }
    setFactoryBusy(true);
    setFactoryError("");
    setFactoryMessage("");
    setProposalReviewError("");
    try {
      await api.setFactorySelectedAction(taskId, {
        selected_action: proposalSelectedAction,
        reviewer,
        notes,
      });
      const [rawTask, status] = await Promise.all([
        api.factoryTask(taskId),
        api.factoryStatus(factoryCampaignId || undefined),
      ]);
      const refreshedTask = unwrapFactoryTask(rawTask);
      setFactoryStatus(status);
      setFactoryTasks((current) =>
        current.map((task) =>
          task.task_id === refreshedTask.task_id ? refreshedTask : task,
        ),
      );
      setValidatedProposalDetail(
        isValidatedNotApplied(refreshedTask) && refreshedTask.proposal
          ? refreshedTask
          : null,
      );
      setProposalNotes("");
      setFactoryMessage(
        `${proposalSelectedAction} was recorded as an immutable routing choice. Nothing was applied and no approval was granted.`,
      );
    } catch (error) {
      setProposalReviewError(
        error instanceof Error
          ? error.message
          : "The selected next action was not recorded.",
      );
    } finally {
      setFactoryBusy(false);
    }
  }
  async function completeSelectedTerminalAction(taskId: string) {
    const reviewer = proposalReviewer.trim();
    const notes = proposalNotes.trim();
    if (!reviewer || !notes) {
      setProposalReviewError(
        "Reviewer identity and terminal-decision notes are required. No completion was recorded.",
      );
      return;
    }
    setFactoryBusy(true);
    setFactoryError("");
    setFactoryMessage("");
    setProposalReviewError("");
    try {
      await api.completeFactorySelectedAction(taskId, { reviewer, notes });
      const [rawTask, status] = await Promise.all([
        api.factoryTask(taskId),
        api.factoryStatus(factoryCampaignId || undefined),
      ]);
      const refreshedTask = unwrapFactoryTask(rawTask);
      setFactoryStatus(status);
      setFactoryTasks((current) =>
        current.map((task) =>
          task.task_id === refreshedTask.task_id ? refreshedTask : task,
        ),
      );
      setValidatedProposalDetail(refreshedTask);
      setProposalNotes("");
      setFactoryMessage(
        "The terminal human decision was recorded separately from selection. No proposal was applied, no approval was granted, and the scientific verdict was unchanged.",
      );
    } catch (error) {
      setProposalReviewError(
        error instanceof Error
          ? error.message
          : "The terminal selected-action completion was not recorded.",
      );
    } finally {
      setFactoryBusy(false);
    }
  }
  async function completeStructuredReview(taskId: string, message: string) {
    const [rawTask, status, rawTasks] = await Promise.all([
      api.factoryTask(taskId),
      api.factoryStatus(factoryCampaignId || undefined),
      api.factoryTasks(12),
    ]);
    const refreshedTask = unwrapFactoryTask(rawTask);
    setFactoryStatus(status);
    setFactoryTasks(Array.isArray(rawTasks) ? rawTasks : rawTasks.tasks);
    setValidatedProposalDetail(refreshedTask);
    setSelectedProposalId(taskId);
    setProposalNotes("");
    setFactoryMessage(message);
    setProposalReviewError("");
  }
  async function repairDerivedViews() {
    setRepairing(true);
    setRepairMessage("");
    try {
      await api.repairDerivedViews();
      await refresh();
      setRepairMessage("Derived registry, exports, and views rebuilt. Source evidence was not changed.");
    } catch (error) {
      setRepairMessage(error instanceof Error ? error.message : "Derived-view repair failed.");
    } finally {
      setRepairing(false);
    }
  }
  return (
    <div className="page">
      <PageHeader
        eyebrow="End-to-end control center"
        title="Run governed research from Studio"
        description="Every routine researcher action links to its browser workflow. Each mutation still passes the same backend validation, hashes, immutable lineage, and manual gates as the command-line path."
      />
      <div className="workflow-summary metrics-grid">
        <Card><span>Drafts</span><strong>{data.drafts.length}</strong></Card>
        <Card><span>Campaigns</span><strong>{data.campaigns.length}</strong></Card>
        <Card><span>Reviews waiting</span><strong>{data.reviews.length}</strong></Card>
        <Card><span>Active jobs</span><strong>{activeJobs}</strong></Card>
      </div>
      <Card className="workflow-health-card codex-factory-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Subscription-backed research assistant</p>
            <h2>Codex research factory</h2>
          </div>
          <StatusBadge
            value={
              activeFactoryTask?.state ||
              factoryStatus?.factory_state ||
              availability?.status ||
              "Checking"
            }
          />
        </div>
        <p>
          Queue one bounded proposal at a time through the locally installed,
          ChatGPT-authenticated Codex CLI. Codex runs read-only; AlphaQuest keeps
          state, hashes, test policy, verdicts, and every human approval gate.
        </p>
        {factoryScopeOptions.length > 0 && (
          <label className="field factory-scope-field">
            <span className="field-label">Factory campaign scope</span>
            <select
              value={factoryCampaignId}
              disabled={factoryBusy || Boolean(activeFactoryTask)}
              onChange={(event) => {
                setFactoryCampaignId(event.target.value);
                setFactoryMessage("");
                setFactoryError("");
              }}
            >
              {factoryScopeOptions.map((item) => (
                <option key={item.campaign_id} value={item.campaign_id}>
                  {item.title || item.campaign_id} · {item.campaign_id}
                </option>
              ))}
            </select>
            <small>
              Select the exact mutable draft or governed published campaign before queueing.
            </small>
          </label>
        )}
        {availability?.detail && <p>{availability.detail}</p>}
        {proposedNextAction && (
          <div className="ai-key-status">
            <div>
              <span>Next eligible AI step</span>
              <strong>
                {proposedNextAction.label ||
                  proposedNextAction.task_type ||
                  proposedNextAction.kind ||
                  "Factory proposal"}
              </strong>
            </div>
            <p>
              {proposedNextAction.detail ||
                proposedNextAction.blocked_reason ||
                "AlphaQuest will build and hash the permitted context before queueing."}
            </p>
          </div>
        )}
        {activeFactoryTask && (
          <div className="ai-key-status">
            <div>
              <span>Active task</span>
              <StatusBadge value={activeFactoryTask.state} />
            </div>
            <p>
              {activeFactoryTask.request?.task_type || activeFactoryTask.task_id}
            </p>
          </div>
        )}
        {reviewableProposals.length > 0 && (
          <label className="field">
            <span className="field-label">Recent proposals and saved reviews</span>
            <select value={validatedProposalSummary?.task_id || ""} onChange={(event) => setSelectedProposalId(event.target.value)}>
              {reviewableProposals.map((task) => <option key={task.task_id} value={task.task_id}>
                {task.task_type || "Proposal"} · {task.task_id} · {task.structured_review?.status || task.proposal_disposition?.status || "Pending review"}
              </option>)}
            </select>
          </label>
        )}
        {validatedProposalTask && (
          <section className="factory-proposal-review" aria-labelledby="factory-proposal-heading">
            <div className="section-heading">
              <div>
                <p className="eyebrow">Validated proposal · human transfer required</p>
                <h3 id="factory-proposal-heading">Review Codex output</h3>
              </div>
              <StatusBadge value="VALIDATED_NOT_APPLIED" />
            </div>
            <Notice tone="warning" title="Proposal only — not applied or approved">
              AlphaQuest validated this output against its expected schema and
              bound context hashes. It has not changed a draft or campaign, and
              it does not grant mechanics approval, certification, candidate
              promotion, or deployment authority.
            </Notice>
            <div className="factory-proposal-meta">
              <span>
                <strong>Task</strong> {validatedProposalTask.task_id}
              </span>
              <span>
                <strong>Type</strong>{" "}
                {validatedProposalTask.task_type ||
                  validatedProposalTask.request?.task_type ||
                  "Proposal"}
              </span>
              {validatedProposalTask.campaign_id && (
                <span>
                  <strong>Campaign</strong> {validatedProposalTask.campaign_id}
                </span>
              )}
            </div>
            {isStructuredReview && <>
              <Notice tone="info" title="Review in three steps">
                Read the proposed values, complete each evidence check, then submit one explicit decision with your notes.
                Leave the review pending if evidence is missing. Dismiss only when you intend to close this proposal.
                Reviewer identity is a local attribution label, not an authenticated signature.
              </Notice>
              <FactoryReviewIdentity task={validatedProposalTask} />
            </>}
            <details className="factory-proposal-payload">
              <summary>Inspect validated proposal</summary>
              <pre>{JSON.stringify(validatedProposalTask.proposal, null, 2)}</pre>
            </details>
            {proposalAlreadyDisposed ? (
              <>
                <Notice tone="info" title="Human routing record already stored">
                  {validatedProposalTask.selected_action?.selected_action
                    ? `Selected action: ${validatedProposalTask.selected_action.selected_action}.`
                    : validatedProposalTask.structured_review?.status ||
                      validatedProposalTask.proposal_disposition?.status ||
                      "This proposal has left the pending review queue."}{" "}
                  {validatedProposalTask.structured_review
                    ? "Campaign publication and mechanics approval remain separate."
                    : "It remains not applied and not approved."}
                  {(validatedProposalTask.selected_action?.reviewer ||
                    validatedProposalTask.structured_review?.reviewer ||
                    validatedProposalTask.proposal_disposition?.reviewer) && (
                    <>
                      {" "}Recorded by{" "}
                      {validatedProposalTask.selected_action?.reviewer ||
                        validatedProposalTask.structured_review?.reviewer ||
                        validatedProposalTask.proposal_disposition?.reviewer}.
                    </>
                  )}
                </Notice>
                <FactoryReviewReceipt task={validatedProposalTask} />
                {terminalCompletionRequired && (
                  <div className="factory-proposal-disposition">
                    <Notice tone="warning" title="Terminal decision still requires completion">
                      Selection proves the chosen branch only. Record a separate
                      immutable terminal decision bound to the predecessor result,
                      approval, budget, and information ledger.
                    </Notice>
                    <label className="field">
                      <span className="field-label">Terminal decision reviewer</span>
                      <input
                        value={proposalReviewer}
                        onChange={(event) => {
                          setProposalReviewer(event.target.value);
                          setProposalReviewError("");
                        }}
                        autoComplete="name"
                      />
                    </label>
                    <label className="field">
                      <span className="field-label">Terminal decision notes</span>
                      <textarea
                        rows={4}
                        value={proposalNotes}
                        onChange={(event) => {
                          setProposalNotes(event.target.value);
                          setProposalReviewError("");
                        }}
                        placeholder="State why this edge or exhausted generation is now closed."
                      />
                    </label>
                    {proposalReviewError && (
                      <Notice tone="warning">{proposalReviewError}</Notice>
                    )}
                    <Button
                      type="button"
                      disabled={
                        factoryBusy ||
                        !proposalReviewer.trim() ||
                        !proposalNotes.trim()
                      }
                      onClick={() =>
                        void completeSelectedTerminalAction(
                          validatedProposalTask.task_id,
                        )
                      }
                    >
                      RECORD TERMINAL DECISION COMPLETION
                    </Button>
                  </div>
                )}
                {validatedProposalTask.selected_action_completion && (
                  <Notice tone="success" title="Terminal human action completed">
                    {validatedProposalTask.selected_action_completion.terminal_status ||
                      "The terminal decision is complete."}{" "}
                    The scientific verdict remains unchanged.
                  </Notice>
                )}
              </>
            ) : (
              <div className="factory-proposal-disposition">
                <label className="field">
                  <span className="field-label">Reviewer identity</span>
                  <input
                    value={proposalReviewer}
                    onChange={(event) => {
                      setProposalReviewer(event.target.value);
                      setProposalReviewError("");
                    }}
                    placeholder="Set a reviewer identity in Settings or enter one here"
                    autoComplete="name"
                  />
                  <small>
                    The configured Studio reviewer identity is used when available.
                  </small>
                </label>
                {isNextActionRanking && (
                  <label className="field">
                    <span className="field-label">Selected governed next action</span>
                    <select
                      value={proposalSelectedAction}
                      onChange={(event) => {
                        setProposalSelectedAction(
                          event.target.value as SelectableFactoryNextAction | "",
                        );
                        setProposalReviewError("");
                      }}
                    >
                      <option value="">Choose one ranked eligible action</option>
                      {rankingActions.map((item) => (
                        <option key={item.action} value={item.action}>
                          {item.rank}. {item.action}
                        </option>
                      ))}
                    </select>
                    <small>
                      This choice is hash-bound to the deterministic eligibility
                      allow-list and Codex ranking. It routes work only; it does not
                      apply mechanics or grant approval.
                    </small>
                  </label>
                )}
                <label className="field">
                  <span className="field-label">Required review notes</span>
                  <textarea
                    rows={4}
                    value={proposalNotes}
                    onChange={(event) => {
                      setProposalNotes(event.target.value);
                      setProposalReviewError("");
                    }}
                    placeholder="Record what was reviewed and what the governed human workflow must verify next."
                  />
                </label>
                {!isStructuredReview && !proposalReviewComplete && (
                  <p className="factory-proposal-requirement">
                    Reviewer identity and non-empty notes are required before
                    either action is enabled.
                  </p>
                )}
                {proposalReviewError && (
                  <Notice tone="warning">{proposalReviewError}</Notice>
                )}
                {isStructuredReview && validatedProposalTask && (
                  <FactoryStructuredReview
                    task={validatedProposalTask}
                    reviewer={proposalReviewer}
                    notes={proposalNotes}
                    disabled={factoryBusy}
                    onDeliveryPending={noteReviewDeliveryPending}
                    onComplete={(message) =>
                      completeStructuredReview(validatedProposalTask.task_id, message)
                    }
                  />
                )}
                <div className="key-actions">
                  {!isStructuredReview && (
                    <Button
                      type="button"
                      disabled={factoryBusy || !proposalReviewComplete}
                      onClick={() =>
                        void (isNextActionRanking
                          ? setSelectedNextAction(validatedProposalTask.task_id)
                          : setProposalDisposition(
                              validatedProposalTask.task_id,
                              "ACKNOWLEDGE",
                            ))
                      }
                    >
                      {isNextActionRanking
                        ? "RECORD SELECTED ACTION"
                        : "ACKNOWLEDGE FOR HUMAN TRANSFER"}
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={factoryBusy || !proposalReviewComplete ||
                      Boolean(validatedProposalTask.review_delivery) || pendingReviewTasks.has(validatedProposalTask.task_id)}
                    onClick={() =>
                      void setProposalDisposition(
                        validatedProposalTask.task_id,
                        "DISMISS",
                      )
                    }
                  >
                    DISMISS
                  </Button>
                </div>
              </div>
            )}
          </section>
        )}
        {rejectedProposalTask && (
          <section
            className="factory-proposal-review"
            aria-labelledby="factory-invalid-proposal-heading"
          >
            <div className="section-heading">
              <div>
                <p className="eyebrow">Rejected AI output · no content is trusted</p>
                <h3 id="factory-invalid-proposal-heading">Dismiss invalid output</h3>
              </div>
              <StatusBadge value="REJECTED_NOT_APPLIED" />
            </div>
            <Notice tone="warning" title="Validation failed closed">
              {rejectedProposalTask.proposal_validation?.error ||
                "The output failed schema, semantic, staleness, or integrity validation."}{" "}
              Its raw payload is hidden, was not applied, and cannot be acknowledged.
            </Notice>
            <label className="field">
              <span className="field-label">Reviewer identity</span>
              <input
                value={proposalReviewer}
                onChange={(event) => {
                  setProposalReviewer(event.target.value);
                  setProposalReviewError("");
                }}
                autoComplete="name"
              />
            </label>
            <label className="field">
              <span className="field-label">Required dismissal notes</span>
              <textarea
                rows={3}
                value={proposalNotes}
                onChange={(event) => {
                  setProposalNotes(event.target.value);
                  setProposalReviewError("");
                }}
                placeholder="Record why this invalid output is being closed before a bounded retry."
              />
            </label>
            {proposalReviewError && <Notice tone="warning">{proposalReviewError}</Notice>}
            <Button
              type="button"
              variant="secondary"
              disabled={factoryBusy || !proposalReviewComplete}
              onClick={() =>
                void setProposalDisposition(rejectedProposalTask.task_id, "DISMISS")
              }
            >
              DISMISS INVALID OUTPUT
            </Button>
          </section>
        )}
        {humanReviewRequired && (
          <Notice tone="warning" title="Human gate is next">
            Complete the required review or approval in Studio before asking
            Codex for another research proposal.
          </Notice>
        )}
        {!factoryError && availability?.authentication_mode === "API_KEY" && (
          <Notice tone="warning" title="Subscription login required">
            This factory refuses API-key authentication. Run the local Codex
            login flow using your ChatGPT subscription, then refresh this page.
          </Notice>
        )}
        {factoryError && <Notice tone="warning">{factoryError}</Notice>}
        {factoryMessage && <Notice tone="success">{factoryMessage}</Notice>}
        <div className="key-actions">
          <Button
            type="button"
            disabled={runFactoryDisabled}
            onClick={() => void runNextFactoryStep()}
          >
            {factoryBusy ? "Queueing…" : "Run next AI step"}
          </Button>
          {activeFactoryTask && (
            <Button
              type="button"
              variant="secondary"
              disabled={factoryBusy || activeFactoryTask.state === "CANCEL_REQUESTED"}
              onClick={() => void cancelFactoryTask(activeFactoryTask.task_id)}
            >
              Cancel task
            </Button>
          )}
          {factoryStatus && (
            <Button
              type="button"
              variant="secondary"
              disabled={factoryBusy || Boolean(activeFactoryTask)}
              onClick={() => void toggleFactoryPause()}
            >
              {factoryStatus.paused ? "Resume factory" : "Pause factory"}
            </Button>
          )}
        </div>
      </Card>
      <section>
        <div className="section-heading">
          <div>
            <p className="eyebrow">Global next-required-action queue</p>
            <h2>Do these in order</h2>
          </div>
          <Link to="/research">View all research</Link>
        </div>
        {actions.length ? (
          <div className="workflow-action-list">
            {actions.slice(0, 12).map((action) => (
              <Card key={`${action.kind}:${action.campaign_id}:${action.label}`}>
                <div className="card-kicker">
                  <StatusBadge value={action.kind} />
                  <span>{action.campaign_id || "Workspace"}</span>
                </div>
                <h3>{action.label}</h3>
                <p>{action.detail}</p>
                <Link className="button button-secondary" to={action.href}>Open required action</Link>
              </Card>
            ))}
          </div>
        ) : (
          <Notice tone="success">No blocked jobs, human reviews, active campaign actions, or unfinished drafts are waiting.</Notice>
        )}
      </section>
      <Card className="workflow-health-card">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Registry and artifact health</p>
            <h2>{diagnostics.status || "Checking workspace"}</h2>
          </div>
          <Button variant="secondary" disabled={repairing} onClick={() => void repairDerivedViews()}>
            {repairing ? "Rebuilding…" : "Rebuild derived views"}
          </Button>
        </div>
        <div className="workflow-health-checks">
          {(diagnostics.checks || []).map((check: any) => (
            <div key={check.id}>
              <span>{check.label}</span>
              <StatusBadge value={check.status} />
            </div>
          ))}
        </div>
        {repairMessage && <Notice tone={repairMessage.includes("rebuilt") ? "success" : "warning"}>{repairMessage}</Notice>}
      </Card>
      <div className="workflow-policy-grid">
        <Card>
          <p className="eyebrow">Deterministic cache boundary</p>
          <h3>Exact-input precompute only</h3>
          <p>{diagnostics.cache_policy?.note}</p>
          <StatusBadge value={diagnostics.cache_policy?.cross_attempt_result_cache || "DISABLED"} />
        </Card>
        <Card>
          <p className="eyebrow">Legacy-interface parity gate</p>
          <h3>Retain until independently proven</h3>
          <p>{diagnostics.legacy_parity?.remaining_gate}</p>
          <StatusBadge value={diagnostics.legacy_parity?.decision || "RETAIN"} />
        </Card>
      </div>
      <Notice tone="info" title="Intentional engineering boundary">
        New arbitrary Python strategy logic still requires a durable engineering handoff, repository tests, and a versioned certification manifest. Studio can run the declared certification suite and publish a fresh immutable certification identity, but it cannot accept or execute pasted code.
      </Notice>
      <div className="workflow-stage-grid">
        {stages.map((stage) => (
          <Card className="workflow-stage-card" key={stage.phase}>
            <div className="card-kicker">
              <p className="eyebrow">{stage.phase}</p>
              <StatusBadge value="Available in Studio" />
            </div>
            <h2>{stage.title}</h2>
            <p>{stage.body}</p>
            <Link className="button button-secondary" to={stage.href}>
              {stage.action}
            </Link>
          </Card>
        ))}
      </div>
      <Notice tone="warning" title="Policy is visible, not editable per strategy">
        Stage order, time windows, random seeds, run counts, objectives, and pass/fail gates remain repository-owned. A campaign may set stricter pre-PnL objectives, but Studio never offers controls that weaken the shared methodology.
      </Notice>
    </div>
  );
}
