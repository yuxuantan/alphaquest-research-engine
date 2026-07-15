# morning_pdh_signed_trend_absorption_short_1130 rescue1

Campaign: `es_trend_orderflow_prior_day_stop_reclaim`

## Rescue Scope
`parameter_space_rescue_1` is a pre-PnL density rescue. It changes only fixed entry parameters and the declared parameter grid inside the existing modules. Entry, stop, target modules, data, costs, sessions, fills, prop rules, and benchmark gates are unchanged.

## Edge Expression
Rescue broadens the original sparse one-sided PDH short into a two-sided prior-day high/low sweep-reclaim using the same absorbed signed-flow and pre-sweep trend mechanic. The core edge remains a failed prior-day stop-run, not a breakout or standalone orderflow signal. Price alone still cannot trigger; a completed prior-day level sweep-reclaim, absorbed aggregate flow on the completed reclaim bar, and pre-sweep completed-bar trend alignment are all required before next-bar entry.

## Modules
- Entry: `trend_orderflow_pdh_pdl_sweep_reclaim`
- Stop: `percent_from_entry`
- Target: `fixed_r`

## Parameter Space
Total combinations: 81.

```yaml
entry.params.min_sweep_ticks: [0, 1, 2]
entry.params.min_orderflow_imbalance: [0.0, 0.02, 0.04]
sl.params.stop_pct: [0.0015, 0.0025, 0.004]
tp.params.target_r_multiple: [0.75, 1.0, 1.5]
```

## Lookahead Control
Prior RTH levels are known before the session. The trend snapshot uses completed bars before the sweep. The sweep, reclaim, and orderflow absorption are known only after the signal bar closes, so entry is next bar open or later.
