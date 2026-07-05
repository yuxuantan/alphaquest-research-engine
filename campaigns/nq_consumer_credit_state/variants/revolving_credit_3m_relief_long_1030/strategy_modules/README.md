# revolving_credit_3m_relief_long_1030 Strategy Modules

Entry module: `nq_consumer_credit_state`

Mechanic: At 10:30 ET, buy NQ when 60-day-lagged revolving consumer-credit three-month growth rank is in the lower tail.

Rationale: Low revolving-credit growth may proxy lower credit-card stress and cleaner household balance-sheet pressure after the release lag.

Availability rule: each NQ session can use only the latest monthly Federal Reserve/FRED consumer-credit observation on or before `session_date - 60 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.
