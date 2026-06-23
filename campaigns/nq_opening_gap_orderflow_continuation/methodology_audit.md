# Methodology audit - NQ opening gap orderflow continuation

## Pre-test status

Decision: TESTING

This campaign is authored before inspecting NQ PnL for these five opening-gap continuation variants. Thresholds are selected from NQ opening-gap and completed source-window signal-density distributions only.

## No-lookahead review

- `prev_rth_close` is derived from completed prior sessions through `feature_set: pdh_pdl_sweep`.
- The current RTH open is recorded at the open, but the signal waits for a completed source window.
- Gap-hold, source-window return, and aggregate flow are all completed before the signal timestamp.
- The engine fills after signal generation; stops use the prior-close boundary with a predeclared max-stop cap.
- Strategy flatten is `15:55:00` ET and prop-firm flatten rules remain config-driven.

## Parameter discipline

Each variant declares exactly two entry-grid dimensions, one stop-grid dimension, and one target-grid dimension for 81 total combinations. No rescue is authorized.

## Post-test verdict - 2026-06-22T16:25:37

Decision: FAIL

No variant completed the full staged flow. `early_signed_gap_hold_continuation_1000` and `morning_signed_gap_hold_continuation_1030` reached `limited_monkey_test` and failed robustness. The other three variants failed `limited_core_grid_test`.

Generated aggregate report: `backtest-campaigns/nq_opening_gap_orderflow_continuation/campaign_test_summary.json`.
