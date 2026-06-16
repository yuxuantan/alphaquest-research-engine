# ES Halloween Seasonal Premium Rescue Attempt 1

Date: 2026-06-16

Decision: FAIL

## Scope

Campaign: `es_halloween_seasonal_premium`

Each failed variant received exactly one rescue. The rescues changed only
existing fixed stop/target values and declared stop/target parameter ranges.

No rescue changed the month definitions, direction, entry module, stop module,
target module, timeframe, data window, costs, fill assumptions, prop-rule gates,
or staged validation gates.

## Rescue Results

| Variant | Terminal stage | Core profitable rate | Top net | Top PF | Top trades | Failure |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `winter_open_long_1000` | `limited_core_grid_test` | `0.0` | `-1968.75` | `0.9274928643771292` | `195` | negative net and weak PF/MAR |
| `winter_midday_long_1200` | `limited_core_grid_test` | `0.5` | `1000.0` | `1.0526870389884089` | `195` | below 70% profitable-combo gate; PF/MAR/profit concentration failed |
| `winter_afternoon_long_1330` | `limited_core_grid_test` | `0.0` | `-2118.75` | `0.8684006211180124` | `195` | negative net and weak PF/MAR |
| `summer_open_short_1000` | `limited_core_grid_test` | `0.0` | `-3296.25` | `0.848448275862069` | `168` | negative net and weak PF/MAR |
| `summer_afternoon_short_1330` | `limited_core_grid_test` | `0.0` | `-302.5` | `0.9857663804258322` | `168` | negative net and weak PF/MAR |

## Conclusion

FAIL. All original variants and all one-time rescues failed
`limited_core_grid_test`. No variant earned monkey, WFA, Monte Carlo, simulated
incubation, or frozen validation. No candidate strategy report was created.

Primary aggregate report:
`backtest-campaigns/es_halloween_seasonal_premium/campaign_test_summary.json`.
