# NQ ChartFanatics Weekly Stage 2 Breakout Bias Methodology Audit

Final verdict: FAIL.

## Source and Edge

This campaign was launched from Chart Fanatics' Stage Analysis Strategy after screening the remaining futures-labeled strategy pages for duplicates and local data gates. The tested edge is the locally reproducible subset: completed prior-week Stage 2 trend state, defined from 10/20/30/40-week moving-average alignment and weekly structure, gating NQ same-day continuation/reclaim entries.

Academic support is limited to broad moving-average, breakout, and time-series momentum evidence; it is not treated as proof that this intraday NQ adaptation should work.

## Duplicate Check

The campaign is distinct from prior NQ measured-move, EMA pullback, daily Bollinger, opening-range retest, wide-range continuation, and market-structure pivot campaigns because the economic gating variable is weekly Stage 2 cycle state, not an intraday trend or orderflow pattern alone.

## Timing and Lookahead

- Weekly state is built only from completed RTH sessions before the current week.
- The current incomplete week is excluded even if earlier current-week sessions have already printed.
- Prior-day high/close and five-day compression levels use only completed sessions before the signal date.
- Intraday triggers use completed five-minute bars; engine entries occur no earlier than the next bar.
- Same-day flattening is enforced and overnight exposure is forbidden.

## Parameter Freeze

Five variants were declared before staged PnL. Each uses two entry tunables, one stop tunable, and one take-profit tunable for 54 combinations. No rescue is authorized.

## Current Status

Pre-PnL density passed: 45/45 declared entry rows and 5/5 variants passed the signal-density screen.

Artifacts:

- `research_artifacts/nq_chartfanatics_weekly_stage_breakout_bias_density_audit_20260701.md`
- `research_artifacts/nq_chartfanatics_weekly_stage_breakout_bias_density_summary_20260701.csv`

Staged validation is now allowed under the frozen parameter grid.


## Staged Validation

All five variants failed `limited_core_grid_test`. Every variant had 0/54 benchmark-passing combinations. Only `stage2_compression_breakout_1200` had any profitable grid rows (15/54), still far below the 70% profitable-iteration threshold.

No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. No rescue was authorized or run.

Artifacts:

- `backtest-campaigns/nq_chartfanatics_weekly_stage_breakout_bias/campaign_test_summary.json`
- `backtest-campaigns/nq_chartfanatics_weekly_stage_breakout_bias/limited_core_results_summary.csv`

## Final Decision

FAIL. The ChartFanatics weekly Stage 2 NQ adaptation cleared source, duplicate, timing, density, and preflight gates, but failed the first staged PnL robustness gate across all five variants. It is rejected unless the user explicitly authorizes a single rescue attempt within the same mechanics family.
