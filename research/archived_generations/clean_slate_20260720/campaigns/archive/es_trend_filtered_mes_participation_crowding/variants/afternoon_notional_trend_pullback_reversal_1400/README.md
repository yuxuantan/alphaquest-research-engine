# afternoon_notional_trend_pullback_reversal_1400

14:00 ET two-sided ES pullback fade using MES notional-equivalent participation over the completed 60-minute pullback window and a prior 120-minute ES trend filter.

This variant belongs to `es_trend_filtered_mes_participation_crowding`. It uses local completed-bar ES/MES Sierra cache data only. No paid data is required or downloaded.

Entry mechanics are fixed before PnL testing: at `14:00:00` ET, require elevated MES `notional` participation rank, a completed ES pullback of the opposite sign, and a prior completed ES trend window that ends before the pullback window begins. Stops are fixed percent-from-entry and targets are fixed-R, both declared in `config.yaml`.
