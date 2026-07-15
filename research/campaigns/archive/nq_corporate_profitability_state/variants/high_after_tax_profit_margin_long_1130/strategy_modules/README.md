# high_after_tax_profit_margin_long_1130 Strategy Modules

Entry module: `nq_corporate_profitability_state`

Mechanic: At 11:30 ET, buy NQ when the 120-day-lagged after-tax-profits-to-GDP rank is elevated.

Rationale: After-tax profit share of GDP expresses a profit-margin state rather than pure profit growth.

Availability rule: each NQ session can use only the latest quarterly FRED/BEA observation on or before `session_date - 120 calendar days`; the one-minute signal uses a completed RTH bar and is intended for next-bar execution.

Stop module: `percent_from_entry` with predeclared `stop_pct` grid `[0.003, 0.004, 0.005]`.

Take-profit module: `fixed_r` with predeclared `target_r_multiple` grid `[1.5, 2.0, 2.5]`.
