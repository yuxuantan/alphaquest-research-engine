# rising_macro_news_short_1000

Mechanic: A large lagged monthly rise in macro-news EMV may continue as risk-off pressure near the morning liquidity window. At 10:00:00 ET, use the completed prior 1-minute bar and enter no earlier than next bar open.

Lookahead control: EMV features are monthly FRED observations made eligible only after observation month-end plus 21 calendar days; the signal cannot see same-month EMV values.

Risk/execution: ES tick size 0.25, point value $50, one tick slippage, $2.50 commission, next-bar-open execution, pessimistic same-bar stop/target ordering, and 15:55 ET flatten are enforced by the staged config.
