# ES Overnight VAP Orderflow Breakout Continuation Density Audit

Date: 2026-06-22

Decision: approve_for_testing_before_pnl

This audit checked signal density only. It did not inspect PnL or tune mechanics after results.

## Data

- Cache: `data/cache/orderflow/es_sierra_footprint_vap_overnight_aoi_1m_20110103_20260529_rth_ny.parquet`
- Validation: `data/cache/orderflow/es_sierra_footprint_vap_overnight_aoi_1m_20110103_20260529_rth_ny.validation.json`
- Rows: 1,485,900
- Bars with completed overnight levels: 1,483,560
- Bad overnight windows: 0
- Duplicate timestamps: 0

## Signal Predicate

Long signal density required a completed RTH bar to break above `overnight_high`,
close in the breakout direction, align with same-direction aggregate flow, have
footprint buy-imbalance volume above the fixed threshold, and be near a prior true
VAP level. Short signal density used the symmetric overnight-low breakdown rules.
Only one signal per session was counted.

## Retained Variants

The retained variants use the same 81-combination grid:
`max_profile_distance_ticks` 4/8/16, `min_orderflow_imbalance` 0.01/0.02/0.05,
`stop_offset_ticks` 1/2/4, and `target_r_multiple` 1.25/2.0/3.0.

| Variant | Fixed mechanics | Density evidence before PnL |
|---|---|---|
| `overnight_vap_immediate_breakout_two_sided_1500` | Signed-volume flow, start 09:31, end 15:00 | Up to about 2,004 signals, 130.1 trades/year |
| `overnight_vap_two_sided_breakout_1530` | Signed-volume flow, start 09:35, end 15:30 | Up to about 2,023 signals, 131.4 trades/year |
| `overnight_vap_morning_breakout_two_sided_1200` | Signed-volume flow, start 09:35, end 12:00 | Up to about 1,734 signals, 112.6 trades/year |
| `overnight_large10_vap_breakout_two_sided_1530` | Sierra large10 aggregate-flow proxy, start 09:35, end 15:30 | Up to about 2,014 signals, 130.8 trades/year |
| `overnight_large20_vap_breakout_two_sided_1530` | Sierra large20 aggregate-flow proxy, start 09:35, end 15:30 | Up to about 2,015 signals, 130.8 trades/year |

## Lookahead Controls

- Overnight high/low levels end no later than 09:29 ET for the same RTH session.
- Prior VAP columns are shifted from completed prior RTH sessions.
- Signals use the completed breakout bar and enter no earlier than the next 1-minute open.
- No final current-session profile, VWAP, daily range, or future footprint/orderflow information is used.
