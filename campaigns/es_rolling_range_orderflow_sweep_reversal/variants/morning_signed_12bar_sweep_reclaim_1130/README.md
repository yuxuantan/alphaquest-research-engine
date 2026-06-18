# morning_signed_12bar_sweep_reclaim_1130

Campaign: `es_rolling_range_orderflow_sweep_reversal`

## Mechanic
From 09:45 through 11:30 ET, fade the first completed 5-minute sweep and reclaim of a prior rolling intraday high/low when same-bar total signed flow shows aggressive pressure into the swept side.

## Modules
- Entry: `rolling_range_orderflow_sweep_reversal`
- Stop: `sweep_extreme`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 81.

```yaml
entry.params.lookback_bars: [6, 12, 18]
entry.params.min_absorption_imbalance: [0.0, 0.02, 0.05]
sl.params.stop_offset_ticks: [0, 2, 4]
tp.params.target_r_multiple: [0.75, 1.0, 1.5]
```

## Lookahead Controls
Rolling levels use prior completed bars only. Sweep/reclaim and orderflow absorption use the completed signal bar. Engine execution remains next-bar open.
