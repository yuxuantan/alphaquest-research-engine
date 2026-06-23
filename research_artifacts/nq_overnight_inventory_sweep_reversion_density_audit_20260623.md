# NQ Overnight Inventory Sweep Reversion Density Audit

Generated: 2026-06-23

This pre-PnL audit uses the generated NQ Databento explicit-roll ETH/RTH cache through 2026-05-29. It mirrors the staged runner order: assign sessions and roll-boundary policy, aggregate to 5-minute bars, then compute overnight levels and VWAP. No PnL, stop/target outcome, WFA, monkey, Monte Carlo, or holdout result was inspected.

Initial midpoint-reclaim, open-outside-range, and VWAP-filtered candidates were rejected for insufficient signal density before PnL. The final five variants below use the frozen entry grid `min_overnight_range_points=[20,40,60]` and `reclaim_buffer_ticks=[0,1,2]`.

Density gate: every selected variant must have at least 40 signals/year and at least 40 latest-252-session signals at every entry-grid corner.

## Minimum Density By Selected Variant

| variant_id                              | min_signals_per_year | min_signal_days_per_year | min_latest_252_signals | min_latest_252_signal_days |
| --------------------------------------- | -------------------- | ------------------------ | ---------------------- | -------------------------- |
| extended_high_extreme_reject_short_1230 | 54.999               | 54.999                   | 117                    | 117                        |
| extended_low_extreme_reclaim_long_1230  | 50.973               | 50.973                   | 107                    | 107                        |
| morning_high_extreme_reject_short_1130  | 51.167               | 51.167                   | 106                    | 106                        |
| morning_low_extreme_reclaim_long_1130   | 46.103               | 46.103                   | 96                     | 96                         |
| morning_two_sided_extreme_reclaim_1130  | 85.972               | 85.972                   | 181                    | 181                        |

Decision: PASS_AFTER_REFORMULATION. Proceed to preflight and staged testing with the final five variants and parameter space frozen.
