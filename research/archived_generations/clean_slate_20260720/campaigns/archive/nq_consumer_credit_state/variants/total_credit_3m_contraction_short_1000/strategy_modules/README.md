# total_credit_3m_contraction_short_1000 Strategy Modules

Entry module: `nq_consumer_credit_state`

Mechanic: At 10:00 ET, short NQ when 60-day-lagged total consumer-credit three-month growth rank is in the lower tail.

Rationale: Weak total-credit growth may proxy household deleveraging or weaker consumer credit demand that can pressure growth-equity risk appetite.

Availability rule: each NQ session can use only the latest monthly Federal Reserve/FRED consumer-credit observation on or before `session_date - 60 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.
