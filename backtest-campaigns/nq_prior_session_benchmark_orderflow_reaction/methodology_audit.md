# NQ Prior-Session Benchmark Open/Close Orderflow Reaction Methodology Audit

Verdict: FAIL.

This campaign tested exactly five NQ variants expressing one edge: completed-bar rejection of prior RTH open/close benchmark levels with same-bar aggregate counterflow confirmation. It was authored as a pre-PnL NQ transfer of `es_prior_session_benchmark_orderflow_reaction`; rescue was disabled.

Duplicate-edge review: this is distinct from NQ prior high/low breakout or reclaim, prior-session IBS, prior value-area acceptance, VWAP deviation, round-number barriers, opening-range retests, and standalone signed-flow persistence. The traded level is the prior RTH open or close, and the signal requires a completed probe-and-reclaim/reject plus counterflow.

No-lookahead review: previous RTH open/close are shifted from completed prior sessions only. Probe/reclaim/reject and orderflow use completed 5-minute bars. Entries occur no earlier than the next bar open. No final current-session high/low, final VWAP, future volume profile, future orderflow, or future return is used.

Density gate: exact ES transfer failed the strict NQ all-row density rule only for the `prior_open_midday_large20_reclaim_reversion_1400` expression. Before PnL inspection, the official NQ plan replaced that one sparse expression with `prior_open_midday_large10_reclaim_reversion_1400`. The official NQ density audit passed all 45 declared entry rows; weakest full-history density was 52.4006 signals/year, weakest limited-core density was 57.7393 signals/year, and weakest latest-252-session count was 54. Artifact: `research_artifacts/nq_prior_session_benchmark_orderflow_reaction_density_audit_20260630.md`.

Validation: focused tests passed with `python3 -m pytest -q tests/test_strategy_modules.py::test_prior_session_benchmark_orderflow_reaction_long_reclaim tests/test_strategy_modules.py::test_prior_session_benchmark_orderflow_reaction_short_rejects_prior_open_with_large20_flow tests/test_strategy_modules.py::test_prior_session_benchmark_orderflow_reaction_requires_counterflow_and_trade_limit`. Preflight passed for all five authored configs with `python3 -m research.preflight --config ... --skip-tests` after the focused test run.

Staged result: all five variants failed `limited_core_grid_test`. Across 270 official combinations, 0 were profitable, 0 passed benchmark gates, and 0 had Apex violations. The best limited-core row was `prior_open_close_afternoon_signed_reclaim_reversion_1530` with top net -892.5, PF 0.9012721238938053, 149 trades, profitable rate 0.0, and failure `min_total_net_profit`. The best variant profitable rate was 0.0, below the required 0.70 core gate.

Scientific-integrity decision: no rescue was authorized. The campaign failed before monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. It is closed as failed.
