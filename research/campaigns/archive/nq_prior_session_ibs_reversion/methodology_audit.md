# Methodology Audit: nq_prior_session_ibs_reversion

Date: 2026-06-30T11:45:00+08:00

Verdict: FAIL

## Source And Duplicate Review

Prior-session IBS uses the prior close location within the completed prior RTH high-low range. It is distinct from raw NQ daily return reversal, overnight gap reversal, prior-session breakout, and value-area/orderflow families.

## Pre-PnL Controls

- Five variants were authored before NQ PnL inspection.
- Signals use completed prior RTH high, low, and close, then wait for the configured completed 5-minute signal bar.
- Pre-PnL density pruning removed sparse IBS threshold/range corners; no NQ PnL was inspected before pruning.
- No rescue attempt was authorized or used.

## Validation Outcome

All five variants failed limited_core_grid_test. Best profitable-rate was delayed_low_ibs_long_range_filtered at 6/9 (0.6666666666666666), below the 0.70 gate. Across all official variants, 56/171 combinations were profitable, 17 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

## Artifacts

- Campaign summary: `backtest-campaigns/nq_prior_session_ibs_reversion/campaign_test_summary.json`
- Campaign results: `backtest-campaigns/nq_prior_session_ibs_reversion/campaign_results.csv`
- Trade logs manifest: `backtest-campaigns/nq_prior_session_ibs_reversion/trade_logs_manifest.csv`
- Equity curves manifest: `backtest-campaigns/nq_prior_session_ibs_reversion/equity_curves_manifest.csv`
- WFA table: `backtest-campaigns/nq_prior_session_ibs_reversion/wfa_table.csv`
- Monte Carlo summary: `backtest-campaigns/nq_prior_session_ibs_reversion/monte_carlo_summary.json`

## Final Label

FAIL
