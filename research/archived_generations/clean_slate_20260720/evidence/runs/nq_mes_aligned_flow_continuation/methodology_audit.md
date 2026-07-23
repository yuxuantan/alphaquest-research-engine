# NQ/MES Aligned Flow Continuation Methodology Audit

Verdict: FAIL.

This campaign tested exactly five NQ variants expressing one edge: NQ continuation only when completed NQ price movement and completed MES aggregate orderflow agree. It was a direct NQ transfer of the ES/MES aligned-flow continuation family before any NQ PnL inspection. Rescue was disabled.

No-lookahead review: NQ return windows and MES orderflow imbalance windows use only completed one-minute bars ending at the signal bar close. The entry module emits signals from completed bars, and the engine enters no earlier than the next bar open. MES is used only as an aligned-flow confirmation input, not as traded-instrument data. No final session high, final session low, final VWAP, volume profile, or future NQ/MES data is used.

Validation: module timing and campaign guardrail tests passed with `python3 -m pytest -q tests/test_es_mes_aligned_flow_continuation.py tests/test_es_mes_flow_divergence.py tests/test_nq_mes_aligned_flow_continuation.py`. Preflight passed for all five authored configs.

Staged result: all five variants failed `limited_core_grid_test`. Across 270 official combinations, 0 were profitable, 0 passed benchmark gates, and 0 had Apex violations. The top net row was `late_morning30_mes_signed_1130` with top net -757.5, PF 0.8711734693877551, 80 trades, and failure `limited_core failed: profitable_rate=0.0; benchmark_pass_combos=0; top_net=-757.5; top_pf=0.8711734693877551; top_trades=80; top_failure=min_total_net_profit`.

Scientific-integrity decision: no rescue was authorized. The campaign failed before monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. It is closed as failed.
