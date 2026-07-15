# Data

- `raw/`: immutable vendor/source files.
- `reference/`: calendars, rolls, and other governed reference data.
- `external/`: downloaded or manually sourced auxiliary series.
- `cache/`: reproducible derived datasets and feature caches.
- `reports/`: generated reports, not authored research evidence.

Do not edit raw data in place. Every derived cache must document source paths, timestamp semantics, availability lag, and validation status. See [data contracts](../docs/data/data-contracts.md).

## ES Sierra SCID event validation

The current tick-reference comparison is
[`reports/data_quality/ES/databento_sierra_tick_comparison_0930_1100_20250714_20260610/report.md`](reports/data_quality/ES/databento_sierra_tick_comparison_0930_1100_20250714_20260610/report.md).
It compares Sierra records with the immutable Databento `trades` archive at
`raw/ES/GLBX-20260713-S6XF67C8UA.zip` for the range strategy's 09:30-11:00 ET window.

Sierra FIRST/LAST unbundled-trade marker groups must be reconstructed before any
event-sensitive feature is calculated. Preserve source order, aggregate each marker
group by exact price and aggressor side, sum component volume, and retain an explicit
source ordinal. Use the comparison report's component-specific date allowlists; do
not extrapolate the one-year result to older contracts without independent tick evidence.

Production event paths are now fail closed:

- `reference/ES/event_quality/sierra_event_capabilities_0930_1100.csv` is the session/capability manifest.
- Sierra event replay is limited to the independently checked 09:30-11:00 ET window.
- `full_strategy_events` is required for the strict 100 ms big-trade trigger; `profile_delta` is a separate capability.
- The purchased year should use `execution_data.source: databento_zip_trades` directly.
- Older Sierra dates are structural/minute-bar sensitivity data only, not faithful event evidence.
- Legacy `large200_record_*` and raw-record trade-count fields are prohibited; see
  `reference/ES/event_quality/legacy_sierra_cache_restrictions.yaml`.

The exact direct-source 1-minute morning cache is
`cache/orderflow/es_databento_trades_1m_20250714_20260610_0930_1100_ny.parquet`.
Large-trade triggers are intentionally not materialized in that bar cache; replay the
canonical event stream so the same-price, same-side, uninterrupted 100 ms state machine
is evaluated in source order.

## ES Sierra price-only TPO lane

`cache/price_only/es_sierra_price_only_tpo_1m_20110815_20260609_0930_1100_ny.parquet`
is a separate, reproducible sensitivity lane for completed-bar auction/TPO strategies.
Build it with `tools/build_sierra_price_only_tpo_cache.py`. It admits only regular
sessions that pass the existing raw-structure gate and contain all 90 morning minutes.

This lane may use completed one-minute OHLC, time-at-price/TPO, and opening-range
levels. It must not be used for volume profile, delta, aggressor side, event size/count,
or sub-second sequencing. Older admitted sessions are internally screened rather than
independently event-verified, and the cache does not provide a historical high-impact
USD news calendar.
