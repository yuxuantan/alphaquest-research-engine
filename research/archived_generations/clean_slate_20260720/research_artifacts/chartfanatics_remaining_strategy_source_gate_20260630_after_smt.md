# Chart Fanatics Remaining Futures Strategy Source Gate

Review date: 2026-06-30

Scope: refreshed Chart Fanatics futures-page review after closing the current NQ campaign, the Liquidity Inversion FVG campaign, and the SMT+PO3 midpoint-reversion campaign.

Sources reviewed:
- Strategy index: https://www.chartfanatics.com/strategies
- Liquidity Inversion Model: https://www.chartfanatics.com/strategies/liquidity-inversion-model
- SMT Divergence+PO3: https://www.chartfanatics.com/strategies/smt-divergence-po3
- Intraday Liquidity & Volatility Model: https://www.chartfanatics.com/strategies/intraday-liquidity-volatility-model
- Nasdaq ICT and Order Flow Scalping Strategy: https://www.chartfanatics.com/strategies/nasdaq-ict-and-order-flow-scalping-strategy
- Order Flow Strategy: https://www.chartfanatics.com/strategies/order-flow-strategy
- Futures Trading Strategy: https://www.chartfanatics.com/strategies/futures-trading-strategy
- The Vix Futures Strategy: https://www.chartfanatics.com/strategies/the-vix-futures-strategy

New campaigns tested from the refreshed review:
- `nq_chartfanatics_liquidity_inversion_fvg`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_smt_po3_midpoint_reversion`: FAIL at pre-PnL density screen.

Already tested Chart Fanatics-derived NQ pages:
- `nq_20_80_price_ending_barrier`: FAIL.
- `nq_chartfanatics_measured_move_pullback`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_daily_bollinger_environment`: FAIL at pre-PnL density screen.

Remaining-page gate decisions:

| Page or family | Decision | Reason |
|---|---|---|
| Nasdaq ICT and Order Flow Scalping | DATA-GATED / DUPLICATE | Requires discretionary higher-timeframe context, Asia session, Bookmap/order-flow/tape confirmation, and seconds-scale refinement. The local testable RTH IFVG/liquidity portion is already covered by `nq_chartfanatics_liquidity_inversion_fvg`; the orderflow/AOI portion overlaps existing ES/NQ orderflow and AOI campaigns. |
| Trader Yush Order Flow Strategy | DUPLICATE | The AOI, value-area/LVN, big-trade, absorption, delta, and trapped-trader framework maps directly to `es_video_aoi_lvn_orderflow_playbook` and related ES orderflow/AOI campaigns already tested. |
| Intraday Liquidity & Volatility | DATA-GATED / DUPLICATE | Full rule needs Asian and London session highs/lows plus daily discretionary bias. The RTH PDH/PDL plus FVG/MSS subset overlaps prior-day stop-run, liquidity inversion, opening-range, and prior-session retest campaigns. |
| VIX Futures Strategy | DUPLICATE / PARTIAL DATA-GATE | Local repo already has ES/NQ VIX level, VIX term-structure, VXN/VIX dispersion, VVIX, variance-risk-premium, and NQ VIX-pressure/orderflow campaigns. The page's intraday VIX-versus-PDH/PDL confirmation would require reliable intraday VIX observations; cached local VIX features are lagged prior-close daily features. |
| Anthony Crudele Futures Strategy | TESTED | Implemented as `nq_chartfanatics_daily_bollinger_environment`; rejected before PnL by density. |
| Volume Profile, Low Volume Node, Auction Market/Auction Theory | DUPLICATE | Covered by prior value-area, true VAP, LVN, AOI, profile trap, and ES video AOI/LVN orderflow campaigns. |
| Structure+OTE, Liquidity Strategy, AMD Model | DUPLICATE | Overlaps FVG inversion, liquidity sweep/reclaim, SMT+PO3, prior-session stop-run, and opening-range manipulation/reversion families. |
| Break & Retest, Trendline, Market DNA, 5 Stage Trading Framework, Unique High RR, OrderFlow Masterclass | NOT A SINGLE NONDUPLICATE EDGE | These are broad frameworks or generic retest/orderflow playbooks. A testable local subset would duplicate existing prior-session breakout/retest, opening-range retest, trend/orderflow, or AOI campaigns. |

Conclusion: no additional nonduplicate ES/NQ Chart Fanatics campaign is eligible with the current local data and the current no-duplicate-edge rule. The next honest path would require new data, such as ETH/Asian/London session bars for NQ/ES, reliable intraday VIX, or Bookmap/depth/tape/seconds data, or explicit user authorization to test a deliberately narrower duplicate-adjacent rescue.
