# NQ Quarterly Expiration Pressure Methodology Audit

Verdict: FAIL.

This campaign was authored as a direct NQ transfer of the ES quarterly expiration pressure edge before any NQ PnL inspection. It kept exactly five variants, no entry tunables, one stop parameter, one target parameter, and rescue disabled.

No-lookahead review: signal dates are deterministic third-Friday quarterly expiration dates plus fixed day offsets; signal times are fixed per variant; the entry module uses the completed one-minute bar ending at the signal time and would enter at the next bar open. No realized settlement, final high/low, volume spike, VWAP, or post-signal return is used.

Data-quality result: the pre-PnL event audit found complete signal and entry bars for the two expiration-Friday variants, but missing expected event bars for the Monday-prior, Monday-after, and Thursday-prior variants. The Monday-prior missing dates include multiple apparent cache gaps on roll Mondays, so staged PnL was not run.

Scientific-integrity decision: dropping the missing variants or retaining only the complete expiration-Friday variants after this audit would change the predeclared five-variant edge. The campaign is closed before PnL.

Primary audit: `research_artifacts/nq_quarterly_expiration_pressure_event_density_audit_20260630.md`.
Campaign summary: `backtest-campaigns/nq_quarterly_expiration_pressure/campaign_test_summary.json`.
