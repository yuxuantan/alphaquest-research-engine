# NQ Prior Value-Area Orderflow Rejection Density Audit - 2026-06-30

Pre-PnL signal-density screen only. No stop, target, trade outcome, monkey, WFA, Monte Carlo, incubation, acceptance, or holdout PnL was inspected.

Data: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet` aggregated to 5-minute NQ RTH bars.
Full window: 2011-01-03 to 2026-06-12; limited-core proxy: 2011-02-22 to 2012-09-07; latest-252 sessions ending 2026-06-12.

| Variant | Entry rows | Passing rows | Min full / year | Min limited-core / year | Min latest252 signals | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `afternoon_large20_two_sided_rejection` | 9 | 0 | 47.54 | 53.20 | 44 | FAIL |
| `late_morning_signed_two_sided_rejection` | 9 | 9 | 85.69 | 71.36 | 76 | PASS |
| `midday_large10_two_sided_rejection` | 9 | 9 | 72.87 | 63.58 | 69 | PASS |
| `morning_signed_vah_rejection_short` | 6 | 6 | 67.69 | 57.09 | 69 | PASS |
| `morning_signed_val_rejection_long` | 9 | 9 | 53.89 | 50.60 | 57 | PASS |

Decision: FAIL pre-PnL density. The declared five-variant family is rejected before NQ PnL because at least one entry row fails the full-history, limited-core proxy, or latest-252 signal-count screen. No narrowing was applied after this screen.

CSV detail: `research_artifacts/nq_prior_value_area_orderflow_rejection_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_prior_value_area_orderflow_rejection_density_summary_20260630.csv`
