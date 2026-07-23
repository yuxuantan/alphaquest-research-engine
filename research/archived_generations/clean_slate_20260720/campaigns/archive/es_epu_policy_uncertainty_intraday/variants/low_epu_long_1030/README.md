# low_epu_long_1030

Mechanic: at 10:30 ET, long ES when the 30-calendar-day-lagged Daily U.S. EPU index ranks in the lower tail of its 252-session history. The signal uses the completed 10:29-10:30 ET bar and enters next bar open.

Lookahead control: the EPU state uses only the official Daily U.S. EPU observation on or before `session_date - 30 calendar days`; no same-day or recent-revision EPU value is available to the signal.

Risk/execution: ES tick size 0.25, point value $50, one tick slippage, $2.50 commission, next-bar-open execution, pessimistic same-bar stop/target ordering, and 15:55 ET flatten are enforced by the staged backtest config.
