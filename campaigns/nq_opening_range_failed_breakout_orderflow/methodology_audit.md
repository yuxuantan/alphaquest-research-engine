# NQ Opening-Range Failed Breakout Orderflow Methodology Audit

Verdict: FAIL.

Rejected before staged NQ PnL: 2/29 declared entry-grid rows failed the pre-PnL density gate. The sparse rows were in `or60_signed_failed_reclaim_1200` at `min_reclaim_orderflow_imbalance=0.10` with `max_reclaim_bars` 3 and 4; latest-252-session signal counts were 24 and 25, and the 3-bar row also fell below 50 signals/year over full history. Dropping the strict 0.10 imbalance tier or the OR60 variant after this screen would be post-result narrowing of the declared five-variant edge. No NQ PnL was inspected.

The density audit used the actual `OpeningRangeFailedBreakoutOrderflowEntry` state machine on prepared completed NQ 5-minute bars. No stop/target outcomes, trade net, benchmark rows, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting were inspected.

The density-passing variants are only density-passing rows, not candidate strategies. Selecting only those variants or removing the two sparse rows after this screen would violate the predeclared five-variant campaign protocol.
