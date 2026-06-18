# ES daily reversal orderflow confirmation density audit - 2026-06-18

Scope: pre-PnL signal-density check only. Counts use local Sierra ES RTH completed-bar
data from `2011-01-03` through `2026-06-09`, aggregated to 5-minute strategy bars.
No PnL, stop, target, WFA, monkey, Monte Carlo, incubation, or holdout result was
inspected.

Rejected formulation before PnL:

- A stricter "absorption" version required the current early price window to continue
  in the prior daily return direction while aggregate signed flow opposed that move.
  That was too sparse: most planned corners were below 30 signals/year and many were
  below 5 signals/year.
- One-sided first-30-minute long/short variants were also too sparse once even mild
  flow thresholds were included.

Final retained mechanic:

- Use the prior completed RTH close-to-close return as the primary reversal edge.
- At a fixed intraday checkpoint, require completed rolling aggregate signed-volume
  imbalance to confirm the reversal direction.
- Enter no earlier than the next 5-minute bar open.

Declared entry grid checked for every retained variant:

- `entry.params.min_abs_reversal_return_pct`: `[0.0, 0.0005, 0.001]`
- `entry.params.min_reversal_flow_imbalance`: `[0.0, 0.005, 0.01]`

Density results:

| Variant | Signal time | Lookback | Flow window | Minimum signals/year across entry grid | Maximum signals/year across entry grid |
|---|---:|---:|---:|---:|---:|
| `first60_1d_flow_confirm_1030` | 10:30 ET | 1 session | 12 bars / 60 minutes | 55.5 | 101.8 |
| `first90_2d_flow_confirm_1100` | 11:00 ET | 2 sessions | 18 bars / 90 minutes | 60.2 | 106.2 |
| `first120_3d_flow_confirm_1130` | 11:30 ET | 3 sessions | 24 bars / 120 minutes | 59.3 | 110.4 |
| `first150_5d_flow_confirm_1200` | 12:00 ET | 5 sessions | 30 bars / 150 minutes | 61.8 | 116.2 |
| `afternoon90_1d_flow_confirm_1400` | 14:00 ET | 1 session | 18 bars / 90 minutes | 73.4 | 115.6 |

Decision: PASS density screen. The final five variants are eligible for staged
testing. This is not evidence of profitability.
