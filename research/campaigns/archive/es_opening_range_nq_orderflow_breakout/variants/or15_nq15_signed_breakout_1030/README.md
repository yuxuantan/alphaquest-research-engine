# or15_nq15_signed_breakout_1030

15-minute ES opening range breakout before 10:30 ET with 15-minute NQ leadership and ES signed-flow confirmation.

This variant belongs to `es_opening_range_nq_orderflow_breakout` and uses only the local ES/NQ Sierra completed-bar lead-lag cache. No paid data is required or downloaded.

Entry mechanics are fixed before PnL testing: freeze the completed ES opening range, require a completed close outside the range, require same-bar ES signed-flow alignment, require NQ to lead ES in the breakout direction over the configured completed lookback, then enter ES on the next bar open. Stops use the opposite opening-range edge with a max-risk cap; targets are fixed-R and positions flatten intraday.
