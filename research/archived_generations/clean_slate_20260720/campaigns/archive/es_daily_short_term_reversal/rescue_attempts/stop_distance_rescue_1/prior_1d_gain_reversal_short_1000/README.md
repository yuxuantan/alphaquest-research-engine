# prior_1d_gain_reversal_short_1000

Short ES at the 10:00 ET completed 5-minute bar when the prior completed one-session RTH close-to-close return is positive by at least the configured threshold. This is the short-side expression of the daily short-term reversal edge.

The signal uses only prior RTH closes recorded after completed sessions. The current session close is not part of the return calculation, and the engine must enter no earlier than the next bar open.

Rescue attempt 1 keeps the same side, lookback, signal time, modules, data, costs, and gates. It changes only the declared threshold, stop, and target parameter space plus matching fixed defaults.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_daily_short_term_reversal/prior_1d_gain_reversal_short_1000/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
