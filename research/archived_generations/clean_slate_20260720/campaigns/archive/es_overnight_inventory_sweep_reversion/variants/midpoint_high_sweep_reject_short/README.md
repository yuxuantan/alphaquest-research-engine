# midpoint_high_sweep_reject_short

Campaign: `es_overnight_inventory_sweep_reversion`

## Mechanic
From 09:30 through 12:00 ET, record a completed 5-minute sweep above the completed overnight high, then require a later completed bar within the reclaim window to close below the overnight midpoint. Enter short at the next bar open; flatten at 15:55 ET unless stop or target is hit. The overnight high and low are completed before the RTH signal window begins.

## Modules
- Entry: `overnight_inventory_reversion`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 81.

```yaml
entry.params.min_overnight_range_points: [4.0, 8.0, 12.0]
entry.params.reclaim_buffer_ticks: [0, 1, 2]
sl.params.stop_pct: [0.002, 0.0035, 0.005]
tp.params.target_r_multiple: [1.0, 1.5, 2.0]
```

## Lookahead Controls
The overnight high/low are computed from the completed ETH session and are only used on RTH bars. Sweep and reclaim checks use completed 5-minute bars, and the engine enters at the next bar open with configured ES tick size, point value, commission, slippage, pessimistic same-bar stop/target handling, and forced flattening. Roll selection uses a fixed calendar and skips roll-boundary sessions.
