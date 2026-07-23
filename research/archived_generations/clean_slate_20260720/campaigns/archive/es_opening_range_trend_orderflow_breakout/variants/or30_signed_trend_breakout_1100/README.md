# or30_signed_trend_breakout_1100

Campaign: `es_opening_range_trend_orderflow_breakout`

## Mechanic
Build the completed first 30-minute RTH opening range, then trade the first two-sided breakout before 11:00:00 ET only if the completed 5-minute breakout bar closes beyond the range, the 15/30-minute completed-bar trend structure agrees with breakout direction, and aggregate signed-volume imbalance confirms the same direction.

## Modules
- Entry: `opening_range_trend_orderflow_breakout`
- Stop: `opening_range_edge`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 81.

```yaml
entry.params.max_opening_range_pct_of_open: [0.0045, 0.0065, 0.009]
entry.params.min_orderflow_imbalance: [0.005, 0.02, 0.04]
sl.params.stop_offset_ticks: [0, 2, 4]
tp.params.target_r_multiple: [0.75, 1.0, 1.5]
```

## Lookahead Controls
The opening range, trend windows, and orderflow confirmation use only completed bars. Engine execution remains next-bar open.
