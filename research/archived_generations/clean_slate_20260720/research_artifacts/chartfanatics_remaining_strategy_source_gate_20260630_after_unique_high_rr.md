# ChartFanatics Remaining Strategy Source Gate After Unique High RR

Review date: 2026-06-30

Status: FAIL for additional nonduplicate ES/NQ campaign launch under the current no-duplicate-edge rule, after testing the one newly eligible page found in the live refresh.

Live source pages reviewed:
- Strategy index: https://www.chartfanatics.com/strategies
- Unique High RR: https://www.chartfanatics.com/strategies/unique-high-rr
- Intraday Liquidity & Volatility Model: https://www.chartfanatics.com/strategies/intraday-liquidity-volatility-model
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
- SMT Divergence + PO3: https://www.chartfanatics.com/strategies/smt-divergence-po3
- Low Volume Node: https://www.chartfanatics.com/strategies/low-volume-node
- Market Auction Theory: https://www.chartfanatics.com/strategies/market-auction-theory

New campaign tested from this refresh:
- `nq_chartfanatics_london_trident_fvg_continuation`: FAIL at pre-PnL density screen. The source-defined 30-minute London FVG/trident/EMA setup produced 0/45 passing entry rows. Best full-history density was 2.7272 signals/year and latest-252 count was at most 1 signal. No PnL was inspected.

Already tested ChartFanatics-derived ES/NQ pages:
- `nq_20_80_price_ending_barrier`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_measured_move_pullback`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_daily_bollinger_environment`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_liquidity_inversion_fvg`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_smt_po3_midpoint_reversion`: FAIL at pre-PnL density screen.
- `es_video_aoi_lvn_orderflow_playbook`: FAIL across exact-video AOI/LVN/orderflow and exact-ORB branches reviewed previously.

Remaining-page decisions:

| Page or family | Decision | Reason |
|---|---|---|
| Intraday Liquidity & Volatility | Duplicate-adjacent, not launched | The locally mechanical subset is NY-session sweep of prior/Asian/London liquidity plus FVG/MSS confirmation. Existing liquidity-sweep, FVG-inversion, overnight-sweep, prior-day stop-run, and opening-range failed-breakout families already cover the economic edge. |
| Nasdaq ICT and Order Flow Scalping | Duplicate/data-gated | Bookmap/tape/depth and discretionary higher-timeframe context are unavailable locally. The OHLC-testable FVG/liquidity subset overlaps rejected ChartFanatics FVG and liquidity campaigns. |
| Order Flow Strategy / Market DNA / OrderFlow Masterclass | Duplicate/data-gated | Requires AOI, large prints, absorption, delta profile, tape, depth, or catalyst-specific orderflow; existing ES/NQ AOI/orderflow proxies were already tested or data-gated. |
| VIX Futures Strategy | Duplicate/partial data-gate | Repo already includes ES/NQ VIX level, term-structure, VVIX, VXN/VIX, variance-risk, VIX-pressure, and VIX-expiration families. Intraday VIX-versus-PDH/PDL confirmation needs reliable intraday VIX observations. |
| Futures Trading Strategy / Bollinger environment | Tested | Implemented as `nq_chartfanatics_daily_bollinger_environment`; rejected before PnL by density. |
| 80/20 Nasdaq | Tested | Implemented as `nq_20_80_price_ending_barrier`; rejected before PnL by density. |
| Measured Move Trend | Tested | Implemented as `nq_chartfanatics_measured_move_pullback`; rejected before PnL by density. |
| SMT Divergence + PO3 | Tested | Implemented as `nq_chartfanatics_smt_po3_midpoint_reversion`; rejected before PnL by density. |
| Volume Profile / Low Volume Node / Auction Market families | Duplicate | Covered by prior value-area, VAP/profile, LVN, AOI, and auction/acceptance families. |
| Structure + OTE / Liquidity Strategy / AMD Model / Break & Retest / Trendline | Duplicate or not a single mechanical edge | A local intraday subset reduces to tested liquidity sweep/reclaim, FVG inversion, opening-range manipulation, prior-session breakout/retest, or market-structure pivot families. |
| Full Psychology MasterClass / Algorithmic Strategy / 5 Stage Trading Framework | Not a strategy edge | These are process, psychology, or broad framework pages rather than one falsifiable ES/NQ market behavior suitable for a five-variant campaign. |

Conclusion: after the current campaign and the new `Unique High RR` density campaign, no further nonduplicate ChartFanatics ES/NQ campaign is eligible with current local data and the current no-duplicate-edge instruction.
