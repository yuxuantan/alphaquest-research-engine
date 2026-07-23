# nq_connors_rsi2_mean_reversion density audit

- Audit date: 2026-06-30
- Full window: 2011-01-03 to 2026-06-12 (3813 sessions)
- Limited-core window: 2011-02-22 to 2012-09-07
- Latest-252 window: 2025-06-09 to 2026-06-12
- Declared entry rows: 45
- Density passes: 41
- Density failures: 4

Gate: each declared entry row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.

The signal count mirrors the entry module's completed-bar RSI2 state, MA/VWAP trend filters, configured entry window, and one-signal-per-session cap.

| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | verdict |
|---|---:|---:|---:|---:|---:|---|
| fifteen_min_long_uptrend_pullback_1545 | 9 | 8 | 40.03 | 42.17 | 46 | FAIL |
| fifteen_min_short_downtrend_bounce_1545 | 9 | 6 | 29.34 | 32.44 | 29 | FAIL |
| five_min_long_vwap_extreme_1430 | 9 | 9 | 69.05 | 53.20 | 82 | PASS |
| five_min_short_vwap_extreme_1430 | 9 | 9 | 56.16 | 52.55 | 58 | PASS |
| thirty_min_two_sided_trend_reversion_1530 | 9 | 9 | 52.08 | 52.55 | 51 | PASS |

Machine summary:

```json
{
  "all_rows_density_pass": false,
  "audit_date": "2026-06-30",
  "campaign_id": "nq_connors_rsi2_mean_reversion",
  "declared_entry_rows": 45,
  "density_fail_rows": 4,
  "density_pass_rows": 41,
  "failed_variants": [
    "fifteen_min_long_uptrend_pullback_1545",
    "fifteen_min_short_downtrend_bounce_1545"
  ],
  "full_end_date": "2026-06-12",
  "full_sessions": 3813,
  "full_start_date": "2011-01-03",
  "latest_252_end_date": "2026-06-12",
  "latest_252_start_date": "2025-06-09",
  "limited_end_date": "2012-09-07",
  "limited_start_date": "2011-02-22",
  "min_full_signals_per_year": 29.34177159070757,
  "min_latest_252_signals": 29,
  "min_limited_signals_per_year": 32.43783303730017,
  "prepared_rows_by_timeframe": {
    "15m": 99138,
    "30m": 49569,
    "5m": 297414
  }
}
```

Detail CSV: `research_artifacts/nq_connors_rsi2_mean_reversion_density_audit_20260630.csv`

Summary CSV: `research_artifacts/nq_connors_rsi2_mean_reversion_density_summary_20260630.csv`
