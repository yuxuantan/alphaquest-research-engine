import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FactoryStatus } from "../types";

const mocks = vi.hoisted(() => ({
  factoryStatus: vi.fn(),
  factoryTasks: vi.fn(),
  factoryTask: vi.fn(),
  runNextFactoryStep: vi.fn(),
  cancelFactoryTask: vi.fn(),
  setFactoryProposalDisposition: vi.fn(),
  setFactorySelectedAction: vi.fn(),
  completeFactorySelectedAction: vi.fn(),
  recordFactoryReviewedSource: vi.fn(),
  factorySourceReviewReadiness: vi.fn(),
  recordFactoryReviewedHypothesis: vi.fn(),
  recordFactoryReviewedEngineeringIntent: vi.fn(),
  pauseFactory: vi.fn(),
  resumeFactory: vi.fn(),
  repairDerivedViews: vi.fn(),
  settings: vi.fn(),
  saveSettings: vi.fn(),
  aiStatus: vi.fn(),
  saveAiKey: vi.fn(),
  removeAiKey: vi.fn(),
}));

vi.mock("../api", () => ({ api: mocks }));
vi.mock("../state", () => ({
  useStudio: () => ({
    refresh: vi.fn(),
    data: {
      drafts: [
        {
          campaign_id: "factory_example",
          title: "Factory example draft",
        },
      ],
      campaigns: [
        {
          campaign_id: "published_example",
          title: "Published example campaign",
        },
      ],
      reviews: [],
      jobs: [],
      workflow_actions: [],
      workspace: { diagnostics: { checks: [] } },
      settings: {
        assistant_mode: "codex_subscription",
        reviewer_identity: "Configured Reviewer",
      },
    },
  }),
}));

import { SettingsPage } from "./SettingsPage";
import { WorkflowPage } from "./WorkflowPage";

function status(
  overrides: Partial<FactoryStatus> = {},
): FactoryStatus {
  return {
    enabled: true,
    paused: false,
    availability: {
      status: "AVAILABLE",
      executable_available: true,
      authenticated: true,
      authentication_mode: "CHATGPT",
      detail: "Logged in using ChatGPT",
    },
    next_action: {
      kind: "SOURCE_EVIDENCE",
      label: "Propose source evidence",
      campaign_id: "factory_example",
      eligible: true,
    },
    ...overrides,
  };
}

beforeEach(() => {
  localStorage.clear();
  vi.resetAllMocks();
  mocks.factoryStatus.mockResolvedValue(status());
  mocks.factoryTasks.mockResolvedValue({ tasks: [] });
  mocks.runNextFactoryStep.mockResolvedValue({
    task: { task_id: "codex-1", state: "WAITING_FOR_CODEX" },
  });
  mocks.setFactoryProposalDisposition.mockResolvedValue({ task: {} });
  mocks.setFactorySelectedAction.mockResolvedValue({ task: {} });
  mocks.completeFactorySelectedAction.mockResolvedValue({ task: {} });
  mocks.recordFactoryReviewedSource.mockResolvedValue({ reviewed_artifact: {} });
  mocks.factorySourceReviewReadiness.mockResolvedValue({
    status: "READY", eligible_capture_count: 1, options: [{
      capture_id: "capture.source", capture_revision_sha256: "c".repeat(64),
      source_version_id: "version.source", status: "FULL_TEXT_CAPTURED",
      content_sha256: "a".repeat(64), retrieval_locator: "https://example.test/source",
      readiness: "READY", issues: [], title: "Captured source", authors: ["Researcher"],
      source_category: "ACADEMIC", version_kind: "ORIGINAL", version_label: "Published version",
    }],
  });
  mocks.recordFactoryReviewedHypothesis.mockResolvedValue({ reviewed_artifact: {} });
  mocks.recordFactoryReviewedEngineeringIntent.mockResolvedValue({ reviewed_artifact: {} });
});

afterEach(() => { cleanup(); localStorage.clear(); });

describe("Codex research factory UI", () => {
  it("lets the researcher select an exact factory campaign scope", async () => {
    render(
      <MemoryRouter>
        <WorkflowPage />
      </MemoryRouter>,
    );

    const scope = await screen.findByRole("combobox", {
      name: /Factory campaign scope/i,
    });
    expect(scope).toHaveValue("factory_example");
    fireEvent.change(scope, { target: { value: "published_example" } });

    await waitFor(() =>
      expect(mocks.factoryStatus).toHaveBeenCalledWith("published_example"),
    );
  });

  it("stops at a required human review", async () => {
    mocks.factoryStatus.mockResolvedValue(
      status({
        next_action: {
          kind: "MECHANICS_REVIEW",
          label: "Human mechanics review",
          requires_human_review: true,
          eligible: false,
        },
      }),
    );

    render(
      <MemoryRouter>
        <WorkflowPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Codex research factory")).toBeVisible();
    expect(screen.getByText("Human gate is next")).toBeVisible();
    expect(screen.getByRole("button", { name: "Run next AI step" })).toBeDisabled();
  });

  it("queues only the next controller-selected task", async () => {
    render(
      <MemoryRouter>
        <WorkflowPage />
      </MemoryRouter>,
    );

    const button = await screen.findByRole("button", {
      name: "Run next AI step",
    });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);

    await waitFor(() =>
      expect(mocks.runNextFactoryStep).toHaveBeenCalledWith({
        request_id: expect.any(String),
        campaign_id: "factory_example",
      }),
    );
    expect(
      await screen.findByText(/next bounded AI task is queued/i),
    ).toBeVisible();
  });

  it("uses subscription-backed Codex settings without requesting a credential", async () => {
    mocks.settings.mockResolvedValue({
      assistant_mode: "codex_subscription",
      codex_timeout_seconds: 1800,
      codex_max_runs_per_day: 12,
    });

    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(/Codex is authenticated through ChatGPT/i),
    ).toBeVisible();
    expect(screen.queryByLabelText("OpenAI API key")).not.toBeInTheDocument();
    expect(mocks.aiStatus).not.toHaveBeenCalled();
  });

  it("shows a generic validated mechanics proposal and records an explicit human transfer", async () => {
    const proposalTask = {
      task_id: "codex-proposal-1",
      state: "PROPOSAL_READY",
      task_type: "MECHANICS_INTENT",
      campaign_id: "factory_example",
      proposal_validation: { status: "VALIDATED_NOT_APPLIED", proposal_id: "proposal-1", payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64) },
      proposal: {
        schema: "alphaquest.mechanics-intent/v1",
        execution_lane: "CERTIFIED_RECIPE",
      },
      proposal_disposition: null,
      applied: false,
      approved: false,
    };
    const proposalSummary = {
      task_id: proposalTask.task_id,
      state: proposalTask.state,
      task_type: proposalTask.task_type,
      campaign_id: proposalTask.campaign_id,
      proposal_validation: proposalTask.proposal_validation,
      proposal_disposition: proposalTask.proposal_disposition,
      applied: false,
      approved: false,
    };
    mocks.factoryStatus.mockResolvedValue(
      status({ latest_task: proposalSummary }),
    );
    mocks.factoryTask
      .mockResolvedValueOnce({ task: proposalTask })
      .mockResolvedValueOnce({
        task: {
          ...proposalTask,
          proposal_disposition: {
            status: "ACKNOWLEDGED_FOR_HUMAN_REVIEW",
            reviewer: "Configured Reviewer",
            notes: "Verify every source before governed authoring.",
            campaign_mutations_performed: false,
            approval_granted: false,
          },
        },
      });

    render(
      <MemoryRouter>
        <WorkflowPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("Proposal only — not applied or approved"),
    ).toBeVisible();
    expect(screen.getByText(/mechanics approval/i)).toBeVisible();
    const acknowledge = screen.getByRole("button", {
      name: "ACKNOWLEDGE FOR HUMAN TRANSFER",
    });
    const dismiss = screen.getByRole("button", { name: "DISMISS" });
    expect(acknowledge).toBeDisabled();
    expect(dismiss).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Required review notes"), {
      target: { value: "Verify every source before governed authoring." },
    });
    await waitFor(() => expect(acknowledge).toBeEnabled());
    fireEvent.change(screen.getByLabelText(/Reviewer identity/), {
      target: { value: "" },
    });
    expect(acknowledge).toBeDisabled();
    expect(dismiss).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/Reviewer identity/), {
      target: { value: "Configured Reviewer" },
    });
    await waitFor(() => expect(acknowledge).toBeEnabled());
    fireEvent.click(acknowledge);

    await waitFor(() =>
      expect(mocks.setFactoryProposalDisposition).toHaveBeenCalledWith(
        "codex-proposal-1",
        {
          disposition: "ACKNOWLEDGE",
          reviewer: "Configured Reviewer",
          notes: "Verify every source before governed authoring.",
        },
      ),
    );
    await waitFor(() =>
      expect(mocks.factoryTask).toHaveBeenCalledWith("codex-proposal-1"),
    );
    expect(
      await screen.findByText(/acknowledged for human transfer/i),
    ).toBeVisible();
    expect(screen.getByText(/no approval was granted/i)).toBeVisible();
  });

  it("records source verification only after hashes and every claim decision are complete", async () => {
    const proposalTask = {
      task_id: "codex-source-review",
      state: "PROPOSAL_READY",
      task_type: "SOURCE_RESEARCH",
      campaign_id: "factory_example",
      proposal_validation: { status: "VALIDATED_NOT_APPLIED", proposal_id: "proposal-1", payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64) },
      proposal: {
        schema: "alphaquest.source-evidence-bundle/v1",
        claims: [
          {
            claim_id: "claim_1",
            statement: "The captured exchange source directly supports this narrow descriptive claim.",
            source_location: "page 7",
            support: "DIRECT",
          },
        ],
      },
      proposal_disposition: null,
      structured_review: null,
    };
    const summary = {
      ...proposalTask,
      proposal: undefined,
    };
    mocks.factoryStatus.mockResolvedValue(status({ latest_task: summary }));
    mocks.factoryTask
      .mockResolvedValueOnce({ task: proposalTask })
      .mockResolvedValueOnce({
        task: {
          ...proposalTask,
          structured_review: {
            status: "ACCEPTED_FOR_HYPOTHESIS",
            reviewer: "Configured Reviewer",
          },
        },
      });

    render(<MemoryRouter><WorkflowPage /></MemoryRouter>);

    const submit = await screen.findByRole("button", {
      name: "ACCEPT REVIEWED SOURCE EVIDENCE",
    });
    expect(screen.queryByRole("button", { name: "ACKNOWLEDGE FOR HUMAN TRANSFER" }))
      .not.toBeInTheDocument();
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Required review notes"), {
      target: { value: "Checked the original source and every claim." },
    });
    await waitFor(() => expect(screen.getByLabelText("Captured source content SHA-256")).toHaveValue("a".repeat(64)));
    fireEvent.change(screen.getByLabelText("Human verification method"), {
      target: { value: "Opened the publisher PDF and checked its metadata." },
    });
    fireEvent.change(screen.getByLabelText("Retraction/correction check"), {
      target: { value: "NOT_RETRACTED" },
    });
    for (const field of ["title", "authors", "year", "locator", "publication type", "venue"]) {
      fireEvent.click(screen.getByRole("checkbox", { name: field }));
    }
    fireEvent.change(screen.getByLabelText("Human claim decision"), {
      target: { value: "ACCEPT" },
    });
    fireEvent.change(screen.getByLabelText("Claim evidence SHA-256"), {
      target: { value: "b".repeat(64) },
    });
    fireEvent.change(screen.getByLabelText("Claim verification method"), {
      target: { value: "Checked page 7 against the captured PDF." },
    });
    fireEvent.change(screen.getByLabelText("Claim review notes"), {
      target: { value: "The captured passage directly supports the narrow claim." },
    });
    await waitFor(() => expect(submit).toBeEnabled());
    fireEvent.click(submit);

    await waitFor(() => expect(mocks.recordFactoryReviewedSource).toHaveBeenCalledWith(
      "codex-source-review",
      expect.objectContaining({
        reviewer: "Configured Reviewer",
        capture_revision_sha256: "c".repeat(64),
        retraction_status: "NOT_RETRACTED",
        claim_reviews: [expect.objectContaining({
          claim_id: "claim_1",
          decision: "ACCEPT",
          evidence_sha256: "b".repeat(64),
        })],
      }),
    ));
    expect(await screen.findByText(/separate human-verified artifact/i)).toBeVisible();
  });

  it.each(["ADMITTED", "INTEGRITY_ERROR", "LOCAL_PENDING"] as const)(
    "blocks dismissal while a structured delivery is %s",
    async (deliveryState) => {
      const proposalTask = {
        task_id: "pending-hypothesis-review", state: "PROPOSAL_READY", task_type: "HYPOTHESIS_PROPOSAL",
        campaign_id: "factory_example", proposal_validation: { status: "VALIDATED_NOT_APPLIED", proposal_id: "proposal-1", payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64) },
        proposal: { schema: "alphaquest.hypothesis-proposal/v1" }, proposal_disposition: null, structured_review: null,
        review_delivery: deliveryState === "LOCAL_PENDING" ? null : { status: deliveryState },
      };
      mocks.factoryStatus.mockResolvedValue(status({ latest_task: { ...proposalTask, proposal: undefined } }));
      mocks.factoryTask.mockResolvedValue({ task: proposalTask });
      mocks.recordFactoryReviewedHypothesis.mockImplementation(() => new Promise(() => {}));
      render(<MemoryRouter><WorkflowPage /></MemoryRouter>);
      const submit = await screen.findByRole("button", { name: "ACCEPT REVIEWED HYPOTHESIS" });
      fireEvent.change(screen.getByLabelText("Required review notes"), { target: { value: "My exact review decision." } });
      const dismiss = screen.getByRole("button", { name: "DISMISS" });
      if (deliveryState === "LOCAL_PENDING") {
        expect(dismiss).toBeEnabled();
        for (const box of screen.getAllByRole("checkbox")) fireEvent.click(box);
        expect(submit).toBeEnabled();
        fireEvent.click(submit);
        await waitFor(() => expect(mocks.recordFactoryReviewedHypothesis).toHaveBeenCalledTimes(1));
      }
      await waitFor(() => expect(dismiss).toBeDisabled());
      fireEvent.click(dismiss);
      expect(mocks.setFactoryProposalDisposition).not.toHaveBeenCalled();
      expect(submit).toBeDisabled();
    },
  );

  it("requires exhaustive hypothesis-field and quality-gate acceptance", async () => {
    const proposalTask = {
      task_id: "codex-hypothesis-review",
      state: "PROPOSAL_READY",
      task_type: "HYPOTHESIS_PROPOSAL",
      campaign_id: "factory_example",
      proposal_validation: { status: "VALIDATED_NOT_APPLIED", proposal_id: "proposal-1", payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64) },
      proposal: { schema: "alphaquest.hypothesis-proposal/v1" },
      proposal_disposition: null,
      structured_review: null,
    };
    mocks.factoryStatus.mockResolvedValue(status({
      latest_task: { ...proposalTask, proposal: undefined },
    }));
    mocks.factoryTask
      .mockResolvedValueOnce({ task: proposalTask })
      .mockResolvedValueOnce({
        task: {
          ...proposalTask,
          structured_review: {
            status: "ACCEPTED_FOR_MECHANICS",
            reviewer: "Configured Reviewer",
          },
        },
      });

    render(<MemoryRouter><WorkflowPage /></MemoryRouter>);
    const submit = await screen.findByRole("button", {
      name: "ACCEPT REVIEWED HYPOTHESIS",
    });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Required review notes"), {
      target: { value: "Reviewed every field against the accepted source claim and objectives." },
    });
    const checks = screen.getAllByRole("checkbox");
    expect(checks).toHaveLength(25);
    for (const check of checks) fireEvent.click(check);
    await waitFor(() => expect(submit).toBeEnabled());
    fireEvent.click(submit);

    await waitFor(() => expect(mocks.recordFactoryReviewedHypothesis).toHaveBeenCalledWith(
      "codex-hypothesis-review",
      expect.objectContaining({
        reviewer: "Configured Reviewer",
        reviewed_fields: expect.arrayContaining(["causal_mechanism", "source_claim_ids"]),
        objective_alignment: "PASS",
        source_claim_alignment: "PASS",
        falsifiability: "PASS",
        information_timeline_no_lookahead: "PASS",
        execution_cost_awareness: "PASS",
      }),
    ));
    expect(await screen.findByText(/complete hypothesis was accepted/i)).toBeVisible();
  });

  it("hides and dismisses a schema-rejected proposal without acknowledgement", async () => {
    const rejectedTask = {
      task_id: "codex-rejected-1",
      state: "PROPOSAL_READY",
      proposal_validation: {
        status: "REJECTED_NOT_APPLIED",
        error: "proposal schema validation failed: extra_forbidden at unexpected",
      },
      proposal: { source_title: "Untrusted output" },
      proposal_disposition: null,
    };
    mocks.factoryStatus
      .mockResolvedValueOnce(
        status({
          latest_task: rejectedTask,
        }),
      )
      .mockResolvedValue(
        status({
          latest_task: {
            ...rejectedTask,
            proposal: undefined,
            proposal_disposition: {
              status: "DISMISSED_INVALID_OUTPUT",
              reviewer: "Configured Reviewer",
            },
          },
        }),
      );
    mocks.factoryTask.mockResolvedValue({
      task: {
        ...rejectedTask,
        proposal: undefined,
        proposal_disposition: {
          status: "DISMISSED_INVALID_OUTPUT",
          reviewer: "Configured Reviewer",
        },
      },
    });

    render(
      <MemoryRouter>
        <WorkflowPage />
      </MemoryRouter>,
    );

    expect(await screen.findByText("Dismiss invalid output")).toBeVisible();
    expect(screen.queryByText("Untrusted output")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "ACKNOWLEDGE FOR HUMAN TRANSFER" }),
    ).not.toBeInTheDocument();
    const dismiss = screen.getByRole("button", {
      name: "DISMISS INVALID OUTPUT",
    });
    expect(dismiss).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Required dismissal notes"), {
      target: { value: "Close this invalid output before a bounded retry." },
    });
    await waitFor(() => expect(dismiss).toBeEnabled());
    fireEvent.click(dismiss);

    await waitFor(() =>
      expect(mocks.setFactoryProposalDisposition).toHaveBeenCalledWith(
        "codex-rejected-1",
        {
          disposition: "DISMISS",
          reviewer: "Configured Reviewer",
          notes: "Close this invalid output before a bounded retry.",
        },
      ),
    );
  });

  it("dismisses a validated proposal without implying application", async () => {
    const proposalTask = {
      task_id: "codex-proposal-dismiss",
      state: "PROPOSAL_READY",
      task_type: "HYPOTHESIS_PROPOSAL",
      proposal_validation: { status: "VALIDATED_NOT_APPLIED", proposal_id: "proposal-1", payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64) },
      proposal: {
        schema: "alphaquest.hypothesis-proposal/v1",
        hypothesis: "Bounded test proposal",
      },
      proposal_disposition: null,
      applied: false,
      approved: false,
    };
    mocks.factoryStatus.mockResolvedValue(
      status({
        latest_task: {
          task_id: proposalTask.task_id,
          state: proposalTask.state,
          task_type: proposalTask.task_type,
          proposal_validation: proposalTask.proposal_validation,
          proposal_disposition: null,
        },
      }),
    );
    mocks.factoryTask
      .mockResolvedValueOnce({ task: proposalTask })
      .mockResolvedValueOnce({
        task: {
          ...proposalTask,
          proposal_disposition: {
            status: "DISMISSED_NOT_APPLIED",
            reviewer: "Configured Reviewer",
            notes: "Evidence does not support transfer.",
            campaign_mutations_performed: false,
            approval_granted: false,
          },
        },
      });

    render(
      <MemoryRouter>
        <WorkflowPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("Proposal only — not applied or approved"),
    ).toBeVisible();
    fireEvent.change(screen.getByLabelText("Required review notes"), {
      target: { value: "Evidence does not support transfer." },
    });
    const dismiss = screen.getByRole("button", { name: "DISMISS" });
    await waitFor(() => expect(dismiss).toBeEnabled());
    fireEvent.click(dismiss);

    await waitFor(() =>
      expect(mocks.setFactoryProposalDisposition).toHaveBeenCalledWith(
        "codex-proposal-dismiss",
        {
          disposition: "DISMISS",
          reviewer: "Configured Reviewer",
          notes: "Evidence does not support transfer.",
        },
      ),
    );
    expect(
      await screen.findByText(/Proposal dismissed.*not applied.*no approval/i),
    ).toBeVisible();
  });

  it("records one ranked next action without applying successor mechanics", async () => {
    const rankingTask = {
      task_id: "codex-ranking-1",
      state: "PROPOSAL_READY",
      task_type: "NEXT_EXPERIMENT",
      campaign_id: "published_example",
      proposal_validation: { status: "VALIDATED_NOT_APPLIED", proposal_id: "proposal-1", payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64) },
      proposal: {
        schema: "alphaquest.next-action-ranking-proposal/v1",
        recommendations: [
          {
            rank: 1,
            action: "ABANDON_EDGE",
            rationale: "Stop because the governed evidence rejects the edge.",
          },
          {
            rank: 2,
            action: "PROPOSE_SUCCESSOR",
            rationale: "Propose one materially different bounded successor.",
          },
        ],
      },
      proposal_disposition: null,
      selected_action: null,
      applied: false,
      approved: false,
    };
    mocks.factoryStatus.mockResolvedValue(
      status({
        latest_task: {
          task_id: rankingTask.task_id,
          state: rankingTask.state,
          task_type: rankingTask.task_type,
          campaign_id: rankingTask.campaign_id,
          proposal_validation: rankingTask.proposal_validation,
          selected_action: null,
        },
      }),
    );
    mocks.factoryTasks.mockResolvedValue({ tasks: [rankingTask] });
    mocks.factoryTask.mockResolvedValue({ task: rankingTask });

    render(
      <MemoryRouter>
        <WorkflowPage />
      </MemoryRouter>,
    );

    const selector = await screen.findByRole("combobox", {
      name: /Selected governed next action/i,
    });
    const record = screen.getByRole("button", { name: "RECORD SELECTED ACTION" });
    expect(record).toBeDisabled();
    fireEvent.change(selector, { target: { value: "PROPOSE_SUCCESSOR" } });
    fireEvent.change(screen.getByLabelText("Required review notes"), {
      target: {
        value: "This preserves the same edge while requiring new human-reviewed mechanics.",
      },
    });
    await waitFor(() => expect(record).toBeEnabled());
    fireEvent.click(record);

    await waitFor(() =>
      expect(mocks.setFactorySelectedAction).toHaveBeenCalledWith(
        "codex-ranking-1",
        {
          selected_action: "PROPOSE_SUCCESSOR",
          reviewer: "Configured Reviewer",
          notes: "This preserves the same edge while requiring new human-reviewed mechanics.",
        },
      ),
    );
    expect(
      await screen.findByText(/immutable routing choice.*Nothing was applied.*no approval/i),
    ).toBeVisible();
  });

  it("requires a separate immutable completion for a terminal selected action", async () => {
    const selectedTask = {
      task_id: "codex-ranking-terminal",
      state: "PROPOSAL_READY",
      task_type: "NEXT_EXPERIMENT",
      campaign_id: "published_example",
      proposal_validation: { status: "VALIDATED_NOT_APPLIED", proposal_id: "proposal-1", payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64) },
      proposal: {
        schema: "alphaquest.next-action-ranking-proposal/v1",
        recommendations: [
          {
            rank: 1,
            action: "ABANDON_EDGE",
            rationale: "Stop after the governed terminal scientific failure.",
          },
        ],
      },
      selected_action: {
        selected_action: "ABANDON_EDGE",
        reviewer: "Configured Reviewer",
        selection_sha256: "a".repeat(64),
      },
      selected_action_completion: null,
      applied: false,
      approved: false,
    };
    const completedTask = {
      ...selectedTask,
      selected_action_completion: {
        completed: true,
        terminal_status: "EDGE_ABANDONED",
        completion_sha256: "b".repeat(64),
      },
    };
    mocks.factoryStatus.mockResolvedValue(
      status({
        latest_task: selectedTask,
        next_action: {
          kind: "HUMAN_ACTION",
          campaign_id: "published_example",
          label: "Record terminal edge abandonment",
          eligible: false,
          requires_human_review: true,
        },
      }),
    );
    mocks.factoryTasks.mockResolvedValue({ tasks: [selectedTask] });
    mocks.factoryTask
      .mockResolvedValueOnce({ task: selectedTask })
      .mockResolvedValueOnce({ task: completedTask });

    render(
      <MemoryRouter>
        <WorkflowPage />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText("Terminal decision still requires completion"),
    ).toBeVisible();
    const complete = screen.getByRole("button", {
      name: "RECORD TERMINAL DECISION COMPLETION",
    });
    expect(complete).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Terminal decision notes"), {
      target: {
        value: "Close this edge without changing the terminal scientific verdict.",
      },
    });
    await waitFor(() => expect(complete).toBeEnabled());
    fireEvent.click(complete);

    await waitFor(() =>
      expect(mocks.completeFactorySelectedAction).toHaveBeenCalledWith(
        "codex-ranking-terminal",
        {
          reviewer: "Configured Reviewer",
          notes: "Close this edge without changing the terminal scientific verdict.",
        },
      ),
    );
    expect(
      await screen.findByText(/terminal human decision was recorded separately/i),
    ).toBeVisible();
    expect(await screen.findByText(/EDGE_ABANDONED/)).toBeVisible();
  });
});


it("reopens a saved structured receipt while another proposal is pending", async () => {
  const pending = { task_id: "pending-hypothesis", state: "PROPOSAL_READY", task_type: "HYPOTHESIS_PROPOSAL",
    campaign_id: "factory_example", proposal_validation: { status: "VALIDATED_NOT_APPLIED", proposal_id: "proposal-1", payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64) },
    proposal: { schema: "alphaquest.hypothesis-proposal/v1" } };
  const saved = { task_id: "saved-source", state: "PROPOSAL_READY", task_type: "SOURCE_RESEARCH",
    campaign_id: "factory_example", proposal_validation: { status: "VALIDATED_NOT_APPLIED", proposal_id: "proposal-1", payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64) },
    proposal: { schema: "alphaquest.source-evidence-bundle/v1", claims: [] },
    structured_review: { status: "ACCEPTED_FOR_HYPOTHESIS", reviewer: "Source Reviewer", notes: "Verified captured source.", review_id: "source-review-1" } };
  mocks.factoryStatus.mockResolvedValue(status({ latest_task: pending }));
  mocks.factoryTasks.mockResolvedValue({ tasks: [pending, saved] });
  mocks.factoryTask.mockImplementation(async (id: string) => ({ task: id === saved.task_id ? saved : pending }));
  render(<MemoryRouter><WorkflowPage /></MemoryRouter>);
  expect(await screen.findByRole("button", { name: "ACCEPT REVIEWED HYPOTHESIS" })).toBeVisible();
  fireEvent.change(screen.getByLabelText("Recent proposals and saved reviews"), { target: { value: saved.task_id } });
  expect(await screen.findByRole("region", { name: "Saved review receipt" })).toBeVisible();
  expect(screen.getByText("source-review-1")).toBeVisible();
  expect(screen.queryByRole("button", { name: "ACCEPT REVIEWED SOURCE EVIDENCE" })).not.toBeInTheDocument();
});
