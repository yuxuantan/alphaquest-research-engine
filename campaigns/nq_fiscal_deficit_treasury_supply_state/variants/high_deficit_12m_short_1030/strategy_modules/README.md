# high_deficit_12m_short_1030 Strategy Modules

Entry module: `nq_fiscal_deficit_treasury_supply_state`

Mechanic: At 10:30 ET, short NQ when the 60-day-lagged twelve-month federal deficit sum rank is in the upper tail.

Rationale: Persistent large deficits may proxy sustained Treasury supply and fiscal-risk pressure rather than a one-month fiscal-calendar artifact.

Availability rule: each NQ session can use only the latest monthly Treasury/FRED Monthly Treasury Statement observation on or before `session_date - 60 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.
