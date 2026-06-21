# es_pivot_filtered_mes_participation_crowding_reversion density audit

Purpose: pre-PnL density gate after reformulating sparse fixed-time variants into fixed signal-window variants.

Data source: `data/cache/orderflow/es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny.csv`.

No paid data was downloaded or requested.

Initial fixed-time formulation was rejected before staged PnL because the best declared-grid density was below 50 trades/year for every variant.

Active formulation uses `signal_mode: first_signal_in_window` and `carry_pivots_across_sessions: true`; both were fixed before PnL testing.

Windows mirror current runner defaults:
- full_core: 2019-05-06 through 2026-06-09
- limited_core_random10: 2021-07-13 through 2022-03-28
- wfa_first90: 2019-05-06 through 2025-09-22
- latest_1y_reference: 2025-06-10 through 2026-06-09

Density decision: PASS

| variant | fixed full/y | fixed limited/y | fixed wfa90/y | fixed latest1y/y | all-pass entry combos | decision |
|---|---:|---:|---:|---:|---:|---|
| afternoon_trade_two_sided_reversal_window_1500 | 95.5399 | 114.2288 | 93.3486 | 99.0678 | 9 | PASS |
| late_morning_trade_two_sided_reversal_window_1200 | 89.1988 | 129.7413 | 86.4571 | 95.0651 | 9 | PASS |
| midday_notional_two_sided_reversal_window_1330 | 119.6363 | 142.4334 | 118.252 | 126.0863 | 9 | PASS |
| morning_notional_down_reversal_long_window_1100 | 51.1519 | 53.5888 | 51.0598 | 57.039 | 6 | PASS |
| morning_notional_two_sided_reversal_window_1130 | 110.0541 | 132.5618 | 108.8545 | 120.0822 | 9 | PASS |

This artifact counts first qualifying entry signal per session only. It does not inspect PnL, grid profitability, WFA selections, or post-entry trade results.
