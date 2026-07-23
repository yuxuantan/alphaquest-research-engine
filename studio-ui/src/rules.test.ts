import { describe, expect, it } from "vitest";
import { buildRule } from "./pages/WizardPage";

const base = {
  feature: "close",
  lag: 0,
  conditionType: "cross",
  direction: "above",
  rollingFunction: "mean",
  window: 20,
  operator: "gt",
  threshold: 0,
  tuneThreshold: false,
  thresholdValues: "-3, -2, -1, 0, 1, 2, 3, 4",
  lower: 0,
  upper: 1,
  inclusive: true,
  signals: "both",
  secondFilter: false,
  filterFeature: "volume",
  filterOperator: "gt",
  filterThreshold: 100,
  booleanGroup: "all",
  signalStartTime: "09:30:00",
  signalEndTime: "15:45:00",
  maxTradesPerDay: 1,
  rthOnly: true,
};

describe("visual completed-bar compiler", () => {
  it("emits a true one-time crossing with a causal prior rolling reference", () => {
    const rule = buildRule(base, "5m");

    expect(rule.long_rule).toMatchObject({
      type: "cross",
      direction: "above",
      left: { source: "feature", name: "close", lag: 0 },
      right: {
        source: "rolling",
        function: "mean",
        window: 20,
        lag: 1,
        min_periods: 20,
      },
    });
    expect(rule.short_rule.direction).toBe("below");
    expect(rule.bar_interval_minutes).toBe(5);
  });

  it("supports lagged comparisons, frozen tunables, ranges, and Boolean groups", () => {
    const comparison = buildRule(
      {
        ...base,
        conditionType: "comparison",
        feature: "volume",
        lag: 2,
        threshold: 0,
        tuneThreshold: true,
        secondFilter: true,
      },
      "1m",
    );
    expect(comparison.long_rule.type).toBe("all");
    expect(comparison.long_rule.conditions[0].left.lag).toBe(2);
    expect(comparison.tunables[0].values).toHaveLength(8);

    const range = buildRule(
      { ...base, conditionType: "range", signals: "long" },
      "15m",
    );
    expect(range.long_rule.type).toBe("range");
    expect(range.short_rule).toBeNull();
  });
});
