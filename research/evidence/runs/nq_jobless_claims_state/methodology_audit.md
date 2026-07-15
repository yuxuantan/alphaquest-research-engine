# NQ Jobless Claims State Methodology Audit

Decision before staged PnL: approved for testing after pre-PnL density reform.

Duplicate screen: this is not a retest of BLS release-day drift, CFNAI, industrial production, manufacturing orders, retail/inventory demand, consumer sentiment, EMV, EPU, real-yield/breakeven, or orderflow families. The signal uses direct FRED/DOL weekly unemployment-insurance claims state variables with a conservative 7-calendar-day lag.

Lookahead controls:
- A session dated D may only use the latest ICSA/IC4WSA/CCSA/CC4WSA observation on or before D minus 7 calendar days.
- The signal is evaluated on the completed one-minute bar immediately before the configured entry time, with fills no earlier than the next bar open.
- No same-day weekly release, final session high/low, final VWAP, future jobless-claims revision, or post-entry path data is used.

Known caveats:
- FRED files are current-vintage histories, not ALFRED point-in-time vintages. The 7-day observation lag reduces release-timing leakage but does not remove historical revision risk.
- Weekly claims state may be stale, noisy, or already priced by the NQ session.
- Initial and continued claims can express level and momentum in opposite directions; robustness gates must reject unstable directionality.
- Same-bar stop/target conflicts remain pessimistic because tick path is not used.

Pre-PnL density:
- Initial grid failed density: `research_artifacts/nq_jobless_claims_state_initial_density_rejected_20260701.md`.
- Final grid passed 45/45 rows: `research_artifacts/nq_jobless_claims_state_density_audit_20260701.md`.
- No trade PnL, equity curve, stop, target, or staged result was inspected before the density reform.

Post-test decision:
- Decision: FAIL.
- All five variants failed limited_core_grid_test; claims_rising_short_1030 had only 1/27 profitable iterations, and no variant met the 0.70 profitable-iteration stability threshold. No branch reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
- Campaign summary: `backtest-campaigns/nq_jobless_claims_state/campaign_test_summary.json`.
