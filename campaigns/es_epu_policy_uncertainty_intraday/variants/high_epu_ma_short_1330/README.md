# high_epu_ma_short_1330

Mechanic: at 13:30 ET, short ES when the 30-calendar-day-lagged 20-day average Daily U.S. EPU ranks in the upper tail. The signal uses the completed 13:29-13:30 ET bar and enters next bar open.

Lookahead control: the EPU state uses only the official Daily U.S. EPU observation on or before `session_date - 30 calendar days`; no same-day or recent-revision EPU value is available to the signal.

Risk/execution: ES tick size 0.25, point value $50, one tick slippage, $2.50 commission, next-bar-open execution, pessimistic same-bar stop/target ordering, and 15:55 ET flatten are enforced by the staged backtest config.
