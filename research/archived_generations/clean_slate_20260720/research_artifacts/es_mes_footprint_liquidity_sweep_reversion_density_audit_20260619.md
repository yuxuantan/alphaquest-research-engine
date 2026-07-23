# ES MES Footprint Liquidity Sweep Reversion Density Audit

Date: 2026-06-19

Purpose: verify likely trade frequency before any PnL backtest. This uses only the local merged ES footprint + MES participation cache and applies the one-trade-per-day rule used by the entry module.

Data: `data/cache/orderflow/es_mes_footprint_liquidity_sweep_1m_20190506_20260609_full_rth_ny.parquet`
Rows: 685,230
Period: 2019-05-06 09:30:00 to 2026-06-09 15:59:00 (7.09 years by calendar span)
Cost policy: local cache only; no paid data download.

## Selected Rolling Variants

| concept                | variant_id                                     | min_annualized_signal_count | median_annualized_signal_count | max_annualized_signal_count | tested_entry_combinations | decision |
| ---------------------- | ---------------------------------------------- | --------------------------- | ------------------------------ | --------------------------- | ------------------------- | -------- |
| selected_rolling_range | rolling30_full_session_notional_two_sided      | 89.94                       | 105.73                         | 123.77                      | 4                         | eligible |
| selected_rolling_range | rolling30_full_session_trade_large10_two_sided | 93.04                       | 105.23                         | 119.96                      | 4                         | eligible |
| selected_rolling_range | rolling45_full_session_trade_large10_two_sided | 78.94                       | 90.50                          | 104.32                      | 4                         | eligible |
| selected_rolling_range | rolling45_midday_notional_two_sided            | 76.26                       | 88.67                          | 104.60                      | 4                         | eligible |
| selected_rolling_range | rolling60_midday_notional_two_sided            | 69.64                       | 81.55                          | 96.70                       | 4                         | eligible |

## Rejected Level Forms Before PnL

| concept                     | variant_id                      | min_annualized_signal_count | median_annualized_signal_count | max_annualized_signal_count | tested_entry_combinations | decision       |
| --------------------------- | ------------------------------- | --------------------------- | ------------------------------ | --------------------------- | ------------------------- | -------------- |
| rejected_pre_pnl_level_form | or30_full_session_notional      | 23.82                       | 27.77                          | 32.42                       | 4                         | reject_density |
| rejected_pre_pnl_level_form | or60_midday_notional            | 21.43                       | 25.73                          | 30.45                       | 4                         | reject_density |
| rejected_pre_pnl_level_form | prior_day_full_session_notional | 10.57                       | 12.62                          | 14.80                       | 4                         | reject_density |

Decision: selected rolling-range variants are eligible for testing because every entry-parameter combination is above 50 annualized one-trade-per-day signals. The alternative level forms are shown as a pre-PnL density check, not as failed backtests.

Full entry-parameter density grid: `research_artifacts/es_mes_footprint_liquidity_sweep_reversion_density_audit_20260619.csv`
