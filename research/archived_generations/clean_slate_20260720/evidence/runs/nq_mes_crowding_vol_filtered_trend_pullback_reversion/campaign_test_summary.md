# NQ MES-Crowding Volatility-Filtered Trend-Pullback Reversion - Campaign Summary

Verdict: FAIL

The NQ execution-leg port did not produce a candidate strategy. Four variants passed the limited core grid but failed the limited monkey test with negative monkey median net profit and insufficient core beat rates. The vol-downshift variant failed core. No variant reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

| Variant | Terminal stage | Core profitable | Top net | Top PF | Top trades | Top MAR | Monkey | Monkey median net | Net beat rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| exclude_extreme_absret5_trade_morning_1030 | limited_monkey_test | 81/81 | 26515.0 | 1.926611916826839 | 57 | 4.992132335746818 | failed | -620.0 | 0.8725 |
| exclude_extreme_downside20_trade_morning_1030 | limited_monkey_test | 81/81 | 14000.0 | 1.5156537753222836 | 49 | 2.162902964325317 | failed | -415.0 | 0.821625 |
| exclude_extreme_range10_trade_morning_1030 | limited_monkey_test | 75/81 | 19400.0 | 1.670005180452426 | 55 | 5.129897708035441 | failed | -425.0 | 0.7595 |
| exclude_extreme_vol20_trade_morning_1030 | limited_monkey_test | 81/81 | 12350.0 | 1.4037927088442046 | 53 | 2.0516844267486056 | failed | -562.5 | 0.81175 |
| vol_downshift_trade_morning_1030 | limited_core_grid_test | 33/81 | 16080.0 | 1.4527664367168802 | 59 | 2.467183033092359 | skipped | None | None |

No rescue was authorized or used.
