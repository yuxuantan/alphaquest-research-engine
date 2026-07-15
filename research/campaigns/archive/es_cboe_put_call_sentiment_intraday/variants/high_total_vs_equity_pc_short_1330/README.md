# high_total_vs_equity_pc_short_1330

Mechanic: at 13:30 ET, short ES when total Cboe put/call is high versus equity put/call on the latest prior Cboe observation. The signal uses the completed 13:29-13:30 ET bar and enters next bar open.

Lookahead control: the put/call state uses only the latest Cboe observation strictly before the ES session date; same-day Cboe option volume is never available to the signal.

Risk/execution: ES tick size 0.25, point value $50, one tick slippage, $2.50 commission, next-bar-open execution, pessimistic same-bar stop/target ordering, and 15:55 ET flatten are enforced by the staged backtest config.
