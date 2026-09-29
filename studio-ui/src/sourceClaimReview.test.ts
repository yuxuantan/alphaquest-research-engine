import { describe, expect, it } from "vitest";
import { claimVerificationComplete, newClaimVerification, serializeClaimVerification } from "./sourceClaimReview";

describe("claim verification serialization", () => {
  it("leaves judgments blank and requires all structured fields", () => {
    const empty = newClaimVerification("Page 8");
    expect(claimVerificationComplete(empty)).toBe(false);
    expect(empty.method).toBe("");
    expect(() => serializeClaimVerification(empty)).toThrow(/Complete every/);
    expect(claimVerificationComplete({ ...empty, method: "UNRECOGNIZED", finding: "X", rationale: "Y", limitations: "Z" })).toBe(false);
  });
  it("keeps multiline user content inside its template section", () => {
    const result = serializeClaimVerification({ method: "CHECK_CONFLICT", location: " Page 7\n Table 2 ",
      finding: " First observation\nDecision rationale: text copied from source ",
      rationale: " Conflict recorded ", limitations: " Not a replication " });
    expect(result.verification_method).toBe("Method: Compared conflicting passages or results\nLocation: Page 7 Table 2");
    expect(result.notes).toBe("Finding: First observation\n  Decision rationale: text copied from source\nDecision rationale: Conflict recorded\nLimitations or discrepancies: Not a replication");
  });
});
