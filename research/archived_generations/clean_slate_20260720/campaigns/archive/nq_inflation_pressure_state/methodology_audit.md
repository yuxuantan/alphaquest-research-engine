# NQ Inflation Pressure State Methodology Audit

Decision before staged PnL: approved for testing after pre-PnL density reform.

Duplicate screen: this is not a retest of BLS release-day drift, import/export price pressure, real-yield/breakeven, Treasury-rate shocks, industrial production, manufacturing orders, retail/inventory demand, housing construction, jobless claims, CFNAI, or orderflow families. The signal uses direct BEA/BLS/FRED CPI and PCE monthly inflation state variables with a conservative 45-calendar-day lag.

Lookahead controls:
- A session dated D may only use the latest PCEPI/PCEPILFE/CPIAUCSL/CPILFESL observation on or before D minus 45 calendar days.
- The signal is evaluated on the completed one-minute bar immediately before the configured entry time, with fills no earlier than the next bar open.
- No same-day monthly release, final session high/low, final VWAP, future inflation-data revision, or post-entry path data is used.

Known caveats:
- FRED files are current-vintage histories, not ALFRED point-in-time vintages. The 45-day observation lag reduces release-timing leakage but does not remove historical revision risk.
- Monthly inflation state may be stale, already priced, or conflated with real-rate and growth regimes.
- Inflation pressure can produce both risk-off discount-rate pressure and disinflation relief; robustness gates must reject unstable directionality.
- Same-bar stop/target conflicts remain pessimistic because tick path is not used.

Pre-PnL density:
- Initial grid failed density: `research_artifacts/nq_inflation_pressure_state_initial_density_rejected_20260701.md`.
- Final grid passed 45/45 rows: `research_artifacts/nq_inflation_pressure_state_density_audit_20260701.md`.
- No trade PnL, equity curve, stop, target, or staged result was inspected before the density reform.

Post-test decision:
- Decision: FAIL.
- All five variants failed limited_core_grid_test; 0 variants had at least one profitable iteration, but no variant met the 0.70 profitable-iteration stability threshold. No branch reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
- Campaign summary: `backtest-campaigns/nq_inflation_pressure_state/campaign_test_summary.json`.
