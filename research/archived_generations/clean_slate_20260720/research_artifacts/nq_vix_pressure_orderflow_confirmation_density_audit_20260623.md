# NQ VIX Pressure Orderflow Confirmation Density Audit

Pre-PnL signal-count audit only. No trade outcomes or PnL were inspected.

Fixed VIX gate: `vix_change_1d_rank_252 >= 0.25`, using the lagged Cboe VIX feature available strictly before the NQ session date.

| variant | min signals/year | max signals/year | min latest-year signals | decision |
|---|---:|---:|---:|---|
| `vix_pressure_1030_signed_weakness_short` | 58.55 | 67.43 | 68 | PASS |
| `vix_pressure_1030_large20_weakness_short` | 51.69 | 52.34 | 53 | PASS |
| `vix_pressure_1130_vwap_signed_pressure_short` | 51.49 | 61.40 | 60 | PASS |
| `vix_pressure_1200_signed_weakness_short` | 53.37 | 65.36 | 56 | PASS |
| `vix_pressure_1200_large20_weakness_short` | 50.59 | 51.49 | 48 | PASS |

All five selected variants pass the pre-PnL density floor at every declared entry-grid corner.
