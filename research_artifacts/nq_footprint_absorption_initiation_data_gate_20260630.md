# NQ Footprint Absorption Initiation Data Gate

Decision: NEEDS MANUAL REVIEW

The ES `es_footprint_absorption_initiation` campaign is not eligible for an honest NQ port with the current local data. Its defining edge is price-level bid/ask footprint imbalance and absorption location relative to the signal close.

Local cache check on 2026-06-30 found ES footprint imbalance/VAP caches only. No NQ footprint imbalance cache exists under `data/cache/orderflow/`.

Rejected substitutes:
- Do not replace price-level footprint absorption with NQ bar-level signed volume; that would change the mechanic and duplicate existing aggregate-orderflow campaigns.
- Do not test only AOI levels without footprint fields; that would duplicate prior-session, opening-range, round-number, and session-open orderflow families.

Required external-state change: build or provide a validated NQ Sierra at-price footprint imbalance cache with `footprint_absorption_long`, `footprint_absorption_short`, imbalance volume, and imbalance price fields at the 1-minute source timeframe.
