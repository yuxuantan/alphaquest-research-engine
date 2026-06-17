# ES SPX 0DTE Expiration Pressure Density Audit - 2026-06-17

No paid data was downloaded. The calendar was generated from the local Sierra ES RTH cache and public Cboe listing-date rules.

- Calendar file: `data/external/spx_0dte_calendar_sessions_20110103_20260609.csv`
- ES cache: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Test data window for configs: 2022-05-11 through 2026-06-09
- Monthly/quarterly standard OPEX Fridays are excluded from strategy signals by default.

| Variant | Bucket | Signal time | Trigger | Threshold | Signals | Signals/year |
|---|---|---:|---|---:|---:|---:|
| `full_week_down_move_fade_long_1000` | `full_week` | `10:00:00` | `fade_move/long` | 8 | 378 | 92.7 |
| `full_week_down_move_fade_long_1000` | `full_week` | `10:00:00` | `fade_move/long` | 16 | 314 | 77.0 |
| `full_week_down_move_fade_long_1000` | `full_week` | `10:00:00` | `fade_move/long` | 24 | 272 | 66.7 |
| `full_week_up_move_fade_short_1000` | `full_week` | `10:00:00` | `fade_move/short` | 8 | 466 | 114.2 |
| `full_week_up_move_fade_short_1000` | `full_week` | `10:00:00` | `fade_move/short` | 16 | 403 | 98.8 |
| `full_week_up_move_fade_short_1000` | `full_week` | `10:00:00` | `fade_move/short` | 24 | 322 | 78.9 |
| `tue_thu_two_sided_fade_1030` | `new_tue_thu` | `10:30:00` | `fade_move/two_sided` | 8 | 379 | 93.0 |
| `tue_thu_two_sided_fade_1030` | `new_tue_thu` | `10:30:00` | `fade_move/two_sided` | 16 | 343 | 84.1 |
| `tue_thu_two_sided_fade_1030` | `new_tue_thu` | `10:30:00` | `fade_move/two_sided` | 24 | 305 | 74.8 |
| `mwf_two_sided_fade_1030` | `mon_wed_fri` | `10:30:00` | `fade_move/two_sided` | 8 | 505 | 123.9 |
| `mwf_two_sided_fade_1030` | `mon_wed_fri` | `10:30:00` | `fade_move/two_sided` | 16 | 443 | 108.7 |
| `mwf_two_sided_fade_1030` | `mon_wed_fri` | `10:30:00` | `fade_move/two_sided` | 24 | 394 | 96.6 |
| `full_week_late_move_continuation_1430` | `full_week` | `14:30:00` | `continue_move/two_sided` | 64 | 590 | 144.6 |
| `full_week_late_move_continuation_1430` | `full_week` | `14:30:00` | `continue_move/two_sided` | 96 | 440 | 107.9 |
| `full_week_late_move_continuation_1430` | `full_week` | `14:30:00` | `continue_move/two_sided` | 128 | 314 | 77.0 |

Conclusion: all declared entry thresholds clear the pre-test density gate of at least 50 expected signals per year before stop/target/path effects. This is only a density screen, not performance evidence.
