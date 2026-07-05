# NQ Overnight Range Compression Orderflow Breakout Methodology Audit

Verdict: FAIL.

This campaign tested exactly five NQ variants expressing one edge: completed ETH overnight range compression followed by a completed RTH breakout through the pre-known overnight high or low with same-direction aggregate orderflow. It was authored as a direct NQ transfer of the ES overnight-range compression orderflow breakout family before any NQ PnL inspection. Rescue was disabled.

Duplicate-edge review: this is distinct from the already rejected NQ prior-session NR compression, opening-gap continuation/fade, overnight sweep-reclaim reversion, overnight-return momentum, and midday range breakout families. The conditioning state is the completed ETH overnight range rank and the traded boundary is the overnight high/low fixed before the RTH decision window.

No-lookahead review: overnight high, low, midpoint, and range rank are built from ETH bars ending no later than 09:29 ET and are fixed before RTH signal evaluation. The RTH breakout and orderflow confirmation use completed 5-minute bars only, and the engine enters no earlier than the next bar open. Stop placement uses completed signal-bar extremes plus a declared offset. No final RTH range, final VWAP, final volume profile, future daily data, or future orderflow is used.

Density gate: pre-PnL density passed all 45 declared entry rows. Weakest full-history density was 63.0503 signals/year, weakest limited-core density was 67.4707 signals/year, and weakest latest-252-session count was 62. Artifact: `research_artifacts/nq_overnight_range_compression_orderflow_breakout_density_audit_20260630.md`.

Validation: focused tests passed with `python3 -m pytest -q tests/test_overnight_range_orderflow_breakout.py tests/test_nq_overnight_range_compression_orderflow_breakout.py`. Preflight passed for all five authored configs with `python3 -m research.preflight --config ...`.

Staged result: all five variants failed `limited_core_grid_test`. Across 405 official combinations, 21 were profitable, 0 passed benchmark gates, and 0 had Apex violations. Best limited-core row was `late_morning_large10_two_sided_breakout_1130` with top net 387.5, PF 1.068888888888889, 125 trades, profitable rate 0.111111, and failure `max_best_day_concentration`. The best variant profitable rate was 0.148148, below the required 0.70 core gate.

Scientific-integrity decision: no rescue was authorized. The campaign failed before monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. It is closed as failed.
