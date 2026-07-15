# RRP drain risk-off short at 10:00

Edge expression: At the completed 10:00 ET bar, short ES when the prior-day lagged five-day ON RRP increase z-score is nonnegative to moderately high, indicating cash moving into the Fed RRP facility and tighter private-market liquidity.

Expected profitability mechanism: If RRP balances are rising, cash is being absorbed into a Fed liability and private-market risk capacity may be weaker, favoring a short ES intraday risk-premium test.

Timing and causality: the feature file shifts RRP state by one listed trade date, so the RRP value is known before the ES RTH session. The signal is emitted only after the configured 5-minute bar closes, and the engine enters at the next bar open or later with ES costs, one-tick slippage, tick rounding, same-bar stop/target handling, and forced flatten.

Failure modes: RRP state can be an ambiguous slow-moving policy variable, broad thresholds can mix regimes, and same-day ES movement may be too noisy after costs.
