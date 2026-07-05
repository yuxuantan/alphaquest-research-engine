# ChartFanatics ES/NQ Strategy Gate After JadeCap Campaign

Timestamp: 2026-07-01T01:20:00+08:00

Verdict: FAIL for the locally testable ChartFanatics/JadeCap campaign launched from the fresh website review. NEEDS MANUAL REVIEW for the remaining ChartFanatics source pool because the remaining untested pages are duplicate edges, incompatible with the current no-overnight staged lane, or require unavailable historical data.

## Context

- The current NQ real-yield/breakeven campaign was tested first and failed staged validation.
- The ChartFanatics strategy index was refreshed from `https://www.chartfanatics.com/strategies`.
- The remaining pages were screened for duplicate edge, data availability, and compatibility with completed-bar, no-lookahead, same-day-flatten staged testing.
- One new locally testable subset was launched after this review: `nq_chartfanatics_jadecap_session_liquidity_fvg`.

## New Campaign Launched

Campaign: `nq_chartfanatics_jadecap_session_liquidity_fvg`

Source: `https://www.chartfanatics.com/strategies/intraday-liquidity-volatility-model`

Local edge: frozen Asian/London pre-RTH session highs/lows, completed RTH sweep, then failed continuation or FVG retest rejection before next-bar NQ entry.

Reason it was allowed despite duplicate-adjacent liquidity/FVG history: this campaign used pre-RTH Asian/London session levels frozen before RTH, not RTH prior levels, rolling intraday levels, prior-session flip retests, overnight compression, or the earlier ChartFanatics liquidity-inversion FVG expression.

Outcome:

- Density gate: PASS, 45/45 declared entry rows and 5/5 variants passed.
- Preflight: PASS for all five official configs.
- Staged validation: FAIL, all five variants failed `limited_core_grid_test`.
- No variant reached limited monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

Artifacts:

- `campaigns/nq_chartfanatics_jadecap_session_liquidity_fvg/campaign.yaml`
- `backtest-campaigns/nq_chartfanatics_jadecap_session_liquidity_fvg/campaign_test_summary.json`
- `backtest-campaigns/nq_chartfanatics_jadecap_session_liquidity_fvg/campaign_results.csv`
- `research_artifacts/nq_chartfanatics_jadecap_session_liquidity_fvg_density_audit_20260701.md`

## Other ChartFanatics Pages Reviewed

The following pages did not produce a new campaign because they were already tested, duplicate the same economic edge, or require unavailable data:

- `https://www.chartfanatics.com/strategies/the-vix-futures-strategy`: intraday VIX confirmation requires aligned intraday VIX OHLC/tick data. A lagged VIX term-structure/orderflow NQ port was tested separately as `nq_vix_term_structure_orderflow_pullback` and failed limited core.
- `https://www.chartfanatics.com/strategies/market-dna-strategy`: requires historical Level II/depth, liquidity walls, passive/aggressive control shifts, and catalyst tape data not present in the local cache.
- `https://www.chartfanatics.com/strategies/nasdaq-ict-and-order-flow-scalping-strategy`: duplicates liquidity sweep, FVG/IFVG, VWAP/POC, prior-level, and Bookmap/orderflow confirmation families already tested or data-gated.
- `https://www.chartfanatics.com/strategies/order-flow-strategy` and `https://www.chartfanatics.com/strategies/orderflow-trading-masterclass`: duplicate AOI/VAP/LVN/orderflow, large-lot, delta, trapped-trader, and absorption campaigns; faithful heatmap/DOM history is unavailable.
- `https://www.chartfanatics.com/strategies/auction-market-theory-strategy`, `https://www.chartfanatics.com/strategies/auction-market-strategy`, and `https://www.chartfanatics.com/strategies/volume-profile-strategy`: duplicate value-area, POC, LVN/VAP, auction acceptance/rejection, and AOI/profile campaigns.
- `https://www.chartfanatics.com/strategies/break-retest`: duplicate of prior-session support/resistance flip-retest and opening-range retest campaigns.
- `https://www.chartfanatics.com/strategies/trendline-strategy` and `https://www.chartfanatics.com/strategies/structure-ote`: higher-timeframe swing frameworks that would require discretionary trendlines, order blocks, breakers, or multi-session holds; forcing same-day flatten would change the edge.

## Tested ChartFanatics-Derived NQ Campaigns In Tree

- `nq_20_80_price_ending_barrier`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_amd_fomc_distribution`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_daily_bollinger_environment`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_jadecap_session_liquidity_fvg`: FAIL, limited core.
- `nq_chartfanatics_liquidity_inversion_fvg`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_london_trident_fvg_continuation`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_measured_move_pullback`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_smt_po3_midpoint_reversion`: FAIL, pre-PnL density screen.
- `nq_vix_term_structure_orderflow_pullback`: FAIL, limited core.

## Reopen Conditions

- Intraday VIX OHLC/tick history aligned to ES/NQ bars for the VIX confirmation playbook.
- Historical Level II/depth/heatmap/DOM data for Market DNA and Bookmap-heavy orderflow playbooks.
- Explicit user approval to test a degraded proxy version of a data-gated page, clearly labelled as a proxy rather than the ChartFanatics strategy.
- Explicit user approval to open a higher-timeframe swing lane with overnight or multi-session exposure for trendline/OTE pages.
