# NQ Market Plumbing Liquidity Capacity Density Audit

Verdict: REJECT BEFORE PNL.

This audit used the repo data-prep path on completed NQ RTH bars and counted only signal availability before any NQ PnL inspection. Stop and target parameters are not signal-density controls for this entry module.

| variant | window | entry combos | min signals/year | max signals/year | weakest entry params |
|---|---|---:|---:|---:|---|
| dealer_lending_pressure_long_1130 | limited_core | 3 | 53.75 | 81.60 | `{"primary_dealer_lending_pressure_threshold": 0.2115384615384615}` |
| dealer_lending_pressure_long_1130 | full_history | 3 | 55.16 | 77.41 | `{"primary_dealer_lending_pressure_threshold": 0.2115384615384615}` |
| dealer_lending_pressure_long_1330 | limited_core | 3 | 53.75 | 81.60 | `{"primary_dealer_lending_pressure_threshold": 0.2115384615384615}` |
| dealer_lending_pressure_long_1330 | full_history | 3 | 55.16 | 77.41 | `{"primary_dealer_lending_pressure_threshold": 0.2115384615384615}` |
| dual_pressure_priority_long_1130 | limited_core | 9 | 71.24 | 121.75 | `{"cboe_vx_oi_stress_threshold": -1.6048759395402283, "primary_dealer_lending_pressure_threshold": 0.2115384615384615}` |
| dual_pressure_priority_long_1130 | full_history | 9 | 74.74 | 119.97 | `{"cboe_vx_oi_stress_threshold": -1.6048759395402283, "primary_dealer_lending_pressure_threshold": 0.2115384615384615}` |
| vx_oi_crowding_short_1330 | limited_core | 3 | 27.85 | 62.82 | `{"cboe_vx_oi_crowding_threshold": 1.8562670360751274}` |
| vx_oi_crowding_short_1330 | full_history | 3 | 21.24 | 61.78 | `{"cboe_vx_oi_crowding_threshold": 1.8562670360751274}` |
| vx_oi_stress_long_1330 | limited_core | 3 | 29.79 | 70.59 | `{"cboe_vx_oi_stress_threshold": -1.6048759395402283}` |
| vx_oi_stress_long_1330 | full_history | 3 | 25.74 | 64.08 | `{"cboe_vx_oi_stress_threshold": -1.6048759395402283}` |

CSV detail: `research_artifacts/nq_market_plumbing_liquidity_capacity_density_audit_20260622.csv`
