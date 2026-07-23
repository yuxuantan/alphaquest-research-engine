import { describe, expect, it } from "vitest";

import {
  formatEvidenceTimestamp,
  mechanicsAnnotationFormState,
} from "./ReviewsPage";

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
