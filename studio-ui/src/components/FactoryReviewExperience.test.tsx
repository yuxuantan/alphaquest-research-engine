import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FactoryStructuredReview } from "./FactoryStructuredReview";
import { FactoryReviewReceipt } from "./FactoryReviewRecord";
import type { CodexTaskRecord } from "../types";

const committedDelivery = { status: "COMMITTED" as const, operation_id: "00000000-0000-4000-8000-000000000001",
  proposal_id: "proposal-1", payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64) };

const mocks = vi.hoisted(() => ({ hypothesis: vi.fn(), engineering: vi.fn(), source: vi.fn(), legacy: vi.fn(), factoryTask: vi.fn(), readiness: vi.fn() }));
vi.mock("../api", () => ({ api: {
  recordFactoryReviewedSource: mocks.source,
  recoverFactoryAdmittedV1Source: mocks.legacy,
  factorySourceReviewReadiness: mocks.readiness,
  factoryTask: mocks.factoryTask,
  recordFactoryReviewedHypothesis: mocks.hypothesis,
  recordFactoryReviewedEngineeringIntent: mocks.engineering,
} }));

const task: CodexTaskRecord = {
  task_id: "hypothesis_task", task_type: "HYPOTHESIS_PROPOSAL", state: "PROPOSAL_READY",
  proposal_validation: { status: "VALIDATED_NOT_APPLIED", payload_sha256: "a".repeat(64), proposal_id: "proposal-1", validation_sha256: "d".repeat(64) },
  proposal: { causal_mechanism: "A delayed inventory response after public information.",
    unresolved_questions: ["Does the effect survive realistic costs?"], confounders: ["Volatility regime"] },
};
function checkAll() {
  for (const box of screen.getAllByRole("checkbox")) fireEvent.click(box);
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); });

beforeEach(() => { localStorage.clear(); vi.resetAllMocks(); vi.spyOn(crypto, "randomUUID").mockReturnValue("00000000-0000-4000-8000-000000000001"); mocks.hypothesis.mockResolvedValue({}); mocks.engineering.mockResolvedValue({}); mocks.legacy.mockResolvedValue({}); mocks.readiness.mockResolvedValue({ status: "READY", eligible_capture_count: 1, options: [{ capture_id: "capture.source", capture_revision_sha256: "c".repeat(64), source_version_id: "version.source", status: "FULL_TEXT_CAPTURED", content_sha256: "a".repeat(64), retrieval_locator: "https://example.test/source", readiness: "READY", issues: [], legacy_recovery_match: true, title: "Captured source", authors: ["Researcher"], source_category: "ACADEMIC", version_kind: "ORIGINAL", version_label: "Published version", claim_evidence: [{ claim_id: "claim", status: "BOUND", evidence_sha256: "b".repeat(64), evidence_kind: "EXTRACTED_TEXT", reason: null }] }] }); });

describe("structured review experience", () => {
  it("recovers a server-admitted V1 source review from empty browser storage", async () => {
    const sourceTask: CodexTaskRecord = {
      ...task,
      task_id: "legacy_source_task",
      task_type: "SOURCE_RESEARCH",
      proposal: { claims: [{ claim_id: "claim", support: "DIRECT", statement: "Evidence", source_location: "Page 1" }] },
      review_delivery: {
        status: "ADMITTED", operation_id: "legacy-operation", proposal_id: "proposal-1",
        payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64),
        artifact_schema: "alphaquest.reviewed-source-evidence/v1", legacy_recovery_available: true,
      },
    };
    mocks.factoryTask.mockResolvedValue({ task: {
      ...sourceTask,
      review_delivery: { ...sourceTask.review_delivery, status: "COMMITTED", legacy_recovery_available: false },
      structured_review: {
        status: "ACCEPTED_FOR_HYPOTHESIS", proposal_id: "proposal-1",
        proposal_payload_sha256: "a".repeat(64), proposal_validation_sha256: "d".repeat(64),
        artifact_sha256: "e".repeat(64),
      },
    } });
    const onComplete = vi.fn().mockResolvedValue(undefined);
    render(<FactoryStructuredReview task={sourceTask} reviewer="" notes="" onComplete={onComplete} />);

    const recovery = await screen.findByRole("button", { name: "RECOVER ADMITTED V1 REVIEW" });
    await waitFor(() => expect(recovery).toBeEnabled());
    expect(screen.queryByLabelText("Human verification method")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Human claim decision")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ACCEPT REVIEWED SOURCE EVIDENCE" })).toBeDisabled();
    fireEvent.click(recovery);
    await waitFor(() => expect(mocks.legacy).toHaveBeenCalledWith("legacy_source_task", {
      delivery: {
        operation_id: "legacy-operation", proposal_id: "proposal-1",
        payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64),
      },
      capture_revision_sha256: "c".repeat(64),
    }));
    await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
    expect(mocks.source).not.toHaveBeenCalled();
    expect(localStorage.length).toBe(0);
  });

  it("blocks V1 recovery when no ready capture matches the admitted content", async () => {
    mocks.readiness.mockResolvedValue({ status: "READY", eligible_capture_count: 1, options: [{
      capture_id: "capture.other", capture_revision_sha256: "c".repeat(64),
      source_version_id: "version.other", status: "FULL_TEXT_CAPTURED",
      content_sha256: "b".repeat(64), retrieval_locator: "https://example.test/other",
      readiness: "READY", issues: [], legacy_recovery_match: false, title: "Other bytes",
      authors: ["Researcher"], source_category: "ACADEMIC", version_kind: "ORIGINAL",
      version_label: "Published version",
    }] });
    const sourceTask: CodexTaskRecord = {
      ...task, task_type: "SOURCE_RESEARCH",
      proposal: { claims: [{ claim_id: "claim", support: "DIRECT", statement: "Evidence", source_location: "Page 1" }] },
      review_delivery: {
        status: "ADMITTED", operation_id: "legacy-operation", proposal_id: "proposal-1",
        payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64),
        artifact_schema: "alphaquest.reviewed-source-evidence/v1", legacy_recovery_available: true,
      },
    };
    render(<FactoryStructuredReview task={sourceTask} reviewer="" notes="" onComplete={vi.fn()} />);
    expect(await screen.findByText(/No capture matches the admitted V1 document/)).toBeVisible();
    expect(screen.getByRole("button", { name: "RECOVER ADMITTED V1 REVIEW" })).toBeDisabled();
    expect(mocks.legacy).not.toHaveBeenCalled();
  });

  it("keeps a failed V1 recovery locked and does not expose recovery for V2 admission", async () => {
    const legacyTask: CodexTaskRecord = {
      ...task, task_id: "failed_legacy_source", task_type: "SOURCE_RESEARCH",
      proposal: { claims: [{ claim_id: "claim", support: "DIRECT", statement: "Evidence", source_location: "Page 1" }] },
      review_delivery: {
        status: "ADMITTED", operation_id: "legacy-operation", proposal_id: "proposal-1",
        payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64),
        artifact_schema: "alphaquest.reviewed-source-evidence/v1", legacy_recovery_available: true,
      },
    };
    mocks.legacy.mockRejectedValue(new Error("Recovery write interrupted"));
    mocks.factoryTask.mockResolvedValue({ task: { ...legacyTask, structured_review: null } });
    const view = render(<FactoryStructuredReview task={legacyTask} reviewer="" notes="" onComplete={vi.fn()} />);
    const recovery = await screen.findByRole("button", { name: "RECOVER ADMITTED V1 REVIEW" });
    await waitFor(() => expect(recovery).toBeEnabled());
    fireEvent.click(recovery);
    expect(await screen.findByText(/admitted V1 operation remains locked/i)).toBeVisible();
    expect(screen.getByRole("button", { name: "ACCEPT REVIEWED SOURCE EVIDENCE" })).toBeDisabled();
    expect(mocks.source).not.toHaveBeenCalled();

    view.unmount();
    render(<FactoryStructuredReview task={{
      ...legacyTask,
      review_delivery: { ...legacyTask.review_delivery!, artifact_schema: "alphaquest.reviewed-source-evidence/v2", legacy_recovery_available: false },
    }} reviewer="" notes="" onComplete={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "RECOVER ADMITTED V1 REVIEW" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "CHECK SAVED REVIEW" })).toBeVisible();
  });

  it("keeps claim decisions blank and blocks a mismatched canonical capture", async () => {
    mocks.readiness.mockResolvedValue({
      status: "NOT_READY", eligible_capture_count: 0, options: [{
        capture_id: "capture.working", capture_revision_sha256: "c".repeat(64),
        source_version_id: "version.working", status: "FULL_TEXT_CAPTURED",
        content_sha256: "a".repeat(64), retrieval_locator: "https://example.test/working",
        readiness: "NOT_READY", issues: ["PUBLICATION_CATEGORY_MISMATCH"],
        title: "Working paper", authors: ["Researcher"], source_category: "WORKING_PAPER",
        version_kind: "WORKING_PAPER_REVISION", version_label: "Working paper",
      }],
    });
    const sourceTask: CodexTaskRecord = {
      ...task,
      task_id: "source_task",
      task_type: "SOURCE_RESEARCH",
      proposal: { claims: [{ claim_id: "claim", support: "DIRECT", statement: "Evidence", source_location: "Page 1" }] },
    };
    render(<FactoryStructuredReview task={sourceTask} reviewer="Researcher" notes="Checked" onComplete={vi.fn()} />);
    expect(await screen.findByText(/No compatible full-text capture/i)).toBeVisible();
    expect(screen.getByText(/PUBLICATION_CATEGORY_MISMATCH/i)).toBeVisible();
    expect(screen.getByLabelText("Canonical full-text capture")).toBeDisabled();
    expect(screen.getByLabelText("Captured source content SHA-256")).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Human claim decision")).toHaveValue("");
    expect(screen.getByRole("button", { name: "ACCEPT REVIEWED SOURCE EVIDENCE" })).toBeDisabled();
    expect(mocks.source).not.toHaveBeenCalled();
  });

  it("displays the bound hash without manual entry and saves the structured notes template", async () => {
    const sourceTask = { ...task, task_type: "SOURCE_RESEARCH", proposal: {
      claims: [{ claim_id: "claim", support: "DIRECT", statement: "Reported values", source_location: "PDF page 8, Table 2" }],
    } };
    mocks.source.mockResolvedValue({});
    render(<FactoryStructuredReview task={sourceTask} reviewer="Researcher" notes="Overall notes" onComplete={vi.fn()} />);
    const hash = await screen.findByLabelText("Claim evidence SHA-256");
    expect(hash).toHaveValue("b".repeat(64));
    expect(hash).toHaveAttribute("readonly");
    expect(screen.getByLabelText("Human claim decision")).toHaveValue("");
    expect(screen.getByLabelText("Claim verification method")).toHaveValue("");
    expect(screen.getByLabelText("What I found")).toHaveValue("");
    checkAll();
    for (const [label, value] of [
      ["Human verification method", "Checked full text and catalog"],
      ["Retraction/correction check", "NOT_RETRACTED"], ["Human claim decision", "ACCEPT"],
      ["Claim verification method", "COMPARE_TABLE"], ["Evidence location", "PDF page 8, Table 2"],
      ["What I found", "Both directions have positive reported means."],
      ["Decision rationale", "The table supports the narrow reported-results claim."],
    ]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
    const submit = screen.getByRole("button", { name: "ACCEPT REVIEWED SOURCE EVIDENCE" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Limitations or discrepancies"), { target: { value: "Not independently reproduced." } });
    fireEvent.click(submit);
    await waitFor(() => expect(mocks.source).toHaveBeenCalledTimes(1));
    expect(mocks.source.mock.calls[0][1].claim_reviews).toEqual([{
      claim_id: "claim", proposed_support: "DIRECT", decision: "ACCEPT", evidence_sha256: "b".repeat(64),
      verification_method: "Method: Compared table values\nLocation: PDF page 8, Table 2",
      notes: "Finding: Both directions have positive reported means.\nDecision rationale: The table supports the narrow reported-results claim.\nLimitations or discrepancies: Not independently reproduced.",
    }]);
  });

  it("clears capture-specific judgments when changing capture and blocks unbound claim acceptance", async () => {
    const first = (await mocks.readiness())["options"][0];
    mocks.readiness.mockResolvedValue({ status: "READY", eligible_capture_count: 2, options: [first, {
      ...first, capture_id: "capture.other", capture_revision_sha256: "e".repeat(64),
      claim_evidence: [{ claim_id: "claim", status: "UNBOUND", evidence_sha256: null, evidence_kind: null,
        reason: "PROPOSED_EVIDENCE_OUTSIDE_SELECTED_CAPTURE" }],
    }] });
    render(<FactoryStructuredReview task={{ ...task, task_type: "SOURCE_RESEARCH", proposal: {
      claims: [{ claim_id: "claim", support: "DIRECT", statement: "Claim", source_location: "Page 1" }],
    } }} reviewer="Researcher" notes="Checked" onComplete={vi.fn()} />);
    const capture = screen.getByLabelText("Canonical full-text capture");
    await waitFor(() => expect(capture).toBeEnabled());
    fireEvent.change(capture, { target: { value: "c".repeat(64) } });
    checkAll();
    fireEvent.change(screen.getByLabelText("Human claim decision"), { target: { value: "ACCEPT" } });
    fireEvent.change(screen.getByLabelText("Claim verification method"), { target: { value: "READ_PASSAGE" } });
    fireEvent.change(screen.getByLabelText("What I found"), { target: { value: "Capture-specific observation" } });
    fireEvent.change(capture, { target: { value: "e".repeat(64) } });
    expect(screen.getByLabelText("Human claim decision")).toHaveValue("");
    expect(screen.getByLabelText("Claim verification method")).toHaveValue("");
    expect(screen.getByLabelText("What I found")).toHaveValue("");
    expect(screen.getAllByRole("checkbox").every((box) => !(box as HTMLInputElement).checked)).toBe(true);
    expect(screen.getByRole("option", { name: "Accept with captured evidence" })).toBeDisabled();
    expect(screen.getByRole("option", { name: "Reject claim" })).toBeEnabled();
    expect(screen.queryByLabelText("Claim evidence SHA-256")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "ACCEPT REVIEWED SOURCE EVIDENCE" })).toBeDisabled();
    expect(mocks.source).not.toHaveBeenCalled();
  });

  it.each(["SOURCE_RESEARCH", "HYPOTHESIS_PROPOSAL", "MECHANICS_INTENT"])(
    "locks %s from server admission with empty origin-local storage",
    async (taskType) => {
      const currentTask: CodexTaskRecord = { ...task, task_type: taskType,
        proposal: taskType === "SOURCE_RESEARCH" ? { claims: [{ claim_id: "claim", support: "DIRECT", statement: "Evidence", source_location: "Page 1" }] }
          : taskType === "MECHANICS_INTENT" ? { execution_lane: "ENGINEERING_HANDOFF" } : task.proposal,
        review_delivery: { status: "ADMITTED", operation_id: "other-origin-operation" },
      };
      render(<FactoryStructuredReview task={currentTask} reviewer="Researcher" notes="Changed notes" onComplete={vi.fn()} />);
      checkAll();
      if (taskType === "SOURCE_RESEARCH") {
        for (const [label, value] of [
          ["Human verification method", "Checked metadata"],
          ["Retraction/correction check", "NOT_RETRACTED"], ["Human claim decision", "ACCEPT"],
          ["Claim verification method", "READ_PASSAGE"], ["What I found", "Confirmed"], ["Decision rationale", "The passage supports the claim"], ["Limitations or discrepancies", "No additional limitations identified"],
        ]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
      }
      expect(localStorage.length).toBe(0);
      const button = screen.getByRole("button", { name: /^ACCEPT/ });
      expect(button).toBeDisabled();
      fireEvent.click(button);
      expect(mocks.source).not.toHaveBeenCalled();
      expect(mocks.hypothesis).not.toHaveBeenCalled();
      expect(mocks.engineering).not.toHaveBeenCalled();
      expect(screen.getByRole("button", { name: "CHECK SAVED REVIEW" })).toBeEnabled();
    },
  );

  it("binds each submission and its marker to one operation and exact proposal revision", async () => {
    mocks.hypothesis.mockImplementation(() => new Promise(() => {}));
    render(<FactoryStructuredReview task={task} reviewer="Researcher" notes="Checked" onComplete={vi.fn()} />);
    checkAll();
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(mocks.hypothesis).toHaveBeenCalledTimes(1));
    const delivery = mocks.hypothesis.mock.calls[0][1].delivery;
    expect(delivery).toEqual({ operation_id: expect.any(String), proposal_id: "proposal-1",
      payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64) });
    expect(delivery.operation_id.length).toBeGreaterThan(0);
    expect(JSON.parse(localStorage.getItem(`alphaquest.review-delivery.pending.v1:${task.task_id}`)!))
      .toEqual({ task_id: task.task_id, ...delivery });
  });

  it.each(["SOURCE_RESEARCH", "HYPOTHESIS_PROPOSAL", "MECHANICS_INTENT"])(
    "does not confirm a competing %s submission as the local operation",
    async (taskType) => {
      const currentTask = { ...task, task_type: taskType, proposal: taskType === "SOURCE_RESEARCH"
        ? { claims: [{ claim_id: "claim", support: "DIRECT", statement: "Evidence", source_location: "Page 1" }] }
        : taskType === "MECHANICS_INTENT" ? { execution_lane: "ENGINEERING_HANDOFF" } : task.proposal };
      const mutation = taskType === "SOURCE_RESEARCH" ? mocks.source : taskType === "MECHANICS_INTENT" ? mocks.engineering : mocks.hypothesis;
      mutation.mockRejectedValue(new Error("A different operation owns this task"));
      const status = taskType === "SOURCE_RESEARCH" ? "ACCEPTED_FOR_HYPOTHESIS" : taskType === "MECHANICS_INTENT" ? "ACCEPTED_FOR_ENGINEERING_HANDOFF" : "ACCEPTED_FOR_MECHANICS";
      mocks.factoryTask.mockResolvedValue({ task: { ...currentTask,
        review_delivery: { status: "COMMITTED", operation_id: "competing-operation", proposal_id: "proposal-1", payload_sha256: "a".repeat(64), validation_sha256: "d".repeat(64) },
        structured_review: { status, proposal_id: "proposal-1", proposal_validation_sha256: "d".repeat(64), proposal_payload_sha256: "a".repeat(64), artifact_sha256: "c".repeat(64), reviewer: "Other reviewer", notes: "Different decision" },
      } });
      const onComplete = vi.fn().mockResolvedValue(undefined);
      render(<FactoryStructuredReview task={currentTask} reviewer="Researcher" notes="My decision" onComplete={onComplete} />);
      checkAll();
      if (taskType === "SOURCE_RESEARCH") {
        for (const [label, value] of [
          ["Human verification method", "Checked metadata"],
          ["Retraction/correction check", "NOT_RETRACTED"], ["Human claim decision", "ACCEPT"],
          ["Claim verification method", "READ_PASSAGE"], ["What I found", "Confirmed"], ["Decision rationale", "The passage supports the claim"], ["Limitations or discrepancies", "No additional limitations identified"],
        ]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
      }
      const button = screen.getByRole("button");
      await waitFor(() => expect(button).toBeEnabled());
      fireEvent.click(button);
      expect(await screen.findByText(/different submission/i)).toBeVisible();
      expect(onComplete).not.toHaveBeenCalled();
      expect(button).toBeDisabled();
      expect(screen.queryByText("Review saved. Read the receipt before continuing.")).not.toBeInTheDocument();
      expect(localStorage.getItem(`alphaquest.review-delivery.pending.v1:${task.task_id}`)).not.toBeNull();
      expect(mutation).toHaveBeenCalledTimes(1);
    },
  );

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

  it.each(["SOURCE_RESEARCH", "HYPOTHESIS_PROPOSAL", "MECHANICS_INTENT"])(
    "recovers a lost POST response from the durable %s receipt without another write",
    async (taskType) => {
      const proposal = taskType === "SOURCE_RESEARCH" ? { claims: [{ claim_id: "claim", support: "DIRECT", statement: "Captured evidence supports the source claim.", source_location: "Page 1" }] }
        : taskType === "MECHANICS_INTENT" ? { execution_lane: "ENGINEERING_HANDOFF" } : task.proposal;
      const currentTask = { ...task, task_type: taskType, proposal };
      const mutation = taskType === "SOURCE_RESEARCH" ? mocks.source : taskType === "MECHANICS_INTENT" ? mocks.engineering : mocks.hypothesis;
      mutation.mockRejectedValueOnce(new Error("Response lost after commit"));
      const status = taskType === "SOURCE_RESEARCH" ? "ACCEPTED_FOR_HYPOTHESIS" : taskType === "MECHANICS_INTENT" ? "ACCEPTED_FOR_ENGINEERING_HANDOFF" : "ACCEPTED_FOR_MECHANICS";
      mocks.factoryTask.mockResolvedValue({ task: { ...currentTask, review_delivery: committedDelivery, structured_review: {
        status, proposal_id: "proposal-1", proposal_validation_sha256: "d".repeat(64), proposal_payload_sha256: "a".repeat(64), artifact_sha256: "c".repeat(64),
      } } });
      const onComplete = vi.fn().mockResolvedValue(undefined);
      render(<FactoryStructuredReview task={currentTask} reviewer="Researcher" notes="Checked the evidence" onComplete={onComplete} />);
      checkAll();
      if (taskType === "SOURCE_RESEARCH") {
        for (const [label, value] of [
          ["Human verification method", "Checked publisher metadata"],
          ["Retraction/correction check", "NOT_RETRACTED"], ["Human claim decision", "ACCEPT"],
          ["Claim verification method", "READ_PASSAGE"], ["What I found", "Direct support confirmed"], ["Decision rationale", "The passage supports the claim"], ["Limitations or discrepancies", "No additional limitations identified"],
        ]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
      }
      const button = screen.getByRole("button");
      await waitFor(() => expect(button).toBeEnabled());
      fireEvent.click(button);
      await waitFor(() => expect(mocks.factoryTask).toHaveBeenCalledWith(task.task_id));
      await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
      expect(button).toBeDisabled();
      fireEvent.click(button);
      expect(mutation).toHaveBeenCalledTimes(1);
    },
  );

  it.each(["SOURCE_RESEARCH", "HYPOTHESIS_PROPOSAL", "MECHANICS_INTENT"])(
    "keeps an in-flight %s review locked after reopening the form",
    async (taskType) => {
      const currentTask = { ...task, task_type: taskType, proposal: taskType === "SOURCE_RESEARCH"
        ? { claims: [{ claim_id: "claim", support: "DIRECT", statement: "Captured evidence supports the source claim.", source_location: "Page 1" }] }
        : taskType === "MECHANICS_INTENT" ? { execution_lane: "ENGINEERING_HANDOFF" } : task.proposal };
      const mutation = taskType === "SOURCE_RESEARCH" ? mocks.source : taskType === "MECHANICS_INTENT" ? mocks.engineering : mocks.hypothesis;
      mutation.mockRejectedValueOnce(new Error("Response lost while server is processing"));
      let finishCommit!: () => void;
      let committed = false;
      const pendingCommit = new Promise<void>((resolve) => { finishCommit = resolve; }).then(() => { committed = true; });
      const status = taskType === "SOURCE_RESEARCH" ? "ACCEPTED_FOR_HYPOTHESIS" : taskType === "MECHANICS_INTENT" ? "ACCEPTED_FOR_ENGINEERING_HANDOFF" : "ACCEPTED_FOR_MECHANICS";
      mocks.factoryTask.mockImplementation(async () => ({ task: { ...currentTask, review_delivery: committedDelivery, structured_review: committed
        ? { status, proposal_id: "proposal-1", proposal_validation_sha256: "d".repeat(64), proposal_payload_sha256: "a".repeat(64), artifact_sha256: "c".repeat(64) } : null } }));
      const onComplete = vi.fn().mockResolvedValue(undefined);
      const props = { task: currentTask, reviewer: "Researcher", notes: "Checked", onComplete };
      const view = render(<FactoryStructuredReview {...props} />);
      checkAll();
      if (taskType === "SOURCE_RESEARCH") {
        for (const [label, value] of [
          ["Human verification method", "Checked metadata"],
          ["Retraction/correction check", "NOT_RETRACTED"], ["Human claim decision", "ACCEPT"],
          ["Claim verification method", "READ_PASSAGE"], ["What I found", "Direct support confirmed"], ["Decision rationale", "The passage supports the claim"], ["Limitations or discrepancies", "No additional limitations identified"],
        ]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
      }
      let submit = screen.getByRole("button");
      await waitFor(() => expect(submit).toBeEnabled());
      fireEvent.click(submit);
      await waitFor(() => expect(mocks.factoryTask).toHaveBeenCalledTimes(1));
      await screen.findByText(/No stored review is visible yet/);
      expect(submit).toBeDisabled();
      fireEvent.click(submit);
      expect(mutation).toHaveBeenCalledTimes(1);
      view.unmount();
      render(<FactoryStructuredReview {...props} />);
      checkAll();
      if (taskType === "SOURCE_RESEARCH") {
        for (const [label, value] of [
          ["Human verification method", "Checked metadata"],
          ["Retraction/correction check", "NOT_RETRACTED"], ["Human claim decision", "ACCEPT"],
          ["Claim verification method", "READ_PASSAGE"], ["What I found", "Direct support confirmed"], ["Decision rationale", "The passage supports the claim"], ["Limitations or discrepancies", "No additional limitations identified"],
        ]) fireEvent.change(screen.getByLabelText(label), { target: { value } });
      }
      const acceptLabel = taskType === "SOURCE_RESEARCH" ? "ACCEPT REVIEWED SOURCE EVIDENCE"
        : taskType === "HYPOTHESIS_PROPOSAL" ? "ACCEPT REVIEWED HYPOTHESIS" : "ACCEPT FOR ENGINEERING HANDOFF";
      submit = screen.getByRole("button", { name: acceptLabel });
      expect(submit).toBeDisabled();
      fireEvent.click(submit);
      expect(mutation).toHaveBeenCalledTimes(1);
      finishCommit();
      await pendingCommit;
      fireEvent.click(screen.getByRole("button", { name: "CHECK SAVED REVIEW" }));
      await waitFor(() => expect(onComplete).toHaveBeenCalledTimes(1));
      expect(submit).toBeDisabled();
      expect(mutation).toHaveBeenCalledTimes(1);
      expect(mocks.factoryTask).toHaveBeenCalledTimes(2);
    },
  );

  it("keeps submission locked when neither the save nor readback can be confirmed", async () => {
    mocks.hypothesis.mockRejectedValueOnce(new Error("Connection lost"));
    mocks.factoryTask.mockRejectedValueOnce(new Error("Readback unavailable"));
    render(<FactoryStructuredReview task={task} reviewer="Researcher" notes="Checked" onComplete={vi.fn()} />);
    checkAll();
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByText(/could not confirm whether the review was saved/i)).toBeVisible();
    expect(screen.getByRole("button", { name: "ACCEPT REVIEWED HYPOTHESIS" })).toBeDisabled();
    expect(screen.queryByText("Review saved. Read the receipt before continuing.")).not.toBeInTheDocument();
  });

  it.each(["proposal_id", "proposal_validation_sha256"])("keeps recovery locked when receipt %s differs", async (field) => {
    mocks.hypothesis.mockRejectedValueOnce(new Error("Connection lost"));
    mocks.factoryTask.mockResolvedValue({ task: { ...task, review_delivery: committedDelivery, structured_review: {
      status: "ACCEPTED_FOR_MECHANICS", proposal_id: "proposal-1", proposal_validation_sha256: "d".repeat(64),
      proposal_payload_sha256: "a".repeat(64), [field]: "wrong-identity",
    } } });
    const onComplete = vi.fn();
    render(<FactoryStructuredReview task={task} reviewer="Researcher" notes="Checked" onComplete={onComplete} />);
    checkAll();
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(mocks.factoryTask).toHaveBeenCalledTimes(1));
    expect(screen.getByRole("button", { name: "ACCEPT REVIEWED HYPOTHESIS" })).toBeDisabled();
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("does not send a decision if browser delivery state cannot be retained", async () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("Storage unavailable"); });
    render(<FactoryStructuredReview task={task} reviewer="Researcher" notes="Checked" onComplete={vi.fn()} />);
    checkAll();
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByText(/could not retain the submission state/i)).toBeVisible();
    expect(mocks.hypothesis).not.toHaveBeenCalled();
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
