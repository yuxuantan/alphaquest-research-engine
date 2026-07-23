# NQ Prior POC Orderflow Magnet Methodology Audit

Verdict: FAIL.

This campaign was sourced from ChartFanatics auction/profile material after the current ChartFanatics London Trident/FVG campaign failed density. It tests an NQ transfer of prior-session POC return-to-value with completed-bar aggregate orderflow confirmation. Existing NQ prior value-area acceptance campaigns use VAH/VAL continuation, not POC magnet reversion.

No staged PnL was inspected. The pre-PnL density audit used the repository `PriorPocOrderflowMagnetEntry` module on completed 5-minute NQ RTH bars from 2011-01-03 through 2026-06-12. Prior POC is built only after the previous RTH session is complete; signals are emitted only after the completed 5-minute signal bar close.

Density result: FAIL. Only 21 of 45 declared entry-grid rows passed all density gates, and only `late_morning_large10_two_sided_magnet` passed all nine entry rows. The four other variants had sparse latest-252 or entry-row failures. Dropping those variants after seeing this screen would be post-result narrowing of the declared five-variant edge.

Downstream stages not run: limited core grid, monkey, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, acceptance OOS, and candidate reporting.

Source caveat: ChartFanatics is practitioner research. The test is a deterministic local approximation using completed RTH OHLCV and aggregate Sierra orderflow, not true volume-at-price, depth, tape reading, or discretionary auction context.
