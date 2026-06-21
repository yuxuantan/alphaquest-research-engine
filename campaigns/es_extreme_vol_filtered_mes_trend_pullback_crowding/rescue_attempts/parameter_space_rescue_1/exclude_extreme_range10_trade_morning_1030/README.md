# exclude_extreme_range10_trade_morning_1030

At 10:30 ET, take a two-sided ES trend-pullback fade only when MES trade participation is elevated over the completed 15-minute pullback, the prior completed 30-minute ES trend points opposite the pullback, and the lagged volatility filter passes: exclude top 5% prior 10-day average RTH range rank. Entry is next bar open.

This variant belongs to `es_extreme_vol_filtered_mes_trend_pullback_crowding`. It uses local completed-bar ES/MES Sierra cache data plus the local lagged-volatility feature CSV only. No paid data is required or downloaded.

Entry mechanics are fixed before PnL testing: at `10:30:00` ET, require elevated MES trade-count participation, a completed ES pullback of the opposite sign, a prior completed ES trend window that ends before the pullback begins, and the predeclared volatility gate `range10_rank_252 <= 0.95`. Stops are fixed percent-from-entry and targets are fixed-R with reward:risk no lower than 1.0, both declared in `config.yaml`.


## Rescue attempt 1

Parameter-space-only rescue. Entry module, volatility gate, MES/trend-pullback mechanic, data, costs, sessions, fills, and benchmark gates are unchanged. The rescue narrows stops to `0.002/0.003/0.004` and raises targets to `2.0/2.5/3.0` to test whether the same edge can survive drawdown/path-risk stress without sub-1R targets.
