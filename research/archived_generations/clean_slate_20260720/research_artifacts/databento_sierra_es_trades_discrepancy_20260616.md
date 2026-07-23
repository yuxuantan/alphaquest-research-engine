# Databento vs Sierra ES Trades Discrepancy Audit - 2026-06-16

Status: NEEDS MANUAL REVIEW for the interrupted Databento daily directory; usable as a diagnostic sample only.

## Inputs Compared

- Completed Databento one-year ES trade-orderflow cache:
  `data/cache/orderflow/es_trade_orderflow_1m_20250609_20260608.csv`
- Interrupted Databento daily ES trades directory:
  `data/raw/ES/databento-es-trades-2020-2026`
- Validated Sierra ES 1-minute trade-orderflow cache:
  `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`

Temporary detailed outputs from this audit:

- `/tmp/propstack_databento_sierra_es_compare_20260616/summary.json`
- `/tmp/propstack_databento_sierra_es_compare_20260616/daily_column_summary.csv`
- `/tmp/propstack_databento_sierra_es_compare_20260616/daily_session_comparison.csv`
- `/tmp/propstack_databento_sierra_es_compare_20260616/daily_same_contract_ohlcv_side_discrepancies.csv`
- `/tmp/propstack_databento_sierra_es_compare_20260616/timestamps_only_in_databento.csv`
- `/tmp/propstack_databento_sierra_es_compare_20260616/timestamps_only_in_sierra.csv`

## Completed One-Year Cache Findings

Range: `2025-06-09 09:30:00` through `2026-06-08 15:59:00`.

- Databento rows: 96,720 across 248 full RTH sessions.
- Sierra rows over the same range: 96,720 across 248 full RTH sessions.
- Missing timestamps: none on either side for this one-year range.
- Cosmetic contract-symbol difference: Databento uses one-digit years, for example `ESU5`; Sierra uses two-digit years, for example `ESU25`.

Full-day roll-selection discrepancies:

- `2025-06-16`: Databento selected `ESU5`; Sierra selected `ESM25`.
- `2025-09-15`: Databento selected `ESZ5`; Sierra selected `ESU25`.
- `2025-12-15`: Databento selected `ESH6`; Sierra selected `ESZ25`.
- `2026-03-16`: Databento selected `ESM6`; Sierra selected `ESH26`.

After excluding those four roll-selection sessions:

- Same-contract rows: 95,160 across 244 full RTH sessions.
- OHLC mismatches: zero.
- Volume mismatches: 3 rows, total Databento minus Sierra difference `+7` contracts, max absolute row difference `3`.
- Signed-volume mismatches: 4 rows, total Databento minus Sierra difference `+117`, max absolute row difference `114`.
- `trades`, `large10_*`, and `large20_*` mismatch nearly every row and should not be treated as equivalent fields.

## Interrupted Daily Directory Findings

Completed local files: 1,250.

Partial `.part` files: 5.

Databento completed-file aggregate:

- Rows: 466,387.
- Sessions: 1,196.
- First timestamp: `2020-01-02 09:30:00`.
- Last timestamp: `2024-10-15 15:59:00`.

Sierra over the same timestamp range:

- Rows: 464,880.
- Sessions: 1,192.

Timestamp coverage:

- Common timestamps: 464,100.
- Timestamps only in Databento: 2,287.
- Timestamps only in Sierra: 780.

Coverage discrepancies:

- `2020-02-28` and `2020-06-30` have completed Databento files on disk, but the raw events end early and aggregate to zero complete RTH bars.
- Databento-only sessions:
  - `2020-03-09`: 377 rows, 13 missing minutes.
  - `2020-03-12`: 377 rows, 13 missing minutes.
  - `2020-03-16`: 376 rows, 14 missing minutes.
  - `2020-03-18`: 377 rows, 13 missing minutes.
  - `2021-12-31`: 390 rows.
  - `2023-03-07`: 390 rows.
- Sierra-only sessions:
  - `2020-02-28`: 390 rows.
  - `2020-06-30`: 390 rows.

Roll or active-contract selection mismatch sessions: 27.

Dates:

`2020-03-13`, `2020-06-12`, `2020-06-15`, `2020-09-11`, `2020-09-14`, `2020-12-11`, `2020-12-14`, `2021-03-12`, `2021-03-15`, `2021-06-11`, `2021-06-14`, `2021-09-10`, `2021-09-13`, `2021-12-10`, `2021-12-13`, `2022-03-11`, `2022-03-14`, `2022-06-13`, `2022-09-12`, `2022-12-12`, `2023-03-13`, `2023-06-12`, `2023-09-11`, `2023-12-11`, `2024-03-11`, `2024-06-17`, `2024-09-16`.

After excluding those roll-selection sessions:

- Same-contract rows: 453,570 across 1,163 sessions.
- Rows with OHLC/volume/side discrepancy: 228.
- 191 of the 228 discrepancy rows are at `15:59:00`.
- Open mismatches: 2 rows, max absolute difference `0.75`.
- High mismatches: 0 rows.
- Low mismatches: 0 rows.
- Close mismatches: 51 rows, max absolute difference `0.75`.
- Volume mismatches: 196 rows, total Databento minus Sierra difference `-4,902` contracts, max absolute row difference `388`.
- Signed-volume mismatches: 227 rows, total Databento minus Sierra difference `-5,131`, max absolute row difference `880`.

Non-equivalent fields after excluding roll-selection sessions:

- `trades`: 453,569 mismatching rows out of 453,570.
- `large10_volume`: 453,556 mismatching rows.
- `large20_volume`: 452,488 mismatching rows.

These fields are not vendor-equivalent because Databento is aggregating individual trade prints, while the Sierra SCID-derived cache is aggregating Sierra trade records with its own `num_trades`, side-volume, and record-volume semantics.

## Interpretation

The completed one-year Databento cache and the Sierra cache agree extremely closely for completed-bar OHLC and total volume once roll-selection dates are excluded. The interrupted daily Databento directory shows the same broad pattern, but it also contains coverage defects and should not be used as a validated input.

For completed-bar OHLCV and aggregate signed-volume research, Sierra is defensible after applying the existing strict session and roll-calendar policy.

For print-level sequencing, trade counts, and large-print features, Sierra SCID-derived fields are not a substitute for Databento prints without a separate source-quality audit.
