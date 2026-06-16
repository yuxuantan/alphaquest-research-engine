# broad_positive_pressure_long_1100

Mechanic: At the completed 11:00 ET 5-minute bar, enter long when shifted SPX TFF open-interest change is above a broad positive threshold; flatten at 15:55 ET unless stop or target is hit.

Edge rationale: Broad positive SPX TFF open-interest pressure may mark equity-index risk-transfer demand that earns a same-day long premium after the CFTC feature is available.

Timeframe/session rationale: 5-minute RTH bars keep the weekly CFTC feature fixed before the intraday signal and preserve next-bar execution after a completed signal bar.

Lookahead controls: the `SPX_open_interest_chg13` row is keyed by shifted `trade_date`, and the module trades only from that session date. The signal uses the completed 11:00:00 bar close and enters at the next 5-minute bar open or later.

Parameter space: `entry.params.threshold` (3) x `sl.params.stop_pct` (3) x `tp.params.target_r_multiple` (3) = 27 combinations. Operator, direction, feature file, feature name, and entry time are fixed mechanics for this variant.
