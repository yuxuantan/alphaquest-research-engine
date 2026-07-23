# ES trend-filtered prior-session breakout orderflow rescue attempt 1 - 2026-06-18

Scope: one allowed parameter-space/fixed-parameter rescue for each failed variant in `es_trend_filtered_prior_session_breakout_orderflow`.

Original result:

- All five original variants failed `limited_core_grid_test`.
- No original reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.
- Failure was not a density issue: the retained hold/acceptance variants cleared the pre-PnL density floor and all original core-grid top rows had more than 150 trades/year.

Allowed rescue changes:

- Keep entry module: `pdh_pdl_trend_orderflow_breakout_continuation`.
- Keep setup mode: `trend_level_hold`.
- Keep stop module: `percent_from_entry`.
- Keep target module: `fixed_r`.
- Keep symbol, timeframe, data window, costs, session logic, prop rules, and staged gates unchanged.
- Change only fixed `min_trend_move_ticks` and existing tunable parameter space.

Rescue parameter space:

- `entry.params.close_buffer_ticks`: `[2, 4, 6]`
- signed-flow variants `entry.params.min_orderflow_imbalance`: `[0.005, 0.01, 0.02]`
- large10 variants `entry.params.min_orderflow_imbalance`: `[0.05, 0.10, 0.20]`
- `sl.params.stop_pct`: `[0.0025, 0.004, 0.006]`
- `tp.params.target_r_multiple`: `[1.0, 1.5, 2.0]`

Rescue results:

| Variant | Profitable combo rate | Benchmark-pass combos | Top net | Top PF | Top trades/year |
|---|---:|---:|---:|---:|---:|
| `all_day_large10_trend_hold_two_sided` | 0.0123 | 0 | 1052.50 | 1.0401 | 122.81 |
| `all_day_signed_high_volume_trend_hold_two_sided` | 0.0000 | 0 | -3472.50 | 0.8278 | 121.51 |
| `all_day_signed_trend_hold_two_sided` | 0.0000 | 0 | -3365.00 | 0.9038 | 157.89 |
| `first_half_large10_trend_hold_two_sided` | 0.0000 | 0 | -456.25 | 0.9671 | 95.43 |
| `first_half_signed_trend_hold_two_sided` | 0.0000 | 0 | -2885.00 | 0.8818 | 144.28 |

Decision after rescue: FAIL. All rescues failed `limited_core_grid_test`; no candidate report was created.
