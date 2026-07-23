# ES FOMC Pre-Announcement Drift Rescue Attempt 1

Date: 2026-06-16

Decision: FAIL

## Scope

Campaign: `es_fomc_pre_announcement_drift`

The rescue was allowed under the clarified per-failed-variant rule. Each failed
variant received exactly one rescue. The rescues changed only existing fixed
parameters or declared stop/target/filter parameter ranges inside the existing
modules.

No rescue changed the economic edge, FOMC event-calendar inclusion rule,
entry module, stop module, target module, timeframe, data window, costs, fill
assumptions, prop-rule gates, or staged validation gates.

## Source Data

- ES local Sierra RTH cache:
  `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Scheduled FOMC calendar:
  `data/external/fomc_scheduled_decision_dates_20110101_20260609.csv`
- Calendar rows: `122`
- Calendar span: `2011-01-26` through `2026-04-29`
- Exclusions: unscheduled meetings, cancelled meetings, notation votes, and
  conference calls.

## Rescue Results

| Variant | Terminal stage | Core profitable rate | Top net | Top PF | Top trades | Monkey/stress result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `decision_day_open_long_1000` | `limited_monkey_test` | `0.75` | `295.0` | `1.2972292191435768` | `11` | monkey `percentage_profitable=0.33666666666666667`, `median_net_profit=-298.75`; stress `percentage_profitable=0.6166666666666667`; one-tick-worse net `-80.0` |
| `decision_day_late_morning_long_1130` | `limited_core_grid_test` | `0.0` | `-342.5` | `0.4385245901639344` | `11` | not reached |
| `decision_day_momentum_confirmed_long_1130` | `limited_core_grid_test` | `0.0` | `-322.5` | `0.26285714285714284` | `7` | not reached |
| `decision_day_low_range_long_1130` | `limited_core_grid_test` | `0.0` | `-120.0` | `0.4418604651162791` | `4` | not reached |
| `prior_day_late_long_1500` | `limited_core_grid_test` | `0.6666666666666666` | `420.0` | `1.3471074380165289` | `11` | not reached |

## Conclusion

FAIL. No FOMC variant earned WFA, Monte Carlo, simulated incubation, or frozen
validation. The best rescue was too sparse and failed the required monkey and
one-tick-worse stress checks. No candidate strategy report was created.

Primary aggregate report:
`backtest-campaigns/es_fomc_pre_announcement_drift/campaign_test_summary.json`.
