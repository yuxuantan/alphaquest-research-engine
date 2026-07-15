# first_half_large10_trend_hold_two_sided

Campaign: `es_trend_filtered_prior_session_breakout_orderflow`

## Edge Expression
From 10:00 through 13:00 ET, trade prior-level holds only when large10 aggregate flow confirms the hold and completed-bar structure is aligned higher-high/higher-low for longs or lower-high/lower-low for shorts.

## Modules
- Entry: `pdh_pdl_trend_orderflow_breakout_continuation`
- Stop: `percent_from_entry`
- Target: `fixed_r`

## Parameter Space
Total combinations: 81.

```yaml
entry.params.close_buffer_ticks: [0, 1, 2]
entry.params.min_orderflow_imbalance: [0.0, 0.05, 0.1]
sl.params.stop_pct: [0.0015, 0.0025, 0.004]
tp.params.target_r_multiple: [0.75, 1.0, 1.5]
```

## Lookahead Control
Prior RTH levels are known before the session; trend and orderflow filters use only completed bars; entry is next bar open or later.
