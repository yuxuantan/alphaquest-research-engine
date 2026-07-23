# dealer_lending_pressure_long_1130

Campaign: `nq_market_plumbing_liquidity_capacity`

- Entry: `market_plumbing_priority`
- Stop: `percent_from_entry`
- Target: `fixed_r`
- Instrument: NQ, 5-minute RTH bars, next-bar-open execution after completed-bar signal.

This is a pre-PnL NQ port of the corrected ES market-plumbing liquidity-capacity config. It keeps the lagged external feature mechanics and changes only instrument, data, and NQ contract economics.
