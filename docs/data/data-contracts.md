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
