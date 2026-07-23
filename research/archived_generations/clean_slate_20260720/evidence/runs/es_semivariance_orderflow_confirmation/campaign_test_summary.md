# Campaign Test Summary

- Campaign: `es_semivariance_orderflow_confirmation`
- Decision: `FAIL`
- Terminal stage: `walk_forward_analysis`
- Original runs: `5`
- Rescue runs: `5`
- One rescue reached WFA; it failed stitched OOS gates. No run reached Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Best Runs

| Run | Variant | Profitable combo rate | Benchmark-pass combos | Top net | Top PF | Top trades/year | WFA PF | WFA MAR | Terminal |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| Best original | `badvol_signed_multitime_short` | 0.4444 | 18 | 4545.00 | 1.4309 | 74.86 |  |  | `limited_core_grid_test` |
| Best rescue | `badvol_signed_multitime_short` | 0.8056 | 28 | 4545.00 | 1.4309 | 74.86 | 0.7123 | -0.7884 | `walk_forward_analysis` |

## Variant Results

| Variant | Run | Profitable combo rate | Benchmark-pass combos | Top net | Top PF | Top trades/year | WFA status |
|---|---|---:|---:|---:|---:|---:|---|
| `badvol_signed_multitime_short` | `rescue1` | 0.8056 | 28 | 4545.00 | 1.4309 | 74.86 | failed |
| `badvol_signed_multitime_short` | `run1` | 0.4444 | 18 | 4545.00 | 1.4309 | 74.86 | not reached |
| `badvol_signed_multitime_twosided` | `rescue1` | 0.6944 | 21 | 3612.50 | 1.2022 | 130.18 | not reached |
| `badvol_signed_multitime_twosided` | `run1` | 0.2222 | 12 | 3612.50 | 1.2022 | 130.18 | not reached |
| `downside_share_signed_multitime_short` | `rescue1` | 0.2222 | 4 | 1272.50 | 1.1414 | 72.75 | not reached |
| `downside_share_signed_multitime_short` | `run1` | 0.0556 | 1 | 816.25 | 1.0810 | 72.74 | not reached |
| `low_badvol_signed_multitime_long` | `rescue1` | 0.2593 | 0 | 661.25 | 1.0711 | 70.88 | not reached |
| `low_badvol_signed_multitime_long` | `run1` | 0.0000 | 0 | -20.00 | 0.9978 | 70.88 | not reached |
| `semivar_balance_signed_multitime_twosided` | `rescue1` | 0.0000 | 0 | -1682.50 | 0.8851 | 108.34 | not reached |
| `semivar_balance_signed_multitime_twosided` | `run1` | 0.0000 | 0 | -1682.50 | 0.8851 | 108.34 | not reached |

Decision: FAIL. No `candidate_strategy_report.md` was created.
