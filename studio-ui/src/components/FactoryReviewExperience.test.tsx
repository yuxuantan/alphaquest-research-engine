import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FactoryStructuredReview } from "./FactoryStructuredReview";
import { FactoryReviewReceipt } from "./FactoryReviewRecord";
import type { CodexTaskRecord } from "../types";

const mocks = vi.hoisted(() => ({ hypothesis: vi.fn(), engineering: vi.fn(), source: vi.fn(), factoryTask: vi.fn() }));
vi.mock("../api", () => ({ api: {
  recordFactoryReviewedSource: mocks.source,
  factoryTask: mocks.factoryTask,
  recordFactoryReviewedHypothesis: mocks.hypothesis,
  recordFactoryReviewedEngineeringIntent: mocks.engineering,
} }));

const task: CodexTaskRecord = {
  task_id: "hypothesis_task", task_type: "HYPOTHESIS_PROPOSAL", state: "PROPOSAL_READY",
  proposal_validation: { status: "VALIDATED_NOT_APPLIED", payload_sha256: "a".repeat(64) },
  proposal: { causal_mechanism: "A delayed inventory response after public information.",
    unresolved_questions: ["Does the effect survive realistic costs?"], confounders: ["Volatility regime"] },
};
function checkAll() {
  for (const box of screen.getAllByRole("checkbox")) fireEvent.click(box);
}

afterEach(cleanup);

beforeEach(() => { vi.resetAllMocks(); mocks.hypothesis.mockResolvedValue({}); mocks.engineering.mockResolvedValue({}); });

describe("structured review experience", () => {
  it("puts exact values beside acknowledgements and exposes unresolved evidence", () => {
    render(<FactoryStructuredReview task={task} reviewer="Researcher" notes="Checked" onComplete={vi.fn()} />);
    const check = screen.getByRole("checkbox", { name: "causal mechanism" });
    expect(within(check.closest(".factory-review-field") as HTMLElement).getByText(String(task.proposal?.causal_mechanism))).toBeVisible();
    expect(screen.getByText("Does the effect survive realistic costs?")).toBeVisible();
    expect(screen.getByRole("button", { name: "ACCEPT REVIEWED HYPOTHESIS" })).toBeDisabled();
  });

  it("clears acknowledgements when the same task displays a different proposal revision", () => {
    const props = { task, reviewer: "Researcher", notes: "Checked", onComplete: vi.fn() };
    const { rerender } = render(<FactoryStructuredReview {...props} />);
    checkAll();
    expect(screen.getByRole("button")).toBeEnabled();
    rerender(<FactoryStructuredReview {...props} task={{ ...task, proposal_validation: { ...task.proposal_validation, payload_sha256: "b".repeat(64) } }} />);
    expect(screen.getByRole("button")).toBeDisabled();
    expect(screen.getAllByRole("checkbox").every((box) => !(box as HTMLInputElement).checked)).toBe(true);
  });

  it("does not invite a second write if saving succeeded but receipt refresh failed", async () => {
    const onComplete = vi.fn().mockRejectedValue(new Error("network read failed"));
    render(<FactoryStructuredReview task={task} reviewer="Researcher" notes="Checked" onComplete={onComplete} />);
    checkAll();
    const button = screen.getByRole("button");
    fireEvent.click(button);
    expect(await screen.findByText(/Review saved, but the screen could not refresh/)).toBeVisible();
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(mocks.hypothesis).toHaveBeenCalledTimes(1);
  });

  it("allows retry only after reading back a task with no stored review", async () => {
    mocks.hypothesis.mockRejectedValueOnce(new Error("Service unavailable"));
    mocks.factoryTask.mockResolvedValue({ task: { ...task, structured_review: null } });
    render(<FactoryStructuredReview task={task} reviewer="Researcher" notes="Checked" onComplete={vi.fn()} />);
    checkAll();
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByText(/Service unavailable/)).toBeVisible();
    expect(mocks.factoryTask).toHaveBeenCalledWith(task.task_id);
    expect(screen.getByRole("button")).toBeEnabled();
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(mocks.hypothesis).toHaveBeenCalledTimes(2));
  });

  it.each(["SOURCE_RESEARCH", "HYPOTHESIS_PROPOSAL", "MECHANICS_INTENT"])(
    "recovers a lost POST response from the durable %s receipt without another write",
    async (taskType) => {
      const proposal = taskType === "SOURCE_RESEARCH" ? { claims: [{ claim_id: "claim", support: "DIRECT", statement: "Captured evidence supports the source claim.", source_location: "Page 1" }] }
        : taskType === "MECHANICS_INTENT" ? { execution_lane: "ENGINEERING_HANDOFF" } : task.proposal;
      const currentTask = { ...task, task_type: taskType, proposal };
      const mutation = taskType === "SOURCE_RESEARCH" ? mocks.source : taskType === "MECHANICS_INTENT" ? mocks.engineering : mocks.hypothesis;
      mutation.mockRejectedValueOnce(new Error("Response lost after commit"));
      const status = taskType === "SOURCE_RESEARCH" ? "ACCEPTED_FOR_HYPOTHESIS" : taskType === "MECHANICS_INTENT" ? "ACCEPTED_FOR_ENGINEERING_HANDOFF" : "ACCEPTED_FOR_MECHANICS";
      mocks.factoryTask.mockResolvedValue({ task: { ...currentTask, structured_review: {
        status, proposal_payload_sha256: "a".repeat(64), artifact_sha256: "c".repeat(64),
      } } });
      const onComplete = vi.fn().mockResolvedValue(undefined);
      render(<FactoryStructuredReview task={currentTask} reviewer="Researcher" notes="Checked the evidence" onComplete={onComplete} />);
      checkAll();
      if (taskType === "SOURCE_RESEARCH") {
        for (const [label, value] of [
          ["Captured source content SHA-256", "a".repeat(64)], ["Human verification method", "Checked publisher metadata"],
          ["Retraction/correction check", "NOT_RETRACTED"], ["Human claim decision", "ACCEPT"],
          ["Claim evidence SHA-256", "b".repeat(64)], ["Claim verification method", "Read page 1"], ["Claim review notes", "Direct support confirmed"],
        ]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
      }
      const button = screen.getByRole("button");
      expect(button).toBeEnabled();
      fireEvent.click(button);
      await waitFor(() => expect(mocks.factoryTask).toHaveBeenCalledWith(task.task_id));
      await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
      expect(button).toBeDisabled();
      fireEvent.click(button);
      expect(mutation).toHaveBeenCalledTimes(1);
    },
  );

  it("keeps submission locked when neither the save nor readback can be confirmed", async () => {
    mocks.hypothesis.mockRejectedValueOnce(new Error("Connection lost"));
    mocks.factoryTask.mockRejectedValueOnce(new Error("Readback unavailable"));
    render(<FactoryStructuredReview task={task} reviewer="Researcher" notes="Checked" onComplete={vi.fn()} />);
    checkAll();
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByText(/could not confirm whether the review was saved/i)).toBeVisible();
    expect(screen.getByRole("button")).toBeDisabled();
    expect(screen.queryByText("Review saved. Read the receipt before continuing.")).not.toBeInTheDocument();
  });

  it("keeps engineering intent restricted to a handoff and requires every contract field", async () => {
    render(<FactoryStructuredReview task={{ ...task, task_type: "MECHANICS_INTENT", proposal: { execution_lane: "ENGINEERING_HANDOFF", unsupported_reason: "No certified package expresses this mechanism." } }} reviewer="Researcher" notes="Checked the unsupported scope" onComplete={vi.fn()} />);
    expect(screen.getByText(/It cannot implement code/)).toBeVisible();
    expect(screen.getAllByRole("checkbox")).toHaveLength(22);
    checkAll();
    fireEvent.click(screen.getByRole("button", { name: "ACCEPT FOR ENGINEERING HANDOFF" }));
    await waitFor(() => expect(mocks.engineering).toHaveBeenCalledWith(task.task_id, expect.objectContaining({ unsupported_scope_confirmed: "PASS" })));
  });
});

describe("saved receipt", () => {
  it("reconstructs a downloadable receipt from persisted task detail", () => {
    const artifact = { schema: "alphaquest.reviewed-hypothesis/v1", artifact_sha256: "c".repeat(64), hypothesis: task.proposal };
    render(<FactoryReviewReceipt task={{ ...task, structured_review: {
      status: "ACCEPTED_FOR_MECHANICS", review_id: "review_1", decision: "ACCEPT_FOR_MECHANICS",
      reviewer: "Actual Reviewer", notes: "Costs remain a separate mechanics check.", recorded_at: "2026-09-28T00:00:00+00:00",
      proposal_payload_sha256: "a".repeat(64), artifact_sha256: "c".repeat(64), artifact,
    } }} />);
    expect(screen.getByText("Actual Reviewer")).toBeVisible();
    expect(screen.getByText("Costs remain a separate mechanics check.")).toBeVisible();
    const link = screen.getByText("Download review artifact (JSON)");
    expect(JSON.parse(decodeURIComponent(link.getAttribute("href")!.split(",")[1]))).toEqual(artifact);
    expect(screen.getByText(/does not authorize performance testing/)).toBeVisible();
  });

  it("never presents an integrity error as a saved decision", () => {
    render(<FactoryReviewReceipt task={{ ...task, structured_review: { status: "INTEGRITY_ERROR" } }} />);
    expect(screen.getByText("Review receipt unavailable")).toBeVisible();
    expect(screen.queryByRole("region", { name: "Saved review receipt" })).not.toBeInTheDocument();
  });
});
