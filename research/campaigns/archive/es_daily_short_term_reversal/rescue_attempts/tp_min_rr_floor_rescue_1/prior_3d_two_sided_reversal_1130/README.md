# prior_3d_two_sided_reversal_1130

At the 11:30 ET completed 5-minute bar, fade the completed three-session RTH close-to-close move: long after a sufficiently negative move and short after a sufficiently positive move.

The signal uses only prior completed RTH closes and expresses the same short-term liquidity-provision reversal thesis over a slightly longer recent-return window.

Rescue attempt 1 keeps the same two-sided direction mode, lookback, signal time, modules, data, costs, and gates. It changes only the declared threshold, stop, and target parameter space plus matching fixed defaults.


## tp_min_rr_floor_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_daily_short_term_reversal/prior_3d_two_sided_reversal_1130/rescue1`. Only target_r_multiple values below 1.0R were raised to 1.0R; entry, stop, data, costs, fills, sessions, and validation gates are unchanged.
