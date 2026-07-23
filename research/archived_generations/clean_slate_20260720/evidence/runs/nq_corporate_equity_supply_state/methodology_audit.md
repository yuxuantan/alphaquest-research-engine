# NQ Corporate Equity Supply State Methodology Audit

Verdict: FAIL.

This campaign used public FRED quarterly Z.1 corporate financing data with a strict 180-calendar-day availability lag. For NQ session date D, the feature table can only use the latest quarterly observation on or before D minus 180 calendar days. Intraday signals fire on completed 1-minute NQ RTH bars and fill no earlier than the next bar open.

Pre-PnL density passed for all 15 declared entry rows across the five variants. No PnL was inspected before the five-variant source set and grids were frozen. The density audit's proxy window did not guarantee signals inside the fast-runtime staged core slice; staged validation still failed closed.

Staged testing halted at limited_core_grid_test for all five variants. Four variants produced zero trades in the actual fast-runtime limited-core slice; low_debt_minus_equity_short_1330 had the best profitable-combination rate at 0.07407407407407407, still below the 0.70 gate and with zero benchmark-passing combinations.

No branch reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. No rescue was authorized and no mechanics were changed after staged PnL results.
