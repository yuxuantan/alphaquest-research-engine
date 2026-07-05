# ChartFanatics Remaining Strategy Source Gate After NQ Jobless Claims

Review date: 2026-07-01

Status: FAIL for launching another ChartFanatics-derived ES/NQ campaign under the current no-duplicate-edge and data-availability rules.

Trigger: after closing `nq_jobless_claims_state`, the live ChartFanatics search was refreshed for ES/NQ futures strategies not already represented in the local research tree.

Live pages surfaced in the refresh:
- Trading Strategies index: `https://www.chartfanatics.com/strategies`
- VIX Futures Strategy: `https://www.chartfanatics.com/strategies/the-vix-futures-strategy`
- Trader Kane SMT + PO3: `https://www.chartfanatics.com/strategies/smt-divergence-po3`
- 80/20 Nasdaq Strategy: `https://www.chartfanatics.com/strategies/80-20-nasdaq-strategy`
- Anthony Crudele Futures Trend Trading Strategy: `https://www.chartfanatics.com/strategies/futures-trading-strategy`
- Market DNA Playbook: `https://www.chartfanatics.com/strategies/market-dna-strategy`
- Order Flow Masterclass: `https://www.chartfanatics.com/strategies/orderflow-trading-masterclass`
- Yush Order Flow Strategy: `https://www.chartfanatics.com/strategies/order-flow-strategy`
- Nasdaq ICT and Order Flow Scalping Strategy: `https://www.chartfanatics.com/strategies/nasdaq-ict-and-order-flow-scalping-strategy`
- Tanja AMD Model: `https://www.chartfanatics.com/strategies/amd-model`
- Universal Strategy: `https://www.chartfanatics.com/strategies/universal-strategy`
- JadeCap Intraday Liquidity and Volatility Model: `https://www.chartfanatics.com/strategies/intraday-liquidity-volatility-model`
- Auction Market Strategy: `https://www.chartfanatics.com/strategies/auction-market-strategy`
- Market Auction Theory: `https://www.chartfanatics.com/strategies/market-auction-theory`
- Low Volume Node: `https://www.chartfanatics.com/strategies/low-volume-node`
- Volume Profile Strategy: `https://www.chartfanatics.com/strategies/volume-profile-strategy`
- Measured Move Trend Strategy: `https://www.chartfanatics.com/strategies/measured-move-trend-strategy`

Duplicate and data gate decisions:

| Page or family | Decision | Reason |
|---|---|---|
| VIX Futures Strategy | Duplicate/data-gated | The local tree already includes ES/NQ VIX level, VIX term-structure, VXN/VIX, VVIX, VIX pressure, VIX expiration, and variance-risk families. The ChartFanatics intraday VIX-pressure confirmation would require intraday VIX observations, while local VIX features are daily or prior-close. |
| SMT Divergence + PO3 | Tested | Represented by `nq_chartfanatics_smt_po3_midpoint_reversion`; rejected before PnL by density. |
| 80/20 Nasdaq | Tested | Represented by `nq_20_80_price_ending_barrier`; rejected before PnL by density. |
| AMD / JadeCap liquidity / liquidity inversion / ICT scalping / Universal liquidity reaction | Tested or duplicate-adjacent | Local testable subsets reduce to prior-session liquidity sweep/reclaim, FVG inversion, opening manipulation, market-structure retest, prior-session breakout/retest, or session-liquidity families already tested or density-rejected. |
| Market DNA / Yush Order Flow / Order Flow Masterclass | Duplicate/data-gated | The live playbooks rely on DOM, heatmap, depth, tape, AOI, large-print absorption, trapped traders, or delta-profile semantics. Available local data supports only aggregate bar/orderflow proxies, and those proxy families have already been tested or data-gated. |
| Auction Market / Market Auction Theory / LVN / Volume Profile | Duplicate | Covered by prior value-area, VAP/profile, LVN, POC magnet, auction/acceptance, and AOI/LVN orderflow families. |
| Anthony Crudele Futures Trend Trading / Measured Move Trend | Duplicate | Local implementations already cover trend-filtered pullback/continuation, opening-range breakout, compression breakout, and measured-move pullback families, including `nq_chartfanatics_measured_move_pullback`. |

Conclusion: no additional ChartFanatics ES/NQ campaign should be launched without explicit user approval to relax the no-duplicate-edge constraint or to accept a currently data-gated intraday VIX/depth/order-book implementation.
