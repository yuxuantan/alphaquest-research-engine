# ES Opening VAP Large200 Reaction Density Audit

Data: `data/cache/orderflow/es_sierra_footprint_opening_vap_large200_1m_20120103_20260609_rth_ny.parquet`

Pre-PnL density by variant across min_probe_ticks=[0,1] and min_orderflow_imbalance=[0.0,0.01,0.03]. Large200 threshold fixed at 200 lots; footprint volume threshold fixed at 20.

| variant_id                     | min_sessions_per_year | median_sessions_per_year | max_sessions_per_year | min_signal_sessions | max_signal_sessions |
| ------------------------------ | --------------------- | ------------------------ | --------------------- | ------------------- | ------------------- |
| ovap30_large_lvn_trap_1500     | 5.77                  | 6.84                     | 7.97                  | 89                  | 123                 |
| ovap30_large_poc_reclaim_1500  | 5.38                  | 6.64                     | 8.17                  | 83                  | 126                 |
| ovap30_large_value_accept_1500 | 164.67                | 165.35                   | 165.65                | 2541                | 2556                |
| ovap30_large_value_trap_1500   | 5.96                  | 7.06                     | 8.36                  | 92                  | 129                 |
| ovap60_large_lvn_trap_1500     | 3.95                  | 4.76                     | 5.64                  | 61                  | 87                  |
| ovap60_large_poc_reclaim_1500  | 4.73                  | 5.70                     | 6.74                  | 73                  | 104                 |
| ovap60_large_value_accept_1500 | 152.30                | 153.07                   | 153.59                | 2350                | 2370                |
| ovap60_large_value_trap_1500   | 4.47                  | 5.31                     | 6.29                  | 69                  | 97                  |

Detail CSV: `research_artifacts/es_opening_vap_large200_reaction_density_audit_20260624.csv`
