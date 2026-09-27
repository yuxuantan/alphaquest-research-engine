import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FactoryStructuredReview } from "./FactoryStructuredReview";
import { FactoryReviewReceipt } from "./FactoryReviewRecord";
import type { CodexTaskRecord } from "../types";

const mocks = vi.hoisted(() => ({ hypothesis: vi.fn(), engineering: vi.fn() }));
vi.mock("../api", () => ({ api: {
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

  it("retains evidence choices and allows retry when the write itself fails", async () => {
    mocks.hypothesis.mockRejectedValueOnce(new Error("Service unavailable"));
    render(<FactoryStructuredReview task={task} reviewer="Researcher" notes="Checked" onComplete={vi.fn()} />);
    checkAll();
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByText("Service unavailable")).toBeVisible();
    expect(screen.getByRole("button")).toBeEnabled();
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(mocks.hypothesis).toHaveBeenCalledTimes(2));
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
