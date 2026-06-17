# ES Sector Rotation Risk Appetite Rescue Attempt 1 - 2026-06-17

Decision: FAIL.

## Rule

Each failed original variant received exactly one rescue. Rescue changes were limited to declared parameter space and matching fixed defaults. No rescue changed entry module, stop module, target module, setup mode, signal time, timeframe, data source/window, costs, slippage, session rules, prop rules, or validation gates.

## Rescue Change

- Long variants changed `entry.params.rank_min` from `[0.55, 0.60, 0.65]` to `[0.65, 0.70, 0.75]`.
- Short variants changed `entry.params.rank_max` from `[0.45, 0.40, 0.35]` to `[0.35, 0.30, 0.25]`.
- Stop space changed from `[0.0015, 0.0025, 0.004]` to `[0.003, 0.004, 0.006]`.
- Target space changed from `[1.0, 1.5, 2.0]` to `[1.5, 2.0, 2.5]`.

## Results

| Variant | Run | Profitable combo rate | Benchmark-pass combos | Top net | Top PF | Top trades | Terminal stage |
|---|---:|---:|---:|---:|---:|---:|---|
| `cyclical_lead_long_1000` | `rescue1` | 0.0 | 0 | -2767.5 | 0.7553050397877984 | 91 | `limited_core_grid_test` |
| `cyclical_lead_long_1000` | `run1` | 0.0 | 0 | -4007.5 | 0.7691532258064516 | 134 | `limited_core_grid_test` |
| `defensive_lead_short_1000` | `rescue1` | 0.0 | 0 | -1675.0 | 0.8746726524504302 | 105 | `limited_core_grid_test` |
| `defensive_lead_short_1000` | `run1` | 0.0 | 0 | -3440.0 | 0.8069855519708234 | 158 | `limited_core_grid_test` |
| `defensive_rotation_short_1130` | `rescue1` | 0.07407407407407407 | 0 | 500.0 | 1.020663291662362 | 145 | `limited_core_grid_test` |
| `defensive_rotation_short_1130` | `run1` | 0.0 | 0 | -1875.0 | 0.9111269107714184 | 145 | `limited_core_grid_test` |
| `financial_industrial_lead_long_1330` | `rescue1` | 0.5185185185185185 | 3 | 2372.5 | 1.312891526541378 | 88 | `limited_core_grid_test` |
| `financial_industrial_lead_long_1330` | `run1` | 0.0 | 0 | -205.0 | 0.9832173557101924 | 131 | `limited_core_grid_test` |
| `growth_lead_long_1030` | `rescue1` | 0.5925925925925926 | 5 | 4127.5 | 1.3940334128878282 | 92 | `limited_core_grid_test` |
| `growth_lead_long_1030` | `run1` | 0.037037037037037035 | 0 | 25.0 | 1.00154012012937 | 130 | `limited_core_grid_test` |

## Conclusion

All originals and all one-time rescues failed before monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
