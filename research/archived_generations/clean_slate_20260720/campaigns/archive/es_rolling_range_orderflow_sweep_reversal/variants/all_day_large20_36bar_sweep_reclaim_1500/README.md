# all_day_large20_36bar_sweep_reclaim_1500

Campaign: `es_rolling_range_orderflow_sweep_reversal`

## Mechanic
From 09:45 through 15:00 ET, fade completed rolling-range sweeps only when the large20 bucket shows pressure into the failed break, using a broader lookback to define more meaningful intraday extremes.

## Modules
- Entry: `rolling_range_orderflow_sweep_reversal`
- Stop: `sweep_extreme`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 81.

```yaml
entry.params.lookback_bars: [18, 36, 54]
entry.params.min_absorption_imbalance: [0.0, 0.01, 0.03]
sl.params.stop_offset_ticks: [0, 2, 4]
tp.params.target_r_multiple: [0.75, 1.0, 1.5]
```

## Lookahead Controls
Rolling levels use prior completed bars only. Sweep/reclaim and orderflow absorption use the completed signal bar. Engine execution remains next-bar open.
