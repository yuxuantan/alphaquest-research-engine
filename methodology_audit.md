# Futures Backtest Methodology Audit

Audit date: 2026-06-18

Overall status: FAIL

Reason: the engine/preflight path now passes focused sanity checks, but no ES
strategy candidate in the active search passed the corrected staged methodology.
The latest completed price-action plus aggregate-orderflow campaign,
`es_trend_filtered_prior_session_breakout_orderflow`, failed before monkey/WFA under the
corrected objective gates. The completed per-failed-variant rescue attempts also
failed limited core.

## Engine And Methodology Fixes

- Point value handling: `BacktestEngine`, monkey trade-log construction, and Monte Carlo prop-rule sizing now derive `tick_value` from `core.point_value * core.tick_size` when `core.tick_value` is absent. This closes the preflight/engine mismatch where non-ES configs could be accepted but valued with ES's default tick value.
- Benchmark-table alignment: staged campaign defaults now match the 2026-06-17 benchmark sheet. Limited core uses a seeded random 10% contiguous period, excludes the latest 10% holdout, and avoids the configured Covid range. WFA uses the first 90% of available data with unanchored 4-year IS / 1-year OOS windows. Simulated incubation uses latest 1-year OOS after 4-year IS, and live acceptance uses latest 0.5-year OOS after 2-year IS.
- Monkey gate: limited monkey now selects the core-grid run closest to the median net profit among all profitable core-grid runs, then requires random-monkey beat rates of at least 90% for net profit and max drawdown. WFA OOS and incubation monkey require at least 80% for the same two beat rates.
- Actual trade-path stress: monkey stages still write `trade_path_stress_results.csv` / `trade_path_stress_summary.json` for missed trades, entry delay, one-tick worse slippage, time-window trims, and pessimistic same-bar stop/target handling. These outputs are diagnostic unless explicitly added as a separate criterion.
- WFA gate: staged WFA now checks no early exit, stitched OOS PF >= 1.2, MAR >= 0.4, trades/year >= 50, and zero Apex/flatten rule violations. In-sample selection is max MAR from rows with trades/year > 50, with early exit if the selected in-sample PF is below 1.0.
- Monte Carlo gate: WFA OOS Monte Carlo now defaults to the benchmark-sheet prop-style test of chance of $50,000 profit before $10,000 drawdown greater than 50%, unless an explicit stage prop-rule override is supplied.
- WFA OOS Monte Carlo rule assembly: the default benchmark-sheet MC gate no longer silently inherits tighter top-level `prop_rules.daily_loss_limit` or `prop_rules.trailing_drawdown`; it inherits account size and contract cap, sets the default profit target and drawdown budget to `$50,000` / `$10,000`, and still allows explicit `monte_carlo.prop_rules` or stage-level `prop_rules` to tighten the test deliberately.
- Incubation and acceptance gates: simulated incubation and acceptance now check OOS PF >= 1.0, MAR >= 1.0, trades/year >= 50, and zero Apex/flatten rule violations.
- Connors RSI2 preflight: `BacktestEngine` now warns when `connors_rsi2_mean_reversion` requests a VWAP trend/extension filter but the prepared data lacks `vwap`.
- Fixed-combo handling: staged core-grid criteria now accept exactly one combination only when the strategy declares no tunable parameters; tunable grids still must stay in the 8 to 120 combination range.
- Variants index hardening: campaign variant metadata updates now use a lock-protected atomic writer, preventing concurrent staged runs from corrupting `variants_index.yaml`.
- Overnight reversal preflight: `BacktestEngine` now warns when `overnight_intraday_reversal` is run without the prior-RTH close feature required to compute the close-to-open gap.

## Verified Controls

- Bar-close signals enter no earlier than the next bar open.
- Same-bar stop/target conflicts fall back to stop-first pessimistic handling when no detail data resolves order.
- Commission, slippage, tick size, point value, and tick value are explicit and tested.
- Apex/prop-style forced flatten, latest-entry, no-overnight, and pending-order cancellation diagnostics are config driven.
- Preflight fails closed on missing timezone, duplicate bars, missing forced-flatten config, parameter-count violations, and excessive parameter combinations.
- Rescue governance now scopes rescues to a failed variant: each failed variant can use at most one logged rescue, and rescues may change only existing fixed parameters or tunable parameter space inside existing modules.
- Minimum target reward:risk: after the 2026-06-20 correction, any `target_r_multiple` below `1.0` is invalid. TP-floor rescues may only raise sub-1R targets to `1.0R`; targets already at or above `1.0R` must not be widened merely to improve results. Preflight, core-grid parameter expansion, engine construction, fixed-R target modules, and the TP-floor rescue generator enforce this fail-closed rule, including WFA parameter sections.
- Active config RR-floor sweep: on 2026-06-20, active source YAML under
  `campaigns/` was mechanically floored so `target_r_multiple < 1.0` no longer
  appears in strategy, core-grid, WFA, or campaign parameter-space definitions.
  Values already at or above `1.0R` were left unchanged; duplicate grid values
  created by flooring were deduplicated rather than replaced with wider targets.
  Historical generated `backtest-campaigns/` artifacts were not rewritten or
  reinterpreted. Audit artifact:
  `research_artifacts/target_rr_floor_active_config_audit_20260620.md`.
- Preflight source scope: default preflight discovery now checks authored active
  configs only, including `campaigns/**/variants/**/config.yaml`,
  `campaigns/**/rescue_attempts/**/config.yaml`, and
  `configs/campaigns/**/*.yaml`. Generated historical snapshots under
  `backtest-campaigns/` are opt-in via `--include-generated-results` so old
  evidence remains immutable while future executable configs fail closed.
- Composite-edge governance: after explicit user approval on 2026-06-17,
  future campaigns may combine one primary edge with at most two independently
  justified secondary conditions, such as a fixed multi-timeframe direction
  filter. The staged benchmarks are unchanged. A new filter cannot be added as
  a rescue after a failed run; it must be logged as a new composite campaign
  with a predeclared thesis, density audit, duplicate check, and unchanged
  tunable caps. Policy artifact:
  `research_artifacts/composite_edge_policy_20260617.md`.
- Price-action/orderflow routing: after the 2026-06-17 user priority update,
  prefer ES campaigns where price action defines the setup and Sierra aggregate
  orderflow acts as confirmation, exhaustion, or dislocation evidence.
  Deprioritize pure signed-flow or large-flow retiming unless the independent
  price-action thesis is strong, non-duplicate, and likely to satisfy the
  50-trades/year benchmark before PnL testing. No paid market data may be
  downloaded or refreshed without explicit approval for that specific pull.
- Pre-test variant mechanics review: new variant configs created after
  2026-06-17 must document how entry, stop, and target express the edge and why
  the mechanics are convincing enough to test. If the mechanics are not
  convincing before results, reformulate before testing. The staged campaign
  runner now fails before creating a run when the review is absent or lacks
  `pre_test_decision: approve_for_testing`; preflight also enforces the review
  when `research_metadata.mechanics_review_required` is set. Policy artifact:
  `research_artifacts/pretest_variant_mechanics_review_policy_20260617.md`.
- Core-grid density diagnostics: core-grid rows now include
  `signals_generated`, `entries_opened`, `trades_closed`, and rejection counts.
  `core_grid_summary.json` now includes `signal_density` so zero-signal or
  zero-trade parameter spaces are explicitly documented as mechanics/density
  failures before interpreting PnL. This does not change benchmark-table stage
  gates or rescue eligibility.

## Campaign Results

### `es_default_spread_orderflow_risk_premium`

Decision: FAIL.

- Added active bounded-composite campaign using only free local FRED DAAA/DBAA
  CSVs plus the local Sierra ES RTH aggregate-orderflow cache. No paid data was
  downloaded. The abandoned BAML/OAS file was data-gated as too short for the
  full WFA workflow.
- Edge distinction: the primary regime is the long-history Moody's
  Baa-minus-Aaa default spread with a conservative two-business-day availability
  lag; ES entries require completed same-day price movement and aggregate
  signed/large-trade orderflow confirmation. This is distinct from the active
  OFR financial-stress and Treasury-rate campaigns.
- Added `tools/build_es_default_spread_features.py` and entry module
  `src/propstack/strategy_modules/entry/default_spread_orderflow_state.py`,
  registered the module, and added focused unit tests. Signals use completed
  5-minute RTH bars and engine entry remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `high_spread_signed_long_1230`, `high_spread_large10_long_1230`,
  `widening_spread_signed_short_1230`,
  `tightening_spread_signed_long_1130`, and
  `two_sided_spread_change_large10_1130`.
- Pre-PnL density audit:
  `research_artifacts/es_default_spread_orderflow_risk_premium_density_audit_20260620.md`.
  All five retained variants exceeded the 50-trades/year density screen in both
  full-period and limited-core reference windows before any PnL testing.
- Originals: all five failed `limited_core_grid_test`. Best original was
  `high_spread_signed_long_1230/run1`, with profitable-combo rate
  `0.2222222222222222`, one benchmark-pass combination, top net `1412.5`,
  PF `1.120085015940489`, MAR `0.599733288512176`, and
  `89.87130716309187` top-combo trades/year.
- Rescues: all five failed variants received exactly one parameter-space/fixed
  parameter rescue preserving edge thesis, entry module, stop module, target
  module, target grid, timeframe, data, costs, fills, sessions, prop rules, and
  validation gates. TP was not widened because every `target_r_multiple` was
  already at least `1.0R`. All five rescues failed `limited_core_grid_test`.
  Best rescue was `high_spread_signed_long_1230/rescue1`, with
  profitable-combo rate `0.49382716049382713`, eight benchmark-pass
  combinations, top net `1817.5`, PF `1.1873228549342953`, MAR
  `0.6212976671933912`, and `93.18939427835099` top-combo trades/year.
- Aggregate artifacts:
  `backtest-campaigns/es_default_spread_orderflow_risk_premium/campaign_test_summary.json`,
  `backtest-campaigns/es_default_spread_orderflow_risk_premium/campaign_results.csv`,
  `backtest-campaigns/es_default_spread_orderflow_risk_premium/trade_logs_manifest.csv`,
  `backtest-campaigns/es_default_spread_orderflow_risk_premium/equity_curves_manifest.csv`,
  `backtest-campaigns/es_default_spread_orderflow_risk_premium/wfa_table.csv`,
  and
  `backtest-campaigns/es_default_spread_orderflow_risk_premium/monte_carlo_summary.csv`.
- Verification:
  `PYTHONPATH=src:. python3 -m pytest tests/test_default_spread_orderflow_state.py
  tests/test_tp_widen_best_core_rescues.py
  tests/test_preflight.py::test_preflight_rejects_target_r_multiple_below_one
  tests/test_core_grid.py::test_parameter_combinations_rejects_target_r_multiple_below_one
  tests/test_backtest_engine.py::test_backtest_engine_rejects_target_r_multiple_below_one -q`
  PASS; targeted preflight for five originals PASS; targeted preflight for five
  rescues PASS; active source RR sweep found zero sub-1R target violations.
- Decision: FAIL. No run reached limited monkey, WFA, WFA OOS monkey, Monte
  Carlo, simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.

### `es_trend_filtered_prior_session_breakout_orderflow`

Decision: FAIL.

- Added active constrained composite campaign
  `es_trend_filtered_prior_session_breakout_orderflow` using only the local
  Sierra ES RTH aggregate-orderflow cache. No paid data was downloaded.
- Edge distinction: a signal requires completed acceptance outside a public
  prior RTH high or low, deterministic completed-bar market-structure trend
  alignment, and same-bar aggregate orderflow confirmation. Neither prior-level
  breakout/orderflow nor generic trend-aligned orderflow alone can trigger.
- Added entry module
  `src/propstack/strategy_modules/entry/pdh_pdl_trend_orderflow_breakout_continuation.py`
  plus registration, engine required-column checks, and focused unit tests.
  Signals use completed 5-minute bars and engine entry remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `first_half_signed_trend_hold_two_sided`,
  `first_half_large10_trend_hold_two_sided`,
  `all_day_signed_trend_hold_two_sided`,
  `all_day_large10_trend_hold_two_sided`, and
  `all_day_signed_high_volume_trend_hold_two_sided`.
- Pre-PnL density audit:
  `research_artifacts/es_trend_filtered_prior_session_breakout_orderflow_density_audit_20260618.md`.
  A stricter fresh first-break/retest formulation was rejected before PnL because
  all five variants produced only `5.39` to `36.39` signals/year on the
  limited-core window. The retained hold/acceptance formulation cleared the
  density floor in every declared entry-grid corner; minimum limited-core
  density ranged from `161.04` to `196.75` signals/year by variant.
- Originals: all five failed `limited_core_grid_test` with `0.0`
  profitable-combo rate. Best original was
  `first_half_signed_trend_hold_two_sided/run1`, with top net `-4866.25`,
  PF `0.63799516458992`, and `163.79680789930606` top-combo trades/year.
- Rescues: all five failed variants received exactly one parameter-space/fixed
  parameter rescue preserving edge thesis, entry module, stop module, target
  module, timeframe, data, costs, fills, sessions, prop rules, and validation
  gates. All five rescues failed `limited_core_grid_test`. Best rescue was
  `all_day_large10_trend_hold_two_sided/rescue1`, with profitable-combo rate
  `0.012345679012345678`, zero benchmark-pass combinations, top net `1052.5`,
  PF `1.0401449413559645`, MAR `0.16586554200022113`, and
  `122.81112803735982` top-combo trades/year. The top rescue also failed profit
  concentration with best-day concentration `0.7672209026128266`.
- Aggregate artifacts:
  `backtest-campaigns/es_trend_filtered_prior_session_breakout_orderflow/campaign_test_summary.json`,
  `backtest-campaigns/es_trend_filtered_prior_session_breakout_orderflow/campaign_results.csv`,
  `backtest-campaigns/es_trend_filtered_prior_session_breakout_orderflow/wfa_table.csv`,
  `backtest-campaigns/es_trend_filtered_prior_session_breakout_orderflow/monte_carlo_summary.json`,
  and
  `research_artifacts/es_trend_filtered_prior_session_breakout_orderflow_rescue_attempt_1_20260618.md`.
- Verification:
  `PYTHONPATH=src python3 -m pytest tests/test_pdh_pdl_trend_orderflow_breakout_continuation.py -q`
  PASS; `PYTHONPATH=src python3 -m research.preflight --skip-tests --config
  <five original configs>` PASS; `PYTHONPATH=src python3 -m research.preflight
  --skip-tests --config <five rescue configs>` PASS.
- Decision: FAIL. No run reached limited monkey, WFA, WFA OOS monkey, Monte
  Carlo, simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.

### `es_session_open_orderflow_reclaim`

Decision: FAIL.

- Added active price-action plus aggregate-orderflow campaign
  `es_session_open_orderflow_reclaim` using only the local Sierra ES RTH
  1-minute aggregate-orderflow cache. No paid data was downloaded.
- Edge distinction: the reference level is the current RTH open itself, known
  from the first regular-session bar. The setup requires a prior completed
  excursion away from that open, then a completed reclaim/rejection back through
  it with same-direction aggregate orderflow confirmation. It is not prior-close
  gap fade, opening-range breakout/retest, opening-drive state, overnight
  high/low, VWAP, prior-day level, round-number, or session-extreme divergence.
- Added entry module
  `src/propstack/strategy_modules/entry/session_open_orderflow_reclaim.py`
  plus registration, engine feature-column checks, and focused unit tests.
  Signals use completed 1-minute bars and engine entry remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `morning_down_open_reclaim_long`, `morning_up_open_reject_short`,
  `midday_large10_two_sided_open_reclaim`,
  `afternoon_large20_down_open_reclaim_long`, and
  `afternoon_large20_up_open_reject_short`.
- Pre-PnL density audit:
  `research_artifacts/es_session_open_orderflow_reclaim_density_audit_20260618.md`.
  All five variants exceeded the 50 trades/year feasibility floor at every
  declared entry-grid corner in both the benchmark limited-core window and the
  full local history before any PnL was inspected.
- Originals: all five failed `limited_core_grid_test`. Best original was
  `morning_down_open_reclaim_long/run1`, with profitable-combo rate
  `0.012345679012345678`, zero benchmark-pass combinations, top net `50.0`,
  PF `1.0062034739454093`, and `74.87188247352238` top-combo trades/year.
- Rescues: all five failed variants received exactly one parameter-space/fixed
  parameter rescue preserving edge thesis, entry module, stop module, target
  module, timeframe, data, costs, fills, sessions, prop rules, and validation
  gates. All five rescues failed `limited_core_grid_test`. Best rescue was
  `morning_up_open_reject_short/rescue1`, with profitable-combo rate
  `0.09876543209876543`, two benchmark-pass combinations, top net `1572.5`,
  PF `1.1076870398904297`, MAR `0.3769003758047812`, and
  `89.84681505285035` top-combo trades/year. The robust-combo rate remained far
  below the required `0.70`.
- Aggregate artifacts:
  `backtest-campaigns/es_session_open_orderflow_reclaim/campaign_test_summary.json`,
  `backtest-campaigns/es_session_open_orderflow_reclaim/campaign_results.csv`,
  `backtest-campaigns/es_session_open_orderflow_reclaim/wfa_table.csv`,
  `backtest-campaigns/es_session_open_orderflow_reclaim/monte_carlo_summary.json`,
  and
  `research_artifacts/es_session_open_orderflow_reclaim_rescue_attempt_1_20260618.md`.
- Verification:
  `PYTHONPATH=src python3 -m pytest tests/test_session_open_orderflow_reclaim.py tests/test_campaign_stages.py::test_staged_campaign_requires_pre_test_mechanics_review tests/test_campaign_stages.py::test_canonicalized_stage_windows_match_shortlist_and_wfa_benchmarks -q`
  PASS; `PYTHONPATH=src python3 -m research.preflight --skip-tests --config
  <five original configs>` PASS; `PYTHONPATH=src python3 -m research.preflight
  --skip-tests --config <five rescue configs>` PASS.
- Decision: FAIL. No run reached limited monkey, WFA, WFA OOS monkey, Monte
  Carlo, simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.

### `es_session_extreme_delta_divergence`

Decision: FAIL.

- Added active price-action plus aggregate-orderflow campaign
  `es_session_extreme_delta_divergence` using only the local Sierra ES RTH
  1-minute aggregate-orderflow cache. No paid data was downloaded.
- Edge distinction: price must make a fresh current-session RTH high or low
  using only prior completed bars as the reference extreme. Aggregate orderflow
  is used only to test whether cumulative signed-volume progress from that
  prior completed extreme fails to confirm the price extension. This is not
  fixed-time orderflow effort ranking, rolling-window sweep/reclaim,
  opening-drive inventory, prior-day levels, VWAP, round numbers, or MES/NQ
  relative value.
- Added entry module
  `src/propstack/strategy_modules/entry/session_extreme_delta_divergence.py`
  plus registration, engine feature-column checks, and focused unit tests.
  Signals use completed 1-minute bars and engine entry remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `morning_high_delta_divergence_short`,
  `morning_low_delta_divergence_long`,
  `midday_two_sided_delta_divergence`,
  `afternoon_high_delta_divergence_short`, and
  `afternoon_low_delta_divergence_long`.
- Pre-PnL density audit:
  `research_artifacts/es_session_extreme_delta_divergence_density_audit_20260618.md`.
  A stricter 2.5% delta-progress threshold was rejected before PnL because one
  afternoon-low corner fell below the 50 signals/year density target in the
  limited-core window. The retained original grids used 36 combinations per
  variant and all declared entry-grid corners cleared the density target.
- Originals: all five failed `limited_core_grid_test` with `0.0`
  profitable-combo rate. Best original was
  `afternoon_high_delta_divergence_short/run1`, with top net `-1889.375`,
  PF `0.7441604603926879`, and `70.25693694465693` top-combo trades/year.
- Rescues: all five failed variants received exactly one parameter-space/fixed
  parameter rescue preserving edge thesis, entry module, stop module, target
  module, direction, timeframe, data, costs, fills, sessions, prop rules, and
  validation gates. The rescue made the same failed-extreme mechanic stricter
  by removing 1-tick probes, tightening close-to-extreme tolerance, and shifting
  only the existing stop grid wider. All five rescues failed
  `limited_core_grid_test`. Best rescue was
  `afternoon_low_delta_divergence_long/rescue1`, with profitable-combo rate
  `0.1111111111111111`, zero benchmark-pass combinations, top net `785.0`,
  PF `1.0930646117368108`, and `55.31419274644488` top-combo trades/year.
- Aggregate artifacts:
  `backtest-campaigns/es_session_extreme_delta_divergence/campaign_test_summary.json`,
  `backtest-campaigns/es_session_extreme_delta_divergence/campaign_results.csv`,
  `backtest-campaigns/es_session_extreme_delta_divergence/wfa_table.csv`,
  `backtest-campaigns/es_session_extreme_delta_divergence/monte_carlo_summary.json`,
  and
  `research_artifacts/es_session_extreme_delta_divergence_rescue_attempt_1_20260618.md`.
- Verification:
  `PYTHONPATH=src python3 -m pytest tests/test_session_extreme_delta_divergence.py tests/test_campaign_stages.py::test_canonicalized_stage_windows_match_shortlist_and_wfa_benchmarks -q`
  PASS; `PYTHONPATH=src python3 -m research.preflight --skip-tests --config
  <five original configs>` PASS; `PYTHONPATH=src python3 -m research.preflight
  --skip-tests --config <five rescue configs>` PASS.
- Decision: FAIL. No run reached limited monkey, WFA, WFA OOS monkey, Monte
  Carlo, simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.

### `es_daily_reversal_orderflow_confirmation`

Decision: FAIL.

- Added active constrained composite campaign
  `es_daily_reversal_orderflow_confirmation` using only the local Sierra ES RTH
  aggregate-orderflow cache. No paid data was downloaded.
- Edge distinction: the primary edge is daily short-term return reversal; the
  secondary condition is fixed completed rolling signed-volume imbalance in the
  contrarian/reversal direction at a predeclared intraday checkpoint. This is
  not the raw daily reversal campaign, standalone signed-flow persistence,
  VWAP pullback continuation, or trend-aligned orderflow continuation.
- Added entry module
  `src/propstack/strategy_modules/entry/daily_reversal_orderflow_confirmation.py`
  plus registration, engine feature-column checks, and focused unit tests.
  Signals use completed 5-minute bars and engine entry remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `first60_1d_flow_confirm_1030`, `first90_2d_flow_confirm_1100`,
  `first120_3d_flow_confirm_1130`, `first150_5d_flow_confirm_1200`, and
  `afternoon90_1d_flow_confirm_1400`.
- Pre-PnL density audit:
  `research_artifacts/es_daily_reversal_orderflow_confirmation_density_audit_20260618.md`.
  The initial strict absorption formulation was rejected before PnL for sparse
  density. The final retained five variants cleared at least 55.5 signals/year
  across declared original entry-grid corners.
- Originals: all five failed `limited_core_grid_test`.
- Rescues: all five failed variants received exactly one parameter-space/fixed
  parameter rescue preserving edge thesis, entry module, stop module, target
  module, timeframe, data, costs, fills, sessions, prop rules, and validation
  gates. Rescue entry-grid density stayed at or above 51.1 signals/year.
  All five rescues failed `limited_core_grid_test`.
- Aggregate artifacts:
  `backtest-campaigns/es_daily_reversal_orderflow_confirmation/campaign_test_summary.json`,
  `backtest-campaigns/es_daily_reversal_orderflow_confirmation/campaign_results.csv`,
  `backtest-campaigns/es_daily_reversal_orderflow_confirmation/wfa_table.csv`,
  `backtest-campaigns/es_daily_reversal_orderflow_confirmation/monte_carlo_summary.json`,
  and
  `research_artifacts/es_daily_reversal_orderflow_confirmation_rescue_attempt_1_20260618.md`.
- Decision: FAIL. No run reached limited monkey, WFA, WFA OOS monkey, Monte
  Carlo, simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.

### `es_rolling_range_orderflow_sweep_reversal`

Decision: FAIL.

- Added active bounded composite campaign `es_rolling_range_orderflow_sweep_reversal`
  using only the local Sierra ES RTH 1-minute aggregate-orderflow cache. No paid
  data was downloaded.
- Edge distinction: the setup uses current-session rolling highs/lows built only
  from prior completed bars, then fades a completed sweep and reclaim when
  aggregate orderflow shows pressure into the failed sweep. It is not prior-day
  stop-run reclaim, opening-range failed breakout, round-number reaction, or
  standalone orderflow absorption.
- Added entry module
  `src/propstack/strategy_modules/entry/rolling_range_orderflow_sweep_reversal.py`
  plus registration and engine feature-column checks. Signals use completed
  5-minute bars and engine entry remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `morning_signed_12bar_sweep_reclaim_1130`,
  `morning_large10_12bar_sweep_reclaim_1130`,
  `midday_signed_24bar_sweep_reclaim_1400`,
  `afternoon_signed_24bar_sweep_reclaim_1500`, and
  `all_day_large20_36bar_sweep_reclaim_1500`.
- Density audit:
  `research_artifacts/es_rolling_range_orderflow_sweep_reversal_density_audit_20260617.md`.
  All declared variants exceeded the 50 signals/year pre-PnL density target at
  the strictest declared entry-grid corners.
- Originals: all five failed `limited_core_grid_test`.
- Rescues: all five failed variants received exactly one parameter-space/fixed
  parameter rescue preserving edge thesis, entry module, stop module, target
  module, timeframe, data, costs, fills, sessions, prop rules, and validation
  gates. All five rescues failed `limited_core_grid_test`.
- Best rescue was `afternoon_signed_24bar_sweep_reclaim_1500/rescue1`, with top
  net `675.0`, PF `1.4272151898734178`, MAR `1.107462152425031`, but only
  22.270712773465068 trades/year; it failed the trade-count gates and only
  0.037037037037037035 of combinations were profitable.
- Aggregate artifacts:
  `backtest-campaigns/es_rolling_range_orderflow_sweep_reversal/campaign_test_summary.json`,
  `backtest-campaigns/es_rolling_range_orderflow_sweep_reversal/campaign_results.csv`,
  `backtest-campaigns/es_rolling_range_orderflow_sweep_reversal/wfa_table.csv`,
  `backtest-campaigns/es_rolling_range_orderflow_sweep_reversal/monte_carlo_summary.json`,
  and
  `research_artifacts/es_rolling_range_orderflow_sweep_reversal_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached limited monkey, WFA, WFA OOS monkey, Monte
  Carlo, simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.

### `es_prior_session_breakout_orderflow_confirmation`

Decision: FAIL.

- Added active bounded composite campaign
  `es_prior_session_breakout_orderflow_confirmation` using only the local
  Sierra ES RTH 1-minute aggregate-orderflow cache. No paid data was downloaded.
- Edge distinction: the setup requires a fresh completed break/acceptance beyond
  the prior RTH high or low plus same-bar aggregate orderflow confirmation. It
  is not the failed price-only prior-session breakout campaign, and it is not
  the failed prior-level delta-dislocation campaign because price and flow must
  align rather than diverge.
- Added entry module
  `src/propstack/strategy_modules/entry/pdh_pdl_orderflow_breakout_continuation.py`
  plus registration and engine feature-column checks. Signals use completed
  5-minute bars and engine entry remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `all_day_signed_buffer_break_two_sided`,
  `all_day_large10_buffer_break_two_sided`,
  `all_day_large20_no_buffer_break_two_sided`,
  `first_half_signed_no_buffer_break_two_sided`, and
  `all_day_signed_high_volume_break_two_sided`.
- Density audit:
  `research_artifacts/es_prior_session_breakout_orderflow_confirmation_density_audit_20260617.md`.
  Two initially drafted sparse variants were reformulated before PnL; the final
  five variants all exceeded the 50 signals/year pre-PnL density target at the
  strictest declared entry-grid corners.
- Originals: all five failed `limited_core_grid_test`.
- Rescues: all five failed variants received exactly one parameter-space/fixed
  parameter rescue preserving edge thesis, entry module, stop module, target
  module, timeframe, data, costs, fills, sessions, prop rules, and validation
  gates. Four rescues failed `limited_core_grid_test`.
- Strongest rescue was `first_half_signed_no_buffer_break_two_sided/rescue1`.
  It passed `limited_core_grid_test` with 0.8055555555555556 profitable-combo
  rate and passed `limited_monkey_test` with net-profit beat rate `0.96` and
  max-drawdown beat rate `0.99`.
- WFA failure: `first_half_signed_no_buffer_break_two_sided/rescue1` failed the
  first WFA window by early exit because selected in-sample PF was
  `0.887903893951947`, below the configured `1.0` threshold. No OOS trades were
  stitched.
- Aggregate artifacts:
  `backtest-campaigns/es_prior_session_breakout_orderflow_confirmation/campaign_test_summary.json`,
  `backtest-campaigns/es_prior_session_breakout_orderflow_confirmation/campaign_results.csv`,
  `backtest-campaigns/es_prior_session_breakout_orderflow_confirmation/wfa_table.csv`,
  `backtest-campaigns/es_prior_session_breakout_orderflow_confirmation/trade_logs_manifest.csv`,
  `backtest-campaigns/es_prior_session_breakout_orderflow_confirmation/equity_curves_manifest.csv`,
  `backtest-campaigns/es_prior_session_breakout_orderflow_confirmation/monte_carlo_summary.json`,
  and
  `research_artifacts/es_prior_session_breakout_orderflow_confirmation_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached WFA OOS monkey, WFA OOS Monte Carlo,
  simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.

### `es_opening_range_trend_orderflow_breakout`

Decision: FAIL.

- Added active bounded composite campaign
  `es_opening_range_trend_orderflow_breakout` using only the local Sierra ES RTH
  1-minute aggregate-orderflow cache. No paid data was downloaded.
- Edge distinction: the setup requires a completed opening-range breakout, a
  completed multi-horizon intraday price-action trend filter, and same-bar
  aggregate orderflow confirmation. This is not a rescue of the failed plain
  ORB/orderflow campaign because price structure is a mandatory predeclared
  condition.
- Added entry module
  `src/propstack/strategy_modules/entry/opening_range_trend_orderflow_breakout.py`
  plus registration and engine feature-column checks. Signals use completed
  5-minute bars and engine entry remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `or15_signed_trend_breakout_1030`,
  `or15_large10_trend_breakout_1030`,
  `or30_signed_trend_breakout_1100`,
  `or30_large20_trend_breakout_1130`, and
  `or60_signed_trend_breakout_1200`.
- Density audit:
  `research_artifacts/es_opening_range_trend_orderflow_breakout_density_audit_20260617.md`.
  All declared original and rescue variants exceeded the 50 trades/year
  pre-PnL density target at the tested corners.
- Originals: all five failed `limited_core_grid_test` with `0.0`
  profitable-combo rate despite adequate limited-window trade density.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving edge thesis, entry module, stop module, target module,
  timeframe, data, costs, fills, sessions, prop rules, and validation gates. All
  five rescues also failed `limited_core_grid_test` with `0.0`
  profitable-combo rate.
- Best run was `or60_signed_trend_breakout_1200/run1`, with top net `-3025.0`,
  PF `0.8567029843675983`, MAR `-0.5208616723709634`, expectancy R
  `-0.06000630710451231`, and 98.17265515632292 trades/year.
- Aggregate artifacts:
  `backtest-campaigns/es_opening_range_trend_orderflow_breakout/campaign_test_summary.json`,
  `backtest-campaigns/es_opening_range_trend_orderflow_breakout/campaign_results.csv`,
  `backtest-campaigns/es_opening_range_trend_orderflow_breakout/wfa_table.csv`,
  `backtest-campaigns/es_opening_range_trend_orderflow_breakout/monte_carlo_summary.json`,
  and
  `research_artifacts/es_opening_range_trend_orderflow_breakout_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached limited monkey, WFA, WFA OOS monkey, Monte
  Carlo, simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.

### `es_midday_range_orderflow_breakout`

Decision: FAIL.

- Added active bounded composite campaign `es_midday_range_orderflow_breakout`
  using only the local Sierra ES RTH 1-minute aggregate-orderflow cache. No paid
  data was downloaded.
- Edge distinction: the price-action boundary is a completed midday/lunch range,
  with completed-bar aggregate orderflow used only as breakout confirmation. It
  is not an opening-range breakout, prior-session level breakout, NR4
  compression setup, VWAP pullback, or standalone signed-flow impulse.
- Added entry module
  `src/propstack/strategy_modules/entry/intraday_range_orderflow_breakout.py`
  plus registration and engine feature-column checks. Signals use completed
  5-minute bars and engine entry remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `lunch_1130_1300_signed_breakout_1430`,
  `lunch_1130_1300_large10_breakout_1430`,
  `lunch_1130_1300_large20_breakout_1430`,
  `late_lunch_1200_1330_signed_breakout_1500`, and
  `late_lunch_1200_1330_large10_breakout_1500`.
- Density audit:
  `research_artifacts/es_midday_range_orderflow_breakout_density_audit_20260617.md`.
  Wider 11:00-13:00 range variants and directional-only ideas were rejected
  before PnL where strict corners risked falling below 50 trades/year.
- Originals: all five failed `limited_core_grid_test` with `0.0`
  profitable-combo rate despite adequate limited-window trade density.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving edge thesis, entry module, stop module, target module,
  timeframe, data, costs, fills, sessions, prop rules, and validation gates. All
  five rescues also failed `limited_core_grid_test` with `0.0`
  profitable-combo rate.
- Best rescue was `lunch_1130_1300_large20_breakout_1430/rescue1`, with top net
  `-2433.75`, PF `0.8948704103671706`, MAR `-0.3417525557764132`, and
  145.69529085872577 trades/year.
- Aggregate artifacts:
  `backtest-campaigns/es_midday_range_orderflow_breakout/campaign_test_summary.json`,
  `backtest-campaigns/es_midday_range_orderflow_breakout/campaign_results.csv`,
  `backtest-campaigns/es_midday_range_orderflow_breakout/wfa_table.csv`,
  `backtest-campaigns/es_midday_range_orderflow_breakout/monte_carlo_summary.json`,
  and
  `research_artifacts/es_midday_range_orderflow_breakout_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached limited monkey, WFA, WFA OOS monkey, Monte
  Carlo, simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.

### `es_opening_range_retest_orderflow`

Decision: FAIL.

- Added active bounded composite campaign `es_opening_range_retest_orderflow`
  using only the local Sierra ES RTH 1-minute aggregate-orderflow cache. No paid
  data was downloaded.
- Edge distinction: the signal requires a completed opening-range breakout, then
  a later retest that holds the broken opening-range boundary with aggregate
  orderflow confirmation. This is not immediate OR breakout continuation and not
  failed-breakout reclaim back inside the range.
- Added entry module
  `src/propstack/strategy_modules/entry/opening_range_retest_orderflow.py` and
  stop module
  `src/propstack/strategy_modules/sl/opening_range_retest_boundary.py`, plus
  registration and engine feature-column checks. Signals use completed
  5-minute bars and engine entry remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `or15_signed_absorption_retest_1030`,
  `or15_signed_aligned_retest_1030`,
  `or30_signed_absorption_retest_1100`,
  `or30_large10_absorption_retest_1130`, and
  `or60_large20_aligned_retest_1230`.
- Density audit:
  `research_artifacts/es_opening_range_retest_orderflow_density_audit_20260617.md`.
  Directional OR15 variants were rejected before PnL as too sparse; every final
  declared two-sided entry corner exceeded 50 signals/year before PnL testing.
- Verification before staged runs:
  `PYTHONPATH=src python3 -m pytest tests/test_opening_range_retest_orderflow.py tests/test_opening_range_orderflow_breakout.py tests/test_opening_range_failed_breakout_orderflow.py tests/test_core_grid.py tests/test_campaign_stages.py tests/test_preflight.py -q`
  passed 67 tests; targeted preflight for the five originals and five rescues
  passed.
- Originals: all five failed `limited_core_grid_test` with `0.0`
  profitable-combo rate despite adequate limited-window trade density.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving edge thesis, entry module, stop module, target module,
  timeframe, data, costs, fills, sessions, prop rules, and validation gates. All
  five rescues also failed `limited_core_grid_test`.
- Best rescue was `or30_large10_absorption_retest_1130/rescue1`, with
  0.024691358024691357 profitable-combo rate, one benchmark-passing combination,
  top net `1184.375`, PF `1.083494888967219`, and 105.1026627366738
  trades/year, far below the 70% profitable-combo robustness gate.
- Aggregate artifacts:
  `backtest-campaigns/es_opening_range_retest_orderflow/campaign_test_summary.json`,
  `backtest-campaigns/es_opening_range_retest_orderflow/campaign_results.csv`,
  `backtest-campaigns/es_opening_range_retest_orderflow/wfa_table.csv`,
  `backtest-campaigns/es_opening_range_retest_orderflow/monte_carlo_summary.json`,
  and
  `research_artifacts/es_opening_range_retest_orderflow_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached limited monkey, WFA, WFA OOS monkey, Monte
  Carlo, simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.

### `es_round_number_orderflow_barrier`

Decision: FAIL.

- Added active bounded composite campaign `es_round_number_orderflow_barrier`
  using only the local Sierra ES RTH 1-minute aggregate-orderflow cache. No paid
  data was downloaded.
- Edge distinction: fixed psychological round-number barriers are traded only
  when completed aggregate orderflow confirms absorption at failed probes or
  continuation participation on breaks. This is not a parameter rescue of the
  failed standalone `es_round_number_barrier_reaction` campaign.
- Added entry module
  `src/propstack/strategy_modules/entry/round_number_orderflow_barrier.py` plus
  registration and engine feature-column checks. Signals use completed 5-minute
  bars and engine entry remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `morning_support_sell_absorption_long`,
  `morning_resistance_buy_absorption_short`,
  `midday_two_sided_large10_absorption_reclaim`,
  `round_number_upside_flow_breakout_long`, and
  `round_number_downside_flow_breakout_short`.
- Density audit:
  `research_artifacts/es_round_number_orderflow_barrier_density_audit_20260617.md`.
  Every declared entry corner exceeded the 50 trades/year pre-PnL density floor
  on the full available period; sparse 50-point absorption corners were rejected
  before performance testing.
- Verification before staged runs:
  `PYTHONPATH=src python3 -m pytest tests/test_round_number_orderflow_barrier.py tests/test_round_number_barrier.py tests/test_preflight.py -q`
  passed 17 tests; targeted preflight for the five originals and five rescues
  passed.
- Originals: all five failed `limited_core_grid_test`. The best original was
  `round_number_downside_flow_breakout_short/run1`, with 0.12962962962962962
  profitable-combo rate, six benchmark-passing combos, top net `2817.5`, PF
  `1.1636178861788617`, and 84.12751394916305 trades/year, below the 70%
  profitable-combo robustness gate.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving edge thesis, entry module, stop module, target module,
  timeframe, data, costs, fills, sessions, prop rules, and validation gates. All
  five rescues also failed `limited_core_grid_test`.
- Best rescue was `morning_support_sell_absorption_long/rescue1`, with
  0.35185185185185186 profitable-combo rate, top net `2075.0`, PF
  `1.2181913774973712`, MAR `1.3491650623474079`, and 49.61231535457581
  trades/year. It failed limited core because profitable-combo rate remained
  below 0.70 and top-row trade density remained below 50/year.
- Aggregate artifacts:
  `backtest-campaigns/es_round_number_orderflow_barrier/campaign_test_summary.json`,
  `backtest-campaigns/es_round_number_orderflow_barrier/campaign_results.csv`,
  `backtest-campaigns/es_round_number_orderflow_barrier/wfa_table.csv`,
  `backtest-campaigns/es_round_number_orderflow_barrier/monte_carlo_summary.json`,
  and
  `research_artifacts/es_round_number_orderflow_barrier_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached limited monkey, WFA, WFA OOS monkey, Monte
  Carlo, simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.

### `es_opening_range_failed_breakout_orderflow`

Decision: FAIL.

- Created a bounded price-action plus aggregate-orderflow campaign using only
  the local Sierra ES RTH 1-minute aggregate-orderflow cache. No paid data was
  downloaded.
- Primary setup: completed opening-range support/resistance false breakout. A
  completed close must first break outside the opening range, then a later
  completed bar must reclaim back through the same boundary with opposite
  aggregate orderflow. Target is the opposite opening-range edge.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and pre-test mechanics reviews:
  `or15_signed_failed_reclaim_1030`,
  `or30_signed_failed_reclaim_1100`,
  `or15_large10_failed_reclaim_1030`,
  `or30_large20_failed_reclaim_1130`, and
  `or60_signed_failed_reclaim_1200`.
- Pre-PnL density audit:
  `research_artifacts/es_opening_range_failed_breakout_orderflow_density_audit_20260617.md`.
  One-bar reclaim and OR15 directional-only ideas were rejected before PnL as
  too sparse. The final grids were kept only where raw density plausibly met
  the 50 trades/year rule.
- Added and verified entry module
  `src/propstack/strategy_modules/entry/opening_range_failed_breakout_orderflow.py`
  plus registration and engine feature-column checks. Targeted tests:
  `PYTHONPATH=src python3 -m pytest tests/test_opening_range_failed_breakout_orderflow.py tests/test_opening_range_orderflow_breakout.py tests/test_core_grid.py tests/test_campaign_stages.py tests/test_preflight.py -q`
  passed 63 tests.
- Originals: all five failed `limited_core_grid_test` with `0.0` profitable
  combinations and zero benchmark-passing combinations. The best original was
  `or30_signed_failed_reclaim_1100/run1`, top net `-867.5`, PF
  `0.8922360248447205`, and 76.207045 trades/year.
- Rescues: all five failed variants received exactly one stop-offset
  parameter-space rescue preserving entry, stop module, target module, data,
  costs, fills, sessions, prop rules, and validation gates. All five rescues
  failed `limited_core_grid_test`; best rescue was
  `or60_signed_failed_reclaim_1200/rescue1`, top net `-1037.5`, PF
  `0.9226179377214245`, and `0.0` profitable-combo rate.
- Aggregate artifacts:
  `backtest-campaigns/es_opening_range_failed_breakout_orderflow/campaign_test_summary.json`,
  `backtest-campaigns/es_opening_range_failed_breakout_orderflow/campaign_results.csv`,
  `backtest-campaigns/es_opening_range_failed_breakout_orderflow/wfa_table.csv`,
  `backtest-campaigns/es_opening_range_failed_breakout_orderflow/monte_carlo_summary.json`,
  `research_artifacts/es_opening_range_failed_breakout_orderflow_rescue_attempt_1_20260617.md`.

### `es_range_compression_orderflow_breakout`

Decision: FAIL.

- Created a bounded composite campaign using only the local Sierra ES RTH
  1-minute aggregate-orderflow cache. No paid data was downloaded.
- Primary setup: prior RTH session is NR4 range compression. Breakout reference
  is either prior RTH high/low or a completed opening range. Secondary condition:
  the completed breakout bar must have aligned aggregate orderflow.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and pre-test mechanics reviews:
  `nr4_prior_large20_flow_breakout_1400`,
  `nr4_prior_signed_flow_breakout_1400`,
  `nr4_or15_large20_flow_breakout_1200`,
  `nr4_or30_large10_flow_breakout_1400`, and
  `nr4_or60_signed_flow_breakout_1330`.
- Pre-PnL density audit:
  `research_artifacts/es_range_compression_orderflow_breakout_density_audit_20260617.md`.
  NR7 and inside-day variants were rejected before PnL as too sparse. The final
  five NR4 variants cleared strict-corner raw signal density above 50/year.
- Added and verified entry module
  `src/propstack/strategy_modules/entry/range_compression_orderflow_breakout.py`
  plus registration and engine feature-column checks. Targeted tests:
  `PYTHONPATH=src python3 -m pytest tests/test_range_compression_orderflow_breakout.py tests/test_opening_range_orderflow_breakout.py tests/test_preflight.py -q`
  passed 14 tests. Scoped preflight passed for five originals and five rescues.
- Originals: all five failed `limited_core_grid_test`. Best original profitable
  combo rate was `0.04938271604938271`; no original had a benchmark-passing
  combo. The best top row was
  `nr4_prior_large20_flow_breakout_1400/run1`, top net `900.0`, PF
  `1.054471`, and 73.153449 trades/year, but it failed profit concentration.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving compression rule, breakout reference, flow bucket, entry
  windows, modules, data, costs, fills, sessions, prop rules, and validation
  gates. The rescue changed only stop/target defaults and stop/target grids.
  All rescues failed `limited_core_grid_test`; best rescue profitable-combo rate
  was `0.024691358024691678`.
- Aggregate artifacts:
  `backtest-campaigns/es_range_compression_orderflow_breakout/campaign_test_summary.json`,
  `backtest-campaigns/es_range_compression_orderflow_breakout/campaign_results.csv`,
  `backtest-campaigns/es_range_compression_orderflow_breakout/wfa_table.csv`,
  `backtest-campaigns/es_range_compression_orderflow_breakout/monte_carlo_summary.json`,
  and
  `research_artifacts/es_range_compression_orderflow_breakout_rescue_attempt_1_20260617.md`.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen
  validation, or candidate reporting. No `candidate_strategy_report.md` was
  created.

### `es_opening_gap_orderflow_absorption_fade`

Decision: FAIL.

- Created a price-action plus aggregate-orderflow campaign using only the local
  Sierra ES RTH 1-minute aggregate-orderflow cache. No paid data was downloaded.
- Primary setup: ES opens 1-3 points away from the prior RTH close. Secondary
  condition: a completed post-open aggregate-flow window must show signed flow
  against the gap, interpreted as possible absorption.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and pre-test mechanics reviews:
  `early_large20_gap_absorption_fade_1000`,
  `morning_large20_gap_absorption_fade_1030`,
  `late_morning_large20_gap_absorption_fade_1100`,
  `midday_large20_gap_absorption_fade_1200`, and
  `late_morning_large10_gap_absorption_fade_1100`.
- Pre-PnL density audit:
  `research_artifacts/es_opening_gap_orderflow_absorption_fade_density_audit_20260617.md`.
  Larger-gap formulations were rejected before PnL as too sparse, and zero-gap
  formulations were rejected before PnL because they no longer expressed an
  opening-gap edge. The selected nonzero 1-3 point gap grid cleared the raw
  signal-density screen.
- Verification before staged runs:
  `PYTHONPATH=src python3 -m pytest tests/test_strategy_modules.py tests/test_opening_range_orderflow_breakout.py tests/test_trend_aligned_orderflow_continuation.py tests/test_vwap_orderflow_pullback_continuation.py tests/test_preflight.py -q`
  passed 150 tests. Scoped preflight passed for the five originals and five
  rescues. A full active-config preflight was intentionally interrupted after
  several minutes because it was loading the full active backlog; scoped
  preflight covered this campaign's configs.
- Originals: all five failed `limited_core_grid_test` with 0.0
  profitable-combo rate. Least-bad original was
  `morning_large20_gap_absorption_fade_1030/run1`, top net `-498.75`, PF
  `0.7170212765957447`, and 34.11936197817293 trades/year.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving entry modules, source windows, flow buckets, data, costs,
  fills, sessions, prop rules, and validation gates. Rescue changed only the
  fixed stop/target defaults and stop/target grids. All rescues failed
  `limited_core_grid_test`. The best rescue profitable-combo rate was
  `0.4197530864197531`, below the required `0.70`, despite top isolated rows
  turning positive in two variants.
- Aggregate artifacts:
  `backtest-campaigns/es_opening_gap_orderflow_absorption_fade/campaign_test_summary.json`,
  `backtest-campaigns/es_opening_gap_orderflow_absorption_fade/campaign_results.csv`,
  `backtest-campaigns/es_opening_gap_orderflow_absorption_fade/wfa_table.csv`,
  `backtest-campaigns/es_opening_gap_orderflow_absorption_fade/monte_carlo_summary.json`,
  and
  `research_artifacts/es_opening_gap_orderflow_absorption_fade_rescue_attempt_1_20260617.md`.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen
  validation, or candidate reporting. No `candidate_strategy_report.md` was
  created.

### `es_vwap_orderflow_pullback_continuation`

Decision: FAIL.

- Created a price-action plus aggregate-orderflow campaign using only the local
  Sierra ES RTH 1-minute aggregate-orderflow cache. No paid data was downloaded.
- Primary setup: completed VWAP-side trend plus pullback/reclaim on 5-minute
  bars. Secondary condition: same completed reclaim bar must have aligned
  aggregate orderflow. This follows the 2026-06-17 routing priority to prefer
  price action as setup and aggregate orderflow as confirmation.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and pre-test mechanics reviews:
  `morning_signed_trend_reclaim_two_sided`,
  `morning_large10_trend_reclaim_two_sided`,
  `morning_large20_trend_reclaim_two_sided`,
  `midday_large10_trend_reclaim_two_sided`, and
  `midday_large20_trend_reclaim_two_sided`.
- Pre-PnL density audit:
  `research_artifacts/es_vwap_orderflow_pullback_continuation_density_audit_20260617.md`.
  Selected variants cleared the raw signal-density screen across declared entry
  grids. Midday signed-flow, afternoon, late-day failed-break, and initial
  opening-drive formulations were rejected before PnL for density or formulation
  defects.
- Added and verified entry module
  `src/propstack/strategy_modules/entry/vwap_orderflow_pullback_continuation.py`.
  Targeted tests:
  `PYTHONPATH=src python3 -m pytest tests/test_vwap_orderflow_pullback_continuation.py tests/test_preflight.py -q`
  passed 12 tests. Targeted preflight passed for five originals and five rescues.
- Originals: all five failed `limited_core_grid_test` with 0.0 profitable-combo
  rate. Least-bad original was
  `morning_large20_trend_reclaim_two_sided/run1`, top net `-752.50`, PF
  `0.9387464387464387`, and 93.27324474648577 trades/year.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving the VWAP trend-reclaim plus orderflow-confirmation mechanic,
  entry/stop/target modules, variant windows, flow modes, data, costs, fills,
  sessions, prop rules, and validation gates. All rescues failed
  `limited_core_grid_test` with 0.0 profitable-combo rate.
- Aggregate artifacts:
  `backtest-campaigns/es_vwap_orderflow_pullback_continuation/campaign_test_summary.json`,
  `backtest-campaigns/es_vwap_orderflow_pullback_continuation/campaign_results.csv`,
  `backtest-campaigns/es_vwap_orderflow_pullback_continuation/wfa_table.csv`,
  `backtest-campaigns/es_vwap_orderflow_pullback_continuation/monte_carlo_summary.json`,
  and
  `research_artifacts/es_vwap_orderflow_pullback_continuation_rescue_attempt_1_20260617.md`.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen
  validation, or candidate reporting. No `candidate_strategy_report.md` was
  created.

### `es_spx_0dte_trend_aligned_pressure`

Decision: FAIL.

- Created a composite campaign with exactly five variants using `spx_0dte_trend_aligned_pressure`, `percent_from_entry`, and `fixed_r`.
- Primary edge: SPX 0DTE calendar pressure. Secondary condition: fixed ES 30-minute and 120-minute completed-bar high/low trend alignment. The filter was declared before PnL testing and is not eligible as a rescue modification.
- Reformulated before PnL from post-2022 full-week-only sessions to all locally known SPX 0DTE sessions from `2016-02-24` through `2026-06-09`, excluding standard monthly OPEX, because the longer history is needed for the benchmark 4-year IS / 1-year OOS WFA structure.
- Pre-test density audit passed: all five final variants cleared 50 signals/year in the raw signal count. Artifact: `research_artifacts/es_spx_0dte_trend_aligned_pressure_density_audit_20260617.md`.
- Every variant config includes the required pre-test mechanics review with `pre_test_decision: approve_for_testing`; staged runner and preflight both enforce this gate.
- Originals: all five failed. `all_0dte_trend_only_1330` and `all_0dte_trend_continuation_1330` were closest at `0.6666666666666666` profitable-combo rate, below the required `0.70`; the other three failed limited core more decisively.
- Rescues: all five one-time parameter-space rescues were run and logged. Two rescues passed limited core; `all_0dte_trend_only_1330/rescue1` failed limited monkey, and `all_0dte_trend_only_1500/rescue1` passed limited monkey but failed WFA by early exit because the first in-sample grid had no row satisfying the trade-density selection filter.
- No run reached WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, frozen acceptance, or candidate packaging.
- Aggregate artifacts: `backtest-campaigns/es_spx_0dte_trend_aligned_pressure/campaign_test_summary.json`, `campaign_results.csv`, `wfa_table.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, and `monte_carlo_summary.json`.
- Verification: targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `PYTHONPATH=src python3 -m pytest tests/test_spx_0dte_trend_aligned_pressure.py tests/test_spx_0dte_expiration_pressure.py tests/test_preflight.py -q` PASS.

### `es_mes_micro_flow_divergence_reversion`

Source thesis: ES may mean-revert when completed MES flow or short-horizon MES price movement diverges from ES.

Data: local one-year ES/MES caches from `2025-06-10` through `2026-06-08`.

| Variant | Terminal stage | Failure | Actual-trade stress |
| --- | --- | --- | --- |
| `afternoon_mes_large20_buy_pressure_short` | `limited_monkey_test` | random monkey `percentage_profitable=0.38`, `median_net_profit=-2552.5` | passed stress gate: `percentage_profitable=1.0`, one-tick net `9992.5` |
| `afternoon_mes_large20_sell_pressure_long` | `limited_core_grid_test` | `percentage_profitable_iterations=0.6944444444444444` | not reached |
| `midday_mes_price_richness_fade` | `limited_core_grid_test` | `percentage_profitable_iterations=0.6666666666666666` | not reached |
| `morning_mes_buy_pressure_reversion_short` | `limited_core_grid_test` | `percentage_profitable_iterations=0.6666666666666666` | not reached |
| `morning_mes_sell_pressure_reversion_long` | `limited_monkey_test` | random monkey `percentage_profitable=0.44`, `median_net_profit=-1335.0` | passed stress gate: `percentage_profitable=0.99`, one-tick net `6430.0` |

Decision: FAIL. No variant reached WFA under the corrected monkey/core gates.

Rescue attempt 1: FAIL. The rescue was originally allowed after all five
original variants failed; under the clarified current rule it consumes this
failed variant's one rescue. It changed only existing tunable parameter space for
`midday_mes_price_richness_fade`; it did not change modules, setup mode,
direction logic, signal timestamp, timeframe, data window, costs, or stage
criteria. Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/midday_mes_price_richness_fade/ES/rescue1/campaign_test_summary.json`.
Core passed with `36/36` profitable combinations and zero Apex violations, but
limited monkey failed with random-placebo `percentage_profitable=0.38666666666666666`
and `median_net_profit=-5822.5`. Actual trade-path stress passed with
`percentage_profitable=1.0` and one-tick-worse net profit `$28,827.50`, but the
required random-placebo profitability/median gate failed. Audit:
`research_artifacts/es_mes_micro_flow_divergence_reversion_rescue_attempt_1_20260615.md`.

Rescue attempt 1 for `afternoon_mes_large20_sell_pressure_long`: FAIL. This
rescue was allowed under the clarified per-failed-variant rule and changed only
the existing `flow_threshold` grid. It did not change modules, setup mode,
signal time, direction, timeframe, data window, costs, or stage criteria.
Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/afternoon_mes_large20_sell_pressure_long/ES/rescue1/campaign_test_summary.json`.
Core passed with `32/36` profitable combinations and zero Apex violations, but
limited monkey failed with random-placebo `percentage_profitable=0.43` and
`median_net_profit=-1723.75`. Actual trade-path stress also failed with
`percentage_profitable=0.4866666666666667` and one-tick-worse net profit
`-$532.50`. Audit:
`research_artifacts/es_mes_micro_flow_divergence_reversion_afternoon_sell_rescue_attempt_1_20260615.md`.

Rescue attempt 1 for `morning_mes_buy_pressure_reversion_short`: FAIL. This
rescue was allowed under the clarified per-failed-variant rule and changed only
the existing `flow_threshold` grid. It did not change modules, setup mode,
signal time, direction, timeframe, data window, costs, or stage criteria.
Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/morning_mes_buy_pressure_reversion_short/ES/rescue1/campaign_test_summary.json`.
Core passed with `36/36` profitable combinations and zero Apex violations, but
limited monkey failed with random-placebo `percentage_profitable=0.36` and
`median_net_profit=-2702.5`. Actual trade-path stress passed with
`percentage_profitable=0.9966666666666667` and one-tick-worse net profit
`$4,467.50`, but the required random-placebo profitability/median gate failed.
Audit:
`research_artifacts/es_mes_micro_flow_divergence_reversion_morning_buy_short_rescue_attempt_1_20260615.md`.

Rescue attempt 1 for `afternoon_mes_large20_buy_pressure_short`: FAIL. This
rescue was allowed under the clarified per-failed-variant rule and changed only
the existing `flow_threshold` grid. It did not change modules, setup mode,
signal time, direction, timeframe, data window, costs, or stage criteria.
Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/afternoon_mes_large20_buy_pressure_short/ES/rescue1/campaign_test_summary.json`.
Core passed with `36/36` profitable combinations and zero Apex violations, but
limited monkey failed with random-placebo `percentage_profitable=0.36666666666666664`
and `median_net_profit=-1901.25`. Actual trade-path stress passed with
`percentage_profitable=1.0` and one-tick-worse net profit `$10,292.50`, but the
required random-placebo profitability/median gate failed. Audit:
`research_artifacts/es_mes_micro_flow_divergence_reversion_afternoon_buy_rescue_attempt_1_20260615.md`.

Rescue attempt 1 for `morning_mes_sell_pressure_reversion_long`: FAIL. This
rescue was allowed under the clarified per-failed-variant rule and changed only
the existing `flow_threshold` grid. It did not change modules, setup mode,
signal time, direction, timeframe, data window, costs, or stage criteria.
Report:
`backtest-campaigns/es_mes_micro_flow_divergence_reversion/morning_mes_sell_pressure_reversion_long/ES/rescue1/campaign_test_summary.json`.
Core passed with `36/36` profitable combinations and zero Apex violations, but
limited monkey failed with random-placebo `percentage_profitable=0.47` and
`median_net_profit=-800.0`. Actual trade-path stress passed with
`percentage_profitable=0.9966666666666667` and one-tick-worse net profit
`$6,807.50`, but the required random-placebo profitability/median gate failed.
Audit:
`research_artifacts/es_mes_micro_flow_divergence_reversion_morning_sell_rescue_attempt_1_20260615.md`.

### `es_prior_session_ibs_reversion`

Source thesis: prior-session Internal Bar Strength may mean-revert in equity-index futures during the next RTH session.

Data: local ES Sierra RTH cache from `2011-01-03` through `2026-06-09`.

Note: the first `run1` open-variant artifacts were invalidated because the configs did not request the prior-RTH feature set and produced zero trades. Corrected `run2` configs used `feature_set: pdh_pdl_sweep`; the zero-trade artifacts were retained for audit.

| Variant | Terminal stage | Profitable combo rate | Top net / trades | Decision |
| --- | --- | ---: | ---: | --- |
| `open_low_ibs_long` | `limited_core_grid_test` | `0.0` | `-1170.0` / `19` | FAIL |
| `open_high_ibs_short` | `limited_core_grid_test` | `0.3333333333333333` | `1060.0` / `53` | FAIL |
| `open_two_sided_ibs_reversion` | `limited_core_grid_test` | `0.0` | `-1490.0` / `83` | FAIL |
| `delayed_low_ibs_long_range_filtered` | `limited_core_grid_test` | `0.3148148148148148` | `1315.0` / `42` | FAIL |
| `delayed_high_ibs_short_range_filtered` | `limited_core_grid_test` | `0.2037037037037037` | `1835.0` / `53` | FAIL |

Decision: FAIL. Best corrected profitable-combo rate was `0.3333333333333333`, below the required `0.70`.

### `es_connors_rsi2_mean_reversion`

Source thesis: Connors-style RSI2 extremes may mean-revert in liquid equity-index futures when filtered by intraday trend or VWAP context.

Data: local ES Sierra RTH cache from `2011-01-03` through `2026-06-09`.

| Variant | Terminal stage | Profitable combo rate | Top net / trades | Decision |
| --- | --- | ---: | ---: | --- |
| `five_min_long_vwap_extreme_1430` | `limited_core_grid_test` | `0.04938271604938271` | `427.5` / `87` | FAIL |
| `five_min_short_vwap_extreme_1430` | `limited_core_grid_test` | `0.0` | `-1235.0` / `117` | FAIL |
| `fifteen_min_long_uptrend_pullback_1545` | `limited_core_grid_test` | `0.06172839506172839` | `2646.25` / `92` | FAIL |
| `fifteen_min_short_downtrend_bounce_1545` | `limited_core_grid_test` | `0.0` | `-1302.5` / `133` | FAIL |
| `thirty_min_two_sided_trend_reversion_1530` | `limited_core_grid_test` | `0.037037037037037035` | `1207.5` / `101` | FAIL |

Decision: FAIL. Best profitable-combo rate was `0.06172839506172839`, below the required `0.70`.

### `es_range_compression_breakout`

Source thesis: NR4, ID/NR4, and NR7 compression patterns may precede intraday volatility expansion and same-session breakout continuation.

Data: local ES Sierra RTH cache from `2011-01-03` through `2026-06-09`.

Signal-density sanity check before testing: all five variants emitted nonzero signals across all 16 calendar years in the configured data window, so the run was not a zero-signal data wiring failure.

| Variant | Terminal stage | Core profitable combo rate | Top net / trades | Monkey result | Decision |
| --- | --- | ---: | ---: | --- | --- |
| `nr4_prior_session_breakout` | `limited_core_grid_test` | `0.5802469135802469` | `2752.5` / `107` | not reached | FAIL |
| `id_nr4_prior_session_breakout` | `limited_monkey_test` | `1.0` | `1785.0` / `18` | random monkey `percentage_profitable=0.3933333333333333`, `median_net_profit=-570.0`; actual-trade stress passed with `percentage_profitable=0.9533333333333334`, one-tick net `1285.0` | FAIL |
| `nr7_opening_range_30_breakout` | `limited_core_grid_test` | `0.037037037037037035` | `95.0` / `61` | not reached | FAIL |
| `nr7_opening_range_15_long_breakout` | `limited_core_grid_test` | `0.5555555555555556` | `1382.5` / `41` | not reached | FAIL |
| `nr7_opening_range_15_short_breakout` | `limited_core_grid_test` | `0.0` | `-882.5` / `34` | not reached | FAIL |

Decision: FAIL. Four variants failed the `0.70` core profitable-combo gate. The ID/NR4 variant passed core but had only `18` trades in the selected core row and failed the random-placebo monkey gate with negative median PnL, so it did not earn WFA.

Rescue attempt 1: FAIL. The rescue was originally allowed after all five
original variants failed; under the clarified current rule it consumes this
failed variant's one rescue. It changed only existing fixed strategy parameters
plus the tunable parameter grid for `id_nr4_prior_session_breakout`; it did not change
modules, setup mode, timeframe, data window, costs, or stage criteria. Report:
`backtest-campaigns/es_range_compression_breakout/id_nr4_prior_session_breakout/ES/rescue1/campaign_test_summary.json`.
Core passed again with `81/81` profitable combinations, but top rows remained
sparse at `19` trades. Limited monkey failed with random-placebo
`percentage_profitable=0.2866666666666667` and `median_net_profit=-548.75`.
Actual trade-path stress passed with `percentage_profitable=0.98` and
one-tick-worse net profit `$692.50`, but the required random-placebo
profitability/median gate failed. Audit:
`research_artifacts/es_range_compression_breakout_rescue_attempt_1_20260615.md`.

### `es_rth_intraday_risk_premium`

Source thesis: equity-index futures may retain a positive RTH intraday premium after a completed early-session bar.

Data: local ES Sierra RTH cache from `2011-01-03` through `2026-06-09`.

Signal-density sanity check before testing: all five fixed-time variants emitted `3817` baseline signals across the configured data window, so the run was not a zero-signal data wiring failure.

| Variant | Terminal stage | Fixed combo net | PF | Trades | Expectancy R | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `open_0935_long` | `limited_core_grid_test` | `-16190.0` | `0.7593370247872459` | `363` | `-0.12341172067563005` | FAIL |
| `first_hour_1000_long` | `limited_core_grid_test` | `-15315.0` | `0.7575589678644926` | `363` | `-0.11573397095390234` | FAIL |
| `midmorning_1030_long` | `limited_core_grid_test` | `-9327.5` | `0.8405555555555555` | `363` | `-0.06250703361311283` | FAIL |
| `late_morning_1100_long` | `limited_core_grid_test` | `-4777.5` | `0.9108841634023503` | `363` | `-0.025730858511327788` | FAIL |
| `early_afternoon_1300_long` | `limited_core_grid_test` | `-10440.0` | `0.7657354426119152` | `363` | `-0.0741318210488584` | FAIL |

Decision: FAIL. Every fixed-combo long-bias variant lost money after costs. No WFA was earned.

### `es_overnight_intraday_reversal`

Source thesis: overnight gaps may reverse during the following intraday session as liquidity providers are compensated for opening inventory pressure.

Data: local ES Sierra RTH cache from `2011-01-03` through `2026-06-09` with `feature_set: pdh_pdl_sweep` for prior RTH close.

Signal-density sanity check before testing: all five variants produced nonzero baseline trades. Baseline trade counts ranged from `423` to `1161`.

| Variant | Terminal stage | Profitable combo rate | Benchmark pass combos | Top net / trades per year | Top PF / MAR | Decision |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `first5_confirm_reversal_1000` | `limited_core_grid_test` | `0.012345679012345678` | `0` | `152.5` / `28.382792844693682` | `1.0286519492719586` / `0.06347638787225555` | FAIL |
| `first15_confirm_reversal_1000` | `limited_core_grid_test` | `0.1728395061728395` | `0` | `1982.5` / `65.3933404996568` | `1.1296387117868236` / `0.3646686603265131` | FAIL |
| `first30_noncontinuation_1000` | `limited_core_grid_test` | `0.024691358024691357` | `0` | `430.0` / `54.0207107707709` | `1.0389845874886672` / `0.12424091766234946` | FAIL |
| `low_overnight_first15_long_1000` | `limited_core_grid_test` | `0.08641975308641975` | `0` | `1147.5` / `39.97127844966522` | `1.152643831060858` / `0.4520801176937031` | FAIL |
| `high_overnight_first15_short_1000` | `limited_core_grid_test` | `0.4074074074074074` | `0` | `3842.5` / `36.92146896327592` | `1.4204048140043763` / `1.4504362709137382` | FAIL |

Decision: FAIL. All variants failed the `0.70` core profitable-combo gate and none produced a benchmark-passing combination. The best single top combo was the short-only variant, but it had only `33/81` profitable combinations and insufficient trades per year.

Rescue attempt 1: FAIL. The rescue was originally allowed after all five
original variants failed; under the clarified current rule it consumes this
failed variant's one rescue. It changed only existing threshold and stop/target
parameter space for `high_overnight_first15_short_1000`; it did not change modules, setup
mode, direction, confirmation-window length, entry time, timeframe, data window,
costs, or stage criteria. Report:
`backtest-campaigns/es_overnight_intraday_reversal/high_overnight_first15_short_1000/ES/rescue1/campaign_test_summary.json`.
Core failed with `56/81` profitable combinations, profitable-combo rate
`0.691358024691358`, zero benchmark-passing combinations, and zero Apex
violations. The top row remained sparse at `54` trades and `36.92146896327592`
trades per year. Audit:
`research_artifacts/es_overnight_intraday_reversal_rescue_attempt_1_20260615.md`.

### `es_signed_orderflow_persistence`

Source thesis: own-ES aggregate signed-orderflow imbalance may persist over
short intraday horizons after completed-bar price confirmation, consistent with
short-horizon order-flow impact, flow toxicity, and persistent order-splitting
research.

Data: corrected local ES Sierra aggregate orderflow cache from `2011-01-03`
through `2026-06-09`.

| Variant | Original profitable combo rate | Original top net / trades | Rescue profitable combo rate | Rescue top net / trades | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `early_5m_signed_flow_continuation_1000` | `0.12345679012345678` | `1447.5` / `198` | `0.1111111111111111` | `728.75` / `198` | FAIL |
| `late_morning_15m_signed_flow_continuation_1130` | `0.07407407407407407` | `612.5` / `65` | `0.012345679012345678` | `90.625` / `70` | FAIL |
| `midday_30m_signed_flow_continuation_1230` | `0.037037037037037035` | `302.5` / `42` | `0.0` | `-3063.75` / `179` | FAIL |
| `afternoon_60m_signed_flow_continuation_1400` | `0.012345679012345678` | `555.0` / `74` | `0.0` | `-1038.75` / `149` | FAIL |
| `late_large20_30m_flow_continuation_1500` | `0.0` | `-156.25` / `35` | `0.0` | `-212.5` / `95` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues failed the `0.70` core profitable-combo gate before
monkey, WFA, Monte Carlo, or frozen validation. Report:
`backtest-campaigns/es_signed_orderflow_persistence/campaign_test_summary.json`.
Audit:
`research_artifacts/es_signed_orderflow_persistence_rescue_attempt_1_20260615.md`.

### `es_opening_drive_inventory_absorption`

Source thesis: first-30/60-minute opening drives can contain same-day
information when paired with volume and orderflow state, but may reverse when
inventory pressure is absorbed. The campaign combined intraday momentum,
intraday return/flow timing, and orderflow-impact literature.

Data: corrected local ES Sierra aggregate orderflow cache from `2011-01-03`
through `2026-06-09`.

| Variant | Original terminal | Original pct | Rescue terminal | Rescue pct | Decision |
| --- | --- | ---: | --- | ---: | --- |
| `open30_flow_continuation_1030` | `limited_core_grid_test` | `0.38271604938271603` | `limited_core_grid_test` | `0.35802469135802467` | FAIL |
| `open60_flow_continuation_1130` | `limited_monkey_test` | `0.16333333333333333` | `limited_monkey_test` | `0.20666666666666667` | FAIL |
| `open30_absorbed_pressure_fade_1015` | `limited_core_grid_test` | `0.0` | `limited_core_grid_test` | `0.0` | FAIL |
| `open60_exhaustion_fade_1300` | `limited_core_grid_test` | `0.5555555555555556` | `limited_core_grid_test` | `0.4074074074074074` | FAIL |
| `open30_price_flow_divergence_fade_1400` | `limited_core_grid_test` | `0.0` | `limited_core_grid_test` | `0.0` | FAIL |

Decision: FAIL. No run reached WFA. The two
`open60_flow_continuation_1130` runs passed core but failed monkey with weak
profitable-run rates and failed one-tick-worse stress. Report:
`backtest-campaigns/es_opening_drive_inventory_absorption/campaign_test_summary.json`.
Audit:
`research_artifacts/es_opening_drive_inventory_absorption_rescue_attempt_1_20260615.md`.

### `es_turn_of_month_seasonality`

Source thesis: equity-index futures may retain a positive turn-of-the-month
calendar premium around month-end and the first calendar days of the next month.
The campaign tested this as a calendar-seasonality edge, distinct from the
unconditional fixed RTH long-bias campaign.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2011-01-03`
through `2026-06-09`, aggregated to 5-minute strategy bars.

| Variant | Original profitable combo rate | Original top net / trades | Rescue profitable combo rate | Rescue top net / trades | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `classic_turn_window_1000_long` | `0.037037037037037035` | `577.5` / `62` | `0.0` | `-96.25` / `73` | FAIL |
| `early_month_first_days_1000_long` | `0.0` | `-287.5` / `25` | `0.07407407407407407` | `178.75` / `13` | FAIL |
| `month_end_last_days_1000_long` | `0.3333333333333333` | `1991.25` / `48` | `0.0` | `-206.25` / `60` | FAIL |
| `opening_turn_window_0935_long` | `0.04938271604938271` | `355.0` / `74` | `0.07407407407407407` | `1685.0` / `73` | FAIL |
| `late_turn_window_1300_long` | `0.0` | `-810.0` / `97` | `0.0` | `-352.5` / `73` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues failed the `0.70` core profitable-combo gate before
monkey, WFA, Monte Carlo, or frozen validation. Report:
`backtest-campaigns/es_turn_of_month_seasonality/campaign_test_summary.json`.
Audit:
`research_artifacts/es_turn_of_month_seasonality_rescue_attempt_1_20260615.md`.

### `es_daily_time_series_momentum`

Source thesis: futures can exhibit time-series momentum, where an asset's own
prior returns predict same-direction continuation. The campaign tested this in
ES using only prior completed RTH closes and intraday same-day execution.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2011-01-03`
through `2026-06-09`, aggregated to 5-minute strategy bars.

| Variant | Original profitable combo rate | Original top net / trades | Rescue profitable combo rate | Rescue top net / trades | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `long_only_trend_1000` | `0.0` | `-572.5` / `142` | `0.2839506172839506` | `2822.5` / `123` | FAIL |
| `short_term_alignment_1000_two_sided` | `0.0` | `-6951.25` / `239` | `0.0` | `-3692.5` / `121` | FAIL |
| `sixty_day_trend_1000_two_sided` | `0.0` | `-6626.25` / `269` | `0.19753086419753085` | `2822.5` / `123` | FAIL |
| `twenty_day_trend_1000_two_sided` | `0.0` | `-7438.75` / `299` | `0.0` | `-7776.25` / `354` | FAIL |
| `vol_norm_trend_1000_two_sided` | `0.012345679012345678` | `452.5` / `92` | `0.14814814814814814` | `1392.5` / `89` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues failed the `0.70` core profitable-combo gate before
monkey, WFA, Monte Carlo, or frozen validation. The strongest rescue was still a
narrow surface at `0.2839506172839506`. Report:
`backtest-campaigns/es_daily_time_series_momentum/campaign_test_summary.json`.
Audit:
`research_artifacts/es_daily_time_series_momentum_rescue_attempt_1_20260615.md`.

### `es_late_day_intraday_momentum`

Source thesis: Gao, Han, Li, and Zhou's market intraday momentum anomaly states
that the first half-hour market return measured from the prior close predicts
the last half-hour return. The campaign tested whether that survives as a
same-day ES futures strategy with realistic costs and flattening.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2011-01-03`
through `2026-06-09`, aggregated to 5-minute strategy bars with
`feature_set: pdh_pdl_sweep` for prior-RTH close and volume-ratio features.

Feature-audit note: an initial zero-trade run used `feature_set: none`, which
did not build `prev_rth_close` or `volume_ratio`. Those invalid outputs were
removed and the original `run1` was rerun with the corrected feature set before
any rescue was consumed.

| Variant | Original profitable combo rate | Original top net / trades | Rescue profitable combo rate | Rescue top net / trades | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `first30_to_last30_two_sided` | `0.0` | `-6765.0` / `253` | `0.0` | `-2941.25` / `72` | FAIL |
| `first30_to_last30_long_only` | `0.0` | `-2697.5` / `137` | `0.0` | `-742.5` / `76` | FAIL |
| `first30_volume_range_conditioned` | `0.0` | `-3270.0` / `164` | `0.0` | `-912.5` / `35` | FAIL |
| `first60_to_last30_two_sided` | `0.0` | `-5220.625` / `186` | `0.0` | `-2316.25` / `57` | FAIL |
| `first30_penultimate_alignment` | `0.0` | `-1902.5` / `68` | `0.0` | `-240.0` / `8` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues had `0.0` profitable core-grid combinations and
failed before monkey, WFA, Monte Carlo, or frozen validation. Report:
`backtest-campaigns/es_late_day_intraday_momentum/campaign_test_summary.json`.
Audit:
`research_artifacts/es_late_day_intraday_momentum_rescue_attempt_1_20260615.md`.

### `es_volume_shock_liquidity_reversal`

Source thesis: high-volume return shocks can have different serial-correlation
properties depending on whether they reflect liquidity/risk-sharing pressure or
information. The campaign tested completed high-volume 5-minute ES shock bars
as liquidity-reversal candidates.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2011-01-03`
through `2026-06-09`, aggregated to 5-minute strategy bars with
`feature_set: pdh_pdl_sweep` for rolling volume-ratio features.

| Variant | Original profitable combo rate | Original top net / trades | Rescue profitable combo rate | Rescue top net / trades | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| `all_day_symmetric_shock_reversion` | `0.0` | `0.0` / `0` | `0.024691358024691357` | `397.5` / `33` | FAIL |
| `morning_down_shock_reversal_long` | `0.06172839506172839` | `215.0` / `142` | `0.1728395061728395` | `1257.5` / `11` | FAIL |
| `morning_up_shock_reversal_short` | `0.04938271604938271` | `532.5` / `6` | `0.08641975308641975` | `2167.5` / `29` | FAIL |
| `midday_symmetric_shock_reversion` | `0.024691358024691357` | `617.5` / `34` | `0.20987654320987653` | `1866.25` / `13` | FAIL |
| `afternoon_symmetric_shock_reversion` | `0.037037037037037035` | `508.75` / `67` | `0.06172839506172839` | `1770.0` / `36` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues failed the `0.70` core profitable-combo gate before
monkey, WFA, Monte Carlo, or frozen validation. The best rescue reached only
`0.20987654320987653` profitable combinations and its top row had only `13`
trades. Report:
`backtest-campaigns/es_volume_shock_liquidity_reversal/campaign_test_summary.json`.
Audit:
`research_artifacts/es_volume_shock_liquidity_reversal_rescue_attempt_1_20260615.md`.

### `es_prior_day_stop_run_reclaim`

Source thesis: prior-session highs and lows are salient support/resistance
levels where clustered stop orders and liquidity provision can create failed
breakouts. The campaign tested whether completed 5-minute ES sweeps through the
prior RTH high/low that closed back inside the level could be faded same day.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2011-01-03`
through `2026-06-09`, aggregated to 5-minute strategy bars with
`feature_set: pdh_pdl_sweep` for prior-RTH high/low and volume-ratio features.

| Variant | Original profitable combo rate | Original terminal stage | Rescue profitable/monkey rate | Rescue terminal stage | Decision |
| --- | ---: | --- | ---: | --- | --- |
| `full_session_two_sided_reclaim` | `0.012345679012345678` | `limited_core_grid_test` | `0.2716049382716049` | `limited_core_grid_test` | FAIL |
| `morning_prior_low_reclaim_long` | `0.1728395061728395` | `limited_core_grid_test` | `0.654320987654321` | `limited_core_grid_test` | FAIL |
| `morning_prior_high_reject_short` | `0.14814814814814814` | `limited_core_grid_test` | `0.32666666666666666` | `limited_monkey_test` | FAIL |
| `midday_two_sided_reclaim` | `0.2716049382716049` | `limited_core_grid_test` | `0.2222222222222222` | `limited_core_grid_test` | FAIL |
| `afternoon_two_sided_reclaim` | `0.12345679012345678` | `limited_core_grid_test` | `0.345679012345679` | `limited_core_grid_test` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues failed before WFA. The strongest rescue,
`morning_prior_high_reject_short/rescue1`, passed the core profitable-combo
gate with `0.8641975308641975` profitable combinations, but failed
`limited_monkey_test` with `percentage_profitable=0.32666666666666666` and
`median_net_profit=-770.0`. Report:
`backtest-campaigns/es_prior_day_stop_run_reclaim/campaign_test_summary.json`.
Audit:
`research_artifacts/es_prior_day_stop_run_reclaim_rescue_attempt_1_20260615.md`.

### `es_vwap_pullback_continuation`

Source thesis: VWAP is a common institutional execution benchmark and intraday
value reference; a completed pullback or failed break around the developing
session VWAP may continue in the established intraday direction when the market
reclaims the trend side of VWAP.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2011-01-03`
through `2026-06-09`, aggregated to 5-minute strategy bars with developing VWAP
computed only from bars available at decision time.

| Variant | Original profitable combo rate | Original terminal stage | Rescue profitable/monkey rate | Rescue terminal stage | Decision |
| --- | ---: | --- | ---: | --- | --- |
| `morning_trend_reclaim_two_sided` | `0.012345679012345678` | `limited_core_grid_test` | `0.1111111111111111` | `limited_core_grid_test` | FAIL |
| `morning_opening_drive_pullback_long` | `0.1728395061728395` | `limited_core_grid_test` | `0.14814814814814814` | `limited_core_grid_test` | FAIL |
| `morning_opening_drive_pullback_short` | `0.037037037037037035` | `limited_core_grid_test` | `0.2345679012345679` | `limited_core_grid_test` | FAIL |
| `midday_trend_reclaim_two_sided` | `0.2222222222222222` | `limited_core_grid_test` | `0.18` | `limited_monkey_test` | FAIL |
| `failed_vwap_break_two_sided` | `0.12345679012345678` | `limited_core_grid_test` | `0.24691358024691357` | `limited_core_grid_test` | FAIL |

Decision: FAIL. All five original variants and all five one-time
parameter-space-only rescues failed before WFA. The strongest rescue,
`midday_trend_reclaim_two_sided/rescue1`, passed the core profitable-combo gate
with `0.8148148148148148` profitable combinations, but failed
`limited_monkey_test` with `percentage_profitable=0.18` and
`median_net_profit=-3210.0`. Report:
`backtest-campaigns/es_vwap_pullback_continuation/campaign_test_summary.json`.
Audit:
`research_artifacts/es_vwap_pullback_continuation_rescue_attempt_1_20260615.md`.

### `es_cftc_tff_hedging_pressure`

Source thesis: weekly CFTC Traders in Financial Futures positioning may proxy
slow-moving equity-index hedging pressure. ES intraday returns may compensate
traders who take the other side of that risk-transfer pressure after the report
feature is available.

Data: corrected local ES Sierra RTH OHLCV/orderflow cache from `2013-04-15`
through `2026-06-09`, plus local shifted CFTC TFF
`SPX_open_interest_chg13` features from
`data/external/cftc_tff_hedging_pressure_features.csv`.

Invalidated run note: initial `run1` artifacts are not economic evidence. The
limited-core first-window sample started before non-null shifted CFTC feature
coverage and produced zero trades. The valid originals are `run2`.

| Variant | Valid original profitable combo rate | Rescue profitable combo rate | Rescue top net / trades | Decision |
| --- | ---: | ---: | ---: | --- |
| `broad_negative_pressure_short_1100` | `0.0` | `0.0` | `-1208.75` / `103` | FAIL |
| `broad_positive_pressure_long_1100` | `0.14814814814814814` | `0.0` | `-2465.0` / `58` | FAIL |
| `extreme_negative_pressure_short_1330` | `0.1111111111111111` | `0.18518518518518517` | `262.5` / `5` | FAIL |
| `extreme_positive_pressure_long_1330` | `0.0` | `0.3333333333333333` | `775.0` / `5` | FAIL |
| `high_positive_pressure_long_0935` | `0.0` | `0.1111111111111111` | `915.625` / `5` | FAIL |

Decision: FAIL. All five corrected originals and all five one-time
parameter-space-only rescues failed the `0.70` core profitable-combo gate before
monkey, WFA, Monte Carlo, or frozen validation. The best rescue reached only
`0.3333333333333333` profitable combinations and its top row had only `5`
trades. Report:
`backtest-campaigns/es_cftc_tff_hedging_pressure/campaign_test_summary.json`.
Audit:
`research_artifacts/es_cftc_tff_hedging_pressure_rescue_attempt_1_20260615.md`.

## Duplicate-Edge Scope

- No local ES `campaign_test_summary.json` currently has `passed=true`.
- Archived tests are ignored when checking whether a proposed campaign is a duplicate edge. They remain historical evidence only and must not block a fresh campaign by themselves.
- The duplicate-edge gate now compares only against active `campaigns/`, active `backtest-campaigns/`, and current non-archived `research_ledger.csv` rows.
- Active rejected edge families from this run remain blocked from relaunch under a new active name: ES/MES micro-flow divergence, prior-session IBS, Connors RSI2, range-compression breakout, RTH intraday risk premium, overnight-intraday reversal, own-ES signed-orderflow persistence, opening-drive inventory/absorption, turn-of-month seasonality, daily time-series momentum, late-day market intraday momentum, volume-shock liquidity reversal, prior-day stop-run reclaim, VWAP pullback continuation, and CFTC/TFF hedging pressure.
- Policy artifact: `research_artifacts/duplicate_edge_scope_policy_20260615.md`.

## Current Data Gate

The retained external-data branches remain data-gated:

- `mes_es_flow_divergence_reversion/ES/1m/afternoon_mes_large20_buy_pressure_short_2020start` requires a longer ES+MES `trades` cache from `2020-01-01` onward. Local cache check found only `data/cache/orderflow/es_mes_flow_divergence_1m_20250610_20260608.csv` and `data/cache/orderflow/es_mes_price_flow_divergence_1m_20250610_20260608.csv`.
- `quote_liquidity_sweep_reversion/ES/1m/tbbo_failed_pdh_pdl_or30_sweep_reclaim` requires an approved ES `tbbo` pilot cache. Local cache check found no TBBO liquidity cache; only metadata/cost manifests and the pilot protocol are present.

No paid Databento data was pulled in this run.

Durable local-data/no-duplicate audit:
`research_artifacts/local_no_duplicate_data_gate_audit_20260615.md`.

Continuation audit after ES/MES rescue:
`research_artifacts/es_goal_continuation_audit_20260615.md`.

The original blocked/data-gate conclusion in that continuation audit was
temporarily superseded by the user's clarification that each failed variant can
be rescued once. After applying the clarified rule to all active failed
variants, the current conclusion remains fail-closed for the active set.

## Rescue Decision

All 75 active failed ES variants now have exactly one `rescue1` report. The 23
previously unrescued variants were given parameter-only rescue runs after the
user clarified that each failed variant can be rescued once. Existing `rescue1`
reports were not rerun, and no second rescue was created for any variant. The
later `es_signed_orderflow_persistence` campaign added five more failed variants
and five completed `rescue1` runs. The later
`es_opening_drive_inventory_absorption` campaign added five more failed
variants and five completed `rescue1` runs. The later
`es_turn_of_month_seasonality` campaign added five more failed variants and five
completed `rescue1` runs. The later `es_daily_time_series_momentum` campaign
added five more failed variants and five completed `rescue1` runs. The later
`es_late_day_intraday_momentum` campaign added five more failed variants and
five completed `rescue1` runs. The later
`es_volume_shock_liquidity_reversal` campaign added five more failed variants
and five completed `rescue1` runs. The later
`es_prior_day_stop_run_reclaim` campaign added five more failed variants and
five completed `rescue1` runs. The later
`es_vwap_pullback_continuation` campaign added five more failed variants and
five completed `rescue1` runs. The later
`es_cftc_tff_hedging_pressure` campaign added five more failed variants and
five completed `rescue1` runs.

Every rescue failed before WFA or at `limited_monkey_test`. The strongest
remaining surfaces still failed objective gates: the best new IBS rescue reached
only `0.5061728395061729` profitable core combinations, the best new Connors
RSI2 rescue reached `0.345679012345679`, the best new range-compression rescue
reached `0.4074074074074074`, and every fixed-time RTH premium rescue had a
`0.0` profitable-combo rate. The already-run ID/NR4 and ES/MES rescues failed
the random-placebo monkey median/profitability gates, and the already-run
high-gap overnight short rescue failed core at `0.691358024691358`.
The opening-drive inventory/absorption campaign failed before WFA; its best
rescue core rate was `0.4074074074074074`, and the only rescue to reach monkey
had `percentage_profitable=0.20666666666666667` with one-tick-worse stress
failing.
The turn-of-month seasonality campaign failed before monkey; its best rescue
core rate was only `0.07407407407407407`.
The daily time-series momentum campaign failed before monkey; its best rescue
core rate was only `0.2839506172839506`.
The late-day market intraday momentum campaign failed before monkey; every
original and rescue core grid had `0.0` profitable combinations.
The volume-shock liquidity reversal campaign failed before monkey; its best
rescue core rate was only `0.20987654320987653`, with only `13` top-row trades.
The prior-day stop-run reclaim campaign failed before WFA; its strongest rescue
passed the core profitable-combo gate but failed monkey with
`percentage_profitable=0.32666666666666666` and `median_net_profit=-770.0`.
The VWAP pullback-continuation campaign failed before WFA; its strongest rescue
passed the core profitable-combo gate but failed monkey with
`percentage_profitable=0.18` and `median_net_profit=-3210.0`.
The CFTC/TFF hedging-pressure campaign failed before WFA; its best rescue core
rate was only `0.3333333333333333`, with only `5` top-row trades.

No active rescued variant produced a candidate strategy for manual chart review
or paper incubation. No second rescue is permitted for these variants under the
current per-failed-variant rule. Consolidated audit:
`research_artifacts/all_failed_variant_rescue_audit_20260615.md`.

## Verification

- `python3 -m pytest tests/test_backtest_engine.py tests/test_campaign_stages.py tests/test_preflight.py`: PASS, 71 tests.
- `python3 -m pytest`: PASS, 348 tests.
- `python3 -m research.preflight --pytest-args "tests/test_backtest_engine.py tests/test_campaign_stages.py tests/test_preflight.py"`: PASS, 58 configs checked.
- `python3 -m pytest tests/test_config_layout.py tests/test_preflight.py`: PASS, 22 tests.
- `python3 -m research.preflight --skip-tests`: PASS, 66 configs checked.
- Active summary sweep over `backtest-campaigns/**/campaign_test_summary.json`: no active variant-level report has `passed=true`; all active runnable reports halted before WFA or are aggregate campaign summaries.
- `python3 -m research.preflight --config campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/afternoon_mes_large20_sell_pressure_long/config.yaml --skip-tests`: PASS, 1 config checked.
- `python3 -m propstack.run_campaign_stages --config campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/afternoon_mes_large20_sell_pressure_long/config.yaml --skip-validation`: completed, failed at `limited_monkey_test`.
- `python3 -m research.preflight --config campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/morning_mes_buy_pressure_reversion_short/config.yaml --skip-tests`: PASS, 1 config checked.
- `python3 -m propstack.run_campaign_stages --config campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/morning_mes_buy_pressure_reversion_short/config.yaml --skip-validation`: completed, failed at `limited_monkey_test`.
- `python3 -m research.preflight --skip-tests`: PASS, 68 configs checked.
- `python3 -m propstack.run_campaign_stages --config campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/afternoon_mes_large20_buy_pressure_short/config.yaml --fast-runtime-defaults`: completed, failed at `limited_monkey_test`.
- `python3 -m research.preflight --skip-tests`: PASS, 69 configs checked.
- `python3 -m propstack.run_campaign_stages --config campaigns/es_mes_micro_flow_divergence_reversion/rescue_attempts/parameter_space_rescue_1/morning_mes_sell_pressure_reversion_long/config.yaml --fast-runtime-defaults`: completed, failed at `limited_monkey_test`.
- `python3 -m pytest tests/test_config_layout.py tests/test_preflight.py`: PASS, 22 tests.
- `python3 -m research.preflight --skip-tests`: PASS, 70 configs checked.
- Targeted rescue preflight loop over `campaigns/*/rescue_attempts/parameter_space_rescue_1/*/config.yaml`: PASS, 30 rescue configs checked.
- Staged rescue loop over the 23 missing `rescue1` reports using `python3 -m propstack.run_campaign_stages --config <config> --fast-runtime-defaults`: completed; all 23 failed.
- Active ES variant-level summary sweep over 73 `campaign_test_summary.json` files after adding `es_signed_orderflow_persistence`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m research.preflight --skip-tests`: PASS, 93 configs checked after adding the missing rescue configs.
- `python3 -m pytest tests/test_preflight.py tests/test_config_layout.py`: PASS, 23 tests, including archive-path exclusion for active config discovery.
- `python3 -m research.preflight --skip-tests`: PASS, 108 active configs checked after adding `es_signed_orderflow_persistence` and applying archive-path exclusion.
- `python3 -m research.preflight --skip-tests --config <five es_signed_orderflow_persistence original configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests --config <five es_signed_orderflow_persistence rescue configs>`: PASS, 5 configs checked.
- `python3 -m propstack.run_campaign_stages --config <each es_signed_orderflow_persistence original/rescue config> --fast-runtime-defaults`: completed, all 10 runs failed at `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests --config <five es_opening_drive_inventory_absorption original configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests --config <five es_opening_drive_inventory_absorption rescue configs>`: PASS, 5 configs checked.
- `python3 -m propstack.run_campaign_stages --config <each es_opening_drive_inventory_absorption original/rescue config> --fast-runtime-defaults`: completed, all 10 valid runs failed before WFA; one transient process-pool error was rerun with the same frozen rescue config and completed normally.
- `python3 -m research.preflight --skip-tests`: PASS, 123 active configs checked after adding `es_opening_drive_inventory_absorption`.
- Active ES variant-level summary sweep over 83 `campaign_test_summary.json` files after adding `es_opening_drive_inventory_absorption`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m research.preflight --skip-tests --config <five es_turn_of_month_seasonality original configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests --config <five es_turn_of_month_seasonality rescue configs>`: PASS, 5 configs checked.
- `python3 -m pytest tests/test_preflight.py tests/test_config_layout.py tests/test_backtest_engine.py tests/test_campaign_stages.py`: PASS, 87 tests.
- `python3 -m propstack.run_campaign_stages --config <each es_turn_of_month_seasonality original/rescue config> --fast-runtime-defaults`: completed, all 10 runs failed at `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests`: PASS, 138 active configs checked after adding `es_turn_of_month_seasonality`.
- Active ES variant-level summary sweep over 93 `variant_test_summary.json` files after adding `es_turn_of_month_seasonality`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m research.preflight --skip-tests --config <five es_daily_time_series_momentum original configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests --config <five es_daily_time_series_momentum rescue configs>`: PASS, 5 configs checked.
- `python3 -m propstack.run_campaign_stages --config <each es_daily_time_series_momentum original/rescue config> --fast-runtime-defaults`: completed, all 10 runs failed at `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests`: PASS, 153 active configs checked after adding `es_daily_time_series_momentum`.
- Active ES variant-level summary sweep over 103 `variant_test_summary.json` files after adding `es_daily_time_series_momentum`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m research.preflight --skip-tests --config <five es_late_day_intraday_momentum original configs>`: PASS, 5 configs checked.
- `python3 -m pytest tests/test_strategy_modules.py -k 'late_day_intraday_momentum'`: PASS, 5 tests.
- `python3 -m propstack.run_campaign_stages --config <each es_late_day_intraday_momentum original/rescue config> --fast-runtime-defaults`: completed, all 10 corrected runs failed at `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests --config <five es_late_day_intraday_momentum rescue configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests`: PASS, 168 active configs checked after adding `es_late_day_intraday_momentum`.
- Active ES variant-level summary sweep over 113 `campaign_test_summary.json` files after adding `es_late_day_intraday_momentum`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m research.preflight --skip-tests --config <five es_volume_shock_liquidity_reversal original configs>`: PASS, 5 configs checked.
- `python3 -m pytest tests/test_strategy_modules.py -k 'volume_conditioned_liquidity_reversal'`: PASS, 2 tests.
- `python3 -m propstack.run_campaign_stages --config <each es_volume_shock_liquidity_reversal original/rescue config> --fast-runtime-defaults`: completed, all 10 runs failed at `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests --config <five es_volume_shock_liquidity_reversal rescue configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests`: PASS, 183 active configs checked after adding `es_volume_shock_liquidity_reversal`.
- Active ES variant-level summary sweep over 123 `campaign_test_summary.json` files after adding `es_volume_shock_liquidity_reversal`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m pytest tests/test_preflight.py tests/test_config_layout.py tests/test_backtest_engine.py tests/test_campaign_stages.py`: PASS, 87 tests after adding `es_volume_shock_liquidity_reversal`.
- `python3 -m research.preflight --skip-tests --config <five es_prior_day_stop_run_reclaim original configs>`: PASS, 5 configs checked.
- `python3 -m pytest tests/test_strategy_modules.py -k 'pdh_pdl_entry'`: PASS, 6 tests.
- `python3 -m propstack.run_campaign_stages --config <each es_prior_day_stop_run_reclaim original/rescue config> --fast-runtime-defaults`: completed, all 10 runs failed before WFA; one rescue reached and failed `limited_monkey_test`, the others failed `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests --config <five es_prior_day_stop_run_reclaim rescue configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests`: PASS, 198 active configs checked after adding `es_prior_day_stop_run_reclaim`.
- Active ES variant-level summary sweep over 133 `campaign_test_summary.json` files after adding `es_prior_day_stop_run_reclaim`: no report has `passed=true`; active variants missing `rescue1` report: `0`.
- `python3 -m pytest tests/test_preflight.py tests/test_config_layout.py tests/test_backtest_engine.py tests/test_campaign_stages.py`: PASS, 87 tests after adding `es_prior_day_stop_run_reclaim`.
- `python3 -m research.preflight --skip-tests --config <five es_vwap_pullback_continuation original configs>`: PASS, 5 configs checked.
- `python3 -m pytest tests/test_strategy_modules.py -k 'vwap_pullback_continuation'`: PASS, 6 tests.
- `python3 -m propstack.run_campaign_stages --config <each es_vwap_pullback_continuation original/rescue config> --fast-runtime-defaults`: completed, all 10 runs failed before WFA; one rescue reached and failed `limited_monkey_test`, the others failed `limited_core_grid_test`.
- `python3 -m research.preflight --skip-tests --config <five es_vwap_pullback_continuation rescue configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests`: PASS, 213 active configs checked after adding `es_vwap_pullback_continuation`.
- Active ES variant-level summary sweep over 143 raw active `campaign_test_summary.json` files after adding `es_vwap_pullback_continuation`: no report has `passed=true`; 70 latest original reports and 70 `rescue1` reports exist for the 70 active source variants; active variants missing `rescue1` report: `0`.
- `python3 -m pytest tests/test_preflight.py tests/test_config_layout.py tests/test_backtest_engine.py tests/test_campaign_stages.py`: PASS, 87 tests after adding `es_vwap_pullback_continuation`.
- `python3 -m research.preflight --skip-tests --config <five es_cftc_tff_hedging_pressure corrected original configs>`: PASS, 5 configs checked.
- `python3 -m pytest tests/test_strategy_modules.py -k 'cftc_tff'`: PASS, 3 tests.
- `python3 -m propstack.run_campaign_stages --config <each es_cftc_tff_hedging_pressure corrected original/rescue config> --fast-runtime-defaults`: completed, all 10 valid runs failed at `limited_core_grid_test`. Initial `run1` artifacts were invalidated because they predated non-null shifted CFTC feature coverage.
- `python3 -m research.preflight --skip-tests --config <five es_cftc_tff_hedging_pressure rescue configs>`: PASS, 5 configs checked.
- `python3 -m research.preflight --skip-tests`: PASS, 233 active configs checked after adding `es_cftc_tff_hedging_pressure`.
- Active ES variant-level summary sweep over 158 raw active `campaign_test_summary.json` files after adding `es_cftc_tff_hedging_pressure`: no report has `passed=true`; 75 latest original reports and 75 `rescue1` reports exist for the 75 active source variants; active variants missing `rescue1` report: `0`.

## Final Decision

FAIL

No strategy is a candidate for manual chart review or paper incubation from this run. Continuing the search without violating the duplicate-edge rule requires avoiding the currently active rejected edge families, now including own-ES signed-orderflow persistence, opening-drive inventory/absorption, turn-of-month seasonality, daily time-series momentum, late-day market intraday momentum, volume-shock liquidity reversal, prior-day stop-run reclaim, VWAP pullback continuation, and CFTC/TFF hedging pressure; archived tests no longer block a fresh campaign by themselves.

## ES Market Plumbing Liquidity Capacity - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_market_plumbing_liquidity_capacity/campaign.yaml` and exactly five variants using the existing `market_plumbing_priority` entry module with `percent_from_entry` stops and `fixed_r` targets.
- Created conservative lagged feature file `data/external/market_plumbing_priority_features_lag1_no_lookahead.csv`; source-row values are shifted by one listed trade date before use.
- Invalidated initial `run1` artifacts because `data.feature_set` used an unsupported descriptive label; corrected valid originals are `run2` with unchanged mechanics, parameters, timeframe, and data window.
- Original `run2` results: four variants failed `limited_core_grid_test`; `dealer_lending_pressure_long_1330` passed core at 0.7777777777777778 profitable combos but failed `limited_monkey_test` with percentage_profitable=0.25333333333333335 and median_net_profit=-1962.5.
- Rescue `rescue1` results: four variants failed `limited_core_grid_test`; `dual_pressure_priority_long_1130` passed core at 0.8888888888888888 profitable combos but failed `limited_monkey_test` with percentage_profitable=0.3466666666666667 and median_net_profit=-1665.0.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_strategy_modules.py -k market_plumbing_priority` PASS; `python3 -m research.preflight --skip-tests` PASS with 248 active configs after rescues.

## ES Bankruptcy Distress Regime Reversion - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_bankruptcy_distress_regime_reversion/campaign.yaml` and exactly five variants using `bankruptcy_distress_reversion`, `percent_from_entry`, and `fixed_r`.
- Used only derived U.S. Courts F-2 YoY/share/z-score features with explicit `effective_date`; raw parsed count columns were not signal inputs.
- Invalidated `run1` zero-trade artifacts because the limited-core first-window sample predated shared elevated-distress feature coverage; corrected `run2` changed only `start_date` to `2016-08-15`.
- Corrected originals: all five failed `limited_core_grid_test` with 0.0 profitable-combo rate.
- Rescues: all five one-time parameter-space-only rescues failed `limited_core_grid_test`; no run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.
- Verification: `python3 -m pytest tests/test_strategy_modules.py -k bankruptcy_distress_reversion` PASS; `python3 -m research.preflight --skip-tests` PASS with 268 active configs before rescue execution.


## ES Prior-Session Level Breakout Continuation - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_prior_session_level_breakout_continuation/campaign.yaml` and exactly five variants using `pdh_pdl_breakout_continuation`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope. This is distinct from active `es_prior_day_stop_run_reclaim`: it enters with confirmed breaks/holds outside prior RTH high/low rather than fading failed sweeps that close back inside.
- Original runs: all five failed `limited_core_grid_test`; best original was `morning_prior_high_breakout_long` at `0.691358024691358` profitable combinations, below the `0.70` core gate.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed. `gap_hold_two_sided_continuation` failed core at `0.654320987654321`; the other four passed core but failed `limited_monkey_test` with monkey profitable rates from `0.2` to `0.3466666666666667` and negative median net profit.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m research.preflight --skip-tests` PASS with `288` active configs after aggregate artifacts were written; active sweep found `90` source variants, `90` rescue configs, `198` raw variant reports, `0` passes, and no missing original/rescue reports.


## ES VPIN Toxicity Continuation - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_vpin_toxicity_continuation/campaign.yaml` and exactly five variants using `vpin_toxicity_continuation`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope. This is distinct from active raw signed-flow persistence and opening-drive inventory because it tests shifted prior-session VPIN/order-flow-toxicity proxy ranks at 13:30 ET.
- Data caveat: this is an OHLCV volume-bucket toxicity proxy, not tick-level VPIN with true buyer/seller classification.
- Original runs: four failed `limited_core_grid_test`; `slow_bucket_toxicity_long_1330` passed core at `0.8271604938271605` but failed `limited_monkey_test`.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed. `slow_bucket_toxicity_long_1330` rescue passed core at `1.0` profitable combinations but failed `limited_monkey_test`; the other four failed core.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_strategy_modules.py tests/test_features.py -k vpin` PASS; `python3 -m research.preflight --skip-tests` PASS with `303` active configs; active sweep found `95` source variants, `95` rescue configs, `208` raw variant reports, `0` passes, and no missing original/rescue reports.


## ES Overnight Return Late-Day Momentum - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_overnight_return_late_day_momentum/campaign.yaml` and exactly five variants using `overnight_return_late_day_momentum`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope. This is distinct from active early overnight-intraday reversal and first/last-window late-day intraday momentum because it uses prior-close-to-RTH-open overnight return as the late-day predictor.
- Original runs: all five failed `limited_core_grid_test` with `0.0` profitable-combo rate.
- Rescues: all five one-time parameter-space/fixed-parameter rescues also failed `limited_core_grid_test` with `0.0` profitable-combo rate.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_strategy_modules.py -k overnight_return_late_day_momentum` PASS; `python3 -m research.preflight --skip-tests` PASS with `318` active configs; active sweep found `100` source variants, `100` rescue configs, `218` raw variant reports, `0` passes, and no missing original/rescue reports.


## ES Prior-Level Delta Dislocation - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_prior_level_delta_dislocation/campaign.yaml` and exactly five variants using `positive_delta_dislocation`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope and ignored archived tests. This is distinct from active prior-level reclaim and breakout campaigns because it requires completed rolling 60-minute price/orderflow disagreement at prior RTH extremes.
- Originals: all five failed `limited_core_grid_test` with zero trades because the fixed fresh-level requirement was too restrictive at 60-minute signal boundaries.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed after disabling only the fixed fresh-level requirement and adjusting declared thresholds. All five failed `limited_core_grid_test`; best rescue was `pdl_sell_absorption_long/rescue1` with `0.5555555555555556` profitable combinations, `437.5` top net, and `15` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_strategy_modules.py tests/test_features.py -k 'positive_delta_dislocation or trade_orderflow or previous_rth_freshness'` PASS; `python3 -m research.preflight --skip-tests` PASS with `333` configs after aggregate artifacts; active sweep found `105` source variants, `105` rescue configs, `228` raw variant reports, `0` passes, and no missing original/rescue reports.


## ES Orderflow Absorption Exhaustion Reversal - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_orderflow_absorption_exhaustion_reversal/campaign.yaml` and exactly five variants using `orderflow_regime`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope and ignored archived tests. This is distinct from active signed-flow persistence because it fades extreme same-clock orderflow effort when price displacement is weak instead of following same-sign flow and return.
- Originals: one variant, `late_morning_15m_absorption_fade_1130`, passed core at `0.9382716049382716` profitable combinations but failed `limited_monkey_test` with monkey profitable rate `0.25` and median net `-190.0`; the other four failed core.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed and failed `limited_core_grid_test`.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_strategy_modules.py tests/test_features.py -k 'orderflow_regime or trade_orderflow_same_clock_ranks or trade_orderflow_signed_toxicity_same_clock_rank'` PASS; `python3 -m research.preflight --skip-tests` PASS with `348` active configs; active sweep found `110` source variants, `110` rescue configs, `238` raw variant-level reports, `0` passes, and no missing original or `rescue1` reports.


## ES Day-of-Week Seasonality - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_day_of_week_seasonality/campaign.yaml` and exactly five variants using `calendar_session_bias`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope and ignored archived tests. This is distinct from active `es_rth_intraday_risk_premium`, which tested unconditional all-weekday long RTH exposure, and distinct from active `es_turn_of_month_seasonality`, which tested monthly calendar windows.
- Originals: all five failed `limited_core_grid_test` with `0.0` profitable-combo rate. Best original was `monday_open_weekend_short_0935/run1` with top net `-800.0`, PF `0.9208508533267376`, and `65` top-combo trades.
- Rescues: all five one-time stop/target parameter-space rescues completed and failed `limited_core_grid_test` with `0.0` profitable-combo rate. Best rescue was `friday_open_preweekend_long_0935/rescue1` with top net `-1314.375`, PF `0.5172176308539945`, and `46` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_strategy_modules.py -k calendar_session_bias` PASS; `python3 -m research.preflight --skip-tests` PASS with `363` configs checked; active sweep found `115` source variants, `115` rescue configs, `248` raw variant-level reports, `0` passes, and no missing original or `rescue1` reports.


## ES Overnight Inventory Sweep Reversion - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_overnight_inventory_sweep_reversion/campaign.yaml` and exactly five variants using `overnight_inventory_reversion`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge check used active-only scope and ignored archived tests. This is distinct from active overnight gap/return reversal, overnight-return late-day continuation, and prior RTH level stop-run reclaim because it trades failed sweeps of completed ETH overnight high/low boundaries.
- Data audit: built `data/cache/databento/es_databento_ohlcv_1m_20100606_20260531_eth_rth_explicit_roll.parquet` from local monthly Databento OHLCV files using the explicit ES roll calendar, not same-day volume selection. Roll-boundary sessions are skipped in configs.
- Originals: `midpoint_low_sweep_reclaim_long/run1` passed core at `0.8271604938271605` profitable combinations but failed `limited_monkey_test` with monkey profitable rate `0.26` and median net `-601.25`; the other four originals failed `limited_core_grid_test`.
- Rescues: all five one-time parameter-space rescues completed and failed `limited_core_grid_test`.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `pytest tests/test_strategy_modules.py -k overnight_inventory` PASS; `python3 -m research.preflight --skip-tests` PASS with `378` configs checked; active sweep found `120` source variants, `120` rescue configs, `258` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## Active-Only Duplicate Recheck - 2026-06-16

Decision: FAIL.

- Archived tests remain ignored for duplicate-edge checks.
- Rechecked remaining unused local modules after `es_overnight_inventory_sweep_reversion`.
- Did not launch `intraday_capitulation_mr`: it is a stricter high-volume shock mean-reversion expression with RSI/VWAP filters and overlaps active volume-shock, Connors RSI/VWAP, and VWAP-context evidence.
- Did not launch pure opening-range breakout/fade: active `es_range_compression_breakout` already used opening-range breakout variants under the Crabel/NR7 compression thesis, so removing compression after active failures would relax mechanics post-result.
- Remaining local modules map to active intraday-momentum, signed-flow/orderflow, CFTC/TFF, market-plumbing, gap/overnight, or prior-level families.
- External-data gates remain unchanged: the longer ES+MES `trades` cache and ES `tbbo` liquidity cache are missing; no paid data was pulled.
- Verification: active sweep found `24` campaigns, `120` source variants, `120` rescue configs, `258` raw variant-level reports, `0` passes, and no active variants missing `rescue1`.


## ES/NQ Cross-Index Lead-Lag - 2026-06-16

Decision: FAIL.

- User-supplied Edge 5 was eligible as a local active-only campaign because full RTH ES and NQ Sierra order-flow caches exist and no active ES/NQ lead-lag campaign existed outside `_archived`.
- Created `campaigns/es_nq_cross_index_lead_lag/campaign.yaml` and exactly five variants using `es_nq_lead_lag`, `percent_from_entry`, and `fixed_r`.
- Built `data/cache/orderflow/es_nq_lead_lag_1m_20110103_20260609_full_rth_ny.parquet` from local ES/NQ caches; the builder aligned `1,484,730` shared minute bars and computes completed-window ES/NQ returns without future bars.
- Originals: all five failed `limited_core_grid_test` with `0.0` profitable-combo rate and zero benchmark-pass combinations. Best original was `morning_nq_down_es_lag_short_1000/run1` with top net `-273.75`, PF `0.9695833333333334`, and `96` top-combo trades.
- Rescues: all five one-time parameter-space rescues completed and failed `limited_core_grid_test`. Best rescue was `afternoon_nq_confirmed_follow_1400/rescue1` with profitable-combo rate `0.037037037037037035`, zero benchmark-pass combinations, top net `868.75`, PF `1.1387225548902196`, and `60` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_es_nq_lead_lag.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `393` active configs. Active sweep found `25` active campaigns, `125` source variants, `125` rescue configs, `268` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES FOMC Pre-Announcement Drift - 2026-06-16

Decision: FAIL.

- User-supplied Edge 3/4/5 review left a local, active-only non-duplicate event edge: scheduled-FOMC pre-announcement drift. The campaign used official Federal Reserve scheduled decision dates and local ES Sierra RTH data.
- Created `campaigns/es_fomc_pre_announcement_drift/campaign.yaml` and exactly five variants using `fomc_pre_announcement_drift`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/fomc_scheduled_decision_dates_20110101_20260609.csv` with `122` scheduled FOMC decision dates from `2011-01-26` through `2026-04-29`; unscheduled meetings, cancelled meetings, notation votes, and conference calls were excluded.
- Originals: all five failed. Best original was `decision_day_open_long_1000/run1` with profitable-combo rate `0.5555555555555556`, top net `238.75`, PF `1.2405541561712847`, and only `11` top-combo trades in the first 18-month core window.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed. `decision_day_open_long_1000/rescue1` passed the core profitable-combo gate at `0.75` but failed `limited_monkey_test` with `percentage_profitable=0.33666666666666667`, `median_net_profit=-298.75`, stress profitability `0.6166666666666667`, and one-tick-worse net `-80.0`. The other rescues failed `limited_core_grid_test`.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_fomc_pre_announcement_drift.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS. Active sweep after aggregation found `26` active campaigns, `130` source variants, `130` rescue configs, `278` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES Volatility-Managed Intraday Premium - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_volatility_managed_intraday_premium/campaign.yaml` and exactly five variants using `volatility_managed_intraday_premium`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_lagged_volatility_features_20110103_20260609.csv` from the local ES Sierra RTH cache. The feature builder shifts every realized-volatility, range, absolute-return, downside-semivolatility, and volatility-ratio feature one RTH session, so current-session range/high/low/close cannot enter the signal state.
- Originals: all five failed before WFA. Best original was `low_10d_range_midmorning_long_1030/run1` with profitable-combo rate `0.5185185185185185`, benchmark pass rate `0.18518518518518517`, top net `3055.0`, PF `1.2919254658385093`, and `99` top-combo trades.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed. `low_10d_range_midmorning_long_1030/rescue1` passed core with profitable-combo rate `0.7222222222222222`, but failed `limited_monkey_test` with `percentage_profitable=0.24` and `median_net_profit=-2081.25`. Actual trade-path stress passed, including one-tick-worse net `532.5`, but the required random-placebo monkey gate failed.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_volatility_managed_intraday_premium.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS. Active sweep after aggregation found `27` active campaigns, `135` source variants, `135` rescue configs, `288` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES Halloween Seasonal Premium - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_halloween_seasonal_premium/campaign.yaml` and exactly five variants using `halloween_seasonal_premium`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge scope was active-only and ignored `_archived`. This half-year seasonal effect is distinct from active day-of-week, turn-of-month, FOMC, volatility-state, and unconditional RTH premium families.
- Originals: all five failed `limited_core_grid_test`. Best original was `winter_midday_long_1200/run1` with profitable-combo rate `0.1111111111111111`, top net `475.0`, PF `1.026319434824768`, and best-day concentration `0.8578947368421053`.
- Rescues: all five one-time stop/target rescues completed and failed `limited_core_grid_test`. Best rescue was `winter_midday_long_1200/rescue1` with profitable-combo rate `0.5`, zero benchmark-passing combinations, top net `1000.0`, PF `1.0526870389884089`, MAR `0.22386592295394953`, and best-day concentration `0.77`.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_halloween_seasonal_premium.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS. Active sweep after aggregation found `28` active campaigns, `140` source variants, `140` rescue configs, `298` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES Quarterly Expiration Pressure - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_quarterly_expiration_pressure/campaign.yaml` and exactly five variants using `quarterly_expiration_pressure`, `percent_from_entry`, and `fixed_r`.
- Duplicate-edge scope was active-only and ignored `_archived`. This deterministic quarterly expiration/roll-calendar edge is distinct from day-of-week, turn-of-month, FOMC, Halloween, volatility-state, and unconditional RTH premium families.
- Originals: all five failed before WFA. Best original was `monday_after_expiration_reversal_long_1000/run1` with profitable-combo rate `0.6666666666666666`, zero benchmark-passing combinations, top net `895.0`, PF `4.008403361344538`, and only `6` top-combo trades.
- Rescues: all five one-time stop/target rescues completed. `monday_after_expiration_reversal_long_1000/rescue1` passed the core profitable-combo gate at `1.0`, but failed `limited_monkey_test` with `percentage_profitable=0.47` and `median_net_profit=-30.0`. Its actual trade-path stress stayed profitable, including one-tick-worse net `576.25`, but the required random-placebo monkey gate failed.
- No run reached WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_quarterly_expiration_pressure.py` PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `453` configs checked. Active sweep after aggregation found `29` active campaigns, `145` source variants, `145` rescue configs, `308` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES Pre-Holiday Effect - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_preholiday_effect/campaign.yaml` and exactly five variants using `preholiday_effect`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/nyse_preholiday_regular_sessions_20110103_20260609.csv` with `143` deterministic last-regular-session-before-full-NYSE-holiday rows. Early-close sessions are excluded to match the validated local RTH cache.
- Duplicate-edge scope was active-only and ignored `_archived`. This is distinct from day-of-week, turn-of-month, Halloween, FOMC, quarterly expiration, and unconditional RTH premium families because it conditions on full exchange holidays.
- Originals: all five failed `limited_core_grid_test`. Best original was `preholiday_late_long_1500/run1` with profitable-combo rate `0.3333333333333333`, zero benchmark-passing combinations, top net `88.125`, PF `1.235`, and best-day concentration `1.75177304964539`.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed and failed `limited_core_grid_test`. Best rescue was `preholiday_momentum_confirmed_midday_long_1200/rescue1` with profitable-combo rate `0.5`, zero benchmark-passing combinations, top net `232.5`, PF `2.2567567567567566`, and only `6` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_preholiday_effect.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `468` configs checked. Active sweep after aggregation found `30` active campaigns, `150` source variants, `150` rescue configs, `318` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES Turn-of-Year Effect - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_turn_of_year_effect/campaign.yaml` and exactly five variants using `turn_of_year_effect`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/nyse_turn_of_year_sessions_20110103_20260609.csv` with `107` deterministic turn-of-year rows covering the last five regular December sessions and first two regular January sessions. Early-close sessions are excluded to match the validated local RTH cache.
- Duplicate-edge scope was active-only and ignored `_archived`. This is distinct from active failed all-month turn-of-month, Halloween, pre-holiday, FOMC, quarterly-expiration, and unconditional RTH premium families because it tests the annual Christmas/New-Year window.
- Originals: all five failed `limited_core_grid_test`. Best original was `january_first2_open_long_1000/run1` with profitable-combo rate `0.3333333333333333`, zero benchmark-passing combinations, top net `222.5`, PF `2.435483870967742`, and only `3` top-combo trades.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed and failed `limited_core_grid_test`. Best rescue was `january_first2_open_long_1000/rescue1` with profitable-combo rate `0.4166666666666667`, zero benchmark-passing combinations, top net `222.5`, PF `2.435483870967742`, and only `3` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_turn_of_year_effect.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `483` configs checked. Active sweep after aggregation found `31` active campaigns, `155` source variants, `155` rescue configs, `328` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES BLS Macro Release-Day Drift - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_bls_macro_release_day_drift/campaign.yaml` and exactly five variants using `bls_macro_release_day_drift`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/bls_macro_release_dates_20110103_20260609.csv` from ALFRED/FRED BLS release-date downloads. It contains `386` rows: `190` Employment Situation releases and `196` CPI releases. The release date is known before RTH; release values, revisions, and surprises are not used.
- Duplicate-edge scope was active-only and ignored `_archived`. This is distinct from active FOMC pre-announcement drift because it conditions on BLS 08:30 ET CPI/Employment Situation dates and tests only post-release RTH behavior.
- Originals: all five failed `limited_core_grid_test`. Best original was `employment_release_open_long_1000/run1` with profitable-combo rate `0.4444444444444444`, zero benchmark-passing combinations, top net `427.5`, PF `1.3949191685912241`, and only `17` top-combo trades.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed and failed `limited_core_grid_test`. Best rescue was `employment_release_open_long_1000/rescue1` with profitable-combo rate `0.5833333333333334`, zero benchmark-passing combinations, top net `465.0`, PF `1.382716049382716`, and only `17` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_bls_macro_release_day_drift.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `498` configs checked. Active sweep after aggregation found `32` active campaigns, `160` source variants, `160` rescue configs, `338` raw variant-level reports, `0` passes, and no active variants missing a latest original or `rescue1` report.


## ES Term-Structure Lead-Lag Feedback - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_term_structure_lead_lag_feedback/campaign.yaml` and exactly five variants using `es_term_structure_lead_lag`, `percent_from_entry`, and `fixed_r`.
- Built `data/cache/orderflow/es_term_structure_lead_lag_1m_20110311_20260316_full_rth_ny.parquet` from local ES front-contract cache, raw Sierra contract files, and the explicit ES roll calendar. The builder uses the next explicit roll-calendar contract as deferred, not same-day volume, and computes rolling front/deferred return gaps from completed current-or-prior minutes only.
- Cache validation: `111930` rows, `287` aligned RTH sessions, first timestamp `2011-03-11 09:30:00`, last timestamp `2026-03-16 15:59:00`, no duplicate timestamps, no invalid OHLC rows, and missing deferred file `ESU26`.
- Originals: all five failed `limited_core_grid_test`. Best original was `late_morning_two_sided_spread_feedback_1130/run1` with profitable-combo rate `0.48148148148148145`, zero benchmark-passing combinations, top net `342.5`, PF `69.5`, and only `4` top-combo trades.
- Rescues: all five one-time parameter-space rescues completed and failed `limited_core_grid_test`. Best rescue was `late_day_two_sided_spread_feedback_1530/rescue1` with profitable-combo rate `0.2222222222222222`, zero benchmark-passing combinations, top net `100.0`, and only `5` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_es_term_structure_lead_lag.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `513` configs checked. Active sweep after aggregation found `33` active campaigns, `165` source variants, `165` rescue configs, `348` raw variant-level reports, `0` passes, and no active variants missing any original run or `rescue1` report.


## ES Monthly OPEX Pressure - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_monthly_opex_pressure/campaign.yaml` and exactly five variants using `monthly_opex_pressure`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/nyse_monthly_opex_sessions_20110103_20260609.csv` with `555` deterministic monthly OPEX signal rows: `124` non-quarterly rows each for previous regular session, OPEX session, and next regular session, plus `61` quarterly rows for each signal type. All strategy configs set `include_quarterly_months: false`.
- Duplicate-edge scope was active-only and ignored `_archived`. This edge is distinct from active failed `es_quarterly_expiration_pressure` because it excludes March, June, September, and December and tests non-quarterly monthly listed-option expiration/pinning/unwind pressure rather than quarterly futures roll and quarterly expiration mechanics.
- Originals: all five failed `limited_core_grid_test`. Best original was `nonquarterly_opex_thursday_positioning_short_1330/run1` with profitable-combo rate `0.5555555555555556`, zero benchmark-passing combinations, top net `740.0`, PF `2.0033898305084747`, and only `12` top-combo trades.
- Rescues: all five one-time stop/target parameter-space rescues completed and failed `limited_core_grid_test`. Best rescue was `nonquarterly_opex_thursday_positioning_short_1330/rescue1` with profitable-combo rate `0.5833333333333334`, zero benchmark-passing combinations, top net `830.625`, PF `2.1536458333333335`, and only `12` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_monthly_opex_pressure.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `528` configs checked. Active sweep after aggregation found `34` active campaigns, `170` source variants, `170` rescue configs, `358` raw variant-level reports, `0` passes, and no active variants missing any original run or `rescue1` report.


## ES VIX Expiration Pressure - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_vix_expiration_pressure/campaign.yaml` and exactly five variants using `vix_expiration_pressure`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/vix_expiration_sessions_20110103_20260609.csv` with `555` deterministic signal rows covering previous regular session, VIX expiration session, and next regular session. The calendar applies the monthly VIX standard expiration rule against the following-month SPX standard expiration session, with holiday/early-close shifts handled before testing.
- Duplicate-edge scope was active-only and ignored `_archived`. This edge is distinct from monthly and quarterly OPEX campaigns because it tests VIX derivatives settlement/SOQ pressure rather than equity/index listed-option expiration or ES quarterly roll pressure.
- Originals: all five failed `limited_core_grid_test`. Best original was `vix_settlement_open_pressure_short_1000/run1` with profitable-combo rate `0.6666666666666666`, zero benchmark-passing combinations, top net `1040.0`, PF `1.4952380952380953`, and only `17` top-combo trades.
- Rescues: all five one-time stop/target parameter-space rescues completed and failed `limited_core_grid_test`. Best rescue was `vix_settlement_open_pressure_short_1000/rescue1` with profitable-combo rate `0.5833333333333334`, zero benchmark-passing combinations, top net `2208.75`, PF `2.2004076086956523`, and only `17` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_vix_expiration_pressure.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; `python3 -m research.preflight --skip-tests` PASS with `543` configs checked. Active sweep after aggregation found `35` active campaigns, `175` source variants, `175` rescue configs, `368` raw variant-level reports, `0` passes, and no active variants missing any original run or `rescue1` report.


## ES Realized Skewness Reversal - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_realized_skewness_reversal/campaign.yaml` and exactly five variants using `realized_skewness_reversal`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_lagged_realized_skewness_features_20110103_20260609.csv` from local ES Sierra RTH 1-minute bars. It contains `3817` sessions and `3755` valid rolling-rank rows. Every tradable feature is shifted one completed RTH session to avoid current-session lookahead.
- Duplicate-edge scope was active-only and ignored `_archived`. This edge is distinct from active failed volatility-managed, daily momentum, RSI pullback, volume shock, and IBS reversion campaigns because it tests lagged third-moment asymmetry ranks rather than return trend, volatility level, or prior close-location.
- Originals: all five failed `limited_core_grid_test`. Best original was `high_1d_skew_open_short_1000/run1` with profitable-combo rate `0.037037037037037035`, zero benchmark-passing combinations, top net `112.5`, PF `1.0221021611001964`, and `80` top-combo trades.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed and failed `limited_core_grid_test`. Best rescue was `high_1d_skew_open_short_1000/rescue1` with profitable-combo rate `0.07407407407407407`, zero benchmark-passing combinations, top net `365.0`, PF `1.0882175226586104`, and `67` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_realized_skewness_reversal.py` PASS; targeted preflight for five originals and five rescues PASS with `10` configs checked. Repo-wide `python3 -m research.preflight --skip-tests` was manually interrupted after about 2.5 minutes while loading parquet data and did not produce a pass/fail result. Active sweep after aggregation found `36` active campaigns, `180` source variants, `180` rescue configs, `378` raw variant-level reports, `0` passes, and no active variants missing any original run or `rescue1` report.


## ES Variance Risk Premium Intraday - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_variance_risk_premium_intraday/campaign.yaml` and exactly five variants using `variance_risk_premium_intraday`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_variance_risk_premium_features_20110103_20260609.csv` from free Cboe VIX daily history plus local ES Sierra RTH 1-minute bars. It contains `3817` sessions and `3735` valid rolling-rank rows. VIX close and ES realized variance are shifted one completed RTH session to avoid current-session lookahead.
- Duplicate-edge scope was active-only and ignored `_archived`. This edge is distinct from active failed realized-volatility-managed, market-plumbing, VIX-expiration, skewness, and daily-momentum families because it tests lagged option-implied variance minus realized variance.
- Originals: all five failed `limited_core_grid_test`. Best original was `low_vrp_open_short_1000/run1` with profitable-combo rate `0.1111111111111111`, zero benchmark-passing combinations, top net `877.5`, PF `1.2184194150591163`, and only `52` top-combo trades with `45.437723555084474` trades/year.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed and failed `limited_core_grid_test`. Best rescue was `high_vrp_low_realized_midmorning_long_1030/rescue1` with profitable-combo rate `0.12345679012345678`, zero benchmark-passing combinations, top net `1220.0`, PF `1.3388888888888888`, and only `36` top-combo trades.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_variance_risk_premium_intraday.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS. Active sweep after aggregation found `37` active campaigns, `185` source variants, `185` rescue configs, `388` raw variant-level reports, `0` passes, and no active variants missing any original run or `rescue1` report.


## ES Realized Jump Variation Premium - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_realized_jump_variation_premium/campaign.yaml` and exactly five variants using `realized_jump_variation_premium`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_realized_jump_variation_features_20110103_20260609.csv` from local ES Sierra RTH 1-minute bars. It contains `3817` sessions and `3759` valid rolling-rank rows. Realized variance, bipower variation, jump variation, signed large-return jump proxies, and ranks are shifted one completed RTH session before use.
- Duplicate-edge scope was active-only and ignored `_archived`. This edge is distinct from active failed volatility-managed, realized-skewness, variance-risk-premium, VPIN/toxicity, and daily-momentum families because it tests discontinuous jump variation separated from continuous variation using bipower variation.
- Originals: all five failed `limited_core_grid_test` with `0.0` profitable-combo rate. Best original was `positive_jump_reversal_short_1200/run1` with top net `-110.0`, PF `0.98661800486618`, and `87` top-combo trades.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed and failed `limited_core_grid_test`. Best rescue was `positive_jump_reversal_short_1200/rescue1` with profitable-combo rate `0.1111111111111111`, zero benchmark-passing combinations, top net `2304.375`, PF `1.3012254901960785`, and `66` top-combo trades; it failed the required `0.70` profitable-combo core gate and `preferred_min_total_trades`.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_realized_jump_variation_premium.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS. Active sweep after aggregation found `38` active campaigns, `190` source variants, `190` rescue configs, `398` raw variant-level reports, `0` passes, and no active variants missing any original run or `rescue1` report.


## Limited Core Grid Period Reporting - 2026-06-16

Decision: INFRASTRUCTURE FIX.

- Clarified limited-core grid reporting after review of `long_only_trend_1000/ES/rescue1`: the current shortlist stage is a fixed first-18-month window, not a dynamic 10 percent sample.
- Updated new limited-core, limited-monkey, WFA, acceptance, and train-selection summary outputs to include `configured_data_subset`, `resolved_data_subset`, and `actual_data_period` with first/last timestamps, row counts, and timeframe metadata where a stage prepares a bounded data subset.
- Existing run artifacts still expose the authoritative period through stage-level `data_quality.first_timestamp` and `data_quality.last_timestamp`; new runs will also expose the period directly in the relevant stage summaries.
- Verification: `python3 -m pytest tests/test_campaign_stages.py` PASS; `python3 -m pytest tests/test_core_grid.py::test_core_grid_summary_and_iteration_audit_reports` PASS.


## Paid Data Consent Guard - 2026-06-16

Decision: INFRASTRUCTURE FIX.

- User policy is now explicit: never download data that costs money unless the
  user explicitly approves the exact paid data pull.
- Added `research_artifacts/paid_data_consent_policy_20260616.md`.
- Updated `python3 -m propstack.download_databento_rth_trades` to refuse any
  non-dry-run Databento request unless `--paid-data-approved` is passed after
  explicit user permission.
- Dry-run metadata/cost checks and free public-data downloads remain allowed for
  research triage.
- Confirmed no Databento downloader process was running after the stopped ES
  `trades` pull.


## ES Active Set Data-Gate Refresh - 2026-06-16

Decision: FAIL.

- Refreshed the active inventory after the latest local-only campaigns and the limited-core reporting fix. Current active sweep found `38` active campaigns, `190` source variants, `190` rescue configs, `398` raw variant-level reports, `0` passes, and no active variants missing an original or `rescue1` report.
- Added `research_artifacts/es_active_set_data_gate_refresh_20260616.md` and a `research_ledger.csv` continuation-audit row.
- Verified the retained external-data branch inputs are still missing: `data/cache/orderflow/es_mes_flow_divergence_1m_20200101_20260609.csv`, `data/cache/orderflow/es_mes_price_flow_divergence_1m_20200101_20260609.csv`, and `data/cache/orderflow/es_tbbo_liquidity_1m_20250609_20260609.csv`.
- No paid data was downloaded. The current local active campaign set has no ES candidate strategy; continuing without weakening the methodology requires either approved external data or a genuinely new dense point-in-time local source that is not a duplicate of an active failed edge.


## ES Treasury Rate Shock Intraday - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_treasury_rate_shock_intraday/campaign.yaml` and exactly five variants using `treasury_rate_state`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_treasury_rate_state_features_20110103_20260609.csv` from the free U.S. Treasury Daily Treasury Rates CSV endpoint plus local ES Sierra RTH bars. The feature builder maps each ES session to the latest Treasury observation date strictly before the ES session date.
- Pre-backtest signal-density audit passed after adjusting one two-condition grid before performance testing: `research_artifacts/es_treasury_rate_shock_intraday_density_audit_20260616.md`. All declared entry grid cells clear 50 trades/year.
- Originals: all five failed `limited_core_grid_test`. Best original was `rate_up_high_level_short_1030/run1` with profitable-combo rate `0.027777777777777776` and top net `30.0`.
- Rescues: all five one-time parameter-space rescues completed and failed `limited_core_grid_test`. Best rescue was `rate_up_high_level_short_1030/rescue1` with profitable-combo rate `0.08333333333333333` and top net `114.375`.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- The user-provided video edge list was reviewed in `research_artifacts/es_video_edge_queue_review_20260616.md`; no immediate non-duplicate ES campaign was queued from that list.
- Verification: `python3 -m pytest tests/test_treasury_rate_state.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; Databento paid-download guard refused a non-dry-run command without `--paid-data-approved`.


## ES OFR Financial Stress Intraday - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_ofr_financial_stress_intraday/campaign.yaml` and exactly five variants using `ofr_financial_stress`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_ofr_financial_stress_features_20110103_20260609.csv` from the free official OFR Financial Stress Index CSV plus local ES Sierra RTH bars. The feature builder maps each ES session to the latest OFR observation on or before `session_date - 2 business days`.
- Pre-backtest signal-density audit passed: `research_artifacts/es_ofr_financial_stress_intraday_density_audit_20260616.md`. Declared grids cleared the 50 trades/year density gate before performance testing.
- Originals: all five failed `limited_core_grid_test` with `0.0` profitable-combo rate.
- Rescues: all five one-time parameter-space rescues completed and failed `limited_core_grid_test`. Best rescue profitable-combo rate was `0.5185185185185185`, below the required `0.70`, with zero benchmark-passing combinations.
- No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_ofr_financial_stress.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS; active sweep found 40 campaigns, 200 source variants, 200 rescue configs, 418 raw variant-level reports, 0 passes, and no missing `rescue1` reports.


## ES VVIX Tail Risk Intraday - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_vvix_tail_risk_intraday/campaign.yaml` and exactly five variants using `vvix_tail_risk`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_vvix_tail_risk_features_20110103_20260609.csv` from free official Cboe VVIX and VIX daily index CSVs plus local ES Sierra RTH bars. The feature builder maps each ES session to the latest Cboe observation strictly before the ES session date.
- Pre-backtest signal-density audit passed: `research_artifacts/es_vvix_tail_risk_intraday_density_audit_20260616.md`. Declared original and rescue grids cleared the 50 trades/year density gate before performance testing.
- Originals: all five failed `limited_core_grid_test`. Best original was `low_vvix_long_1030/run1` with profitable-combo rate `0.5185185185185185`, but it remained below the required `0.70` and failed trade-count/concentration gates.
- Rescues: all five one-time parameter-space rescues completed. Four failed `limited_core_grid_test`. `low_vvix_long_1030/rescue1` passed core with profitable-combo rate `0.9629629629629629`, but failed `limited_monkey_test` with random-placebo profitable rate `0.31666666666666665` and median net profit `-1482.5`.
- No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_vvix_tail_risk.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS.


## ES EPU Policy Uncertainty Intraday - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_epu_policy_uncertainty_intraday/campaign.yaml` and exactly five variants using `epu_policy_uncertainty`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_epu_policy_uncertainty_features_20110103_20260609.csv` from the free public Daily U.S. EPU CSV plus local ES Sierra RTH bars. The feature builder maps each ES session to the latest EPU observation on or before `session_date - 30 calendar days` to avoid recent-revision leakage.
- Pre-backtest signal-density audit passed: `research_artifacts/es_epu_policy_uncertainty_intraday_density_audit_20260616.md`. Declared original and rescue entry grids cleared the 50 trades/year density gate before performance testing.
- Originals: all five failed `limited_core_grid_test`. Best original was `low_epu_long_1030/run1` with profitable-combo rate `0.1111111111111111`, zero benchmark-passing combinations, top net `922.5`, and top PF `1.0687406855439643`.
- Rescues: all five one-time parameter-space rescues completed and failed `limited_core_grid_test`. Best rescue was `low_epu_long_1030/rescue1` with profitable-combo rate `0.4074074074074074`, zero benchmark-passing combinations, top net `2170.625`, and top PF `1.1913709499669385`.
- No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_epu_policy_uncertainty.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS.


## ES Consumer Sentiment State Intraday - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_consumer_sentiment_state_intraday/campaign.yaml` and exactly five variants using `consumer_sentiment_state`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_consumer_sentiment_features_20110103_20260609.csv` from the free public FRED/University of Michigan `UMCSENT` CSV plus local ES Sierra RTH bars. The feature builder maps each ES session to the latest UMCSENT observation on or before `session_date - 45 calendar days`.
- Pre-backtest signal-density audit passed: `research_artifacts/es_consumer_sentiment_state_intraday_density_audit_20260616.md`. Declared original grids cleared the 50 trades/year density gate before performance testing.
- Originals: all five failed `limited_core_grid_test`. Best original was `falling_sentiment_short_1200/run1` with profitable-combo rate `0.0`, zero benchmark-passing combinations, top net `-507.5`, and top PF `0.9586136595310907`.
- Rescues: all five one-time parameter-space rescues completed and failed `limited_core_grid_test`. Best rescue was `high_sentiment_short_1030/rescue1` with profitable-combo rate `0.07407407407407407`, zero benchmark-passing combinations, top net `140.0`, top PF `1.1454545454545455`, and only `12` top-combo trades.
- No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_consumer_sentiment_state.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS.


## ES Cboe Put/Call Sentiment Intraday - 2026-06-16

Decision: FAIL.

- Created `campaigns/es_cboe_put_call_sentiment_intraday/campaign.yaml` and exactly five variants using `cboe_put_call_sentiment`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_cboe_put_call_features_20110103_20260609.csv` from free public Cboe equity/index/total put-call ratio CSVs plus local ES Sierra RTH bars. The feature builder maps each ES session to the latest Cboe observation strictly before the ES session date.
- Pre-backtest signal-density audit passed: `research_artifacts/es_cboe_put_call_sentiment_intraday_density_audit_20260616.md`. Declared original grids cleared the 50 trades/year density gate before performance testing.
- Originals: all five failed `limited_core_grid_test`. Best original was `falling_total_pc_long_1130/run1` with profitable-combo rate `0.5185185185185185`, one benchmark-passing combination, top net `3262.5`, top PF `1.2238805970149254`, and top MAR `1.5534026510713692`.
- Rescues: all five one-time parameter-space rescues completed. Three failed `limited_core_grid_test`. `falling_total_pc_long_1130/rescue1` passed core with profitable-combo rate `1.0` but failed `limited_monkey_test` with random-monkey profitable rate `0.19666666666666666` and median net `-2727.5`. `high_total_vs_equity_pc_short_1330/rescue1` passed core with profitable-combo rate `0.8888888888888888` but failed `limited_monkey_test` with random-monkey profitable rate `0.06666666666666667`, median net `-3923.75`, and one-tick-worse stress not profitable.
- No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_cboe_put_call_sentiment.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS.


## ES Oil Price Shock Spillover - 2026-06-17

Decision: FAIL.

- Created `campaigns/es_oil_price_shock_spillover/campaign.yaml` and exactly five variants using `oil_price_shock_spillover`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_oil_price_shock_features_20110103_20260609.csv` from free public EIA WTI and Brent daily spot-price XLS files plus local ES Sierra RTH bars. The feature builder maps each ES session to the latest EIA oil observation on or before `session_date - 2` business days.
- Pre-backtest signal-density audit passed: `research_artifacts/es_oil_price_shock_spillover_density_audit_20260617.md`. Declared original and rescue grids cleared the 50 trades/year density gate before performance testing.
- Originals: all five failed `limited_core_grid_test`. Best original was `wti_up_risk_off_short_1030/run1` with profitable-combo rate `0.07407407407407407`, zero benchmark-passing combinations, top net `1250.0`, top PF `1.0855871276959945`, and top MAR `0.23116690498374848`.
- Rescues: all five one-time parameter-space rescues completed. Four failed `limited_core_grid_test`. `wti_up_risk_off_short_1030/rescue1` passed core with profitable-combo rate `0.7777777777777778`, but failed `limited_monkey_test` with random-monkey profitable rate `0.17`, median net `-3905.0`, trade-path stress profitable rate `0.15666666666666668`, and one-tick-worse stress not profitable.
- No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_oil_price_shock_spillover.py` PASS; targeted preflight for five originals PASS; targeted preflight for five rescues PASS.


## Staged Core/Monkey Gate Correction - 2026-06-17

Decision: INFRASTRUCTURE FIX; prior active core/monkey artifacts require manual
review when they depended on the corrected gates.

- Corrected `limited_core_grid_test` so a core stage must have at least one
  benchmark-passing parameter combination in addition to the existing valid combo
  count, `>=70%` profitable-combo rate, and zero prop-rule violations.
- Corrected monkey-stage criteria so random-placebo monkey comparisons are
  diagnostic output only, while actual trade-path stress is the pass/fail gate:
  `>=80%` profitable, median positive, one-tick-worse profitable, and zero
  prop-rule violations.
- Limited monkey parameter handoff now prefers profitable benchmark-passing core
  grid rows when available, rather than any profitable core row.
- Active artifact scan after the fix found `27` prior core-stage passes now
  invalid because `number_passing_benchmark=0`, and `2` prior limited-monkey
  failures that should advance under the corrected monkey gate.
- Reran the two affected valid-core rescues without changing mechanics or
  parameter space:
  - `es_volatility_managed_intraday_premium/low_10d_range_midmorning_long_1030/ES/rescue1`
    passed corrected core and monkey, then failed WFA early exit because selected
    first-window IS PF was `0.87 < 1.00`.
  - `es_cboe_put_call_sentiment_intraday/falling_total_pc_long_1130/ES/rescue1`
    passed corrected core and monkey, then failed WFA early exit because selected
    first-window IS PF was `0.99 < 1.00`.
- Updated affected aggregate summaries and appended research-ledger rows. No
  strategy mechanics, signal definitions, parameter spaces, or data sources were
  changed. No paid data was downloaded.
- Verification: `python3 -m pytest tests/test_campaign_stages.py` PASS; `python3
  -m pytest tests/test_monkey.py tests/test_core_grid.py` PASS; affected variant
  JSON summaries validate with `python3 -m json.tool`.


## Active Aggregate Backfill - 2026-06-17

Decision: INFRASTRUCTURE / BOOKKEEPING FIX.

- Backfilled missing campaign-level aggregate summaries from existing run
  artifacts only:
  - `backtest-campaigns/es_connors_rsi2_mean_reversion/campaign_test_summary.json`
  - `backtest-campaigns/es_mes_micro_flow_divergence_reversion/campaign_test_summary.json`
  - `backtest-campaigns/es_prior_session_ibs_reversion/campaign_test_summary.json`
- Normalized older aggregate summaries with `decision: FAIL` but no explicit
  status to `status: completed`.
- Under corrected gates, Connors RSI2 and prior-session IBS fail
  `limited_core_grid_test`; ES/MES divergence reports that historically reached
  monkey are corrected-core failures where benchmark-passing combinations are
  zero.
- Active authored campaigns now have matching aggregate summaries. No strategy
  mechanics, signal definitions, parameter spaces, or data sources were changed.
  No paid data was downloaded.


## ES Dollar Risk-Appetite Intraday Spillover - 2026-06-17

Decision: FAIL.

- Created `campaigns/es_dollar_risk_appetite_intraday/campaign.yaml` and
  exactly five variants using `dollar_risk_appetite`,
  `percent_from_entry`, and `fixed_r`.
- Built `data/external/es_dollar_risk_appetite_features_20110103_20260609.csv`
  from the free official FRED/Federal Reserve `DTWEXBGS` nominal broad dollar
  index plus local ES Sierra RTH bars. The feature builder maps each ES session
  to the latest dollar observation on or before `session_date - 1` business day.
- Pre-backtest density audit passed:
  `research_artifacts/es_dollar_risk_appetite_intraday_density_audit_20260617.md`.
  The narrowest declared condition still had about `53.53` eligible sessions per
  year before performance testing.
- Originals: all five failed `limited_core_grid_test` with `0.0` profitable
  combinations and zero benchmark-passing combinations. Best original was
  `high_dollar_up_short_1130/run1` with top net `-295.0`, top PF
  `0.9749362786745964`, and `79` top-combo trades.
- Rescues: all five one-time parameter-space rescues completed and all failed
  `limited_core_grid_test` with `0.0` profitable combinations and zero
  benchmark-passing combinations. Best rescue was
  `dollar_down_risk_on_long_1030/rescue1` with top net `-1880.625`, top PF
  `0.7975100942126514`, and `118` top-combo trades.
- No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated
  incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_dollar_risk_appetite.py` PASS;
  targeted preflight for five originals PASS; targeted preflight for five
  rescues PASS.


## ES Trade-Size Segmented Stealth Orderflow - 2026-06-17

Decision: FAIL.

- Added `trade_size_segment_orderflow`, a completed-bar entry module that
  computes large-trade and residual smaller-flow imbalance from existing local
  Sierra aggregate orderflow features. It follows the larger-trade direction
  only when the large-vs-residual disagreement is large enough.
- Created `campaigns/es_trade_size_stealth_orderflow/campaign.yaml` and exactly
  five variants, each with `trade_size_segment_orderflow`,
  `percent_from_entry`, `fixed_r`, README, and config.
- Pre-backtest density audit passed:
  `research_artifacts/es_trade_size_stealth_orderflow_density_audit_20260617.md`.
  Every frozen variant shape had a predeclared threshold point near or above 50
  signals/year before performance testing.
- Originals: all five failed `limited_core_grid_test`. Best original was
  `large20_loose_short_1030/run1` with profitable-combo rate
  `0.5061728395061729`, zero benchmark-passing combinations, top net `1920.0`,
  top PF `1.3251481795088909`, and `101` top-combo trades.
- Rescues: all five one-time parameter-space rescues completed and all failed
  `limited_core_grid_test`. Best rescue was `large20_loose_short_1030/rescue1`
  with profitable-combo rate `0.19753086419753085`, zero benchmark-passing
  combinations, top net `1670.0`, top PF `1.2616529573051312`, and `106`
  top-combo trades.
- No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated
  incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_trade_size_segment_orderflow.py
  tests/test_strategy_modules.py -q` PASS; targeted preflight for five
  originals PASS; targeted preflight for five rescues PASS.


## ES Trade Fragmentation Liquidity Reversion - 2026-06-17

Decision: FAIL.

- Added `trade_fragmentation_liquidity_reversion`, a completed-bar entry module
  that combines high same-clock rolling trade-count rank with low same-clock
  rolling average-trade-size rank, then fades a completed 15, 30, or 60 minute
  price move using next-bar-open execution.
- Created `campaigns/es_trade_fragmentation_liquidity_reversion/campaign.yaml`
  and exactly five variants, each with `trade_fragmentation_liquidity_reversion`,
  `percent_from_entry`, `fixed_r`, README, and config.
- Pre-backtest density audit passed:
  `research_artifacts/es_trade_fragmentation_liquidity_reversion_density_audit_20260617.md`.
  The frozen base thresholds produced plausible signal density above 50
  signals/year before any PnL testing.
- Originals: all five failed `limited_core_grid_test` with `0.0` profitable
  combinations and zero benchmark-passing combinations. Best original by
  top-combo net profit was `morning_15m_fragmented_up_fade_short/run1` with top
  net `-1984.375`, top PF `0.7422052614485223`, and `105` top-combo trades.
- Rescues: all five one-time parameter-space rescues completed and all failed
  `limited_core_grid_test` with `0.0` profitable combinations and zero
  benchmark-passing combinations. Best rescue by top-combo net profit was
  `midday_30m_fragmented_down_fade_long/rescue1` with top net `-3803.75`, top PF
  `0.45854092526690393`, and `167` top-combo trades.
- No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated
  incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_trade_fragmentation_liquidity_reversion.py
  tests/test_strategy.py tests/test_preflight.py tests/test_campaign_stages.py
  tests/test_core_grid.py tests/test_monkey.py -q` PASS with `64` tests;
  targeted preflight for five originals and five rescues PASS.


## ES Realized Semivariance Asymmetry - 2026-06-17

Decision: FAIL.

- Added `realized_semivariance_asymmetry`, a completed-bar entry module that
  uses lagged prior-session downside semivariance, upside semivariance,
  downside share, and bad-minus-good semivariance balance ranks.
- Added `tools/build_es_realized_semivariance_features.py`, which builds
  `data/external/es_realized_semivariance_features_20110103_20260609.csv` from
  local Sierra ES RTH bars and shifts every tradable feature one completed RTH
  session before use.
- Created `campaigns/es_realized_semivariance_asymmetry/campaign.yaml` and
  exactly five variants, each with `realized_semivariance_asymmetry`,
  `percent_from_entry`, `fixed_r`, README, and config.
- Pre-backtest density audit passed:
  `research_artifacts/es_realized_semivariance_asymmetry_density_audit_20260617.md`.
  Every declared threshold had expected signal density above 50 trades/year.
- Originals: all five failed `limited_core_grid_test`. Best original was
  `high_1d_badvol_continuation_short_1030/run1` with profitable-combo rate
  `0.2222222222222222`, zero benchmark-passing combinations, top net `2302.5`,
  top PF `1.1168336927565647`, and `132` top-combo trades.
- Rescues: all five one-time parameter-space rescues completed. Four failed
  `limited_core_grid_test`. `high_1d_badvol_continuation_short_1030/rescue1`
  passed core and limited monkey, then failed `walk_forward_analysis` with
  `early_exit=true`, stitched OOS net `-9625.0`, PF `0.6356926570779712`, MAR
  `-0.7825314922408811`, and expectancy R `-0.24698221123551944`.
- No run reached WFA OOS monkey, Monte Carlo, simulated incubation, or frozen
  validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_realized_semivariance_asymmetry.py
  tests/test_strategy.py tests/test_preflight.py tests/test_campaign_stages.py -q`
  PASS with `53` tests; targeted preflight for five originals PASS; targeted
  preflight for five rescues PASS.


## ES Amihud Illiquidity Price Impact - 2026-06-17

Decision: FAIL.

- Added `amihud_illiquidity_state`, a completed-bar entry module that uses
  lagged daily Amihud-style price impact, computed as absolute RTH return
  divided by ES notional volume, with every tradable feature shifted one
  completed RTH session before use.
- Added `tools/build_es_amihud_illiquidity_features.py`, which builds
  `data/external/es_amihud_illiquidity_features_20110103_20260609.csv` from
  the local Sierra ES RTH aggregate cache. The build produced `3817` rows and
  `3740` rank-complete rows. No paid data was downloaded.
- Created `campaigns/es_amihud_illiquidity_price_impact/campaign.yaml` and
  exactly five variants, each with `amihud_illiquidity_state`,
  `percent_from_entry`, `fixed_r`, README, config, and strategy-module shims.
- Pre-backtest density audit passed:
  `research_artifacts/es_amihud_illiquidity_price_impact_density_audit_20260617.md`.
  Every declared threshold had expected signal density above 50 trades/year.
- Originals: all five failed `limited_core_grid_test`. Best original was
  `high_1d_illiq_stress_short_1030/run1` with profitable-combo rate
  `0.14814814814814814`, zero benchmark-passing combinations, top net
  `2115.0`, top PF `1.1749741468459152`, and `87` top-combo trades.
- Rescues: all five one-time parameter-space rescues completed and all failed
  `limited_core_grid_test`. Best rescue was
  `high_1d_illiq_premium_long_1000/rescue1` with profitable-combo rate
  `0.1111111111111111`, zero benchmark-passing combinations, top net
  `1663.75`, top PF `1.1705972827480133`, and `71` top-combo trades.
- No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated
  incubation, or frozen validation. No candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_amihud_illiquidity_state.py
  tests/test_strategy.py tests/test_preflight.py tests/test_campaign_stages.py
  tests/test_core_grid.py tests/test_monkey.py -q` PASS with `65` tests;
  targeted preflight for five originals and five rescues PASS.


## ES realized volatility-of-volatility state campaign - 2026-06-17

- Added local feature builder `tools/build_es_realized_vol_of_vol_features.py`; output `data/external/es_realized_vol_of_vol_features_20110103_20260609.csv` contains 3,817 sessions and 3,740 valid rolling-rank rows. All tradable fields are shifted one completed RTH session.
- Added entry module `realized_vol_of_vol_state` with RTH-only requirement and focused tests in `tests/test_realized_vol_of_vol_state.py`.
- Preflight: `python3 -m research.preflight --skip-tests --config <all 10 es_realized_vol_of_vol_state configs>` PASS.
- Staged tests: all five originals failed `limited_core_grid_test`; all five parameter-space-only rescues also failed `limited_core_grid_test`.
- Aggregate report: `backtest-campaigns/es_realized_vol_of_vol_state/campaign_test_summary.json`.
- Final decision: FAIL. No candidate strategy report was created.


## ES round-number barrier reaction campaign - 2026-06-17

- Added entry module `round_number_barrier` with RTH-only requirement and focused tests in `tests/test_round_number_barrier.py`.
- Source campaign: `campaigns/es_round_number_barrier_reaction/campaign.yaml`.
- Density gate: `research_artifacts/es_round_number_barrier_reaction_density_audit_20260617.md`; final declared original/rescue grids have minimum pre-test density of 61.3 signals/year.
- Preflight: `python3 -m research.preflight --skip-tests --config <all 10 es_round_number_barrier_reaction configs>` PASS.
- Staged tests: all five originals failed `limited_core_grid_test`; all five parameter-space-only rescues also failed `limited_core_grid_test`.
- Aggregate report: `backtest-campaigns/es_round_number_barrier_reaction/campaign_test_summary.json`.
- Final decision: FAIL. No candidate strategy report was created.


## ES daily short-term return reversal campaign - 2026-06-17

- Added entry module `daily_short_term_reversal` with focused tests in
  `tests/test_daily_short_term_reversal.py`.
- Source campaign: `campaigns/es_daily_short_term_reversal/campaign.yaml`.
- Edge thesis: fade recent completed RTH close-to-close ES returns as a
  liquidity-provision short-term reversal effect. This is distinct from active
  daily time-series momentum because it is contrarian, and distinct from
  prior-session IBS because it uses close-to-close return magnitude and sign
  rather than close location inside the prior RTH range.
- Density gate:
  `research_artifacts/es_daily_short_term_reversal_density_audit_20260617.md`;
  declared original grids had expected signal density near or above the 50
  trades/year methodology floor.
- Preflight: full active-config preflight passed after scaffold with
  `python3 -m research.preflight --skip-tests` (`803` configs checked). After
  rescue scaffolding, targeted preflight across all ten new configs passed with
  `python3 -m research.preflight --skip-tests --config <all 10 es_daily_short_term_reversal configs>`
  (`10` configs checked). Focused tests passed with `python3 -m pytest
  tests/test_daily_short_term_reversal.py tests/test_strategy_modules.py
  tests/test_preflight.py -q` (`145` tests), and final focused regression passed
  with `191` tests.
- Staged tests: all five originals failed `limited_core_grid_test` with zero
  profitable grid combinations.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving the same close-to-close reversal mechanic, direction mode,
  lookback, signal time, modules, timeframe, data window, costs, fill rules,
  session rules, prop rules, and validation gates. All five rescues also failed
  `limited_core_grid_test` with zero profitable grid combinations.
- Aggregate report:
  `backtest-campaigns/es_daily_short_term_reversal/campaign_test_summary.json`.
- Final decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte
  Carlo, simulated incubation, frozen validation, or candidate reporting. No
  candidate strategy report was created.


## ES SPX 0DTE Expiration Pressure - 2026-06-17

- Created `campaigns/es_spx_0dte_expiration_pressure/campaign.yaml` and exactly five variants using `spx_0dte_expiration_pressure`, `percent_from_entry`, and `fixed_r`.
- Built `data/external/spx_0dte_calendar_sessions_20110103_20260609.csv` from the local Sierra ES RTH cache and public Cboe SPX Weeklys listing rules. No paid data was downloaded.
- Pre-test density audit: `research_artifacts/es_spx_0dte_expiration_pressure_density_audit_20260617.md`; all declared original and rescue threshold spaces cleared the 50 expected signals/year screen before performance testing.
- Verification: `python3 -m pytest tests/test_spx_0dte_expiration_pressure.py tests/test_strategy_modules.py tests/test_preflight.py -q` PASS (`146` tests). Targeted preflight for five originals and five rescues PASS.
- Originals: all five failed before WFA. Best original by top limited-core net was `full_week_down_move_fade_long_1000/run1` with top net `12640.0`, profitable-combo rate `0.25925925925925924`, and `0` benchmark-passing combinations.
- Rescues: all five failed variants received one parameter-space-only rescue. Four rescues failed `limited_core_grid_test`. `full_week_late_move_continuation_1430/rescue1` reached WFA after core/monkey but failed `walk_forward_analysis` by early exit; stitched OOS net `-4122.5`, PF `0.5265575653172553`, MAR `-1.5399289192985244`, trades/year `64.18426923443607`.
- Aggregate report: `backtest-campaigns/es_spx_0dte_expiration_pressure/campaign_test_summary.json`.
- Final decision: FAIL. No run reached WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No candidate strategy report was created.


## ES Treasury Auction Pressure - 2026-06-17

- Added entry module `treasury_auction_pressure` with focused tests in `tests/test_treasury_auction_pressure.py`.
- Built free official FiscalData auction calendar with `tools/build_es_treasury_auction_calendar.py`; output `data/external/es_treasury_coupon_auction_sessions_20110103_20260609.csv` has 1,324 all-coupon auction sessions and 1,036 note days. No paid data was downloaded.
- Source campaign: `campaigns/es_treasury_auction_pressure/campaign.yaml`, exactly five variants.
- Preflight: targeted originals and rescues PASS. Focused tests PASS.
- Staged tests: all five originals failed `limited_core_grid_test`; all five parameter-space-only rescues also failed `limited_core_grid_test`.
- Aggregate report: `backtest-campaigns/es_treasury_auction_pressure/campaign_test_summary.json`.
- Final decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No candidate strategy report was created.

## ES Cboe SKEW Tail Risk Intraday - 2026-06-17

- Created `campaigns/es_cboe_skew_tail_risk_intraday/campaign.yaml` and exactly five variants using the new `cboe_skew_tail_risk` entry module with `percent_from_entry` stops and `fixed_r` targets.
- Built `data/external/es_cboe_skew_tail_risk_features_20110103_20260609.csv` from the free official Cboe SKEW daily CSV and local ES Sierra RTH sessions. No paid data was downloaded. Every tradable feature uses the latest Cboe SKEW close strictly before the ES session date.
- Original runs: all five failed `limited_core_grid_test`; best original was `high_skew_short_1000/run1` with profitable-combo rate `0.07407407407407407`, zero benchmark-pass combinations, top net `$565.00`, PF `1.0800283286118981`, and `87` top-combo trades.
- Rescues: all five one-time parameter-space-only rescues completed and failed `limited_core_grid_test`; best rescue was `high_skew_short_1000/rescue1` with profitable-combo rate `0.14814814814814814`, zero benchmark-pass combinations, top net `$565.00`, PF `1.0800283286118981`, and `87` top-combo trades.
- No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.
- Verification: `python3 -m pytest tests/test_cboe_skew_tail_risk.py -q` PASS; targeted preflight for five originals and five rescues PASS.

## ES Cboe Implied Correlation Intraday - 2026-06-17

- Created `campaigns/es_cboe_implied_correlation_intraday/campaign.yaml` and exactly five variants using the new `cboe_implied_correlation` entry module with `percent_from_entry` stops and `fixed_r` targets.
- Built `data/external/es_cboe_implied_correlation_features_20110103_20260609.csv` from free official Cboe COR1M/COR3M daily CSVs and local ES Sierra RTH sessions. No paid data was downloaded. Every tradable feature uses the latest Cboe implied-correlation close strictly before the ES session date.
- Original runs: all five failed `limited_core_grid_test`; best original was `high_short_term_correlation_short_1330/run1` with profitable-combo rate `0.2222222222222222`, zero benchmark-pass combinations, top net `$1980.00`, PF `1.1112984822934233`, and `144` top-combo trades.
- Rescues: all five one-time parameter-space-only rescues completed and failed `limited_core_grid_test`; best rescue was `high_short_term_correlation_short_1330/rescue1` with profitable-combo rate `0.9259259259259259`, zero benchmark-pass combinations, top net `$2656.25`, PF `1.1317747736574475`, and `150` top-combo trades.
- No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## ES Cboe VIX Term Structure Intraday - 2026-06-17

- Created `campaigns/es_cboe_vix_term_structure_intraday/campaign.yaml` and exactly five variants using the new `cboe_vix_term_structure` entry module with `percent_from_entry` stops and `fixed_r` targets.
- Built `data/external/es_cboe_vix_term_structure_features_20110103_20260609.csv` from free official Cboe VIX9D, VIX, VIX3M, and VIX6M daily CSVs and local ES Sierra RTH sessions. No paid data was downloaded. Every tradable feature uses the latest Cboe volatility-index close strictly before the ES session date.
- Original runs: all five failed `limited_core_grid_test`; best original was `contango_long_1030/run1` with profitable-combo rate `0.07407407407407407`, zero benchmark-pass combinations, top net `$180.00`, PF `1.012591815320042`, and `119` top-combo trades.
- Rescues: all five one-time parameter-space-only rescues completed and failed `limited_core_grid_test`. `contango_long_1030/rescue1` improved to profitable-combo rate `0.8888888888888888`, but still had zero benchmark-pass combinations and top PF `1.1840448554003542`, below the 1.2 gate. Best rescue by top net was `curve_flattening_short_1200/rescue1` with profitable-combo rate `0.7037037037037037`, zero benchmark-pass combinations, top net `$2997.50`, PF `1.1856899488926746`, and `123` top-combo trades.
- No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## ES Cboe VIX Level State Intraday - 2026-06-17

- Created `campaigns/es_cboe_vix_level_state_intraday/campaign.yaml` and exactly five variants using the new `cboe_vix_level_state` entry module with `percent_from_entry` stops and `fixed_r` targets.
- Built `data/external/es_cboe_vix_level_features_20110103_20260609.csv` from the existing local free Cboe VIX daily-history cache and local ES Sierra RTH sessions. No paid data was downloaded. Every tradable feature uses the latest Cboe VIX close strictly before the ES session date.
- Original runs: all five failed `limited_core_grid_test`; best original was `vix_spike_riskoff_short_1130/run1` with profitable-combo rate `0.14814814814814814`, zero benchmark-pass combinations, top net `$1212.50`, PF `1.0590383444917832`, and `165` top-combo trades.
- Rescues: all five one-time parameter-space-only rescues completed and failed `limited_core_grid_test`; best rescue was `vix_spike_riskoff_short_1130/rescue1` with profitable-combo rate `0.5555555555555556`, zero benchmark-pass combinations, top net `$2618.75`, PF `1.1243766326288294`, and `165` top-combo trades.
- No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## ES Credit Spread State Intraday Data Gate - 2026-06-17

- Added and tested a potential `credit_spread_state` entry module plus
  `tools/build_es_credit_spread_features.py`.
- Downloaded only free public FRED graph CSVs for ICE BofA HY OAS
  `BAMLH0A0HYM2` and IG OAS `BAMLC0A0CM`; no paid market data was downloaded.
- Built `data/external/es_credit_spread_features_20110103_20260609.csv` using
  local ES Sierra RTH sessions and a conservative two-business-day availability
  lag for credit-spread observations.
- Data gate failed before campaign scaffolding: current free FRED/ICE OAS
  caches start on `2023-06-19`; valid ranked ES sessions span only
  `2023-09-13` to `2026-06-09` (`680` rows).
- Because the staged methodology requires at least 10 WFA windows under the
  48-month train / 12-month test / 12-month step setup, this edge cannot pass
  with the currently available no-cost history. No five-variant campaign was
  launched, and no candidate strategy report was created.
- Verification: `python3 -m pytest tests/test_credit_spread_state.py
  tests/test_strategy_modules.py tests/test_preflight.py -q` PASS (`145`
  tests).
## ES Intraday Periodicity Persistence - 2026-06-17

- Added `intraday_periodicity_persistence`, a local Sierra-only campaign testing
  prior sessions' same-clock half-hour return persistence on ES.
- Built `data/external/es_intraday_periodicity_features_20110103_20260609.csv`
  from the local ES RTH Sierra 1-minute cache. Feature construction uses
  `shift(1)` within each slot so current-session slot outcomes are excluded.
- Pre-test density audit:
  `research_artifacts/es_intraday_periodicity_persistence_density_audit_20260617.md`.
  The frozen original grid was expected to clear the 50 trades/year density rule.
- Authored exactly five variants under
  `campaigns/es_intraday_periodicity_persistence/variants/`, each with entry,
  stop, target module shims, `config.yaml`, and `README.md`.
- Parameter count: 2 entry tunables, 1 stop tunable, 1 target tunable, 81
  combinations per variant.
- Verification before staged runs:
  `python3 -m pytest tests/test_intraday_periodicity_persistence.py tests/test_strategy_modules.py tests/test_preflight.py -q`
  passed with 144 tests; targeted preflight over the five original configs
  passed. Broad active-tree preflight was stopped because it was loading every
  unrelated active campaign config and consuming several minutes/memory.
- Original outcome: all five variants failed `limited_core_grid_test` with zero
  profitable combinations and zero benchmark-passing combinations.
- Rescue outcome: each failed variant received exactly one parameter-space-only
  rescue. All five rescues also failed `limited_core_grid_test` with zero
  profitable combinations and zero benchmark-passing combinations.
- Aggregate artifacts:
  `backtest-campaigns/es_intraday_periodicity_persistence/campaign_test_summary.json`,
  `backtest-campaigns/es_intraday_periodicity_persistence/campaign_results.csv`,
  `backtest-campaigns/es_intraday_periodicity_persistence/wfa_table.csv`, and
  `backtest-campaigns/es_intraday_periodicity_persistence/monte_carlo_summary.json`.
- Decision: FAIL. No candidate strategy report was created.

## Staged Runner Screening Gate Fix - 2026-06-17

- Added `research_artifacts/core_grid_monkey_vs_archived_audit_20260617.md`
  after comparing current core-grid/monkey gates with archived staged-run
  artifacts.
- Fixed run traceability: new staged runs write the effective canonical config
  to run-level `config.yaml` and retain the original input config as
  `source_config.yaml`.
- Fixed limited core-grid benchmark pass counting: the stage now uses a
  screening benchmark that keeps trade-density, drawdown/concentration, and
  rule-compliance checks, but leaves full PF/MAR/expectancy gates for WFA and
  later stages.
- Full-span absolute trade-count thresholds are scaled to the actual limited
  screen period and recorded in `benchmark_thresholds` /
  `benchmark_threshold_adjustments`.
- Monkey pass/fail criteria now match the stated methodology: stressed actual
  trade path must be at least 80% profitable, median-positive, survive a
  one-tick-worse slippage path, and show no Apex/flatten violations. The random
  monkey comparison remains diagnostic output, not the pass/fail gate.
- Verification:
  `python3 -m pytest tests/test_campaign_stages.py -q` PASS (`34` tests);
  `python3 -m pytest tests/test_campaign_stages.py tests/test_backtest_engine.py tests/test_preflight.py tests/test_wfa.py -q`
  PASS (`96` tests);
  `python3 -m pytest tests/test_monkey.py tests/test_core_grid.py -q` PASS
  (`12` tests);
  `python3 -m py_compile src/propstack/research/campaign_stages.py src/propstack/research/core_grid.py src/propstack/research/monkey.py`
  PASS.
- Methodology-fix reruns are documented in
  `research_artifacts/methodology_fix_reruns_20260617.md`.
  `es_cboe_implied_correlation_intraday/high_short_term_correlation_short_1330`,
  `es_cboe_vix_term_structure_intraday/contango_long_1030`, and
  `es_cboe_vix_term_structure_intraday/curve_flattening_short_1200` all passed
  the corrected limited core-grid gate, then failed `limited_monkey_test`
  because stressed actual trade paths were below the 80% profitable threshold
  and the one-tick-worse slippage path was unprofitable. Decision: FAIL for all
  three retests.
- `es_market_plumbing_liquidity_capacity/dual_pressure_priority_long_1130`
  was also rerun under the corrected gate. It failed corrected
  `limited_core_grid_test`: profitable-combo rate was
  `0.8888888888888888`, but benchmark-pass combinations remained `0` because
  the screening benchmark rejected the top rows for max consecutive losses.
  Decision: FAIL.
- `es_vwap_pullback_continuation/midday_trend_reclaim_two_sided` was rerun
  under the corrected gate. It passed corrected limited core grid
  (`0.8148148148148148` profitable-combo rate, `9` screening benchmark-pass
  combinations) but failed `limited_monkey_test` because the one-tick-worse
  path was unprofitable (`-203.75`) despite the broader stress distribution
  being median-positive. Decision: FAIL.
- `es_oil_price_shock_spillover/wti_up_risk_off_short_1030` was rerun under
  the corrected gate. It passed corrected limited core grid
  (`0.7777777777777778` profitable-combo rate, `3` screening benchmark-pass
  combinations) and corrected `limited_monkey_test`, then failed
  `walk_forward_analysis` by early exit because the selected first-window
  in-sample PF was `0.93 < 1.00`. Decision: FAIL.
- `es_spx_0dte_expiration_pressure/full_week_late_move_continuation_1430` was
  rerun under the corrected gate after the false-negative scan found its
  original limited core-grid profitable rate was `0.7037037037037037` but old
  full-stage benchmark pass count was `0`. The corrected rerun passed limited
  core grid (`15` screening benchmark-pass combinations) and corrected
  `limited_monkey_test` (`0.8133333333333334` stress profitable rate,
  one-tick-worse net `1647.5`), then failed `walk_forward_analysis` by early
  exit at window 4 because the selected in-sample PF was `0.91 < 1.00`.
  Stitched OOS PF was `0.5178719866999169`, MAR was `-1.368206562790248`, and
  expectancy R was negative. Decision: FAIL.

## ES FINRA Margin Leverage State - 2026-06-17

- Launched one non-duplicate ES campaign using official FINRA monthly margin
  statistics with a 35-calendar-day availability lag and local Sierra ES RTH
  1-minute bars.
- Built features with `tools/build_es_finra_margin_features.py` and wrote
  `data/external/es_finra_margin_leverage_features_20110103_20260609.csv`.
  Signals use only lagged monthly FINRA observations plus a completed intraday
  bar; entries remain next-bar-open through the engine.
- Added entry module `finra_margin_leverage` and targeted tests in
  `tests/test_finra_margin_leverage.py`. Verification:
  `python3 -m pytest tests/test_finra_margin_leverage.py tests/test_strategy_modules.py tests/test_preflight.py -q`
  PASS (`144` tests); targeted preflight over the five original configs PASS.
- Authored exactly five variants under
  `campaigns/es_finra_margin_leverage/variants/`, each with entry, stop,
  target module shims, `config.yaml`, and `README.md`.
- Original outcome: all five variants failed `limited_core_grid_test`. The
  earliest limited-core slice ran from `2011-01-03` into `2012`, before the
  120-month FINRA rank features were non-null, producing zero trades.
- Rescue outcome: each failed variant received exactly one rescue. The only
  changed fixed value was `data_subset.start_date`, moved to the first session
  where that variant's frozen FINRA rank feature was non-null. Entry module,
  setup mode, direction, entry time, stop/target modules, parameter grid,
  costs, fills, session rules, prop rules, and validation gates were unchanged.
- All five rescues failed `limited_core_grid_test`. No rescue reached monkey,
  WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or
  candidate reporting.
- Aggregate artifacts:
  `backtest-campaigns/es_finra_margin_leverage/campaign_test_summary.json`,
  `backtest-campaigns/es_finra_margin_leverage/campaign_results.csv`,
  `backtest-campaigns/es_finra_margin_leverage/wfa_table.csv`,
  `backtest-campaigns/es_finra_margin_leverage/monte_carlo_summary.json`, and
  `research_artifacts/es_finra_margin_leverage_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No candidate strategy report was created.


## ES AQR BAB Factor State Campaign - 2026-06-17

- Added free-public-data campaign `es_aqr_bab_factor_state` using AQR Betting Against Beta daily U.S. factor returns with a conservative 45-calendar-day publication lag. No paid data was downloaded.
- Source data: local Sierra ES RTH cache plus `data/external/aqr_bab_equity_factors_daily.xlsx`; feature output `data/external/es_aqr_bab_features_20110103_20260609.csv` has 3,817 ES sessions and uses AQR observations through 2026-03-31 for the latest 2026-06-09 ES session.
- Preflight: originals and rescues passed. Focused tests: `python3 -m pytest tests/test_aqr_bab_factor_state.py tests/test_campaign_stages.py tests/test_monkey.py tests/test_core_grid.py -q` PASS with 50 tests.
- Staged tests: all five originals failed `limited_core_grid_test`; all five failed variants received exactly one parameter-space-only rescue. Four rescues failed `limited_core_grid_test`. `low_bab_z63_rebound_long_1100/rescue1` passed core and limited monkey, then failed `walk_forward_analysis` by early exit on window 2 because selected IS PF was `0.99 < 1.00`; stitched OOS PF was `0.8619637937819756`, MAR `-0.3811286271107167`, and trades/year `71.7246404539663`.
- Final decision: FAIL. No run reached WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.


## Staged Selection Filter Enforcement - 2026-06-17

- Fixed WFA selection so configured in-sample filters are hard eligibility rules. If `trades/year > 50` removes every train-grid row, WFA now early-exits with `no_in_sample_rows_after_selection_filter` instead of selecting a sparse fallback row.
- Fixed simulated incubation and acceptance train-selection so they fail closed when no parameter row satisfies configured selection filters. This prevents the OOS stages from running base/default parameters after an empty eligible set.
- Verification: `python3 -m pytest tests/test_campaign_stages.py tests/test_wfa.py tests/test_monte_carlo.py tests/test_monkey.py tests/test_backtest_engine.py tests/test_preflight.py -q` passed 127 tests.
- Verification: `python3 -m py_compile src/propstack/research/wfa.py src/propstack/research/campaign_stages.py src/propstack/prop/rules.py src/propstack/prop/simulator.py` passed.


## ES/NQ Relative-Value Reversion - 2026-06-17

- Added active non-duplicate campaign `es_nq_relative_value_reversion` using the existing local ES/NQ aligned RTH 1-minute completed return-spread cache. No paid data was downloaded.
- Edge distinction: this campaign fades ES-specific divergence versus NQ. It rejects plain NQ-following signals and is distinct from the active failed `es_nq_cross_index_lead_lag` continuation campaign.
- Authored exactly five variants with one entry tunable, one stop tunable, one target tunable, and 27 combinations per variant.
- Signal-density audit: all 15 entry-threshold cells cleared the 50 signals/year screen before performance testing; see `research_artifacts/es_nq_relative_value_reversion_density_audit_20260617.md`.
- Verification before staged runs: `python3 -m pytest tests/test_es_nq_relative_value_reversion.py tests/test_es_nq_lead_lag.py tests/test_strategy_modules.py tests/test_preflight.py -q` passed 150 tests; targeted preflight for the five originals and five rescues passed.
- Originals: all five failed `limited_core_grid_test`. Best original was `thirty_min_divergence_fade_1130/run1` with profitable-combo rate `0.18518518518518517`, top net `447.50`, top PF `1.069676511954993`, and 93 top-combo trades.
- Rescues: all five failed variants received exactly one parameter-space/fixed-parameter rescue. All five rescues failed `limited_core_grid_test`. Best rescue was `thirty_min_divergence_fade_1030/rescue1` with profitable-combo rate `0.14814814814814814`, top net `601.25`, top PF `1.0508127196404086`, and 131 top-combo trades.
- Aggregate artifacts: `backtest-campaigns/es_nq_relative_value_reversion/campaign_test_summary.json`, `campaign_results.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Final decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.
## ES NAAIM Active-Manager Exposure Sentiment - 2026-06-17

- Campaign: `es_naaim_exposure_sentiment`
- Source data: local Sierra ES RTH 1-minute cache plus free public NAAIM Exposure
  Index workbook cached at `data/external/naaim_exposure_index_20260610.xlsx`.
- Feature construction: `tools/build_es_naaim_exposure_features.py`; signal
  sessions use the first ES RTH session at least two business days after the
  NAAIM observation date.
- Density audit: `research_artifacts/es_naaim_exposure_sentiment_density_audit_20260617.md`;
  all five proposed setup modes had 805 eligible weekly signals, about 52.21/year.
- Original runs: all five failed `limited_core_grid_test` with 0.0 profitable
  combo rate.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue changing only stop/target grids. All five rescues also failed
  `limited_core_grid_test` with 0.0 profitable combo rate.
- Aggregate artifacts: `backtest-campaigns/es_naaim_exposure_sentiment/campaign_test_summary.json`,
  `backtest-campaigns/es_naaim_exposure_sentiment/campaign_results.csv`,
  `backtest-campaigns/es_naaim_exposure_sentiment/wfa_table.csv`, and
  `backtest-campaigns/es_naaim_exposure_sentiment/monte_carlo_summary.json`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation,
  frozen validation, or candidate reporting.


## ES Leveraged ETF Rebalance Pressure - 2026-06-17

- Added active non-duplicate campaign `es_leveraged_etf_rebalance_pressure`
  using the local Sierra ES RTH 1-minute cache. No paid data was downloaded.
- Edge distinction: this campaign tests LETF same-day close rebalance pressure
  after large completed current-day moves from the prior RTH close. It is not a
  rerun of the active failed first-half-hour-to-last-half-hour market intraday
  momentum campaign or same-clock periodicity campaign.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, and `README.md`.
- Added entry module `leveraged_etf_rebalance_pressure`, registered it in the
  entry registry, and added required-feature warnings for `prev_rth_close`.
- Density audit:
  `research_artifacts/es_leveraged_etf_rebalance_pressure_density_audit_20260617.md`;
  all declared 20/30/40 bp one-sided and two-sided late-day thresholds cleared
  50 prospective signals/year before performance testing.
- Verification before staged runs:
  `python3 -m pytest tests/test_leveraged_etf_rebalance_pressure.py tests/test_strategy_modules.py tests/test_preflight.py -q`
  passed 145 tests; targeted preflight for the five originals and five rescues
  passed.
- Originals: all five failed `limited_core_grid_test` with 0.0 profitable-combo
  rate and zero benchmark-passing combinations.
- Rescues: all five failed variants received exactly one
  parameter-space/fixed-parameter rescue. The rescue preserved edge thesis,
  entry module, setup mode, signal time, direction rule, data, costs, fills,
  sessions, prop rules, and validation gates. All five rescues also failed
  `limited_core_grid_test` with 0.0 profitable-combo rate.
- Best rescue by top-row net was `up_day_rebalance_long_1500/rescue1`: top net
  `-1522.50`, top PF `0.8378594249201278`, 142 top-combo trades, and
  92.78322390692647 trades/year.
- Aggregate artifacts:
  `backtest-campaigns/es_leveraged_etf_rebalance_pressure/campaign_test_summary.json`,
  `backtest-campaigns/es_leveraged_etf_rebalance_pressure/campaign_results.csv`,
  `backtest-campaigns/es_leveraged_etf_rebalance_pressure/wfa_table.csv`,
  `backtest-campaigns/es_leveraged_etf_rebalance_pressure/monte_carlo_summary.json`,
  and
  `research_artifacts/es_leveraged_etf_rebalance_pressure_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation,
  frozen validation, or candidate reporting. No `candidate_strategy_report.md`
  was created.


## ES Gao Last-Half-Hour Orderflow Confirmation - 2026-06-17

- Added active price-action plus aggregate-orderflow campaign
  `es_gao_last_half_hour_orderflow_confirmation` using the existing tested
  `gao_last_half_hour_orderflow` module and only the local Sierra ES RTH
  1-minute orderflow cache. No paid data was downloaded.
- Edge distinction: this campaign tests Gao-style first-window price-action
  prediction of last-half-hour returns only when completed aggregate orderflow
  confirms the first-window direction. It is not the failed price-only
  `es_late_day_intraday_momentum` campaign and not standalone signed-flow
  persistence.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `first30_signed_flow_two_sided_1530`,
  `first30_large20_flow_two_sided_1530`,
  `first60_signed_flow_two_sided_1530`,
  `first60_large20_flow_two_sided_1530`, and
  `first30_broad_large_alignment_1530`.
- Density audit:
  `research_artifacts/es_gao_last_half_hour_orderflow_confirmation_density_audit_20260617.md`;
  every original declared entry corner exceeded 90 signals/year before
  stop/target filtering. Rescue density also cleared the 50/year gate.
- Verification before staged runs:
  `PYTHONPATH=src python3 -m pytest tests/test_strategy_modules.py -q -k gao_last_half_hour_orderflow`
  passed 3 tests; targeted preflight for the five originals and five rescues
  passed.
- Originals: all five failed `limited_core_grid_test` with 0.0 profitable-combo
  rate. Least-bad original was
  `first30_large20_flow_two_sided_1530/run1`, top net `-5350.00`, PF
  `0.5451647183846972`, and 133.24081683091848 trades/year.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving edge thesis, entry module, stop module, target module,
  timeframe, signal time, first-window length, flow mode, data, costs, fills,
  sessions, prop rules, and validation gates. All five rescues failed
  `limited_core_grid_test`; least-bad rescue was
  `first30_broad_large_alignment_1530/rescue1`, top net `-2055.00`, PF
  `0.7144841959013546`, and 73.45024501632395 trades/year.
- Aggregate artifacts:
  `backtest-campaigns/es_gao_last_half_hour_orderflow_confirmation/campaign_test_summary.json`,
  `backtest-campaigns/es_gao_last_half_hour_orderflow_confirmation/campaign_results.csv`,
  `backtest-campaigns/es_gao_last_half_hour_orderflow_confirmation/wfa_table.csv`,
  `backtest-campaigns/es_gao_last_half_hour_orderflow_confirmation/monte_carlo_summary.json`,
  and
  `research_artifacts/es_gao_last_half_hour_orderflow_confirmation_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation,
  frozen validation, or candidate reporting. No `candidate_strategy_report.md`
  was created.


## ES Trend-Aligned Orderflow Continuation - 2026-06-17

- Added active price-action plus aggregate-orderflow campaign
  `es_trend_aligned_orderflow_continuation` using only the local Sierra ES RTH
  1-minute orderflow cache. No paid data was downloaded.
- Edge distinction: this campaign tests completed two-horizon HH/HL or LH/LL
  price-action trend structure confirmed by same-bar aggregate orderflow. It is
  not standalone signed-flow persistence, opening-range breakout, VWAP pullback,
  prior-level dislocation, range compression, or absorption/fade logic.
- Added entry module
  `src/propstack/strategy_modules/entry/trend_aligned_orderflow_continuation.py`
  plus registration and engine feature-column checks. Signals use completed
  5-minute bars only; engine entry remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `morning_15_30_large20_trend_flow_1030`,
  `late_morning_15_30_signed_trend_flow_1130`,
  `midday_15_30_large10_trend_flow_1230`,
  `afternoon_30_60_large20_trend_flow_1400`, and
  `late_day_30_60_large10_trend_flow_1430`.
- Density audit:
  `research_artifacts/es_trend_aligned_orderflow_continuation_density_audit_20260617.md`;
  every original declared entry corner exceeded roughly 52 signals/year before
  stop/target filtering. The rescue entry grid also cleared the 50/year density
  screen with fixed `min_trend_move_ticks = 0`.
- Verification before staged runs:
  `PYTHONPATH=src python3 -m pytest tests/test_trend_aligned_orderflow_continuation.py tests/test_opening_range_orderflow_breakout.py tests/test_strategy.py tests/test_data_pipeline.py tests/test_campaign_stages.py tests/test_preflight.py -q`
  passed 71 tests; targeted preflight for the five originals and five rescues
  passed.
- Limited core-grid data period used by the staged runner:
  `2011-02-22 09:30:00-05:00` through `2012-09-06 15:59:00-04:00`
  (`random_fraction` 10% shortlist window, avoiding latest 10% and COVID
  range per current runner defaults).
- Originals: all five failed `limited_core_grid_test` with 0.0 profitable-combo
  rate. Least-bad original was
  `late_day_30_60_large10_trend_flow_1430/run1`, top net `-220.00`, PF
  `0.9666919000757003`, 74 trades, and 48.87459580960513 trades/year; it still
  failed net-profit, trade-density, and preferred-count gates.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving edge thesis, entry module, stop module, target module,
  timeframe, signal time, trend horizons, flow mode, data, costs, fills,
  sessions, prop rules, and validation gates. All five rescues failed
  `limited_core_grid_test`; least-bad rescue was
  `morning_15_30_large20_trend_flow_1030/rescue1`, top net `-1626.25`, PF
  `0.5827453495830661`, and 65.15759441399504 trades/year.
- Aggregate artifacts:
  `backtest-campaigns/es_trend_aligned_orderflow_continuation/campaign_test_summary.json`,
  `backtest-campaigns/es_trend_aligned_orderflow_continuation/campaign_results.csv`,
  `backtest-campaigns/es_trend_aligned_orderflow_continuation/wfa_table.csv`,
  `backtest-campaigns/es_trend_aligned_orderflow_continuation/monte_carlo_summary.json`,
  and
  `research_artifacts/es_trend_aligned_orderflow_continuation_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation,
  frozen validation, or candidate reporting. No `candidate_strategy_report.md`
  was created.


## ES Chicago Fed CFNAI Activity Pullback - 2026-06-17

- Added active non-duplicate campaign `es_chicagofed_cfnai_activity_pullback`
  using local Sierra ES RTH 1-minute bars plus a local no-paid-data Chicago Fed
  CFNAI feature cache.
- Every variant YAML included a detailed pre-test mechanics review and
  `pre_test_decision: approve_for_testing` before staged testing.
- Density audit:
  `research_artifacts/es_chicagofed_cfnai_activity_pullback_density_audit_20260617.md`;
  all original and rescue parameter-space corners cleared 50 signals/year before
  PnL testing.
- Originals: all five variants failed `limited_core_grid_test`.
  `headline_activity_weak_pullback_long_1100/run1` had the best original
  profitable-combo rate at 0.4444. No original reached monkey.
- Rescues: all five failed variants received exactly one
  parameter-space-only rescue preserving the CFNAI availability rule, driver
  column, long direction, entry time, entry module, stop module, target module,
  data window, timeframe, costs, fill assumptions, and validation gates.
- All five rescues failed `limited_core_grid_test`. Best rescue by
  profitable-combo rate was `headline_activity_weak_pullback_long_1100/rescue1`
  at 0.6049, below the required 0.70. Best top-combo net was
  `production_income_weak_pullback_long_1100/rescue1` at 4712.5, but only
  0.5432 of combinations were profitable.
- Aggregate artifacts:
  `backtest-campaigns/es_chicagofed_cfnai_activity_pullback/campaign_test_summary.json`,
  `backtest-campaigns/es_chicagofed_cfnai_activity_pullback/campaign_results.csv`,
  `backtest-campaigns/es_chicagofed_cfnai_activity_pullback/wfa_table.csv`,
  `backtest-campaigns/es_chicagofed_cfnai_activity_pullback/trade_logs_manifest.csv`,
  `backtest-campaigns/es_chicagofed_cfnai_activity_pullback/equity_curves_manifest.csv`,
  and
  `backtest-campaigns/es_chicagofed_cfnai_activity_pullback/monte_carlo_summary.json`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation,
  frozen validation, or candidate reporting. No `candidate_strategy_report.md`
  was created.
- User priority update on 2026-06-17: next new campaigns should prioritize
  local ES/MES price action and aggregated-orderflow mechanics over slow
  macro-state filters unless explicitly redirected.


## ES Sector-Rotation Risk-Appetite Intraday - 2026-06-17

- Added active non-duplicate campaign `es_sector_rotation_risk_appetite`
  using local Sierra ES RTH 1-minute bars plus no-cost public Yahoo chart daily
  adjusted-close data for SPY and SPDR sector ETFs. No paid data was
  downloaded.
- Edge distinction: this campaign tests lagged cross-sector ETF rotation as an
  equity risk-appetite state. It is not ES/NQ lead-lag or relative value,
  broad-dollar/rates/volatility state, survey sentiment, BAB factor state, or
  ES own-return momentum.
- Feature construction: `tools/build_es_sector_rotation_features.py` wrote
  `data/external/es_sector_rotation_features_20110103_20260609.csv` with 3,817
  ES sessions and 3,817 valid rank rows. Every tradable sector feature uses the
  latest ETF close available on or before `session_date - 1` business day.
- Density audit:
  `research_artifacts/es_sector_rotation_risk_appetite_density_audit_20260617.md`;
  all five original threshold spaces cleared the 50 signals/year pre-PnL screen.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, and `README.md`.
- Verification before staged runs:
  `PYTHONPATH=src python3 -m pytest tests/test_sector_rotation_risk_appetite.py tests/test_strategy_modules.py tests/test_preflight.py -q`
  passed 143 tests; targeted preflight for the five originals and five rescues
  passed.
- Originals: all five failed `limited_core_grid_test`. Four variants had zero
  profitable combinations. Best original was `growth_lead_long_1030/run1` with
  1/27 profitable combinations, top net `25.0`, top PF `1.00154012012937`, and
  zero benchmark-passing combinations.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving edge thesis, entry module, setup mode, signal time,
  direction rule, data, costs, fills, sessions, prop rules, and validation
  gates. All five rescues also failed `limited_core_grid_test`.
- Best rescues were `growth_lead_long_1030/rescue1` with 16/27 profitable
  combinations, five benchmark-passing combinations, top net `4127.5`, top PF
  `1.3940334128878282`, and `financial_industrial_lead_long_1330/rescue1` with
  14/27 profitable combinations, three benchmark-passing combinations, top net
  `2372.5`, top PF `1.312891526541378`. Both failed the 70% profitable-combo
  stability gate.
- Aggregate artifacts:
  `backtest-campaigns/es_sector_rotation_risk_appetite/campaign_test_summary.json`,
  `backtest-campaigns/es_sector_rotation_risk_appetite/campaign_results.csv`,
  `backtest-campaigns/es_sector_rotation_risk_appetite/wfa_table.csv`,
  `backtest-campaigns/es_sector_rotation_risk_appetite/monte_carlo_summary.json`,
  and
  `research_artifacts/es_sector_rotation_risk_appetite_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo,
  simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.


## ES/MES Micro-Flow Divergence Data Refresh Retry - 2026-06-17

- User confirmed MES data was in; retried
  `es_mes_micro_flow_divergence_reversion` using local Sierra parquet only. No
  paid data was downloaded.
- Built MES active-contract RTH orderflow cache
  `data/cache/orderflow/mes_sierra_trade_orderflow_1m_20190506_20260616_full_rth_ny.parquet`:
  687,180 full-session RTH minute bars, 1,762 sessions, zero duplicate
  timestamps, zero invalid OHLC rows, zero missing session segments, minimum
  side-volume coverage 1.0; 74 sessions dropped by regular/full-session policy.
- Built merged ES/MES completed-bar feature cache
  `data/cache/orderflow/es_mes_flow_divergence_1m_20190506_20260609_full_rth_ny.csv`:
  685,230 aligned ES/MES minute bars, 1,757 sessions, first `2019-05-06
  09:30:00`, last `2026-06-09 15:59:00`, zero duplicate timestamps, zero
  invalid OHLC rows, zero zero-volume ES/MES rows.
- Created data-refresh run configs under
  `campaigns/es_mes_micro_flow_divergence_reversion/data_refresh_20260617/`.
  The refresh configs changed only data path/dataset/run metadata and benchmark
  window settings needed for the corrected methodology: WFA 48-month IS /
  12-month OOS / 12-month step, simulated incubation 48/12, acceptance 24/6.
  Entry mechanics, stop modules, target modules, parameter grids, costs,
  slippage, tick size, point value, sessions, and flatten rules were unchanged
  from the original and existing rescue configs.
- Verification: targeted preflight passed for all ten refresh configs.
  `PYTHONPATH=src python3 -m pytest tests/test_es_mes_flow_divergence.py -q`
  passed after adding parquet-input support to the ES/MES merge builder.
- The limited shortlist window resolved to `2021-07-13` through `2022-03-28`
  for all refresh runs under the benchmark random 10% contiguous-window rule.
- All five refreshed originals failed before WFA. Each failed original received
  exactly one rerun of its existing parameter-space rescue config.
- Terminal results: four original/rescue runs failed `limited_core_grid_test`;
  six reached `limited_monkey_test` and failed the 90% random net-profit
  beat-rate gate. The failing monkey net-profit beat rates were 0.83 to 0.86;
  one run also failed the max-drawdown beat-rate gate at 0.8766666666666667.
- Aggregate artifacts:
  `backtest-campaigns/es_mes_micro_flow_divergence_reversion/campaign_test_summary.json`,
  `backtest-campaigns/es_mes_micro_flow_divergence_reversion/campaign_results.csv`,
  `backtest-campaigns/es_mes_micro_flow_divergence_reversion/wfa_table.csv`,
  `backtest-campaigns/es_mes_micro_flow_divergence_reversion/monte_carlo_summary.json`,
  and
  `research_artifacts/es_mes_micro_flow_divergence_reversion_mes_data_refresh_20260617.md`.
- Decision: FAIL. No refreshed original or rescue run reached WFA, WFA OOS
  monkey, Monte Carlo, simulated incubation, frozen validation, or candidate
  reporting. No `candidate_strategy_report.md` was created.

## ES/MES Participation Crowding Reversion - 2026-06-17

- Edge thesis: unusually high MES notional-equivalent or trade-count
  participation during a completed ES move may proxy for smaller-contract
  crowding and temporary ES price pressure. This is distinct from the failed
  ES/MES micro-flow divergence campaign because it ignores MES signed imbalance
  leadership and uses only relative participation intensity plus completed ES
  return direction.
- Data: local Sierra ES/MES aligned RTH 1-minute cache
  `data/cache/orderflow/es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny.csv`,
  built from the refreshed ES/MES completed-bar cache; no paid data was
  downloaded.
- Density-only audit: `research_artifacts/es_mes_participation_crowding_density_audit_20260617.md`.
  The five variants had enough expected trade density in at least part of their
  declared grids before any PnL testing.
- Exactly five variants were created under
  `campaigns/es_mes_participation_crowding_reversion/variants/`, each with an
  entry wrapper, stop wrapper, target wrapper, config, and README. Each variant
  used two entry tunables, one stop tunable, and one target tunable for 81
  declared combinations.
- Verification before staged tests:
  `PYTHONPATH=src python3 -m pytest tests/test_es_mes_participation.py tests/test_es_mes_flow_divergence.py -q`
  passed, YAML parse passed for the campaign and five configs, and
  `PYTHONPATH=src python3 -m research.preflight --skip-tests --config <five configs>`
  passed.
- Original result: all five variants failed `limited_core_grid_test`.
- Rescue: each failed variant received exactly one parameter-space-only rescue
  under
  `campaigns/es_mes_participation_crowding_reversion/rescue_attempts/parameter_space_rescue_1/`.
  Rescue configs passed YAML validation, focused tests, and targeted preflight.
- Rescue result: three rescues failed `limited_core_grid_test`; two rescues
  passed limited core but failed `limited_monkey_test`. The best rescue was
  `morning_notional_down_reversal_long_1030/rescue1`, with profitable-combo
  rate `0.8395061728395061`, but monkey net-profit beat rate
  `0.8566666666666667` and max-drawdown beat rate `0.6833333333333333`, both
  below the `0.90` limited monkey benchmark. The midday rescue had profitable
  combo rate `0.8024691358024691` but failed monkey with net/drawdown beat
  rates `0.79` and `0.8666666666666667`.
- Final decision: FAIL. No run reached WFA, WFA OOS monkey, Monte Carlo,
  simulated incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.


## ES USD/JPY Safe-Haven Spillover - 2026-06-17

- Added active non-duplicate campaign `es_usdjpy_safe_haven_spillover` using the
  local Sierra ES RTH 1-minute cache plus free FRED DEXJPUS USD/JPY daily data.
  No paid data was downloaded.
- Edge distinction: this campaign tests JPY-specific safe-haven/carry-unwind
  state, not the active failed broad-dollar index risk-appetite campaign.
- Feature construction: `tools/build_es_usdjpy_safe_haven_features.py` wrote
  `data/external/es_usdjpy_safe_haven_features_20110103_20260609.csv` with
  3817 rows and 3760 valid rank rows. Every tradable feature uses the latest
  FRED DEXJPUS observation available no later than one business day before the
  ES session.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, and `README.md`.
- Verification before staged runs:
  `PYTHONPATH=src python3 -m pytest tests/test_usdjpy_safe_haven.py tests/test_dollar_risk_appetite.py tests/test_campaign_stages.py -q`
  passed 45 tests; targeted preflight for the five originals and five rescues
  passed.
- Originals: all five failed `limited_core_grid_test`. Best original was
  `weak_yen_long_1200/run1`, top net `1207.50`, top PF `1.215625`, but only
  0.25925925925925924 profitable-combo rate and zero benchmark-passing combos.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving edge thesis, entry module, setup mode, signal time,
  direction rule, data, costs, fills, sessions, prop rules, and validation
  gates. Four rescues failed `limited_core_grid_test`.
- `weak_yen_long_1200/rescue1` passed limited core with 1.0 profitable-combo
  rate and top PF `1.3466307277628031`, but failed `limited_monkey_test` because
  core-vs-monkey net-profit beat rate was 0.8333333333333334, below the 0.9
  gate.
- Aggregate artifacts:
  `backtest-campaigns/es_usdjpy_safe_haven_spillover/campaign_test_summary.json`,
  `backtest-campaigns/es_usdjpy_safe_haven_spillover/campaign_results.csv`,
  `backtest-campaigns/es_usdjpy_safe_haven_spillover/wfa_table.csv`,
  `backtest-campaigns/es_usdjpy_safe_haven_spillover/monte_carlo_summary.json`,
  and
  `research_artifacts/es_usdjpy_safe_haven_spillover_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached WFA, WFA OOS monkey, Monte Carlo, simulated
  incubation, frozen validation, or candidate reporting. No
  `candidate_strategy_report.md` was created.


## ES Cboe VXN/VIX Dispersion Intraday - 2026-06-17

- Added active non-duplicate campaign `es_cboe_vxn_vix_dispersion_intraday`
  using the local Sierra ES RTH 1-minute cache plus free official Cboe VIX and
  VXN daily histories. No paid data was downloaded.
- Edge distinction: this campaign tests relative Nasdaq-versus-S&P option-implied
  volatility dispersion through VXN/VIX and VXN-minus-VIX states. It is not a
  rerun of standalone VIX level/change, VIX term structure, VVIX, SKEW, implied
  SPX component correlation, variance risk premium, ES/NQ price lead-lag, or
  realized-volatility state.
- Feature construction:
  `tools/build_es_cboe_vxn_vix_dispersion_features.py` wrote
  `data/external/es_cboe_vxn_vix_dispersion_features_20110103_20260609.csv`
  with 3817 rows and 3817 valid rank rows. Every tradable feature uses the
  latest Cboe VIX and VXN closes strictly before the ES session date.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, and `README.md`.
- Density audit:
  `research_artifacts/es_cboe_vxn_vix_dispersion_density_audit_20260617.md`;
  all original and rescue threshold grids cleared the rough 50 signals/year
  density screen before fills.
- Verification before staged runs:
  `PYTHONPATH=src python3 -m pytest tests/test_cboe_vxn_vix_dispersion.py tests/test_cboe_vix_level_state.py tests/test_campaign_stages.py -q`
  passed 48 tests; targeted preflight for the five originals and five rescues
  passed.
- Originals: all five failed `limited_core_grid_test`. Best original was
  `falling_vxn_vix_ratio_long_1200/run1`, top net `1320.00`, top PF
  `1.0866425992779782`, 136 trades, 88.69290276343247 trades/year, but only
  0.1111111111111111 profitable-combo rate and one benchmark-passing combo.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving edge thesis, entry module, setup mode, signal time,
  direction rule, data, costs, fills, sessions, prop rules, and validation
  gates. All five rescues also failed `limited_core_grid_test`.
- Best rescue was `falling_vxn_vix_ratio_long_1200/rescue1`, top net `2012.50`,
  top PF `1.2277227722772277`, 85 trades, 55.63172506305864 trades/year, but
  only 0.25925925925925924 profitable-combo rate and six benchmark-passing
  combinations, below the 70% limited-core stability gate.
- Aggregate artifacts:
  `backtest-campaigns/es_cboe_vxn_vix_dispersion_intraday/campaign_test_summary.json`,
  `backtest-campaigns/es_cboe_vxn_vix_dispersion_intraday/campaign_results.csv`,
  `backtest-campaigns/es_cboe_vxn_vix_dispersion_intraday/wfa_table.csv`,
  `backtest-campaigns/es_cboe_vxn_vix_dispersion_intraday/monte_carlo_summary.json`,
  and
  `research_artifacts/es_cboe_vxn_vix_dispersion_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation,
  frozen validation, or candidate reporting. No `candidate_strategy_report.md`
  was created.


## ES Realized Sector Dispersion State - 2026-06-17

- Added active non-duplicate campaign `es_sector_dispersion_state` using the
  local Sierra ES RTH 1-minute cache plus the existing no-cost Yahoo sector ETF
  adjusted-close cache. No paid data was downloaded.
- Edge distinction: this campaign tests realized cross-sector ETF return
  dispersion and dispersion changes. It is not directional sector leadership,
  option-implied correlation, VXN/VIX implied-volatility dispersion, rates or
  dollar state, ES own-return state, or realized ES volatility-of-volatility.
- Feature construction:
  `tools/build_es_sector_dispersion_features.py` wrote
  `data/external/es_sector_dispersion_features_20110103_20260609.csv` with
  3817 rows and 3817 valid rank rows. Every tradable feature uses sector ETF
  closes available on or before session date minus one business day.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, and `README.md`.
- Density audit:
  `research_artifacts/es_sector_dispersion_state_density_audit_20260617.md`;
  all five original threshold grids cleared the rough 50 signals/year density
  screen before fills.
- Verification before staged runs:
  `PYTHONPATH=src python3 -m pytest tests/test_sector_dispersion_state.py tests/test_strategy_modules.py tests/test_preflight.py -q`
  passed 143 tests; targeted preflight for the five originals and five rescues
  passed.
- Originals: all five failed `limited_core_grid_test`. Four originals had a
  0.0 profitable-combo rate; `falling_5d_dispersion_long_1330/run1` had
  0.07407407407407407 profitable-combo rate and zero benchmark-passing
  combinations.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving edge thesis, entry module, setup mode, signal time,
  direction rule, data, costs, fills, sessions, prop rules, and validation
  gates. All five rescues also failed `limited_core_grid_test`.
- Best rescue was `rising_1d_dispersion_short_1130/rescue1`, top net `1945.00`,
  top PF `1.1158600148920328`, 111 trades, 72.37936784423603 trades/year, but
  only 0.25925925925925924 profitable-combo rate and zero benchmark-passing
  combinations, below the 70% limited-core stability gate.
- Aggregate artifacts:
  `backtest-campaigns/es_sector_dispersion_state/campaign_test_summary.json`,
  `backtest-campaigns/es_sector_dispersion_state/campaign_results.csv`,
  `backtest-campaigns/es_sector_dispersion_state/wfa_table.csv`,
  `backtest-campaigns/es_sector_dispersion_state/monte_carlo_summary.json`,
  and
  `research_artifacts/es_sector_dispersion_state_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation,
  frozen validation, or candidate reporting. No `candidate_strategy_report.md`
  was created.


## ES Opening Range Orderflow Breakout - 2026-06-17

- Added active price-action plus aggregate-orderflow campaign
  `es_opening_range_orderflow_breakout` using only the local Sierra ES RTH
  1-minute orderflow cache. No paid data was downloaded.
- Edge distinction: this campaign tests completed opening-range breakout
  continuation confirmed by same-bar aggregate orderflow. It is not the prior
  NR4/NR7 range-compression breakout campaign, not the opening-drive inventory
  absorption campaign, and not standalone signed-flow persistence.
- Added entry module
  `src/propstack/strategy_modules/entry/opening_range_orderflow_breakout.py`
  plus registration and engine feature-column checks. Signals use completed
  opening-range levels and completed 5-minute confirmation bars; engine entry
  remains next-bar open.
- Authored exactly five variants with entry, stop, target module shims,
  `config.yaml`, `README.md`, and required pre-test mechanics reviews:
  `or15_signed_flow_breakout_1030`, `or30_signed_flow_breakout_1100`,
  `or15_large10_flow_breakout_1030`, `or30_large20_flow_breakout_1100`, and
  `or60_signed_flow_breakout_1200`.
- Density audit:
  `research_artifacts/es_opening_range_orderflow_breakout_density_audit_20260617.md`;
  every declared entry corner exceeded 50 signals/year, and the strictest
  entry corner remained above 50/year even with the tightest declared 16-point
  OR-edge stop cap.
- Verification before staged runs:
  `PYTHONPATH=src python3 -m pytest tests/test_opening_range_orderflow_breakout.py tests/test_strategy.py tests/test_data_pipeline.py tests/test_campaign_stages.py tests/test_preflight.py -q`
  passed 68 tests; targeted preflight for the five originals and five rescues
  passed.
- Originals: all five failed `limited_core_grid_test`. Four originals had a
  0.0 profitable-combo rate. The best original was
  `or60_signed_flow_breakout_1200/run1` with 0.07407407407407407 profitable
  combinations; its top row made `267.50`, PF `1.0201127819548872`, 94 trades,
  and 61.52153056462903 trades/year, but failed concentration and expectancy
  quality.
- Rescues: all five failed variants received exactly one parameter-space-only
  rescue preserving edge thesis, entry module, stop module, target module,
  timeframe, data, costs, fills, sessions, prop rules, and validation gates.
  The rescue tested smaller breakout buffers, lower flow thresholds, and
  smaller fixed-R targets; all five rescues failed `limited_core_grid_test`
  with 0.0 profitable-combo rate.
- Aggregate artifacts:
  `backtest-campaigns/es_opening_range_orderflow_breakout/campaign_test_summary.json`,
  `backtest-campaigns/es_opening_range_orderflow_breakout/campaign_results.csv`,
  `backtest-campaigns/es_opening_range_orderflow_breakout/wfa_table.csv`,
  `backtest-campaigns/es_opening_range_orderflow_breakout/monte_carlo_summary.json`,
  and
  `research_artifacts/es_opening_range_orderflow_breakout_rescue_attempt_1_20260617.md`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation,
  frozen validation, or candidate reporting. No `candidate_strategy_report.md`
  was created.


## ES Semivariance Orderflow Confirmation - 2026-06-18

- Added constrained composite campaign `es_semivariance_orderflow_confirmation` using lagged realized semivariance, same-session price action from the known RTH open, and completed aggregate signed orderflow. No paid data was downloaded.
- Initial one-checkpoint variants failed pre-PnL signal density; before any staged PnL testing, the mechanics were reformulated to fixed multi-time decision variants. Original density artifact: `research_artifacts/es_semivariance_orderflow_confirmation_density_audit_20260618.md`; final density artifact: `research_artifacts/es_semivariance_orderflow_confirmation_reformulated_density_audit_20260618.md`.
- Verification before staged runs: `PYTHONPATH=src python3 -m pytest tests/test_realized_semivariance_orderflow_confirmation.py -q` passed 4 tests; targeted preflight for the five originals and five rescue configs passed.
- Originals: all five final variants failed `limited_core_grid_test`. Best original was `badvol_signed_multitime_short/run1` with 24/54 profitable combinations (0.4444), 18 benchmark-passing combos, top net `4545.00`, PF `1.4309`, and 74.86 trades/year, below the 70% profitable-combo threshold.
- Rescues: all five failed variants received exactly one parameter-space/fixed-parameter rescue preserving edge thesis, entry module, stop module, target module, decision times, data, costs, fills, sessions, prop rules, and validation gates.
- Best rescue was `badvol_signed_multitime_short/rescue1`: limited core passed with 29/36 profitable combinations (0.8056) and 28 benchmark-passing combos; limited monkey passed. It then failed WFA with early exit, stitched OOS PF `0.7123`, MAR `-0.7884`, expectancy R `-0.1411`, and 94.68 trades/year.
- Aggregate artifacts: `backtest-campaigns/es_semivariance_orderflow_confirmation/campaign_test_summary.json`, `backtest-campaigns/es_semivariance_orderflow_confirmation/campaign_results.csv`, `backtest-campaigns/es_semivariance_orderflow_confirmation/wfa_table.csv`, `backtest-campaigns/es_semivariance_orderflow_confirmation/monte_carlo_summary.json`, and `research_artifacts/es_semivariance_orderflow_confirmation_rescue_attempt_1_20260618.md`.
- Decision: FAIL. No run reached WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.


## ES Wide-Range Orderflow Continuation - 2026-06-18
- Added and tested `wide_range_orderflow_continuation` as a price-action-first aggregate-orderflow continuation campaign.
- Pre-PnL density audit passed for all five variants on full history and the default limited-core random window.
- Five originals and five per-failed-variant parameter-space-only rescues were run. All failed `limited_core_grid_test`; no run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.
- Decision: FAIL. No candidate strategy report was created.

## ES Prior Value-Area Orderflow Acceptance - 2026-06-18

- Added and tested `prior_value_area_orderflow_acceptance`, a local Sierra completed-bar price-action/orderflow campaign using prior-session approximate value-area boundaries.
- Pre-PnL density passed for originals and rescues; strict corners stayed above 50 signals/year in the current limited-core window.
- All five original variants failed limited core. All five one-time rescues were run; four failed limited core, and `morning_signed_vah_acceptance_long/rescue1` failed limited monkey despite core passing.
- No WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate report was reached. Decision: FAIL.


## ES Prior-Session Flip Retest Orderflow - 2026-06-18

- Added and tested `es_prior_session_flip_retest_orderflow`, a price-action plus aggregate-orderflow campaign using only the local Sierra ES RTH cache. No paid data was downloaded.
- Initial fresh-level-only/one-sided formulation was rejected before PnL for sparse density. The final pre-PnL formulation kept the same S/R flip retest edge, disabled the fresh-level requirement, made all five variants two-sided, and passed strict density checks above 50 signals/year.
- Added default-preserving support for `entry.params.require_fresh_level=false`, `entry.params.flow_confirmation=aligned|absorbed`, and the `prior_level_retest_boundary` stop. Targeted tests passed: `PYTHONPATH=src python3 -m pytest tests/test_pdh_pdl_orderflow_breakout_continuation.py tests/test_preflight.py -q`.
- Originals: all five variants failed `limited_core_grid_test` with 0.0 profitable-combo rate.
- Rescues: all five one-time parameter-space/fixed-parameter rescues were run. All failed `limited_core_grid_test`; best rescue was `afternoon_large10_aligned_two_sided_flip/rescue1` with top net `-38.75`, PF `0.9977064220183486`, and 90.98917839163146 trades/year, still below profitability and robustness requirements.
- Aggregate artifacts: `backtest-campaigns/es_prior_session_flip_retest_orderflow/campaign_test_summary.json`, `campaign_results.csv`, `wfa_table.csv`, `monte_carlo_summary.json`, and `research_artifacts/es_prior_session_flip_retest_orderflow_rescue_attempt_1_20260618.md`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## ES Opening Gap Orderflow Continuation - 2026-06-18

- Added and tested `es_opening_gap_orderflow_continuation`, a prior-close opening-gap hold continuation campaign using local Sierra aggregate orderflow only. No paid data was downloaded.
- Initial density corners were too sparse; before any PnL testing, gap/flow thresholds were reformulated twice while preserving the gap-hold plus aligned-orderflow mechanic. Final strict density passed above 50 signals/year for all five variants.
- Added `opening_gap_orderflow_continuation` and `opening_gap_boundary`; targeted tests passed with `PYTHONPATH=src python3 -m pytest tests/test_opening_gap_orderflow_continuation.py -q`.
- Originals: all five variants failed `limited_core_grid_test` with 0.0 profitable-combo rate.
- Rescues: all five one-time parameter-space/fixed-parameter rescues were run and all failed `limited_core_grid_test`. Best run was `late_morning_large10_gap_hold_continuation_1100/rescue1` with top net `686.25`, PF `1.057068607068607`, and 51.32806680543288 trades/year.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## ES Intraday Capitulation Orderflow Reversion - 2026-06-18

- Added and tested `es_intraday_capitulation_orderflow_reversion`, a completed-bar downside capitulation campaign using only local Sierra ES RTH OHLCV, session VWAP, session-local RSI/volume state, and aggregate signed-volume imbalance. No paid data was downloaded.
- Pre-PnL density passed for all five variants on full history and the seeded limited-core random window; strict corners stayed above 50 signals/year. Artifact: `research_artifacts/es_intraday_capitulation_orderflow_reversion_density_audit_20260618.md`.
- Added/tightened `intraday_capitulation_mr` so RSI and volume history are session-local, signals use completed-window sell imbalance, and next-bar execution is preserved. Targeted tests passed: `PYTHONPATH=src python3 -m pytest tests/test_intraday_capitulation_mr.py tests/test_strategy_modules.py::test_intraday_capitulation_mr_entry_emits_on_completed_15m_bar tests/test_strategy_modules.py::test_intraday_capitulation_mr_entry_rejects_close_not_near_low -q`.
- Originals: all five variants failed `limited_core_grid_test` with 0.0 profitable-combo rate.
- Rescues: all five one-time parameter-space/fixed-parameter rescues were run and all failed `limited_core_grid_test` with 0.0 profitable-combo rate. Best run was `late_day_10m_capitulation_long_1530/rescue1` with top net `-2477.5`, PF `0.6868878357030016`, and 73.57176633697684 trades/year.
- Aggregate artifacts: `backtest-campaigns/es_intraday_capitulation_orderflow_reversion/campaign_test_summary.json`, `campaign_results.csv`, `wfa_table.csv`, `monte_carlo_summary.json`, and `research_artifacts/es_intraday_capitulation_orderflow_reversion_rescue_attempt_1_20260618.md`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## ES Opening-Drive VWAP Orderflow Pullback - 2026-06-18

- Added and tested `es_opening_drive_vwap_orderflow_pullback`, a price-action plus aggregate-orderflow composite using local Sierra ES RTH cache only. No paid data was downloaded.
- The campaign requires a completed 30- or 60-minute opening-drive direction, a later session-VWAP pullback/reclaim, and aligned completed-bar aggregate orderflow. It is distinct from raw VWAP trend reclaim and raw opening-range breakout/retest campaigns.
- Pre-PnL density rejected 15-minute drive variants before PnL because their strict corner had only 26.65 limited-window signals/year. The final five 30/60-minute variants passed the 50 trades/year density screen. Artifact: `research_artifacts/es_opening_drive_vwap_orderflow_pullback_density_audit_20260618.md`.
- Added a targeted test for `vwap_orderflow_pullback_continuation` in `opening_drive_pullback` mode; targeted tests passed with `PYTHONPATH=src python3 -m pytest tests/test_vwap_orderflow_pullback_continuation.py -q`.
- Originals: all five variants failed `limited_core_grid_test` with 0.0 profitable-combo rate.
- Rescues: all five one-time parameter-space/fixed-parameter rescues were run and all failed `limited_core_grid_test` with 0.0 profitable-combo rate. Best run was `drive30_large20_pullback_1230/rescue1` with top net `-747.5`, PF `0.8987127371273713`, and 60.11494167194664 trades/year.
- Aggregate artifacts: `backtest-campaigns/es_opening_drive_vwap_orderflow_pullback/campaign_test_summary.json`, `campaign_results.csv`, `wfa_table.csv`, `monte_carlo_summary.json`, and `research_artifacts/es_opening_drive_vwap_orderflow_pullback_rescue_attempt_1_20260618.md`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## ES VWAP Deviation Orderflow Reversion - 2026-06-18

- Added and tested `es_vwap_deviation_orderflow_reversion`, a two-sided VWAP-extension reversion campaign using completed counter-direction aggregate orderflow. No paid data was downloaded.
- Added `vwap_deviation_orderflow_reversion` entry module and engine feature requirements. Targeted tests passed with `PYTHONPATH=src python3 -m pytest tests/test_vwap_deviation_orderflow_reversion.py -q`.
- Pre-PnL density passed for all five final variants at the strict corner in both full history and the seeded limited-core window. Artifact: `research_artifacts/es_vwap_deviation_orderflow_reversion_density_audit_20260618.md`.
- Originals: all five variants failed `limited_core_grid_test` with 0.0 profitable-combo rate.
- Rescues: all five one-time parameter-space/fixed-parameter rescues were run and all failed `limited_core_grid_test` with 0.0 profitable-combo rate. Best run was `midday_signed_counterflow_1400/rescue1` with top net `-1858.75`, PF `0.39882757226601984`, and 60.450316066562436 trades/year.
- Aggregate artifacts: `backtest-campaigns/es_vwap_deviation_orderflow_reversion/campaign_test_summary.json`, `campaign_results.csv`, `wfa_table.csv`, `monte_carlo_summary.json`, and `research_artifacts/es_vwap_deviation_orderflow_reversion_rescue_attempt_1_20260618.md`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.


## ES/MES Aligned-Flow Continuation - 2026-06-18

- Added and tested `es_mes_aligned_flow_continuation`, a cross-contract price-action/orderflow confirmation campaign using local Sierra ES/MES completed 1-minute RTH bars. No paid data was downloaded.
- Pre-PnL density passed for all five variants on full history, the seeded limited-core random window, WFA first-90%, and latest-year validation slice. Artifact: `research_artifacts/es_mes_aligned_flow_continuation_density_audit_20260618.md`.
- Added `es_mes_aligned_flow_continuation` entry module and engine feature requirements. Focused tests passed with `PYTHONPATH=src python3 -m pytest tests/test_es_mes_aligned_flow_continuation.py -q`.
- Originals: all five variants failed `limited_core_grid_test` with 0.0 profitable-combo rate.
- Rescues: all five one-time parameter-space/fixed-parameter rescues were run. All failed `limited_core_grid_test`; best rescue was `midday30_mes_large10_1230/rescue1` with 6/81 profitable combinations, top net `1192.5`, PF `1.488229`, and 63.52 trades/year, still far below the 70% profitable-combo gate.
- Aggregate artifacts: `backtest-campaigns/es_mes_aligned_flow_continuation/campaign_test_summary.json`, `campaign_results.csv`, `wfa_table.csv`, `monte_carlo_summary.json`, and `research_artifacts/es_mes_aligned_flow_continuation_rescue_attempt_1_20260618.md`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## ES SPX 0DTE Orderflow Continuation - 2026-06-18

- Added and tested `es_spx_0dte_orderflow_continuation`, the second and final local SPX 0DTE composite under the composite-edge policy. It uses the known SPX 0DTE calendar plus completed ES price movement and aggregate orderflow alignment. No paid data was downloaded.
- Corrected the pre-PnL data-validity start to `2016-02-24`, the first regular M/W/F SPX weekly-expiration regime date used for this edge. The initial 2011-start density draft was superseded because pre-2016 sessions are too sparse for the 50 trades/year rule.
- Pre-PnL density passed for all five original variants and all five rescue grids on full history, the seeded limited-core random window, WFA first-90%, and latest-year validation slice. Artifacts: `research_artifacts/es_spx_0dte_orderflow_continuation_density_audit_20260618.md` and `research_artifacts/es_spx_0dte_orderflow_continuation_rescue_attempt_1_density_audit_20260618.md`.
- Added `spx_0dte_orderflow_continuation` entry module and registry wiring. Focused tests passed with `PYTHONPATH=src python3 -m pytest tests/test_spx_0dte_orderflow_continuation.py -q`; campaign preflight passed for all original and rescue configs.
- Originals: all five variants failed `limited_core_grid_test`; early signed, early large10, and midday large20 had 0/81 profitable combinations, while late morning and late day had only 4/81 and 3/81 profitable combinations respectively.
- Rescues: all five one-time parameter-space/fixed-parameter rescues were run. All failed `limited_core_grid_test`; best rescue was `late_morning_large20_flow_continuation_1030/rescue1` with 37/81 profitable combinations, top net `1332.5`, PF `1.1483`, MAR `0.6452`, and 78.18 trades/year, still below the 70% profitable-combo gate.
- Aggregate artifacts: `backtest-campaigns/es_spx_0dte_orderflow_continuation/campaign_test_summary.json`, `campaign_results.csv`, `wfa_table.csv`, `monte_carlo_summary.json`, `trade_logs_manifest.csv`, and `equity_curves_manifest.csv`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created. Per the campaign stop rule, do not launch another local SPX 0DTE primary-edge composite unless materially new option-flow/gamma data is explicitly approved before testing.


## ES Intraday Periodicity Orderflow Confirmation - 2026-06-18

- Added and tested `es_intraday_periodicity_orderflow_confirmation`, a bounded composite of prior-session-only same-clock intraday return persistence and completed local Sierra ES aggregate orderflow confirmation. No paid data was downloaded.
- Pre-PnL density passed for all five original variants and all five rescue grids on full history, the seeded limited-core random window, WFA first-90%, and latest-year validation slice. Artifacts: `research_artifacts/es_intraday_periodicity_orderflow_confirmation_density_audit_20260618.md` and `research_artifacts/es_intraday_periodicity_orderflow_confirmation_rescue_attempt_1_density_audit_20260618.md`.
- Focused tests passed with `PYTHONPATH=src python3 -m pytest tests/test_intraday_periodicity_orderflow_confirmation.py tests/test_intraday_periodicity_persistence.py tests/test_campaign_stages.py::test_default_stage_criteria_match_screenshot_benchmarks tests/test_campaign_stages.py::test_canonicalized_stage_windows_match_shortlist_and_wfa_benchmarks tests/test_campaign_stages.py::test_random_fraction_stage_subset_uses_seeded_ten_percent_avoiding_covid_and_latest_holdout -q`.
- Originals: all five variants failed `limited_core_grid_test`; only `morning_1030_large10_confirmed_slot/run1` had any profitable combinations, at 6/81.
- Rescues: all five one-time parameter-space/fixed-parameter rescues were run. All failed `limited_core_grid_test`; best rescue was `morning_1030_large10_confirmed_slot/rescue1` with 29/81 profitable combinations, top net `1890.0`, PF `1.3109`, MAR `1.2782`, and 82.22 trades/year, still below the 70% profitable-combination gate.
- Aggregate artifacts: `backtest-campaigns/es_intraday_periodicity_orderflow_confirmation/campaign_test_summary.json`, `campaign_results.csv`, `wfa_table.csv`, `monte_carlo_summary.json`, `trade_logs_manifest.csv`, and `equity_curves_manifest.csv`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created. This result argues against another local intraday-periodicity composite without materially new evidence or data.


## 2026-06-18 - es_trend_filtered_mes_participation_crowding

- Created and tested `es_trend_filtered_mes_participation_crowding`, a bounded composite of MES participation crowding and prior completed ES trend alignment.
- Data used: local `data/cache/orderflow/es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny.csv`; no paid or external data download was performed.
- Pre-PnL density audits were written before PnL tests: `research_artifacts/es_trend_filtered_mes_participation_crowding_density_audit_20260618.md` and `research_artifacts/es_trend_filtered_mes_participation_crowding_rescue_attempt_1_density_audit_20260618.md`.
- Focused tests passed: `tests/test_trend_filtered_mes_participation_crowding.py` plus campaign-stage benchmark/window tests.
- Original runs: five variants, 81 combinations each. Two morning variants passed limited core but failed limited monkey; three midday/afternoon variants failed limited core.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. No module, session, data-window, cost, fill, or benchmark changes were made.
- Best rescue: `morning_trade_trend_pullback_reversal_1030/ES/rescue1` passed limited core, limited monkey, WFA, and WFA OOS monkey. WFA stitched OOS PF=1.449, MAR=1.734, trades/year=77.9, apex violations=0.
- Terminal rejection: WFA OOS Monte Carlo failed with probability_profit_before_drawdown=0.000, probability_account_breach=1.000, probability_net_profit_gt_0=0.000.
- Decision: FAIL. No `candidate_strategy_report.md` was created because the strategy failed the configured prop-style Monte Carlo gate.

## 2026-06-18 - es_mes_lead_lag_catchup

- Created and tested `es_mes_lead_lag_catchup`, a local ES/MES same-underlying lead-lag catch-up campaign using `data/cache/orderflow/es_mes_flow_divergence_1m_20190506_20260609_full_rth_ny.csv`; no paid or external data download was performed.
- Added `src/propstack/strategy_modules/entry/es_mes_lead_lag.py` and focused tests in `tests/test_es_mes_lead_lag.py` for long, short, lag rejection, signal-window behavior, and next-bar execution.
- Pre-PnL density artifacts: `research_artifacts/es_mes_lead_lag_catchup_density_audit_20260618.md` and `research_artifacts/es_mes_lead_lag_catchup_rescue_attempt_1_density_audit_20260618.md`. Both counted at most one signal per session and did not inspect PnL.
- Preflight passed for all five original configs and all five rescue configs. Focused tests plus benchmark-window tests passed with `PYTHONPATH=src python3 -m pytest tests/test_es_mes_lead_lag.py tests/test_campaign_stages.py::test_default_stage_criteria_match_screenshot_benchmarks tests/test_campaign_stages.py::test_canonicalized_stage_windows_match_shortlist_and_wfa_benchmarks tests/test_campaign_stages.py::test_random_fraction_stage_subset_uses_seeded_ten_percent_avoiding_covid_and_latest_holdout -q`.
- Original runs: all five variants failed `limited_core_grid_test` with 0/81 profitable combinations and zero apex violations.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. Entry module, stop module, target module, data, timeframe, direction logic, costs, fills, stage criteria, and prop rules were unchanged.
- Rescue runs: all five rescues failed `limited_core_grid_test` with 0/81 profitable combinations and zero apex violations.
- Aggregate artifacts: `backtest-campaigns/es_mes_lead_lag_catchup/campaign_test_summary.json`, `backtest-campaigns/es_mes_lead_lag_catchup/campaign_results.csv`, `backtest-campaigns/es_mes_lead_lag_catchup/wfa_table.csv`, `backtest-campaigns/es_mes_lead_lag_catchup/monte_carlo_summary.json`, `backtest-campaigns/es_mes_lead_lag_catchup/trade_logs_manifest.csv`, and `backtest-campaigns/es_mes_lead_lag_catchup/equity_curves_manifest.csv`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-18 - es_orderflow_impulse_reversal

- Created and tested `es_orderflow_impulse_reversal`, a local ES aggregate-orderflow campaign that fades completed same-clock signed-flow plus same-direction price impulses using `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`; no paid or external data download was performed.
- The campaign deliberately tested the liquidity-provision/inventory-correction mirror of signed-flow continuation, not a relaunch of the continuation edge. The stop module was `sweep_extreme`, so reversal invalidation was tied to the completed signal-bar high/low plus an offset.
- Pre-PnL density artifact: `research_artifacts/es_orderflow_impulse_reversal_density_audit_20260618.md`. The first density pass failed four variants at strict entry-threshold corners; because no PnL or trade outcomes had been inspected, entry thresholds were reformulated before testing. The retained grids passed density for all five variants in both the full data and canonical limited-core random 10% window.
- Preflight passed for all five original configs and all five rescue configs. Focused module test passed: `PYTHONPATH=src python3 -m pytest tests/test_strategy_modules.py::test_orderflow_regime_flow_impulse_reversal_fades_confirmed_flow -q`.
- Original runs: all five variants failed `limited_core_grid_test` with 0/81 profitable combinations and zero apex violations. Best original was `afternoon_60m_impulse_reversal_1400/run1`, top net `-1847.5`, PF `0.5050`, and 63.38 trades/year.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The rescue preserved entry module, stop module, target module, signal times, data, timeframe, costs, fills, stage criteria, and prop rules; only stop-offset and target-R grids shifted toward a quicker micro-retracement expression.
- Rescue runs: all five rescues failed `limited_core_grid_test` with 0/81 profitable combinations and zero apex violations. Best rescue was `afternoon_60m_impulse_reversal_1400/rescue1`, top net `-1969.375`, PF `0.4878`, and 63.38 trades/year.
- Aggregate artifacts: `backtest-campaigns/es_orderflow_impulse_reversal/campaign_test_summary.json`, `backtest-campaigns/es_orderflow_impulse_reversal/campaign_results.csv`, `backtest-campaigns/es_orderflow_impulse_reversal/wfa_table.csv`, `backtest-campaigns/es_orderflow_impulse_reversal/monte_carlo_summary.json`, `backtest-campaigns/es_orderflow_impulse_reversal/trade_logs_manifest.csv`, and `backtest-campaigns/es_orderflow_impulse_reversal/equity_curves_manifest.csv`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-18 - es_prior_value_area_orderflow_rejection

- Created and tested `es_prior_value_area_orderflow_rejection`, a local ES price-action/orderflow campaign that fades failed probes beyond frozen prior-session VAH/VAL when the completed signal bar closes back inside value with counterflow. No paid or external data download was performed.
- Added `prior_value_area_orderflow_rejection` entry module and registered its engine feature requirements. Focused tests passed with `PYTHONPATH=src python3 -m pytest tests/test_strategy_modules.py::test_prior_value_area_orderflow_acceptance_uses_prior_session_profile_for_long tests/test_strategy_modules.py::test_prior_value_area_orderflow_rejection_fades_vah_probe_back_inside tests/test_strategy_modules.py::test_prior_value_area_orderflow_rejection_fades_val_probe_back_inside tests/test_strategy_modules.py::test_prior_value_area_orderflow_rejection_requires_counterflow_and_trade_limit tests/test_campaign_stages.py::test_random_fraction_stage_subset_uses_seeded_ten_percent_avoiding_covid_and_latest_holdout -q`.
- Pre-PnL raw module-density artifact: `research_artifacts/es_prior_value_area_orderflow_rejection_density_audit_20260618.md`. Caveat: raw module counts overstate tradable density when positions overlap; staged `limited_core_grid_test` signal-density summaries are authoritative because the engine suppresses new signals while already in a position.
- Original runs: all five variants failed `limited_core_grid_test` with 0 profitable combinations and zero apex violations.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The rescue preserved entry module, stop module, target module, signal windows, value-area approximation, data, timeframe, costs, fills, stage criteria, and prop rules; only stop-offset and target-R grids shifted toward faster return-to-value exits.
- Rescue runs: all five rescues failed `limited_core_grid_test` with 0 profitable combinations and zero apex violations. Best rescue was `afternoon_large20_two_sided_rejection/rescue1`, top net `-1344.9999999999523`, PF `0.7318045862412856`, and 66.11731906154708 trades/year.
- Aggregate artifacts: `backtest-campaigns/es_prior_value_area_orderflow_rejection/campaign_test_summary.json`, `backtest-campaigns/es_prior_value_area_orderflow_rejection/campaign_results.csv`, `backtest-campaigns/es_prior_value_area_orderflow_rejection/wfa_table.csv`, `backtest-campaigns/es_prior_value_area_orderflow_rejection/monte_carlo_summary.json`, `backtest-campaigns/es_prior_value_area_orderflow_rejection/trade_logs_manifest.csv`, and `backtest-campaigns/es_prior_value_area_orderflow_rejection/equity_curves_manifest.csv`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-18 - es_morning_trend_lunch_reversal_orderflow

- Created and tested `es_morning_trend_lunch_reversal_orderflow`, a local ES price-action/orderflow campaign that fades same-session morning extensions only after a completed opposite-color signal bar and completed aggregate counterflow. No paid or external data download was performed.
- Added `morning_trend_lunch_reversal_orderflow` entry module, registry wiring, and engine feature requirements. Focused tests passed with `PYTHONPATH=src python3 -m pytest tests/test_morning_trend_lunch_reversal_orderflow.py tests/test_campaign_stages.py::test_random_fraction_stage_subset_uses_seeded_ten_percent_avoiding_covid_and_latest_holdout -q`.
- Pre-PnL raw module-density artifact: `research_artifacts/es_morning_trend_lunch_reversal_orderflow_density_audit_20260618.md`. All five variants passed raw density in the canonical limited-core window; staged `limited_core_grid_test` signal-density remains authoritative for tradable density after open-position suppression.
- Original runs: all five variants failed `limited_core_grid_test` with 0 profitable combinations and zero apex violations.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The rescue preserved entry module, stop module, target module, signal windows, data, timeframe, costs, fills, stage criteria, and prop rules; only extension thresholds, counterflow thresholds, and target-R grid changed.
- Rescue runs: all five rescues failed `limited_core_grid_test`. Best rescue was `late_morning_signed_up_extension_short_1130/rescue1`, with 1/81 profitable combinations, top net `51.875`, PF `1.0137235449735449`, and 45.085926192798176 trades/year, failing the 70% profitable-combo, trade-count, and concentration gates.
- Aggregate artifacts: `backtest-campaigns/es_morning_trend_lunch_reversal_orderflow/campaign_test_summary.json`, `backtest-campaigns/es_morning_trend_lunch_reversal_orderflow/campaign_results.csv`, `backtest-campaigns/es_morning_trend_lunch_reversal_orderflow/wfa_table.csv`, `backtest-campaigns/es_morning_trend_lunch_reversal_orderflow/monte_carlo_summary.json`, `backtest-campaigns/es_morning_trend_lunch_reversal_orderflow/trade_logs_manifest.csv`, and `backtest-campaigns/es_morning_trend_lunch_reversal_orderflow/equity_curves_manifest.csv`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-18 - es_ema_pullback_orderflow_continuation

- Created and tested `es_ema_pullback_orderflow_continuation`, a local ES price-action/orderflow campaign using same-session prior completed EMA trend state, completed pullback/reclaim of the prior fast EMA, completed aggregate orderflow confirmation, next-bar execution, `sweep_extreme` stops, and `fixed_r` targets. No paid or external market data was downloaded.
- Added `ema_pullback_orderflow_continuation` entry module, registry wiring, engine feature requirements, and focused tests. Verification passed with `PYTHONPATH=src python3 -m pytest tests/test_ema_pullback_orderflow_continuation.py tests/test_campaign_stages.py::test_random_fraction_stage_subset_uses_seeded_ten_percent_avoiding_covid_and_latest_holdout -q`.
- Pre-PnL density passed for all five original variants and all original entry threshold combinations. Artifact: `research_artifacts/es_ema_pullback_orderflow_continuation_density_audit_20260618.md`.
- Original runs: all five variants failed `limited_core_grid_test` with 0/81 profitable combinations and zero apex violations. The best original was `lunch_signed_two_sided_ema_pullback_1300/run1`, top net `-3470.0`, PF `0.7699320404442235`, 194 trades, and 126.06482619734493 trades/year.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The first strict rescue density draft was rejected before PnL because some corners fell below 50 trades/year; the retained rescue grid passed density before testing. The rescue preserved entry module, stop module, target module, timeframe, data, costs, fills, sessions, stage criteria, and prop rules.
- Rescue runs: all five rescues failed `limited_core_grid_test` with 0/81 profitable combinations and zero apex violations. The best rescue was `lunch_signed_two_sided_ema_pullback_1300/rescue1`, top net `-1498.75`, PF `0.891962515768607`, 136 trades, and 89.33056922346829 trades/year.
- Aggregate artifacts: `backtest-campaigns/es_ema_pullback_orderflow_continuation/campaign_test_summary.json`, `backtest-campaigns/es_ema_pullback_orderflow_continuation/campaign_results.csv`, `backtest-campaigns/es_ema_pullback_orderflow_continuation/wfa_table.csv`, `backtest-campaigns/es_ema_pullback_orderflow_continuation/monte_carlo_summary.json`, `backtest-campaigns/es_ema_pullback_orderflow_continuation/trade_logs_manifest.csv`, and `backtest-campaigns/es_ema_pullback_orderflow_continuation/equity_curves_manifest.csv`.
- User-suggested footprint/CVD absorption-initiation was assessed separately and queued behind a data-contract gate in `research_artifacts/footprint_absorption_initiation_edge_feasibility_20260618.md`; true diagonal footprint imbalance is not considered validated until local raw Sierra price-level bid/ask-volume features are built and tested.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-18 - Fixed-Config Core Trade Log Artifact

- Updated the staged runner so every future `limited_core_grid_test` writes a fixed-config mechanics cross-check run before grid evaluation.
- The fixed-config run uses the exact `strategy.entry`, `strategy.sl`, and `strategy.tp` parameters already present in the variant `config.yaml`; it does not use grid-selected, monkey-selected, WFA-selected, rescue-derived, or post-result parameters.
- New artifacts per variant run: `limited_core_grid_test/fixed_config_core_trade_log.csv`, `fixed_config_core_daily_results.csv`, `fixed_config_core_metrics.json`, `fixed_config_core_equity_curve.csv`, and `fixed_config_core_equity_curve.html`.
- The fixed-config core log uses the same resolved limited-core shortlist window as the core grid stage, which avoids touching the latest untouched holdout before a candidate reaches validation.
- Purpose: manual chart/source cross-check of trade mechanics only. It is not a pass/fail shortcut and does not replace core grid, monkey, WFA, Monte Carlo, incubation, or frozen validation gates.

## 2026-06-18 - es_footprint_absorption_initiation

- Created and tested `es_footprint_absorption_initiation`, a local ES price-action/footprint campaign using Sierra at-price bid/ask volume reduced to completed 1-minute diagonal-imbalance features. No paid or external market data was downloaded.
- Data contract: true LOB depth was not available; the tested feature is local Sierra traded-price bid/ask volume by price level. The derived cache is `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet`.
- Added `src/propstack/data/footprint.py`, `tools/build_sierra_footprint_feature_cache.py`, and `src/propstack/strategy_modules/entry/footprint_absorption_initiation.py`; registered engine feature checks and added focused tests.
- Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_footprint_absorption_initiation.py tests/test_footprint_features.py tests/test_sierra_trade_orderflow_cache.py -q` and `PYTHONPATH=src:. python3 -m pytest tests/test_campaign_stages.py -q`.
- Pre-PnL density: the first isolated one-sided prior-low/prior-high variants were rejected before PnL for insufficient density. Final five variants passed density before PnL; artifacts: `research_artifacts/es_footprint_absorption_initiation_density_audit_20260618.md` and `research_artifacts/es_footprint_absorption_initiation_density_summary_20260618.csv`.
- Original runs: all five variants failed `limited_core_grid_test`. Best original was `round_number_footprint_absorption_rejection_1500/run1`, with 4/81 profitable combinations, top net `687.5`, PF `1.1480086114101185`, 80 trades, and 56.42 trades/year.
- Fixed-config trade logs were written for all five originals under each `limited_core_grid_test/fixed_config_core_trade_log.csv`.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. Rescue density passed before PnL; artifact: `research_artifacts/es_footprint_absorption_initiation_rescue_attempt_1_density_audit_20260618.md`.
- Rescue runs: all five rescues failed `limited_core_grid_test`. Best rescue was `round_number_footprint_absorption_rejection_1500/rescue1`, with 11/81 profitable combinations, four benchmark-passing combinations, top net `1275.0`, PF `1.224669603524229`, 80 trades, and 56.42 trades/year. It still failed the required 70% profitable-combination gate.
- Fixed-config trade logs were written for all five rescues as well, for 10 total fixed-config core logs in this campaign.
- Aggregate artifacts: `backtest-campaigns/es_footprint_absorption_initiation/campaign_test_summary.json`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-18 - Footprint Zero-Diagonal Imbalance Cache Fix

- Investigated `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet` after manual inspection found `2026-06-09 09:30:00` had `footprint_highest_sell_imbalance_price = 7460.00`, equal to the bar high.
- Root cause: the footprint feature generator treated a missing opposite-side diagonal level as an infinite imbalance, which falsely marked sufficiently large bid volume at the bar high as a sell imbalance and sufficiently large ask volume at the bar low as a buy imbalance. Those infinities also caused nonzero imbalance-count rows to store `footprint_max_*_imbalance_ratio = 0.0`.
- Fixed `src/propstack/data/footprint.py` so diagonal imbalances require an observed comparison level: sell imbalances require `ask_above > 0`, and buy imbalances require `bid_below > 0`.
- Added regression coverage in `tests/test_footprint_features.py`; verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_footprint_features.py tests/test_footprint_absorption_initiation.py -q`.
- Rebuilt the ES footprint cache and validation JSON from local Sierra raw parquet files only; no paid or external data was downloaded. The corrected `2026-06-09 09:30:00` row now has `footprint_highest_sell_imbalance_price = 7458.75` and `footprint_max_sell_imbalance_ratio = 3.820896`.
- Post-rebuild sanity checks: rows `1,489,410`, duplicate timestamps `0`, sell rows with highest sell imbalance at bar high `0`, buy rows with lowest buy imbalance at bar low `0`, and nonzero-count rows with zero max ratio `0`.
- Detailed audit artifact: `research_artifacts/footprint_imbalance_zero_diagonal_bug_audit_20260618.md`.
- Impact: footprint absorption campaign artifacts produced before this fix should be treated as stale if that edge is revisited, even though the prior campaign decision was already FAIL.

## 2026-06-18 - es_footprint_absorption_initiation Corrected-Cache Rerun

- Reran all 10 source configs that reference `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet`: five original variants and five one-time parameter-space rescues.
- Preflight passed for all 10 configs with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...`.
- All 10 corrected-cache reruns failed `limited_core_grid_test`; no run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- Fixed-config core trade logs were written for all 10 reruns under each `limited_core_grid_test/fixed_config_core_trade_log.csv`.
- Corrected-cache best original: `round_number_footprint_absorption_rejection_1500/run1`, profitable-combo rate `1/81` (`0.012345679012345678`), benchmark-passing combinations `0`, top net `372.5`, PF `1.0747991967871486`, trades/year `58.534579970581646`.
- Corrected-cache max rescue profitable-combo rate: `prior_extreme_footprint_absorption_reversal_1500/rescue1`, `12/81` (`0.14814814814814814`), with zero benchmark-passing combinations and only `16.863300` trades/year in the top row.
- Corrected-cache best top-net rescue with any benchmark-passing combination: `round_number_footprint_absorption_rejection_1500/rescue1`, profitable-combo rate `4/81` (`0.04938271604938271`), benchmark-passing combinations `1`, top net `1416.25`, PF `1.2434464976364417`, trades/year `58.534579970581646`.
- Regenerated aggregate artifacts: `backtest-campaigns/es_footprint_absorption_initiation/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Updated `research_ledger.csv` rows for `es_footprint_absorption_initiation` to mark these as corrected-cache rerun evidence.
- Decision remains FAIL.

## 2026-06-18 - es_prior_session_benchmark_orderflow_reaction

- Created and tested `es_prior_session_benchmark_orderflow_reaction`, a local ES price-action/orderflow campaign that fades failed probes through completed previous RTH open/close benchmark levels only after a completed bar closes back across the level with aggregate counterflow. No paid or external market data was downloaded.
- Added `prior_session_benchmark_orderflow_reaction` entry-module wiring and focused tests for long reclaim, short rejection, counterflow gating, and one-trade-per-session behavior. Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_strategy_modules.py::test_prior_session_benchmark_orderflow_reaction_long_reclaim tests/test_strategy_modules.py::test_prior_session_benchmark_orderflow_reaction_short_rejects_prior_open_with_large20_flow tests/test_strategy_modules.py::test_prior_session_benchmark_orderflow_reaction_requires_counterflow_and_trade_limit tests/test_campaign_stages.py::test_random_fraction_stage_subset_uses_seeded_ten_percent_avoiding_covid_and_latest_holdout tests/test_campaign_stages.py::test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params -q`.
- Pre-PnL density passed for all five original variants and all five parameter-space rescues before PnL testing. Original density artifact: `research_artifacts/es_prior_session_benchmark_orderflow_reaction_density_audit_20260618.md`; rescue density artifact: `research_artifacts/es_prior_session_benchmark_orderflow_reaction_rescue_attempt_1_density_audit_20260618.md`.
- Original runs: all five variants failed `limited_core_grid_test` with 0/81 profitable combinations. Best original was `prior_close_midday_large10_reclaim_reversion_1400/run1`, top net `-476.25`, PF `0.9519546027742748`, 109 trades, and 71.22667693722123 trades/year.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The rescue preserved entry module, stop module, target module, timeframe, benchmark levels, signal windows, data, costs, fills, sessions, stage criteria, and prop rules.
- Rescue runs: all five rescues failed `limited_core_grid_test`. Best rescue was `prior_close_midday_large10_reclaim_reversion_1400/rescue1`, with 2/81 profitable combinations, top net `280.0`, PF `1.0298030867482704`, 104 trades, and 67.9593981786331 trades/year. It failed the 70% profitable-combination benchmark and concentration/losing-streak gates.
- Fixed-config core trade logs were written for all five originals and all five rescues, for 10 total fixed-config core logs in this campaign.
- Aggregate artifacts: `backtest-campaigns/es_prior_session_benchmark_orderflow_reaction/campaign_test_summary.json`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-18 - es_vix_term_structure_orderflow_pullback

- Created and tested `es_vix_term_structure_orderflow_pullback`, a composite local ES campaign that uses lagged Cboe VIX term-structure state as the prior-close risk regime and requires current-session ES VWAP pullback/rejection continuation plus completed aggregate orderflow before next-bar entry. No paid or external market data was downloaded; the campaign used local Sierra ES trade-orderflow bars and the existing local Cboe VIX term-structure feature CSV.
- Added `vix_term_structure_orderflow_pullback` entry-module wiring and focused tests for contango-long gating, wrong-direction rejection, front-stress short gating, existing VWAP/orderflow behavior, and fixed-config core trade-log artifact generation. Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_vix_term_structure_orderflow_pullback.py tests/test_vwap_orderflow_pullback_continuation.py tests/test_cboe_vix_term_structure.py tests/test_campaign_stages.py::test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params -q`.
- The first opening-drive-heavy draft was rejected before PnL for insufficient pre-PnL density and reformulated before staged testing. The retained mechanics preserved the same edge family: lagged VIX term-state plus ES VWAP/orderflow continuation. Original density artifact: `research_artifacts/es_vix_term_structure_orderflow_pullback_density_audit_20260618.md`.
- Preflight passed for all five originals and all five rescues with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...`.
- Original runs: all five variants failed `limited_core_grid_test` with 0/81 profitable combinations and zero apex violations. Best original was `curve_flattening_signed_vwap_reject_short_1500/run1`, top net `-192.5`, PF `0.9738451086956522`, 76 trades, and 75.4125688369364 trades/year.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The rescue preserved entry module, stop module, target module, timeframe, data window, VIX-state plus VWAP/orderflow pullback mechanic, costs, fills, sessions, prop rules, and staged gates. Rescue density passed before PnL; artifact: `research_artifacts/es_vix_term_structure_orderflow_pullback_rescue_attempt_1_density_audit_20260618.md`.
- Rescue runs: all five rescues failed `limited_core_grid_test`. Best rescue was `front_stress_large10_vwap_reject_short_1500/rescue1`, with 1/81 profitable combinations, top net `115.625`, PF `1.0346441947565543`, and 80 trades. It remained far below the required 70% profitable-combination gate.
- Fixed-config core trade logs were written for all five originals and all five rescues, for 10 total fixed-config core logs in this campaign.
- Aggregate artifacts: `backtest-campaigns/es_vix_term_structure_orderflow_pullback/campaign_test_summary.json`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-18 - es_footprint_absorption_initiation user-requested parquet rerun

- Reran every active source config that directly references `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet`: five original variants plus five per-variant parameter-space rescues under `campaigns/es_footprint_absorption_initiation`.
- Preflight passed for all 10 configs with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...`. Focused verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_footprint_features.py tests/test_campaign_stages.py::test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params -q`.
- All 10 reruns failed `limited_core_grid_test`. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- Fixed-config core trade logs and equity curves were regenerated for all 10 reruns. Aggregate artifacts were refreshed under `backtest-campaigns/es_footprint_absorption_initiation/`, including `campaign_test_summary.json`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Best original by top net profit remained `round_number_footprint_absorption_rejection_1500/run1`: 1/81 profitable combinations, 0 benchmark-passing combinations, top net `372.5`, PF `1.0747991967871486`, and 58.534579970581646 trades/year.
- Best rescue by top net profit remained `round_number_footprint_absorption_rejection_1500/rescue1`: 4/81 profitable combinations, 1 benchmark-passing combination, top net `1416.25`, PF `1.2434464976364417`, and 58.534579970581646 trades/year. It still failed the required >=70% profitable-combination gate.
- Decision: FAIL.

## 2026-06-19 - es_footprint_absorption_initiation user-requested parquet rerun

- Reran every active source config that directly references `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet`: five original variants plus five per-variant parameter-space rescues under `campaigns/es_footprint_absorption_initiation`.
- No paid or external data was downloaded. The run used the existing local Sierra footprint imbalance parquet.
- Preflight passed for all 10 configs with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...`. Focused verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_footprint_features.py tests/test_strategy_modules.py tests/test_campaign_stages.py::test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params -q`.
- All 10 reruns failed `limited_core_grid_test`. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- Fixed-config core trade logs and equity curves were regenerated for all 10 reruns. Aggregate artifacts were refreshed under `backtest-campaigns/es_footprint_absorption_initiation/`, including `campaign_test_summary.json`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Best original by top net profit remained `round_number_footprint_absorption_rejection_1500/run1`: 1/81 profitable combinations, 0 benchmark-passing combinations, top net `372.5`, PF `1.0747991967871486`, and 58.534579970581646 trades/year.
- Best rescue by top net profit remained `round_number_footprint_absorption_rejection_1500/rescue1`: 4/81 profitable combinations, 1 benchmark-passing combination, top net `1416.25`, PF `1.2434464976364417`, and 58.534579970581646 trades/year. It still failed the required >=70% profitable-combination gate.
- Decision: FAIL.

## 2026-06-18 - es_trend_filtered_prior_value_area_acceptance_orderflow

- Created and tested `es_trend_filtered_prior_value_area_acceptance_orderflow`, a bounded composite ES price-action/orderflow campaign. The signal required prior-session value-area acceptance, completed aggregate orderflow confirmation, and completed-bar multi-window trend alignment before next-bar entry. No paid or external data was downloaded.
- Added `trend_filtered_prior_value_area_acceptance` entry-module wiring and focused regression tests for accepted long signals, trend-gate rejection without consuming the session signal, and next-bar-open execution. Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_trend_filtered_prior_value_area_acceptance.py tests/test_campaign_stages.py::test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params -q`.
- Authored exactly five original variants before PnL testing, each with detailed YAML mechanics review: `morning_signed_vah_trend_acceptance_long`, `morning_signed_val_trend_acceptance_short`, `late_morning_large10_two_sided_trend_acceptance`, `midday_signed_two_sided_trend_acceptance`, and `afternoon_large20_two_sided_trend_acceptance`.
- Preflight passed for all five originals and all five rescues with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...`.
- Pre-PnL density passed for all originals and rescues. The actual limited-core period resolved by the staged random 10% rule was `2011-02-22` through `2012-09-06`, avoiding the latest 10% and the configured COVID avoid range. Density artifacts: `research_artifacts/es_trend_filtered_prior_value_area_acceptance_orderflow_density_audit_20260618.md` and `research_artifacts/es_trend_filtered_prior_value_area_acceptance_orderflow_rescue_attempt_1_density_audit_20260618.md`.
- Original runs: all five variants failed `limited_core_grid_test`. Best original was `morning_signed_vah_trend_acceptance_long/run1`, with 2/81 profitable combinations, top net `77.5`, PF `1.0062791168725946`, 102 trades, and 66.74245619273331 trades/year; it failed concentration and remained far below the 70% profitable-combo gate.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The rescue preserved entry module, stop module, target module, timeframe, prior value-area acceptance plus trend/orderflow mechanic, data, costs, fills, sessions, stage criteria, and prop rules.
- Rescue runs: all five rescues failed `limited_core_grid_test`. Best rescue was `morning_signed_vah_trend_acceptance_long/rescue1`, with 16/81 profitable combinations, top net `767.5`, PF `1.0631687242798353`, 99 trades, and 64.78992129903257 trades/year; it failed the concentration gate and the required 70% profitable-combo benchmark.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues, for 10 total fixed-config core logs in this campaign.
- Aggregate artifacts: `backtest-campaigns/es_trend_filtered_prior_value_area_acceptance_orderflow/campaign_test_summary.json`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-18 - es_nq_relative_value_orderflow_absorption_reversion

- Created and tested `es_nq_relative_value_orderflow_absorption_reversion`, a bounded composite ES campaign that fades ES/NQ return-spread divergence only when completed ES aggregate signed imbalance over the same lookback points counter to the ES price leg. No paid or external data was downloaded; the campaign used the existing local ES/NQ lead-lag/orderflow cache.
- The exact-minute draft was rejected before PnL for insufficient strict-corner signal density. The retained mechanics were reformulated before staged testing to the first qualifying completed bar inside a fixed window, max one trade per day. Density artifacts: `research_artifacts/es_nq_relative_value_orderflow_absorption_reversion_density_audit_20260618.md` and `research_artifacts/es_nq_relative_value_orderflow_absorption_reversion_rescue_attempt_1_density_audit_20260618.md`.
- Authored exactly five original variants before PnL testing, each with detailed YAML mechanics review: `morning15_two_sided_absorption_1000`, `morning30_underperform_absorption_long_1030`, `morning30_outperform_absorption_short_1030`, `late_morning30_two_sided_absorption_1130`, and `midday60_two_sided_absorption_1400`.
- Added `es_nq_relative_value_orderflow_absorption_reversion` entry-module wiring and focused regression tests for long/short absorption gating, wrong-flow rejection with session release, and next-bar-open execution.
- Original runs: all five variants failed `limited_core_grid_test`. Best original was `midday60_two_sided_absorption_1400/run1`, with 17/81 profitable combinations, five benchmark-passing combinations, top net `3872.5`, PF `1.3575715604801477`, 138 trades, and 90.65263168412297 trades/year. It still failed the required >=70% profitable-combination gate.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The rescue preserved entry module, stop module, target module, data, costs, fills, sessions, staged gates, and the ES/NQ divergence plus ES signed-flow absorption mechanic.
- Rescue runs: three rescues failed `limited_core_grid_test`. Two rescues passed limited core and limited monkey, then failed `walk_forward_analysis`: `midday60_two_sided_absorption_1400/rescue1` had stitched OOS PF `0.7169466764061359`, MAR `-0.6975521321854036`, trades/year `40.80309072008192`, and net `-1937.5`; `morning30_outperform_absorption_short_1030/rescue1` early-exited WFA with zero stitched OOS trades after IS selection failed profitability criteria.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues, for 10 total fixed-config core logs. WFA stitched OOS trade logs/equity curves were written for the two rescue WFA attempts.
- Aggregate artifacts: `backtest-campaigns/es_nq_relative_value_orderflow_absorption_reversion/campaign_test_summary.json`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Decision: FAIL. No run reached WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-18 - WFA OOS Monte Carlo Gate Correction Audit

- Fixed `src/propstack/research/campaign_stages.py` so default WFA OOS Monte Carlo uses the benchmark-sheet `$50,000` profit target before `$10,000` drawdown budget instead of silently inheriting tighter top-level daily/trailing drawdown rules. Account size and max-contract rules are still inherited; explicit MC/stage `prop_rules` can still tighten the test.
- Added focused regression tests in `tests/test_campaign_stages.py` for the default `$10,000` drawdown budget and for explicit stage-level drawdown overrides. Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_campaign_stages.py::test_wfa_oos_monte_carlo_defaults_to_50k_target_before_10k_drawdown tests/test_campaign_stages.py::test_wfa_oos_monte_carlo_does_not_inherit_tighter_top_level_drawdown_by_default tests/test_campaign_stages.py::test_wfa_oos_monte_carlo_stage_prop_rules_can_tighten_drawdown_defaults tests/test_monte_carlo.py::test_absolute_profit_target_and_drawdown_limit_override_percent_rules -q`.
- Reran `campaigns/es_trend_filtered_mes_participation_crowding/rescue_attempts/parameter_space_rescue_1/morning_trade_trend_pullback_reversal_1030/config.yaml` through the normal staged runner with the corrected MC gate. It again passed limited core, limited monkey, WFA, and WFA OOS monkey, then failed WFA OOS Monte Carlo.
- Corrected rerun WFA metrics: stitched OOS net profit `17410.0`, PF `1.449261337978195`, MAR `1.7344926418082498`, trades/year `77.87399848190942`, trades `158`, and apex/flatten violations `0`.
- Corrected rerun MC metrics: `probability_profit_before_drawdown = 0.0`, `probability_account_breach = 1.0`, median ending balance `139660.0`, p5 ending balance `139162.375`, p95 drawdown `10837.625`, and all 300 MC paths breached the corrected `$10,000` trailing drawdown budget before the `$50,000` profit target.
- Updated aggregate artifacts: `backtest-campaigns/es_trend_filtered_mes_participation_crowding/campaign_test_summary.json` and `backtest-campaigns/es_trend_filtered_mes_participation_crowding/monte_carlo_summary.json`.
- Decision remains FAIL. This is not a candidate strategy and no `candidate_strategy_report.md` was created.

## 2026-06-18 - es_trend_orderflow_prior_day_stop_reclaim

- Drafted `es_trend_orderflow_prior_day_stop_reclaim`, a bounded composite ES price-action/orderflow campaign requiring prior RTH high/low stop-run sweep-reclaim, pre-sweep completed-bar trend alignment, and absorbed aggregate orderflow on the completed reclaim bar before next-bar entry. No paid or external data was downloaded.
- Added `trend_orderflow_pdh_pdl_sweep_reclaim` entry-module wiring and focused tests for absorbed-flow gating and next-bar-open execution. Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_trend_orderflow_pdh_pdl_sweep_reclaim.py tests/test_pdh_pdl_trend_orderflow_breakout_continuation.py -q`.
- Authored exactly five variants with detailed YAML mechanics reviews before PnL inspection: `morning_pdl_signed_trend_absorption_long_1130`, `morning_pdh_signed_trend_absorption_short_1130`, `late_morning_signed_two_sided_trend_absorption_1230`, `midday_large10_two_sided_trend_absorption_1400`, and `afternoon_large20_two_sided_trend_absorption_1500`.
- Preflight passed with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...` for all five variants.
- Pre-PnL density audit failed before any staged PnL was run. The canonical limited-core period resolved to `2011-02-22` through `2012-09-06`; full configured data was `2011-01-03` through `2026-06-09`.
- Best limited-core density was `19.4627` signals/year; best full-data density was `26.630788` signals/year. Both are far below the required `50` signals/year screen even at the loosest entry corner.
- Density artifacts: `research_artifacts/es_trend_orderflow_prior_day_stop_reclaim_density_audit_20260618.md`, `research_artifacts/es_trend_orderflow_prior_day_stop_reclaim_density_audit_20260618.csv`, and `research_artifacts/es_trend_orderflow_prior_day_stop_reclaim_density_summary_20260618.csv`.
- Decision: FAIL before staged backtesting. No core grid, monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate report was run or created.

## 2026-06-18 - es_rolling_stat_envelope_orderflow_reversion

- Created and tested `es_rolling_stat_envelope_orderflow_reversion`, a local ES price-action/orderflow campaign. The signal fades a completed close outside a rolling mean/std close envelope when same-bar aggregate signed flow is pressing into the statistical extreme; envelope statistics use prior completed bars only and entry is next-bar open. No paid or external data was downloaded.
- Added `rolling_stat_envelope_orderflow_reversion` entry-module wiring and focused tests for lower-band sell-pressure reversal, wrong-flow rejection, and next-bar-open engine execution. Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_rolling_stat_envelope_orderflow_reversion.py tests/test_campaign_stages.py::test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params -q`.
- Authored exactly five original variants with detailed YAML mechanics reviews before PnL testing: `morning_5m_signed_6bar_reversion_1130`, `late_morning_5m_large10_12bar_reversion_1230`, `midday_5m_signed_18bar_reversion_1400`, `afternoon_5m_large20_24bar_reversion_1500`, and `all_day_1m_signed_30bar_reversion_1530`.
- Pre-PnL density passed for all originals before PnL. The canonical limited-core period resolved to `2011-02-22` through `2012-09-06`; full configured data was `2011-01-03` through `2026-06-09`. Density artifacts: `research_artifacts/es_rolling_stat_envelope_orderflow_reversion_density_audit_20260618.md`, `research_artifacts/es_rolling_stat_envelope_orderflow_reversion_density_audit_20260618.csv`, and `research_artifacts/es_rolling_stat_envelope_orderflow_reversion_density_summary_20260618.csv`.
- Original runs: all five failed `limited_core_grid_test` with `0/81` profitable combinations and `0` benchmark-passing combinations. Best original by top net was `all_day_1m_signed_30bar_reversion_1530/run1`, top net `-9395.0`, PF `0.5360493827160494`, and trades/year `243.08504867038465`.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The rescue preserved entry module, stop module, target module, data, costs, fills, sessions, stage gates, and the rolling-envelope reversion mechanic. A first rescue density draft was rejected before rescue PnL because some strict threshold corners fell below `50` signals/year; the retained rescue grid passed density before staged testing. Rescue density artifacts: `research_artifacts/es_rolling_stat_envelope_orderflow_reversion_rescue_attempt_1_density_audit_20260618.md`, `research_artifacts/es_rolling_stat_envelope_orderflow_reversion_rescue_attempt_1_density_audit_20260618.csv`, and `research_artifacts/es_rolling_stat_envelope_orderflow_reversion_rescue_attempt_1_density_summary_20260618.csv`.
- Rescue runs: all five failed `limited_core_grid_test` with `0/81` profitable combinations and `0` benchmark-passing combinations. Best rescue by top net was `afternoon_5m_large20_24bar_reversion_1500/rescue1`, top net `-3753.75`, PF `0.5252924438823902`, and trades/year `67.49014970436532`.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues, for 10 total fixed-config core logs.
- Aggregate artifacts: `backtest-campaigns/es_rolling_stat_envelope_orderflow_reversion/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-18 - es_overnight_range_compression_orderflow_breakout

- Created and tested `es_overnight_range_compression_orderflow_breakout`, a local ES price-action/orderflow campaign. The signal uses a locally built completed overnight range feature file, then enters only after a completed RTH close breaks outside the overnight high/low with same-direction aggregate Sierra orderflow; entry is next-bar open. No paid or external data was downloaded.
- Added `overnight_range_orderflow_breakout` entry-module wiring and focused tests for compressed-range breakout gating, wrong-flow rejection, uncompressed-range rejection, and next-bar-open execution. Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_overnight_range_orderflow_breakout.py tests/test_campaign_stages.py::test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params -q`.
- The first one-sided morning draft failed pre-PnL density before any stop, target, fill, net-profit, WFA, monkey, Monte Carlo, or validation result was computed. Artifact: `research_artifacts/es_overnight_range_compression_orderflow_breakout_density_audit_20260618.md`.
- Reformulated before staged PnL while preserving the same edge family: two-sided overnight boundary breakout, fixed zero extra breakout buffer, max overnight range rank as a lower-to-middle state, and aggregate orderflow threshold as the second entry tunable. Exactly five variants were retained with detailed YAML mechanics reviews before PnL: `morning_signed_two_sided_breakout_1030`, `morning_large10_two_sided_breakout_1100`, `late_morning_large10_two_sided_breakout_1130`, `midday_signed_two_sided_breakout_1300`, and `afternoon_large20_two_sided_breakout_1500`.
- Pre-PnL reformulated density passed for all five originals. The canonical limited-core period resolved to `2011-02-22` through `2012-09-05`; full configured data was `2011-01-03` through `2026-05-29`. Weakest full-window density was `57.196098` signals/year and weakest limited-core density was `59.791815` signals/year. Artifact: `research_artifacts/es_overnight_range_compression_orderflow_breakout_reformulated_density_audit_20260618.md`.
- Original runs: all five variants failed `limited_core_grid_test` with `0/81` profitable combinations and `0` benchmark-passing combinations. Best original was `midday_signed_two_sided_breakout_1300/run1`, top net `-202.5`, PF `0.9656488549618321`, and trades/year `83.49658623704724`.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The rescue preserved entry module, stop module, target module, timeframe, data, costs, fills, sessions, stage gates, and the completed overnight compression breakout plus aggregate orderflow confirmation mechanic. Rescue density passed before rescue PnL; artifact: `research_artifacts/es_overnight_range_compression_orderflow_breakout_rescue_attempt_1_density_audit_20260618.md`.
- Rescue runs: all five rescues failed `limited_core_grid_test` with `0/81` profitable combinations and `0` benchmark-passing combinations. Best rescue was `midday_signed_two_sided_breakout_1300/rescue1`, top net `-77.5`, PF `0.9865275966970882`, and trades/year `83.49658623704724`.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues, for 10 total fixed-config core logs.
- Aggregate artifacts: `backtest-campaigns/es_overnight_range_compression_orderflow_breakout/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-19 - es_trend_orderflow_prior_day_stop_reclaim rescue1 continuation

- Continued the previously drafted `es_trend_orderflow_prior_day_stop_reclaim` campaign after the original five variants failed pre-PnL density. No paid or external data was downloaded.
- Applied the one allowed parameter-space/fixed-parameter rescue per failed variant. The rescue preserved the entry module `trend_orderflow_pdh_pdl_sweep_reclaim`, stop module `percent_from_entry`, target module `fixed_r`, local Sierra data, costs, fills, sessions, prop rules, and validation gates. Fixed entry parameters were loosened before rescue PnL: wider `09:45-15:30` signal window, one-versus-two completed 5-minute bar trend snapshot, and declared grids for `entry.params.min_sweep_ticks` plus `entry.params.min_orderflow_imbalance`.
- Preflight passed for all five rescue configs with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...`. Focused tests passed with `PYTHONPATH=src:. python3 -m pytest tests/test_trend_orderflow_pdh_pdl_sweep_reclaim.py tests/test_campaign_stages.py::test_random_fraction_stage_subset_uses_seeded_ten_percent_avoiding_covid_and_latest_holdout tests/test_campaign_stages.py::test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params -q`.
- A standalone vectorized rescue density audit initially reported PASS, but staged-run `signal_density` contradicted it. That density artifact was explicitly marked invalidated: `research_artifacts/es_trend_orderflow_prior_day_stop_reclaim_rescue_attempt_1_density_audit_20260619.md`. The staged runner's module-level `signal_density` is the authoritative evidence.
- Rescue staged runs: all five failed `limited_core_grid_test`. Three signed two-sided rescues had `1/81` profitable combinations and `0` benchmark-passing combinations; the large10 and large20 rescues had `0/81` profitable combinations. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- Best rescue by top net was tied across the signed two-sided rescue configs: top net `36.25`, PF `1.019155`, only `24` top-row trades, `16.600526` trades/year, and failure reason `min_trades_per_year;preferred_min_total_trades;max_best_day_concentration`.
- Fixed-config core trade logs and equity curves were written for all five rescue runs.
- Aggregate artifacts: `backtest-campaigns/es_trend_orderflow_prior_day_stop_reclaim/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Decision: FAIL. No `candidate_strategy_report.md` was created.

## 2026-06-19 - es_key_reversal_orderflow_reversal

- Created and tested `es_key_reversal_orderflow_reversal`, a local ES price-action/orderflow campaign. The signal uses the immediately prior completed 1-minute bar high/low/close, requires the next completed bar to sweep and close back through the prior close with reversal body and close-location confirmation, and confirms with completed Sierra aggregate orderflow. No paid or external data was downloaded.
- Added `key_reversal_orderflow_reversal` entry-module wiring and focused tests. Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_strategy_modules.py tests/test_campaign_stages.py::test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params -q`.
- The first 5-minute formulation and a 1-minute grid including a 3-tick sweep corner were rejected before PnL for insufficient strict-corner density. Final pre-PnL density passed for all originals; rescue density also passed. Density artifacts: `research_artifacts/es_key_reversal_orderflow_reversal_density_audit_20260619.md` and `research_artifacts/es_key_reversal_orderflow_reversal_rescue1_density_audit_20260619.md`.
- Original runs: all five variants failed `limited_core_grid_test` with `0/54` profitable combinations and `0` benchmark-passing combinations. Best original was `afternoon_large20_two_sided_key_reversal_1530/run1`, top net `-1534.375`, PF `0.7911704661449472`, and trades/year `100.51056449402189`.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The rescue preserved entry module, stop module, target module, timeframe, data, costs, fills, sessions, stage gates, and the prior-bar key-reversal plus aggregate-orderflow confirmation mechanic.
- Rescue runs: all five failed `limited_core_grid_test`. Best rescue was `midday_signed_two_sided_key_reversal_1400/rescue1`, top net `-1720.0`, PF `0.7959667852906287`, trades/year `80.48603404398688`, and profitable combo rate `0.0`.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues, for 10 total fixed-config core logs.
- Aggregate artifacts: `backtest-campaigns/es_key_reversal_orderflow_reversal/campaign_test_summary.json`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-19 - es_footprint_absorption_initiation user-requested footprint parquet rerun

- Reran every active source config that directly references `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet`: five original variants plus five one-time parameter-space rescues.
- All 10 reruns completed through the current staged runner with no runner errors. Every run failed `limited_core_grid_test`; no run reached limited monkey, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- Best original remained `round_number_footprint_absorption_rejection_1500/run1`: `1/81` profitable combinations, `0` benchmark-passing combinations, top net `372.5`, PF `1.0747991967871486`, and trades/year `58.534579970581646`; it failed for best-day concentration.
- Best rescue remained `round_number_footprint_absorption_rejection_1500/rescue1`: `4/81` profitable combinations, `1` benchmark-passing combination, top net `1416.25`, PF `1.2434464976364417`, and trades/year `58.534579970581646`. It still failed because only `4.94%` of combinations were profitable, far below the `70%` limited-core benchmark.
- Fixed-config core trade logs were refreshed and present for all 10 runs.
- Refreshed aggregate artifacts: `backtest-campaigns/es_footprint_absorption_initiation/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Rerun audit: `research_artifacts/es_footprint_absorption_initiation_user_requested_parquet_rerun_20260619.md`.
- Decision remains FAIL. No `candidate_strategy_report.md` was created.

## 2026-06-19 - es_opening_range_failed_breakout_trend_orderflow

- Created and tested `es_opening_range_failed_breakout_trend_orderflow`, a bounded composite price-action/orderflow campaign. The signal uses a completed opening-range outside close, a reclaim back inside the range, frozen pre-breakout 3-bar/6-bar trend agreement, and completed Sierra aggregate orderflow confirmation. Entry is next-bar open. No paid or external data was downloaded.
- Added `opening_range_failed_breakout_trend_orderflow` entry-module wiring and focused tests for matching trend acceptance, wrong-trend rejection, and fixed-config trade-log output. Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_opening_range_failed_breakout_orderflow.py tests/test_campaign_stages.py::test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params -q`.
- The first source set failed pre-PnL density before any staged PnL was run. Full-history minimum density was at most `26.31` signals/year and limited-core minimum density was at most `18.17` signals/year across the five variants. Artifact: `research_artifacts/es_opening_range_failed_breakout_trend_orderflow_density_audit_20260619.md`.
- Reformulated before staged PnL by keeping the same OR failed-breakout reclaim plus trend/orderflow mechanic but monitoring the public OR levels through `15:30 ET`, shortening the trend snapshot to 3/6 bars, and declaring a 54-combination grid. Raw pre-PnL density passed for all five reformulated variants; weakest full-history minimum was `77.30055880787653` signals/year and weakest limited-core minimum was `61.631882770870334` signals/year. Artifact: `research_artifacts/es_opening_range_failed_breakout_trend_orderflow_reformulated_density_audit_20260619.md`.
- Original staged runs: all five reformulated variants failed `limited_core_grid_test` with `0/54` profitable combinations and `0` benchmark-passing combinations. The staged runner contradicted raw density optimism; closed-trade counts and staged diagnostics are authoritative.
- Best original was `or30_full_session_signed_trend_reclaim_1530/run1`, top net `-1252.5`, PF `0.13620689655172413`, and trades/year `25.320912625565832`.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The rescue preserved entry module, stop module, target module, data, costs, fills, sessions, stage gates, and the OR failed-breakout reclaim plus trend/orderflow mechanic.
- Rescue runs: all five failed `limited_core_grid_test` with `0/54` profitable combinations and `0` benchmark-passing combinations. Best rescue was `or30_full_session_large10_trend_reclaim_1530/rescue1`, top net `-2472.5`, PF `0.22794691647150664`, and trades/year `50.1361387211106`.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues, for 10 total fixed-config core logs.
- Aggregate artifacts: `backtest-campaigns/es_opening_range_failed_breakout_trend_orderflow/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`.
- Rescue audit: `research_artifacts/es_opening_range_failed_breakout_trend_orderflow_rescue_attempt_1_20260619.md`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-19 - es_opening_drive_mes_crowding_reversal

- Created and tested `es_opening_drive_mes_crowding_reversal`, a local ES/MES completed-bar campaign. The primary setup freezes the opening-drive extreme, then fades a completed failed extension beyond that extreme when MES participation rank is high. No paid data was downloaded.
- Added `opening_drive_mes_crowding_reversal` entry-module wiring, engine required-column checks, and focused tests for long/short signals plus next-bar execution. Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_opening_drive_mes_crowding_reversal.py tests/test_campaign_stages.py::test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params -q`.
- Authored exactly five original variants with detailed pre-test mechanics reviews: `od15_notional_failed_extension_reversal_1130`, `od15_trade_failed_extension_reversal_1130`, `od30_notional_failed_extension_reversal_1300`, `od30_trade_failed_extension_reversal_1300`, and `od60_notional_failed_extension_reversal_1530`.
- Pre-PnL density passed before staged testing. Weakest full-history density was 99.91 signals/year and weakest canonical limited-core density was 108.59 signals/year. Artifact: `research_artifacts/es_opening_drive_mes_crowding_reversal_density_audit_20260619.md`.
- Original runs: all five failed `limited_core_grid_test`. Best original was `od30_notional_failed_extension_reversal_1300/run1` with 28/81 profitable combinations, six benchmark-passing combinations, top net 1425.0, PF 1.1796973518284994, and 143.9715780738555 trades/year. It failed because profitable-combo rate was 0.345679012345679, below the required 0.70.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. Rescue density passed before rescue PnL. All five rescues failed `limited_core_grid_test`; best rescue by PF was `od30_trade_failed_extension_reversal_1300/rescue1` with 20/81 profitable combinations, nine benchmark-passing combinations, top net 1401.25, PF 1.2067502766506824, and 158.97991972245975 trades/year, but profitable-combo rate was only 0.24691358024691357.
- Aggregate artifacts: `backtest-campaigns/es_opening_drive_mes_crowding_reversal/campaign_test_summary.json`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`. Rescue audit: `research_artifacts/es_opening_drive_mes_crowding_reversal_rescue_attempt_1_20260619.md`.
- Decision: FAIL. No run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## 2026-06-19 - es_footprint_absorption_initiation current-engine footprint parquet rerun

- Reran every active source config that directly references `data/cache/orderflow/es_sierra_footprint_imbalance_1m_20101214_20260610_full_rth_ny.parquet` after current engine/module edits were newer than the prior 04:59 aggregate report: five original variants plus five one-time parameter-space rescues.
- Preflight passed for all 10 configs with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...`; staged reruns used `PYTHONPATH=src:. python3 -m propstack.run_campaign_stages --config <config.yaml> --fast-runtime-defaults`.
- All 10 reruns completed with no runner errors and failed `limited_core_grid_test`. No run reached limited monkey, WFA, WFA OOS monkey, WFA OOS Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- Best original remained `round_number_footprint_absorption_rejection_1500/run1`: `1/81` profitable combinations, `0` benchmark-passing combinations, top net `372.5`, PF `1.0747991967871486`, and trades/year `58.534579970581646`.
- Best rescue remained `round_number_footprint_absorption_rejection_1500/rescue1`: `4/81` profitable combinations, `1` benchmark-passing combination, top net `1416.25`, PF `1.2434464976364417`, and trades/year `58.534579970581646`. It failed because profitable-combo rate was `0.04938271604938271`, below the required `0.70`.
- Fixed-config core trade logs and equity curves are present for all 10 reruns.
- Refreshed aggregate artifacts: `backtest-campaigns/es_footprint_absorption_initiation/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`. Rerun audit: `research_artifacts/es_footprint_absorption_initiation_user_requested_parquet_rerun_20260619.md`.
- Decision remains FAIL. No `candidate_strategy_report.md` was created.

## 2026-06-19 - es_opening_range_nq_orderflow_breakout

- Created and tested `es_opening_range_nq_orderflow_breakout`, a bounded composite ES price-action/orderflow campaign. The signal freezes a completed ES opening range, trades only completed ES closes outside the range, requires same-direction ES aggregate signed flow, and requires completed NQ return leadership over the configured lookback window. Entry is next-bar open. No paid or external data was downloaded.
- Added `opening_range_nq_orderflow_breakout` entry-module wiring and focused tests for long/short NQ leadership gates, wrong-lead rejection, and next-bar execution. Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_opening_range_nq_orderflow_breakout.py tests/test_opening_range_orderflow_breakout.py tests/test_campaign_stages.py::test_fixed_config_core_artifacts_write_trade_log_from_yaml_strategy_params -q`.
- Preflight passed for all five originals and all five rescues with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...`.
- Pre-PnL original density passed before staged PnL; weakest full-history density was `142.48` signals/year and weakest limited-core density was `130.40` signals/year. Artifact: `research_artifacts/es_opening_range_nq_orderflow_breakout_density_audit_20260619.md`.
- Original staged runs: all five failed `limited_core_grid_test` with `0/81` profitable combinations and `0` benchmark-passing combinations. Best original was `or30_nq15_signed_breakout_1030/run1`, top net `-306.25`, PF `0.9890556597873671`, and trades/year `142.98502077221735`.
- Rescue policy applied once per failed variant, parameter-space/fixed-parameter only. The rescue preserved entry module, stop module, target module, local ES/NQ data, costs, fills, sessions, and validation gates; the only fixed-parameter narrowing was long-only continuation. Rescue density passed before rescue PnL; weakest full-history density was `73.17` signals/year and weakest limited-core density was `66.94` signals/year. Artifact: `research_artifacts/es_opening_range_nq_orderflow_breakout_rescue1_density_audit_20260619.md`.
- Rescue staged runs: all five failed `limited_core_grid_test` with `0/81` profitable combinations and `0` benchmark-passing combinations. Best rescue was `or30_nq15_signed_breakout_1030/rescue1`, top net `-33.75`, PF `0.9974446337308348`, and trades/year `66.94298699790177`.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues, for 10 total fixed-config core logs.
- Aggregate artifacts: `backtest-campaigns/es_opening_range_nq_orderflow_breakout/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.json`. Rescue audit: `research_artifacts/es_opening_range_nq_orderflow_breakout_rescue_attempt_1_20260619.md`.
- Decision: FAIL. No run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-19 - es_gao_last_half_hour_orderflow_confirmation user-authorized rescue2

- Ran a user-authorized second rescue for `first30_broad_large_alignment_1530` only. This is an explicit exception to the normal one-rescue-per-failed-variant rule, requested by the user.
- Changed only stop/target parameter space and fixed defaults: `sl.params.stop_pct` to `[0.0025, 0.003, 0.0035]` with fixed default `0.003`, and `tp.params.target_r_multiple` to `[1.25, 1.5, 2.0]` with fixed default `1.5`. Entry module, entry thresholds, first-window length, signal time, data, costs, fills, sessions, and validation gates were unchanged from `rescue1`.
- Preflight passed for `campaigns/es_gao_last_half_hour_orderflow_confirmation/rescue_attempts/parameter_space_rescue_2/first30_broad_large_alignment_1530/config.yaml`.
- Staged result: FAIL at `limited_core_grid_test`. Profitable combinations `1/36`, benchmark-passing combinations `0`, top net `107.5`, PF `1.0152158527954707`, trades/year `73.45024501632395`, failure reason `max_consecutive_losses;max_best_day_concentration`.
- Fixed-config core trade log and equity curve were written under `backtest-campaigns/es_gao_last_half_hour_orderflow_confirmation/first30_broad_large_alignment_1530/ES/rescue2/limited_core_grid_test/`.
- Decision remains FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## 2026-06-19 - user-authorized stop-distance rescue across best core variants

- Applied the user's explicit exception: for each active campaign, select the variant/run with the best existing limited-core grid evidence, then run one additional rescue that only widens stop distance. This is not a new edge and is not a mechanics rewrite.
- Selection and config generation were implemented in `tools/stop_widen_best_core_rescues.py`. The selector ranked existing core results by pass status, benchmark-passing combinations, profitable-combo rate, benchmark-passing rate, top net profit, PF, MAR, trades/year, and absence of Apex violations.
- Rescue configs were written under `campaigns/<campaign_id>/rescue_attempts/stop_distance_rescue_1/<variant_id>/config.yaml` with `test_run_id: stop_widen_rescue1`. The only intended strategy-parameter changes were stop widening: `sl.params.stop_pct` multiplied by `1.5`, `sl.params.max_stop_points` multiplied by `1.5`, and `sl.params.stop_offset_ticks` multiplied by `1.5` and rounded up. Entry modules, entry parameter spaces, target modules, data, costs, sessions, fill rules, and stage gates were preserved.
- Infrastructure fixes made before/while running this batch: `src/propstack/utils/config.py` now normalizes string entries in `variants_index.yaml` so legacy string-only variant lists do not crash index updates; `src/propstack/research/campaign_stages.py` caps the default fast-runtime worker count at `3` to avoid WFA process-pool stalls from large cached data slices.
- A temporary attempt to reuse existing WFA train grids for two long-running reruns produced `wfa_base_config_hash mismatch` errors. Those outputs were not accepted. The temporary reuse flags were removed and both affected runs were recomputed cleanly.
- Batch coverage: `118` campaigns selected, `118` staged summaries written, and `118` fixed-config core trade logs written under each `limited_core_grid_test/fixed_config_core_trade_log.csv`.
- Terminal stages: `91` failed `limited_core_grid_test`, `12` failed `limited_monkey_test`, `14` failed `walk_forward_analysis`, and `1` failed `wfa_oos_monte_carlo`.
- Strongest partial result was `es_trend_filtered_mes_participation_crowding/morning_trade_trend_pullback_reversal_1030`: core `79/81` benchmark-passing combinations and `100%` profitable combinations; stitched WFA OOS PF `1.4479787172517495`, MAR `2.4985322265215255`, and `77.38112507379607` trades/year. It still failed the WFA OOS Monte Carlo gate with `probability_profit_before_drawdown=0.0`, `probability_account_breach=1.0`, and `probability_payout_eligible=0.0`.
- Aggregate artifacts: `research_artifacts/stop_widen_best_core_rescue_queue_20260619.csv`, `research_artifacts/stop_widen_best_core_rescue_queue_20260619.json`, `research_artifacts/stop_widen_best_core_rescue_results_20260619.csv`, `research_artifacts/stop_widen_best_core_rescue_results_20260619.json`, and `research_artifacts/stop_widen_best_core_rescue_results_20260619.md`.
- `research_ledger.csv` was updated with one row per stop-widen rescue using `rescue_attempt=stop_distance_rescue_1_user_authorized_20260619`.
- Decision: FAIL. No run completed all staged gates, no simulated incubation or acceptance pass was reached, and no new `candidate_strategy_report.md` was created.

## 2026-06-19 - es_variance_ratio_orderflow_regime

- Created and tested `es_variance_ratio_orderflow_regime`, a price-action/orderflow campaign using rolling completed-bar variance ratio as the serial-dependence regime gate and Sierra aggregate orderflow as confirmation. No paid or external data was downloaded.
- Added `variance_ratio_orderflow_regime` entry-module wiring. The module computes variance ratio from rolling in-session completed closes, recent completed return, completed aggregate signed/large-trade flow, and signal-bar close location before emitting a next-bar-open signal.
- Authored exactly five variants with detailed YAML mechanics reviews before PnL: `morning_high_vr_signed_continuation_1130`, `midday_high_vr_large10_continuation_1400`, `afternoon_high_vr_signed_continuation_1530`, `morning_low_vr_signed_reversion_1130`, and `midday_low_vr_large10_reversion_1430`.
- The first pre-PnL density grid failed because strict morning corners had fewer than 50 signals/year. The reformulation happened before any PnL, stop, target, or trade-outcome inspection and only changed entry threshold grids. Final original density passed with minimum full-window density `54.816658` signals/year and minimum limited-core density `65.524423` signals/year. Artifacts: `research_artifacts/es_variance_ratio_orderflow_regime_density_audit_20260619.md`, `research_artifacts/es_variance_ratio_orderflow_regime_reformulated_density_audit_20260619.md`, and `research_artifacts/es_variance_ratio_orderflow_regime_final_density_audit_20260619.md`.
- Preflight passed for all five original configs. Original staged runs: all five failed `limited_core_grid_test` with `0/81` profitable combinations and `0` benchmark-passing combinations. Best original was `morning_high_vr_signed_continuation_1130/run1`, top net `-725.0`, PF `0.8543445504771472`, and trades/year `45.49321009773999`.
- Applied the one allowed parameter-space/fixed-threshold rescue per failed variant. Rescue kept the same entry module, stop module, target module, data, costs, fills, sessions, and validation gates. Initial rescue density failed; before any rescue PnL, threshold grids were adjusted until final rescue density passed with minimum full-window density `60.713012` and minimum limited-core density `50.60302`. Artifacts: `research_artifacts/es_variance_ratio_orderflow_regime_rescue1_density_audit_20260619.md`, `research_artifacts/es_variance_ratio_orderflow_regime_rescue1_final_density_audit_20260619.md`, and `research_artifacts/es_variance_ratio_orderflow_regime_rescue1_final2_density_audit_20260619.md`.
- Rescue staged runs: all five failed `limited_core_grid_test` with `0/81` profitable combinations and `0` benchmark-passing combinations. Best rescue was `midday_high_vr_large10_continuation_1400/rescue1`, top net `-182.5`, PF `0.9722222222222222`, and trades/year `41.58762555441617`.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues, for 10 total fixed-config core logs.
- Aggregate artifacts: `backtest-campaigns/es_variance_ratio_orderflow_regime/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Verification commands passed: `PYTHONPATH=src:. python3 -m pytest tests/test_strategy_modules.py::test_variance_ratio_orderflow_regime_emits_completed_bar_continuation_long tests/test_strategy_modules.py::test_variance_ratio_orderflow_regime_emits_completed_bar_reversion_short -q`; preflight passed for all original and rescue configs with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## TP Minimum-RR Rescue Batch - 2026-06-19

- Scope: one selected original/rescue variant per eligible campaign, selected from existing tested runs; target_r_multiple values below 1.0R were raised to 1.0R only.
- Rationale: user-authorized rule that no tested TP should be below 1.0 reward:risk because low-RR variants may lose too much gross PnL to slippage, commissions, and fees.
- Controls: entry, stop, data, session, costs, fill assumptions, and staged gates unchanged.
- Runs summarized: 94
- Campaigns skipped by minimum-RR rule: 25
- Full-stage passes: 0
- Terminal stage counts: limited_core_grid_test=90, limited_monkey_test=1, walk_forward_analysis=3
- Result artifact: `research_artifacts/tp_min_rr_best_core_rescue_results_20260619.md`
## 2026-06-19 - es_overnight_drift_european_open

- Tested the ES overnight European-open drift campaign on the existing local Databento ETH/RTH OHLCV cache; no paid data was downloaded.
- Corrected all original configs before testing so `target_r_multiple` values are never below 1.0R, and added preflight enforcement for this floor plus unsupported continuous-contract rules.
- Original staged runs: all five variants failed `limited_core_grid_test` with `0.0` profitable-combination rate and `0` Apex rule violations.
- Rescue policy applied once per failed variant under `campaigns/es_overnight_drift_european_open/rescue_attempts/parameter_space_rescue_1/`; rescue preserved modules, data, session, timeframe, signal clocks, costs, fill assumptions, and flatten rules.
- Rescue staged runs: all five failed `limited_core_grid_test` with `0.0` profitable-combination rate and `0` Apex rule violations.
- Best rescue was `london_open_prior_down_long_0300/rescue1`: top net `-652.5`, PF `0.9037610619469026`, MAR `-0.34059765617355614`, trades/year `58.54904019480725`; still below the 70% profitable-combo core gate.
- Fixed-config core trade logs and equity curves were written for all original and rescue runs.
- Aggregate artifacts: `backtest-campaigns/es_overnight_drift_european_open/campaign_test_summary.json`, `backtest-campaigns/es_overnight_drift_european_open/campaign_results.csv`, `backtest-campaigns/es_overnight_drift_european_open/trade_logs_manifest.csv`, `backtest-campaigns/es_overnight_drift_european_open/equity_curves_manifest.csv`, `backtest-campaigns/es_overnight_drift_european_open/wfa_table.csv`, and `backtest-campaigns/es_overnight_drift_european_open/monte_carlo_summary.csv`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## 2026-06-19 - es_mes_footprint_liquidity_sweep_reversion

- Created and tested `es_mes_footprint_liquidity_sweep_reversion`, a bounded composite price-action/orderflow campaign using completed rolling ES liquidity sweeps, Sierra footprint absorption, and MES participation crowding. The cache was built only from existing local ES footprint and MES participation files; no paid data was downloaded.
- Pre-PnL density audit passed for the five selected rolling variants. Minimum selected annualized one-trade-per-day signal density was `69.638557` signals/year; prior-day and opening-range level forms were rejected before PnL for insufficient density. Artifact: `research_artifacts/es_mes_footprint_liquidity_sweep_reversion_density_audit_20260619.md`.
- Preflight passed for all five original configs and all five rescue configs. The preflight includes the hard `target_r_multiple >= 1.0` rule; no sub-1R target was used.
- Original staged runs: all five failed `limited_core_grid_test`. Best original was `rolling45_full_session_trade_large10_two_sided/run1`: top net `1735.0`, PF `1.188586956521739`, MAR `1.062499316736399`, trades/year `104.12902805877536`, profitable-combo rate `0.3611111111111111`.
- Rescue policy applied exactly once per failed variant under `campaigns/es_mes_footprint_liquidity_sweep_reversion/rescue_attempts/parameter_space_rescue_1/`. Rescue changed only existing entry-threshold and stop-offset grids; TP grids were not changed because they already satisfied the 1.0R floor.
- Rescue staged runs: all five failed `limited_core_grid_test`. Best rescue was `rolling45_full_session_trade_large10_two_sided/rescue1`: top net `1872.5`, PF `1.1918053777208706`, MAR `1.1075348899720623`, trades/year `104.12761606699735`, profitable-combo rate `0.5555555555555556`. It still failed the 70% profitable-combo gate and had `0` benchmark-passing combinations.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_mes_footprint_liquidity_sweep_reversion/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-19 - target reward:risk floor correction

- User correction: TP should only be adjusted when an existing `target_r_multiple` is below `1.0R`; valid `1.0R+` targets must not be widened merely because higher reward:risk might improve after-cost PnL.
- Hard rule: no future staged test, core-grid combination, fixed-config core trade log, monkey run, WFA run, or signal-provided fixed-R target may use `target_r_multiple < 1.0`.
- Enforcement added at three levels: `research/preflight.py` recursively rejects sub-`1.0R` config values, `src/propstack/research/core_grid.py` rejects sub-`1.0R` parameter grids before expansion, and `src/propstack/backtest/engine.py` plus `src/propstack/strategy_modules/tp/fixed_r.py` reject sub-`1.0R` direct engine/signal targets at execution time.
- Existing historical artifacts were not rewritten; they remain evidence of prior tests. Any future rerun from an old sub-`1.0R` YAML must first be converted through an explicit minimum-RR floor rescue or it will fail closed.
- Verification: `PYTHONPATH=src:. python3 -m pytest tests/test_preflight.py::test_preflight_rejects_target_r_multiple_below_one tests/test_core_grid.py::test_parameter_combinations_rejects_target_r_multiple_below_one tests/test_backtest_engine.py::test_backtest_engine_rejects_target_r_multiple_below_one -q` passed, and `PYTHONPATH=src:. python3 -m pytest tests/test_core_grid.py tests/test_backtest_engine.py tests/test_preflight.py -q` passed.

## 2026-06-20 - target reward:risk floor correction follow-up

- User clarified the TP correction: only raise a target when it is below `1.0R`; do not widen already-valid `1.0R+` targets as a generic profitability rescue.
- Extended module-level enforcement to `src/propstack/strategy_modules/tp/cost_adjusted_fixed_r.py` so direct cost-adjusted fixed-R target calls cannot bypass the `1.0R` floor.
- Confirmed `signal_fixed_r` already routes signal-provided target metadata through `fixed_r_target`, so metadata-driven fixed-R targets below `1.0R` are rejected at execution time.
- Active authored YAML audit found no remaining `target_r_multiple < 1.0` values under `campaigns/`; stale historical references may still exist in generated reports or research notes, but they are not valid for future reruns and would fail closed under preflight/core-grid/engine enforcement.
- Verification: `PYTHONPATH=src:. python3 -m pytest tests/test_strategy_modules.py::test_fixed_r_target_rejects_reward_risk_below_one tests/test_strategy_modules.py::test_cost_adjusted_fixed_r_target_rejects_reward_risk_below_one tests/test_strategy_modules.py::test_signal_fixed_r_target_rejects_signal_reward_risk_below_one tests/test_preflight.py::test_preflight_rejects_target_r_multiple_below_one tests/test_core_grid.py::test_parameter_combinations_rejects_target_r_multiple_below_one tests/test_backtest_engine.py::test_backtest_engine_rejects_target_r_multiple_below_one -q` passed, and `PYTHONPATH=src:. python3 -m pytest tests/test_strategy_modules.py tests/test_strategy.py tests/test_preflight.py tests/test_core_grid.py tests/test_backtest_engine.py -q` passed.

## 2026-06-19 - es_morning_orderflow_momentum_continuation

- Created and tested `es_morning_orderflow_momentum_continuation`, a local Sierra-only price-action plus aggregate-orderflow campaign. The edge trades immediate post-opening-window ES continuation only when completed opening-window return and same-window aggregate signed or large-trade flow agree. No paid data was downloaded.
- Duplicate check: archived tests were ignored, but active failed campaigns were considered. This campaign was treated as distinct from standalone rolling signed-flow persistence, Gao last-half-hour prediction, price-only late-day momentum, and opening-range level breakout because the trigger is the completed opening-window return plus same-window flow confirmation with immediate next-bar entry.
- Authored exactly five variants with detailed pre-test mechanics reviews: `first30_signed_flow_continuation_1000`, `first45_large10_flow_continuation_1015`, `first60_signed_flow_continuation_1030`, `first60_large20_flow_continuation_1030`, and `first90_broad_large_alignment_1100`.
- Pre-PnL density audit passed after relaxing overly strict draft thresholds before any PnL inspection. Full-history minimum selected density was `56.6` signals/year and the seeded limited-core window minimum was `57.2` signals/year. Artifact: `research_artifacts/es_morning_orderflow_momentum_continuation_density_audit_20260619.md`.
- Original preflight passed for all five configs. Original staged runs: all five failed `limited_core_grid_test`. Best original was `first30_signed_flow_continuation_1000/run1`: profitable-combo rate `0.12345679012345678`, benchmark-passing combinations `3/81`, top net `2227.5`, PF `1.2052995391705068`, MAR `0.6633788420899629`, and trades/year `79.29228122899285`.
- Applied the one allowed parameter-space rescue per failed variant under `campaigns/es_morning_orderflow_momentum_continuation/rescue_attempts/parameter_space_rescue_1/`. Rescue changed only existing entry-threshold and stop-distance parameter spaces. The TP grid was not changed and remained `[1.0, 1.5, 2.0]`; no sub-`1.0R` target was used.
- Rescue preflight passed for all five rescue configs. Rescue staged runs: all five failed `limited_core_grid_test`. Best rescue was again `first30_signed_flow_continuation_1000/rescue1`: profitable-combo rate `0.2839506172839506`, benchmark-passing combinations `11/81`, top net `2227.5`, PF `1.2052995391705068`, MAR `0.6633788420899629`, and trades/year `79.29228122899285`. It remained far below the required `>=0.70` profitable-combo gate.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_morning_orderflow_momentum_continuation/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Verification commands passed: targeted preflight for five originals and five rescues; `PYTHONPATH=src:. python3 -m pytest tests/test_strategy_modules.py::test_morning_orderflow_momentum_emits_two_sided_signed_flow_continuation tests/test_strategy_modules.py::test_morning_orderflow_momentum_requires_completed_window_and_no_future_flow tests/test_strategy_modules.py::test_morning_orderflow_momentum_broad_large_alignment_filter tests/test_preflight.py::test_preflight_rejects_target_r_multiple_below_one tests/test_core_grid.py::test_parameter_combinations_rejects_target_r_multiple_below_one tests/test_backtest_engine.py::test_backtest_engine_rejects_target_r_multiple_below_one -q`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-20 - es_nyfed_rrp_liquidity_state

- Created and tested `es_nyfed_rrp_liquidity_state`, a local no-paid-data funding-liquidity campaign using a one-listed-trade-date lag of NY Fed ON RRP five-day change z-scores as the state variable. Source support was Brunnermeier and Pedersen (2009) for the funding-liquidity channel plus the New York Fed RRP FAQ for operation mechanics.
- Built lag-one local feature file `data/external/nyfed_rrp_liquidity_state_lag1_features_20140811_20260529.csv`; signals never use same-day RRP results.
- Authored exactly five variants with detailed pre-test mechanics reviews: `rrp_drain_short_1000`, `rrp_drain_short_1330`, `rrp_drain_short_1500`, `rrp_release_long_1000`, and `rrp_release_long_1330`.
- Original preflight passed for all five configs. Original staged runs all failed `limited_core_grid_test`. Best original by profitable-combo rate was `rrp_release_long_1330/run1`: profitable-combo rate `0.37037037037037035`, benchmark-pass combos `4/27`, top net `2895.0`, PF `1.1614162252578757`, MAR `0.6580958558393306`, and trades/year `139.31339919550535`.
- Applied one parameter-space rescue per failed variant under `campaigns/es_nyfed_rrp_liquidity_state/rescue_attempts/parameter_space_rescue_1/`. Rescue preserved entry, stop, target modules, data, sessions, fills, costs, and validation gates. It only removed weak near-zero RRP states from the threshold grids: drain `[0.125, 0.25, 0.375]`, release `[-0.25, -0.375, -0.5]`. TP grid remained `[1.0, 1.5, 2.0]`.
- Rescue density audit passed without PnL inspection: drain minimum `60.0` full-window signals/year and `75.6` limited-core signals/year; release minimum `53.2` full-window signals/year and `94.3` limited-core signals/year. Artifact: `research_artifacts/es_nyfed_rrp_liquidity_state_rescue_attempt_1_density_audit_20260620.md`.
- Rescue preflight passed for all five configs. Rescue staged runs all failed `limited_core_grid_test`. Best rescue was `rrp_drain_short_1000/rescue1`: profitable-combo rate `0.3333333333333333`, benchmark-pass combos `3/27`, top net `2666.25`, PF `1.1775133155792277`, MAR `0.6347742486118267`, and trades/year `83.79993009096303`.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues. All ten RRP configs were verified to have zero sub-`1.0R` target values.
- Aggregate artifacts: `backtest-campaigns/es_nyfed_rrp_liquidity_state/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Verification commands passed: RRP original and rescue preflight; `PYTHONPATH=src:. python3 -m pytest tests/test_strategy_modules.py::test_market_plumbing_priority_selects_first_active_leg tests/test_strategy_modules.py::test_fixed_r_target_rejects_reward_risk_below_one tests/test_strategy_modules.py::test_cost_adjusted_fixed_r_target_rejects_reward_risk_below_one tests/test_strategy_modules.py::test_signal_fixed_r_target_rejects_signal_reward_risk_below_one tests/test_preflight.py::test_preflight_rejects_target_r_multiple_below_one tests/test_core_grid.py::test_parameter_combinations_rejects_target_r_multiple_below_one tests/test_backtest_engine.py::test_backtest_engine_rejects_target_r_multiple_below_one -q`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-20 - es_sector_rotation_orderflow_pullback

- Created and tested `es_sector_rotation_orderflow_pullback`, a bounded composite campaign using lagged public sector ETF leadership as the risk-appetite state plus completed-bar ES VWAP/EMA pullback and Sierra aggregate orderflow confirmation. No paid data was downloaded.
- Duplicate check: this is distinct from the rejected fixed-time `es_sector_rotation_risk_appetite` campaign because the sector state only gates direction; it is also distinct from pure VWAP/EMA orderflow pullback campaigns because trades require a lagged cross-sector state before the ES price-action trigger.
- Authored exactly five variants with detailed pre-test mechanics reviews: `growth_vwap_reclaim_large10_long_1130`, `cyclical_vwap_reclaim_signed_long_1400`, `financial_industrial_ema_pullback_large10_long_1500`, `defensive_vwap_reject_large10_short_1130`, and `defensive_ema_pullback_signed_short_1530`.
- Pre-PnL density audit passed after rejecting an under-dense persistent-defensive EMA draft before any PnL inspection. The selected variants ranged from `56.25` to `85.67` signals/year. Artifact: `research_artifacts/es_sector_rotation_orderflow_pullback_density_audit_20260620.md`.
- Original preflight passed for all five configs. Original staged runs all failed `limited_core_grid_test`. Best original was `financial_industrial_ema_pullback_large10_long_1500/run1`: profitable-combo rate `0.3333333333333333`, benchmark-pass combos `3/81`, top net `1587.5`, PF `1.2620718118035492`, MAR `0.4645667684858558`, and trades/year `56.13268963958591`.
- Applied one parameter-space rescue per failed variant under `campaigns/es_sector_rotation_orderflow_pullback/rescue_attempts/parameter_space_rescue_1/`. Rescue preserved entry mechanics, entry parameter grids, TP module/grid, data, sessions, fills, costs, and validation gates. It only widened `sl.params.stop_pct` from `[0.0015, 0.0025, 0.004]` to `[0.0025, 0.004, 0.006]` and set the fixed stop default to `0.004`.
- Rescue preflight passed for all five configs. Rescue staged runs all failed `limited_core_grid_test`. Best rescue was `financial_industrial_ema_pullback_large10_long_1500/rescue1`: profitable-combo rate `0.6666666666666666`, benchmark-pass combos `7/81`, top net `1837.5`, PF `1.2547660311958406`, MAR `0.592991419475163`, and trades/year `56.13268963958591`. It remained below the required `>=0.70` profitable-combination gate.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_sector_rotation_orderflow_pullback/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Verification commands passed: sector-orderflow module and RR guard tests via `PYTHONPATH=src:. python3 -m pytest tests/test_sector_rotation_orderflow_pullback.py tests/test_tp_widen_best_core_rescues.py tests/test_preflight.py::test_preflight_rejects_target_r_multiple_below_one tests/test_core_grid.py::test_parameter_combinations_rejects_target_r_multiple_below_one tests/test_backtest_engine.py::test_backtest_engine_rejects_target_r_multiple_below_one -q`; original and rescue preflight passed with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-20 - es_low_toxicity_orderflow_extension_fade

- Created and tested `es_low_toxicity_orderflow_extension_fade`, a local Sierra aggregate-orderflow campaign that fades completed 5-minute price extensions only when same-clock absolute signed-volume imbalance ranks in the low-toxicity tail versus prior sessions. No paid data was downloaded.
- Duplicate check: this is distinct from active signed-flow persistence and orderflow impulse/reversal campaigns because it does not trade high signed-flow pressure. It trades the opposite state: price extension with unusually low same-clock absolute imbalance, interpreted as weak informed pressure.
- Authored exactly five variants with detailed pre-test mechanics reviews: `two_slot_morning_balanced_extension_fade`, `two_slot_midday_balanced_extension_fade`, `two_slot_late_balanced_extension_fade`, `three_slot_up_extension_fade_short`, and `three_slot_down_extension_fade_long`.
- Pre-PnL density audit rejected single-slot drafts for sub-50/year frequency, then approved the selected multi-slot mechanics. The selected variants ranged from `101.03` to `172.77` signals/year. Artifact: `research_artifacts/es_low_toxicity_orderflow_extension_fade_density_audit_20260620.md`.
- Original preflight passed for all five configs. Original staged runs all failed `limited_core_grid_test`. Best original was `two_slot_midday_balanced_extension_fade/run1`: profitable-combo rate `0.06172839506172839`, benchmark-pass combos `0/81`, top net `1430.0`, PF `1.2104488594554819`, MAR `0.4229436435347066`, and trades/year `48.26338305866597`; it failed trade-count and concentration gates.
- Applied one parameter-space rescue per failed variant under `campaigns/es_low_toxicity_orderflow_extension_fade/rescue_attempts/parameter_space_rescue_1/`. Rescue preserved entry module, slot definitions, TP module/grid, data, sessions, fills, costs, and validation gates. It only tightened the low-toxicity rank grid, raised the completed-extension threshold grid, and widened the stop grid. TP grid remained `[1.0, 1.5, 2.0]`.
- Rescue preflight passed for all five configs. Rescue staged runs all failed `limited_core_grid_test`. Best rescue was `three_slot_up_extension_fade_short/rescue1`: profitable-combo rate `0.2839506172839506`, benchmark-pass combos `3/81`, top net `1426.25`, PF `1.1969958563535912`, MAR `0.3531103679896602`, and trades/year `54.299392039154206`. It remained far below the required `>=0.70` profitable-combination gate.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_low_toxicity_orderflow_extension_fade/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Verification commands passed: `PYTHONPATH=src:. python3 -m pytest tests/test_strategy_modules.py::test_trade_orderflow_state_rank_uses_prior_same_clock_history tests/test_strategy_modules.py::test_trade_orderflow_state_rank_filters_return_and_trade_limit tests/test_strategy_modules.py::test_trade_orderflow_state_rank_can_use_precomputed_rank_column tests/test_strategy_modules.py::test_trade_orderflow_multi_state_rank_routes_stateless_slots tests/test_preflight.py::test_preflight_rejects_target_r_multiple_below_one tests/test_core_grid.py::test_parameter_combinations_rejects_target_r_multiple_below_one tests/test_backtest_engine.py::test_backtest_engine_rejects_target_r_multiple_below_one -q`; original and rescue preflight passed with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-20 - es_prior_poc_orderflow_magnet

- Created and tested `es_prior_poc_orderflow_magnet`, a local Sierra aggregate-orderflow campaign using prior-session approximate POC as a price-action liquidity magnet and completed-bar orderflow as confirmation. No paid data was downloaded.
- Duplicate check ignored `_archived` and treated this as distinct from active prior VAH/VAL acceptance, VAH/VAL rejection, prior high/low stop-run reclaim, opening-range failure, and prior open/close benchmark reactions. The mechanic is displacement from prior POC plus initiation back toward POC.
- Authored exactly five variants with detailed pre-test mechanics reviews: `morning_above_poc_signed_magnet_short`, `morning_below_poc_signed_magnet_long`, `late_morning_large10_two_sided_magnet`, `midday_signed_two_sided_magnet`, and `afternoon_large20_two_sided_magnet`.
- Pre-PnL density audit passed for all selected variants at the strict corner. Full-history strict-corner density ranged from `84.57` to `177.66` signals/year and limited-core density ranged from `101.74` to `195.40` signals/year. Artifact: `research_artifacts/es_prior_poc_orderflow_magnet_density_audit_20260620.md`.
- Source-config correction before final testing: the initial first run exposed that `core_grid.data_subset`, `monkey.data_subset`, and `wfa.data_subset` must be present for the runner's random-window and first-90% stage windows to resolve from the authored config. All five configs were corrected before final testing. Final run summaries show `limited_core_grid_test` used `2011-02-22` through `2012-09-06`, avoiding the latest 10% and the configured COVID range.
- Original preflight passed for all five configs. Original staged runs all failed `limited_core_grid_test`. Best original was `morning_above_poc_signed_magnet_short/run1`: profitable-combo rate `0.024691358024691357`, `2/81` profitable combinations, fixed-config core net `-3457.50`, and `119` fixed-config trades.
- Applied one parameter-space rescue per failed variant under `campaigns/es_prior_poc_orderflow_magnet/rescue_attempts/parameter_space_rescue_1/`. Rescue preserved entry module, setup mode, time window, flow mode, stop module, target module, data, sessions, costs, fills, and validation gates. It only adjusted entry threshold and/or stop-offset grids. TP grids were not changed and remained `[1.0, 1.5, 2.0]` because all targets already satisfied the `1.0R` floor.
- Rescue preflight passed for all five configs. Rescue staged runs all failed `limited_core_grid_test`. Best rescue was again `morning_above_poc_signed_magnet_short/rescue1`: profitable-combo rate `0.024691358024691357`, `2/81` profitable combinations, fixed-config core net `-2832.50`, and `109` fixed-config trades. It remained far below the required `>=0.70` profitable-combination gate.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_prior_poc_orderflow_magnet/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Verification commands passed: targeted POC module tests plus RR guard test; original and rescue preflight passed with `PYTHONPATH=src:. python3 -m research.preflight --skip-tests --config ...`.
- Decision: FAIL. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-20 - staged data-window fallback fix

- While testing `es_prior_poc_orderflow_magnet`, an initial run exposed a runner footgun: `limited_core_grid_test`, `limited_monkey_test`, and `walk_forward_analysis` resolved their `data_window` from section-level `core_grid.data_subset`, `monkey.data_subset`, or `wfa.data_subset`, then `data.data_subset`, but did not fall back to `core.data_subset`.
- Impact: authored configs that only declared `core.data_subset` could unintentionally run shortlist stages over the full source range instead of the benchmark random 10% window. The invalid POC run was overwritten after correcting the source configs; final POC artifacts show `2011-02-22` through `2012-09-06` for limited core.
- Fix: `src/propstack/research/campaign_stages.py::_stage_subset` now falls back in order: stage config, stage section, `core.data_subset`, then `data.data_subset`.
- Regression test added: `tests/test_campaign_stages.py::test_stage_subset_data_window_falls_back_to_core_data_subset`.
- Verification: `PYTHONPATH=src:. python3 -m pytest tests/test_campaign_stages.py::test_random_fraction_stage_subset_uses_seeded_ten_percent_avoiding_covid_and_latest_holdout tests/test_campaign_stages.py::test_first_fraction_stage_subset_uses_first_ninety_percent tests/test_campaign_stages.py::test_stage_subset_data_window_falls_back_to_core_data_subset -q` passed. A simulated POC config with only `core.data_subset` now resolves limited core/monkey to `2011-02-22` through `2012-09-06` and WFA to `2011-01-03` through `2024-11-22`.
## ES Prior LVN Orderflow Rejection - 2026-06-20

- Edge: prior-session approximate low-volume-node failed-auction rejection with aligned aggregate Sierra orderflow.
- Source artifacts: `campaigns/es_prior_lvn_orderflow_rejection/campaign.yaml` and `research_artifacts/es_prior_lvn_orderflow_rejection_density_audit_20260620.md`.
- Density: all five variants cleared 50 signals/year at the strict corner on full history and the seeded limited-core window.
- Originals: all five failed `limited_core_grid_test`. Best original was `morning_signed_two_sided_lvn_rejection/run1`, with profitable-combo rate `0.30864197530864196`, passing `12/81`, top net `3577.5`, PF `1.2357495881383855`, and MAR `1.4460835971947001`, still below the required `0.70` profitable-combo gate.
- Rescues: all five one-time parameter-space/fixed-parameter rescues completed and failed `limited_core_grid_test`. Best rescue was `morning_signed_two_sided_lvn_rejection/rescue1` by profitable-combo rate at `0.2839506172839506`; `morning_downside_signed_lvn_reclaim_long/rescue1` improved top net to `1827.5` but only `17/81` combinations were profitable.
- TP policy: no TP widening was applied because all targets were already at least `1.0R`; rescue TP grids remained `[1.0, 1.5, 2.0]`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, or frozen validation.


## ES Intraday Invariance Dislocation Reversion - 2026-06-20
- Edge tested: same-clock ranked intraday trading-invariance dislocation, fading completed 15-minute price movement when aggregate signed flow is not strongly aligned.
- Sources: Andersen, Bondarenko, Kyle, and Obizhaeva (2018) on E-mini S&P 500 intraday trading invariance; Kyle and Obizhaeva (2016) market microstructure invariance; Ane and Geman (2000) transaction-clock return behavior.
- Pre-PnL density audit: PASS after rejecting two sparse single-sided morning draft variants before any PnL testing; final five two-sided variants all exceeded 50 capped signals/year in full and limited-core windows.
- Original tests: five variants, 81 combinations each, all failed limited_core_grid_test with zero benchmark-passing combinations.
- Rescue tests: each failed variant received exactly one parameter-space-only rescue; entry module, data, costs, fills, sessions, and stage gates were unchanged; target_r_multiple remained >= 1.0R. All five rescues failed limited_core_grid_test.
- Decision: FAIL. Report: backtest-campaigns/es_intraday_invariance_dislocation_reversion/campaign_test_summary.json. No WFA, Monte Carlo, frozen validation, or candidate report was reached.

## 2026-06-20 - local no-duplicate edge inventory gate

- Active campaign inventory checked: 128 active ES campaign definitions, all with top-level summaries; all 128 decisions are FAIL.
- Footprint absorption/imbalance is not eligible as a fresh campaign because active `es_footprint_absorption_initiation` already tested diagonal bid/ask footprint absorption at AOIs, reran after the corrected footprint cache, and failed all five originals plus all five rescues before WFA.
- The remaining unused active entry modules were classified as duplicate, stale wrappers, or data-gated. `quote_liquidity_sweep_reversion` remains blocked without approved TBBO/quote/depth data.
- Artifact: `research_artifacts/local_no_duplicate_edge_inventory_gate_20260620.md`.
- Decision: FAIL for the current local-edge inventory. No new candidate strategy was promoted.

## 2026-06-20 - es_turn_of_month_orderflow_confirmation pre-campaign gate

- Evaluated a possible bounded composite using turn-of-month seasonality plus completed first-30-minute ES aggregate orderflow confirmation before any PnL inspection.
- Duplicate context: pure `es_turn_of_month_seasonality` already failed all original and one-time rescue variants. A composite would need a convincing calendar-flow mechanism and enough frequency without stretching the calendar window into a generic half-month filter.
- Density result: faithful calendar first/last 4-5 day windows and trading-day first 3 / last 1 or first/last 4 windows produced only `14.00` to `40.94` signals/year after weak completed-orderflow confirmation, below the 50/year feasibility rule.
- The only variants that cleared 50/year used first/last 6-7 trading days, which was rejected as overbroad and no longer a faithful turn-of-month expression.
- Artifact: `research_artifacts/es_turn_of_month_orderflow_confirmation_density_gate_20260620.md`.
- Decision: FAIL before campaign authoring. No variants, configs, PnL tests, rescues, or candidate reports were created.

## 2026-06-20 - es_sector_opening_breadth_orderflow_continuation

- Edge screened: same-day cash sector ETF opening breadth plus completed ES price movement and aggregate orderflow continuation.
- No paid data was downloaded. Sector features were built from existing local Yahoo ETF daily CSVs using raw same-day ETF `Open` and prior raw `Close`; ES confirmation used the local Sierra RTH aggregate orderflow cache.
- Feature builder added: `tools/build_es_sector_opening_breadth_features.py`; output: `data/external/es_sector_opening_breadth_features_20110103_20260609.csv`.
- Entry module added: `sector_opening_breadth_orderflow`; it uses only same-day ETF open features available after 09:30 ET and completed ES bars before the configured 10:00-12:30 ET signal timestamps. Entries remain next-bar.
- Pre-PnL density audit passed all five proposed variants at `50.50` to `115.84` full-sample signals/year and `61.74` to `129.98` limited-core signals/year. Artifact: `research_artifacts/es_sector_opening_breadth_orderflow_continuation_density_audit_20260620.md`.
- Exactly five original variants were authored with mechanics reviews before testing. Each grid used 81 combinations: two entry tunables, one stop tunable, one target tunable, and `target_r_multiple >= 1.0`.
- All five originals failed. All five failed variants received one logged parameter-space-only rescue that preserved setup modes, signal windows, modules, data, costs, sessions, validation gates, and target grid.
- Best original: `broad_up_early_signed_long_1000/run1`, limited-core profitable-combination rate `0.5679`, benchmark-passing combinations `4/81`.
- Best rescue: `broad_up_early_signed_long_1000/rescue1`, limited-core profitable-combination rate `1.0`; it passed limited monkey/trade-path stress but failed WFA because window 2 had no in-sample row satisfying the selection filter. No run reached Monte Carlo or validation.
- Fixed-config core trade logs and equity curves were written for all 10 original/rescue runs.
- Campaign summary: `backtest-campaigns/es_sector_opening_breadth_orderflow_continuation/campaign_test_summary.json`.
- Decision: FAIL. No candidate strategy report was created.

## 2026-06-20 - es_credit_etf_orderflow_risk_appetite

- Edge screened: lagged HYG high-yield ETF return-state as a tradable credit-risk appetite proxy, gated by completed ES RTH price movement and aggregate signed orderflow confirmation.
- No paid data was downloaded. HYG and LQD daily histories came from the free Yahoo chart endpoint; SPY came from the existing local Yahoo cache; ES used the local Sierra aggregate-orderflow cache.
- Feature builder added: `tools/build_es_credit_etf_features.py`; output: `data/external/es_credit_etf_risk_appetite_features_20110103_20260609.csv`.
- Entry module added: `credit_etf_orderflow_state`. It maps each ES session only to ETF daily closes strictly before that session date, uses rolling ranks computed from prior observations, and waits for completed ES bars before next-bar entry.
- Pre-PnL density audit rejected sparse HYG-LQD, HYG-SPY, large10, and large20 drafts. The final five variants all cleared the 50/year feasibility rule using HYG 1-day, 3-day, or 5-day return-state plus signed-flow confirmation. Artifact: `research_artifacts/es_credit_etf_orderflow_risk_appetite_density_audit_20260620.md`.
- Exactly five original variants were authored with detailed mechanics reviews before testing. Each grid used 81 combinations with two entry tunables, one stop tunable, one target tunable, and `target_r_multiple >= 1.0`.
- All five original variants failed `limited_core_grid_test`. Best original was `hyg_5d_two_sided_signed_1230/run1`, with profitable-combo rate `0.38271604938271603`, benchmark-passing combinations `20/81`, top net `5110.0`, PF `1.310769883237242`, MAR `2.061847420417271`, and trades/year `95.8216178751774`, still below the required `0.70` profitable-combo gate.
- All five failed variants received exactly one parameter-space-only rescue under `campaigns/es_credit_etf_orderflow_risk_appetite/rescue_attempts/parameter_space_rescue_1/`. The rescue preserved setup modes, entry/stop/target modules, timeframe, data, costs, sessions, fills, validation gates, and target grid. TP was not adjusted because every target already satisfied the `1.0R` floor.
- Best rescue by limited-core result was `hyg_5d_two_sided_signed_1230/rescue1`, with profitable-combo rate `0.8765432098765432`, benchmark-passing combinations `54/81`, top net `6447.5`, PF `1.369696100917431`, MAR `2.7739748230950885`, and trades/year `95.8216178751774`. It failed `limited_monkey_test` because max-drawdown robustness was `0.8766666666666667` versus the `0.90` threshold; one-tick-worse net profit was `-405.0`.
- Deepest progressing rescue was `hyg_3d_two_sided_signed_1230/rescue1`. It passed limited core and limited monkey, then failed WFA. Stitched OOS metrics were PF `1.077365644773513`, MAR `0.08981641818942494`, trades/year `68.54306003101846`, net profit `16170.0`, and total trades `676`, below the WFA PF >= `1.2` and MAR >= `0.4` gates.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_credit_etf_orderflow_risk_appetite/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Decision: FAIL. No run reached Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-20 - es_spy_turnover_orderflow_attention

- Edge screened: prior-day SPY abnormal volume / return-volume attention state plus completed same-day ES price movement and aggregate signed-orderflow continuation.
- No paid data was downloaded. SPY daily adjusted close and volume came from the existing local free Yahoo CSV; ES used the local Sierra aggregate-orderflow cache.
- Feature builder added: `tools/build_es_spy_turnover_features.py`; output: `data/external/es_spy_turnover_attention_features_20110103_20260609.csv`.
- Entry module added: `spy_turnover_orderflow_attention`. It maps each ES session only to SPY daily close/volume observations strictly before that session date, uses rolling ranks computed from prior observations, and waits for completed ES 5-minute bars before next-bar entry.
- Pre-PnL density audit rejected morning-only, midday-only, single-time, and stricter signed-flow drafts when full-history density fell below 50 signals/year. The final five full-day variants cleared the density rule at the fixed review settings with about `55.02` to `57.16` signals/year full-sample and `54.59` to `63.69` signals/year in the limited-core reference window. Artifact: `research_artifacts/es_spy_turnover_orderflow_attention_density_audit_20260620.md`.
- Exactly five original variants were authored with detailed mechanics reviews before testing. Each grid used 81 combinations with two entry tunables, one stop tunable, one target tunable, and `target_r_multiple >= 1.0`.
- All five original variants failed `limited_core_grid_test`. Best original was `spy_5d_volume_attention_continuation_1530/run1`, with profitable-combo rate `0.38271604938271603`, benchmark-passing combinations `13/81`, top net `2355.0`, PF `1.1702204553668232`, MAR `0.5894761822531764`, and trades/year `67.9285940478482`, still below the required `0.70` profitable-combo gate.
- All five failed variants received exactly one parameter-space-only rescue under `campaigns/es_spy_turnover_orderflow_attention/rescue_attempts/parameter_space_rescue_1/`. The rescue preserved setup modes, entry/stop/target modules, signal schedule, timeframe, data, costs, sessions, fills, and validation gates. TP was not adjusted because every target already satisfied the `1.0R` floor.
- Best rescue by limited-core result was `spy_3d_absret_attention_continuation_1530/rescue1`, with profitable-combo rate `0.9629629629629629`, benchmark-passing combinations `63/81`, top net `4900.0`, PF `1.330522765598651`, MAR `2.7292390054229503`, and trades/year `78.77600724132766`. It passed limited monkey/stress but failed WFA by early exit: stitched PF `0.9450324342779105`, MAR `-0.16161731136310653`, trades/year `52.17242192103712`, net profit `-805.0`, and negative expectancy.
- `spy_5d_volume_attention_continuation_1530/rescue1` also passed limited core but failed `limited_monkey_test`; max-drawdown robustness was `0.86` versus the `0.90` threshold and the one-tick-worse run had net profit `-560.0`.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_spy_turnover_orderflow_attention/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Decision: FAIL. No run reached WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-20 - es_treasury_rate_orderflow_confirmation campaign failure

- Authored exactly five Treasury-rate plus ES aggregate-orderflow confirmation variants using the existing local Treasury feature file and Sierra RTH orderflow cache; no paid data was downloaded.
- All original and rescue configs used `target_r_multiple >= 1.0`; TP was not adjusted because the user correction allows only flooring sub-1R targets, not widening already-valid targets.
- All five originals failed `limited_core_grid_test`; all five failed variants received exactly one parameter-space-only rescue under `campaigns/es_treasury_rate_orderflow_confirmation/rescue_attempts/parameter_space_rescue_1/`.
- All five rescues also failed `limited_core_grid_test`; best rescue `curve_1d_signed_rate_confirmation_1530/rescue1` had profitable-combo rate `0.0` with `0/81` benchmark-passing combinations, so it remained below the `0.70` profitable-combo gate.
- Fixed-config core trade logs and equity curves were written for all ten runs. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. Decision: FAIL.

## 2026-06-20 - es_impulse_pause_orderflow_continuation campaign failure

- Authored a price-action plus aggregate-orderflow campaign with exactly five active variants after a pre-PnL density reformulation. The rejected draft `morning_signed_long_impulse_pause_breakout_1130` was moved under `campaigns/es_impulse_pause_orderflow_continuation/rejected_pre_pnl_density/` because its strict limited-core density was below 50 signals/year before any PnL was inspected.
- Active variants passed preflight and density: the limited-core random 10% period was 2011-02-22 to 2012-09-06; the lowest active strict-corner density was above 50 signals/year. Density artifact: `research_artifacts/es_impulse_pause_orderflow_continuation_density_audit_20260620.md`.
- TP correction enforced: every original and rescue config kept `target_r_multiple >= 1.0`; the rescue attempt did not widen TP because all active configs already satisfied the 1.0R floor.
- Results: all five originals and all five per-variant parameter-space rescues failed `limited_core_grid_test` with 0 profitable combinations after costs. No variant reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
- Fixed-config core trade logs were written for all 10 runs at `backtest-campaigns/es_impulse_pause_orderflow_continuation/*/ES/*/limited_core_grid_test/fixed_config_core_trade_log.csv`.
- Decision: FAIL. Report: `backtest-campaigns/es_impulse_pause_orderflow_continuation/campaign_test_summary.json`.

## 2026-06-20 - es_import_export_price_pressure campaign failure

- Authored `campaigns/es_import_export_price_pressure/campaign.yaml` and exactly five variants using lagged free public FRED/BLS import/export price-index features plus local Sierra ES RTH aggregate orderflow. No paid data was downloaded.
- Feature builder: `tools/build_es_import_export_price_pressure_features.py`. Feature file: `data/external/es_import_export_price_pressure_features_20110103_20260609.csv`. The availability rule is conservative: monthly observation date plus 51 calendar days.
- Pre-PnL density audit: `research_artifacts/es_import_export_price_pressure_density_audit_20260620.md`. Export-demand longs, broad import-pressure shorts, and core-relief pullback longs were rejected before PnL because they failed the 50 trades/year density gate in at least one required reference window.
- Active variants used fixed macro thresholds before testing: import-disinflation longs at `import_all_mom3_rank_120m <= 0.45`, core-pressure shorts at `core_vs_headline_rank_120m >= 0.45` for signed flow and `>= 0.40` for noon large20 flow. Each grid had 27 combinations: `entry.params.min_session_return_bps` x `sl.params.stop_pct` x `tp.params.target_r_multiple`.
- Verification before staging: `PYTHONPATH=src:. python3 -m pytest tests/test_import_export_price_pressure.py tests/test_preflight.py::test_preflight_rejects_target_r_multiple_below_one tests/test_core_grid.py::test_parameter_combinations_rejects_target_r_multiple_below_one tests/test_backtest_engine.py::test_backtest_engine_rejects_target_r_multiple_below_one tests/test_strategy_modules.py::test_fixed_r_target_rejects_reward_risk_below_one tests/test_strategy_modules.py::test_cost_adjusted_fixed_r_target_rejects_reward_risk_below_one tests/test_strategy_modules.py::test_signal_fixed_r_target_rejects_signal_reward_risk_below_one -q` passed. Original and rescue configs passed `python3 -m research.preflight --skip-tests`.
- Original results: all five originals failed `limited_core_grid_test`. The strongest original was `import_disinflation_large20_long_1200/run1` with profitable-combo rate `0.3333333333333333`, `3/27` benchmark-passing combinations, top net `1285.0`, PF `1.1513991163475699`, MAR `0.46342591529032295`, and trades/year `84.54790066400578`; it still failed the `0.70` profitable-combo gate.
- Rescue results: each failed variant received exactly one parameter-space-only rescue under `campaigns/es_import_export_price_pressure/rescue_attempts/parameter_space_rescue_1/`. Rescue preserved entry mechanics, macro thresholds, signal time, flow column, TP grid, data, costs, sessions, and validation gates; it only widened `sl.params.stop_pct` to `[0.004, 0.006, 0.008]`. TP was not adjusted because every `target_r_multiple` was already at least `1.0R`.
- Best rescue: `import_disinflation_large20_long_1200/rescue1` passed `limited_core_grid_test` with profitable-combo rate `0.9259259259259259` and `13/27` benchmark-passing combinations, but failed `limited_monkey_test`; net-profit beat rate was `0.9066666666666666`, while max-drawdown beat rate was only `0.49333333333333335` versus the `0.90` requirement.
- No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_import_export_price_pressure/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Decision: FAIL. No `candidate_strategy_report.md` was created.

## 2026-06-20 - pre-campaign density rejections

- Rejected corporate buyback blackout/resumption before campaign authoring. The screen used deterministic quarter-end blackout/resumption windows plus completed ES price/orderflow confirmation. No screened shape reached 50 trades/year across full, limited-core, WFA90, and latest-year reference windows. Artifact: `research_artifacts/es_buyback_blackout_orderflow_density_screen_20260620.csv`.
- Rejected real-yield/breakeven decomposition before campaign authoring. Free public FRED `DFII10`, `T10YIE`, and `DGS10` data were cached and mapped with strict prior-observation availability; no paid data was downloaded. No screened real-yield or breakeven shape reached 50 trades/year across the required reference windows. Feature file: `data/external/es_real_yield_breakeven_features_20110103_20260609.csv`. Screen artifact: `research_artifacts/es_real_yield_breakeven_orderflow_density_screen_20260620.csv`.
- Consolidated pre-campaign rejection note: `research_artifacts/pre_campaign_density_rejections_20260620.md`.
- `research_ledger.csv` was updated with both pre-campaign density rejections so these edges are not recycled as active campaign candidates under the current trade-count rule.

## 2026-06-20 - es_market_structure_pivot_trend_bias

- Created and tested a standalone completed swing-pivot market-structure campaign using `market_structure_pivot_continuation`. The implementation confirms pivots only after right-side bars complete and uses next-bar execution. No paid data was downloaded.
- The first fixed-time draft and the 10:00-12:00 morning window were rejected before PnL for insufficient density. Final density artifact: `research_artifacts/es_market_structure_pivot_trend_bias_density_audit_20260620.md`; all active variants cleared 50 trades/year at fixed review settings.
- Verification passed: `PYTHONPATH=src:. python3 -m pytest tests/test_market_structure_pivot.py` and targeted preflight for five originals/five rescues.
- Result: FAIL. All five originals and all five one-time parameter-space rescues failed `limited_core_grid_test`; no branch reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## 2026-06-20 - es_pivot_filtered_mes_participation_crowding_reversion

- Authored a composite campaign combining the primary MES participation crowding reversion edge with a fixed completed swing-pivot market-structure direction filter. No paid data was downloaded; the campaign used the local `data/cache/orderflow/es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny.csv` cache.
- Added default-preserving engine support for this campaign: `mes_participation_crowding` now supports `signal_mode: first_signal_in_window`, and the market-structure pivot helper now supports `carry_pivots_across_sessions: true` for last completed pivot-pattern bias. Defaults preserve prior fixed-time and per-session behavior unless configs opt in.
- Verification passed: `PYTHONPATH=src:. python3 -m pytest tests/test_es_mes_participation.py tests/test_market_structure_pivot.py -q`; targeted preflight passed for five originals and five rescues. All active configs kept `target_r_multiple >= 1.0`.
- Pre-PnL density rejected the initial fixed-time composite because best declared-grid density stayed below 50 trades/year. The active five window-based variants passed fixed-config and grid-density screens across full, limited-core random 10%, WFA first 90%, and latest-year reference windows. Artifact: `research_artifacts/es_pivot_filtered_mes_participation_crowding_reversion_density_audit_20260620.md`.
- Original results: four variants failed `limited_core_grid_test`. The afternoon two-sided trade-share variant passed limited core with profitable-combo rate `0.8641975308641975` and zero apex violations, but failed `limited_monkey_test`; net-profit beat rate was `0.8666666666666667` versus the `0.90` gate.
- Rescue results: every failed variant received exactly one stop-widen parameter-only rescue under `campaigns/es_pivot_filtered_mes_participation_crowding_reversion/rescue_attempts/stop_widen_rescue_1/`. Entry mechanics, windows, pivot filter, target grid, data, costs, sessions, and gates were unchanged. Four rescues failed limited core. The afternoon rescue passed limited core with profitable-combo rate `0.9876543209876543`, then failed limited monkey because max-drawdown beat rate was `0.82` versus the `0.90` gate.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_pivot_filtered_mes_participation_crowding_reversion/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Decision: FAIL. No run reached WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-20 - es_pivot_filtered_vwap_pullback_continuation

- Authored a composite campaign combining VWAP pullback/failed-break continuation with a fixed completed 5/15-minute swing-pivot market-structure direction filter. No paid data was downloaded; the campaign used the local Sierra ES RTH aggregate-orderflow/OHLCV cache.
- The strict 2-of-2 pivot-alignment draft was rejected before PnL for insufficient density. The active five variants used a fixed 1-of-2/no-opposition pivot filter and cleared full, limited-core, WFA90, and latest-year density screens. Artifact: `research_artifacts/es_pivot_filtered_vwap_pullback_continuation_density_audit_20260620.md`.
- Verification passed before rescue runs: `PYTHONPATH=src:. python3 -m research.preflight --skip-tests` for five rescue configs, and `PYTHONPATH=src:. python3 -m pytest tests/test_market_structure_pivot.py tests/test_strategy_modules.py::test_fixed_r_target_rejects_reward_risk_below_one tests/test_core_grid.py::test_parameter_combinations_rejects_target_r_multiple_below_one tests/test_preflight.py::test_preflight_rejects_target_r_multiple_below_one -q`.
- Original results: all five originals failed `limited_core_grid_test`. Best original was `failed_vwap_break_two_sided_1500/run1` with profitable-combo rate `0.05555555555555555`, benchmark-passing combinations `0/54`, top net `456.25`, PF `1.3732106339468302`, MAR `1.1274897977432308`, and trades/year `19.02619013167414`, still below both trade-count and 70% profitable-combo gates.
- Rescue results: every failed variant received exactly one stop-widen parameter-only rescue under `campaigns/es_pivot_filtered_vwap_pullback_continuation/rescue_attempts/stop_widen_rescue_1/`. Entry mechanics, VWAP setup modes, signal windows, pivot filter, target grid, data, costs, sessions, and gates were unchanged. All five rescues also failed `limited_core_grid_test`; best rescue was `failed_vwap_break_two_sided_1500/stop_widen_rescue1` with profitable-combo rate `0.16666666666666666` and `0/54` benchmark-passing combinations.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_pivot_filtered_vwap_pullback_continuation/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-20 - es_pivot_filtered_prior_value_area_acceptance

- Authored a composite campaign combining prior-session value-area acceptance, same-direction aggregate orderflow confirmation, and a fixed completed 5/15-minute swing-pivot market-structure direction filter. No paid data was downloaded; ES used the local Sierra RTH aggregate-orderflow/OHLCV cache.
- The strict 2-of-2 pivot-alignment draft was rejected before PnL after the first morning variants showed only about 12-29 signals/year at the limiting windows. The active five variants used a fixed 1-of-2/no-opposition pivot filter, with carried prior-session pivots enabled. A narrow short-only draft was also rejected before PnL for sub-50/year density and replaced by a broader morning signed two-sided value-acceptance variant.
- Final pre-PnL density passed for all five active variants and all nine entry-parameter combinations across full history, limited-core, WFA90, and latest-year windows. Minimum limiting rates ranged from `61.09` to `129.98` signals/year. Artifact: `research_artifacts/es_pivot_filtered_prior_value_area_acceptance_density_audit_20260620.md`.
- Verification passed: targeted preflight for five originals/five rescues and `PYTHONPATH=src:. python3 -m pytest tests/test_market_structure_pivot.py tests/test_strategy_modules.py::test_fixed_r_target_rejects_reward_risk_below_one tests/test_core_grid.py::test_parameter_combinations_rejects_target_r_multiple_below_one tests/test_preflight.py::test_preflight_rejects_target_r_multiple_below_one -q`. All target grids kept `target_r_multiple >= 1.0`.
- Original results: all five originals failed `limited_core_grid_test`. Best original was `morning_signed_vah_pivot_acceptance_long/run1` with profitable-combo rate `0.5185185185185185`, `18/54` benchmark-passing combinations, top net `2500.0`, PF `1.277623542476402`, MAR `0.7504405175421055`, and trades/year `53.420681774900025`, below the required `0.70` profitable-combo gate.
- Rescue results: every failed variant received exactly one stop-widen parameter-only rescue under `campaigns/es_pivot_filtered_prior_value_area_acceptance/rescue_attempts/stop_widen_rescue_1/`. Entry mechanics, value-area approximation, orderflow condition, signal windows, fixed pivot filter, target grid, data, costs, sessions, and gates were unchanged. All rescues failed `limited_core_grid_test`; best rescue was `morning_signed_vah_pivot_acceptance_long/stop_widen_rescue1` with profitable-combo rate `0.6111111111111112` and `21/54` benchmark-passing combinations.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_pivot_filtered_prior_value_area_acceptance/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-20 - es_pivot_filtered_spx_0dte_pressure density rejection

- Screened the queued SPX 0DTE expiration-pressure plus completed pivot-bias composite before authoring a campaign. No paid data was downloaded; the screen used the local Sierra ES cache and local deterministic SPX 0DTE calendar file.
- Strict 2-of-2 pivot alignment failed the trade-count rule, with limiting signal rates mostly below 10-42/year depending on variant and threshold.
- The looser fixed 1-of-2/no-opposition pivot filter also failed density. Most fade variants had minimum limiting rates around `14.42` to `26.09` signals/year. The late continuation variant had two settings above 50/year, but its strictest declared entry threshold had only `46.81` signals/year in WFA90, so the full declared parameter space was not viable.
- Artifact: `research_artifacts/es_pivot_filtered_spx_0dte_pressure_density_audit_20260620.md`.
- Decision: FAIL at pre-PnL density gate. No campaign source tree, staged backtest, rescue, WFA, Monte Carlo, or candidate report was created.

## 2026-06-20 - es_pivot_filtered_opening_range_orderflow_breakout density rejection

- Screened the queued opening-range/orderflow breakout plus completed 5/15-minute swing-pivot market-structure direction-filter composite before authoring a campaign. No paid data was downloaded; the screen used the local Sierra ES aggregate-orderflow/OHLCV cache.
- Superseded note: after the user explicitly requested the pivot-structure idea be tested and combined with other campaigns, this branch was subsequently authored and staged as `es_pivot_filtered_opening_range_orderflow_breakout`. The staged result below is now the controlling evidence for this branch.
- Strict 2-of-2 pivot alignment failed the trade-count rule for all five candidate ORB variants. The limiting rates were roughly `8.01` to `28.02` signals/year depending on variant and reference window.
- The looser fixed 1-of-2/no-opposition pivot filter also failed the exact-five-variant requirement. Only `or15_large10_flow_breakout_1030` kept all nine declared entry parameter corners above 50 signals/year across full history, limited-core random 10%, WFA90, and latest-year windows. The other four variants had one or more declared entry corners below the density gate.
- Artifact: `research_artifacts/es_pivot_filtered_opening_range_orderflow_breakout_density_audit_20260620.md`.
- Decision: FAIL at pre-PnL density gate. No campaign source tree, staged backtest, rescue, WFA, Monte Carlo, or candidate report was created.

## 2026-06-20 - es_pivot_filtered_opening_range_orderflow_breakout staged follow-up

- Authored a composite campaign combining opening-range orderflow breakout with a fixed completed swing-pivot market-structure direction filter. No paid data was downloaded; ES used the local Sierra RTH aggregate-orderflow/OHLCV cache.
- The tested variants were `or15_signed_pivot_flow_breakout_1030`, `or15_large10_pivot_flow_breakout_1030`, `or30_signed_pivot_flow_breakout_1100`, `or30_large20_pivot_flow_breakout_1100`, and `or60_signed_pivot_flow_breakout_1200`.
- Verification passed: `python3 -m pytest tests/test_market_structure_pivot.py -q`; five generated configs and five rescue configs had 54 or 81 combinations, exactly two entry tunables, one stop tunable, one target tunable, and all `target_r_multiple >= 1.0`.
- Original results: all five originals failed `limited_core_grid_test`. Best original was `or60_signed_pivot_flow_breakout_1200/run1` with profitable-combo rate `0.3333333333333333`, `0/54` benchmark-passing combinations, top net `1696.25`, PF `1.52152190622598`, and trades/year `21.130714810327618`; it failed trade-count and concentration gates.
- Rescue results: every failed variant received exactly one parameter-space rescue under `campaigns/es_pivot_filtered_opening_range_orderflow_breakout/rescue_attempts/parameter_space_rescue_1/`. Entry wrapper, base ORB module, fixed pivot filter, stop module, target module, data, costs, sessions, fills, and gates were unchanged. All five rescues failed `limited_core_grid_test`; best rescue was `or15_large10_pivot_flow_breakout_1030/rescue1` with profitable-combo rate `0.48148148148148145`, `0/81` benchmark-passing combinations, top net `1550.0`, and PF `1.116600790513834`.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_pivot_filtered_opening_range_orderflow_breakout/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.


## 2026-06-20 - es_nq_semivariance_filtered_relative_value_absorption

- Authored a bounded composite campaign combining ES/NQ relative-value reversion, completed ES signed-flow absorption, and a lagged prior-session realized-semivariance regime filter. No external or paid data was downloaded; the campaign used `data/cache/orderflow/es_nq_lead_lag_1m_20110103_20260609_full_rth_ny.parquet` and `data/external/es_realized_semivariance_features_20110103_20260609.csv`.
- Added entry module `src/propstack/strategy_modules/entry/es_nq_semivariance_filtered_relative_value_absorption.py` and focused tests in `tests/test_es_nq_semivariance_filtered_relative_value_absorption.py`. Verification passed with `PYTHONPATH=src:. python3 -m pytest tests/test_es_nq_semivariance_filtered_relative_value_absorption.py -q`; targeted preflight passed for five originals and five rescues.
- Pre-PnL density artifact: `research_artifacts/es_nq_semivariance_filtered_relative_value_absorption_density_audit_20260620.md`. The initial fifth variant was reformulated before PnL because one strict latest-year corner had 49.03 trades/year; the final five variants all cleared the density floor.
- Original results: all five originals failed `limited_core_grid_test` with `0/36` profitable combinations. Best original was `midday60_low_badvol_absorption_twosided_1430/run1` with top net `-1080.0`, PF `0.8156209987195903`, MAR `-0.36045429370210624`, and trades/year `66.60269264219863`.
- Rescue results: every failed variant received exactly one parameter-space/fixed-parameter rescue under `campaigns/es_nq_semivariance_filtered_relative_value_absorption/rescue_attempts/parameter_space_rescue_1/`. Entry/stop/target modules, data, costs, sessions, and gates were unchanged; target RR stayed in `[1.0, 1.5]`. All five rescues failed `limited_core_grid_test`; best rescue was `midday60_low_badvol_absorption_twosided_1430/rescue1` with top net `-72.5`, PF `0.986346516007533`, MAR `-0.025652768973958504`, and trades/year `63.67492454360885`.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_nq_semivariance_filtered_relative_value_absorption/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Decision: FAIL. No run reached monkey, WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.

## 2026-06-20 - es_high_semivariance_mes_trend_pullback_crowding

- Authored and tested a bounded composite campaign combining MES participation crowding, completed ES trend-pullback structure, and a lagged prior-session downside-semivariance regime filter. No paid data was downloaded; the campaign used `data/cache/orderflow/es_mes_participation_crowding_1m_20190506_20260609_full_rth_ny.csv` and `data/external/es_realized_semivariance_features_20110103_20260609.csv`.
- Added entry module `src/propstack/strategy_modules/entry/semivariance_filtered_trend_mes_participation_crowding.py` and focused tests in `tests/test_semivariance_filtered_trend_mes_participation_crowding.py`. Verification passed with targeted tests and preflight for five originals and five rescues.
- Fixed-time high-semivariance variants were rejected before PnL for insufficient density. The tested windowed first-signal variants cleared the 50 trades/year density screen across full history, limited-core, WFA90, and latest-year windows. Density artifact: `research_artifacts/es_high_semivariance_mes_trend_pullback_crowding_density_audit_20260620.md`.
- Original results: all five originals failed `limited_core_grid_test`. Best original was `midday60_notional_high_downside_window_1430/run1` with profitable-combo rate `0.14814814814814814`, `4/54` benchmark-passing combinations, top net `6772.5`, PF `1.1705275084980487`, MAR `1.6069036998484771`, and trades/year `147.227996812312`.
- Rescue results: every failed variant received exactly one stop/target-widen parameter-only rescue under `campaigns/es_high_semivariance_mes_trend_pullback_crowding/rescue_attempts/stop_target_widen_rescue_1/`. Entry mechanics, MES participation feature, prior ES trend-pullback condition, high-semivariance filter, data, costs, sessions, and gates were unchanged; target RR stayed at or above `1.5`.
- Three rescues failed `limited_core_grid_test`. The `midday60_notional_high_downside_window_1430` and `afternoon60_notional_high_downside_window_1530` rescues passed limited core with profitable-combo rate `0.8888888888888888`, but both failed `limited_monkey_test`. The best rescue was `afternoon60_notional_high_downside_window_1530/stop_target_widen_rescue1`, with limited-monkey net-profit beat rate `0.8733333333333333` and max-drawdown beat rate `0.76` versus the `0.90` gate.
- Fixed-config core trade logs and equity curves were written for all five originals and all five rescues.
- Aggregate artifacts: `backtest-campaigns/es_high_semivariance_mes_trend_pullback_crowding/campaign_test_summary.json`, `campaign_test_summary.md`, `campaign_results.csv`, `trade_logs_manifest.csv`, `equity_curves_manifest.csv`, `wfa_table.csv`, and `monte_carlo_summary.csv`.
- Decision: FAIL. No run reached WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting. No `candidate_strategy_report.md` was created.
