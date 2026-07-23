# ChartFanatics ES/NQ Strategy Gate After Weekly Stage Campaign

Timestamp: 2026-07-01T02:20:00+08:00

Verdict: FAIL for the new locally testable ChartFanatics weekly-stage campaign. NEEDS MANUAL REVIEW for the remaining ChartFanatics source pool because the remaining untested pages are duplicate edges, require unavailable historical depth/tape/catalyst data, or are incompatible with the current no-overnight staged lane.

## Context

- The ChartFanatics strategy index was refreshed from `https://www.chartfanatics.com/strategies`.
- After prior ChartFanatics-derived NQ campaigns had failed, one still-local, nonduplicate subset remained testable: Ted Zhang's Stage Analysis Strategy.
- That campaign was launched as `nq_chartfanatics_weekly_stage_breakout_bias` using prior completed weekly Stage 2 state and same-day NQ continuation/reclaim entries.

## New Campaign Launched

Campaign: `nq_chartfanatics_weekly_stage_breakout_bias`

Source: `https://www.chartfanatics.com/strategies/stage-analysis-strategy`

Local edge: prior completed weekly Stage 2 trend state, based on 10/20/30/40-week moving-average alignment and weekly structure, gating NQ same-day continuation/reclaim entries. Current incomplete week is excluded; entries use completed five-minute RTH bars and same-day flattening.

Outcome:

- Density gate: PASS, 45/45 declared entry rows and 5/5 variants passed.
- Preflight: PASS for all five official configs.
- Staged validation: FAIL, all five variants failed `limited_core_grid_test` with 0/54 benchmark-passing combinations per variant.
- No variant reached limited monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.

Artifacts:

- `campaigns/nq_chartfanatics_weekly_stage_breakout_bias/campaign.yaml`
- `backtest-campaigns/nq_chartfanatics_weekly_stage_breakout_bias/campaign_test_summary.json`
- `backtest-campaigns/nq_chartfanatics_weekly_stage_breakout_bias/limited_core_results_summary.csv`
- `research_artifacts/nq_chartfanatics_weekly_stage_breakout_bias_density_audit_20260701.md`

## Other ChartFanatics Pages Reviewed

The following pages did not produce another campaign because they were already tested, duplicate the same economic edge, require unavailable data, or would need a separate overnight/swing research lane:

- `https://www.chartfanatics.com/strategies/the-vix-futures-strategy`: intraday VIX confirmation requires aligned intraday VIX OHLC/tick data. The locally available lagged VIX term-structure/orderflow NQ port was tested as `nq_vix_term_structure_orderflow_pullback` and failed limited core.
- `https://www.chartfanatics.com/strategies/market-dna-strategy`: requires historical Level II/depth, liquidity walls, passive/aggressive control shifts, and catalyst tape data not present in the local cache.
- `https://www.chartfanatics.com/strategies/order-flow-strategy` and `https://www.chartfanatics.com/strategies/orderflow-trading-masterclass`: duplicate AOI/VAP/LVN/orderflow, large-lot, delta, trapped-trader, absorption, and stop-run campaigns; faithful heatmap/DOM history is unavailable.
- `https://www.chartfanatics.com/strategies/auction-market-theory-strategy`, `https://www.chartfanatics.com/strategies/auction-market-strategy`, `https://www.chartfanatics.com/strategies/market-auction-theory`, and `https://www.chartfanatics.com/strategies/volume-profile-strategy`: duplicate value-area, POC, LVN/VAP, auction acceptance/rejection, and prior-value retest campaigns.
- `https://www.chartfanatics.com/strategies/break-retest`: duplicate of prior-session support/resistance flip-retest and opening-range retest campaigns.
- `https://www.chartfanatics.com/strategies/trendline-strategy`: higher-timeframe swing framework requiring discretionary trendlines and multi-session holds; forcing same-day flatten would change the edge.
- `https://www.chartfanatics.com/strategies/real-simple-strategy`: stocks-only swing framework built around earnings gaps, sector strength, and stock-specific institutional accumulation; not an ES/NQ futures edge under the current request.
- `https://www.chartfanatics.com/strategies/low-volume-node`: duplicates prior LVN/profile/AOI/orderflow work already tested locally.
- `https://www.chartfanatics.com/strategies/nasdaq-ict-and-order-flow-scalping-strategy`, `https://www.chartfanatics.com/strategies/liquidity-strategy`, `https://www.chartfanatics.com/strategies/amd-model`, and `https://www.chartfanatics.com/strategies/structure-ote`: duplicate liquidity sweep, FVG/IFVG, SMT/PO3, OTE, AMD, prior-level, and discretionary order-block families already tested or data-gated.

## Tested ChartFanatics-Derived NQ Campaigns In Tree

- `nq_20_80_price_ending_barrier`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_amd_fomc_distribution`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_daily_bollinger_environment`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_jadecap_session_liquidity_fvg`: FAIL, limited core.
- `nq_chartfanatics_liquidity_inversion_fvg`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_london_trident_fvg_continuation`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_measured_move_pullback`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_smt_po3_midpoint_reversion`: FAIL, pre-PnL density screen.
- `nq_chartfanatics_weekly_stage_breakout_bias`: FAIL, limited core.
- `nq_vix_term_structure_orderflow_pullback`: FAIL, limited core.

## Reopen Conditions

- Intraday VIX OHLC/tick history aligned to ES/NQ bars for the VIX confirmation playbook.
- Historical Level II/depth/heatmap/DOM data for Market DNA and Bookmap-heavy orderflow playbooks.
- Explicit user approval to test a degraded proxy version of a data-gated page, clearly labelled as a proxy rather than the ChartFanatics strategy.
- Explicit user approval to open a higher-timeframe swing lane with overnight or multi-session exposure for trendline, OTE, or stock-style swing pages.
