# business_ch11_growth_prior_down_long_1130

Campaign: `es_bankruptcy_distress_regime_reversion`

## Mechanic
Enter long at the completed 11:30 ET 5-minute bar when business Chapter 11 filing YoY growth is elevated and the prior ES RTH session closed down.

## Modules
- Entry: `bankruptcy_distress_reversion`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 27.

```yaml
entry.params.threshold:
- 10.744789877476235
- 26.479693379760022
- 42.74900543088623
sl.params.stop_pct:
- 0.003
- 0.005
- 0.007
tp.params.target_r_multiple:
- 1.0
- 1.5
- 2.0
```

## Lookahead Controls
The entry module uses only the latest feature row with `effective_date <= session_date`, rejects stale rows beyond 180 days, uses the prior recorded RTH session return filter, and emits signals only at completed 5-minute bar closes for next-bar execution.
