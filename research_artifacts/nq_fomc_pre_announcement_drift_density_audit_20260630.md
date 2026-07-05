# NQ FOMC Pre-Announcement Drift Density Audit

Created: 2026-06-30

This audit uses only the NQ RTH bar cache and the official scheduled FOMC event calendar before any NQ PnL inspection. Event-driven FOMC strategies are sparse by design, so the density gate is the campaign benchmark of at least 5 signals/year, not the 50 signals/year used for dense daily-state campaigns.

Data window: 2011-01-03 through 2026-06-12. Event calendar: `data/external/fomc_scheduled_decision_dates_20110101_20260609.csv`, 121 scheduled decision dates present in the NQ RTH cache plus 119 prior-calendar-day sessions.

| Variant | Threshold | Signals | Signals/year | Pass |
| --- | --- | ---: | ---: | --- |
| `decision_day_open_long_1000` | all | 121 | 7.837427 | yes |
| `decision_day_late_morning_long_1130` | all | 121 | 7.837427 | yes |
| `decision_day_momentum_confirmed_long_1130` | min_session_return_bps=-50 | 109 | 7.059161 | yes |
| `decision_day_momentum_confirmed_long_1130` | min_session_return_bps=-40 | 104 | 6.735300 | yes |
| `decision_day_momentum_confirmed_long_1130` | min_session_return_bps=-30 | 95 | 6.153349 | yes |
| `decision_day_low_range_long_1130` | max_session_range_bps=80 | 85 | 5.505151 | yes |
| `decision_day_low_range_long_1130` | max_session_range_bps=100 | 100 | 6.477212 | yes |
| `decision_day_low_range_long_1130` | max_session_range_bps=120 | 108 | 6.995389 | yes |
| `prior_day_late_long_1500` | all | 119 | 7.707883 | yes |

Pre-PnL decision: approve all five variants for staged testing. The NQ-specific momentum thresholds `[-50, -40, -30]` bps and low-range thresholds `[80, 100, 120]` bps were selected from signal density only to avoid invalid sparse grids; no PnL, net profit, drawdown, or trade outcome was inspected.
