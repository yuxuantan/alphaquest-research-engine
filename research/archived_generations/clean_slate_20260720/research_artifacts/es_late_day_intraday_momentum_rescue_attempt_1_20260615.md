# ES Late-Day Intraday Momentum Rescue Attempt 1

Date: 2026-06-15

Decision: FAIL

Rescue scope: per failed variant. The rescue changed only fixed parameter defaults and declared parameter grids inside the existing `late_day_intraday_momentum`, `percent_from_entry`, and `fixed_r` modules. It did not change timeframe, data window, source edge, stage gates, or execution assumptions.

Feature-audit note: the first zero-trade run used `feature_set: none`, which did not build `prev_rth_close` or `volume_ratio`. Those invalid outputs were removed and the original `run1` was rerun with `feature_set: pdh_pdl_sweep` before any rescue was consumed.

| Variant | Run1 profitable combos | Rescue1 profitable combos | Rescue1 top net | Rescue1 top PF | Rescue1 top trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| `first30_to_last30_two_sided` | 0.0 | 0.0 | -2941.25 | 0.07942097026604068 | 72 |
| `first30_to_last30_long_only` | 0.0 | 0.0 | -742.5 | 0.7933194154488518 | 76 |
| `first30_volume_range_conditioned` | 0.0 | 0.0 | -912.5 | 0.4296875 | 35 |
| `first60_to_last30_two_sided` | 0.0 | 0.0 | -2316.25 | 0.08267326732673268 | 57 |
| `first30_penultimate_alignment` | 0.0 | 0.0 | -240.0 | 0.1111111111111111 | 8 |

Conclusion: no candidate reached monkey, WFA, Monte Carlo, or frozen validation.
