# ES/MES Participation Crowding Density Audit - 2026-06-17

Scope: density-only audit before any PnL test for `es_mes_participation_crowding_reversion`.

Data: `data/cache/orderflow/es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny.csv`.

Feature logic:
- MES notional-equivalent volume = MES volume / 10.
- MES notional participation share = MES notional-equivalent volume / (ES volume + MES notional-equivalent volume).
- MES trade share = MES trades / (ES trades + MES trades).
- Same-clock ranks use prior observations only, with `rank_window=252` and `rank_min_periods=60`.
- Signal rows use completed bars: 10:30 entries use the `10:29` bar, 12:00 entries use `11:59`, and 14:00 entries use `13:59`.

Density result over 2019-05-06 through 2026-06-09:

| variant | grid floor/mid density | note |
|---|---:|---|
| morning_notional_down_reversal_long_1030 | rank >= 0.55 and return >= 2 ticks: 64.3/year; rank >= 0.65 and return >= 6 ticks: 51.7/year | viable |
| morning_notional_up_reversal_short_1030 | rank >= 0.55 and return >= 2 ticks: 71.0/year; rank >= 0.65 and return >= 6 ticks: 54.4/year | viable |
| midday_notional_two_sided_reversal_1200 | rank >= 0.55 and return >= 2 ticks: 134.5/year; rank >= 0.75 and return >= 6 ticks: 81.2/year | viable |
| afternoon_trade_down_reversal_long_1400 | rank >= 0.55 and return >= 2 ticks: 59.6/year; rank >= 0.65 and return >= 2 ticks: 49.8/year | lower-density upper grid points expected to be ineligible in WFA selection |
| afternoon_trade_up_reversal_short_1400 | rank >= 0.55 and return >= 2 ticks: 71.6/year; rank >= 0.65 and return >= 6 ticks: 52.7/year | viable |

Decision: density is sufficient to launch exactly five variants. This audit did not inspect profitability, drawdown, expectancy, WFA, or any outcome metric.
