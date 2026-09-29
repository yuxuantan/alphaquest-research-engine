import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ReviewsPage } from "./ReviewsPage";

const mocks = vi.hoisted(() => ({ reviews: vi.fn(), mechanicsReview: vi.fn(), settings: vi.fn(), annotateMechanics: vi.fn() }));
vi.mock("../api", () => ({ api: mocks }));
afterEach(cleanup);

it("requires a deliberate status and notes before saving an inspected mechanics sample", async () => {
  const item = { review_id: "sample", campaign_id: "example", variant_id: "v01", attempt_id: "original" };
  const detail = { ...item, sampled_trade_ids: ["1"], unreviewed_trade_ids: ["1"], non_correct_trade_ids: [],
    trade_evidence_token: "frozen-token", trade_evidence: { trade_id: "1", trade: {} }, blockers: [], ready_for_approval: false };
  mocks.reviews.mockResolvedValue({ items: [], candidate: [], mechanics: [item] });
  mocks.settings.mockResolvedValue({ reviewer_identity: "Researcher" });
  mocks.mechanicsReview.mockResolvedValue(detail);
  mocks.annotateMechanics.mockResolvedValue({ ...detail, unreviewed_trade_ids: [],
    trade_evidence: { ...detail.trade_evidence, annotation: { reviewer_status: "Correct", reviewer_notes: "Checked chart entry timing and next-bar fill." } } });
  render(<MemoryRouter><ReviewsPage /></MemoryRouter>);
  const button = await screen.findByRole("button", { name: "Save annotation and continue" });
  expect(button).toBeDisabled();
  expect(screen.getByLabelText("Implementation status")).toHaveValue("");
  fireEvent.change(screen.getByLabelText("Implementation status"), { target: { value: "Correct" } });
  expect(button).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Review notes"), { target: { value: "Checked chart entry timing and next-bar fill." } });
  expect(button).toBeEnabled();
  fireEvent.click(button);
  await waitFor(() => expect(mocks.annotateMechanics).toHaveBeenCalledWith(expect.objectContaining({
    evidence_token: "frozen-token", reviewer_status: "Correct", reviewer_notes: "Checked chart entry timing and next-bar fill.",
  })));
});
