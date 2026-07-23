# Paid Data Consent Policy - 2026-06-16

Decision: active policy.

User instruction:
- Never download data that costs any money unless the user explicitly gives permission.

Operational rule:
- Metadata checks, dry runs, local-file inventory checks, and free public-data downloads are allowed when needed for research.
- Any non-dry-run paid vendor request, including Databento historical data, requires explicit user approval for the exact data pull before execution.
- Approval must cover the vendor, dataset/schema, symbols, date range, and expected cost or cost cap.
- A fresh metadata/cost check should be run immediately before any paid pull when the vendor supports it.

Code guard:
- `python3 -m propstack.download_databento_rth_trades` now refuses any non-dry-run request unless `--paid-data-approved` is passed.
- The flag is not a substitute for approval; it is an execution-time record that approval was already received.

Current state:
- The interrupted ES Databento `trades` pull in `data/raw/ES/databento-es-trades-2020-2026` is incomplete and not validated.
- Do not use that directory as a complete research input unless a future explicitly approved run completes it and writes a complete manifest.
