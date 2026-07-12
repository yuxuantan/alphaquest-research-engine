# Data

- `raw/`: immutable vendor/source files.
- `reference/`: calendars, rolls, and other governed reference data.
- `external/`: downloaded or manually sourced auxiliary series.
- `cache/`: reproducible derived datasets and feature caches.
- `reports/`: generated reports, not authored research evidence.

Do not edit raw data in place. Every derived cache must document source paths, timestamp semantics, availability lag, and validation status. See [data contracts](../docs/data/data-contracts.md).
