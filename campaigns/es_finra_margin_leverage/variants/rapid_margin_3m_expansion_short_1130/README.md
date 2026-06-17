# rapid_margin_3m_expansion_short_1130

Mechanic: at 11:30 ET, short ES when three-month FINRA customer margin-debt growth ranks in the upper tail of its 120-month history.

Lookahead control: the FINRA monthly observation is mapped to ES sessions only after a 35-calendar-day lag from month-end. The signal uses the completed 11:30 ET bar and enters next bar open.

Risk/execution: ES tick size 0.25, point value $50, one tick slippage, $2.50 commission, next-bar-open execution, pessimistic same-bar stop/target ordering, and 15:55 ET flatten are enforced by config.
