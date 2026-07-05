# nq_vix_term_structure_orderflow_pullback pre-PnL density audit

Verdict: PASS.

This audit uses only declared entry predicates: lagged VIX term-state rank, completed NQ VWAP context, completed aggregate orderflow, configured signal window, and max one signal per session. It does not inspect PnL, stops, targets, fills, WFA, Monte Carlo, prop-rule outcomes, or future returns.

- Detail CSV: `research_artifacts/nq_vix_term_structure_orderflow_pullback_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_vix_term_structure_orderflow_pullback_density_summary_20260701.csv`
- NQ bar cache: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`
- Full configured subset: `{'start_date': '2011-01-03', 'end_date': '2026-06-12', 'session_labels': ['RTH']}`
- Resolved limited-core subset: `{'start_date': '2011-02-22', 'end_date': '2012-09-07', 'session_labels': ['RTH']}`
- Full rows: `1,487,070`
- Density rule: at least one predeclared entry-grid row per variant must reach >= 50 signals/year on both full data and limited core
- Density rows passing: 35/45
- Variants passing the density gate: 5/5

| variant | pass rows | best full signals | best full/year | best limited signals | best limited/year | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| backwardation_surge_signed_vwap_reject_short_1500 | 9 | 1130 | 74.68 | 108 | 73.36 | PASS |
| contango_large10_vwap_reclaim_long_1500 | 9 | 1119 | 73.95 | 117 | 79.47 | PASS |
| contango_morning_signed_vwap_reclaim_long_1300 | 9 | 1121 | 74.09 | 106 | 72.00 | PASS |
| curve_flattening_signed_vwap_reject_short_1500 | 5 | 1073 | 70.91 | 83 | 56.38 | PASS |
| front_stress_large10_vwap_reject_short_1500 | 3 | 995 | 65.76 | 83 | 56.38 | PASS |

Conclusion: density is sufficient to proceed to preflight and staged validation. This is not evidence of profitability.
