# five_day_dollar_up_short_1200

Mechanic: at 12:00 ET, short ES when the one-business-day-lagged broad U.S. dollar index five-day return ranks in the upper tail of its 252-observation history. The signal uses the completed 12:00 ET bar and enters next bar open.

Lookahead control: the dollar state uses only the latest FRED DTWEXBGS observation on or before the ES session date minus one business day; same-day dollar observations are never available to the signal.

Risk/execution: ES tick size 0.25, point value $50, one tick slippage, $2.50 commission, next-bar-open execution, pessimistic same-bar stop/target ordering, and 15:55 ET flatten are enforced by the staged backtest config.
