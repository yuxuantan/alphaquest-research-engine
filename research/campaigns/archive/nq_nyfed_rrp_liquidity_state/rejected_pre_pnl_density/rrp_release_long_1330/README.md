# RRP release risk-on long at 13:30

Edge expression: At the completed 13:30 ET bar, buy NQ when the prior-day lagged five-day ON RRP change z-score is nonpositive to moderately negative, testing whether easier liquidity state supports afternoon risk appetite.

Expected profitability mechanism: If RRP balances are falling, cash may be leaving the Fed facility and private-market liquidity/risk appetite may improve, favoring a long NQ intraday risk-premium test.

Timing and causality: the feature file shifts RRP state by one listed trade date, so the RRP value is known before the NQ RTH session. The signal is emitted only after the configured 5-minute bar closes, and the engine enters at the next bar open or later with NQ costs, one-tick slippage, tick rounding, same-bar stop/target handling, and forced flatten.

Failure modes: RRP state can be an ambiguous slow-moving policy variable, broad thresholds can mix regimes, and same-day NQ movement may be too noisy after costs.


## Parameter-space rescue 1

Rescue keeps the 13:30 long timing but requires a stronger prior-day RRP decline so the setup expresses easing private-market funding capacity instead of a neutral RRP state. Entry, stop, target modules, data, costs, fills, sessions, and validation gates are unchanged. Rescue threshold grid: `entry.params.rrp_release_threshold=[-0.25, -0.375, -0.5]`. TP grid remains `[1.0, 1.5, 2.0]`; sub-1.0R targets are forbidden.


NQ port note: This variant was ported from the ES parameter-space rescue source before any NQ PnL was inspected. The NQ campaign does not authorize a post-result rescue.
