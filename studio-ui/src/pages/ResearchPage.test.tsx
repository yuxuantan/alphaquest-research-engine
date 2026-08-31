import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("../state", () => ({
  useStudio: () => ({
    loading: false,
    data: {
      drafts: [],
      campaigns: [
        {
          campaign_id: "yush_orderflow_range",
          title: "Yush orderflow range",
          instrument: "ES",
          timeframe: "3m",
          updated_at: "2026-08-01T00:00:00Z",
          workflow_context: {
            current_attempt_id: "mechanics_correction_1",
            target_variant_id: "v02",
            scientific_status: "NEEDS MANUAL REVIEW",
            primary_action: {
              section: "reviews",
              label: "Review sampled trades",
              attempt_id: "mechanics_correction_1",
              variant_id: "v02",
            },
          },
          research_progress: {
            campaign: {
              variant_id: "v02",
              current_step: 3,
              total_steps: 12,
              current_stage_label: "Mechanics approval",
              next_action: "Review sampled trades",
            },
            variants: [],
          },
        },
      ],
    },
  }),
}));

import { ResearchPage, researchRecordHref } from "./ResearchPage";

describe("research campaign navigation", () => {
  it("opens a campaign under Research even when its next action is mechanics review", () => {
    render(
      <MemoryRouter>
        <ResearchPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("listitem")).toHaveAttribute(
      "href",
      "/research/yush_orderflow_range/overview?attempt=mechanics_correction_1&variant=v02",
    );
    expect(
      screen.getByText("Stage 3 of 12 · Mechanics approval · v02"),
    ).toBeVisible();
    expect(screen.getByText("Next: Review sampled trades")).toBeVisible();
  });

  it("keeps draft rows in the design workflow", () => {
    expect(
      researchRecordHref({
        kind: "draft",
        campaign_id: "draft_campaign",
        wizard_step: 4,
      }),
    ).toBe("/research/draft_campaign/design/4");
  });
});
