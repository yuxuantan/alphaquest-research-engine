import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { VerdictDecisionMatrix } from "./CampaignPage";
import { OBJECTIVE_TEMPLATES } from "./WizardPage";

describe("governed objective templates", () => {
  it("never weakens repository robustness floors", () => {
    for (const template of Object.values(OBJECTIVE_TEMPLATES)) {
      expect(template.minimum_mar).toBeGreaterThanOrEqual(0.4);
      expect(template.minimum_complete_wfa_windows).toBeGreaterThanOrEqual(3);
      expect(template.minimum_wfa_oos_trades).toBeGreaterThanOrEqual(50);
      expect(template.minimum_acceptance_oos_trades).toBeGreaterThanOrEqual(30);
      expect(template.monte_carlo_min_runs).toBeGreaterThanOrEqual(8000);
      expect(template.monte_carlo_horizon_months).toBeGreaterThanOrEqual(6);
      expect(template.minimum_net_profit_probability_percent).toBeGreaterThanOrEqual(70);
      expect(template.maximum_account_breach_probability_percent).toBeLessThanOrEqual(10);
      expect(template.forward_incubation_min_calendar_days).toBeGreaterThanOrEqual(90);
      expect(template.forward_incubation_min_trades).toBeGreaterThanOrEqual(30);
    }
  });
});

describe("final verdict matrix", () => {
  it("keeps candidate PASS separate from deployment authorization", () => {
    render(
      <VerdictDecisionMatrix
        scientificValidity="PASS"
        genericVerdict="PASS"
        accountEvaluations={[]}
      />,
    );

    expect(screen.getByText("Open independent candidate review. PASS remains candidate-only.")).toBeVisible();
    expect(screen.getByText("NOT AUTHORIZED")).toBeVisible();
  });

  it("fails closed when scientific evidence fails", () => {
    render(
      <VerdictDecisionMatrix
        scientificValidity="FAIL"
        genericVerdict="PASS"
        evidenceErrors={[]}
      />,
    );

    expect(screen.getByText(/Reject this variant/)).toBeVisible();
  });
});
