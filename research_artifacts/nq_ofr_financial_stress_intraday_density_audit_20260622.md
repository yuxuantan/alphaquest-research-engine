# nq_ofr_financial_stress_intraday Signal Density Audit

Date: 2026-06-22

Verdict: PASS.

This pre-PnL audit counted lagged OFR feature rows meeting each declared stress-rank threshold. No stops, targets, fills, or PnL were evaluated.

Sessions: 3813
Years (252-session): 15.130952
Min signals/year: 64.173092
Max signals/year: 93.450826

| variant_id | min_signals_per_year | max_signals_per_year | grid_rows |
| --- | ---: | ---: | ---: |
| funding_stress_short_1130 | 76.862313 | 93.450826 | 3 |
| high_credit_stress_short_1030 | 67.081039 | 80.166798 | 3 |
| rising_global_stress_short_1000 | 64.173092 | 89.683714 | 3 |
| us_stress_short_1200 | 66.750590 | 82.744296 | 3 |
| volatility_stress_short_1330 | 69.129819 | 88.361920 | 3 |

All declared entry-grid rows clear the 50 signals/year density screen.
