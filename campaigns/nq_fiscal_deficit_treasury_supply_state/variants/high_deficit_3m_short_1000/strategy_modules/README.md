# high_deficit_3m_short_1000 Strategy Modules

Entry module: `nq_fiscal_deficit_treasury_supply_state`

Mechanic: At 10:00 ET, short NQ when the 60-day-lagged three-month federal deficit sum rank is in the upper tail.

Rationale: A large recent deficit may proxy higher Treasury financing/supply pressure and fiscal-risk discounting that weighs on growth-equity risk appetite.

Availability rule: each NQ session can use only the latest monthly Treasury/FRED Monthly Treasury Statement observation on or before `session_date - 60 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.
