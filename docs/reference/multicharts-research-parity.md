# MultiCharts research and backtesting parity

AlphaQuest targets research and backtesting parity, not terminal parity. The
comparison surface is the current MultiCharts feature catalogue:

- <https://www.multicharts.com/features/chart-analysis/>
- <https://www.multicharts.com/features/chart-types/>
- <https://www.multicharts.com/features/volume-analysis/>
- <https://www.multicharts.com/features/strategy-backtesting/>
- <https://www.multicharts.com/features/strategy-optimization/>
- <https://www.multicharts.com/features/walk-forward/>
- <https://www.multicharts.com/features/trading-system-analysis/>
- <https://www.multicharts.com/features/simulator/>
- <https://www.multicharts.com/features/market-scanner/>

The live capability contract is returned by
`GET /api/analysis/capabilities` and displayed in Studio under **Analysis**.
That contract is authoritative for product claims.

## Implemented equivalents

| MultiCharts research capability | AlphaQuest equivalent |
| --- | --- |
| Multi-resolution and multi-series charts | Hash-verified governed chart snapshot with native, 5/15/30/60-minute, daily, and comparison views |
| OHLC, candles, hollow candles, line, Heikin-Ashi | Read-only Studio chart types; derived bars are explicitly non-executable |
| Volume and cumulative delta | Canonical volume plus delta only when retained by the governed dataset |
| Volume Profile and TPO | Certified order-flow/TPO datasets and mechanics evidence |
| Drawing and measurement tools | Local horizontal levels and two-point trend measurements |
| Market-data playback | Deterministic first/previous/play/next/jump playback with selectable speed |
| Market scanner | On-demand latest-state scan across hash-verified governed datasets |
| Exhaustive optimization | Predeclared core grid over every combination |
| Custom optimization fitness | Frozen stage criteria and objective benchmark gates |
| Walk-forward testing | Contiguous or purged windows with stitched unseen OOS trades |
| High-precision execution | Certified event/quote replay with market, limit, stop, stop-limit, OCO, partial fills, and bid/ask liquidity |
| Strategy performance report | Strict ResultBundleV2, 147 scoped extended statistic fields, trade explorer, curves, breakdowns, Monte Carlo, and parameter surfaces |
| Report export and printing | Hash-verified ZIP export plus print layout |
| Report/chart synchronization | Trade selection updates the retained execution chart; sampled mechanics evidence links to native event replay |

## Scientifically stronger substitutions

Genetic optimization is not used. AlphaQuest caps a governed parameter space at
120 combinations, so exhaustive evaluation is practical and stronger than a
lossy heuristic search. A genetic result would hide untested combinations and
weaken parameter-neighbour evidence.

Renko, Kagi, Point & Figure, and Line Break charts are not inferred from OHLC
bars. Exact construction requires the ordered tick path. The Analysis capability
contract reports them as `data_required`; they become eligible only when the
source dataset retains and certifies that path.

## Explicit exclusions

The following are outside the agreed product scope:

- live broker routing and synchronization;
- DOM, chart trading, discretionary order entry, and account tracking;
- EasyLanguage or PowerLanguage compatibility;
- multi-strategy portfolio simulation, until multiple strategies are actually
  traded.

These exclusions must not be presented as implemented or approximated.
