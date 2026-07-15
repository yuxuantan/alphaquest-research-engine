# high_dollar_up_short_1130

Mechanic: at 11:30 ET, short ES when the one-business-day-lagged broad U.S. dollar index is in a high level rank and its one-day return also ranks in the upper tail. The signal uses the completed 11:30 ET bar and enters next bar open.

Lookahead control: the dollar state uses only the latest FRED DTWEXBGS observation on or before the ES session date minus one business day; same-day dollar observations are never available to the signal.

Risk/execution: ES tick size 0.25, point value $50, one tick slippage, $2.50 commission, next-bar-open execution, pessimistic same-bar stop/target ordering, and 15:55 ET flatten are enforced by the staged backtest config.


## stop_distance_rescue_1

User-authorized additional rescue created on 2026-06-19. Source run: `es_dollar_risk_appetite_intraday/high_dollar_up_short_1130/run1`. Only stop distance was widened by 1.5x; entry, target/exit, data, costs, fills, sessions, and validation gates are unchanged.
