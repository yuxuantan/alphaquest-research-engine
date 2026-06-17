# ES Treasury Auction Pressure Rescue Attempt 1

Date: 2026-06-17

All five original variants failed limited_core_grid_test. Each failed variant received exactly one rescue.

Allowed rescue scope used:

- Entry module unchanged: `treasury_auction_pressure`
- Stop module unchanged: `percent_from_entry`
- Target module unchanged: `fixed_r`
- Auction scope, signal time, direction, timeframe, data window, costs, fills, sessions, prop rules, and gates unchanged
- Only stop/target parameter space changed to `sl.params.stop_pct = [0.001, 0.0015, 0.0025]` and `tp.params.target_r_multiple = [0.5, 0.75, 1.0]`

## Results

| Variant | Profitable Combo Rate | Benchmark-Passing Combos | Top Net | Top PF | Top Trades |
|---|---:|---:|---:|---:|---:|
| all_coupon_pre_auction_short_1130 | 0.0 | 0 | -3311.25 | 0.2797716150081566 | 121 |
| all_coupon_post_auction_short_1305 | 0.0 | 0 | -2305.0 | 0.6935859089398472 | 121 |
| all_coupon_late_reversal_long_1430 | 0.0 | 0 | -1205.0 | 0.8689505165851006 | 121 |
| note_only_post_auction_short_1305 | 0.0 | 0 | -912.5 | 0.8346171273221568 | 100 |
| all_coupon_late_pressure_short_1500 | 0.0 | 0 | -3942.5 | 0.36179684338324564 | 121 |

Final decision: FAIL. No rescue reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
