# NQ Household Debt-Service State Density Rejection

Date: 2026-07-02

Verdict: FAIL

This pre-campaign screen tested whether household debt-service and financial-obligation burden could support one NQ campaign with exactly five distinct variants.

Source checks:

- `TDSP`, `MDSP`, and `CDSP` resolve through FRED and are current through `2026-01-01`.
- `FODSP` resolves but is stale, ending at `2023-07-01`, so it was excluded from a current 2011-2026 NQ campaign.
- Household debt-to-GDP style series were not used because the screened debt-service edge needed current quarterly service/obligation burden inputs.

Density checks:

- Low total debt-service rank, low mortgage debt-service rank, low consumer debt-service rank, and low non-mortgage service rank cleared the pre-PnL density screen using a 120-calendar-day lag and rank thresholds `[0.50, 0.55, 0.60]` interpreted as low-rank cutoffs.
- High debt-service stress and four-quarter change expressions did not clear all full, limited-core, and latest-252 windows.
- The non-mortgage service proxy is mechanically equivalent to consumer debt service in the available screened series set, so it is not a defensible separate fifth variant.

Decision:

No campaign launched. The current public source set did not produce five distinct, density-valid variants without duplicating the same low consumer debt-service expression.
