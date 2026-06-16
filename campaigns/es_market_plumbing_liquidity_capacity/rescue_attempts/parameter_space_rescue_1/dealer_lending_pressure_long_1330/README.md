# dealer_lending_pressure_long_1330 rescue1

Campaign: `es_market_plumbing_liquidity_capacity`

This is the only allowed rescue for this failed variant.

## Scope
Same late-day dealer-lending mechanic with neighboring distribution thresholds and non-overlapping stop/target values to test monkey robustness without changing the edge.

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
