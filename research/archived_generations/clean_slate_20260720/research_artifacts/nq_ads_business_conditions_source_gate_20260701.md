# NQ ADS / Business Conditions Source Gate

Date: 2026-07-01

Verdict: FAIL

This source gate screened a possible high-frequency business-conditions state edge before campaign launch.

Findings:

- `ADS` did not resolve through the FRED graph CSV endpoint during the source probe (`HTTP Error 404`).
- `USSLIND` resolved but ended at `2020-02-01`, so it is not current enough for the 2011-2026 NQ campaign scope.
- `CFNAI` is available through 2026-05 but is already represented by the failed `nq_chicagofed_cfnai_activity_pullback` campaign family.
- `ANFCI` and `NFCI` are available through 2026-06-19, but they are financial-conditions/stress indexes and overlap the already tested `nq_ofr_financial_stress_intraday`, volatility-stress, and credit-stress families.

Decision:

No new campaign launched. The available branch is either stale, unavailable through the tested public CSV path, or duplicate/adjacent to existing failed NQ activity/financial-stress campaigns.
