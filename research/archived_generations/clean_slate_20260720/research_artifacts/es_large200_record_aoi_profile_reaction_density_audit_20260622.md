# ES Large200 Record AOI Profile Reaction Density Audit

Verdict before PnL: approve for staged testing as a proxy-only campaign.

This audit does not validate true ES prints above 200 lots. It validates only a bounded
local proxy: Sierra SCID rows with `volume >= 200`, `num_trades == 1`, and exact side-volume
coverage, merged back to the completed 1-minute footprint cache.

## Source-Quality Gate

- Raw Sierra ES trade Parquet files scanned: 65.
- Raw rows scanned: 2,902,395,425.
- Raw records with `volume >= 200`: 503,526.
- `volume >= 200` records with `num_trades == 1`: 341,824.
- `volume >= 200` records with `num_trades > 1`: 6,793.
- `volume >= 200` records with `num_trades == 0`: 154,909.
- Bad large-record clusters were concentrated in older 2010-2011 files and excluded from the 2012+ proxy cache.
- Active RTH proxy records retained from 2012-01-03 through 2026-06-09: 170,425 before merge and 167,326 after merge to the footprint cache.
- Merged proxy cache rows: 1,395,420.
- Merged proxy cache large-record minutes: 104,377.
- Source-quality label: Sierra SCID large-record proxy only; not vendor-equivalent large-print truth.

## Density Gate

Density was measured before PnL using completed-bar levels only:

- Prior RTH high and low from the completed previous RTH session.
- Prior POC, VAH, VAL, and LVNs from the completed previous RTH session.
- Opening-range high and low only after the first 30 RTH one-minute bars closed.
- Large-record side from completed-bar `large200_record_signed_volume`.
- Threshold uses `large200_record_max_volume >= min_large`.

Representative results with `min_large=200`:

| Variant family | Max profile distance ticks | Raw signals | Signal sessions | Sessions/year | Raw signals/year |
| --- | ---: | ---: | ---: | ---: | ---: |
| all_combo | 16 | 4,817 | 1,468 | 101.72 | 333.79 |
| market_trap | 16 | 1,841 | 928 | 64.31 | 127.57 |
| market_cont | 16 | 1,673 | 927 | 64.24 | 115.93 |
| profile_trap | 16 | 932 | 597 | 41.37 | 64.58 |
| profile_cont | 16 | 777 | 517 | 35.83 | 53.84 |
| all_combo | 32 | 5,370 | 1,656 | 114.75 | 372.11 |
| market_trap | 32 | 2,105 | 1,080 | 74.84 | 145.86 |
| market_cont | 32 | 1,970 | 1,094 | 75.81 | 136.51 |
| all_combo | 64 | 5,764 | 1,817 | 125.91 | 399.41 |
| market_trap | 64 | 2,308 | 1,193 | 82.67 | 159.93 |
| market_cont | 64 | 2,161 | 1,216 | 84.26 | 149.74 |

The profile-only variants do not clear 50 sessions/year with a one-signal-per-day cap,
but they clear 50 raw signals/year. They are therefore configured with a fixed two-trades-per-day
cap before PnL. This is not a rescue or result-driven change.

## Decision

Proceed to normal staged tests with fail-closed interpretation. Any pass from this campaign
is a candidate strategy requiring manual due diligence and independent print-source verification.
