# ES Signed Orderflow Persistence Rescue Audit

Date: 2026-06-15

Decision: FAIL

## Scope

Campaign: `es_signed_orderflow_persistence`

Edge: own-ES aggregate signed-orderflow persistence after completed-bar price
confirmation.

All five original variants failed the `limited_core_grid_test`, so each failed
variant received exactly one `rescue1` under the current per-failed-variant
rule. Rescues changed only existing fixed defaults and declared parameter
spaces. They did not change entry module, stop module, target module, signal
time, flow column, return column, direction rule, data window, costs, or stage
criteria.

## Original Results

| Variant | Profitable combo rate | Top net | Top trades | Top PF | Top MAR | Top best-day concentration |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `early_5m_signed_flow_continuation_1000` | 0.12345679012345678 | 1447.5 | 198 | 1.0905536440412886 | 0.36035583150915795 | 0.5233160621761658 |
| `late_morning_15m_signed_flow_continuation_1130` | 0.07407407407407407 | 612.5 | 65 | 1.1249362570117287 | 0.3482335765813583 | 0.4204081632653061 |
| `midday_30m_signed_flow_continuation_1230` | 0.037037037037037035 | 302.5 | 42 | 1.0770700636942676 | 0.16056525684274506 | 2.4214876033057853 |
| `afternoon_60m_signed_flow_continuation_1400` | 0.012345679012345678 | 555.0 | 74 | 1.076419965576592 | 0.23564400593996865 | 0.7117117117117117 |
| `late_large20_30m_flow_continuation_1500` | 0.0 | -156.25 | 35 | 0.9460742018981881 | -0.11323349304597441 | 0.0 |

## Rescue Results

| Variant | Profitable combo rate | Top net | Top trades | Top PF | Top MAR | Top best-day concentration |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `early_5m_signed_flow_continuation_1000` | 0.1111111111111111 | 728.75 | 198 | 1.0471453986737829 | 0.22023079872748183 | 0.3361921097770154 |
| `late_morning_15m_signed_flow_continuation_1130` | 0.012345679012345678 | 90.625 | 70 | 1.0156587473002159 | 0.03489642435389931 | 2.703448275862069 |
| `midday_30m_signed_flow_continuation_1230` | 0.0 | -3063.75 | 179 | 0.801281011837198 | -0.5314234063094864 | 0.0 |
| `afternoon_60m_signed_flow_continuation_1400` | 0.0 | -1038.75 | 149 | 0.931480870712401 | -0.3010622123298385 | 0.0 |
| `late_large20_30m_flow_continuation_1500` | 0.0 | -212.5 | 95 | 0.9713708319299428 | -0.09616780614052077 | 0.0 |

## Artifacts

- Campaign summary: `backtest-campaigns/es_signed_orderflow_persistence/campaign_test_summary.json`
- Results table: `backtest-campaigns/es_signed_orderflow_persistence/campaign_results.csv`
- WFA table: `backtest-campaigns/es_signed_orderflow_persistence/wfa_table.csv`
- Monte Carlo summary: `backtest-campaigns/es_signed_orderflow_persistence/monte_carlo_summary.json`
- Trade-log manifest: `backtest-campaigns/es_signed_orderflow_persistence/trade_logs_manifest.csv`
- Equity-curve manifest: `backtest-campaigns/es_signed_orderflow_persistence/equity_curves_manifest.csv`

## Conclusion

FAIL. No variant reached monkey, WFA, Monte Carlo, or frozen validation. The
campaign is now an active rejected edge family and must not be relaunched under
a different active name without a genuinely different economic edge.
