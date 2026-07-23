# ES Volatility-Managed Intraday Premium Rescue Attempt 1

Date: 2026-06-16

Decision: FAIL

## Scope

Campaign: `es_volatility_managed_intraday_premium`

The rescue was allowed under the per-failed-variant rule. Each failed variant
received exactly one rescue. The rescues changed only existing fixed parameters
or declared volatility-threshold, stop, and target parameter ranges.

No rescue changed the lagged volatility feature construction, the one-session
feature shift, the entry module, stop module, target module, timeframe, data
window, costs, fill assumptions, prop-rule gates, or staged validation gates.

## Source Data

- ES local Sierra RTH cache:
  `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Lagged volatility feature CSV:
  `data/external/es_lagged_volatility_features_20110103_20260609.csv`
- Feature rows: `3817`
- Valid rank rows: `3739`
- Lookahead control: every volatility feature is shifted one RTH session, so
  a signal uses only information available after the prior RTH close.

## Rescue Results

| Variant | Terminal stage | Core profitable rate | Benchmark pass rate | Top net | Top PF | Top trades | Monkey/stress result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `low_20d_vol_open_long_1000` | `limited_core_grid_test` | `0.5277777777777778` | `0.0` | `2298.75` | `1.4162516976007242` | `54` | not reached |
| `low_10d_range_midmorning_long_1030` | `limited_monkey_test` | `0.7222222222222222` | `0.3888888888888889` | `3163.75` | `1.322749298648304` | `91` | monkey `percentage_profitable=0.24`, `median_net_profit=-2081.25`; stress `percentage_profitable=0.9866666666666667`; one-tick-worse net `532.5` |
| `low_5d_abs_move_lunch_long_1200` | `limited_core_grid_test` | `0.07407407407407407` | `0.0` | `165.0` | `1.0973451327433628` | `22` | not reached |
| `low_downside20_afternoon_long_1330` | `limited_core_grid_test` | `0.037037037037037035` | `0.0` | `76.25` | `1.0295256534365924` | `36` | not reached |
| `vol_downshift_late_morning_long_1100` | `limited_core_grid_test` | `0.2222222222222222` | `0.0` | `1718.75` | `1.0651658767772512` | `200` | not reached |

## Conclusion

FAIL. The strongest rescue passed the core profitable-combo gate but failed the
random-placebo monkey requirement with only `24%` profitable runs and a negative
median net result. No variant earned WFA, Monte Carlo, simulated incubation, or
frozen validation. No candidate strategy report was created.

Primary aggregate report:
`backtest-campaigns/es_volatility_managed_intraday_premium/campaign_test_summary.json`.
