# Methodology audit - NQ Gao last-half-hour orderflow confirmation

## Pre-test status

Decision: TESTING

This campaign was authored before inspecting any NQ PnL for these five variants. The threshold ranges were selected from unconditional NQ first-window return and imbalance distributions only.

## No-lookahead review

- Source windows are completed before the 15:30 ET signal timestamp.
- The entry module emits at the bar close matching `last_window_start`; the engine fills after signal generation.
- Stops use `percent_from_entry`; targets use `fixed_r`.
- Forced strategy flatten is `15:55:00` ET and prop-firm flatten rules remain config-driven.
- No final session statistic, future VWAP, future range, or post-entry orderflow is referenced by the entry decision.

## Parameter discipline

Each variant declares exactly two entry-grid dimensions, one stop-grid dimension, and one target-grid dimension for 81 total combinations. No rescue is authorized.

## Required next step

Run the full staged flow for all five variants. If a variant fails at core, monkey, WFA, Monte Carlo, acceptance OOS, simulated incubation, or prop-rule simulation, mark it failed and do not tune mechanics after seeing results.

## Post-test verdict - 2026-06-22T16:01:32

Decision: FAIL

All five variants failed `limited_core_grid_test`. No downstream monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or prop-rule promotion stage was reached.

- Best profitable-combo rate: `first30_large20_flow_two_sided_1530` at 33/81 = 0.4074, below the 0.70 gate.
- Highest top-row net profit: `first30_broad_large_alignment_1530` with top net 652.5, but only 10 trades and failed trade-density gates.
- No rescue was authorized or applied.

Generated aggregate report: `backtest-campaigns/nq_gao_last_half_hour_orderflow_confirmation/campaign_test_summary.json`.
