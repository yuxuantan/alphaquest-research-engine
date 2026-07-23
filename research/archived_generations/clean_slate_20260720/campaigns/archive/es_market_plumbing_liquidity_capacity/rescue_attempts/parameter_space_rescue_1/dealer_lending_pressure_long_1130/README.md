# dealer_lending_pressure_long_1130 rescue1

Campaign: `es_market_plumbing_liquidity_capacity`

This is the only allowed rescue for this failed variant.

## Scope
Neighboring lower-tail dealer-lending thresholds plus a shifted risk grid; no timing, filter, module, data-window, or direction change.

No entry module, stop module, target module, edge thesis, timeframe, data window, costs, fill rules, or stage criteria changed.

## Parameter Space
Total combinations: 36.

```yaml
entry.params.primary_dealer_lending_pressure_threshold:
- 0.1538461538461538
- 0.2115384615384615
- 0.25
- 0.3076923076923077
sl.params.stop_pct:
- 0.004
- 0.006
- 0.008
tp.params.target_r_multiple:
- 1.25
- 1.75
- 2.25
```
