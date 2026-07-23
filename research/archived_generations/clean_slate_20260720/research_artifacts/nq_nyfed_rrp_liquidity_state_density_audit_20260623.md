# NQ NY Fed RRP Liquidity State Final Pre-PnL Density Audit

Date: 2026-06-23

Verdict: PASS FOR STAGED TESTING

This final audit counted only entry signals after the pre-PnL density reform. No NQ PnL, stop, target, monkey, WFA, Monte Carlo, prop simulation, or holdout result was inspected before this audit.

Prepared data and method:

- Source bars: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Feature file: `data/external/nyfed_rrp_liquidity_state_lag1_features_20140811_20260529.csv`
- Prepared bars: 229,086 NQ 5-minute RTH bars
- Sessions: 2,937
- Years at 252 sessions/year: 11.654762
- Date range: 2014-08-11 through 2026-05-29
- Latest-year check: latest 252 sessions through 2026-05-29
- Final variants: five RRP-drain short timing variants at 10:00, 11:30, 13:30, 14:30, and 15:00 ET
- Final entry threshold grid: `[0.125, 0.25]`

Result:

- Minimum full-history density: 72.245148 signals/year
- Minimum latest-252 density: 50 signals

CSV: `research_artifacts/nq_nyfed_rrp_liquidity_state_density_audit_20260623.csv`
