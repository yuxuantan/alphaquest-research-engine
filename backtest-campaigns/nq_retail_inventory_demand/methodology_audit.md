# NQ Retail Inventory Demand Methodology Audit

Decision before staged PnL: approved for testing after pre-PnL density reform.

Duplicate screen: this is not a retest of consumer sentiment, industrial production, import/export pressure, CFNAI, EPU, EMV, or orderflow families. The signal uses direct FRED retail-sales and inventory/sales state variables with a conservative 45-calendar-day lag.

Lookahead controls:
- A session dated D may only use the latest RSAFS/RSXFS/ISRATIO/BUSINV observation on or before D minus 45 calendar days.
- The signal is evaluated on the completed one-minute bar immediately before the configured entry time, with fills no earlier than the next bar open.
- No same-day monthly release, final session high/low, final VWAP, future revision, or post-entry path data is used.

Known caveats:
- FRED files are current-vintage histories, not ALFRED point-in-time vintages. The 45-day lag reduces release-timing leakage but does not remove historical revision risk.
- Monthly retail and inventory state may be too stale for same-day NQ futures.
- Demand-strength and risk-premium interpretations can conflict; robustness gates must reject unstable directionality.
- Same-bar stop/target conflicts remain pessimistic because tick path is not used.

Pre-PnL density:
- Initial grid failed density: `research_artifacts/nq_retail_inventory_demand_initial_density_rejected_20260701.md`.
- Final grid passed 45/45 rows: `research_artifacts/nq_retail_inventory_demand_density_audit_20260701.md`.
- No trade PnL, equity curve, stop, target, or staged result was inspected before the density reform.

Post-test decision:
- Decision: FAIL.
- All five variants failed `limited_core_grid_test`; two variants had profitable top cells, but no variant met the required 0.70 profitable-iteration stability threshold.
- No branch reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
- Campaign summary: `backtest-campaigns/nq_retail_inventory_demand/campaign_test_summary.json`.
