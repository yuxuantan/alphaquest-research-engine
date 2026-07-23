# NQ Manufacturing Orders State Density Audit

Pre-PnL signal-density screen only. No trade PnL, stops, targets, or equity curves were inspected.

- Detail CSV: `research_artifacts/nq_manufacturing_orders_state_density_audit_20260701.csv`
- Summary CSV: `research_artifacts/nq_manufacturing_orders_state_density_summary_20260701.csv`
- Feature CSV: `data/external/nq_manufacturing_orders_state_features_20110103_20260612.csv`
- Density pass rows: 44/45
- Passing variants: 4/5
- Minimum required signals per year: 50.0

| Variant | Rows Passed | Min Signals/Yr | Max Signals/Yr | Verdict |
|---|---:|---:|---:|---|
| core_capgoods_3m_strength_long_1130 | 9/9 | 85.434430 | 225.772665 | PASS |
| durables_1m_weakness_short_1200 | 9/9 | 69.571429 | 123.422390 | PASS |
| ex_transport_3m_strength_long_1330 | 9/9 | 69.824348 | 125.429258 | PASS |
| total_orders_3m_strength_long_1000 | 9/9 | 79.864027 | 153.926786 | PASS |
| total_orders_3m_weakness_short_1030 | 8/9 | 33.046429 | 117.950035 | FAIL |
