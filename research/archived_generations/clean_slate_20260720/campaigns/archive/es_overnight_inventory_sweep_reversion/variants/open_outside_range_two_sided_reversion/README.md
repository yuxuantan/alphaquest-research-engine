# open_outside_range_two_sided_reversion

Campaign: `es_overnight_inventory_sweep_reversion`

## Mechanic
From 09:30 through 10:30 ET, require the opening bar to start outside the completed overnight range, then fade a completed sweep and reclaim back through the relevant overnight extreme. Enter at the next 5-minute bar open; flatten at 15:55 ET unless stop or target is hit. The overnight high and low are completed before the RTH signal window begins.

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
