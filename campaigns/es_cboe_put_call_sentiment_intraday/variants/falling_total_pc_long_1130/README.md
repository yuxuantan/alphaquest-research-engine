# falling_total_pc_long_1130

Mechanic: at 11:30 ET, long ES when the latest prior total Cboe put/call ratio one-day change ranks in the lower tail of its 252-session history. The signal uses the completed 11:29-11:30 ET bar and enters next bar open.

Lookahead control: the put/call state uses only the latest Cboe observation strictly before the ES session date; same-day Cboe option volume is never available to the signal.

Risk/execution: ES tick size 0.25, point value $50, one tick slippage, $2.50 commission, next-bar-open execution, pessimistic same-bar stop/target ordering, and 15:55 ET flatten are enforced by the staged backtest config.
