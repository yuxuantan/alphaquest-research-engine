# ES/NQ Relative-Value Reversion Rescue Attempt 1 - 2026-06-17

Decision: FAIL.

## Scope

Campaign: `es_nq_relative_value_reversion`

The rescue preserved the core strategy mechanic:

- Same entry module: `es_nq_relative_value_reversion`
- Same stop module: `percent_from_entry`
- Same target module: `fixed_r`
- Same data: local ES/NQ aligned RTH 1-minute completed return-spread cache
- Same costs, slippage, tick size, point value, sessions, prop rules, and validation gates
- Same lookback and entry time per variant

Allowed rescue changes:

- Fixed `entry.params.min_abs_es_return_bps` from `0` to `1`
- Adjusted `entry.params.min_spread_bps` parameter spaces
- Adjusted stop and target parameter spaces

## Original Outcome

All five originals failed `limited_core_grid_test`.

| Variant | Profitable combo rate | Top net | Top PF | Top trades |
|---|---:|---:|---:|---:|
| `thirty_min_divergence_fade_1000` | 0.0 | -6447.50 | 0.440685 | 127 |
| `thirty_min_divergence_fade_1030` | 0.0 | -1815.00 | 0.844072 | 118 |
| `thirty_min_divergence_fade_1130` | 0.18518518518518517 | 447.50 | 1.069677 | 93 |
| `sixty_min_divergence_fade_1030` | 0.0 | -3302.50 | 0.600906 | 128 |
| `sixty_min_divergence_fade_1400` | 0.0 | -4685.00 | 0.496372 | 132 |

## Rescue Outcome

All five rescues failed `limited_core_grid_test`.

| Variant | Profitable combo rate | Top net | Top PF | Top trades |
|---|---:|---:|---:|---:|
| `thirty_min_divergence_fade_1000` | 0.0 | -3400.00 | 0.758993 | 110 |
| `thirty_min_divergence_fade_1030` | 0.14814814814814814 | 601.25 | 1.050813 | 131 |
| `thirty_min_divergence_fade_1130` | 0.37037037037037035 | 427.50 | 1.070486 | 87 |
| `sixty_min_divergence_fade_1030` | 0.0 | -2305.00 | 0.824347 | 126 |
| `sixty_min_divergence_fade_1400` | 0.0 | -3205.00 | 0.768717 | 111 |

## Artifacts

- `backtest-campaigns/es_nq_relative_value_reversion/campaign_test_summary.json`
- `backtest-campaigns/es_nq_relative_value_reversion/campaign_results.csv`
- `backtest-campaigns/es_nq_relative_value_reversion/wfa_table.csv`
- `backtest-campaigns/es_nq_relative_value_reversion/monte_carlo_summary.json`
- `research_artifacts/es_nq_relative_value_reversion_density_audit_20260617.md`

## Final Decision

FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.
