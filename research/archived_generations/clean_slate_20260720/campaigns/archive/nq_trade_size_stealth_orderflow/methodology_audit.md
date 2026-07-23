# Methodology Audit: nq_trade_size_stealth_orderflow

Date: 2026-06-30T11:33:00+08:00

Verdict: FAIL

## Source And Duplicate Review

The edge is large/medium trade-size segmented orderflow disagreement versus residual smaller-flow pressure. It is distinct from existing failed NQ total signed-flow, VPIN, MES crowding, semivariance/orderflow, variance-ratio/orderflow, cross-index, and opening-drive families because this campaign requires large10 or large20 bucket pressure to dominate or oppose residual smaller-flow pressure.

## Pre-PnL Controls

- Five variants were authored before NQ PnL inspection.
- All variants use completed 1-minute rolling orderflow windows and next-bar execution.
- Density audit passed before staged PnL; weakest declared corner had 58.621558 signals/year and 70 latest-252-session signals.
- No density-only grid change was needed.
- No rescue attempt was authorized or used.

## Validation Outcome

All five variants failed limited_core_grid_test. Best profitable-rate was large20_not_aligned_long_1000 at 45/81 (0.5555555555555556), below the 0.70 gate. Across all official variants, 98/405 combinations were profitable, 16 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

## Artifacts

- Campaign summary: `backtest-campaigns/nq_trade_size_stealth_orderflow/campaign_test_summary.json`
- Campaign results: `backtest-campaigns/nq_trade_size_stealth_orderflow/campaign_results.csv`
- Trade logs manifest: `backtest-campaigns/nq_trade_size_stealth_orderflow/trade_logs_manifest.csv`
- Equity curves manifest: `backtest-campaigns/nq_trade_size_stealth_orderflow/equity_curves_manifest.csv`
- WFA table: `backtest-campaigns/nq_trade_size_stealth_orderflow/wfa_table.csv`
- Monte Carlo summary: `backtest-campaigns/nq_trade_size_stealth_orderflow/monte_carlo_summary.json`

## Final Label

FAIL
