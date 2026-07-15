# RRP drain risk-off short at 10:00

Edge expression: At the completed 10:00 ET bar, short NQ when the prior-day lagged five-day ON RRP increase z-score is nonnegative to moderately high, indicating cash moving into the Fed RRP facility and tighter private-market liquidity.

Expected profitability mechanism: If RRP balances are rising, cash is being absorbed into a Fed liability and private-market risk capacity may be weaker, favoring a short NQ intraday risk-premium test.

Timing and causality: the feature file shifts RRP state by one listed trade date, so the RRP value is known before the NQ RTH session. The signal is emitted only after the configured 5-minute bar closes, and the engine enters at the next bar open or later with NQ costs, one-tick slippage, tick rounding, same-bar stop/target handling, and forced flatten.

Failure modes: RRP state can be an ambiguous slow-moving policy variable, broad thresholds can mix regimes, and same-day NQ movement may be too noisy after costs.


## Parameter-space rescue 1

Rescue narrows the short setup to clearer RRP-drain states after near-zero drain states diluted the original core grid. This keeps the same funding-liquidity mechanism but requires a stronger prior-day cash absorption signal. Entry, stop, target modules, data, costs, fills, sessions, and validation gates are unchanged. Rescue threshold grid: `entry.params.rrp_drain_threshold=[0.125, 0.25, 0.375]`. TP grid remains `[1.0, 1.5, 2.0]`; sub-1.0R targets are forbidden.


NQ port note: This variant was ported from the ES parameter-space rescue source before any NQ PnL was inspected. The NQ campaign does not authorize a post-result rescue.
