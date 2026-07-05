# confirmed_ci_demand_strength_long_1330 Strategy Modules

Entry module: `nq_sloos_bank_lending_survey_state`

Mechanic: At 13:30 ET, buy NQ when both the 75-day-lagged large-firm and small-firm C&I loan-demand ranks are elevated.

Rationale: The min-rank expression requires confirmed C&I demand strength across borrower-size segments.

Availability rule: each NQ session can use only the latest quarterly Federal Reserve/FRED SLOOS observation on or before `session_date - 75 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.
