# ChartFanatics source gate after BTC campaign rejection

Generated: 2026-07-01

Scope: refreshed the live ChartFanatics futures strategy index after `nq_btc_crypto_risk_sentiment` failed staged validation.

Reviewed pages:

- Trading Strategies index: https://www.chartfanatics.com/strategies
- The VIX Futures Strategy: https://www.chartfanatics.com/strategies/the-vix-futures-strategy
- Algorithmic Strategy: https://www.chartfanatics.com/strategies/algorithmic-strategy
- Futures Trading Strategy: https://www.chartfanatics.com/strategies/futures-trading-strategy
- Market DNA Strategy: https://www.chartfanatics.com/strategies/market-dna-strategy
- Trendline Strategy: https://www.chartfanatics.com/strategies/trendline-strategy
- Break & Retest: https://www.chartfanatics.com/strategies/break-retest
- Low Volume Node: https://www.chartfanatics.com/strategies/low-volume-node

Decision: no new ChartFanatics ES/NQ campaign launched.

Reasons:

- `The VIX Futures Strategy` requires same-moment intraday VIX high/low/pressure aligned to ES/NQ prior-day level behavior. Broad VIX/VVIX/term-structure families have already failed locally, and the faithful page version needs intraday VIX data not present in the current cache.
- `Futures Trading Strategy` is the Bollinger environment idea already represented by `nq_chartfanatics_daily_bollinger_environment`, which failed density.
- `Break & Retest`, `Low Volume Node`, auction/profile, liquidity, SMT/PO3, orderflow, and AOI pages map to already-tested prior-level retest, LVN/VAP, value-area, liquidity sweep, and orderflow families.
- `Market DNA` and Bookmap-heavy orderflow pages require historical depth/DOM/liquidity-wall and catalyst tape data unavailable in the current local lane.
- `Trendline Strategy` is a 4-hour swing/overnight discretionary trendline framework. It is not eligible for the current same-day no-overnight staged lane without changing the edge.
- `Algorithmic Strategy` is a process/portfolio-management page, not one testable market-behavior edge with five predeclared variants.

Fail-closed conclusion: launching another ChartFanatics campaign now would duplicate a failed local edge, require unavailable depth/intraday-VIX/overnight data, or violate the one-campaign-one-edge rule. The next campaign therefore used a non-ChartFanatics copper/growth source trail and was explicitly marked separate from ChartFanatics.
