# late_morning_signed_two_sided_trend_absorption_1230 rescue1

Campaign: `es_trend_orderflow_prior_day_stop_reclaim`

## Rescue Scope
`parameter_space_rescue_1` is a pre-PnL density rescue. It changes only fixed entry parameters and the declared parameter grid inside the existing modules. Entry, stop, target modules, data, costs, sessions, fills, prop rules, and benchmark gates are unchanged.

## Edge Expression
Rescue preserves the signed two-sided prior-day sweep-reclaim but widens the fixed signal window and uses a shorter completed-bar trend snapshot so the same mechanic can meet the trade-frequency screen before any PnL testing. Price alone still cannot trigger; a completed prior-day level sweep-reclaim, absorbed aggregate flow on the completed reclaim bar, and pre-sweep completed-bar trend alignment are all required before next-bar entry.

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


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_trend_orderflow_prior_day_stop_reclaim/late_morning_signed_two_sided_trend_absorption_1230/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
