# debit_credit_ratio_expansion_short_1330

Mechanic: at 13:30 ET, short ES when the three-month change in FINRA debit balances relative to customer free-credit balances ranks in the upper tail of its 120-month history.

Lookahead control: the FINRA monthly observation is mapped to ES sessions only after a 35-calendar-day lag from month-end. The signal uses the completed 13:30 ET bar and enters next bar open.

Risk/execution: ES tick size 0.25, point value $50, one tick slippage, $2.50 commission, next-bar-open execution, pessimistic same-bar stop/target ordering, and 15:55 ET flatten are enforced by config.
