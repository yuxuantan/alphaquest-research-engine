/** Structured human input serialized into the existing immutable review contract. */
export const CLAIM_VERIFICATION_METHODS = {
  READ_PASSAGE: "Read source passage",
  COMPARE_TABLE: "Compared table values",
  CHECK_CONFLICT: "Compared conflicting passages or results",
  ASSESS_INFERENCE: "Assessed inference against source evidence",
} as const;

export interface ClaimVerification {
  method: string;
  location: string;
  finding: string;
  rationale: string;
  limitations: string;
}

export function newClaimVerification(): ClaimVerification {
  return { method: "", location: "", finding: "", rationale: "", limitations: "" };
}

export function claimVerificationComplete(review: ClaimVerification | undefined): boolean {
  return Boolean(review && Object.hasOwn(CLAIM_VERIFICATION_METHODS, review.method) &&
    review.location.trim() && review.finding.trim() && review.rationale.trim() && review.limitations.trim());
}

export function serializeClaimVerification(review: ClaimVerification) {
  if (!claimVerificationComplete(review)) throw new Error("Complete every claim verification field.");
  const paragraph = (value: string) => value.trim().replace(/\r\n?/g, "\n").replace(/\n/g, "\n  ");
  return {
    verification_method: `Method: ${CLAIM_VERIFICATION_METHODS[review.method as keyof typeof CLAIM_VERIFICATION_METHODS]}\nLocation: ${review.location.trim().replace(/\s+/g, " ")}`,
    notes: `Finding: ${paragraph(review.finding)}\nDecision rationale: ${paragraph(review.rationale)}\nLimitations or discrepancies: ${paragraph(review.limitations)}`,
  };
}
