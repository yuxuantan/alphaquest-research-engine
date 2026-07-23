# NQ ChartFanatics London Trident FVG Continuation Density Audit

Audit date: 2026-06-30

Verdict: FAIL

Source: ChartFanatics Unique High RR, TG Capital, https://www.chartfanatics.com/strategies/unique-high-rr

No PnL was inspected. This audit counts only predeclared completed-bar signals from local NQ Databento ETH/RTH OHLCV.

Density rule: every declared entry-grid row must exceed 50 signals/year on full history and the limited-core proxy window, and must have at least 50 raw signals in the latest 252 sessions.

Detail CSV: `research_artifacts/nq_chartfanatics_london_trident_fvg_continuation_density_audit_20260630.csv`
Summary CSV: `research_artifacts/nq_chartfanatics_london_trident_fvg_continuation_density_summary_20260630.csv`

## Machine Summary

```json
{
  "all_rows_density_pass": false,
  "audit_date": "2026-06-30",
  "campaign_id": "nq_chartfanatics_london_trident_fvg_continuation",
  "declared_entry_rows": 45,
  "density_fail_rows": 45,
  "density_pass_rows": 0,
  "full_end_date": "2026-05-29",
  "full_sessions": 4779,
  "full_start_date": "2011-01-03",
  "latest_252_end_date": "2026-05-29",
  "latest_252_start_date": "2025-08-10",
  "limited_end_date": "2012-09-07",
  "limited_start_date": "2011-02-22",
  "min_full_signals_per_year": 0.6493333333333333,
  "min_latest_252_signals": 0,
  "min_limited_signals_per_year": 0.0,
  "prepared_30m_bars": 182051,
  "timeframe": "30m",
  "variant_summary": [
    {
      "entry_rows": 9,
      "max_full_signals_per_year": 1.7532,
      "max_latest_252_signals": 1,
      "max_limited_signals_per_year": 2.5950266429840143,
      "median_full_signals_per_year": 1.3636000000000001,
      "median_latest_252_signals": 1.0,
      "median_limited_signals_per_year": 2.5950266429840143,
      "min_full_signals_per_year": 1.0389333333333335,
      "min_latest_252_signals": 1,
      "min_limited_signals_per_year": 1.9462699822380105,
      "pass_rows": 0,
      "variant_id": "london_long_trident_ema13_0630",
      "verdict": "FAIL"
    },
    {
      "entry_rows": 9,
      "max_full_signals_per_year": 1.7532,
      "max_latest_252_signals": 1,
      "max_limited_signals_per_year": 2.5950266429840143,
      "median_full_signals_per_year": 1.3636000000000001,
      "median_latest_252_signals": 1.0,
      "median_limited_signals_per_year": 2.5950266429840143,
      "min_full_signals_per_year": 1.0389333333333335,
      "min_latest_252_signals": 1,
      "min_limited_signals_per_year": 1.9462699822380105,
      "pass_rows": 0,
      "variant_id": "london_long_trident_ema15_0630",
      "verdict": "FAIL"
    },
    {
      "entry_rows": 9,
      "max_full_signals_per_year": 0.9740000000000001,
      "max_latest_252_signals": 0,
      "max_limited_signals_per_year": 0.6487566607460036,
      "median_full_signals_per_year": 0.7792,
      "median_latest_252_signals": 0.0,
      "median_limited_signals_per_year": 0.0,
      "min_full_signals_per_year": 0.6493333333333333,
      "min_latest_252_signals": 0,
      "min_limited_signals_per_year": 0.0,
      "pass_rows": 0,
      "variant_id": "london_short_trident_ema13_0630",
      "verdict": "FAIL"
    },
    {
      "entry_rows": 9,
      "max_full_signals_per_year": 2.7272000000000003,
      "max_latest_252_signals": 1,
      "max_limited_signals_per_year": 3.2437833037300177,
      "median_full_signals_per_year": 2.1428000000000003,
      "median_latest_252_signals": 1.0,
      "median_limited_signals_per_year": 2.5950266429840143,
      "min_full_signals_per_year": 1.6882666666666668,
      "min_latest_252_signals": 1,
      "min_limited_signals_per_year": 1.9462699822380105,
      "pass_rows": 0,
      "variant_id": "london_two_sided_trident_ema13_0630",
      "verdict": "FAIL"
    },
    {
      "entry_rows": 9,
      "max_full_signals_per_year": 2.4674666666666667,
      "max_latest_252_signals": 1,
      "max_limited_signals_per_year": 2.5950266429840143,
      "median_full_signals_per_year": 1.9480000000000002,
      "median_latest_252_signals": 1.0,
      "median_limited_signals_per_year": 1.9462699822380105,
      "min_full_signals_per_year": 1.5584,
      "min_latest_252_signals": 1,
      "min_limited_signals_per_year": 1.2975133214920072,
      "pass_rows": 0,
      "variant_id": "london_two_sided_trident_ema15_strict_confirm_0630",
      "verdict": "FAIL"
    }
  ]
}
```

## Variant Summary

| variant_id | entry_rows | pass_rows | min_full_signals_per_year | median_full_signals_per_year | max_full_signals_per_year | min_limited_signals_per_year | median_limited_signals_per_year | max_limited_signals_per_year | min_latest_252_signals | median_latest_252_signals | max_latest_252_signals | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| london_long_trident_ema13_0630 | 9 | 0 | 1.0389333333333335 | 1.3636000000000001 | 1.7532 | 1.9462699822380105 | 2.5950266429840143 | 2.5950266429840143 | 1 | 1.0 | 1 | FAIL |
| london_long_trident_ema15_0630 | 9 | 0 | 1.0389333333333335 | 1.3636000000000001 | 1.7532 | 1.9462699822380105 | 2.5950266429840143 | 2.5950266429840143 | 1 | 1.0 | 1 | FAIL |
| london_short_trident_ema13_0630 | 9 | 0 | 0.6493333333333333 | 0.7792 | 0.9740000000000001 | 0.0 | 0.0 | 0.6487566607460036 | 0 | 0.0 | 0 | FAIL |
| london_two_sided_trident_ema13_0630 | 9 | 0 | 1.6882666666666668 | 2.1428000000000003 | 2.7272000000000003 | 1.9462699822380105 | 2.5950266429840143 | 3.2437833037300177 | 1 | 1.0 | 1 | FAIL |
| london_two_sided_trident_ema15_strict_confirm_0630 | 9 | 0 | 1.5584 | 1.9480000000000002 | 2.4674666666666667 | 1.2975133214920072 | 1.9462699822380105 | 2.5950266429840143 | 1 | 1.0 | 1 | FAIL |

## Predeclared Mechanics

- Instrument: NQ futures.
- Data: local Databento one-minute ETH/RTH explicit-roll OHLCV cache, resampled to 30-minute bars.
- Setup window: the third candle of a three-candle FVG starts between 02:30 and 04:00 ET.
- Entry window: confirmation completes between 03:00 and 06:30 ET; staged testing, if approved, would enter next 30-minute open.
- Long setup: bullish FVG, stacked 5/9/13-or-15/21 EMAs, close above 200 EMA, doji wick into FVG midpoint with body above midpoint, confirmation close above doji high.
- Short setup: bearish FVG, reverse EMA stack, close below 200 EMA, doji wick into FVG midpoint with body below midpoint, confirmation close below doji low.
- Entry tunables: min_gap_ticks in [1, 2, 4] and max_doji_body_ratio in [0.25, 0.35, 0.45].
- Stop tunable for campaign definition: stop_offset_ticks in [0, 4, 8].
- Take-profit tunable for campaign definition: target_r_multiple in [2.0, 3.0].

## Lookahead Controls

- FVGs are known only after the third 30-minute candle closes.
- The doji and confirmation candle are both completed before any signal is counted.
- EMA state uses only completed 30-minute closes through the confirmation candle.
- No future high, low, session range, VWAP, orderflow, or post-entry path is used.
