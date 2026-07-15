# Data Contracts

Every campaign must declare a stable dataset ID, source path, symbol, timezone, timeframe, and session semantics. Raw vendor files are immutable. Derived caches must record their source files, construction policy, and validation report.

Preflight checks:

- data path existence
- supported source type
- timezone-aware timestamps
- duplicate bars
- required OHLCV fields
- explicit continuous-contract rule

Feature builders must use only information available at the decision timestamp. Daily or macro series require a documented publication lag. Current-session levels must be developing values, never final-session values used retrospectively.

## Trade-event data

Event-sensitive strategies must declare an execution source and event semantics. A row
in a vendor file is not automatically a trade event. Sierra SCID FIRST/LAST groups must
be reconstructed by exact price and aggressor side, with component volume summed and
source order retained as `(timestamp, source_ordinal)`.

Per-session capability manifests are mandatory for proxy sources. A profile/delta pass
does not imply a 100 ms trigger pass. Runs must error or explicitly blackout ineligible
sessions; they may not silently extrapolate an independently checked window or era.

Fields based on event size, event count, fragmentation, or sequential timing must be
rebuilt from canonical events. Legacy raw-component `large200_record_*` fields are not
valid trade-event features. Databento `trades` provides trade messages, not MBO/DOM, and
that limitation must remain in the source-quality label.
