# vx_oi_crowding_short_1330 rescue1

Campaign: `es_market_plumbing_liquidity_capacity`

This is the only allowed rescue for this failed variant.

## Scope
Same upper-tail VX-OI short mechanic with q70-q90 neighboring thresholds to address sparse density without switching direction or adding filters.

No entry module, stop module, target module, edge thesis, timeframe, data window, costs, fill rules, or stage criteria changed.

## Parameter Space
Total combinations: 36.

```yaml
entry.params.cboe_vx_oi_crowding_threshold:
- 0.9098809274140917
- 1.1143077692623922
- 1.30241097911329
- 1.8562670360751274
sl.params.stop_pct:
- 0.004
- 0.006
- 0.008
tp.params.target_r_multiple:
- 1.25
- 1.75
- 2.25
```
