# nq_prior_session_benchmark_orderflow_reaction / prior_close_morning_signed_reclaim_reversion_1130

Mechanic: Morning two-sided failed probe of the completed previous RTH close with total signed-volume counterflow confirmation.

Entry module: `prior_session_benchmark_orderflow_reaction` with `previous_close` levels, `signed_volume` counterflow, `09:35:00` to `11:30:00` ET signal window, and next-bar execution from completed 5-minute bars.

Stop module: `sweep_extreme` using the completed signal-bar sweep extreme plus the configured tick offset.

Target module: `fixed_r`, with same-session flatten at `12:30:00`.

No-lookahead controls: previous RTH open/close are from the completed prior RTH session only; probe, reclaim/reject close, and orderflow are read from completed bars only; no current-session final high/low, final VWAP, volume profile, future orderflow, or future return is used.
