# morning_pdl_signed_trend_absorption_long_1130

Campaign: `es_trend_orderflow_prior_day_stop_reclaim`

## Edge Expression
From 10:00 through 11:30 ET, trade only a prior-day-low sweep that reclaims back above PDL while signed aggregate flow on the completed reclaim bar is sell-pressure absorbed into an already established uptrend.

## Modules
- Entry: `trend_orderflow_pdh_pdl_sweep_reclaim`
- Stop: `percent_from_entry`
- Target: `fixed_r`

## Parameter Space
Total combinations: 81.

```yaml
entry.params.min_sweep_ticks: [1, 2, 3]
entry.params.min_orderflow_imbalance: [0.0, 0.02, 0.05]
sl.params.stop_pct: [0.0015, 0.0025, 0.004]
tp.params.target_r_multiple: [0.75, 1.0, 1.5]
```

## Lookahead Control
Prior RTH levels are known before the session. The trend snapshot is made from completed bars before the sweep. The sweep, reclaim, and orderflow absorption are known only after the signal bar closes, so entry is next bar open or later.
