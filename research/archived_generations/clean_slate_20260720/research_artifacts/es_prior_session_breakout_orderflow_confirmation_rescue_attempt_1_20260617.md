# ES Prior-Session Breakout Orderflow Confirmation Rescue Attempt 1

Date: 2026-06-17

Campaign: `es_prior_session_breakout_orderflow_confirmation`

Trigger: all five original variants failed `limited_core_grid_test`.

Allowed scope: one rescue per failed variant, changing only fixed parameters or declared parameter space inside existing entry, stop, and target modules.

Unchanged:

- Entry module: `pdh_pdl_orderflow_breakout_continuation`
- Stop module: `percent_from_entry`
- Target module: `fixed_r`
- Data, timeframe, costs, slippage, tick size, point value, sessions, prop rules, and stage criteria
- Core prior-session breakout plus aggregate-orderflow confirmation mechanic

| Variant | Rescue rationale |
|---|---|
| `all_day_large10_buffer_break_two_sided` | Original positive rows with a 1-tick buffer fell just below 50 trades/year; rescue fixes zero buffer to preserve density and tests stop/target space around the only economically plausible 1.5R region without changing the breakout plus large10-flow mechanic. |
| `all_day_large20_no_buffer_break_two_sided` | Original large20 rows were near flat but not profitable; rescue preserves no-buffer large20 confirmation and tests whether a wider predeclared stop/target region is required for the stricter participation proxy. |
| `all_day_signed_buffer_break_two_sided` | Original positive rows with a 1-tick buffer fell just below 50 trades/year; rescue fixes zero buffer for density and tests a higher fixed-R target region while preserving total signed-flow breakout confirmation. |
| `all_day_signed_high_volume_break_two_sided` | Original high-volume rows were close to flat only at higher volume ratios; rescue keeps the same volume-plus-signed-flow mechanic and removes the low-volume corner while testing a wider risk/reward region. |
| `first_half_signed_no_buffer_break_two_sided` | Original first-half rows had the strongest top metrics but failed parameter robustness; rescue preserves no-buffer first-half signed-flow confirmation and tests neighboring stop/target values around the plausible 1.5R region. |

Result: FAIL.

All five one-time rescues completed. Four failed `limited_core_grid_test`. `first_half_signed_no_buffer_break_two_sided/rescue1` passed limited core and limited monkey, then failed `walk_forward_analysis` on the first WFA window because selected in-sample PF was `0.887903893951947`, below the `1.0` early-exit threshold. No OOS trades were stitched.

| Variant | Terminal stage | Profitable combo rate | Top net | Top PF | Trades/year | Notes |
|---|---|---:|---:|---:|---:|---|
| `all_day_large10_buffer_break_two_sided` | `limited_core_grid_test` | 0.0000 | -130.00 | 0.9857 | 59.45 | min_total_net_profit |
| `all_day_large20_no_buffer_break_two_sided` | `limited_core_grid_test` | 0.2222 | 205.62 | 1.0172 | 56.83 | max_best_day_concentration |
| `all_day_signed_buffer_break_two_sided` | `limited_core_grid_test` | 0.0000 | -365.00 | 0.9608 | 60.76 | min_total_net_profit;max_consecutive_losses |
| `all_day_signed_high_volume_break_two_sided` | `limited_core_grid_test` | 0.2778 | 1671.25 | 1.1391 | 56.83 |  |
| `first_half_signed_no_buffer_break_two_sided` | `walk_forward_analysis` | 0.8056 | 1535.00 | 1.2074 | 54.22 | limited monkey passed; WFA early exit `selected_train_profit_factor_below_minimum` |
