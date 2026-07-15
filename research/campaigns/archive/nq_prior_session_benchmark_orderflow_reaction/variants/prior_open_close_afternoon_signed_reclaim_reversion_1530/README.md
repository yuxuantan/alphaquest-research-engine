# nq_prior_session_benchmark_orderflow_reaction / prior_open_close_afternoon_signed_reclaim_reversion_1530

Mechanic: Afternoon failed probe of either previous RTH open or previous RTH close with total signed-volume counterflow confirmation.

Entry module: `prior_session_benchmark_orderflow_reaction` with `both` levels, `signed_volume` counterflow, `13:00:00` to `15:30:00` ET signal window, and next-bar execution from completed 5-minute bars.

Stop module: `sweep_extreme` using the completed signal-bar sweep extreme plus the configured tick offset.

Target module: `fixed_r`, with same-session flatten at `15:55:00`.

No-lookahead controls: previous RTH open/close are from the completed prior RTH session only; probe, reclaim/reject close, and orderflow are read from completed bars only; no current-session final high/low, final VWAP, volume profile, future orderflow, or future return is used.
