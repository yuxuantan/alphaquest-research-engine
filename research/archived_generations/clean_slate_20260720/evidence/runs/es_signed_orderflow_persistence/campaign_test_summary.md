# ES Signed Orderflow Persistence Campaign Summary

Final decision: FAIL

All five original variants and all five required per-variant rescues failed the limited core-grid gate before monkey, WFA, Monte Carlo, or frozen validation.

| Variant | Run | Profitable combos | Top net | Top trades | Top PF | Top MAR | Top best-day concentration |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `early_5m_signed_flow_continuation_1000` | `run1` | 0.123457 | 1447.5 | 198 | 1.0905536440412886 | 0.36035583150915795 | 0.5233160621761658 |
| `early_5m_signed_flow_continuation_1000` | `rescue1` | 0.111111 | 728.75 | 198 | 1.0471453986737829 | 0.22023079872748183 | 0.3361921097770154 |
| `late_morning_15m_signed_flow_continuation_1130` | `run1` | 0.074074 | 612.5 | 65 | 1.1249362570117287 | 0.3482335765813583 | 0.4204081632653061 |
| `late_morning_15m_signed_flow_continuation_1130` | `rescue1` | 0.012346 | 90.625 | 70 | 1.0156587473002159 | 0.03489642435389931 | 2.703448275862069 |
| `midday_30m_signed_flow_continuation_1230` | `run1` | 0.037037 | 302.5 | 42 | 1.0770700636942676 | 0.16056525684274506 | 2.4214876033057853 |
| `midday_30m_signed_flow_continuation_1230` | `rescue1` | 0.000000 | -3063.75 | 179 | 0.801281011837198 | -0.5314234063094864 | 0.0 |
| `afternoon_60m_signed_flow_continuation_1400` | `run1` | 0.012346 | 555.0 | 74 | 1.076419965576592 | 0.23564400593996865 | 0.7117117117117117 |
| `afternoon_60m_signed_flow_continuation_1400` | `rescue1` | 0.000000 | -1038.75 | 149 | 0.931480870712401 | -0.3010622123298385 | 0.0 |
| `late_large20_30m_flow_continuation_1500` | `run1` | 0.000000 | -156.25 | 35 | 0.9460742018981881 | -0.11323349304597441 | 0.0 |
| `late_large20_30m_flow_continuation_1500` | `rescue1` | 0.000000 | -212.5 | 95 | 0.9713708319299428 | -0.09616780614052077 | 0.0 |

No candidate_strategy_report.md was written because no variant passed the staged methodology.
WFA and Monte Carlo tables are explicit not-reached manifests, not positive evidence.
