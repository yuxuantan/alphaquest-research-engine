# low_sentiment_ma_long_1330

Mechanic: at 13:30 ET, long ES when the 45-calendar-day-lagged 12-month average University of Michigan consumer sentiment ranks in the lower tail. The signal uses the completed 13:29-13:30 ET bar and enters next bar open.

Lookahead control: the sentiment state uses only the latest UMCSENT observation on or before `session_date - 45 calendar days`; no current-month survey value is available to the signal.

Risk/execution: ES tick size 0.25, point value $50, one tick slippage, $2.50 commission, next-bar-open execution, pessimistic same-bar stop/target ordering, and 15:55 ET flatten are enforced by the staged backtest config.
