# vx_oi_stress_long_1330

Campaign: `es_market_plumbing_liquidity_capacity`

## Mechanic
Enter long at the completed 13:30 ET 5-minute bar when lagged VX futures open-interest z-score is in its lower tail, a conservative proxy for volatility-risk intermediation state.

## Modules
- Entry: `market_plumbing_priority`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 27.

```yaml
entry.params.cboe_vx_oi_stress_threshold:
- -1.6048759395402283
- -1.1583033389307238
- -0.9745886843350382
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
The variant uses `data/external/market_plumbing_priority_features_lag1_no_lookahead.csv`, where each external feature row is lagged by one listed trade date. Entries occur at or after 11:30 ET, and signals generated on completed 5-minute bars are executed by the engine at the next bar open.
