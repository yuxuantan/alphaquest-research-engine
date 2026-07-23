# ES opening-range failed breakout orderflow density audit - 2026-06-17

Scope: pre-PnL density check only. Counts used local Sierra ES RTH aggregate-orderflow data from `2011-01-03` through `2026-06-09`, aggregated to 5-minute strategy bars. No PnL, stop, target, WFA, monkey, Monte Carlo, or holdout result was inspected.

Rejected before PnL:

- One-bar reclaim grids for signed-flow OR15/OR30 and large10 OR15 were too sparse at the strictest threshold.
- OR15 directional-only long and short variants were too sparse, with strict-grid floors below 20 signals/year.

Final declared variants:

| Variant | Entry grid retained | Strict retained density | Max raw signals |
| --- | --- | ---: | ---: |
| `or15_signed_failed_reclaim_1030` | max_reclaim_bars [3, 4], imbalance [0.02, 0.06] | above 50/year after excluding the 0.10 imbalance corner | 1435 |
| `or30_signed_failed_reclaim_1100` | max_reclaim_bars [3, 4], imbalance [0.02, 0.06] | above 50/year after excluding the 0.10 imbalance corner | 1458 |
| `or15_large10_failed_reclaim_1030` | max_reclaim_bars [3, 4], imbalance [0.02, 0.06, 0.10] | 61.30/year | 1285 |
| `or30_large20_failed_reclaim_1130` | max_reclaim_bars [2, 3, 4], imbalance [0.02, 0.06, 0.10] | 77.44/year | 1678 |
| `or60_signed_failed_reclaim_1200` | max_reclaim_bars [3, 4], imbalance [0.02, 0.06, 0.10] | 53.27/year | 1429 |

Decision: approve density for staged testing. The final grids keep only parameter spaces that plausibly satisfy the 50 trades/year rule before performance testing.
