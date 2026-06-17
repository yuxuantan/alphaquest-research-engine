# Core/Monkey Gate Change Audit - 2026-06-17

Scope: compare the current staged runner against archived campaign-test artifacts, focusing on whether limited core grid and monkey gates are stricter now than in `_archived`.

## Findings

1. The current staged runner canonicalizes `campaign_tests` before execution. For `limited_core_grid_test` and `limited_monkey_test`, configured `data_subset` is removed and replaced with the default shortlist window.

2. Current default shortlist window is the first 18 months of the configured dataset. Archived examples used a seeded random 18-month window with an avoid range:
   - archived `morning_orderflow_momentum` 1515 snapshot: `random_months`, 18 months, seed 31, avoid 2020-02-01 to 2021-06-30
   - active `es_volume_shock_liquidity_reversal/morning_down_shock_reversal_long/run1`: first 18 months, actual period 2011-01-03 to 2012-07-02

3. Current limited core is stricter than archived limited core:
   - current: valid combination count, at least 70% profitable iterations, at least one benchmark-passing combo, zero Apex/flatten violations
   - archived examples: minimum combination count, at least 70% profitable iterations, zero Apex/flatten violations

4. The new `number_passing_benchmark >= 1` criterion can halt runs that archived logic would have allowed into monkey/WFA. Examples observed in active outputs:
   - `es_cboe_vix_term_structure_intraday/contango_long_1030/rescue1`: 88.89% profitable, 0 benchmark-pass combos
   - `es_cboe_vix_term_structure_intraday/curve_flattening_short_1200/rescue1`: 70.37% profitable, 0 benchmark-pass combos
   - `es_spx_0dte_expiration_pressure/full_week_late_move_continuation_1430/run1`: 70.37% profitable, 0 benchmark-pass combos
   - `es_cboe_implied_correlation_intraday/high_short_term_correlation_short_1330/rescue1`: 92.59% profitable, 0 benchmark-pass combos

5. Current monkey is stricter than archived monkey:
   - archived monkey checked random-trade beat rates and Apex/flatten violations
   - current monkey also requires actual trade-path stress: profitable stress paths, positive median stress net, one-tick-worse slippage still profitable, and zero stress-path Apex/flatten violations
   - current limited monkey criteria use 90% net-profit and drawdown beat rates

6. A read-only diagnostic rerun of `es_volume_shock_liquidity_reversal/morning_down_shock_reversal_long/run1` over the archived 2013-09-03 to 2015-02-27 shortlist window still failed limited core:
   - 81 combinations
   - 4 profitable combinations, profitable rate 4.94%
   - 0 benchmark-pass combinations
   - top net profit 352.50, top trade count 7

## Interpretation

Yes, the current core/monkey gates are different from archived gates and can prevent some variants from reaching WFA that would have reached WFA under archived logic. The most material changes are the first-18-month shortlist window, `number_passing_benchmark >= 1`, and the added trade-path stress requirements.

For the active `volume_shock` variant checked here, the failure does not appear to be caused by the first-18-month shortlist window. It also fails badly on the archived random shortlist window.

The stricter gates are aligned with the current research methodology because they enforce enough-trades/profit-concentration requirements and realistic fill stress before WFA. If a separate exploratory triage mode is desired, it should be explicit and non-promotional; it should not be mixed with the pass/fail staged runner.
