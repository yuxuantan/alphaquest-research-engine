# ES Prior LVN Orderflow Rejection Density Audit

Date: 2026-06-20

Data: local Sierra ES trade-orderflow cache, 5-minute RTH bars. No paid data downloaded.
Base subset: `{'start_date': '2011-01-03', 'end_date': '2026-06-09', 'session_labels': ['RTH']}`
Limited-core subset: `{'start_date': '2011-02-22', 'end_date': '2012-09-06', 'session_labels': ['RTH']}`

Strict corner: `lvn_quantile=0.10`, `min_orderflow_imbalance=0.04`, `min_sweep_ticks=2`, `max_trades_per_day=1`.

| variant | full strict signals/yr | limited strict signals/yr | pass |
|---|---:|---:|---:|
| `morning_signed_two_sided_lvn_rejection` | 136.94 | 130.63 | True |
| `morning_downside_signed_lvn_reclaim_long` | 116.33 | 111.78 | True |
| `late_morning_large10_two_sided_lvn_rejection` | 113.74 | 110.48 | True |
| `midday_signed_two_sided_lvn_rejection` | 91.44 | 83.19 | True |
| `afternoon_large20_two_sided_lvn_rejection` | 95.40 | 92.94 | True |

Decision: PASS density gate for campaign authoring.

CSV: `research_artifacts/es_prior_lvn_orderflow_rejection_density_audit_20260620.csv`
