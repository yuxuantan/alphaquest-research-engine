# NQ Market Plumbing Liquidity Capacity Density Audit

Verdict: REJECT BEFORE PNL.

This audit used the repo data-prep path on completed NQ RTH bars and counted only signal availability before any NQ PnL inspection. Stop and target parameters are not signal-density controls for this entry module.

The first pre-PnL density pass rejected the original ES VX strict-tail corners as too sparse. The revised VX threshold grids were selected from signal availability only before any NQ PnL was tested.

| variant | window | entry combos | min signals/year | max signals/year | weakest entry params |
|---|---|---:|---:|---:|---|
| dealer_lending_pressure_long_1130 | limited_core | 3 | 53.75 | 81.60 | `{"primary_dealer_lending_pressure_threshold": 0.2115384615384615}` |
| dealer_lending_pressure_long_1130 | full_history | 3 | 55.16 | 77.41 | `{"primary_dealer_lending_pressure_threshold": 0.2115384615384615}` |
| dealer_lending_pressure_long_1330 | limited_core | 3 | 53.75 | 81.60 | `{"primary_dealer_lending_pressure_threshold": 0.2115384615384615}` |
| dealer_lending_pressure_long_1330 | full_history | 3 | 55.16 | 77.41 | `{"primary_dealer_lending_pressure_threshold": 0.2115384615384615}` |
| dual_pressure_priority_long_1130 | limited_core | 9 | 71.24 | 121.75 | `{"cboe_vx_oi_stress_threshold": -1.6048759395402283, "primary_dealer_lending_pressure_threshold": 0.2115384615384615}` |
| dual_pressure_priority_long_1130 | full_history | 9 | 74.74 | 119.97 | `{"cboe_vx_oi_stress_threshold": -1.6048759395402283, "primary_dealer_lending_pressure_threshold": 0.2115384615384615}` |
| vx_oi_crowding_short_1330 | limited_core | 3 | 58.93 | 75.77 | `{"cboe_vx_oi_crowding_threshold": 1.2}` |
| vx_oi_crowding_short_1330 | full_history | 3 | 55.99 | 77.13 | `{"cboe_vx_oi_crowding_threshold": 1.2}` |
| vx_oi_stress_long_1330 | limited_core | 3 | 58.28 | 69.29 | `{"cboe_vx_oi_stress_threshold": -1.2}` |
| vx_oi_stress_long_1330 | full_history | 3 | 48.54 | 62.88 | `{"cboe_vx_oi_stress_threshold": -1.2}` |

Initial rejected density screen: `research_artifacts/nq_market_plumbing_liquidity_capacity_initial_density_rejected_20260622.md`
CSV detail: `research_artifacts/nq_market_plumbing_liquidity_capacity_density_audit_20260622.csv`
