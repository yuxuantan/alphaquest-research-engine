# NQ Prior-Session S/R Flip Retest Orderflow Methodology Audit

Verdict: FAIL.

This campaign tested exactly five NQ variants expressing one edge: a previous RTH high/low breaks, later retests from the other side, and confirms with completed retest-bar aggregate orderflow. It was authored as a pre-PnL transfer of `es_prior_session_flip_retest_orderflow`; no NQ rescue was authorized.

Duplicate-edge review: this is distinct from NQ price-only prior-session retest continuation and immediate breakout-with-orderflow because it requires retest-bar orderflow confirmation on the later S/R flip retest. It is also distinct from prior-day stop-run reclaim, prior open/close benchmark reactions, opening-range retests, round-number barriers, and value-area acceptance/rejection.

No-lookahead review: prior RTH levels are from completed prior sessions only. Breakout, retest-hold, and orderflow conditions use completed 5-minute bars. Entries occur no earlier than the next bar open. No final current-session high/low, final VWAP, future volume profile, future orderflow, or future return is used.

Density gate: passed before PnL inspection. All 45/45 declared entry rows passed all density windows. Weakest full-history density was 72.37 signals/year, weakest limited-core proxy density was 75.40 signals/year, and weakest latest-252-session count was 56. Artifact: `research_artifacts/nq_prior_session_flip_retest_orderflow_density_audit_20260630.md`.

Validation: focused tests passed with `python3 -m pytest tests/test_pdh_pdl_orderflow_breakout_continuation.py -q` and `python3 -m pytest tests/test_strategy_modules.py::test_pdh_pdl_breakout_continuation_retest_waits_for_next_bar -q`. Preflight passed for all five configs with `python3 -m research.preflight --config ... --skip-tests`.

Staged result: four variants failed `limited_core_grid_test`. `morning_signed_aligned_two_sided_flip` passed limited core with 54/54 profitable and benchmark-passing combinations, passed limited monkey with core beating random-entry net profit in 0.992625 of runs and drawdown in 0.9925 of runs, then failed `walk_forward_analysis` in the first WFA window because the selected in-sample profit factor was 0.9030, below the 1.00 early-exit minimum. Stitched OOS trades were 0.

Scientific-integrity decision: FAIL. No mechanics, filters, data windows, or parameter spaces were changed after seeing staged results. No branch reached WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
