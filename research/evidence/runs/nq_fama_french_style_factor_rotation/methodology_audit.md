# NQ Fama-French Style Factor Rotation Methodology Audit

Verdict: FAIL.

This campaign used Kenneth French daily HML, RMW, and CMA factor returns with a strict 45-calendar-day availability lag. For NQ session date D, the feature table can only use the latest factor observation on or before D minus 45 calendar days. Intraday signals fire on completed 1-minute NQ RTH bars and fill no earlier than the next bar open.

Pre-PnL density passed for all 15 declared entry rows across the five variants. One density-only threshold replacement was made before any PnL inspection: `hml_21d_growth_strength_long_1030` replaced the 0.25 low-tail HML threshold with 0.40 because the initial row had 48 latest-252-session signals versus the 50-session floor.

Staged testing halted before WFA. Four variants failed `limited_core_grid_test`. `hml_21d_value_strength_short_1000` passed core breadth but failed `limited_monkey_test` because the core drawdown beat rate versus random-entry controls was 0.653875, below the 0.90 gate.

No rescue was authorized and no mechanics were changed after staged PnL results.
