# NQ Industrial Production State Methodology Audit

Decision before staged PnL: approved for testing after pre-PnL density reform.

Duplicate screen: this is not a retest of CFNAI, consumer sentiment, BLS release-day drift, EMV, EPU, real-yield/breakeven, credit spread, or orderflow families. The signal uses direct FRED industrial-production and capacity-utilization monthly state variables with a conservative 45-calendar-day lag.

Lookahead controls:
- A session dated D may only use the latest IPMAN/INDPRO/CUMFNS observation on or before D minus 45 calendar days.
- The signal is evaluated on the completed one-minute bar immediately before the configured entry time, with fills no earlier than the next bar open.
- No same-day monthly release, final session high/low, final VWAP, future industrial-production revision, or post-entry path data is used.

Known caveats:
- FRED files are current-vintage histories, not ALFRED point-in-time vintages. The 45-day observation lag reduces release-timing leakage but does not remove historical revision risk.
- Monthly real-activity state may be too stale for same-day NQ futures.
- Weak-activity and strong-activity variants can express opposite risk-premium interpretations; robustness gates must reject unstable directionality.
- Same-bar stop/target conflicts remain pessimistic because tick path is not used.

Pre-PnL density:
- Initial grid failed density: `research_artifacts/nq_industrial_production_state_initial_density_rejected_20260701.md`.
- Final grid passed 45/45 rows: `research_artifacts/nq_industrial_production_state_density_audit_20260701.md`.
- No trade PnL, equity curve, stop, target, or staged result was inspected before the density reform.
