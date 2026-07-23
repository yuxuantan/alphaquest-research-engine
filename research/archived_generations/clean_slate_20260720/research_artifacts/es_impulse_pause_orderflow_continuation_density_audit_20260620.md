# es_impulse_pause_orderflow_continuation pre-PnL density audit

This audit counts signal opportunities only. It does not inspect PnL, returns, stops, targets, or grid-test profitability.

Full data period: 2011-01-03 to 2026-06-09.
Limited-core random 10% period: 2011-02-22 to 2012-09-06; seed=31, avoids latest 10% and the configured COVID range.

| variant | min full signals/year | min limited signals/year | pass |
|---|---:|---:|---|
| afternoon_large10_two_sided_impulse_pause_breakout_1530 | 120.60 | 67.56 | True |
| full_session_signed_two_sided_impulse_pause_breakout_1530 | 139.52 | 82.51 | True |
| late_morning_large10_two_sided_impulse_pause_breakout_1230 | 115.03 | 67.56 | True |
| midday_signed_two_sided_impulse_pause_breakout_1400 | 126.76 | 78.61 | True |
| morning_signed_two_sided_impulse_pause_breakout_1130 | 92.22 | 57.17 | True |

CSV detail: `research_artifacts/es_impulse_pause_orderflow_continuation_density_audit_20260620.csv`
JSON summary: `research_artifacts/es_impulse_pause_orderflow_continuation_density_audit_20260620.json`
