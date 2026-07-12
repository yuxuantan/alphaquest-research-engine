# Verdict Semantics

## PASS

The configured workflow passed its recorded objective gates. This means candidate strategy only. It does not mean ready to trade.

## FAIL

A required gate failed, the campaign was rejected before PnL, or a terminal methodology rule was violated. Preserve the evidence and ledger entry.

## NEEDS MANUAL REVIEW

Evidence is incomplete, ambiguous, inconsistent, or lacks a terminal staged verdict. Do not promote or delete it until reviewed.

Registry lifecycle labels such as `active`, `candidate`, and `closed` are navigation states. The immutable run verdict remains authoritative for that run.
