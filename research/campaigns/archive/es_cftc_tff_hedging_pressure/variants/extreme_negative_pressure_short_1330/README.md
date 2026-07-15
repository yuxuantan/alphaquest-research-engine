# extreme_negative_pressure_short_1330

Mechanic: At the completed 13:30 ET 5-minute bar, enter short when shifted SPX TFF open-interest change is below an extreme negative threshold; flatten at 15:55 ET unless stop or target is hit.

Edge rationale: Extreme negative pressure may indicate unusually one-sided risk transfer; a later short entry tests whether the premium is persistent rather than an opening-only effect.

Timeframe/session rationale: 5-minute RTH bars keep the weekly CFTC feature fixed before the intraday signal and preserve next-bar execution after a completed signal bar.

Lookahead controls: the `SPX_open_interest_chg13` row is keyed by shifted `trade_date`, and the module trades only from that session date. The signal uses the completed 13:30:00 bar close and enters at the next 5-minute bar open or later.

Parameter space: `entry.params.threshold` (3) x `sl.params.stop_pct` (3) x `tp.params.target_r_multiple` (3) = 27 combinations. Operator, direction, feature file, feature name, and entry time are fixed mechanics for this variant.
