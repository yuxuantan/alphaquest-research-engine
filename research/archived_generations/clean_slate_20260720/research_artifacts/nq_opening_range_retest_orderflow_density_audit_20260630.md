# NQ Opening-Range Retest Orderflow Density Audit - 2026-06-30

Pre-PnL signal-density screen only. No stop, target, trade outcome, monkey, WFA, Monte Carlo, incubation, acceptance, or holdout PnL was inspected.

Data: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` aggregated to 5-minute NQ RTH bars.
Full window: 2011-01-03 to 2026-06-12; limited-core proxy: 2011-02-22 to 2012-09-07; latest-252 sessions: 2025-06-09 to 2026-06-12.

| Variant | Entry rows | Passing rows | Min full / year | Min limited-core / year | Min latest252 signals | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `or15_signed_absorption_retest_1030` | 9 | 3 | 38.93 | 54.50 | 28 | FAIL |
| `or15_signed_aligned_retest_1030` | 9 | 4 | 42.94 | 62.28 | 29 | FAIL |
| `or30_large10_absorption_retest_1130` | 9 | 9 | 63.41 | 76.55 | 51 | PASS |
| `or30_signed_absorption_retest_1100` | 9 | 0 | 40.81 | 53.85 | 22 | FAIL |
| `or60_large20_aligned_retest_1230` | 9 | 0 | 49.36 | 66.82 | 43 | FAIL |

Decision: FAIL pre-PnL density. The declared five-variant family is rejected before NQ PnL because at least one entry row fails the full-history, limited-core proxy, or latest-252 signal-count screen. No narrowing was applied after this screen.

CSV detail: `research_artifacts/nq_opening_range_retest_orderflow_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_opening_range_retest_orderflow_density_summary_20260630.csv`
