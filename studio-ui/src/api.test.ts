import { describe, expect, it } from "vitest";
import { normalizeBootstrap, unwrapArray } from "./api";

describe("browser contract normalization", () => {
  it("keeps operational job state separate from scientific verdict", () => {
    const result = normalizeBootstrap({
      drafts: [],
      campaigns: [],
      reviews: [],
      jobs: [
        {
          job_id: "job-1",
          operational_state: "SUCCEEDED",
          research_verdict: "FAIL",
        },
      ],
    });
    expect(result.jobs[0].state).toBe("SUCCEEDED");
    expect(result.jobs[0].research_verdict).toBe("FAIL");
  });

  it("fails soft when optional bootstrap collections are absent", () => {
    const result = normalizeBootstrap({ workspace: { name: "fresh" } });
    expect(result.drafts).toEqual([]);
    expect(result.campaigns).toEqual([]);
    expect(result.reviews).toEqual([]);
    expect(result.jobs).toEqual([]);
  });

  it("unwraps list endpoints without leaking transport wrappers", () => {
    expect(unwrapArray({ jobs: [{ job_id: "1" }] }, "jobs")).toEqual([
      { job_id: "1" },
    ]);
  });
});
