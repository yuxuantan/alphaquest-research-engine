# revolving_credit_to_income_low_long_1200 Strategy Modules

Entry module: `nq_consumer_credit_state`

Mechanic: At 12:00 ET, buy NQ when 60-day-lagged revolving consumer credit relative to disposable personal income ranks in the lower tail.

Rationale: Lower revolving-credit burden may identify reduced household financing stress, especially for discretionary and growth-sensitive equity exposure.

Availability rule: each NQ session can use only the latest monthly Federal Reserve/FRED consumer-credit observation on or before `session_date - 60 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.
