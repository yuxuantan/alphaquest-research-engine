import { describe, expect, it } from "vitest";

import {
  formatEvidenceTimestamp,
  formatTradeDuration,
  formatUsdPnl,
  MECHANICS_EVIDENCE_BADGE,
  mechanicsAnnotationFormState,
  REVIEW_QUEUE_HELP,
  shouldShowSingleTargetFallback,
} from "./ReviewsPage";
import { resolveStrategyEvidencePanels } from "../strategyEvidence";

describe("review queue explanations", () => {
  it("separates mechanics, candidate, and indexed governance scopes", () => {
    expect(REVIEW_QUEUE_HELP.mechanics).toContain("unlock performance testing");
    expect(REVIEW_QUEUE_HELP.mechanics).toContain("does not judge profitability");
    expect(REVIEW_QUEUE_HELP.candidate).toContain("not approval for live trading");
    expect(REVIEW_QUEUE_HELP.items).toContain("does not unblock");
  });
});

describe("review evidence timezone formatting", () => {
  it("normalizes UTC and offset timestamps to New York summer time", () => {
    expect(
      formatEvidenceTimestamp(
        "2025-07-14T14:25:18.818Z",
        "America/New_York",
      ),
    ).toBe("2025-07-14 10:25:18.818 GMT-4");
    expect(
      formatEvidenceTimestamp(
        "2025-07-14 10:25:18.818457657-04:00",
        "America/New_York",
      ),
    ).toBe("2025-07-14 10:25:18.818457657 GMT-4");
  });

  it("uses the correct daylight-saving offset for the timestamp date", () => {
    expect(
      formatEvidenceTimestamp(
        "2025-12-15T15:25:18Z",
        "America/New_York",
      ),
    ).toBe("2025-12-15 10:25:18 GMT-5");
  });
});

describe("mechanics annotation form state", () => {
  it("restores a saved review when its sampled trade is reopened", () => {
    expect(
      mechanicsAnnotationFormState({
        trade_evidence: {
          annotation: {
            reviewer_status: "Needs deeper review",
            reviewer_notes: "Check the AOI tap manually",
          },
        },
      }),
    ).toEqual({
      status: "Needs deeper review",
      notes: "Check the AOI tap manually",
    });
  });

  it("starts an unreviewed sampled trade with a clean form", () => {
    expect(mechanicsAnnotationFormState({ trade_evidence: {} })).toEqual({
      status: "Correct",
      notes: "",
    });
  });
});

describe("strategy-neutral mechanics evidence presentation", () => {
  it("uses a hash-bound badge rather than naming a historical implementation", () => {
    expect(MECHANICS_EVIDENCE_BADGE).toBe("Hash-bound evidence");
    expect(MECHANICS_EVIDENCE_BADGE).not.toContain("v18");
  });

  it("suppresses the single-target fallback when v04 retains T1 and T2", () => {
    const panels = resolveStrategyEvidencePanels({
      metadata: {
        strategy_id: "yush_adaptive_orderflow_range_v4",
        variant_id: "v04",
      },
      strategy_context: {
        target_1_price: 7489.25,
        target_2_price: 7479.75,
      },
    });

    expect(shouldShowSingleTargetFallback(panels)).toBe(false);
    expect(
      shouldShowSingleTargetFallback([
        { rows: [{ key: "entry_trigger_price" }] },
      ]),
    ).toBe(true);
  });
});

describe("mechanics trade P&L formatting", () => {
  it("shows signed USD amounts and preserves a neutral zero", () => {
    expect(formatUsdPnl(125.5)).toBe("+$125.50");
    expect(formatUsdPnl(-81.25)).toBe("-$81.25");
    expect(formatUsdPnl(0)).toBe("$0.00");
  });

  it("does not invent P&L when the frozen evidence has no value", () => {
    expect(formatUsdPnl(null)).toBe("Not recorded");
    expect(formatUsdPnl("not-a-number")).toBe("Not recorded");
  });
});

describe("mechanics trade duration formatting", () => {
  it("summarizes the exact interval between entry and exit", () => {
    expect(
      formatTradeDuration(
        "2026-05-08T15:00:00.004Z",
        "2026-05-08T15:35:23.903Z",
      ),
    ).toBe("35m 24s");
    expect(
      formatTradeDuration(
        "2026-05-08T15:00:00Z",
        "2026-05-08T16:02:03Z",
      ),
    ).toBe("1h 2m 3s");
  });

  it("fails closed when either timestamp is missing or reversed", () => {
    expect(formatTradeDuration(null, "2026-05-08T16:02:03Z")).toBe(
      "Not recorded",
    );
    expect(
      formatTradeDuration(
        "2026-05-08T16:02:03Z",
        "2026-05-08T15:00:00Z",
      ),
    ).toBe("Not recorded");
  });
});
