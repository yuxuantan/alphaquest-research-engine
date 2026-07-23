# ES Gao Last-Half-Hour Orderflow Confirmation Density Audit - 2026-06-17

Data: local Sierra ES aggregate orderflow cache, 5-minute RTH bars from 2011-01-03 through 2026-06-09.

Screen: count sessions where the completed first window return and aggregate orderflow agree before the 15:30 ET last-half-hour entry. No PnL, stops, targets, or post-signal information used.

Declared entry grid for all variants: `entry.params.min_first_return_ticks = [0, 4]` and `entry.params.min_orderflow_imbalance = [0.005, 0.02]`. Counts are annualized and ordered as `(0 ticks, 0.005)`, `(0 ticks, 0.02)`, `(4 ticks, 0.005)`, `(4 ticks, 0.02)`.

| Variant | Annualized signal counts |
|---|---:|
| `first30_signed_flow_two_sided_1530` | 169.79, 116.59, 157.61, 109.46 |
| `first30_large20_flow_two_sided_1530` | 160.40, 146.46, 147.95, 135.77 |
| `first60_signed_flow_two_sided_1530` | 168.69, 97.15, 159.81, 93.71 |
| `first60_large20_flow_two_sided_1530` | 164.48, 149.96, 154.89, 142.32 |
| `first30_broad_large_alignment_1530` | 134.08, 96.63, 125.27, 91.18 |

Decision: approve for staged testing because every declared entry corner is comfortably above 50 trades/year before stop/target filtering. This density screen is not evidence of profitability.
