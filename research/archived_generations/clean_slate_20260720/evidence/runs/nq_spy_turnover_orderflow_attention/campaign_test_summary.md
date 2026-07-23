# NQ SPY Turnover Orderflow Attention - Campaign Summary

Verdict: FAIL

One variant passed core but failed `limited_monkey_test`; the other four variants failed `limited_core_grid_test`. No WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was reached.

| Variant | Terminal stage | Core profitable | Top net | Top PF | Monkey status | Monkey median net |
|---|---:|---:|---:|---:|---:|---:|
| spy_1d_absret_attention_continuation_1530 | limited_core_grid_test | 6/81 | 545.0 | 1.0726666666666667 | skipped | None |
| spy_1d_volume_attention_continuation_1530 | limited_core_grid_test | 13/81 | 550.0 | 1.073775989268947 | skipped | None |
| spy_3d_absret_attention_continuation_1530 | limited_monkey_test | 75/81 | 2862.5 | 1.283135509396637 | failed | -1080.0 |
| spy_3d_volume_attention_continuation_1530 | limited_core_grid_test | 13/81 | 1590.0 | 1.2173615857826383 | skipped | None |
| spy_5d_volume_attention_continuation_1530 | limited_core_grid_test | 49/81 | 3045.0 | 1.4087248322147652 | skipped | None |

No rescue was authorized or used.
