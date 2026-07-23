# nq_gao_last_half_hour_orderflow_confirmation campaign test summary

Decision: FAIL

All five predeclared NQ Gao last-half-hour orderflow variants failed `limited_core_grid_test`. No downstream monkey, WFA, Monte Carlo, simulated incubation, or acceptance stages were reached.

| Variant | Stage | Profitable | Benchmark pass | Top net | Top PF | Top trades | Top failure |
|---|---:|---:|---:|---:|---:|---:|---|
| first30_broad_large_alignment_1530 | limited_core_grid_test | 26/81 (0.3210) | 0 | 652.5 | 4.434210526315789 | 10 | min_trades_per_year;preferred_min_total_trades |
| first30_large20_flow_two_sided_1530 | limited_core_grid_test | 33/81 (0.4074) | 2 | 452.5 | 1.1377473363774733 | 92 |  |
| first30_signed_flow_long_only_1530 | limited_core_grid_test | 31/81 (0.3827) | 0 | 555.0 | 3.466666666666667 | 12 | min_trades_per_year;preferred_min_total_trades |
| first30_signed_flow_two_sided_1530 | limited_core_grid_test | 15/81 (0.1852) | 0 | 310.0 | 1.5961538461538463 | 16 | min_trades_per_year;preferred_min_total_trades |
| first60_signed_flow_two_sided_1530 | limited_core_grid_test | 15/81 (0.1852) | 0 | 355.0 | 2.775 | 8 | min_trades_per_year;preferred_min_total_trades |

Notes:
- Best profitable-combo rate: `first30_large20_flow_two_sided_1530` at 33/81 = 0.4074, below the 0.70 core-grid gate.
- Highest top-row net profit: `first30_broad_large_alignment_1530`, but the top row had only 10 trades and failed trade-density gates.
- No rescue was authorized or applied.
