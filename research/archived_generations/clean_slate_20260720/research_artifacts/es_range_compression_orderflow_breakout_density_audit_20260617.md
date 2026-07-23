# ES Range Compression Orderflow Breakout Density Audit

Date: 2026-06-17

Purpose: pre-PnL eligibility screen for a bounded composite campaign. This audit checked raw signal frequency only. It did not inspect stops, targets, net profit, drawdown, WFA, or any performance result.

Data:
- Local Sierra aggregate orderflow cache only: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Prepared through the repo data pipeline with `feature_set: none`
- Strategy timeframe: 5-minute RTH bars
- Date range: 2011-01-03 through 2026-06-09
- No network access or paid data download

Composite edge definition:
- Primary price-action edge: prior RTH session is NR4 range compression.
- Breakout reference: prior RTH high/low or completed RTH opening range.
- Aggregate orderflow condition: same completed breakout bar must have signed flow aligned with breakout direction.

Rejected before PnL:
- ID/NR4 prior-session flow breakout: strict-corner density about 12.77/year.
- NR7 opening-range signed and large-flow variants: strict-corner density about 29-32/year.
- Any formulation requiring rare compression plus rare flow thresholds below the 50/year methodology floor.

Approved entry grids:
- Prior-session variants: `entry.params.min_breakout_ticks: [0, 2, 4]`
- Opening-range variants: `entry.params.min_breakout_ticks: [0, 1, 2]`
- All variants: `entry.params.min_orderflow_imbalance: [0.02, 0.05, 0.08]`

Selected variants:

| Variant | Reference | Flow bucket | Signal window ET | Min signals/year | Median signals/year | Max signals/year | Decision |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| nr4_prior_large20_flow_breakout_1400 | prior RTH high/low | large20 | 09:35-14:00 | 56.19 | 57.42 | 58.84 | approve_for_testing |
| nr4_prior_signed_flow_breakout_1400 | prior RTH high/low | signed | 09:35-14:00 | 53.72 | 57.16 | 59.43 | approve_for_testing |
| nr4_or15_large20_flow_breakout_1200 | 15-minute opening range | large20 | 09:45-12:00 | 62.93 | 63.70 | 64.22 | approve_for_testing |
| nr4_or30_large10_flow_breakout_1400 | 30-minute opening range | large10 | 10:00-14:00 | 62.34 | 63.58 | 63.90 | approve_for_testing |
| nr4_or60_signed_flow_breakout_1330 | 60-minute opening range | signed | 10:30-13:30 | 51.72 | 55.09 | 58.26 | approve_for_testing |

Duplicate-edge decision:
- Not the plain `es_range_compression_breakout` campaign because same completed-bar aggregate orderflow confirmation is required for every signal.
- Not `es_opening_range_orderflow_breakout` because the prior-session NR4 compression state is mandatory before any opening-range breakout can signal.
- Not standalone `es_signed_orderflow_persistence` because public price-action breakout from compression is the primary trigger.

Final pre-PnL decision: approve exactly five NR4 range-compression plus aggregate-orderflow breakout variants for staged testing.
