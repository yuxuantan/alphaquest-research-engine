# ES Overnight VAP Footprint Trap Reversion Density Audit

Date: 2026-06-22

Decision: approve_for_testing_before_pnl

This audit checked whether the proposed overnight high/low plus prior true VAP plus
footprint absorption setup has enough completed-bar signal density to justify staged
PnL testing. It did not inspect trade PnL or tune mechanics after PnL results.

## Data

- Cache: `data/cache/orderflow/es_sierra_footprint_vap_overnight_aoi_1m_20110103_20260529_rth_ny.parquet`
- Validation: `data/cache/orderflow/es_sierra_footprint_vap_overnight_aoi_1m_20110103_20260529_rth_ny.validation.json`
- Rows: 1,485,900
- Bars with completed overnight levels: 1,483,560
- Duplicate timestamps: 0
- Overnight feature rows with bad windows: 0
- Six RTH sessions lack completed overnight features and therefore fail closed with null overnight AOIs:
  2014-06-12, 2014-06-13, 2014-09-23, 2014-09-24, 2014-09-25, 2014-12-31.

## Signal Predicate

Long signal density required all of the following on a completed 1-minute RTH bar:

- `low <= overnight_low - min_probe_ticks * 0.25`
- `close >= overnight_low + confirmation_ticks * 0.25`
- `close > open`
- nearest prior true VAP level within `max_profile_distance_ticks`
- `footprint_absorption_long > 0`
- `footprint_max_sell_imbalance_volume >= min_absorption_volume`
- `footprint_highest_sell_imbalance_price < close`

Short signal density used the symmetric overnight-high, buyer-absorption, and close-back-below rules.
Only one signal per session was counted.

## Retained Variants

The retained variants use the same 81-combination grid:
`max_profile_distance_ticks` 4/8/16, `min_absorption_volume` 20/50/100,
`stop_offset_ticks` 1/2/4, and `target_r_multiple` 1.25/2.0/3.0.

| Variant | Fixed mechanics | Density evidence before PnL |
|---|---|---|
| `overnight_vap_immediate_open_trap_two_sided_1500` | Start 09:31, end 15:00, 1-tick probe, 0-tick confirmation | Up to 1,185 signals, 76.9 trades/year at distance 16 / absorption 20 |
| `overnight_vap_two_sided_trap_1530` | Start 09:35, end 15:30, 1-tick probe, 0-tick confirmation | Up to 1,224 signals, 79.5 trades/year at distance 16 / absorption 20 |
| `overnight_vap_confirmed_reclaim_two_sided_1530` | Start 09:35, end 15:30, 1-tick probe, 1-tick confirmation | Up to 1,087 signals, 70.6 trades/year at distance 16 / absorption 20 |
| `overnight_vap_deep_probe_two_sided_1530` | Start 09:35, end 15:30, 2-tick probe, 0-tick confirmation | Up to 1,051 signals, 68.2 trades/year at distance 16 / absorption 20 |
| `overnight_vap_morning_trap_two_sided_1200` | Start 09:35, end 12:00, 1-tick probe, 0-tick confirmation | Up to 811 signals, 52.7 trades/year at distance 16 / absorption 20 |

## Rejected Before PnL

- Direction-specific long-only and short-only overnight trap variants were rejected before PnL because
  they stayed below the configured 50 trades/year gate even when extended through 15:00 ET.
- Adverse signed-delta filters at 0.005 through 0.02 were rejected before PnL because they stayed below
  the configured 50 trades/year gate.

## Lookahead Controls

- Overnight high/low features end no later than 09:29 ET for the same RTH session.
- Prior VAP columns are shifted from completed prior RTH sessions.
- The entry module uses the completed signal bar and enters no earlier than the next 1-minute open.
- No final current-session profile, VWAP, daily range, or future footprint information is used.
