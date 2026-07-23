# chapter11_share_prior_down_long_1330

Campaign: `nq_bankruptcy_distress_regime_reversion`

## Mechanic
Enter long at the completed 13:30 ET 5-minute bar when Chapter 11 share of filings is elevated and the prior NQ RTH session closed down.

## Modules
- Entry: `bankruptcy_distress_reversion`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 27.

```yaml
entry.params.threshold:
- 1.0573527162516125
- 1.4143413485118217
- 1.7033545575370934
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
