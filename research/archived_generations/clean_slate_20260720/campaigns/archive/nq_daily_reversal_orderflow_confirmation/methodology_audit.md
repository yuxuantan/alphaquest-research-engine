# NQ Daily Reversal With Aggregate Orderflow Confirmation Methodology Audit

Verdict: FAIL.

This campaign tested exactly five NQ variants expressing one edge: fading completed prior RTH close-to-close returns only when completed same-session aggregate orderflow confirms the reversal direction. It was authored as a pre-PnL NQ transfer of `es_daily_reversal_orderflow_confirmation`; rescue was disabled.

Duplicate-edge review: this is distinct from raw NQ daily short-term reversal because orderflow confirmation is mandatory, and distinct from standalone orderflow persistence because the primary state is a prior completed daily return that is faded.

No-lookahead review: prior returns use only completed RTH closes before the signal session. Orderflow windows end at the completed signal bar. Entries occur no earlier than the next bar open. No final current-session close, high/low, final VWAP, future volume, or future orderflow is used.

Density gate: pre-PnL density passed all 45 declared entry rows. Weakest full-history density was 63.4119 signals/year, weakest limited-core density was 92.7722 signals/year, and weakest latest-252-session count was 58. Artifact: `research_artifacts/nq_daily_reversal_orderflow_confirmation_density_audit_20260630.md`.

Validation: focused tests passed with `python3 -m pytest -q tests/test_daily_reversal_orderflow_confirmation.py tests/test_nq_daily_reversal_orderflow_confirmation.py`. Preflight passed for all five authored configs with `python3 -m research.preflight --config ...`.

Staged result: all five variants failed `limited_core_grid_test`. Across 270 official combinations, 2 were profitable, 0 passed benchmark gates, and 0 had Apex violations. Best limited-core row was `first150_5d_flow_confirm_1200` with top net 230.0, PF 1.02683780630105, 146 trades, profitable rate 0.037037, and failure `max_best_day_concentration`. The best variant profitable rate was 0.037037, below the required 0.70 core gate.

Scientific-integrity decision: no rescue was authorized. The campaign failed before monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. It is closed as failed.
