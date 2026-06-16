# dual_pressure_priority_long_1130 rescue1

Campaign: `es_market_plumbing_liquidity_capacity`

This is the only allowed rescue for this failed variant.

## Scope
Same two-leg priority mechanic with neighboring thresholds and shifted risk values; max two entry tunables retained.

No entry module, stop module, target module, edge thesis, timeframe, data window, costs, fill rules, or stage criteria changed.

## Parameter Space
Total combinations: 81.

```yaml
entry.params.primary_dealer_lending_pressure_threshold:
- 0.2115384615384615
- 0.25
- 0.3076923076923077
entry.params.cboe_vx_oi_stress_threshold:
- -1.6048759395402283
- -1.1583033389307238
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
