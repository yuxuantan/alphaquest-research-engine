# low_participation_slack_short_1200 Strategy Modules

Entry module: `nq_labor_market_slack_state`

Mechanic: At 12:00 ET, short NQ when the 45-day-lagged labor-force participation rank is low.

Rationale: Low labor-force participation expresses labor-market damage not captured by unemployment alone.

Availability rule: each NQ session can use only the latest monthly FRED/BLS observation on or before `session_date - 45 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.
