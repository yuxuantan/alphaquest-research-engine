# NQ Market Plumbing Liquidity Capacity Density Audit

Verdict: APPROVED FOR TESTING.

This audit used the repo data-prep path on completed NQ RTH bars and counted only signal availability before any NQ PnL inspection. Stop and target parameters are not signal-density controls for this entry module.

Pre-PnL reformulations from signal density only:
- Original ES VX strict-tail grids were rejected as too sparse before PnL.
- VX-crowding grid was widened to `[0.85, 1.0, 1.2]` before PnL.
- VX-stress grid was widened to `[-1.1, -1.0, -0.9]` before PnL after `[-1.2, -1.1, -1.0]` still failed full-history density.

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
| vx_oi_stress_long_1330 | limited_core | 3 | 62.82 | 80.95 | `{"cboe_vx_oi_stress_threshold": -1.1}` |
| vx_oi_stress_long_1330 | full_history | 3 | 55.53 | 70.05 | `{"cboe_vx_oi_stress_threshold": -1.1}` |

Initial rejected density screen: `research_artifacts/nq_market_plumbing_liquidity_capacity_initial_density_rejected_20260622.md`
Reformulation-1 rejected density screen: `research_artifacts/nq_market_plumbing_liquidity_capacity_density_reform1_rejected_20260622.md`
CSV detail: `research_artifacts/nq_market_plumbing_liquidity_capacity_density_audit_20260622.csv`
