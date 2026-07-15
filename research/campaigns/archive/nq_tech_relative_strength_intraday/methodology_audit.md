# Methodology Audit - NQ Tech Relative Strength Intraday

Verdict: FAIL

## Scope

- Campaign: `nq_tech_relative_strength_intraday`
- Symbol: `NQ`
- Data: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Feature file: `data/external/nq_tech_relative_strength_features_20110103_20260612.csv`
- Density audit: `research_artifacts/nq_tech_relative_strength_density_audit_20260622.md`
- Aggregate summary: `backtest-campaigns/nq_tech_relative_strength_intraday/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_tech_relative_strength_intraday/campaign_results.csv`

## Leakage Controls

- XLK and SPY inputs are lagged one business day before the NQ session date.
- Rolling ranks are computed before the session-level as-of join.
- Signals use completed NQ bars and enter no earlier than the next bar open.
- Stop, target, and forced flatten are same-day rules from config.
- No current-session final range, final VWAP, future NQ bar, future ETF close, or post-entry ETF state is used.

## Test Discipline

- The five variants and parameter grids were fixed before PnL testing from pre-PnL density counts.
- Four variants used 27-combination grids and the attention variant used an 81-combination grid.
- No rescue attempt was authorized or used.
- Full staged promotion required core, monkey, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation core/monkey, and acceptance OOS.

## Result

`tech_5d_weakness_short_1130` passed the limited core grid with 20/27 profitable combinations, but failed the limited monkey/randomized schedule gate with 18.85% profitable schedules and median randomized net of -2370.0.

The other four variants failed the limited core grid:

| Variant | Core profitable | Top net | Top PF | Top trades | Top MAR |
|---|---:|---:|---:|---:|---:|
| tech_1d_strength_long_1000 | 0/27 | -4812.5 | 0.712429 | 139 | -0.458102 |
| tech_1d_weakness_short_1000 | 0/27 | -5292.5 | 0.735771 | 146 | -0.468684 |
| tech_5d_strength_long_1030 | 3/27 | 1095.0 | 1.044162 | 182 | 0.172597 |
| tech_attention_strength_long_1330 | 0/81 | -2232.5 | 0.631296 | 64 | -0.451087 |

## Decision

FAIL. No variant passed the full staged workflow. The campaign is rejected as a candidate strategy.
