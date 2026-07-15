# NQ Connors RSI2 Intraday Mean Reversion Methodology Audit

Verdict: FAIL.

This campaign tested exactly five NQ variants expressing one edge: completed-bar two-period RSI extremes filtered by same-session moving-average or cumulative VWAP context, with next-bar execution and same-day flattening. It was authored as a pre-PnL NQ transfer of `es_connors_rsi2_mean_reversion`; rescue was disabled.

Duplicate-edge review: this is distinct from the already rejected NQ daily short-term reversal, prior-session IBS reversion, intraday capitulation snapback, VWAP-deviation/orderflow reversion, rolling statistical-envelope reversion, measured-move pullback, and EMA pullback continuation families. The traded state is same-session completed-bar RSI2 overextension, not prior-session close location, daily return, high-volume sell flush, VWAP/orderflow dislocation, rolling band touch, measured projection, or EMA reclaim.

No-lookahead review: RSI2, moving-average state, and cumulative VWAP use completed bars only. Signal timestamps are completed bar closes and the engine enters no earlier than the next bar open. VWAP is cumulative through the signal bar, not final session VWAP. No final session high/low, final volume profile, future range, future orderflow, or post-entry data is used.

Density gate: the initial pre-PnL grid failed 4 of 45 entry rows because strict 15-minute RSI5 long and RSI95 short extremes were too sparse. That failed screen is preserved at `research_artifacts/nq_connors_rsi2_mean_reversion_initial_density_rejected_20260630.md`. Before any PnL inspection, the final grid conservatively dropped those broad sparse extremes from the affected 15-minute variants. The final density audit passed all 39 declared entry rows. Weakest full-history density was 52.0768 signals/year, weakest limited-core density was 52.5493 signals/year, and weakest latest-252-session count was 51. Artifact: `research_artifacts/nq_connors_rsi2_mean_reversion_density_audit_20260630.md`.

Validation: focused tests passed with `python3 -m pytest -q tests/test_strategy_modules.py::test_connors_rsi2_mean_reversion_emits_metadata_driven_long_signal tests/test_strategy_modules.py::test_connors_rsi2_mean_reversion_requires_vwap_extension tests/test_nq_connors_rsi2_mean_reversion.py`. Preflight passed for all five authored configs with `python3 -m research.preflight --config ...`.

Staged result: all five variants failed `limited_core_grid_test`. Across 351 official combinations, 14 were profitable, 3 passed benchmark gates, and 0 had Apex violations. Best limited-core row was `five_min_short_vwap_extreme_1430` with top net 2770.0, PF 1.115996649916248, 169 trades, profitable rate 0.061728, and failure `max_consecutive_losses`. The best variant profitable rate was 0.074074, below the required 0.70 core gate.

Scientific-integrity decision: no rescue was authorized. The campaign failed before monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. It is closed as failed.
