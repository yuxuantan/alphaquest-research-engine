# Chart Fanatics Remaining Futures Strategy Source Gate After NQ/MES Closure

Review date: 2026-06-30

Scope: refreshed Chart Fanatics futures-page review after confirming the open-tab ES video AOI/LVN orderflow branches failed, closing the `nq_mes_aligned_flow_continuation` campaign, and rechecking the no-duplicate-edge constraint.

Sources reviewed:
- Strategy index: https://www.chartfanatics.com/strategies
- Liquidity Inversion Model: https://www.chartfanatics.com/strategies/liquidity-inversion-model
- Nasdaq ICT and Order Flow Scalping Strategy: https://www.chartfanatics.com/strategies/nasdaq-ict-and-order-flow-scalping-strategy
- Order Flow Strategy: https://www.chartfanatics.com/strategies/order-flow-strategy
- 80/20 Nasdaq Strategy: https://www.chartfanatics.com/strategies/80-20-nasdaq-strategy
- Auction Market Theory Strategy: https://www.chartfanatics.com/strategies/auction-market-theory-strategy
- Measured Move Trend Strategy: https://www.chartfanatics.com/strategies/measured-move-trend-strategy
- The Vix Futures Strategy: https://www.chartfanatics.com/strategies/the-vix-futures-strategy
- Futures Trading Strategy: https://www.chartfanatics.com/strategies/futures-trading-strategy
- Volume Profile Strategy: https://www.chartfanatics.com/strategies/volume-profile-strategy
- OrderFlow Trading Masterclass: https://www.chartfanatics.com/strategies/orderflow-trading-masterclass
- Auction Market Strategy: https://www.chartfanatics.com/strategies/auction-market-strategy
- Structure + OTE: https://www.chartfanatics.com/strategies/structure-ote
- Liquidity Strategy: https://www.chartfanatics.com/strategies/liquidity-strategy
- AMD Model: https://www.chartfanatics.com/strategies/amd-model
- Trendline Strategy: https://www.chartfanatics.com/strategies/trendline-strategy
- Break & Retest: https://www.chartfanatics.com/strategies/break-retest
- SMT Divergence+PO3: https://www.chartfanatics.com/strategies/smt-divergence-po3
- Low Volume Node: https://www.chartfanatics.com/strategies/low-volume-node
- Market Auction theory: https://www.chartfanatics.com/strategies/market-auction-theory
- Intraday Liquidity & Volatility Model: https://www.chartfanatics.com/strategies/intraday-liquidity-volatility-model

Current/open-tab campaign status:
- `es_video_aoi_lvn_orderflow_playbook` run5 `video_model1_range_midpoint_two_sided_exact_3m_1500`: failed `limited_core_grid_test`; 81 combinations, 0 profitable, 0 benchmark-pass rows.
- `es_video_aoi_lvn_orderflow_playbook` run7 exact ORB30 family: failed `limited_core_grid_test`; five variants, 405 combinations, 0 profitable, 0 benchmark-pass rows.

New NQ campaign closed before this gate:
- `nq_mes_aligned_flow_continuation`: failed `limited_core_grid_test`; five variants, 270 combinations, 0 profitable, 0 benchmark-pass rows. This was not a Chart Fanatics edge; it closed the active ES-derived NQ/MES continuation branch before this website refresh.

Already tested Chart Fanatics-derived ES/NQ pages:
- `nq_20_80_price_ending_barrier`: FAIL.
- `nq_chartfanatics_measured_move_pullback`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_daily_bollinger_environment`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_liquidity_inversion_fvg`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_smt_po3_midpoint_reversion`: FAIL at pre-PnL density screen.
- `es_video_aoi_lvn_orderflow_playbook`: FAIL across exact-video AOI/LVN/orderflow and exact-ORB branches reviewed here.

Remaining-page gate decisions:

| Page or family | Decision | Reason |
|---|---|---|
| Nasdaq ICT and Order Flow Scalping | DATA-GATED / DUPLICATE | Requires discretionary higher-timeframe context, Asia session, Bookmap/order-flow/tape confirmation, and seconds-scale refinement. The locally testable RTH IFVG/liquidity subset is already covered by `nq_chartfanatics_liquidity_inversion_fvg`; AOI/orderflow portions overlap tested ES/NQ orderflow and AOI campaigns. |
| Trader Yush Order Flow Strategy | DUPLICATE | The AOI, value-area/LVN, big-trade, absorption, delta, and trapped-trader framework maps to `es_video_aoi_lvn_orderflow_playbook` and related ES orderflow/AOI campaigns already tested. |
| Intraday Liquidity & Volatility | DATA-GATED / DUPLICATE | Full rule needs Asian and London session highs/lows plus discretionary daily bias. The RTH PDH/PDL plus FVG/MSS subset overlaps prior-day stop-run, liquidity inversion, opening-range, and prior-session retest campaigns. |
| VIX Futures Strategy | DUPLICATE / PARTIAL DATA-GATE | Repo already has ES/NQ VIX level, VIX term-structure, VXN/VIX dispersion, VVIX, variance-risk-premium, and NQ VIX-pressure/orderflow campaigns. The page's intraday VIX-versus-PDH/PDL confirmation would require reliable intraday VIX observations; local VIX features are lagged prior-close daily features. |
| Anthony Crudele Futures Strategy | TESTED | Implemented as `nq_chartfanatics_daily_bollinger_environment`; rejected before PnL by density. |
| Volume Profile, Low Volume Node, Auction Market/Auction Theory | DUPLICATE | Covered by prior value-area, true VAP, LVN, AOI, profile trap, and ES video AOI/LVN orderflow campaigns. |
| Structure+OTE, Liquidity Strategy, AMD Model | DUPLICATE | Overlaps FVG inversion, liquidity sweep/reclaim, SMT+PO3, prior-session stop-run, and opening-range manipulation/reversion families. |
| Break & Retest, Trendline, Market DNA, 5 Stage Trading Framework, Unique High RR, OrderFlow Masterclass | NOT A SINGLE NONDUPLICATE EDGE | Broad frameworks or generic retest/orderflow playbooks. A testable local subset would duplicate existing prior-session breakout/retest, opening-range retest, trend/orderflow, or AOI campaigns. |

Conclusion: no additional nonduplicate ES/NQ Chart Fanatics campaign is eligible with the current local data and the current no-duplicate-edge rule. The honest next path would require new data, such as ETH/Asian/London session bars for NQ/ES, reliable intraday VIX, or Bookmap/depth/tape/seconds data, or explicit user authorization to test a deliberately duplicate-adjacent rescue.
