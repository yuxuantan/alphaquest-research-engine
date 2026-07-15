# low_employment_ratio_slack_short_1130 Strategy Modules

Entry module: `nq_labor_market_slack_state`

Mechanic: At 11:30 ET, short NQ when the 45-day-lagged employment-population ratio rank is low.

Rationale: A low employment-population ratio expresses labor-market slack from weak employment breadth.

Availability rule: each NQ session can use only the latest monthly FRED/BLS observation on or before `session_date - 45 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.
