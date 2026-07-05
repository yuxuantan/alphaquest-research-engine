# NQ Volume-Shock Liquidity Reversal Methodology Audit

Verdict: FAIL.

Rejected before staged NQ PnL: 3/45 declared entry-grid rows failed the pre-PnL density gate. The sparse rows were in `midday_symmetric_shock_reversion` at `min_volume_ratio=2.25` with `min_move_ticks` 6, 10, and 14; latest-252-session signal count was only 29 for each sparse row, and the 10/14-tick rows also failed the limited-core 50 signals/year gate. Dropping the strict 2.25 volume-ratio tier or the midday variant after this screen would be post-result narrowing of the declared five-variant edge. No NQ PnL was inspected.

The density audit counted deterministic entry opportunities on completed NQ 5-minute bars after building rolling-volume features with the same `prepare_data` ordering used by staged runs. No stop/target outcomes, trade net, benchmark rows, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting were inspected.

The density-passing variants are only density-passing rows, not candidate strategies. Selecting only those variants or removing the three sparse rows after this screen would violate the predeclared five-variant campaign protocol.
