# ES Intraday Invariance Dislocation Reversion Density Audit

Generated: 2026-06-20

This is a pre-PnL density audit. It uses only completed local Sierra ES 1-minute bars and the declared entry grid. No net profit, exits, stops, targets, or optimization results are used.

Pre-PnL reformulation note: the first draft included two single-sided morning variants. They failed the limited-core density threshold before any PnL testing, so they were removed and replaced with density-qualified two-sided session variants.

Rules checked:
- Full configured subset: 2011-01-03 through 2026-06-09, RTH only.
- Limited-core benchmark subset: 2011-02-22 through 2012-09-06, RTH only.
- Signal counts are capped by variant max_trades_per_day to approximate executable opportunity count.
- Density pass requires at least one declared entry-grid point per variant with >=50 capped signals/year in both windows.

| variant | best full signals/year | best limited-core signals/year | full grid point | limited grid point | pass |
|---|---:|---:|---|---|---|
| morning_15m_two_sided_dislocation_fade_1130 | 192.58 | 64.68 | rank=0.9, return_ticks=4 | rank=0.9, return_ticks=4 | true |
| midday_15m_two_sided_dislocation_fade_1400 | 220.31 | 84.90 | rank=0.9, return_ticks=4 | rank=0.9, return_ticks=4 | true |
| lunch_15m_two_sided_dislocation_fade_1330 | 156.93 | 55.25 | rank=0.9, return_ticks=4 | rank=0.9, return_ticks=4 | true |
| afternoon_15m_two_sided_dislocation_fade_1530 | 193.57 | 72.77 | rank=0.9, return_ticks=4 | rank=0.9, return_ticks=4 | true |
| full_session_15m_two_sided_dislocation_fade_1530 | 282.57 | 109.16 | rank=0.9, return_ticks=4 | rank=0.9, return_ticks=4 | true |

Conclusion: PASS. Proceed to preflight and staged testing without changing mechanics or parameter space after this point.

Detail CSV: research_artifacts/es_intraday_invariance_dislocation_reversion_density_audit_20260620.csv
