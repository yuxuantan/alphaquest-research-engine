# ChartFanatics ES/NQ Strategy Gate After 52-Week Anchor Campaign

Timestamp: 2026-07-01T02:20:31+08:00

Verdict: NEEDS MANUAL REVIEW for the remaining ChartFanatics ES/NQ source pool. No new campaign was launched because the refreshed website check found no nonduplicate, locally testable ES/NQ edge after `nq_52week_anchor_momentum` failed limited core.

## Current Campaign Closure

Campaign: `nq_52week_anchor_momentum`

Outcome: FAIL.

All five frozen NQ 52-week-anchor variants passed density and preflight, then failed `limited_core_grid_test` in valid `run2` evidence. Every variant had 0 benchmark-passing combinations; no variant reached limited monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

Artifacts:

- `backtest-campaigns/nq_52week_anchor_momentum/campaign_test_summary.json`
- `backtest-campaigns/nq_52week_anchor_momentum/limited_core_results_summary.csv`
- `campaigns/nq_52week_anchor_momentum/methodology_audit.md`

## Live ChartFanatics Refresh

Refreshed source index: `https://www.chartfanatics.com/strategies`

The current index includes ES/NQ-relevant futures pages such as VIX Futures, Futures Trading Strategy, Unique High RR, Intraday Liquidity & Volatility, Liquidity Inversion, Nasdaq ICT/order-flow scalping, Order Flow Strategy, Market DNA, Auction Market Theory/Strategy, Volume Profile, Low Volume Node, AMD, Liquidity Strategy, SMT+PO3, Break & Retest, Structure+OTE, Trendline, 80/20 Nasdaq, Measured Move, Stage Analysis, Algorithmic Strategy, and 5 Stage Trading Framework.

## Not Launched

| Page or family | Current decision | Local evidence |
|---|---|---|
| Futures Trading Strategy / Bollinger environment | Already tested | Implemented as `nq_chartfanatics_daily_bollinger_environment`; rejected before PnL by density. The live page describes a daily Bollinger Band environment framework with 1-5 day swing holds, daily primary timeframe, and optional lower-timeframe execution. |
| Unique High RR / London Trident FVG | Already tested | Implemented as `nq_chartfanatics_london_trident_fvg_continuation`; rejected before PnL by density. The live page requires London 03:00-06:30 ET, 30-minute FVG, EMA stack, Trident doji/confirmation, and daily trend management. |
| Stage Analysis Strategy | Already tested | Implemented as `nq_chartfanatics_weekly_stage_breakout_bias`; failed limited core. |
| 80/20 Nasdaq | Already tested | Implemented as `nq_20_80_price_ending_barrier`; rejected before PnL by density. |
| Measured Move Trend | Already tested | Implemented as `nq_chartfanatics_measured_move_pullback`; rejected before PnL by density. |
| Liquidity Inversion / SMT+PO3 / AMD / JadeCap Intraday Liquidity | Already tested or duplicate-adjacent | Covered by `nq_chartfanatics_liquidity_inversion_fvg`, `nq_chartfanatics_smt_po3_midpoint_reversion`, `nq_chartfanatics_amd_fomc_distribution`, and `nq_chartfanatics_jadecap_session_liquidity_fvg`, plus prior liquidity-sweep/reclaim and opening-range families. |
| VIX Futures Strategy | Data-gated / duplicate-adjacent | Faithful test requires intraday VIX observations aligned to ES/NQ PDH/PDL events. Local lagged VIX/term-structure proxies have already failed or are not the same live-confirmation edge. |
| Order Flow Strategy / OrderFlow Masterclass / Market DNA | Data-gated / duplicate | Faithful versions require historical depth, tape, large-print, absorption, delta-profile, heatmap/DOM, or catalyst context. Local AOI/orderflow proxies and ES/NQ orderflow families have already been tested or data-gated. |
| Auction Market Theory / Auction Market Strategy / Volume Profile / Low Volume Node | Duplicate | Covered by prior value-area, POC, LVN, VAP/profile, AOI, auction acceptance/rejection, and ES video AOI/LVN orderflow campaigns. |
| Break & Retest / Structure+OTE / Trendline | Duplicate or incompatible lane | Same-day local reductions duplicate prior-session breakout/retest, stop-run, FVG, and market-structure pivot families. Swing versions require discretionary higher-timeframe POI management and overnight exposure. |
| Algorithmic Strategy | Not a single edge | The page is a strategy-generation, robustness-testing, and portfolio-management process, not one falsifiable ES/NQ market behavior suitable for exactly five variants. |
| 5 Stage Trading Framework | Not a strategy edge | The page is trader-development/process guidance, not a mechanical ES/NQ edge. |

## Reopen Conditions

- Reliable intraday VIX OHLC/tick history aligned to ES/NQ bars for the VIX confirmation playbook.
- Historical Level II/depth/heatmap/DOM and large-print tape for Market DNA and order-flow masterclass playbooks.
- Explicit approval to relax `no duplicated edge` and test a deliberately duplicate-adjacent ChartFanatics subset.
- Explicit approval to open a swing/overnight research lane for ChartFanatics pages that require multi-day holds or options-on-futures risk.

Conclusion: no additional ChartFanatics campaign can be honestly launched under the current no-duplicate-edge rule and local data constraints.
