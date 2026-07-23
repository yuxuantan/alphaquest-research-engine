# all_day_signed_high_volume_break_two_sided

Campaign: `es_prior_session_breakout_orderflow_confirmation`

## Mechanic
From 09:35 through 15:00 ET, trade a fresh prior-level close break only when total signed flow confirms direction and the breakout bar has at least moderate relative volume.

## Modules
- Entry: `pdh_pdl_orderflow_breakout_continuation`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 108.

```yaml
entry.params.min_volume_ratio: [0.5, 0.75, 1.0]
entry.params.min_orderflow_imbalance: [0.0, 0.001, 0.005, 0.01]
sl.params.stop_pct: [0.0015, 0.0025, 0.004]
tp.params.target_r_multiple: [0.75, 1.0, 1.5]
```

## Lookahead Controls
Prior RTH levels are complete before the current session. Break and orderflow confirmation use only completed 5-minute bars. Engine execution remains next-bar open.
