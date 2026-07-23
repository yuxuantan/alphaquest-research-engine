# all_day_large10_trend_hold_two_sided rescue1

Campaign: `es_trend_filtered_prior_session_breakout_orderflow`

This is the single allowed parameter-space/fixed-parameter rescue for `all_day_large10_trend_hold_two_sided`.

## Preserved Mechanics
- Entry module: `pdh_pdl_trend_orderflow_breakout_continuation`
- Setup mode: `trend_level_hold`
- Stop module: `percent_from_entry`
- Target module: `fixed_r`
- Symbol, timeframe, data window, cost model, fill model, session rules, prop rules, and staged gates are unchanged.

## Rescue Changes
- Fixed `entry.params.min_trend_move_ticks` changed to `2` so the trend filter requires actual displacement instead of equal highs/lows being sufficient.
- Entry grid shifts to stricter prior-level buffer and orderflow thresholds.
- Stop/target grid shifts wider to test whether accepted prior-level continuation needs more room than the original tight stop geometry.

## Parameter Space
Total combinations: 81.

```yaml
entry.params.close_buffer_ticks: [2, 4, 6]
entry.params.min_orderflow_imbalance: [0.05, 0.1, 0.2]
sl.params.stop_pct: [0.0025, 0.004, 0.006]
tp.params.target_r_multiple: [1.0, 1.5, 2.0]
```


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_trend_filtered_prior_session_breakout_orderflow/all_day_large10_trend_hold_two_sided/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
