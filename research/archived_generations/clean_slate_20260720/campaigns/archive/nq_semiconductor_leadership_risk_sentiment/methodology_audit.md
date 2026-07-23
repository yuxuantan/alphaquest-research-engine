# NQ Semiconductor Leadership Methodology Audit

Final decision: FAIL.

This campaign tests whether lagged semiconductor ETF leadership versus QQQ can
proxy a Nasdaq-specific industry information or risk-appetite state that affects
same-day NQ intraday drift. It is high duplicate risk because broad XLK/SPY tech
leadership and broad sector-rotation campaigns have already failed. It is not
treated as a clean independent edge unless the staged evidence is strong enough
to survive the full fail-closed workflow.

No same-day ETF close is used. Each NQ session may only use SMH, SOXX, and QQQ
daily observations available on or before the prior business day. Signals are
created on completed NQ 1-minute bars and may enter no earlier than the next bar
open. Positions flatten at 15:55 ET, before the configured prop-rule cutoff.

Predeclared official variants:

- smh_1d_leadership_long_1000
- smh_1d_nonleadership_short_1000
- smh_3d_leadership_long_1030
- soxx_3d_leadership_long_1130
- soxx_3d_nonleadership_short_1330

Each variant has one entry threshold, one stop parameter, and one target
parameter, for 27 official combinations. No rescue is authorized.

The pre-PnL density audit passed 45/45 declared rows. Four variants failed
limited_core_grid_test. The `soxx_3d_nonleadership_short_1330` branch passed
limited core but failed limited_monkey_test because the max-drawdown monkey beat
rate did not meet the 0.90 gate. No branch reached WFA, Monte Carlo, simulated
incubation, acceptance OOS, or candidate reporting.
