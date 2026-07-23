# ES daily reversal orderflow confirmation rescue attempt 1 - 2026-06-18

Scope: one allowed parameter-space-only rescue for each failed variant in
`es_daily_reversal_orderflow_confirmation`.

Original result:

- All five original variants failed `limited_core_grid_test`.
- No original reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.
- Failure was not a zero-signal issue: all original grid combinations generated trades and every
  combination exceeded 50 trades/year in the limited core slice.

Allowed rescue changes:

- Keep entry module: `daily_reversal_orderflow_confirmation`.
- Keep stop module: `percent_from_entry`.
- Keep target module: `fixed_r`.
- Keep symbol, timeframe, data window, costs, session logic, prop rules, and staged gates unchanged.
- Change only fixed parameters inside existing modules and tunable parameter space.

Rescue parameter space:

- `entry.params.min_abs_reversal_return_pct`: `[0.0005, 0.001, 0.0015]`
- `entry.params.min_reversal_flow_imbalance`: `[0.0, 0.005, 0.01]`
- `sl.params.stop_pct`: `[0.0025, 0.004, 0.006]`
- `tp.params.target_r_multiple`: `[1.0, 1.5, 2.0]`

Rationale before rescue results:

- The original grid included a zero prior-return threshold. The rescue removes that weakest
  daily-reversal condition while preserving the same composite mechanic.
- The original grid was broadly negative, so the rescue tests whether this slower liquidity-provision
  reversal needs wider stop/target geometry rather than tight intraday stop-outs.
- No new filter, time window, data source, or direction rule is added.

Pre-PnL rescue density check:

| Variant | Minimum signals/year across rescue entry grid | Maximum signals/year across rescue entry grid |
|---|---:|---:|
| `first60_1d_flow_confirm_1030` | 51.1 | 92.6 |
| `first90_2d_flow_confirm_1100` | 56.8 | 100.9 |
| `first120_3d_flow_confirm_1130` | 56.8 | 107.0 |
| `first150_5d_flow_confirm_1200` | 59.9 | 113.0 |
| `afternoon90_1d_flow_confirm_1400` | 68.1 | 107.3 |

Decision before rescue run: eligible for the one allowed rescue per failed variant.
