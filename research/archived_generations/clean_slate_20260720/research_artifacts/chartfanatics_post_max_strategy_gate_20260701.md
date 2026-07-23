# ChartFanatics ES/NQ Strategy Gate After MAX Daily-Return Failure

Generated: 2026-07-01T02:35:23+08:00

Verdict: NEEDS MANUAL REVIEW / no additional ChartFanatics campaign launched.

## Reviewed Sources

- ChartFanatics strategy index: https://www.chartfanatics.com/strategies
- VIX Futures Strategy: https://www.chartfanatics.com/strategies/the-vix-futures-strategy
- Volume Profile Strategy: https://www.chartfanatics.com/strategies/volume-profile-strategy
- Low Volume Node: https://www.chartfanatics.com/strategies/low-volume-node
- Auction Market Strategy: https://www.chartfanatics.com/strategies/auction-market-strategy
- Futures Trading Strategy: https://www.chartfanatics.com/strategies/futures-trading-strategy
- Market DNA Strategy: https://www.chartfanatics.com/strategies/market-dna-strategy
- Nasdaq ICT and Order Flow Scalping: https://www.chartfanatics.com/strategies/nasdaq-ict-and-order-flow-scalping-strategy

## Duplicate / Data Gate

- VIX pressure / prior-day high-low confirmation overlaps local NQ VIX level, VIX pressure/orderflow, VIX term-structure, VVIX, and VIX-expiration campaigns. Several have already failed staged gates.
- Daily Bollinger regime / Crudele futures framework overlaps `nq_chartfanatics_daily_bollinger_environment` and related daily regime campaigns.
- Volume Profile, LVN, Auction Market Theory, and prior POC retest overlap prior POC, prior value area, prior LVN, VAP/profile AOI, and the ES video LVN orderflow playbook. A fresh campaign would duplicate an already tested profile/orderflow edge unless a materially different data object is introduced.
- Market DNA and Nasdaq ICT/order-flow scalping require discretionary catalysts, Bookmap/depth, or live tape/heatmap evidence that is not available in the local historical NQ cache.
- Algorithmic Strategy is process guidance rather than a single testable market edge.

## Decision

No new ChartFanatics campaign is launched from this refresh. Launching another VIX/profile/LVN/Auction/ICT campaign from these pages would duplicate existing failed local edges or require unavailable historical data. Continue the broader NQ search using a source-backed, nonduplicate edge.
