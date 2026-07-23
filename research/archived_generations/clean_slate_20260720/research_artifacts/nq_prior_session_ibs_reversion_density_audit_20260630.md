# NQ Prior-Session IBS Reversion Density Audit

Date: 2026-06-30

Verdict: PASS_WITH_GRID_PRUNING pre-PnL density screen.

Method: counted candidate sessions using completed prior RTH high, low, and close from the NQ RTH cache. No NQ PnL was inspected. Sparse low-IBS and high-IBS corners were removed before staged testing.

| Variant | Min signals/year | Max signals/year | Min latest-252 signals | Max latest-252 signals |
|---|---:|---:|---:|---:|
| `open_low_ibs_long` | 61.874700 | 61.874700 | 52 | 52 |
| `open_high_ibs_short` | 52.670754 | 94.928286 | 71 | 102 |
| `delayed_low_ibs_long_range_filtered` | 61.874700 | 61.874700 | 52 | 52 |
| `delayed_high_ibs_short_range_filtered` | 52.670754 | 94.928286 | 71 | 102 |
| `open_two_sided_ibs_reversion` | 64.830712 | 156.802986 | 55 | 154 |

Decision: all retained NQ IBS entry grids clear the 50 signals/year floor and have at least 52 latest-252-session signals. Removed corners were not staged and no NQ PnL was inspected before pruning.
