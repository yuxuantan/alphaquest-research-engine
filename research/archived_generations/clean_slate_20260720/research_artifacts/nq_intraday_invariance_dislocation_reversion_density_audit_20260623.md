# NQ Intraday Invariance Dislocation Reversion Density Audit

Generated: 2026-06-23

This audit uses completed NQ 1-minute RTH bars from 2011-01-03 through 2026-06-12. The same-clock invariance rank is computed from prior observations only; the current score is not inserted until after the signal decision. No PnL, stop, target, or trade outcome was inspected.

Frozen entry grid before PnL:

- `entry.params.invariance_rank_threshold`: 0.85, 0.90, 0.95
- `entry.params.min_return_ticks`: 8, 12, 16
- `entry.params.max_aligned_flow_imbalance`: fixed at 0.05

Density gate: every variant must have at least 50 signals/year and at least 50 latest-252-session signals at every entry-grid corner.

## Minimum Density By Variant

| variant_id                                       | min_signals_per_year | min_signal_days_per_year | min_latest_252_signals | min_latest_252_signal_days |
| ------------------------------------------------ | -------------------- | ------------------------ | ---------------------- | -------------------------- |
| afternoon_15m_two_sided_dislocation_fade_1530    | 143.665              | 79.929                   | 221                    | 119                        |
| full_session_15m_two_sided_dislocation_fade_1530 | 220.225              | 119.440                  | 299                    | 157                        |
| lunch_15m_two_sided_dislocation_fade_1330        | 113.481              | 64.319                   | 172                    | 96                         |
| midday_30m_two_sided_dislocation_fade_1430       | 192.503              | 104.348                  | 239                    | 127                        |
| opening_15m_two_sided_dislocation_fade_1130      | 139.713              | 78.763                   | 209                    | 114                        |

Decision: PASS. All five variants proceed to preflight and staged testing with mechanics and parameter space frozen.
