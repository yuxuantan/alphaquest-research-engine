# Campaign Test Summary

Campaign: `es_opening_range_failed_breakout_trend_orderflow`
Decision: FAIL
Updated at: `2026-06-19T05:49:52`

All five reformulated original variants and all five one-time parameter-space rescues failed limited_core_grid_test with 0 profitable combinations. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

| Variant | Run | Profitable Combos | Benchmark Combos | Top Net | Top PF | Top Trades/Year | Fixed Trade Log Rows |
|---|---:|---:|---:|---:|---:|---:|---:|
| `or15_full_session_large10_trend_reclaim_1530` | `run1` | 0 / 54 | 0 | -1952.5 | 0.13510520487264674 | 32.170078073930036 | 51 |
| `or15_full_session_large10_trend_reclaim_1530` | `rescue1` | 0 / 54 | 0 | -2852.5 | 0.31430288461538464 | 71.45476501962364 | 82 |
| `or15_full_session_signed_trend_reclaim_1530` | `run1` | 0 / 54 | 0 | -1750.625 | 0.4446867565424266 | 34.85011856720358 | 51 |
| `or15_full_session_signed_trend_reclaim_1530` | `rescue1` | 0 / 54 | 0 | -2702.5 | 0.321831869510665 | 71.45476501962364 | 83 |
| `or30_full_session_large10_trend_reclaim_1530` | `run1` | 0 / 54 | 0 | -1260.0 | 0.13550600343053174 | 24.65457281962989 | 38 |
| `or30_full_session_large10_trend_reclaim_1530` | `rescue1` | 0 / 54 | 0 | -2472.5 | 0.22794691647150664 | 50.1361387211106 | 77 |
| `or30_full_session_signed_trend_reclaim_1530` | `run1` | 0 / 54 | 0 | -1252.5 | 0.13620689655172413 | 25.320912625565832 | 38 |
| `or30_full_session_signed_trend_reclaim_1530` | `rescue1` | 0 / 54 | 0 | -2637.5 | 0.11269974768713205 | 48.8339013517311 | 78 |
| `or60_full_session_signed_trend_reclaim_1530` | `run1` | 0 / 54 | 0 | -1507.5 | 0.0821917808219178 | 26.929072455662897 | 40 |
| `or60_full_session_signed_trend_reclaim_1530` | `rescue1` | 0 / 54 | 0 | -2917.5 | 0.23173140223831468 | 61.212108810476906 | 76 |

Best original: `or30_full_session_signed_trend_reclaim_1530/run1` top net `-1252.5`.
Best rescue: `or30_full_session_large10_trend_reclaim_1530/rescue1` top net `-2472.5`.

Final decision: FAIL
