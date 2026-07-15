# high_after_tax_profit_yoy_growth_long_1030 Strategy Modules

Entry module: `nq_corporate_profitability_state`

Mechanic: At 10:30 ET, buy NQ when the 120-day-lagged four-quarter after-tax corporate-profits growth rank is elevated.

Rationale: After-tax profit growth focuses on profits available after tax drag and may better track equity cash-flow support.

Availability rule: each NQ session can use only the latest quarterly FRED/BEA observation on or before `session_date - 120 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.
