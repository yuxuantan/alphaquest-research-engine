# NQ Infectious Disease EMV State Methodology Audit

Verdict: FAIL.

This campaign used public FRED daily INFECTDISEMVTRACKD infectious-disease EMV data with a strict 7-calendar-day availability lag. For NQ session date D, the feature table can only use the latest daily observation on or before D minus 7 calendar days. Intraday signals fire on completed 1-minute NQ RTH bars and fill no earlier than the next bar open.

Pre-PnL density passed for all 15 declared entry rows across the five variants. No PnL was inspected before the five-variant source set and grids were frozen.

Staged testing halted at limited_core_grid_test for four variants. The rising_5d_emv_short_1030 branch passed limited core with a profitable-combination rate of 0.7407407407407407 and 10 benchmark-passing cells, but failed limited_monkey_test because net-profit beat rate was 0.89 and max-drawdown beat rate was 0.769625, both below the 0.90 gate.

No branch reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. No rescue was authorized and no mechanics were changed after staged PnL results.
