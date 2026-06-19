# ES Opening-Range NQ Orderflow Breakout Density Audit

Date: 2026-06-19

Data: `data/cache/orderflow/es_nq_lead_lag_1m_20110103_20260609_full_rth_ny.parquet`

Method: vectorized entry-only signal-count audit over declared entry grids. It freezes OR boundaries, applies ES signed-flow breakout confirmation, applies completed NQ leadership, enforces max one signal per day, and does not inspect PnL, stop, target, WFA, monkey, or Monte Carlo results.

Decision before staged PnL: PASS

| variant | min full signals/year | min limited-core signals/year | min full signals | min limited signals | limited-core period |
|---|---:|---:|---:|---:|---|
| or15_nq15_signed_breakout_1030 | 196.72 | 182.95 | 3036 | 282 | 2011-02-22 to 2012-09-06 |
| or15_nq30_signed_breakout_1130 | 220.69 | 206.30 | 3406 | 318 | 2011-02-22 to 2012-09-06 |
| or30_nq15_signed_breakout_1030 | 142.48 | 130.40 | 2199 | 201 | 2011-02-22 to 2012-09-06 |
| or30_nq30_signed_breakout_1130 | 205.27 | 192.03 | 3168 | 296 | 2011-02-22 to 2012-09-06 |
| or60_nq60_signed_breakout_1300 | 191.86 | 173.22 | 2961 | 267 | 2011-02-22 to 2012-09-06 |

CSV: `research_artifacts/es_opening_range_nq_orderflow_breakout_density_audit_20260619.csv`
