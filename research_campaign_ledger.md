# ES Strategy Research Campaign Ledger

Created: 2026-06-05

## Repository Audit

- Project structure: Python package under `src/propstack`, campaign YAMLs under `configs/campaigns`, ES roll data under `configs/data/ES`, raw/cache market data under `data/raw` and `data/cache`, generated evidence under `data/reports/campaigns`, tests under `tests`.
- Existing strategy shell: `propstack.strategy.modular.ModularStrategy` composes one entry module, one stop module, and one target module.
- Existing entry modules: `opening_range_breakout`, `opening_range_inverse_breakout`, `pdh_pdl_sweep_reclaim`, `intraday_capitulation_mr`.
- Existing stop modules: `sweep_extreme`, `opening_range_edge`, `opening_range_width`, `percent_from_entry`.
- Existing target modules: `fixed_r`, `cost_adjusted_fixed_r`, `opening_range_extension`, `opening_range_opposite_edge`, `percent_from_entry`.
- YAML schema: top-level `campaign_id`, `variant_id`, `strategy_name`, `symbol`, `dataset_id`, `timeframe`, `data`, `strategy`, `core`, `benchmarks`, `core_grid`, `monkey`, `wfa`, `prop_rules`, `monte_carlo`; report root is computed from campaign, symbol, dataset, timeframe, and variant by current code.
- Test framework: `pytest`, configured in `pyproject.toml` with `pythonpath = ["src"]`.
- End-to-end campaign script: `PYTHONPATH=src python3 -m propstack.run_campaign_stages --config PATH --skip-validation`.
- Acceptance criteria: staged runner defaults in `src/propstack/research/campaign_stages.py`. A pass requires limited core grid >=100 combinations and >=70% profitable iterations, monkey beat rates, WFA no early exit with >=10 windows and stitched OOS PF >=1.5, MAR >=1.5, expectancy R >=0.2, total trades >=500, win rate >=0.45, WFA OOS Monte Carlo probability profit before drawdown >=0.50, simulated incubation core PF >=1.2, MAR >=1.2, expectancy R >=0.15, total trades >=75, win rate >=0.40, and incubation monkey beat rates >=0.80.
- Data assumptions: ES Databento DBN 1-minute source, explicit roll calendar `configs/data/ES/motivewave_rithmic_roll_calendar.csv`, no price adjustment, spreads excluded, America/New_York timestamps, RTH/ETH sessions from config, roll-boundary reset of previous-day levels, warmup days before requested subset.
- Execution assumptions: signals are evaluated on bar close and entered next bar open; ES tick size 0.25 and tick value 12.50; commission and slippage come from YAML and must not be reduced to force a pass.
- Same-bar ambiguity: engine resolves stop/target conflicts with 1-minute detail data on higher-timeframe runs where available; otherwise fallback is conservative stop-first.
- Prop-rule assumptions: `PropRules` tracks starting balance, daily loss limit, trailing drawdown, max contracts, best-day concentration, min trading days, payout threshold, profit target percent, and drawdown limit percent.

## Prior Campaigns Found

| Campaign | Variant | Timeframe | Config | Result Path | Status | Main Failure Reason |
| --- | --- | --- | --- | --- | --- | --- |
| five_min_orb_vol_filter | baseline | 1m | `configs/campaigns/five_min_orb_vol_filter/variants/ES/1m/baseline.yaml` | `data/reports/campaigns/five_min_orb_vol_filter/ES/1m_full_history/baseline` | rejected | Core was positive but grid had 0% profitable iterations; WFA profitable window rate 16.7%; Monte Carlo probability profit before drawdown 27%. |
| five_min_orb_vol_filter | inverse | 1m | `configs/campaigns/five_min_orb_vol_filter/variants/ES/1m/inverse.yaml` | `data/reports/campaigns/five_min_orb_vol_filter/ES/1m_full_history/inverse` | rejected | Core net profit negative and grid had 0% profitable iterations. |
| five_min_orb_vol_filter | fixed_rr_cost_adjusted | 1m | `configs/campaigns/five_min_orb_vol_filter/variants/ES/1m/fixed_rr_cost_adjusted.yaml` | `data/reports/campaigns/five_min_orb_vol_filter/ES/1m_full_history/fixed_rr_cost_adjusted` | rejected | Core PF 1.11 and drawdown 11.8%; WFA profitable window rate 50%, below staged robustness criteria. |
| pdh_pdl_sweep | baseline | 1m | `configs/campaigns/pdh_pdl_sweep/variants/ES/1m/baseline.yaml` | `data/reports/campaigns/pdh_pdl_sweep/ES/1m_full_history/baseline` | rejected/incomplete | Existing core report only; campaign edge overlaps with prior-day sweep-reclaim already tested. |
| pdh_pdl_sweep | core_grid_rescue | 1m | `configs/campaigns/pdh_pdl_sweep/variants/ES/1m/core_grid_rescue.yaml` | `data/reports/campaigns/pdh_pdl_sweep/ES/1m_full_history/core_grid_rescue` | rejected | Core net profit negative, grid had 0% profitable iterations, monkey beat rates about 4.4%-4.6%. |
| intraday_capitulation_mr | baseline | 15m | `configs/campaigns/intraday_capitulation_mr/variants/ES/15m/baseline.yaml` | `data/reports/campaigns/intraday_capitulation_mr/ES/1m_full_history/baseline` | rejected/incomplete | Core net profit negative with PF 0.77, expectancy R -0.148, drawdown 24.2%. |

## Search Budget

- Maximum new campaigns: 5.
- Variants per campaign: exactly 3.
- Timeframes per variant: exactly 3.
- New variant-timeframe configs per campaign: 9.
- Tunable parameters per config: maximum 2 entry, 1 TP, 1 SL, maximum 4 total.

## New Campaign 1 Plan

- Campaign: `overnight_inventory_reversion`
- Edge thesis: ES RTH opens or early drives that extend beyond overnight inventory extremes can become failed auctions when price reclaims the overnight range; the strategy fades the failed extension back toward the range/session balance.
- Research/rationale: market-structure reasoning. No external citation is claimed.
- Why ES: ES has deep overnight participation, visible RTH liquidity reset at 09:30 ET, and frequent overnight high/low reference behavior.
- Regime expected to work: balanced or mean-reverting sessions where overnight extremes act as liquidity pools and failed early auctions rotate inward.
- Regime expected to fail: strong trend days, macro/news breakouts, or persistent opening drives that hold outside overnight range.
- Variants:
  - `on_extreme_reclaim_fixed_r`: trade a reclaim of overnight high/low after an RTH sweep outside the overnight range.
  - `on_extreme_reclaim_vwap_filter`: same failed-auction entry, requiring reclaim relative to session VWAP to avoid fading strong one-way auctions.
  - `on_midpoint_reversion_confirmed`: enter only after reclaiming deeper into the overnight range, using the overnight midpoint as confirmation context.
- Timeframes:
  - Fast reclaim variants: 1m, 2m, 5m for tight auction timing and enough trade count.
  - Midpoint confirmation variant: 2m, 5m, 10m for less noise and cleaner confirmation bars.

## New Campaign 2 Plan

- Campaign: `vwap_pullback_continuation`
- Edge thesis: After ES establishes an RTH directional bias, a controlled pullback into session VWAP that rejects and closes back in trend direction can offer continuation with defined invalidation at the pullback extreme.
- Research/rationale: market-structure reasoning. No external citation is claimed.
- Why ES: ES has deep intraday liquidity and VWAP is a common institutional benchmark; trend days often respect VWAP or quickly reclaim it after shallow pullbacks.
- Regime expected to work: directional RTH sessions with orderly pullbacks and sustained participation.
- Regime expected to fail: balanced/choppy sessions, VWAP chop, news reversals, and late-day mean reversion.
- Variants:
  - `opening_drive_vwap_pullback`: require an opening-drive bias before taking the first VWAP pullback continuation.
  - `vwap_reclaim_trend_continuation`: require a sequence of closes on the trend side of VWAP, then a pullback and reclaim.
  - `failed_vwap_break_continuation`: require an intrabar break through VWAP that fails by the close, expressing trapped countertrend traders.
- Timeframes:
  - Opening-drive variant: 1m, 2m, 5m for enough entries while preserving early-session timing.
  - Reclaim/trapped-countertrend variants: 2m, 5m, 10m to reduce VWAP noise and same-bar churn.

## New Campaign 3 Plan

- Campaign: `pdh_pdl_breakout_continuation`
- Edge thesis: A fresh break and hold beyond the prior RTH high/low can indicate range expansion and continuation participation, unlike the already rejected sweep-reclaim fade of the same levels.
- Research/rationale: market-structure reasoning. No external citation is claimed.
- Why ES: Prior-session highs/lows are widely watched references in ES, and successful acceptance beyond them can attract breakout and stop-driven continuation flow.
- Regime expected to work: directional range-expansion days, gap-and-go sessions, and sessions where prior-day extremes convert into support/resistance.
- Regime expected to fail: false breakouts, balanced sessions, low-volume lunch chop, and immediate reversion back into the prior range.
- Variants:
  - `fresh_close_break`: trade the first fresh RTH close through the prior RTH high/low.
  - `break_retest_hold`: require a close through the level, then a retest that holds the broken level.
  - `gap_hold_continuation`: require an RTH gap beyond the prior RTH high/low and sustained closes outside the level.
- Timeframes:
  - Fresh close break: 1m, 2m, 5m to capture initial acceptance quickly.
  - Break-retest hold: 2m, 5m, 10m to reduce noise around the retest.
  - Gap-hold continuation: 1m, 2m, 5m to keep enough early-session observations.

## New Campaign 4 Plan

- Campaign: `rth_gap_fade`
- Edge thesis: ES RTH gaps away from the prior RTH close can overextend early and partially or fully mean-revert toward the prior close when the opening impulse fails.
- Research/rationale: market-structure reasoning. No external citation is claimed.
- Why ES: ES has a liquid overnight session and a visible RTH liquidity reset; prior RTH close is a common reference for gap-fill behavior.
- Regime expected to work: non-news gaps, overnight inventory imbalance that fades after RTH liquidity enters, and early failed directional auctions.
- Regime expected to fail: strong gap-and-go trend days, major macro/news sessions, and days where the prior close is no longer a relevant magnet.
- Variants:
  - `open_reversal`: fade when a gap bar closes back against the gap open.
  - `extension_reject`: fade only after price extends farther from the prior close and then rejects back toward the gap open.
  - `vwap_reclaim`: fade when price reclaims session VWAP against the opening gap.
- Timeframes:
  - All variants: 1m, 2m, 5m to test early gap behavior with enough observations while reducing noise on coarser bars.

## New Campaign 5 Plan

- Campaign: `opening_range_filtered_breakout`
- Edge thesis: ES opening-range breaks may become more robust when the break is confirmed by current-bar participation and VWAP context, while failed breaks stretched away from VWAP may express a distinct early range-fade edge.
- Research/rationale: market-structure reasoning. No external citation is claimed.
- Why ES: ES has deep RTH liquidity and the opening range is a commonly watched early-session reference; successful acceptance or failed acceptance around that range can attract systematic participation.
- Regime expected to work: active RTH openings with clear early auction acceptance, volume-confirmed initiative flow, or overextended failed range breaks.
- Regime expected to fail: low-volume chop, news whipsaws, days where the opening range is too wide to offer clean risk, and trend days for the inverse-fade variant.
- Variants:
  - `volume_confirmed_extension`: continuation breaks with minimum same-bar volume ratio and opening-range extension targets.
  - `vwap_aligned_fixed_r`: continuation breaks requiring trade-side VWAP alignment and cost-adjusted fixed-R targets.
  - `failed_break_fade`: inverse/fade entries after breaks stretched on the breakout side of VWAP, targeting a return through the range.
- Timeframes:
  - All variants: 1m, 2m, 5m, preserving a clean 3-by-3 comparison and testing whether a slightly slower opening-range signal reduces noise without under-sampling.

## Attempt Log

| Campaign | Variant | Timeframe | Config | Result Path | Pass/Fail | Main Failure Reason |
| --- | --- | --- | --- | --- | --- | --- |
| overnight_inventory_reversion | on_extreme_reclaim_fixed_r | 1m | `configs/campaigns/overnight_inventory_reversion/variants/ES/1m/on_extreme_reclaim_fixed_r.yaml` | `data/reports/campaigns/overnight_inventory_reversion/ES/1m_full_history/1m/on_extreme_reclaim_fixed_r/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -28,937.50, best PF 0.71. Failure type: performance-related. Edge expression should not be revisited on 1m without a materially different thesis. |
| overnight_inventory_reversion | on_extreme_reclaim_fixed_r | 2m | `configs/campaigns/overnight_inventory_reversion/variants/ES/2m/on_extreme_reclaim_fixed_r.yaml` | `data/reports/campaigns/overnight_inventory_reversion/ES/1m_full_history/2m/on_extreme_reclaim_fixed_r/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -27,822.50, best PF 0.68. Failure type: performance-related. |
| overnight_inventory_reversion | on_extreme_reclaim_fixed_r | 5m | `configs/campaigns/overnight_inventory_reversion/variants/ES/5m/on_extreme_reclaim_fixed_r.yaml` | `data/reports/campaigns/overnight_inventory_reversion/ES/1m_full_history/5m/on_extreme_reclaim_fixed_r/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 2 profitable iterations (1.85%), best net profit 270.00, PF 1.00, max DD 12.1%, max consecutive losses 14. Failure type: performance/robustness-related. Abandon this variant mechanic. |
| overnight_inventory_reversion | on_extreme_reclaim_vwap_filter | 1m | `configs/campaigns/overnight_inventory_reversion/variants/ES/1m/on_extreme_reclaim_vwap_filter.yaml` | `data/reports/campaigns/overnight_inventory_reversion/ES/1m_full_history/1m/on_extreme_reclaim_vwap_filter/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -26,670.00, best PF 0.70. Failure type: performance-related. |
| overnight_inventory_reversion | on_extreme_reclaim_vwap_filter | 2m | `configs/campaigns/overnight_inventory_reversion/variants/ES/2m/on_extreme_reclaim_vwap_filter.yaml` | `data/reports/campaigns/overnight_inventory_reversion/ES/1m_full_history/2m/on_extreme_reclaim_vwap_filter/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -18,807.50, best PF 0.75. Failure type: performance-related. |
| overnight_inventory_reversion | on_extreme_reclaim_vwap_filter | 5m | `configs/campaigns/overnight_inventory_reversion/variants/ES/5m/on_extreme_reclaim_vwap_filter.yaml` | `data/reports/campaigns/overnight_inventory_reversion/ES/1m_full_history/5m/on_extreme_reclaim_vwap_filter/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 33 profitable iterations (30.56%), below 70%; best net profit 12,800.00, PF 1.16, MAR 0.45, win rate 44.1%. Failure type: robustness-related. Most promising campaign-1 rejection so far, but do not tune further after OOS/stage failure. |
| overnight_inventory_reversion | on_midpoint_reversion_confirmed | 2m | `configs/campaigns/overnight_inventory_reversion/variants/ES/2m/on_midpoint_reversion_confirmed.yaml` | `data/reports/campaigns/overnight_inventory_reversion/ES/1m_full_history/2m/on_midpoint_reversion_confirmed/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 28 profitable iterations (25.93%), below 70%; best combo had only 7 trades, net profit 710.00, PF 1.52, MAR 0.31. Failure type: robustness/trade-count-related. |
| overnight_inventory_reversion | on_midpoint_reversion_confirmed | 5m | `configs/campaigns/overnight_inventory_reversion/variants/ES/5m/on_midpoint_reversion_confirmed.yaml` | `data/reports/campaigns/overnight_inventory_reversion/ES/1m_full_history/5m/on_midpoint_reversion_confirmed/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 2 profitable iterations (1.85%), below 70%; best combo had 6 trades, net profit 52.50, PF 1.03. Failure type: trade-count/robustness-related. |
| overnight_inventory_reversion | on_midpoint_reversion_confirmed | 10m | `configs/campaigns/overnight_inventory_reversion/variants/ES/10m/on_midpoint_reversion_confirmed.yaml` | `data/reports/campaigns/overnight_inventory_reversion/ES/1m_full_history/10m/on_midpoint_reversion_confirmed/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 29 profitable iterations (26.85%), below 70%; best combo had only 3 trades, net profit 1,197.50, PF 3.96. Failure type: trade-count/robustness-related. Campaign 1 exhausted; most promising rejected config remains 5m VWAP-filtered extreme reclaim, but it is not robust enough to revisit soon. |
| vwap_pullback_continuation | opening_drive_vwap_pullback | 1m | `configs/campaigns/vwap_pullback_continuation/variants/ES/1m/opening_drive_vwap_pullback.yaml` | `data/reports/campaigns/vwap_pullback_continuation/ES/1m_full_history/1m/opening_drive_vwap_pullback/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -18,937.50, best PF 0.83, best MAR -0.36, 287 trades. Failure type: performance-related; the 1m opening-drive VWAP pullback expression is not viable under current costs/risk. |
| vwap_pullback_continuation | opening_drive_vwap_pullback | 2m | `configs/campaigns/vwap_pullback_continuation/variants/ES/2m/opening_drive_vwap_pullback.yaml` | `data/reports/campaigns/vwap_pullback_continuation/ES/1m_full_history/2m/opening_drive_vwap_pullback/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -30,522.50, best PF 0.65, best MAR -0.49, 229 trades. Failure type: performance-related; coarser 2m confirmation did not improve the opening-drive VWAP pullback edge. |
| vwap_pullback_continuation | opening_drive_vwap_pullback | 5m | `configs/campaigns/vwap_pullback_continuation/variants/ES/5m/opening_drive_vwap_pullback.yaml` | `data/reports/campaigns/vwap_pullback_continuation/ES/1m_full_history/5m/opening_drive_vwap_pullback/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -24,500.00, best PF 0.70, best MAR -0.46, 259 trades. Failure type: performance-related; opening-drive VWAP pullback variant exhausted across 1m/2m/5m. |
| vwap_pullback_continuation | vwap_reclaim_trend_continuation | 2m | `configs/campaigns/vwap_pullback_continuation/variants/ES/2m/vwap_reclaim_trend_continuation.yaml` | `data/reports/campaigns/vwap_pullback_continuation/ES/1m_full_history/2m/vwap_reclaim_trend_continuation/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -26,837.50, best PF 0.81, best MAR -0.42, 410 trades. Failure type: performance-related; trend-side VWAP context did not overcome costs/adverse selection on 2m. |
| vwap_pullback_continuation | vwap_reclaim_trend_continuation | 5m | `configs/campaigns/vwap_pullback_continuation/variants/ES/5m/vwap_reclaim_trend_continuation.yaml` | `data/reports/campaigns/vwap_pullback_continuation/ES/1m_full_history/5m/vwap_reclaim_trend_continuation/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -9,512.50, best PF 0.94, best MAR -0.32, 434 trades. Failure type: performance-related; closer than 2m but still no profitable parameter neighborhood. |
| vwap_pullback_continuation | vwap_reclaim_trend_continuation | 10m | `configs/campaigns/vwap_pullback_continuation/variants/ES/10m/vwap_reclaim_trend_continuation.yaml` | `data/reports/campaigns/vwap_pullback_continuation/ES/1m_full_history/10m/vwap_reclaim_trend_continuation/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -17,945.00, best PF 0.87, best MAR -0.32, 367 trades. Failure type: performance-related; trend-reclaim variant exhausted across 2m/5m/10m. |
| vwap_pullback_continuation | failed_vwap_break_continuation | 2m | `configs/campaigns/vwap_pullback_continuation/variants/ES/2m/failed_vwap_break_continuation.yaml` | `data/reports/campaigns/vwap_pullback_continuation/ES/1m_full_history/2m/failed_vwap_break_continuation/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -16,067.50, best PF 0.89, best MAR -0.34, 367 trades. Failure type: performance-related; failed VWAP break improved on opening-drive 2m but remains negative. |
| vwap_pullback_continuation | failed_vwap_break_continuation | 5m | `configs/campaigns/vwap_pullback_continuation/variants/ES/5m/failed_vwap_break_continuation.yaml` | `data/reports/campaigns/vwap_pullback_continuation/ES/1m_full_history/5m/failed_vwap_break_continuation/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 8 profitable iterations (7.41%), below 70%; best net profit 8,617.50, best PF 1.06, best MAR 0.36, 401 trades. Failure type: robustness/performance-related; first positive pocket in campaign 2, but too sparse and weak to trade or tune further. |
| vwap_pullback_continuation | failed_vwap_break_continuation | 10m | `configs/campaigns/vwap_pullback_continuation/variants/ES/10m/failed_vwap_break_continuation.yaml` | `data/reports/campaigns/vwap_pullback_continuation/ES/1m_full_history/10m/failed_vwap_break_continuation/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -10,685.00, best PF 0.91, best MAR -0.28, 307 trades. Failure type: performance-related; failed-break variant exhausted across 2m/5m/10m. Campaign 2 exhausted; best rejected pocket was 5m failed-break with 7.41% profitable iterations, still far below the 70% robustness gate. |
| pdh_pdl_breakout_continuation | fresh_close_break | 1m | `configs/campaigns/pdh_pdl_breakout_continuation/variants/ES/1m/fresh_close_break.yaml` | `data/reports/campaigns/pdh_pdl_breakout_continuation/ES/1m_full_history/1m/fresh_close_break/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 58 profitable iterations (53.70%), below 70%; best net profit 7,457.50, best PF 1.35, best MAR 0.78, 58 trades. Failure type: robustness/trade-count-related; strongest new pocket so far but not robust enough to trade. |
| pdh_pdl_breakout_continuation | fresh_close_break | 2m | `configs/campaigns/pdh_pdl_breakout_continuation/variants/ES/2m/fresh_close_break.yaml` | `data/reports/campaigns/pdh_pdl_breakout_continuation/ES/1m_full_history/2m/fresh_close_break/campaign_tests` | fail | Limited core grid passed with 106 profitable iterations (98.15%) and best net profit 10,705.00, PF 1.73, MAR 1.39, 54 trades; limited monkey then failed because core beat monkey max drawdown in 88.625% of runs versus required 90% (net-profit beat rate 94.3% passed). Failure type: robustness-related near miss; not a tradable pass. |
| pdh_pdl_breakout_continuation | fresh_close_break | 5m | `configs/campaigns/pdh_pdl_breakout_continuation/variants/ES/5m/fresh_close_break.yaml` | `data/reports/campaigns/pdh_pdl_breakout_continuation/ES/1m_full_history/5m/fresh_close_break/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 58 profitable iterations (53.70%), below 70%; best net profit 6,730.00, best PF 1.86, best MAR 1.77, 29 trades. Failure type: robustness/trade-count-related; stronger best MAR but too sparse and below the profitable-iteration gate. |
| pdh_pdl_breakout_continuation | break_retest_hold | 2m | `configs/campaigns/pdh_pdl_breakout_continuation/variants/ES/2m/break_retest_hold.yaml` | `data/reports/campaigns/pdh_pdl_breakout_continuation/ES/1m_full_history/2m/break_retest_hold/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 4 profitable iterations (3.70%), below 70%; best net profit 1,425.00, best PF 1.07, best MAR 0.08, 49 trades. Failure type: performance/trade-count-related; retest mechanic weak on 2m. |
| pdh_pdl_breakout_continuation | break_retest_hold | 5m | `configs/campaigns/pdh_pdl_breakout_continuation/variants/ES/5m/break_retest_hold.yaml` | `data/reports/campaigns/pdh_pdl_breakout_continuation/ES/1m_full_history/5m/break_retest_hold/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 34 profitable iterations (31.48%), below 70%; best net profit 2,850.00, best PF 1.17, best MAR 0.22, 43 trades. Failure type: robustness/trade-count-related; retest mechanic improved on 5m but remains weak. |
| pdh_pdl_breakout_continuation | break_retest_hold | 10m | `configs/campaigns/pdh_pdl_breakout_continuation/variants/ES/10m/break_retest_hold.yaml` | `data/reports/campaigns/pdh_pdl_breakout_continuation/ES/1m_full_history/10m/break_retest_hold/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 28 profitable iterations (25.93%), below 70%; best net profit 5,377.50, best PF 1.42, best MAR 0.95, 37 trades. Failure type: robustness/trade-count-related; retest mechanic exhausted across 2m/5m/10m. |
| pdh_pdl_breakout_continuation | gap_hold_continuation | 1m | `configs/campaigns/pdh_pdl_breakout_continuation/variants/ES/1m/gap_hold_continuation.yaml` | `data/reports/campaigns/pdh_pdl_breakout_continuation/ES/1m_full_history/1m/gap_hold_continuation/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 33 profitable iterations (30.56%), below 70%; best net profit 12,807.50, best PF 1.26, best MAR 1.11, 130 trades. Failure type: robustness-related; best pocket interesting but parameter neighborhood too sparse. |
| pdh_pdl_breakout_continuation | gap_hold_continuation | 2m | `configs/campaigns/pdh_pdl_breakout_continuation/variants/ES/2m/gap_hold_continuation.yaml` | `data/reports/campaigns/pdh_pdl_breakout_continuation/ES/1m_full_history/2m/gap_hold_continuation/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 72 profitable iterations (66.67%), just below 70%; best net profit 16,152.50, best PF 1.43, best MAR 1.59, 106 trades. Failure type: robustness near miss; strong best pocket but not enough profitable neighborhood to pass. |
| pdh_pdl_breakout_continuation | gap_hold_continuation | 5m | `configs/campaigns/pdh_pdl_breakout_continuation/variants/ES/5m/gap_hold_continuation.yaml` | `data/reports/campaigns/pdh_pdl_breakout_continuation/ES/1m_full_history/5m/gap_hold_continuation/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 61 profitable iterations (56.48%), below 70%; best net profit 13,267.50, best PF 1.46, best MAR 1.76, 103 trades. Failure type: robustness-related. Campaign 3 exhausted; best rejected evidence was 2m fresh-close-break passing core but failing monkey drawdown by 1.375 percentage points, and 2m gap-hold missing core profitable-rate by 3.33 percentage points. |
| rth_gap_fade | open_reversal | 1m | `configs/campaigns/rth_gap_fade/variants/ES/1m/open_reversal.yaml` | `data/reports/campaigns/rth_gap_fade/ES/1m_full_history/1m/open_reversal/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -6,425.00, best PF 0.96, best MAR -0.12, 338 trades. Failure type: performance-related; simple gap-open reversal is not viable on 1m with gap-fill targets and current costs. |
| rth_gap_fade | open_reversal | 2m | `configs/campaigns/rth_gap_fade/variants/ES/2m/open_reversal.yaml` | `data/reports/campaigns/rth_gap_fade/ES/1m_full_history/2m/open_reversal/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -18,595.00, best PF 0.82, best MAR -0.41, 274 trades. Failure type: performance-related; coarser 2m open-reversal gap fade deteriorated. |
| rth_gap_fade | open_reversal | 5m | `configs/campaigns/rth_gap_fade/variants/ES/5m/open_reversal.yaml` | `data/reports/campaigns/rth_gap_fade/ES/1m_full_history/5m/open_reversal/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -7,257.50, best PF 0.87, best MAR -0.25, 179 trades. Failure type: performance-related; open-reversal gap fade exhausted across 1m/2m/5m. |
| rth_gap_fade | extension_reject | 1m | `configs/campaigns/rth_gap_fade/variants/ES/1m/extension_reject.yaml` | `data/reports/campaigns/rth_gap_fade/ES/1m_full_history/1m/extension_reject/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -1,417.50, best PF 0.99, best MAR -0.03, 331 trades. Failure type: performance-related; extension rejection improved toward breakeven but still no profitable parameter neighborhood. |
| rth_gap_fade | extension_reject | 2m | `configs/campaigns/rth_gap_fade/variants/ES/2m/extension_reject.yaml` | `data/reports/campaigns/rth_gap_fade/ES/1m_full_history/2m/extension_reject/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -18,305.00, best PF 0.76, best MAR -0.38, 216 trades. Failure type: performance-related; 2m extension rejection is not viable. |
| rth_gap_fade | extension_reject | 5m | `configs/campaigns/rth_gap_fade/variants/ES/5m/extension_reject.yaml` | `data/reports/campaigns/rth_gap_fade/ES/1m_full_history/5m/extension_reject/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -13,750.00, best PF 0.79, best MAR -0.41, 195 trades. Failure type: performance-related; extension-reject gap fade exhausted across 1m/2m/5m. |
| rth_gap_fade | vwap_reclaim | 1m | `configs/campaigns/rth_gap_fade/variants/ES/1m/vwap_reclaim.yaml` | `data/reports/campaigns/rth_gap_fade/ES/1m_full_history/1m/vwap_reclaim/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -11,010.00, best PF 0.91, best MAR -0.28, 323 trades. Failure type: performance-related; VWAP confirmation did not rescue 1m gap fade. |
| rth_gap_fade | vwap_reclaim | 2m | `configs/campaigns/rth_gap_fade/variants/ES/2m/vwap_reclaim.yaml` | `data/reports/campaigns/rth_gap_fade/ES/1m_full_history/2m/vwap_reclaim/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -5,942.50, best PF 0.94, best MAR -0.25, 314 trades. Failure type: performance-related; 2m VWAP reclaim gap fade improved versus open reversal but stayed loss-making across the full grid. |
| rth_gap_fade | vwap_reclaim | 5m | `configs/campaigns/rth_gap_fade/variants/ES/5m/vwap_reclaim.yaml` | `data/reports/campaigns/rth_gap_fade/ES/1m_full_history/5m/vwap_reclaim/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -6,775.00, best PF 0.93, best MAR -0.29, 249 trades. Failure type: performance-related; campaign 4 exhausted with no profitable parameter neighborhoods across open reversal, extension rejection, or VWAP reclaim. |
| opening_range_filtered_breakout | vwap_aligned_fixed_r | 1m | `configs/campaigns/opening_range_filtered_breakout/variants/ES/1m/vwap_aligned_fixed_r.yaml` | `data/reports/campaigns/opening_range_filtered_breakout/ES/1m_full_history/1m/vwap_aligned_fixed_r/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 72 profitable iterations (66.67%), below 70%; best net profit 12,732.50, best PF 1.16, best MAR 1.09, 285 trades. Failure type: robustness near miss; positive pocket but not enough profitable neighborhood and best PF/MAR remain below confidence gates. |
| opening_range_filtered_breakout | vwap_aligned_fixed_r | 2m | `configs/campaigns/opening_range_filtered_breakout/variants/ES/2m/vwap_aligned_fixed_r.yaml` | `data/reports/campaigns/opening_range_filtered_breakout/ES/1m_full_history/2m/vwap_aligned_fixed_r/campaign_tests` | fail | Limited core grid passed with 84 profitable iterations (77.78%) and best net profit 11,002.50, PF 1.18, MAR 0.96, 248 trades; limited monkey then failed because core beat monkey net profit in 76.10% of runs versus required 90% (drawdown beat rate 99.8625% passed). Failure type: robustness-related; candidate did not show enough edge over constrained random alternatives. |
| opening_range_filtered_breakout | vwap_aligned_fixed_r | 5m | `configs/campaigns/opening_range_filtered_breakout/variants/ES/5m/vwap_aligned_fixed_r.yaml` | `data/reports/campaigns/opening_range_filtered_breakout/ES/1m_full_history/5m/vwap_aligned_fixed_r/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 60 profitable iterations (55.56%), below 70%; best net profit 9,115.00, best PF 1.31, best MAR 0.91, 160 trades. Failure type: robustness/trade-count-related; vwap-aligned fixed-R variant exhausted across 1m/2m/5m. |
| opening_range_filtered_breakout | volume_confirmed_extension | 2m | `configs/campaigns/opening_range_filtered_breakout/variants/ES/2m/volume_confirmed_extension.yaml` | `data/reports/campaigns/opening_range_filtered_breakout/ES/1m_full_history/2m/volume_confirmed_extension/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 72 profitable iterations (66.67%), below 70%; best net profit 11,142.50, best PF 1.18, best MAR 1.04, 248 trades. Failure type: robustness near miss; removing VWAP alignment did not create a broad enough positive parameter neighborhood. |
| opening_range_filtered_breakout | volume_confirmed_extension | 5m | `configs/campaigns/opening_range_filtered_breakout/variants/ES/5m/volume_confirmed_extension.yaml` | `data/reports/campaigns/opening_range_filtered_breakout/ES/1m_full_history/5m/volume_confirmed_extension/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 51 profitable iterations (47.22%), below 70%; best net profit 7,355.63, best PF 1.25, best MAR 0.78, 160 trades. Failure type: robustness/trade-count-related; 5m volume-confirmed extension is weaker than 2m. |
| opening_range_filtered_breakout | volume_confirmed_extension | 1m | `configs/campaigns/opening_range_filtered_breakout/variants/ES/1m/volume_confirmed_extension.yaml` | `data/reports/campaigns/opening_range_filtered_breakout/ES/1m_full_history/1m/volume_confirmed_extension/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 39 profitable iterations (36.11%), below 70%; best net profit 10,253.13, best PF 1.25, best MAR 1.16, 198 trades. Failure type: robustness-related; volume-confirmed extension variant exhausted across 1m/2m/5m. |
| opening_range_filtered_breakout | failed_break_fade | 2m | `configs/campaigns/opening_range_filtered_breakout/variants/ES/2m/failed_break_fade.yaml` | `data/reports/campaigns/opening_range_filtered_breakout/ES/1m_full_history/2m/failed_break_fade/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 12 profitable iterations (11.11%), below 70%; best combo had only 2 trades, net profit 1,110.00, PF 6.29, MAR 8.45. Failure type: trade-count/robustness-related; the inverse fade expression is sparse and not robust on 2m. |
| opening_range_filtered_breakout | failed_break_fade | 5m | `configs/campaigns/opening_range_filtered_breakout/variants/ES/5m/failed_break_fade.yaml` | `data/reports/campaigns/opening_range_filtered_breakout/ES/1m_full_history/5m/failed_break_fade/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 3 profitable iterations (2.78%), below 70%; best combo had only 7 trades, net profit 547.50, PF 1.24, MAR 0.94. Failure type: trade-count/robustness-related; 5m inverse fade is not viable. |
| opening_range_filtered_breakout | failed_break_fade | 1m | `configs/campaigns/opening_range_filtered_breakout/variants/ES/1m/failed_break_fade.yaml` | `data/reports/campaigns/opening_range_filtered_breakout/ES/1m_full_history/1m/failed_break_fade/campaign_tests` | fail | Limited core grid failed: 108 combinations tested, 0 profitable iterations, best net profit -1,610.00, best PF 0.67, best MAR -0.26, 13 trades. Failure type: performance/trade-count-related; failed-break fade variant exhausted across 1m/2m/5m. Campaign 5 exhausted. |

## Budget-Exhausted Conclusion

- Search budget used: 5 new campaigns, each structured as exactly 3 variants x 3 timeframes.
- Tradable pass found: no. No candidate passed all staged gates.
- Strongest rejected evidence:
  - `pdh_pdl_breakout_continuation/fresh_close_break/2m`: core passed, monkey failed only on max-drawdown beat rate (88.625% vs required 90%).
  - `opening_range_filtered_breakout/vwap_aligned_fixed_r/2m`: core passed with 84/108 profitable iterations, monkey failed on net-profit beat rate (76.10% vs required 90%).
  - `pdh_pdl_breakout_continuation/gap_hold_continuation/2m`: core near miss at 72/108 profitable iterations (66.67% vs required 70%).
- Confidence decision: none of these are acceptable to trade under the stated process. The near misses are useful research leads only; trading them now would violate the robustness gates.

## Reopened Search: Academic Source Requirement

- Date reopened: 2026-06-06.
- Reason: Prior campaigns were mostly market-structure hypotheses without verified academic support. New attempts must use verified academic sources and keep the full staged validation criteria unchanged.
- Full validation command: `PYTHONPATH=src python3 -m propstack.run_campaign_stages --config PATH`.
- Pass definition: all default stages in `src/propstack/research/campaign_stages.py` must pass without criteria overrides.

## New Academic Campaign 6 Plan

- Campaign: `late_day_intraday_momentum`
- Academic source: Gao, Lei; Han, Yufeng; Li, Sophia Zhengzi; Zhou, Guofu (2018), "Market Intraday Momentum", Journal of Financial Economics 129(2), 394-414, DOI `10.1016/j.jfineco.2018.05.009`, URL `https://www.sciencedirect.com/science/article/abs/pii/S0304405X18301351`.
- Finding used: The first half-hour market return predicts the last half-hour market return; predictability is stronger on high-volume and high-volatility days and can improve when combined with the penultimate half-hour return.
- Evidence directness for ES: Indirect. The paper primarily tests SPY and ETFs; ES is used as the liquid S&P 500 futures proxy.
- Edge thesis: Trade the final RTH half-hour in the direction implied by earlier same-day market momentum, expecting closing flow to continue the opening information impulse.
- Why it may apply to ES: ES tracks S&P 500 index exposure, trades with deep liquidity, and is commonly used for index exposure and closing-risk adjustment.
- Why it may survive costs/slippage: The strategy trades at most once per day, uses existing ES transaction-cost assumptions, and avoids high-turnover intraday scalping.
- Expected working regime: Active, directional sessions with persistent information digestion and closing-flow pressure.
- Expected failure regime: Low-volume chop, sharp late reversals, and days where futures closing behavior diverges from ETF closing behavior.
- Translation risks: SPY closing mechanics, ETF flow, and sample period may not transfer cleanly to ES futures; ES has nearly 24-hour trading and different microstructure around the cash close.

### Campaign 6 Variants And Configs

| Variant | Timeframe | Config | Status | Result Path | Main Failure Reason |
| --- | --- | --- | --- | --- | --- |
| first_half_hour_sign | 30m | `configs/campaigns/late_day_intraday_momentum/variants/ES/30m/first_half_hour_sign.yaml` | fail | `data/reports/campaigns/late_day_intraday_momentum/ES/1m_full_history/30m/first_half_hour_sign/campaign_tests` | Limited core grid failed: 100 combinations, 0 profitable iterations; best net profit -4,630.00, PF 0.856, 121 trades. Failure type: performance-related. |
| first_half_hour_sign | 15m | `configs/campaigns/late_day_intraday_momentum/variants/ES/15m/first_half_hour_sign.yaml` | fail | `data/reports/campaigns/late_day_intraday_momentum/ES/1m_full_history/15m/first_half_hour_sign/campaign_tests` | Limited core grid failed: 100 combinations, 0 profitable iterations; best net profit -5,290.00, PF 0.836, 118 trades. Failure type: performance-related. |
| first_half_hour_sign | 5m | `configs/campaigns/late_day_intraday_momentum/variants/ES/5m/first_half_hour_sign.yaml` | fail | `data/reports/campaigns/late_day_intraday_momentum/ES/1m_full_history/5m/first_half_hour_sign/campaign_tests` | Limited core grid failed: 100 combinations, 0 profitable iterations; best net profit -5,290.00, PF 0.836, 118 trades. Failure type: performance-related. |
| first_and_penultimate_alignment | 30m | `configs/campaigns/late_day_intraday_momentum/variants/ES/30m/first_and_penultimate_alignment.yaml` | fail | `data/reports/campaigns/late_day_intraday_momentum/ES/1m_full_history/30m/first_and_penultimate_alignment/campaign_tests` | Limited core grid failed: 200 combinations, 50 profitable iterations (25.00%), below 70%; best net profit 3,697.50, PF 1.197, 83 trades, best-day concentration 58.0%. Failure type: robustness/trade-count-related. |
| first_and_penultimate_alignment | 15m | `configs/campaigns/late_day_intraday_momentum/variants/ES/15m/first_and_penultimate_alignment.yaml` | fail | `data/reports/campaigns/late_day_intraday_momentum/ES/1m_full_history/15m/first_and_penultimate_alignment/campaign_tests` | Limited core grid failed: 200 combinations, 50 profitable iterations (25.00%), below 70%; best net profit 3,697.50, PF 1.197, 83 trades, best-day concentration 58.0%. Failure type: robustness/trade-count-related. |
| first_and_penultimate_alignment | 5m | `configs/campaigns/late_day_intraday_momentum/variants/ES/5m/first_and_penultimate_alignment.yaml` | fail | `data/reports/campaigns/late_day_intraday_momentum/ES/1m_full_history/5m/first_and_penultimate_alignment/campaign_tests` | Limited core grid failed: 200 combinations, 50 profitable iterations (25.00%), below 70%; best net profit 3,697.50, PF 1.197, 83 trades, best-day concentration 58.0%. Failure type: robustness/trade-count-related. |
| volume_volatility_conditioned | 30m | `configs/campaigns/late_day_intraday_momentum/variants/ES/30m/volume_volatility_conditioned.yaml` | fail | `data/reports/campaigns/late_day_intraday_momentum/ES/1m_full_history/30m/volume_volatility_conditioned/campaign_tests` | Limited core grid failed: 200 combinations, 0 profitable iterations; best net profit -4,630.00, PF 0.856, 121 trades. Failure type: performance-related. |
| volume_volatility_conditioned | 15m | `configs/campaigns/late_day_intraday_momentum/variants/ES/15m/volume_volatility_conditioned.yaml` | fail | `data/reports/campaigns/late_day_intraday_momentum/ES/1m_full_history/15m/volume_volatility_conditioned/campaign_tests` | Limited core grid failed: 200 combinations, 0 profitable iterations; best net profit -5,290.00, PF 0.836, 118 trades. Failure type: performance-related. |
| volume_volatility_conditioned | 5m | `configs/campaigns/late_day_intraday_momentum/variants/ES/5m/volume_volatility_conditioned.yaml` | fail | `data/reports/campaigns/late_day_intraday_momentum/ES/1m_full_history/5m/volume_volatility_conditioned/campaign_tests` | Limited core grid failed: 200 combinations, 0 profitable iterations; best net profit -3,665.00, PF 0.863, 108 trades. Failure type: performance-related. |

- Campaign 6 conclusion: exhausted. No Gao late-day intraday momentum variant-timeframe passed the default limited core grid gate, so no candidate advanced to full validation.

## New Academic Campaign 7 Plan

- Campaign: `overnight_return_late_day_momentum`
- Academic source: Liu, Qingfu; Tse, Yiuman (2017), "Overnight Returns of Stock Indexes: Evidence from ETFs and Futures", International Review of Economics & Finance 48, DOI `10.1016/j.iref.2017.01.005`, URL `https://www.sciencedirect.com/science/article/pii/S1059056016301563`.
- Finding used: For US ETF and futures markets, overnight returns forecast first half-hour returns negatively and last half-hour returns positively.
- Evidence directness for ES: Direct enough to prioritize. The paper explicitly includes E-mini futures and tests first and last half-hour intraday intervals.
- Edge thesis: Trade the final RTH half-hour in the direction of the close-to-open overnight return, expecting overnight information to continue into closing flow.
- Why this is not a renamed failed campaign: Existing `rth_gap_fade` variants traded opening reversal mechanics. This campaign does not enter near the open; it waits for the final half-hour and tests the source paper's positive last-half-hour relation.
- Why it may survive costs/slippage: It trades at most once per day, uses current ES transaction-cost assumptions, and avoids intraday scalping frequency.
- Expected working regime: Sessions where overnight information remains relevant into close and closing flows extend the overnight direction.
- Expected failure regime: Full opening reversal, low-participation closes, and late-day news shocks that override overnight information.
- Translation risks: The published sample ends in 2014; post-2014 E-mini market structure and overnight information assimilation may have changed.

### Campaign 7 Variants And Configs

| Variant | Timeframe | Config | Status | Result Path | Main Failure Reason |
| --- | --- | --- | --- | --- | --- |
| overnight_sign_close_continuation | 30m | `configs/campaigns/overnight_return_late_day_momentum/variants/ES/30m/overnight_sign_close_continuation.yaml` | fail | `data/reports/campaigns/overnight_return_late_day_momentum/ES/1m_full_history/30m/overnight_sign_close_continuation/campaign_tests` | Limited core grid failed: 100 combinations, 0 profitable iterations; best net profit -2,445.00, PF 0.915, 119 trades. Failure type: performance/trade-count-related. |
| overnight_sign_close_continuation | 15m | `configs/campaigns/overnight_return_late_day_momentum/variants/ES/15m/overnight_sign_close_continuation.yaml` | fail | `data/reports/campaigns/overnight_return_late_day_momentum/ES/1m_full_history/15m/overnight_sign_close_continuation/campaign_tests` | Limited core grid failed: 100 combinations, 0 profitable iterations; best net profit -3,245.00, PF 0.888, 114 trades. Failure type: performance/trade-count-related. |
| overnight_sign_close_continuation | 5m | `configs/campaigns/overnight_return_late_day_momentum/variants/ES/5m/overnight_sign_close_continuation.yaml` | fail | `data/reports/campaigns/overnight_return_late_day_momentum/ES/1m_full_history/5m/overnight_sign_close_continuation/campaign_tests` | Limited core grid failed: 100 combinations, 0 profitable iterations; best net profit -3,245.00, PF 0.888, 114 trades. Failure type: performance/trade-count-related. |
| opening_reversal_confirmed | 30m | `configs/campaigns/overnight_return_late_day_momentum/variants/ES/30m/opening_reversal_confirmed.yaml` | fail | `data/reports/campaigns/overnight_return_late_day_momentum/ES/1m_full_history/30m/opening_reversal_confirmed/campaign_tests` | Limited core grid failed: 200 combinations, 50 profitable iterations (25.00%), below 70%; best net profit 4,905.00, PF 1.343, 79 trades, best-day concentration 43.7%. Failure type: robustness/trade-count/concentration-related. |
| opening_reversal_confirmed | 15m | `configs/campaigns/overnight_return_late_day_momentum/variants/ES/15m/opening_reversal_confirmed.yaml` | fail | `data/reports/campaigns/overnight_return_late_day_momentum/ES/1m_full_history/15m/opening_reversal_confirmed/campaign_tests` | Limited core grid failed: 200 combinations, 50 profitable iterations (25.00%), below 70%; best net profit 4,905.00, PF 1.343, 79 trades, best-day concentration 43.7%. Failure type: robustness/trade-count/concentration-related. |
| opening_reversal_confirmed | 5m | `configs/campaigns/overnight_return_late_day_momentum/variants/ES/5m/opening_reversal_confirmed.yaml` | fail | `data/reports/campaigns/overnight_return_late_day_momentum/ES/1m_full_history/5m/opening_reversal_confirmed/campaign_tests` | Limited core grid failed: 200 combinations, 50 profitable iterations (25.00%), below 70%; best net profit 4,905.00, PF 1.343, 79 trades, best-day concentration 43.7%. Failure type: robustness/trade-count/concentration-related. |
| overnight_penultimate_alignment | 30m | `configs/campaigns/overnight_return_late_day_momentum/variants/ES/30m/overnight_penultimate_alignment.yaml` | fail | `data/reports/campaigns/overnight_return_late_day_momentum/ES/1m_full_history/30m/overnight_penultimate_alignment/campaign_tests` | Limited core grid failed: 200 combinations, 50 profitable iterations (25.00%), below 70%; best net profit 7,070.00, PF 1.425, 86 trades. Failure type: robustness/trade-count-related. |
| overnight_penultimate_alignment | 15m | `configs/campaigns/overnight_return_late_day_momentum/variants/ES/15m/overnight_penultimate_alignment.yaml` | fail | `data/reports/campaigns/overnight_return_late_day_momentum/ES/1m_full_history/15m/overnight_penultimate_alignment/campaign_tests` | Limited core grid failed: 200 combinations, 50 profitable iterations (25.00%), below 70%; best net profit 7,070.00, PF 1.425, 86 trades. Failure type: robustness/trade-count-related. |
| overnight_penultimate_alignment | 5m | `configs/campaigns/overnight_return_late_day_momentum/variants/ES/5m/overnight_penultimate_alignment.yaml` | fail | `data/reports/campaigns/overnight_return_late_day_momentum/ES/1m_full_history/5m/overnight_penultimate_alignment/campaign_tests` | Limited core grid failed: 200 combinations, 50 profitable iterations (25.00%), below 70%; best net profit 7,070.00, PF 1.425, 86 trades. Failure type: robustness/trade-count-related. |

- Campaign 7 conclusion: exhausted. No Liu-Tse overnight return late-day momentum variant-timeframe passed the default limited core grid gate. Strongest rejected expression was overnight-plus-penultimate alignment with best net profit 7,070.00 and PF 1.425, but only 25.00% profitable grid iterations and insufficient trade count.

## Grant-Wolf-Yu Fallback Review

- Source reviewed: Grant, James L.; Wolf, Avner; Yu, Susana (2005), "Intraday Price Reversals in the US Stock Index Futures Market: A 15-Year Study", Journal of Banking & Finance, DOI `10.1016/j.jbankfin.2004.04.006`.
- Finding reviewed: Large opening-price changes in S&P 500 futures show initial continuation, then reversal after roughly 10 minutes; the abstract notes reversal profitability is reduced after transaction costs.
- Ledger overlap: Existing `rth_gap_fade` already tested open reversal, extension rejection, and VWAP reclaim gap-fade mechanics across 1m/2m/5m, all with zero profitable limited-core neighborhoods.
- Distinct-mechanic screen: Tested only the paper-specific sequence on 2021-2022 core data: large opening move, 5/10/15/20/30 minute continuation, then delayed fade to 10:30/11:00/12:00/15:30/16:00. Only 2 of 700 rough combinations were positive, both barely above breakeven with PF about 1.02.
- Decision: Do not create a full Grant-Wolf-Yu campaign. It would be mostly a renamed failed opening-gap-fade campaign, and the only distinct delayed-reversal expression is not economically robust under current costs.

## New Academic Campaign 8 Plan

- Campaign: `daily_time_series_momentum`
- Academic source: Moskowitz, Tobias J.; Ooi, Yao Hua; Pedersen, Lasse Heje (2012), "Time Series Momentum", Journal of Financial Economics 104(2), 228-250, DOI `10.1016/j.jfineco.2011.11.003`, URL `https://www.sciencedirect.com/science/article/pii/S0304405X11002613`.
- Finding used: Past one- to 12-month returns positively predict futures returns across equity index, currency, commodity, and bond futures.
- Evidence directness for ES: Direct for futures and equity index futures, but translated from the paper's diversified monthly holding design into a single-instrument RTH intraday implementation.
- Edge thesis: Use only completed prior RTH closes to determine a trailing trend direction, enter once near the next RTH open, and flatten by the RTH close.
- Why this is not a renamed failed campaign: It does not use opening ranges, gaps, VWAP, PDH/PDL levels, overnight extremes, or late-day intraday momentum. It is a prior-session close-to-close trend-following mechanic.
- Why it may survive costs/slippage: It trades at most once per day and uses broad multi-session trend filters rather than frequent intraday scalps.
- Expected working regime: Persistent equity-index trend regimes and crisis-trend periods.
- Expected failure regime: Sideways mean-reverting regimes, sharp overnight reversals, and periods where most trend return occurs outside RTH.
- Translation risks: The source's canonical strategy is monthly and diversified across many futures; this is a single ES RTH expression.

### Campaign 8 Variants And Configs

| Variant | Timeframe | Config | Status | Result Path | Main Failure Reason |
| --- | --- | --- | --- | --- | --- |
| close_to_close_trend | 30m | `configs/campaigns/daily_time_series_momentum/variants/ES/30m/close_to_close_trend.yaml` | fail | `data/reports/campaigns/daily_time_series_momentum/ES/1m_full_history/30m/close_to_close_trend/campaign_tests` | Limited core grid failed: 120 combinations, 11 profitable iterations (9.17%), below 70%; best net profit 877.50, PF 1.004, 482 trades, best-day concentration 395.4%. Failure type: weak edge/concentration-related. |
| close_to_close_trend | 15m | `configs/campaigns/daily_time_series_momentum/variants/ES/15m/close_to_close_trend.yaml` | fail | `data/reports/campaigns/daily_time_series_momentum/ES/1m_full_history/15m/close_to_close_trend/campaign_tests` | Limited core grid failed: 120 combinations, 12 profitable iterations (10.00%), below 70%; best net profit 3,830.00, PF 1.010, 450 trades, best-day concentration 343.3%. Failure type: weak edge/concentration-related. |
| close_to_close_trend | 5m | `configs/campaigns/daily_time_series_momentum/variants/ES/5m/close_to_close_trend.yaml` | fail | `data/reports/campaigns/daily_time_series_momentum/ES/1m_full_history/5m/close_to_close_trend/campaign_tests` | Limited core grid failed: 120 combinations, 4 profitable iterations (3.33%), below 70%; best net profit 1,310.00, PF 1.004, 430 trades, best-day concentration 1046.6%. Failure type: weak edge/concentration-related. |
| volatility_normalized_trend | 30m | `configs/campaigns/daily_time_series_momentum/variants/ES/30m/volatility_normalized_trend.yaml` | fail | `data/reports/campaigns/daily_time_series_momentum/ES/1m_full_history/30m/volatility_normalized_trend/campaign_tests` | Limited core grid failed: 240 combinations, 22 profitable iterations (9.17%), below 70%; best net profit 877.50, PF 1.004, 482 trades, best-day concentration 395.4%. Failure type: weak edge/concentration-related. |
| volatility_normalized_trend | 15m | `configs/campaigns/daily_time_series_momentum/variants/ES/15m/volatility_normalized_trend.yaml` | fail | `data/reports/campaigns/daily_time_series_momentum/ES/1m_full_history/15m/volatility_normalized_trend/campaign_tests` | Limited core grid failed: 240 combinations, 24 profitable iterations (10.00%), below 70%; best net profit 3,830.00, PF 1.010, 450 trades, best-day concentration 343.3%. Failure type: weak edge/concentration-related. |
| volatility_normalized_trend | 5m | `configs/campaigns/daily_time_series_momentum/variants/ES/5m/volatility_normalized_trend.yaml` | fail | `data/reports/campaigns/daily_time_series_momentum/ES/1m_full_history/5m/volatility_normalized_trend/campaign_tests` | Limited core grid failed: 240 combinations, 8 profitable iterations (3.33%), below 70%; best net profit 1,310.00, PF 1.004, 430 trades, best-day concentration 1046.6%. Failure type: weak edge/concentration-related. |
| short_term_alignment | 30m | `configs/campaigns/daily_time_series_momentum/variants/ES/30m/short_term_alignment.yaml` | fail | `data/reports/campaigns/daily_time_series_momentum/ES/1m_full_history/30m/short_term_alignment/campaign_tests` | Limited core grid failed: 240 combinations, 24 profitable iterations (10.00%), below 70%; best net profit 3,087.50, PF 1.013, 445 trades, best-day concentration 112.4%. Failure type: weak edge/concentration-related. |
| short_term_alignment | 15m | `configs/campaigns/daily_time_series_momentum/variants/ES/15m/short_term_alignment.yaml` | fail | `data/reports/campaigns/daily_time_series_momentum/ES/1m_full_history/15m/short_term_alignment/campaign_tests` | Limited core grid failed: 240 combinations, 28 profitable iterations (11.67%), below 70%; best net profit 11,877.50, PF 1.031, 447 trades, best-day concentration 110.7%. Failure type: weak edge/concentration-related. |
| short_term_alignment | 5m | `configs/campaigns/daily_time_series_momentum/variants/ES/5m/short_term_alignment.yaml` | fail | `data/reports/campaigns/daily_time_series_momentum/ES/1m_full_history/5m/short_term_alignment/campaign_tests` | Limited core grid failed: 240 combinations, 13 profitable iterations (5.42%), below 70%; best net profit 1,310.00, PF 1.004, 430 trades, best-day concentration 1046.6%. Failure type: weak edge/concentration-related. |

- Campaign 8 conclusion: exhausted. The single-instrument RTH intraday translation of futures time-series momentum did not produce a robust core parameter neighborhood. Best rejected expression was `15m/short_term_alignment` with net profit 11,877.50, but PF was only 1.031 and profitable grid rate was 11.67%, far below the 70% default gate.

## New Academic Campaign 9 Plan

- Campaign: `calendar_session_seasonality`
- Academic source: Floros, Christos; Salvador, Enrique (2014), "Calendar anomalies in cash and stock index futures: International evidence", Economic Modelling 37, 216-223, DOI `10.1016/j.econmod.2013.10.036`, URL `https://www.sciencedirect.com/science/article/abs/pii/S0264999313004781`.
- Finding used: Day-of-week and monthly seasonal effects differ between cash and stock index futures and are conditioned by market regime; the study includes S&P 500 futures.
- Evidence directness for ES: Direct for S&P 500 futures calendar effects, translated to intraday ES session windows.
- Edge thesis: Calendar effects may concentrate return by weekday and intraday session window; test whether weekday/session windows survive current ES costs and prop constraints.
- Why this is not a renamed failed campaign: It does not use opening range, gaps, VWAP, prior-day levels, overnight extremes, intraday momentum, or multi-session trend. It is a weekday/session seasonal bias.
- Why it may survive costs/slippage: It trades at most once per eligible day and uses session windows rather than high-turnover scalping.
- Expected working regime: Persistent weekday/session flow imbalance.
- Expected failure regime: Calendar anomaly decay, regime shifts, and outlier-dominated windows.
- Translation risks: The source studies daily futures calendar effects; this campaign tests intraday RTH windows and therefore relies on full staged validation.

### Campaign 9 Variants And Configs

| Variant | Timeframe | Config | Status | Result Path | Main Failure Reason |
| --- | --- | --- | --- | --- | --- |
| midweek_morning_strength | 30m | `configs/campaigns/calendar_session_seasonality/variants/ES/30m/midweek_morning_strength.yaml` | `data/reports/campaigns/calendar_session_seasonality/ES/1m_full_history/30m/midweek_morning_strength/campaign_tests` | failed limited monkey | Core passed exactly 84/120 profitable (70.0%); top grid net $52,815 PF 1.255, but selected core monkey beat rates were 79.625% net profit / 79.625% max DD vs 90% required. |
| midweek_morning_strength | 15m | `configs/campaigns/calendar_session_seasonality/variants/ES/15m/midweek_morning_strength.yaml` | `data/reports/campaigns/calendar_session_seasonality/ES/1m_full_history/15m/midweek_morning_strength/campaign_tests` | failed limited monkey | Core passed 101/120 profitable (84.17%); top grid net $70,292.50 PF 1.257, but selected core monkey beat rates were 86.65% net profit / 82.7375% max DD vs 90% required. |
| midweek_morning_strength | 5m | `configs/campaigns/calendar_session_seasonality/variants/ES/5m/midweek_morning_strength.yaml` | pending | pending | pending |
| late_week_afternoon_bias | 30m | `configs/campaigns/calendar_session_seasonality/variants/ES/30m/late_week_afternoon_bias.yaml` | pending | pending | pending |
| late_week_afternoon_bias | 15m | `configs/campaigns/calendar_session_seasonality/variants/ES/15m/late_week_afternoon_bias.yaml` | pending | pending | pending |
| late_week_afternoon_bias | 5m | `configs/campaigns/calendar_session_seasonality/variants/ES/5m/late_week_afternoon_bias.yaml` | pending | pending | pending |
| broad_session_calendar_mix | 30m | `configs/campaigns/calendar_session_seasonality/variants/ES/30m/broad_session_calendar_mix.yaml` | pending | pending | pending |
| broad_session_calendar_mix | 15m | `configs/campaigns/calendar_session_seasonality/variants/ES/15m/broad_session_calendar_mix.yaml` | pending | pending | pending |
| broad_session_calendar_mix | 5m | `configs/campaigns/calendar_session_seasonality/variants/ES/5m/broad_session_calendar_mix.yaml` | pending | pending | pending |
