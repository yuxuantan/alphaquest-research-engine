# extreme_positive_pressure_long_1330

Mechanic: At the completed 13:30 ET 5-minute bar, enter long when shifted SPX TFF open-interest change is above an extreme positive threshold; flatten at 15:55 ET unless stop or target is hit.

Edge rationale: Extreme positive pressure may be slow-moving enough that a later RTH entry still captures residual risk premium while avoiding the open.

Timeframe/session rationale: 5-minute RTH bars keep the weekly CFTC feature fixed before the intraday signal and preserve next-bar execution after a completed signal bar.

Lookahead controls: the `SPX_open_interest_chg13` row is keyed by shifted `trade_date`, and the module trades only from that session date. The signal uses the completed 13:30:00 bar close and enters at the next 5-minute bar open or later.

Parameter space: `entry.params.threshold` (3) x `sl.params.stop_pct` (3) x `tp.params.target_r_multiple` (3) = 27 combinations. Operator, direction, feature file, feature name, and entry time are fixed mechanics for this variant.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_cftc_tff_hedging_pressure/extreme_positive_pressure_long_1330/rescue1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
