# vx_oi_crowding_short_1330

Campaign: `es_market_plumbing_liquidity_capacity`

## Mechanic
Enter short at the completed 13:30 ET 5-minute bar when lagged VX futures open-interest z-score is in its upper tail, testing whether crowded volatility-risk intermediation coincides with weaker same-day ES risk appetite.

## Modules
- Entry: `market_plumbing_priority`
- Stop: `percent_from_entry`
- Target/exit: `fixed_r`
- Forced flatten: `15:55:00` America/New_York

## Parameter Space
Declared before testing. Total combinations: 27.

```yaml
entry.params.cboe_vx_oi_crowding_threshold:
- 1.1143077692623922
- 1.30241097911329
- 1.8562670360751274
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
