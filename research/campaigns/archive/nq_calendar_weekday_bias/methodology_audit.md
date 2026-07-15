# Methodology Audit - NQ Calendar Weekday Bias

Verdict: FAIL

## Scope

- Campaign: `nq_calendar_weekday_bias`
- Symbol: `NQ`
- Data: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Density audit: `research_artifacts/nq_calendar_weekday_bias_density_audit_20260622.md`
- Aggregate summary: `backtest-campaigns/nq_calendar_weekday_bias/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_calendar_weekday_bias/campaign_results.csv`

## Leakage Controls

- Weekday is known before the trading session and contains no price-derived information.
- Signals use completed 5-minute NQ bars and enter no earlier than the next bar open.
- Stop, target, and forced flatten are same-day rules from config.
- No current-session final close, future high/low, final VWAP, future volume, or overnight exposure is used.

## Test Discipline

- The five weekday-pair mappings were fixed before PnL testing from calendar-anomaly literature and pre-PnL density counts.
- Each variant used a 9-combination grid: three stop settings and three target settings.
- No rescue attempt was authorized or used.
- Full staged promotion required core, monkey, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation core/monkey, and acceptance OOS.

## Result

All five variants failed the limited core grid. `thu_fri_lateweek_strength_1030` was closest at 6/9 profitable combinations, below the required 0.70 core breadth gate, with top PF only 1.141988.

## Decision

FAIL. No variant passed the full staged workflow. The campaign is rejected as a candidate strategy.
