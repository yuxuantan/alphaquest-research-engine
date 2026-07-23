# nq_prior_session_benchmark_orderflow_reaction / prior_open_midday_large10_reclaim_reversion_1400

Mechanic: Midday failed probe of the previous RTH open requiring large-10 trade-size counterflow on the reclaim/rejection bar.

Entry module: `prior_session_benchmark_orderflow_reaction` with `previous_open` levels, `large10` counterflow, `11:00:00` to `14:00:00` ET signal window, and next-bar execution from completed 5-minute bars.

Stop module: `sweep_extreme` using the completed signal-bar sweep extreme plus the configured tick offset.

Target module: `fixed_r`, with same-session flatten at `15:00:00`.

No-lookahead controls: previous RTH open/close are from the completed prior RTH session only; probe, reclaim/reject close, and orderflow are read from completed bars only; no current-session final high/low, final VWAP, volume profile, future orderflow, or future return is used.
