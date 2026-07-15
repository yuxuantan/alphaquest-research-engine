# all_day_large10_buffer_break_two_sided

Campaign: `es_prior_session_breakout_orderflow_confirmation`

## Mechanic
From 09:35 through 15:00 ET, trade the first fresh prior-high/low close break only when same-bar large10 aggregate flow agrees with the breakout direction.

## Modules
- Entry: `pdh_pdl_orderflow_breakout_continuation`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 72.

```yaml
entry.params.close_buffer_ticks: [0, 1]
entry.params.min_orderflow_imbalance: [0.0, 0.001, 0.005, 0.01]
sl.params.stop_pct: [0.0015, 0.0025, 0.004]
tp.params.target_r_multiple: [0.75, 1.0, 1.5]
```

## Lookahead Controls
Prior RTH levels are complete before the current session. Break and orderflow confirmation use only completed 5-minute bars. Engine execution remains next-bar open.
