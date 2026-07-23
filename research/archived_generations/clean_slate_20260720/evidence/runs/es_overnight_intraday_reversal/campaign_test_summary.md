# Campaign Test Summary

- Campaign: `es_overnight_intraday_reversal`
- Decision: `FAIL`
- Rescue attempt: `not_used`
- Reason: all five predeclared variants failed the limited core grid gate.

| Variant | Profitable Combos | Profit Rate | Benchmark Passes | Top Net | Top PF | Top Trades/Yr | Top MAR | Top Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `first15_confirm_reversal_1000` | 14/81 | 0.172840 | 0 | 1982.5 | 1.129639 | 65.39 | 0.364669 | min_profit_factor;min_mar;preferred_min_total_trades |
| `first30_noncontinuation_1000` | 2/81 | 0.024691 | 0 | 430.0 | 1.038985 | 54.02 | 0.124241 | min_profit_factor;min_expectancy_r;min_mar;preferred_min_total_trades;max_best_day_concentration;min_positive_month_rate |
| `first5_confirm_reversal_1000` | 1/81 | 0.012346 | 0 | 152.5 | 1.028652 | 28.38 | 0.063476 | min_profit_factor;min_expectancy_r;min_mar;min_trades_per_year;preferred_min_total_trades;max_best_day_concentration |
| `high_overnight_first15_short_1000` | 33/81 | 0.407407 | 0 | 3842.5 | 1.420405 | 36.92 | 1.450436 | min_trades_per_year;preferred_min_total_trades |
| `low_overnight_first15_long_1000` | 7/81 | 0.086420 | 0 | 1147.5 | 1.152644 | 39.97 | 0.452080 | min_profit_factor;min_mar;min_trades_per_year;preferred_min_total_trades;min_positive_month_rate |

No candidate_strategy_report.md was created because no variant reached promotion criteria.
