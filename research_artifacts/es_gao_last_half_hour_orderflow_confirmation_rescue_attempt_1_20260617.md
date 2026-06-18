# ES Gao Last-Half-Hour Orderflow Confirmation Rescue Attempt 1 - 2026-06-17

Trigger: all five original variants failed `limited_core_grid_test`; no variant reached monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS.

Allowed rescue scope: per-failed-variant parameter-space-only rescue. No entry module, stop module, target module, signal time, first-window length, flow mode, data source, costs, sessions, fill handling, prop rules, or validation gates were changed.

Original grid:

- `entry.params.min_first_return_ticks`: `[0, 4]`
- `entry.params.min_orderflow_imbalance`: `[0.005, 0.02]`
- `sl.params.stop_pct`: `[0.00075, 0.001, 0.0015]`
- `tp.params.target_r_multiple`: `[0.5, 0.75, 1.0]`
- Combinations per variant: 36

Rescue grid:

- `entry.params.min_first_return_ticks`: `[8, 12]`
- `entry.params.min_orderflow_imbalance`: `[0.02, 0.03]`
- `sl.params.stop_pct`: `[0.001, 0.0015, 0.002]`
- `tp.params.target_r_multiple`: `[0.5, 0.75, 1.0]`
- Combinations per variant: 36

Rationale before running rescue: the original grid was consistently negative, so the only defensible rescue is to require stronger completed first-window price action and stronger completed aggregate orderflow while preserving the same Gao last-half-hour continuation mechanism.

Rescue entry-density check: all variants remained above 50 signals/year at all declared rescue entry corners before stop/target filtering.

| Variant | Annualized counts for `[8, 0.02]`, `[8, 0.03]`, `[12, 0.02]`, `[12, 0.03]` |
|---|---:|
| `first30_signed_flow_two_sided_1530` | 98.25, 72.00, 84.44, 61.89 |
| `first30_large20_flow_two_sided_1530` | 120.09, 114.84, 102.20, 98.05 |
| `first60_signed_flow_two_sided_1530` | 86.00, 55.93, 78.03, 51.33 |
| `first60_large20_flow_two_sided_1530` | 130.00, 120.28, 116.72, 109.26 |
| `first30_broad_large_alignment_1530` | 82.17, 62.54, 70.96, 54.05 |

Result: all five rescue variants failed `limited_core_grid_test`; no rescue reached monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS.

Least-bad rescue row: `first30_broad_large_alignment_1530/rescue1`, top net profit `-2055.0`, profit factor `0.7144841959013546`, and `73.45024501632395` trades/year. Failure reason: `min_total_net_profit;max_consecutive_losses`.

Status: completed_failed.
