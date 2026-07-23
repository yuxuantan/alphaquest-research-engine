# NQ Intraday Periodicity Persistence Density Audit

Review date: 2026-06-30

Scope: pre-PnL density and signal/entry-bar availability audit for all 45 declared entry rows.

Feature CSV: `data/external/nq_intraday_periodicity_features_20110103_20260612.csv`
Raw bars: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`

Gate: full-history density >= 50 signals/year, latest-1260-session density >= 50 signals/year, latest-252-session signals >= 20, and zero missing signal/entry bars for each slot.

| variant_id | rows | pass_rows | min_full_signals_per_year | min_latest_1260_signals_per_year | min_latest_252_signals | pass_variant_density_gate |
| --- | --- | --- | --- | --- | --- | --- |
| afternoon_1330_slot_persistence | 9 | 9 | 128.831752 | 140.252839 | 110 | True |
| late_afternoon_1430_slot_persistence | 9 | 9 | 157.525802 | 179.760681 | 157 | True |
| late_morning_1130_slot_persistence | 9 | 9 | 152.020172 | 166.130476 | 126 | True |
| morning_1000_slot_persistence | 9 | 9 | 174.884731 | 189.045024 | 189 | True |
| morning_1030_slot_persistence | 9 | 9 | 169.702962 | 196.551514 | 212 | True |

Conclusion: PASS.
All declared entry rows passed density and signal/entry-bar availability gates. Staged PnL may proceed under the frozen configs.
