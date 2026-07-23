# nq_spx_0dte_trend_aligned_pressure Signal Density Audit

Date: 2026-06-22

Verdict: PASS.

This pre-PnL audit computed the same completed-window logic as `spx_0dte_trend_aligned_pressure`: ex-ante SPX 0DTE calendar membership, completed NQ 30-minute and 120-minute trend states, and the configured open-to-signal move threshold. No stops, targets, fills, or PnL were evaluated.

Sessions: 2564
Years (252-session): 10.174603
Min signals/year: 51.205928
Max signals/year: 60.837754

| variant_id | min_signals_per_year | max_signals_per_year | grid_rows |
| --- | ---: | ---: | ---: |
| all_0dte_trend_continuation_1330 | 51.205928 | 51.500780 | 3 |
| all_0dte_trend_continuation_1400 | 54.154446 | 54.449298 | 3 |
| all_0dte_trend_continuation_1500 | 51.697348 | 51.992200 | 3 |
| all_0dte_trend_only_1330 | 53.761310 | 53.761310 | 1 |
| all_0dte_trend_only_1500 | 60.837754 | 60.837754 | 1 |

All declared entry-grid rows clear the 50 signals/year density screen.
