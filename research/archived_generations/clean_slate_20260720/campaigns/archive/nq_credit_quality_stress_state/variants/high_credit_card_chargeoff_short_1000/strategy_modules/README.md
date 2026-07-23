# high_credit_card_chargeoff_short_1000 Strategy Modules

Entry module: `nq_credit_quality_stress_state`

Mechanic: At 10:00 ET, short NQ when the 120-day-lagged credit-card charge-off rate rank is elevated.

Rationale: Credit-card charge-offs represent household credit-quality stress with high consumer-risk sensitivity.

Availability rule: each NQ session can use only the latest quarterly FRED observation on or before `session_date - 120 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.
