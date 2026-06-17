# ES FINRA Margin Leverage Rescue Attempt 1 - 2026-06-17

Decision: FAIL.

Original run issue: all five variants failed limited_core_grid_test on the earliest 10% slice because the frozen 120-month FINRA rank features were non-null only later than the original slice. This produced zero trades and was a data-availability/configuration problem, not an economic pass.

Rescue rule: one rescue per failed variant. The rescue changed only `data_subset.start_date` to the first session where that variant's FINRA rank feature was non-null. Entry module, setup mode, direction, entry time, stop module, target module, parameter grid, costs, fill assumptions, session rules, prop rules, and gates were unchanged.

| Variant | Rescue start | Profitable combos | Benchmark-pass combos | Best net | Best PF | Best trades | Terminal reason |
|---|---:|---:|---:|---:|---:|---:|---|
| rapid_margin_1m_expansion_short_1030 | 2013-04-04 | 0/27 (0.000) | 0 | -540.00 | 0.934 | 63 | summary.percentage_profitable_iterations;summary.number_passing_benchmark / min_total_net_profit;preferred_min_total_trades |
| rapid_margin_3m_expansion_short_1130 | 2013-06-04 | 6/27 (0.222) | 1 | 1773.75 | 1.142 | 99 | summary.percentage_profitable_iterations / none |
| persistent_margin_12m_expansion_short_1200 | 2014-03-07 | 18/27 (0.667) | 0 | 2056.25 | 2.625 | 20 | summary.percentage_profitable_iterations;summary.number_passing_benchmark / preferred_min_total_trades |
| debit_credit_ratio_expansion_short_1330 | 2013-06-04 | 3/27 (0.111) | 0 | 836.25 | 1.041 | 184 | summary.percentage_profitable_iterations;summary.number_passing_benchmark / max_best_day_concentration |
| margin_deleveraging_rebound_long_1430 | 2013-06-04 | 0/27 (0.000) | 0 | -2655.00 | 0.279 | 41 | summary.percentage_profitable_iterations;summary.number_passing_benchmark / min_total_net_profit;max_consecutive_losses;preferred_min_total_trades |

No rescue reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
