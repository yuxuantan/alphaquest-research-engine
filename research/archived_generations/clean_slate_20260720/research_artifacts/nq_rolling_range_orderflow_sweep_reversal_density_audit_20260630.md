# NQ Rolling Range Orderflow Sweep Reversal Density Audit - 2026-06-30

Pre-PnL signal-density screen only. No stop, target, trade outcome, monkey, WFA, Monte Carlo, incubation, acceptance, or holdout PnL was inspected.

Data: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` aggregated to 5-minute NQ RTH bars.
Full window: 2011-01-03 to 2026-06-12; limited-core proxy: 2011-02-22 to 2012-09-07; latest-252 sessions: 2025-06-09 to 2026-06-12.

| Variant | Entry rows | Passing rows | Min full / year | Min limited-core / year | Min latest252 signals | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `afternoon_signed_24bar_sweep_reclaim_1500` | 9 | 9 | 111.21 | 132.35 | 90 | PASS |
| `all_day_large20_36bar_sweep_reclaim_1500` | 9 | 6 | 53.89 | 51.25 | 49 | FAIL |
| `midday_signed_24bar_sweep_reclaim_1400` | 9 | 9 | 76.82 | 95.37 | 67 | PASS |
| `morning_large10_12bar_sweep_reclaim_1130` | 9 | 9 | 76.37 | 63.58 | 91 | PASS |
| `morning_signed_12bar_sweep_reclaim_1130` | 9 | 8 | 44.24 | 57.09 | 42 | FAIL |

Decision: FAIL pre-PnL density. The declared five-variant family is rejected before NQ PnL because at least one entry row fails the full-history, limited-core proxy, or latest-252 signal-count screen. No narrowing was applied after this screen.

CSV detail: `research_artifacts/nq_rolling_range_orderflow_sweep_reversal_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_rolling_range_orderflow_sweep_reversal_density_summary_20260630.csv`
