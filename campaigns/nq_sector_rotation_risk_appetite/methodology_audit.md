# Methodology Audit - NQ Sector-Rotation Risk-Appetite Intraday

Verdict: FAIL

## Scope

- Campaign: `nq_sector_rotation_risk_appetite`
- Symbol: `NQ`
- Data: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Feature file: `data/external/nq_sector_rotation_features_20110103_20260612.csv`
- Density audit: `research_artifacts/nq_sector_rotation_risk_appetite_density_audit_20260622.md`
- Aggregate summary: `backtest-campaigns/nq_sector_rotation_risk_appetite/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_sector_rotation_risk_appetite/campaign_results.csv`

## Leakage Controls

- Sector ETF inputs are lagged one business day before the NQ session date.
- Rolling sector ranks are computed before the session-level as-of join.
- Signals use completed NQ bars and enter no earlier than the next bar open.
- Stop, target, and forced flatten are same-day rules from config.
- No current-session final range, final VWAP, future NQ bar, future ETF close, or post-entry sector state is used.

## Test Discipline

- The five variants and parameter grids were fixed before PnL testing from pre-PnL density counts.
- Each variant used a 27-combination grid: one sector-rank entry threshold, three stop settings, and three target settings.
- No rescue attempt was authorized or used.
- Full staged promotion required core, monkey, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation core/monkey, and acceptance OOS.

## Result

`growth_lead_long_1030` passed the limited core grid with 23/27 profitable combinations, but failed the limited monkey/randomized schedule gate with 28.6125% profitable schedules and median randomized net of -1465.0.

The other four variants failed the limited core grid:

| Variant | Core profitable | Top net | Top PF | Top trades | Top MAR |
|---|---:|---:|---:|---:|---:|
| cyclical_lead_long_1000 | 0/27 | -30.0 | 0.997156 | 133 | -0.008303 |
| defensive_lead_short_1000 | 0/27 | -1710.0 | 0.808081 | 157 | -0.502629 |
| defensive_rotation_short_1130 | 6/27 | 3715.0 | 1.24958 | 144 | 1.724353 |
| growth_acceleration_long_1330 | 0/27 | -835.0 | 0.884028 | 110 | -0.289516 |

## Decision

FAIL. No variant passed the full staged workflow. The campaign is rejected as a candidate strategy.
