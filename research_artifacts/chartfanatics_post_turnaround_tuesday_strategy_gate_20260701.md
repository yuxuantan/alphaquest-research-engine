# ChartFanatics source gate after Turnaround Tuesday rejection

Generated: 2026-07-01

Scope: refreshed the live ChartFanatics futures strategy index after `nq_turnaround_tuesday_reversal` failed the pre-PnL density screen.

Reviewed pages:

- Trading Strategies index: https://www.chartfanatics.com/strategies
- Order Flow Strategy: https://www.chartfanatics.com/strategies/order-flow-strategy
- Auction Market Theory Strategy: https://www.chartfanatics.com/strategies/auction-market-theory-strategy
- Algorithmic Strategy: https://www.chartfanatics.com/strategies/algorithmic-strategy
- Unique High RR: https://www.chartfanatics.com/strategies/unique-high-rr
- Trendline Strategy: https://www.chartfanatics.com/strategies/trendline-strategy
- 5 Stage Trading Framework: https://www.chartfanatics.com/strategies/5-stage-trading-framework
- Market DNA Strategy: https://www.chartfanatics.com/strategies/market-dna-strategy
- OrderFlow Trading Masterclass: https://www.chartfanatics.com/strategies/orderflow-trading-masterclass

Decision: no new ChartFanatics ES/NQ campaign launched.

Reasons:

- `Order Flow Strategy`, `Auction Market Theory Strategy`, `Market DNA Strategy`, and `OrderFlow Trading Masterclass` reduce locally to AOI/value-area/LVN, big-trade, absorption, trapped-trader, failed-auction, or acceptance mechanics. Those are already covered by the ES video AOI/LVN orderflow playbook and prior ES/NQ value-area, LVN, auction, orderflow, opening-range, and prior-level campaigns.
- `Unique High RR` is the London-session Trident/FVG idea; the local NQ subset was already represented by `nq_chartfanatics_london_trident_fvg_continuation` and failed density.
- `Trendline Strategy` is a 4-hour swing/overnight discretionary trendline playbook. It is not eligible for the current same-day no-overnight staged lane without changing the edge.
- `Algorithmic Strategy` and `5 Stage Trading Framework` are process/portfolio/playbook-management pages, not one testable market-behavior edge with five predeclared variants.
- Remaining visible futures pages were previously gated after the weekly-stage, 52-week-anchor, MAX, and other ChartFanatics-derived campaign failures.

Fail-closed conclusion: launching another ChartFanatics campaign now would duplicate a failed local edge, require unavailable depth/tape/Bookmap or overnight/swing data, or violate the one-campaign-one-edge rule.
