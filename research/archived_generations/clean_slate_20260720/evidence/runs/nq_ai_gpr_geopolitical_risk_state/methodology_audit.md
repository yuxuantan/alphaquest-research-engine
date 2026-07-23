# NQ AI-GPR Geopolitical Risk State Methodology Audit

Verdict: FAIL.

This campaign used public daily AI-GPR geopolitical-risk data with a strict 30-calendar-day availability lag. For NQ session date D, the feature table can only use the latest AI-GPR observation on or before D minus 30 calendar days. Intraday signals fire on completed 1-minute NQ RTH bars and fill no earlier than the next bar open.

Pre-PnL density passed for all 15 declared entry rows across the five variants. No PnL was inspected before the five-variant source set and grids were frozen.

Staged testing halted at `limited_core_grid_test` for every variant. The best profitable-combination rate was `0.2962962962962963`, below the required `0.70` gate. No branch reached monkey robustness, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

No rescue was authorized and no mechanics were changed after staged PnL results.
