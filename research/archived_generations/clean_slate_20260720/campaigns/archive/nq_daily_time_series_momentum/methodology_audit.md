# Methodology Audit - NQ Daily Time-Series Momentum

Verdict: FAIL

## Scope

- Campaign: `nq_daily_time_series_momentum`
- Symbol: `NQ`
- Data: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Density audit: `research_artifacts/nq_daily_time_series_momentum_density_audit_20260622.md`
- Aggregate summary: `backtest-campaigns/nq_daily_time_series_momentum/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_daily_time_series_momentum/campaign_results.csv`

## Leakage Controls

- Trend direction uses only RTH closes recorded before the signal session.
- Signals at 10:00, 10:30, or 11:30 ET use completed bars and enter no earlier than the next bar open.
- Stop, target, and forced flatten are same-day rules from config.
- No current-session final close, future high/low, final VWAP, future volume, or overnight exposure is used.

## Test Discipline

- The five variants and parameter grids were fixed before PnL testing from pre-PnL density counts.
- Each variant used a 27-combination grid: one entry threshold, three stop settings, and three target settings.
- No rescue attempt was authorized or used.
- Full staged promotion required core, monkey, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation core/monkey, and acceptance OOS.

## Result

All five variants failed the limited core grid. The best top-row PF was only 1.02997 on `vol_norm_20d_trend_two_sided_1130`, which had 6/27 profitable combinations and did not clear the core gate.

## Decision

FAIL. No variant passed the full staged workflow. The campaign is rejected as a candidate strategy.
