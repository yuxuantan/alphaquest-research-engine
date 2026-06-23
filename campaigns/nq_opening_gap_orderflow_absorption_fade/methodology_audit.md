# Methodology audit - NQ opening gap orderflow absorption fade

## Pre-test status

Decision: TESTING

This campaign is authored before inspecting NQ PnL for these five gap-fade variants. Entry thresholds are selected from NQ counter-gap flow density only.

## No-lookahead review

- `prev_rth_close` is derived from completed prior sessions through `feature_set: pdh_pdl_sweep`.
- The current RTH open is recorded at the open, but the signal waits for a completed source window.
- Counter-gap aggregate flow is completed before the signal timestamp.
- Gap-fill targets use only the known prior RTH close and next-bar entry price.
- Strategy flatten is `15:55:00` ET and prop-firm flatten rules remain config-driven.

## Parameter discipline

Each variant declares exactly two entry-grid dimensions, one stop-grid dimension, and one target-grid dimension for 81 total combinations. No rescue is authorized.

## Post-test verdict - 2026-06-22T16:35:17

Decision: FAIL

All five variants failed `limited_core_grid_test`. No downstream monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate-report stage was reached.

Generated aggregate report: `backtest-campaigns/nq_opening_gap_orderflow_absorption_fade/campaign_test_summary.json`.
