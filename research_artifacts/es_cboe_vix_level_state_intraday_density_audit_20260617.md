# ES Cboe VIX Level State Density Audit - 2026-06-17

No paid data was downloaded. The feature file was built from the existing local `data/external/cboe_vix_history.csv` cache and local Sierra ES RTH sessions.

Full 2011-01-03 to 2026-06-09 eligible-session densities before bar/fill checks:

| Family | Threshold | Eligible sessions/year |
| --- | ---: | ---: |
| VIX close upper rank | 0.55 / 0.60 / 0.65 | 102.5 / 89.8 / 79.5 |
| VIX close lower rank | 0.45 / 0.40 / 0.35 | 123.8 / 115.3 / 104.8 |
| VIX 1-day change upper rank | 0.55 / 0.60 / 0.65 | 113.0 / 100.3 / 87.9 |
| VIX 1-day change lower rank | 0.45 / 0.40 / 0.35 | 109.9 / 97.1 / 84.6 |
| VIX 5-day mean upper rank | 0.55 / 0.60 / 0.65 | 101.3 / 87.9 / 76.9 |

First-18-month limited-window densities also clear the 50/year screen for the declared thresholds.
