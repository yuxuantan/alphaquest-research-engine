# falling_consumer_loan_delinquency_long_1330 Strategy Modules

Entry module: `nq_credit_quality_stress_state`

Mechanic: At 13:30 ET, buy NQ when the 120-day-lagged four-quarter change in consumer-loan delinquency rank is low, expressing improving consumer credit quality.

Rationale: Consumer-loan delinquency improvement tests whether broader household credit repair supports NQ risk appetite.

Availability rule: each NQ session can use only the latest quarterly FRED observation on or before `session_date - 120 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.
