# ES SPX 0DTE Trend-Aligned Pressure Density Audit - 2026-06-17

Decision: eligible for staged testing on signal density.

Scope:

- Campaign: `es_spx_0dte_trend_aligned_pressure`
- Data: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Calendar: `data/external/spx_0dte_calendar_sessions_20110103_20260609.csv`
- Period: `2016-02-24` through `2026-06-09`
- Eligible sessions: all locally known SPX 0DTE sessions from the M/W/F Weeklys
  era onward, excluding standard monthly OPEX Fridays.
- Approximate elapsed years: `10.289`

Mechanic screened:

- Use only completed RTH 1-minute ES bars.
- At the signal timestamp, compare the latest completed 30-minute window with
  the prior 30-minute window, and the latest completed 120-minute window with
  the prior 120-minute window.
- Long trend: both windows show higher high and higher low.
- Short trend: both windows show lower high and lower low.
- Mixed/insufficient state: no signal.
- Continuation variants additionally require the open-to-signal move to agree
  with the trend direction.

Density results:

| Variant | Signal time | Trigger | Long trend days | Short trend days | No-trade days | Strictest tested threshold | Strictest signals | Strictest signals/year |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `all_0dte_trend_only_1330` | 13:30 | calendar only | 322 | 246 | 1219 | 0 ticks | 568 | 55.2 |
| `all_0dte_trend_only_1500` | 15:00 | calendar only | 398 | 235 | 1154 | 0 ticks | 633 | 61.5 |
| `all_0dte_trend_continuation_1330` | 13:30 | continue move | 322 | 246 | 1219 | 8 ticks | 542 | 52.7 |
| `all_0dte_trend_continuation_1400` | 14:00 | continue move | 370 | 249 | 1168 | 8 ticks | 549 | 53.4 |
| `all_0dte_trend_continuation_1500` | 15:00 | continue move | 398 | 235 | 1154 | 8 ticks | 526 | 51.1 |

Conclusion:

All five reformulated pre-test variants clear the 50 trades/year density
requirement before performance testing. The reformulation from post-2022
full-week only to all locally known 0DTE sessions was made before PnL testing
because the longer era is required to support the benchmark 4-year IS / 1-year
OOS WFA structure. This audit does not evaluate profitability and did not use
trade outcomes.
