# Chart Fanatics Remaining Strategy Source Gate - 2026-07-02

Status: NEEDS MANUAL REVIEW.

Scope: refreshed the live Chart Fanatics strategy index after closing
`nq_labor_market_slack_state`. The objective was to identify ES/NQ strategies
that had not already been tested and that could be reduced to one auditable
edge with exactly five predeclared variants.

Live sources reviewed:

- https://www.chartfanatics.com/strategies
- https://www.chartfanatics.com/strategies/momentum-model-performance-development
- https://www.chartfanatics.com/strategies/liquidity-inversion-model
- https://www.chartfanatics.com/strategies/stage-analysis-strategy
- https://www.chartfanatics.com/strategies/nasdaq-ict-and-order-flow-scalping-strategy
- https://www.chartfanatics.com/strategies/order-flow-strategy
- https://www.chartfanatics.com/strategies/80-20-nasdaq-strategy
- https://www.chartfanatics.com/strategies/auction-market-theory-strategy
- https://www.chartfanatics.com/strategies/measured-move-trend-strategy
- https://www.chartfanatics.com/strategies/the-vix-futures-strategy
- https://www.chartfanatics.com/strategies/algorithmic-strategy
- https://www.chartfanatics.com/strategies/futures-trading-strategy
- https://www.chartfanatics.com/strategies/volume-profile-strategy
- https://www.chartfanatics.com/strategies/universal-strategy
- https://www.chartfanatics.com/strategies/market-dna-strategy
- https://www.chartfanatics.com/strategies/orderflow-trading-masterclass
- https://www.chartfanatics.com/strategies/auction-market-strategy
- https://www.chartfanatics.com/strategies/structure-ote
- https://www.chartfanatics.com/strategies/5-stage-trading-framework
- https://www.chartfanatics.com/strategies/liquidity-strategy
- https://www.chartfanatics.com/strategies/unique-high-rr
- https://www.chartfanatics.com/strategies/amd-model
- https://www.chartfanatics.com/strategies/trendline-strategy
- https://www.chartfanatics.com/strategies/break-retest
- https://www.chartfanatics.com/strategies/smt-divergence-po3
- https://www.chartfanatics.com/strategies/low-volume-node
- https://www.chartfanatics.com/strategies/market-auction-theory
- https://www.chartfanatics.com/strategies/intraday-liquidity-volatility-model

Current campaign closed before this refresh:

- `nq_labor_market_slack_state`: FAIL at `limited_core_grid_test`. All five
  predeclared labor-market slack variants failed limited core; best branch was
  `low_employment_ratio_slack_short_1130` with 9/27 profitable combinations and
  3/27 benchmark-passing combinations. No monkey, WFA, Monte Carlo, simulated
  incubation, acceptance OOS, or candidate report was reached.

Already represented by tested Chart Fanatics-derived campaigns:

- 80/20 Nasdaq Strategy -> `nq_20_80_price_ending_barrier`, failed density.
- Measured Move Trend Strategy -> `nq_chartfanatics_measured_move_pullback`,
  failed density.
- Anthony Crudele Futures/Bollinger framework ->
  `nq_chartfanatics_daily_bollinger_environment`, failed density.
- Liquidity Inversion Model -> `nq_chartfanatics_liquidity_inversion_fvg`,
  failed density.
- SMT Divergence plus PO3 -> `nq_chartfanatics_smt_po3_midpoint_reversion`,
  failed density.
- Unique High RR / London Trident ->
  `nq_chartfanatics_london_trident_fvg_continuation`, failed density.
- JadeCap Intraday Liquidity and Volatility ->
  `nq_chartfanatics_jadecap_session_liquidity_fvg`, failed limited core.
- Auction/profile POC return-to-value -> `nq_prior_poc_orderflow_magnet`,
  failed density.
- Fixed round-number and completed aggregate orderflow confirmation ->
  `nq_round_number_orderflow_barrier`, failed limited core.
- Trader Yush AOI/LVN/orderflow material -> overlaps the active
  `es_video_aoi_lvn_orderflow_playbook` family plus prior value-area, LVN, AOI,
  absorption, and orderflow campaigns.

Fresh page decisions:

| Chart Fanatics source | Disposition | Reason |
| --- | --- | --- |
| Jeff Holden Momentum Model | NOT A TRADING EDGE | The page is a performance-development loop for diagnosing recurring mistakes. It explicitly says it is not a single entry pattern, so it cannot form one campaign edge under the five-variant rule. |
| Ted Zhang Stage Analysis | DUPLICATE / NOT LOCAL PROP-FIRM FIT | The page is a weekly swing trend framework using 10-, 20-, 30-, and 40-week moving averages. A same-day ES/NQ version would be a sibling of existing time-series momentum, moving-average trend, market-structure trend, and trend-pullback campaigns rather than a new economic edge; the source itself expects swing/position holding, which conflicts with default forced same-day flatten rules unless the edge is materially changed. |
| Universal Strategy | DUPLICATE / TOO BROAD | Liquidity catalyst, displacement, retracement, FVG, support/resistance, and trendline retest components overlap existing liquidity sweep, FVG inversion, break/retest, prior-level stop-run, and structure-retest campaigns. |
| Trendline Strategy | DUPLICATE / TOO DISCRETIONARY | Manual 4-hour action/safety lines reduce locally to generic support/resistance or trendline break/bounce mechanics already represented by break/retest, support/resistance, trend, and market-structure campaigns. |
| Break and Retest | DUPLICATE | Prior-day high/low, premarket level, clean break, retest, and confirmation candle mechanics overlap existing ES/NQ prior-session breakout/retest and opening-range retest families. |
| VIX Futures Strategy | DUPLICATE / DATA-GATED | Existing repo families cover VIX level, term structure, VXN/VIX dispersion, VVIX, variance-risk-premium, VIX-expiration, and NQ VIX-pressure/orderflow. The page's intraday VIX confirmation requires reliable intraday VIX observations beyond current lagged daily feature caches. |
| Auction Market, Volume Profile, Low Volume Node, Market Auction Theory | DUPLICATE | Covered by POC magnet, prior value-area acceptance, true VAP, LVN, AOI/LVN orderflow, and profile trap families. |
| Nasdaq ICT, Intraday Liquidity and Volatility, Liquidity Strategy, AMD, Structure + OTE | DUPLICATE / DATA-GATED | Locally testable subsets overlap FVG inversion, session-liquidity/FVG, prior-level stop-run, ORB, and SMT/PO3 campaigns. Full source mechanics require ETH/Asian/London context, discretionary POIs, Bookmap/depth/tape, or seconds-scale entries. |
| Market DNA and Order Flow Masterclass | DATA-GATED / DUPLICATE | Requires tape/depth/passive-liquidity behavior and overlaps existing aggregate orderflow, absorption, AOI, trapped-trader, and large-print campaigns where local data is available. |
| Algorithmic Strategy and 5 Stage Trading Framework | NOT A SINGLE EDGE | These are system-development or trader-development frameworks, not a concrete ES/NQ signal family. |
| Stock/options/forex-specific pages | OUT OF SCOPE | Small-cap short, parabolic short, first red day, episodic pivot, options support/resistance, forex PO3/ADR, and psychology pages do not define a fresh ES/NQ futures edge under current constraints. |

Conclusion:

No additional Chart Fanatics ES/NQ campaign is eligible on 2026-07-02 without
violating the no-duplicate-edge rule, changing the source mechanics into a new
edge, or requiring unavailable ETH/session/depth/tape/intraday-VIX data. No new
Chart Fanatics campaign was launched from this refresh.
