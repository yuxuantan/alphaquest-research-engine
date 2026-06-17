# Methodology-Fix Reruns - 2026-06-17

Reason: after fixing the limited core-grid screening benchmark, rerun selected
active non-archived variants that previously showed at least 70% profitable
core-grid combinations but were stopped by full-stage benchmark fields that are
now reserved for WFA and later stages.

No mechanics, parameters, data, costs, sessions, or rescue spaces were changed.
Temporary source configs only changed `test_run_id` to `methodology_fix_rerun1`
so old `rescue1` artifacts remain intact.

## Results

| campaign | variant | corrected core | monkey stress | decision |
|---|---:|---:|---:|---|
| `es_cboe_implied_correlation_intraday` | `high_short_term_correlation_short_1330` | passed: profitable rate `0.9259259259259259`, benchmark pass `6` | failed: stress profitable rate `0.5633333333333334`, one-tick net `-1401.25` | FAIL |
| `es_cboe_vix_term_structure_intraday` | `contango_long_1030` | passed: profitable rate `0.8888888888888888`, benchmark pass `8` | failed: stress profitable rate `0.6166666666666667`, one-tick net `-955.0` | FAIL |
| `es_cboe_vix_term_structure_intraday` | `curve_flattening_short_1200` | passed: profitable rate `0.7037037037037037`, benchmark pass `4` | failed: stress profitable rate `0.6833333333333333`, one-tick net `-1082.5` | FAIL |
| `es_market_plumbing_liquidity_capacity` | `dual_pressure_priority_long_1130` | failed: profitable rate `0.8888888888888888`, benchmark pass `0`; all top rows failed `max_consecutive_losses` | not reached | FAIL |
| `es_vwap_pullback_continuation` | `midday_trend_reclaim_two_sided` | passed: profitable rate `0.8148148148148148`, benchmark pass `9` | failed: stress profitable rate `0.8866666666666667`, median net `1221.226646360949`, but one-tick net `-203.75` | FAIL |
| `es_oil_price_shock_spillover` | `wti_up_risk_off_short_1030` | passed: profitable rate `0.7777777777777778`, benchmark pass `3` | passed: stress profitable rate `0.8333333333333334`, one-tick net `382.5`; WFA failed first-window train PF `0.93 < 1.00` | FAIL |
| `es_spx_0dte_expiration_pressure` | `full_week_late_move_continuation_1430` | passed: profitable rate `0.7037037037037037`, benchmark pass `15` | passed: stress profitable rate `0.8133333333333334`, median net `2056.226368778107`, one-tick net `1647.5`; WFA failed early exit at window 4 with selected train PF `0.91 < 1.00`, stitched OOS PF `0.5178719866999169`, MAR `-1.368206562790248` | FAIL |

## Artifacts

- `backtest-campaigns/es_cboe_implied_correlation_intraday/high_short_term_correlation_short_1330/ES/methodology_fix_rerun1/campaign_test_summary.json`
- `backtest-campaigns/es_cboe_vix_term_structure_intraday/contango_long_1030/ES/methodology_fix_rerun1/campaign_test_summary.json`
- `backtest-campaigns/es_cboe_vix_term_structure_intraday/curve_flattening_short_1200/ES/methodology_fix_rerun1/campaign_test_summary.json`
- `backtest-campaigns/es_market_plumbing_liquidity_capacity/dual_pressure_priority_long_1130/ES/methodology_fix_rerun1/campaign_test_summary.json`
- `backtest-campaigns/es_vwap_pullback_continuation/midday_trend_reclaim_two_sided/ES/methodology_fix_rerun1/campaign_test_summary.json`
- `backtest-campaigns/es_oil_price_shock_spillover/wti_up_risk_off_short_1030/ES/methodology_fix_rerun1/campaign_test_summary.json`
- `backtest-campaigns/es_spx_0dte_expiration_pressure/full_week_late_move_continuation_1430/ES/methodology_fix_rerun1/campaign_test_summary.json`

## Conclusion

These variants were legitimate core-screen false negatives under the old
limited benchmark gate or old random-placebo monkey gate, but none passed WFA
under the corrected methodology. Four failed corrected monkey stress; one
failed corrected core screening because no parameter row passed the max losing
streak check; two passed core and monkey but failed WFA on in-sample selection
or stitched OOS economics. They are rejected and should not be promoted to
candidate review.
