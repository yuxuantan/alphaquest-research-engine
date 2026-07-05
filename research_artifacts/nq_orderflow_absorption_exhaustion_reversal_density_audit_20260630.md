# NQ Orderflow Absorption Exhaustion Reversal Density Audit

Verdict: REJECT BEFORE PNL.

This pre-PnL audit built the configured rolling NQ trade-orderflow features, then used the actual `orderflow_regime` entry module to count entry-condition signals only. No stop, target, PnL, monkey, WFA, Monte Carlo, prop simulation, or holdout result was inspected.

Full-history subset: `{"end_date": "2026-06-12", "session_labels": ["RTH"], "start_date": "2011-01-03"}`.
Limited-core reference subset: `{"end_date": "2012-09-07", "session_labels": ["RTH"], "start_date": "2011-02-22"}`.

| variant | window | entry combos | min signals/year | max signals/year | weakest entry params | pass |
|---|---|---:|---:|---:|---|---|
| afternoon_60m_absorption_fade_1400 | full_history | 9 | 0.99 | 5.68 | `{"max_abs_return_ticks": 1, "pressure_rank_threshold": 0.9}` | no |
| afternoon_60m_absorption_fade_1400 | limited_core | 9 | 4.08 | 10.19 | `{"max_abs_return_ticks": 1, "pressure_rank_threshold": 0.9}` | no |
| early_5m_absorption_fade_1000 | full_history | 9 | 1.52 | 7.40 | `{"max_abs_return_ticks": 1, "pressure_rank_threshold": 0.9}` | no |
| early_5m_absorption_fade_1000 | limited_core | 9 | 4.08 | 18.34 | `{"max_abs_return_ticks": 1, "pressure_rank_threshold": 0.9}` | no |
| late_30m_absorption_fade_1500 | full_history | 9 | 1.12 | 6.87 | `{"max_abs_return_ticks": 1, "pressure_rank_threshold": 0.9}` | no |
| late_30m_absorption_fade_1500 | limited_core | 9 | 3.40 | 13.58 | `{"max_abs_return_ticks": 1, "pressure_rank_threshold": 0.9}` | no |
| late_morning_15m_absorption_fade_1130 | full_history | 9 | 1.06 | 6.81 | `{"max_abs_return_ticks": 1, "pressure_rank_threshold": 0.9}` | no |
| late_morning_15m_absorption_fade_1130 | limited_core | 9 | 2.72 | 13.58 | `{"max_abs_return_ticks": 1, "pressure_rank_threshold": 0.9}` | no |
| midday_30m_absorption_fade_1230 | full_history | 9 | 0.86 | 6.08 | `{"max_abs_return_ticks": 1, "pressure_rank_threshold": 0.9}` | no |
| midday_30m_absorption_fade_1230 | limited_core | 9 | 0.68 | 10.19 | `{"max_abs_return_ticks": 1, "pressure_rank_threshold": 0.9}` | no |

CSV detail: `research_artifacts/nq_orderflow_absorption_exhaustion_reversal_density_audit_20260630.csv`
