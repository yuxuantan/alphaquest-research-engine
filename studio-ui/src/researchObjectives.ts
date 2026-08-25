export const OBJECTIVE_TEMPLATES = {
  generic_candidate: {
    label: "Generic research candidate",
    description: "Repository-safe baseline for determining whether an edge merits promotion.",
    evaluation_horizon_months: 24,
    minimum_annualized_return_percent: 20,
    minimum_mar: 0.4,
    maximum_drawdown_percent: 10,
    minimum_complete_wfa_windows: 3,
    minimum_wfa_oos_trades: 50,
    minimum_acceptance_oos_trades: 30,
    monte_carlo_min_runs: 8000,
    monte_carlo_horizon_months: 6,
    minimum_net_profit_probability_percent: 70,
    maximum_account_breach_probability_percent: 10,
    forward_incubation_min_calendar_days: 90,
    forward_incubation_min_trades: 30,
    maximum_variants: 5,
  },
  conservative_account: {
    label: "Conservative account candidate",
    description: "Tighter drawdown and robustness objectives for constrained account deployment.",
    evaluation_horizon_months: 36,
    minimum_annualized_return_percent: 15,
    minimum_mar: 0.75,
    maximum_drawdown_percent: 7.5,
    minimum_complete_wfa_windows: 4,
    minimum_wfa_oos_trades: 75,
    minimum_acceptance_oos_trades: 50,
    monte_carlo_min_runs: 10000,
    monte_carlo_horizon_months: 12,
    minimum_net_profit_probability_percent: 80,
    maximum_account_breach_probability_percent: 5,
    forward_incubation_min_calendar_days: 120,
    forward_incubation_min_trades: 50,
    maximum_variants: 3,
  },
} as const;

export type ObjectiveTemplateKey = keyof typeof OBJECTIVE_TEMPLATES;

export function buildResearchObjectives(
  templateKey: ObjectiveTemplateKey,
  title: string,
) {
  const template = OBJECTIVE_TEMPLATES[templateKey];
  const deadline = new Date();
  deadline.setUTCMonth(deadline.getUTCMonth() + 6);
  return {
    schema: "alphaquest.research-objectives/v1",
    development_goal: `Determine whether ${title.trim()} has enough causal and robust evidence to become a candidate strategy.`,
    development_deadline: deadline.toISOString().slice(0, 10),
    evaluation_horizon_months: template.evaluation_horizon_months,
    minimum_annualized_return_fraction:
      template.minimum_annualized_return_percent / 100,
    minimum_mar: template.minimum_mar,
    maximum_drawdown_fraction: template.maximum_drawdown_percent / 100,
    minimum_complete_wfa_windows: template.minimum_complete_wfa_windows,
    minimum_wfa_oos_trades: template.minimum_wfa_oos_trades,
    minimum_acceptance_oos_trades: template.minimum_acceptance_oos_trades,
    monte_carlo_min_runs: template.monte_carlo_min_runs,
    monte_carlo_horizon_months: template.monte_carlo_horizon_months,
    minimum_net_profit_probability:
      template.minimum_net_profit_probability_percent / 100,
    maximum_account_breach_probability:
      template.maximum_account_breach_probability_percent / 100,
    forward_incubation_min_calendar_days:
      template.forward_incubation_min_calendar_days,
    forward_incubation_min_trades: template.forward_incubation_min_trades,
    maximum_variants: template.maximum_variants,
    abandonment_rules: [
      "Abandon the edge when the governed scientific test suite returns terminal FAIL.",
      "Stop when data, timing, mechanics, or evidence integrity cannot be established without ambiguity.",
    ],
    retirement_rules: [
      "Retire a candidate when forward evidence breaches its frozen risk or performance limits.",
    ],
    confirmed: true,
  };
}
