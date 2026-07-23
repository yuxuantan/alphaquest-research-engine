# ES Opening-Range NQ Orderflow Breakout Rescue1 Density Audit

Date: 2026-06-19

Data: `data/cache/orderflow/es_nq_lead_lag_1m_20110103_20260609_full_rth_ny.parquet`

Method: vectorized entry-equivalent signal-count audit over rescue1 declared entry grids. It freezes opening-range boundaries, applies long-only ES signed-flow breakout confirmation, applies completed NQ leadership, enforces max one signal per day, and does not inspect PnL, stop, target, WFA, monkey, Monte Carlo, or holdout results.

Decision before rescue staged PnL: PASS

| variant | entry combos | min full signals/year | min limited-core signals/year | min full signals | min limited signals | limited-core period | strict corner |
|---|---:|---:|---:|---:|---:|---|---|
| or15_nq15_signed_breakout_1030 | 9 | 108.36 | 100.74 | 1672 | 155 | 2011-02-22 to 2012-09-06 | imb=0.04, lead=2.0, long=True, short=False |
| or15_nq30_signed_breakout_1130 | 9 | 130.46 | 122.83 | 2013 | 189 | 2011-02-22 to 2012-09-06 | imb=0.04, lead=2.0, long=True, short=False |
| or30_nq15_signed_breakout_1030 | 9 | 73.17 | 66.94 | 1129 | 103 | 2011-02-22 to 2012-09-06 | imb=0.04, lead=2.0, long=True, short=False |
| or30_nq30_signed_breakout_1130 | 9 | 117.36 | 109.83 | 1811 | 169 | 2011-02-22 to 2012-09-06 | imb=0.04, lead=2.0, long=True, short=False |
| or60_nq60_signed_breakout_1300 | 9 | 109.07 | 90.34 | 1683 | 139 | 2011-02-22 to 2012-09-06 | imb=0.04, lead=2.0, long=True, short=False |

CSV: `research_artifacts/es_opening_range_nq_orderflow_breakout_rescue1_density_audit_20260619.csv`
