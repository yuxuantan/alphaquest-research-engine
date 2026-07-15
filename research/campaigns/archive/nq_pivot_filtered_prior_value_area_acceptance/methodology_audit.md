# Methodology Audit: nq_pivot_filtered_prior_value_area_acceptance

Date: 2026-06-30T11:55:30+08:00

Verdict: FAIL

## Source And Duplicate Review

This campaign was created after the direct NQ prior value-area acceptance campaign failed. It is a bounded composite: prior value-area acceptance remains the primary edge and a fixed completed 5/15-minute pivot-structure filter only rejects base signals. It is distinct from NQ pivot/MES campaigns because it uses no MES participation or crowding proxy.

## Pre-PnL Controls

- Five variants were authored before NQ PnL inspection.
- The density audit used the real `MarketStructureFilteredEntry` wrapper and passed all five variants before staged PnL.
- Signals use prior RTH value levels from the completed prior session, completed signal-bar orderflow, and completed pivot structure; entry is next-bar open or later.
- No rescue attempt was authorized or used.

## Validation Outcome

All five variants failed limited_core_grid_test. Best profitable-rate was midday_signed_two_sided_pivot_acceptance at 34/54 (0.6296296296296297), below the 0.70 gate. Across all official variants, 89/270 combinations were profitable, 39 benchmark-pass rows, and 0 Apex-rule-violating iterations. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

## Artifacts

- Campaign summary: `backtest-campaigns/nq_pivot_filtered_prior_value_area_acceptance/campaign_test_summary.json`
- Campaign results: `backtest-campaigns/nq_pivot_filtered_prior_value_area_acceptance/campaign_results.csv`
- Trade logs manifest: `backtest-campaigns/nq_pivot_filtered_prior_value_area_acceptance/trade_logs_manifest.csv`
- Equity curves manifest: `backtest-campaigns/nq_pivot_filtered_prior_value_area_acceptance/equity_curves_manifest.csv`
- WFA table: `backtest-campaigns/nq_pivot_filtered_prior_value_area_acceptance/wfa_table.csv`
- Monte Carlo summary: `backtest-campaigns/nq_pivot_filtered_prior_value_area_acceptance/monte_carlo_summary.json`

## Final Label

FAIL
