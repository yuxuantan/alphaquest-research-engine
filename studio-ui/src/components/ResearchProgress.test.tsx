import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ResearchStage, VariantProgress } from "../types";
import { progressPosition, ResearchFlow } from "./ResearchProgress";

const stages: ResearchStage[] = [
  {
    id: "protocol_frozen",
    label: "Protocol frozen",
    phase: "Define",
    description: "Protocol is immutable.",
    step: 1,
    status: "complete",
  },
  {
    id: "mechanics_review",
    label: "Mechanics approval",
    phase: "Validate mechanics",
    description: "A human verifies the sampled trades.",
    step: 2,
    status: "current",
  },
  {
    id: "limited_core_grid_test",
    label: "Limited Core Grid Test",
    phase: "Test robustness",
    description: "The predeclared grid is tested.",
    step: 3,
    status: "locked",
  },
];

const progress: VariantProgress = {
  variant_id: "v02",
  is_current: true,
  current_step: 2,
  total_steps: 3,
  current_stage_id: "mechanics_review",
  current_stage_label: "Mechanics approval",
  current_phase: "Validate mechanics",
  scientific_status: "NEEDS MANUAL REVIEW",
  operational_state: "NOT_QUEUED",
  next_action: "Review two remaining sampled trades.",
  stages,
};

describe("research stage flow", () => {
  it("shows the exact current step, every ordered stage, and the next action", () => {
    render(<ResearchFlow progress={progress} />);

    expect(
      screen.getByRole("heading", {
        name: "Stage 2 of 3 · Mechanics approval",
      }),
    ).toBeVisible();
    expect(screen.getByText("Review two remaining sampled trades.")).toBeVisible();
    expect(screen.getByText("Protocol frozen")).toBeVisible();
    expect(screen.getByText("Limited Core Grid Test")).toBeVisible();
    expect(screen.getByText("Locked")).toBeVisible();
    expect(screen.getByText("v02")).toBeVisible();
  });

  it("does not invent a stage position when progress is unavailable", () => {
    expect(progressPosition(null)).toBe("Stage not available");
  });
});
