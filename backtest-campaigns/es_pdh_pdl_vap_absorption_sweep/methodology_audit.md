# ES PDH/PDL Developing VAP Absorption Sweep Methodology Audit

Decision: FAIL

This is an exact user-specified smoke implementation, not a completed five-variant
campaign-family search. I did not invent extra variants after seeing the zero-trade
smoke result.

## Mechanics

- Direction: both directions.
- Either PDH or PDL sweep-and-return can qualify either direction.
- Short setup: near developing VAH, positive four-tick aggregate delta at least 300,
  then at least five seconds later price is below that positive-delta zone.
- Long setup: near developing VAL, negative four-tick aggregate delta at most -300,
  then at least five seconds later price is above that negative-delta zone.
- LVN is defined as volume less than or equal to 10% of POC volume.
- Structure timeframe: 3-minute bars.
- Entry timing: intrabar release timestamp and release price from Sierra SCID-derived records;
  no wait for the 3-minute bar close.
- Stop: sweep extreme.
- Target: 1.5R.
- Session gate: entries from 09:30 through 11:30 America/New_York.

## No-Lookahead Controls

- Previous-day high/low come from the completed prior RTH session.
- Developing VAH/VAL/POC and the no-LVN value-area check are computed only through the
  intrabar release timestamp.
- The 3-minute strategy bars are generated from a 1-minute source cache, preserving
  lower-timeframe detail for stop/target ordering.
- For the first 1-minute detail bar containing an intrabar entry, target-only fills are
  suppressed while stop fills remain eligible.

## Smoke Result

- Smoke cache: `data/cache/orderflow/es_pdh_pdl_vap_absorption_sweep_1m_source_3m_features_20260601_20260609_rth_ny.parquet`
- Period: 2026-06-01 through 2026-06-09 RTH.
- Strategy rows: 910 3-minute rows.
- Detail rows: 2730 1-minute rows.
- Raw intrabar release rows: 274 short-side, 273 long-side.
- Trades generated: 0.
- Apex rule violations: 0.

Gate audit: `research_artifacts/es_pdh_pdl_vap_absorption_sweep_smoke_gate_audit_20260626.csv`

## 2026 YTD Result

- YTD cache: `data/cache/orderflow/es_pdh_pdl_vap_absorption_sweep_1m_source_3m_features_20260102_20260609_rth_ny.parquet`
- Period: 2026-01-02 through 2026-06-09 RTH, the latest available local Sierra cache range.
- Strategy rows: 14,170 3-minute rows.
- Detail rows: 42,510 1-minute rows.
- Raw intrabar release rows: 4,298 short-side, 4,305 long-side.
- Engine signals generated: 4.
- Trades closed: 4.
- Exits: 3 stop, 1 target.
- Net profit: -932.50.
- Profit factor: 0.3635.
- Expectancy R: -0.5262.
- Trades per year: 10.08.
- Win rate: 25%.
- Max drawdown: 1,465.00.
- MAR: -1.5960.
- Apex rule violations: 0.

YTD gate audit: `research_artifacts/es_pdh_pdl_vap_absorption_sweep_ytd_2026_gate_audit_20260626.csv`

## 2026 YTD LVN10 / 1.5R / Sweep-Any Rerun

- Cache: `data/cache/orderflow/es_pdh_pdl_vap_absorption_sweep_lvn10_1m_source_3m_features_20260102_20260609_rth_ny.parquet`
- Cache validation: `data/cache/orderflow/es_pdh_pdl_vap_absorption_sweep_lvn10_1m_source_3m_features_20260102_20260609_rth_ny.validation.json`
- Period: 2026-01-02 through 2026-06-09 RTH.
- Strategy rows: 14,170 3-minute rows.
- Detail rows: 42,510 1-minute rows.
- Raw intrabar release rows: 4,298 short-side, 4,305 long-side.
- Engine signals generated: 33.
- Trades closed: 33.
- Exits: 12 target, 19 stop, 2 EOD flatten.
- Net profit: 147.50.
- Profit factor: 1.0170.
- Expectancy R: -0.0522.
- Trades per year: 77.78.
- Win rate: 42.42%.
- Max drawdown: 6,152.50.
- MAR: 0.0581.
- Apex rule violations: 0.

Rerun gate audit: `research_artifacts/es_pdh_pdl_vap_absorption_sweep_lvn10_tp15_ytd_2026_gate_audit_20260626.csv`

## Verdict

The latest LVN10 / 1.5R / sweep-any rerun still fails closed. It improved density and
nominal net profit, but profit factor remains below 1.2, expectancy R is negative, MAR
is far below 0.4, and drawdown is too large relative to edge. It does not justify monkey,
WFA, Monte Carlo, incubation, or acceptance testing.
