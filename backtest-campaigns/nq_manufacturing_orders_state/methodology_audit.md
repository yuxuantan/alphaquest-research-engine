# NQ Manufacturing Orders State Methodology Audit

Decision before staged PnL: approved for testing after pre-PnL density reform.

Duplicate screen: this is not a retest of industrial production, retail/inventory demand, CFNAI, consumer sentiment, BLS release-day drift, EMV, EPU, real-yield/breakeven, or orderflow families. The signal uses direct Census/FRED manufacturing new-orders monthly state variables with a conservative 45-calendar-day lag.

Lookahead controls:
- A session dated D may only use the latest AMTMNO/DGORDER/NEWORDER/AMXTNO observation on or before D minus 45 calendar days.
- The signal is evaluated on the completed one-minute bar immediately before the configured entry time, with fills no earlier than the next bar open.
- No same-day monthly release, final session high/low, final VWAP, future manufacturing-orders revision, or post-entry path data is used.

Known caveats:
- FRED files are current-vintage histories, not ALFRED point-in-time vintages. The 45-day observation lag reduces release-timing leakage but does not remove historical revision risk.
- Monthly manufacturing-orders state may be too stale for same-day NQ futures.
- New-orders strength and weakness can express opposite growth-momentum and risk-premium interpretations; robustness gates must reject unstable directionality.
- Same-bar stop/target conflicts remain pessimistic because tick path is not used.

Pre-PnL density:
- Initial grid failed density: `research_artifacts/nq_manufacturing_orders_state_initial_density_rejected_20260701.md`.
- Final grid passed 45/45 rows: `research_artifacts/nq_manufacturing_orders_state_density_audit_20260701.md`.
- No trade PnL, equity curve, stop, target, or staged result was inspected before the density reform.

Post-test decision:
- Decision: FAIL.
- All five variants failed limited_core_grid_test; 4 variants had profitable top cells, but no variant met the 0.70 profitable-iteration stability threshold. No branch reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
- Campaign summary: `backtest-campaigns/nq_manufacturing_orders_state/campaign_test_summary.json`.
