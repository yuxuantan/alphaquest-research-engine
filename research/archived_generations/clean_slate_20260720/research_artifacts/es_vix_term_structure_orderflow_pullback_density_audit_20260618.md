# es_vix_term_structure_orderflow_pullback Pre-PnL Density Audit

This vectorized pre-PnL audit uses only declared entry predicates: lagged VIX term-state rank, completed ES VWAP context, completed aggregate orderflow, configured signal window, and max one signal per session. It does not use PnL, stops, targets, fills, or future returns. Staged engine signal counts remain authoritative after execution-state suppression.

Full configured subset: `{'start_date': '2011-01-03', 'end_date': '2026-06-09', 'session_labels': ['RTH']}`
Resolved limited-core subset: `{'start_date': '2011-02-22', 'end_date': '2012-09-06', 'session_labels': ['RTH']}`
Full rows: `1,488,630`

## Summary

| campaign_id | variant_id | best_full_signals | best_full_trades_per_year | best_limited_core_signals | best_limited_core_trades_per_year | density_gate_pass |
| --- | --- | --- | --- | --- | --- | --- |
| es_vix_term_structure_orderflow_pullback | backwardation_surge_signed_vwap_reject_short_1500 | 1078 | 69.86151525904897 | 102 | 66.29092526690391 | True |
| es_vix_term_structure_orderflow_pullback | contango_large10_vwap_reclaim_long_1500 | 1266 | 82.04515613910574 | 119 | 77.3394128113879 | True |
| es_vix_term_structure_orderflow_pullback | contango_morning_signed_vwap_reclaim_long_1300 | 1103 | 71.48168026969482 | 97 | 63.04137010676156 | True |
| es_vix_term_structure_orderflow_pullback | curve_flattening_signed_vwap_reject_short_1500 | 1028 | 66.62118523775727 | 83 | 53.94261565836299 | True |
| es_vix_term_structure_orderflow_pullback | front_stress_large10_vwap_reject_short_1500 | 1104 | 71.54648687012066 | 90 | 58.49199288256227 | True |

Detail CSV: `research_artifacts/es_vix_term_structure_orderflow_pullback_density_audit_20260618.csv`
Summary CSV: `research_artifacts/es_vix_term_structure_orderflow_pullback_density_summary_20260618.csv`
