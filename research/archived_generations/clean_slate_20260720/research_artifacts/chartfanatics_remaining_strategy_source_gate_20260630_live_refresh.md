# ChartFanatics Remaining Strategy Source Gate - Live Refresh

Review date: 2026-06-30

Status: FAIL for new-campaign search under the current no-duplicate-edge rule.

Scope: refreshed the live ChartFanatics strategy index after the current NQ campaign closures and checked whether any ES/NQ futures playbook could be launched as a new, nonduplicate, locally testable campaign.

Live source pages reviewed:
- Strategy index: https://www.chartfanatics.com/strategies
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

Already tested from the ChartFanatics pass:
- `nq_20_80_price_ending_barrier`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_measured_move_pullback`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_daily_bollinger_environment`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_liquidity_inversion_fvg`: FAIL at pre-PnL density screen.
- `nq_chartfanatics_smt_po3_midpoint_reversion`: FAIL at pre-PnL density screen.

Current local pass check:
- Focused scan of NQ parent and variant summaries found `pass_like_count=0`.
- Multiple NQ variants have passed `limited_core_grid_test`, but no NQ branch has a parent or variant summary with full staged PASS.
- ChartFanatics-derived campaigns did not reach staged PnL after failing density gates.

Data availability refresh:
- Local ETH/RTH Databento 1-minute caches exist for NQ and ES:
  - `data/cache/databento/nq_databento_ohlcv_1m_20100606_20260531_eth_rth_explicit_roll.parquet`
  - `data/cache/databento/es_databento_ohlcv_1m_20100606_20260531_eth_rth_explicit_roll.parquet`
- This means Asian/London OHLC session levels are not strictly data-gated anymore.
- However, launching a new Asian/London-liquidity plus FVG campaign would still be duplicate-adjacent to already rejected liquidity-sweep, FVG-inversion, prior-day stop-run, overnight-sweep/reclaim, and opening-range failed-breakout families. Under the current no-duplicate-edge instruction, changing the reference level from prior/current/overnight liquidity to Asian/London liquidity is not enough to define a new economic edge.

Remaining-page decisions:

| Page or family | Decision | Reason |
|---|---|---|
| Intraday Liquidity & Volatility | Duplicate-adjacent, not launched | The locally mechanical subset is NY-session sweep of prior/Asian/London liquidity plus FVG/MSS confirmation. Prior-RTH liquidity, current-RTH liquidity, overnight high/low sweeps, and FVG inversion have already been tested or density-rejected. Asian/London levels are a reference-level variant, not a distinct edge under the current rule. |
| Nasdaq ICT and Order Flow Scalping | Duplicate/data-gated | Bookmap/orderflow and discretionary multi-timeframe context are not available in the local OHLCV cache. The locally testable liquidity/FVG subset overlaps `nq_chartfanatics_liquidity_inversion_fvg`, `nq_prior_day_stop_run_reclaim`, and opening-range failed-breakout campaigns. |
| Order Flow Strategy / Market DNA / OrderFlow Masterclass | Duplicate/data-gated | Requires AOI, large print, absorption, delta-profile, tape, depth, or catalyst-specific orderflow. Existing ES/NQ AOI/orderflow proxies were already tested or data-gated. |
| VIX Futures Strategy | Duplicate/partial data-gate | Local repo already includes ES/NQ VIX level, term-structure, VVIX, VXN/VIX, variance-risk, VIX-pressure, and VIX-expiration families. The page's intraday VIX-versus-PDH/PDL confirmation needs intraday VIX observations, while local VIX features are prior-close daily features. |
| Futures Trading Strategy / Bollinger environment | Tested | Implemented as `nq_chartfanatics_daily_bollinger_environment`; rejected before PnL by density. |
| 80/20 Nasdaq | Tested | Implemented as `nq_20_80_price_ending_barrier`; rejected before PnL by density. |
| Measured Move Trend | Tested | Implemented as `nq_chartfanatics_measured_move_pullback`; rejected before PnL by density. |
| SMT Divergence + PO3 | Tested | Implemented as `nq_chartfanatics_smt_po3_midpoint_reversion`; rejected before PnL by density. |
| Volume Profile / Low Volume Node / Auction Market families | Duplicate | Covered by prior value-area, VAP/profile, LVN, AOI, and auction/acceptance families, including the ES video AOI/LVN orderflow campaign. |
| Structure + OTE / Liquidity Strategy / AMD Model / Break & Retest / Trendline | Duplicate or not a single mechanical edge | A local intraday version would reduce to already tested liquidity sweep/reclaim, FVG inversion, opening-range manipulation, prior-session breakout/retest, or market-structure pivot families. Swing versions require discretionary higher-timeframe POI management and overnight exposure. |
| Full Psychology MasterClass / Algorithmic Strategy / 5 Stage Trading Framework | Not a strategy edge | These are process, psychology, or broad framework pages rather than one falsifiable ES/NQ market behavior suitable for a five-variant campaign. |

Conclusion: no further ChartFanatics ES/NQ campaign was launched in this refresh. The only newly plausible data path, Asian/London session-liquidity plus FVG confirmation, is duplicate-adjacent under the current instruction. Testing it would require explicit user approval to relax the no-duplicate-edge constraint or to treat Asian/London session liquidity as a distinct edge family despite prior liquidity/FVG/overnight-sweep failures.
