# NQ Treasury Term Premium State Methodology Audit

Verdict: FAIL.

This campaign used public FRED daily THREEFYTP10 10-year Treasury term-premium data with a strict 7-calendar-day availability lag. For NQ session date D, the feature table can only use the latest daily observation on or before D minus 7 calendar days. Intraday signals fire on completed 1-minute NQ RTH bars and fill no earlier than the next bar open.

Pre-PnL density passed for all 15 declared entry rows across the five variants. No PnL was inspected before the five-variant source set and grids were frozen.

Staged testing halted at limited_core_grid_test for four variants. The high_21d_term_premium_rebound_long_1330 branch passed limited core with a profitable-combination rate of 1.0 but failed limited_monkey_test because net-profit beat rate was 0.84675 and max-drawdown beat rate was 0.866375, both below the 0.90 gate.

No branch reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. No rescue was authorized and no mechanics were changed after staged PnL results.
