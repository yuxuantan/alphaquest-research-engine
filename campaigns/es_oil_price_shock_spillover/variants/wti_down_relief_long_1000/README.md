# wti_down_relief_long_1000

Mechanic: at 10:00 ET, long ES when the two-business-day-lagged WTI one-day return ranks in the lower tail of its 252-session history. The signal uses the completed 10:00 ET bar and enters next bar open.

Lookahead control: the oil state uses only the latest EIA WTI/Brent observation on or before the ES session date minus two business days; same-day oil observations are never available to the signal.

Risk/execution: ES tick size 0.25, point value $50, one tick slippage, $2.50 commission, next-bar-open execution, pessimistic same-bar stop/target ordering, and 15:55 ET flatten are enforced by the staged backtest config.
