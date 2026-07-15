# RRP release risk-on long at 13:30

Edge expression: At the completed 13:30 ET bar, buy ES when the prior-day lagged five-day ON RRP change z-score is nonpositive to moderately negative, testing whether easier liquidity state supports afternoon risk appetite.

Expected profitability mechanism: If RRP balances are falling, cash may be leaving the Fed facility and private-market liquidity/risk appetite may improve, favoring a long ES intraday risk-premium test.

Timing and causality: the feature file shifts RRP state by one listed trade date, so the RRP value is known before the ES RTH session. The signal is emitted only after the configured 5-minute bar closes, and the engine enters at the next bar open or later with ES costs, one-tick slippage, tick rounding, same-bar stop/target handling, and forced flatten.

Failure modes: RRP state can be an ambiguous slow-moving policy variable, broad thresholds can mix regimes, and same-day ES movement may be too noisy after costs.
