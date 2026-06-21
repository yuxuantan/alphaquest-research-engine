# all_day_signed_high_volume_trend_hold_two_sided

Campaign: `es_trend_filtered_prior_session_breakout_orderflow`

## Edge Expression
From 10:00 through 14:30 ET, trade completed prior-level holds only when total signed flow confirms direction, current completed-bar trend agrees, and the signal bar has above-normal relative volume.

## Modules
- Entry: `pdh_pdl_trend_orderflow_breakout_continuation`
- Stop: `percent_from_entry`
- Target: `fixed_r`

## Parameter Space
Total combinations: 81.

```yaml
entry.params.close_buffer_ticks: [0, 1, 2]
entry.params.min_orderflow_imbalance: [0.0, 0.001, 0.005]
sl.params.stop_pct: [0.0015, 0.0025, 0.004]
tp.params.target_r_multiple: [0.75, 1.0, 1.5]
```

## Lookahead Control
Prior RTH levels are known before the session; trend and orderflow filters use only completed bars; entry is next bar open or later.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_trend_filtered_prior_session_breakout_orderflow/all_day_signed_high_volume_trend_hold_two_sided/run1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
