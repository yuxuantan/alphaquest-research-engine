# vx_oi_stress_long_1330 rescue1

Campaign: `es_market_plumbing_liquidity_capacity`

This is the only allowed rescue for this failed variant.

## Scope
Broader neighboring low-VX-OI tail thresholds with shifted stop/target values; same 13:30 long VX-state mechanic.

No entry module, stop module, target module, edge thesis, timeframe, data window, costs, fill rules, or stage criteria changed.

## Parameter Space
Total combinations: 36.

```yaml
entry.params.cboe_vx_oi_stress_threshold:
- -1.6048759395402283
- -1.1583033389307238
- -0.9745886843350382
- -0.7981471492981622
sl.params.stop_pct:
- 0.004
- 0.006
- 0.008
tp.params.target_r_multiple:
- 1.25
- 1.75
- 2.25
```
