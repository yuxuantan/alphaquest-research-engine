# ChartFanatics Remaining Strategy Source Gate After NQ Manufacturing Orders

Review date: 2026-07-01

Status: FAIL for launching another ChartFanatics-derived ES/NQ campaign under the current no-duplicate-edge rule.

Trigger: after closing `nq_manufacturing_orders_state`, the live ChartFanatics search was refreshed for ES/NQ futures strategies not already represented in the local research tree.

Live pages surfaced in the refresh:
- Trader Kane's 50% Reversal Strategy: `https://www.chartfanatics.com/strategies/smt-divergence-po3`
- The Vix Futures Strategy: `https://www.chartfanatics.com/strategies/the-vix-futures-strategy`
- JadeCap Liquidity Trading Strategy: `https://www.chartfanatics.com/strategies/intraday-liquidity-volatility-model`
- Dhesi Liquidity Inversion Model: `https://www.chartfanatics.com/strategies/liquidity-inversion-model`
- Yush Order Flow Strategy: `https://www.chartfanatics.com/strategies/order-flow-strategy`
- Nasdaq ICT and Order Flow Scalping Strategy: `https://www.chartfanatics.com/strategies/nasdaq-ict-and-order-flow-scalping-strategy`
- 80/20 Nasdaq Strategy: `https://www.chartfanatics.com/strategies/80-20-nasdaq-strategy`
- AMD Model: `https://www.chartfanatics.com/strategies/amd-model`
- Volume Profile Strategy: `https://www.chartfanatics.com/strategies/volume-profile-strategy`
- Break & Retest: `https://www.chartfanatics.com/strategies/break-retest`

Duplicate and data gate decisions:

| Page or family | Decision | Reason |
|---|---|---|
| VIX Futures Strategy | Duplicate/data-gated | Local tree already includes ES/NQ VIX level, term-structure, VXN/VIX, VVIX, VIX-pressure, VIX-expiration, and variance-risk families. The ChartFanatics page's intraday VIX pressure confirmation would require intraday VIX observations; local VIX feature families use prior-close daily Cboe data. |
| SMT Divergence + PO3 | Tested | Represented by `nq_chartfanatics_smt_po3_midpoint_reversion`; rejected before PnL by density. |
| JadeCap liquidity / Dhesi liquidity inversion / ICT scalping / Break & Retest / AMD | Duplicate-adjacent | Locally testable subsets reduce to prior-session liquidity sweep/reclaim, FVG inversion, opening manipulation, market-structure retest, or prior-session breakout/retest families already tested or density-rejected. |
| 80/20 Nasdaq | Tested | Represented by `nq_20_80_price_ending_barrier`; rejected before PnL by density. |
| Order Flow / Market DNA / OrderFlow Masterclass | Duplicate/data-gated | Requires tape, depth, Bookmap-style liquidity, AOI, large-print absorption, or delta-profile semantics beyond available local NQ aggregate bars; existing orderflow proxies have already been tested or data-gated. |
| Volume Profile / LVN / Auction Market | Duplicate | Covered by prior value-area, VAP/profile, LVN, auction/acceptance, and AOI/LVN orderflow families. |

Conclusion: no additional ChartFanatics ES/NQ campaign should be launched without explicit user approval to relax the no-duplicate-edge constraint or to accept a currently data-gated intraday VIX/depth/order-book implementation.
