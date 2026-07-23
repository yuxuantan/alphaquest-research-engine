# Core Grid / Monkey Test Versus Archived Runs Audit - 2026-06-17

Question: are current limited core-grid and monkey tests different from archived runs in a way that could make variants fail when they would previously have progressed?

## Pre-Fix Current Behavior Observed

At the start of this audit, staged runs were driven by
`src/propstack/research/campaign_stages.py` with the behavior below. This section
is retained as the finding that triggered the fix; it is no longer the effective
post-fix behavior.

Limited core grid used default criteria:

- `summary.total_combinations_tested` must be a valid methodology count: exactly 1 fixed combo, or 8-120 tunable combos.
- `summary.percentage_profitable_iterations >= 0.70`.
- `summary.number_passing_benchmark >= 1`.
- `summary.apex_rule_violating_iterations <= 0`.

Limited monkey used default criteria:

- core net profit must beat constrained random monkey paths at least 90% of the time.
- core max drawdown must beat constrained random monkey paths at least 90% of the time.
- actual trade-path stress must be enabled.
- stressed actual trade paths must be at least 80% profitable.
- stressed actual trade-path median net profit must be positive.
- one-tick-worse slippage path must remain profitable.
- no Apex/flatten rule violations in core or stress paths.

The actual trade-path stress perturbs the realized trade path with:

- 0-1 bar entry delay by default.
- 5% missed trade probability by default.
- 0-1 extra slippage ticks by default.
- entry time-window trim/jitter up to 5 minutes by default.
- pessimistic stop fill when stop and target both touch inside the same stressed bar.

The canonical limited-stage data window was the first 18 months of the
configured core data range unless a different effective stage config was used.

## Post-Fix Effective Behavior

The staged runner was updated after this audit and then realigned to the
2026-06-17 benchmark table. The effective behavior is now:

- run-level `config.yaml` is the canonical effective config actually used by the
  staged runner;
- the original input config is saved as `source_config.yaml`;
- limited core-grid requires valid combo count, at least 70% profitable
  iterations, and no rule violations; it no longer requires at least one
  benchmark-passing parameter set;
- limited core-grid and limited monkey use a seeded random 10% contiguous period
  of available data, avoid the latest 10% holdout, and avoid the configured
  Covid range;
- the limited core-grid benchmark is now a screening benchmark: trade-density,
  drawdown, concentration, and rule-compliance checks are retained, while
  full-stage PF/MAR/expectancy-style gates are reserved for WFA and later;
- full-span absolute trade-count rules are scaled to the actual limited-window
  span;
- limited monkey selects the run closest to median net profit among all
  profitable limited-core rows, then requires the strategy to beat constrained
  random monkey paths at least 90% of the time on both net profit and max
  drawdown;
- WFA OOS monkey and incubation monkey use the same random-monkey beat-rate
  logic with 80% thresholds;
- actual trade-path stress remains written as diagnostic output for missed
  trades, entry delay, worse slippage, time-window trims, and pessimistic
  same-bar stop/target handling, but it is not a default stage gate;
- WFA uses the first 90% of available data with unanchored 4-year IS / 1-year
  OOS windows and max-MAR in-sample selection from rows with trades/year > 50;
- simulated incubation uses latest 1-year OOS after the prior 4-year IS;
- live acceptance uses latest 0.5-year OOS after the prior 2-year IS;
- WFA OOS Monte Carlo defaults to testing chance of $50,000 profit before
  $10,000 drawdown greater than 50%.

## Archived Behavior Observed

Archived campaign configs such as:

- `_archived/campaigns/morning_orderflow_momentum/variants/ES/1m/two_sided_signed_flow_1515_flatten_continuation.yaml`
- `_archived/reports/nq_connors_rsi2_mean_reversion/NQ/databento_nq_1m_20110103_20260529_dominant_session_volume/15m/fifteen_min_long_uptrend_pullback_1559/campaign_tests/config_snapshot.yaml`

used limited core-grid criteria:

- `summary.total_combinations_tested >= 100`.
- `summary.percentage_profitable_iterations >= 0.70`.
- `summary.apex_rule_violating_iterations <= 0`.

They did not require `summary.number_passing_benchmark >= 1` at limited core-grid.

Archived limited monkey criteria observed in those configs required:

- `summary.core_beats_monkey_net_profit_rate >= 0.90`.
- `summary.core_beats_monkey_max_drawdown_rate >= 0.90`.
- `summary.core_metrics.apex_rule_violations <= 0`.

They did not require the separate actual trade-path stress checks in the stage criteria.

Archived limited data windows were configured as deterministic random 18-month windows with seed 31 and pandemic avoid ranges, rather than the current canonical first-18-month window.

## Important False-Negative Risks

1. `number_passing_benchmark >= 1` is a real stricter core-grid gate.

   Example archived NQ Connors run passed limited core grid with 108 combinations and 84.26% profitable iterations, but `number_passing_benchmark` was 0. Under the current default gate, that same run would fail at limited core grid before monkey.

2. Applying full benchmark fields inside a short limited window was too strict.

   If `preferred_min_total_trades` is set for the full research span, requiring a benchmark pass on an 18-month limited window can reject a variant that has enough trades per year but not enough absolute total trades in the short screen.

   Status: fixed. Limited core-grid benchmark pass counting now uses a
   short-window screening benchmark and scales full-span absolute trade-count
   thresholds to the actual limited-stage span.

3. Pre-fix monkey was stricter after the random-monkey comparison.

   Archived configs did not require the actual trade-path stress criteria. A variant can now pass the random monkey comparison and still fail because one-tick-worse slippage, missed trades, entry delay, time-window trim, or pessimistic same-bar fill ordering breaks the result.

   Status: fixed in gate logic. Random monkey/placebo comparisons are the
   benchmark gate again. Actual trade-path stress remains diagnostic output.

4. The old first-18-month limited window could reject regime-dependent edges earlier than the benchmark random-window method.

   Status: fixed. New runs use a seeded random 10% period, avoid the latest 10%
   holdout, and avoid the configured Covid range.

5. The saved `config.yaml` in older run directories may be the source config, not a fully effective canonicalized config.

   The reliable source for what was actually enforced is `stage_result.json`, plus newer summaries containing `resolved_data_subset` and `actual_data_period`.

   Status: fixed for new staged runs. Run-level `config.yaml` is now the
   effective canonical config, and the original input config is saved as
   `source_config.yaml`.

## Current ES Volume Shock Campaign Check

For `backtest-campaigns/es_volume_shock_liquidity_reversal`, all original and rescue variants failed before monkey. Their limited core-grid profitable-combo rates ranged from 0.0 to about 0.21, far below the 0.70 gate.

This specific campaign was not blocked by a borderline monkey change. It failed the broad profitability requirement directly.

The removed benchmark-pass gate also would not change the decision for this
campaign because the profitable-combo rate was already much too low.

## Conclusion

Yes, the pre-fix limited core-grid and monkey gates were stricter than the archived configs in ways that could stop variants earlier:

- core grid could require at least one full benchmark-passing parameter set;
- monkey included actual trade-path stress gates beyond the random-placebo gate;
- limited-stage window selection had drifted to first-18-month behavior rather
  than the benchmark random-window method;
- older run configs are not always a complete record of canonicalized effective criteria.

But for the active `es_volume_shock_liquidity_reversal` failures, these differences do not explain the rejection. Those variants failed because the core grid had very low profitable-combo rates, not because monkey or a borderline benchmark rule stopped them.

Fix status:

- effective canonical config snapshots are written for new runs;
- actual limited-stage windows are documented in stage summaries;
- limited core-grid now uses the benchmark-table 70% profitable-combo gate
  without requiring a benchmark-passing combo;
- limited monkey, WFA OOS monkey, and incubation monkey now use benchmark-table
  random beat-rate gates;
- trade-path stress remains enabled as diagnostic output;
- WFA, simulated incubation, and acceptance train-selection now reject or
  early-exit when no parameter row satisfies the configured selection filters,
  including the benchmark-table `trades/year > 50` train-selection rule.
