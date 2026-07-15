# total_ch11_z_prior_up_short_1330

Campaign: `nq_bankruptcy_distress_regime_reversion`

## Mechanic
Enter short at the completed 13:30 ET 5-minute bar when total Chapter 11 filings are high versus the 16-quarter history and the prior NQ RTH session closed up, testing distress-regime reversal after strength.

## Modules
- Entry: `bankruptcy_distress_reversion`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 27.

```yaml
entry.params.threshold:
- 0.0172143361987526
- 0.7960824618812837
- 1.111666518216771
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
