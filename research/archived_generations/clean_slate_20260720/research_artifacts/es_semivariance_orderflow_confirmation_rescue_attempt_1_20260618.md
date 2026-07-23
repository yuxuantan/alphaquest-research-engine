# ES semivariance orderflow confirmation rescue attempt 1 - 2026-06-18

Scope: one allowed parameter-space/fixed-parameter rescue for each failed variant in `es_semivariance_orderflow_confirmation`.

Original result:

- All five original variants passed pre-PnL density after reformulation but failed `limited_core_grid_test`.
- No original reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.

Allowed rescue changes:

- Keep entry module: `realized_semivariance_orderflow_confirmation`.
- Keep stop module: `percent_from_entry`.
- Keep target module: `fixed_r`.
- Keep semivariance state, price/orderflow confirmation, fixed decision times, data, costs, sessions, fills, prop rules, and staged gates unchanged.
- Change only fixed defaults and existing parameter grids.

Rescue results:

| Variant | Profitable combo rate | Benchmark-pass combos | Top net | Top PF | Top trades/year | Terminal |
|---|---:|---:|---:|---:|---:|---|
| `badvol_signed_multitime_short` | 0.8056 | 28 | 4545.00 | 1.4309 | 74.86 | `walk_forward_analysis` |
| `badvol_signed_multitime_twosided` | 0.6944 | 21 | 3612.50 | 1.2022 | 130.18 | `limited_core_grid_test` |
| `downside_share_signed_multitime_short` | 0.2222 | 4 | 1272.50 | 1.1414 | 72.75 | `limited_core_grid_test` |
| `low_badvol_signed_multitime_long` | 0.2593 | 0 | 661.25 | 1.0711 | 70.88 | `limited_core_grid_test` |
| `semivar_balance_signed_multitime_twosided` | 0.0000 | 0 | -1682.50 | 0.8851 | 108.34 | `limited_core_grid_test` |

Decision after rescue: FAIL. `badvol_signed_multitime_short/rescue1` passed limited core and limited monkey, then failed WFA with stitched OOS PF 0.7123, MAR -0.7884, negative expectancy, and early exit. No candidate report was created.
