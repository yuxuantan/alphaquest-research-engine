# Manual Due Diligence Checklist

Audit date: 2026-06-15

Status: FAIL - no ES candidate strategy passed the staged methodology in this run.

## Gate Before Chart Review

- Confirm `methodology_audit.md` final decision is PASS.
- Confirm `campaign_test_summary.json` has `passed=true`.
- Confirm the strategy has a `candidate_strategy_report.md`.
- Confirm final acceptance OOS PF, MAR, expectancy, trade count, and Apex-rule checks passed.
- Confirm random-placebo monkey paths and actual-trade perturbation stress paths are each at least 80% profitable with positive median net profit, and confirm the one-tick-worse slippage path remains profitable.

Current result: do not proceed. The active `es_mes_micro_flow_divergence_reversion`, `es_prior_session_ibs_reversion`, `es_connors_rsi2_mean_reversion`, `es_range_compression_breakout`, `es_rth_intraday_risk_premium`, `es_overnight_intraday_reversal`, `es_signed_orderflow_persistence`, `es_opening_drive_inventory_absorption`, `es_turn_of_month_seasonality`, `es_daily_time_series_momentum`, `es_late_day_intraday_momentum`, `es_volume_shock_liquidity_reversal`, `es_prior_day_stop_run_reclaim`, `es_vwap_pullback_continuation`, `es_cftc_tff_hedging_pressure`, `es_market_plumbing_liquidity_capacity`, and `es_bankruptcy_distress_regime_reversion` campaigns failed before WFA completion, and all active failed variants have consumed their one allowed rescue without passing.

Current continuation gate: archived tests are ignored when checking duplicate edges. The next campaign must avoid the currently active rejected edge families, but it is not blocked solely because a similar archived test exists. The retained external-data branches still require approval for longer ES+MES `trades` history or a bounded ES `tbbo` liquidity-sweep pilot. No paid data was pulled in this run.

Supporting audit: `research_artifacts/local_no_duplicate_data_gate_audit_20260615.md`.

## Required If A Future Candidate Passes

- Review every WFA OOS and acceptance trade on a chart with timestamp, setup bar, entry bar, stop, target, and flatten time visible.
- Verify no entry uses information unavailable at signal time.
- Check all stop/target same-bar conflicts and confirm pessimistic handling or detail-data resolution.
- Check trade distribution by year, month, session time, and side.
- Check largest winning day/trade contribution and remove any candidate dominated by one event.
- Check prop-rule logs for latest-entry, forced-flatten, no-overnight, and drawdown compliance.
- Paper/incubate only after manual review; do not treat any backtest pass as ready to trade.


2026-06-16 update: `es_market_plumbing_liquidity_capacity` also failed before WFA after all five variants consumed exactly one rescue. Do not proceed to chart review.


2026-06-16 update: `es_bankruptcy_distress_regime_reversion` also failed before WFA after all five variants consumed exactly one rescue. Do not proceed to chart review.


2026-06-16 update: `es_prior_session_level_breakout_continuation` also failed before WFA after all five variants consumed exactly one rescue. Do not proceed to chart review.


2026-06-16 update: `es_vpin_toxicity_continuation` also failed before WFA after all five variants consumed exactly one rescue. Do not proceed to chart review.


2026-06-16 update: `es_overnight_return_late_day_momentum` also failed at core after all five variants consumed exactly one rescue. Do not proceed to chart review.


2026-06-16 update: `es_prior_level_delta_dislocation` also failed at core after all five variants consumed exactly one rescue. Do not proceed to chart review.


2026-06-16 update: `es_orderflow_absorption_exhaustion_reversal` also failed before WFA after all five variants consumed exactly one rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 110 source variants, 110 one-time rescues, 238 raw variant-level reports, 0 passes, and no active variants missing `rescue1`. No candidate strategy report exists, so manual chart review / paper incubation is not authorized for any active campaign.

2026-06-16 update: `es_day_of_week_seasonality` also failed at core after all five variants consumed exactly one stop/target parameter-space rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 115 source variants, 115 one-time rescues, 248 raw variant-level reports, 0 passes, and no active variants missing `rescue1`. No candidate strategy report exists.


2026-06-16 update: `es_overnight_inventory_sweep_reversion` also failed before WFA after all five variants consumed exactly one parameter-space rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 24 campaigns, 120 source variants, 120 one-time rescues, 258 raw variant-level reports, 0 passes, and no active variants missing a latest original or `rescue1`. No candidate strategy report exists.

2026-06-16 active-only recheck: remaining unused local modules were not launched because they map to active rejected edge families or require missing external caches. Archived tests were ignored for this decision. No manual chart review or paper incubation is authorized.

2026-06-16 update: `es_nq_cross_index_lead_lag` also failed at core after all five variants consumed exactly one parameter-space rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 25 campaigns, 125 source variants, 125 one-time rescues, 268 raw variant-level reports, 0 passes, and no active variants missing a latest original or `rescue1`. No candidate strategy report exists.

2026-06-16 update: `es_fomc_pre_announcement_drift` also failed before WFA after all five variants consumed exactly one parameter-space/fixed-parameter rescue. The only core-surviving rescue failed monkey and one-tick-worse stress. Do not proceed to chart review.

2026-06-16 verification: active sweep found 26 campaigns, 130 source variants, 130 one-time rescues, 278 raw variant-level reports, 0 passes, and no active variants missing a latest original or `rescue1`. No candidate strategy report exists.

2026-06-16 update: `es_volatility_managed_intraday_premium` also failed before WFA after all five variants consumed exactly one parameter-space/fixed-parameter rescue. The only core-surviving rescue failed the random-placebo monkey gate. Do not proceed to chart review.

2026-06-16 verification: active sweep found 27 campaigns, 135 source variants, 135 one-time rescues, 288 raw variant-level reports, 0 passes, and no active variants missing a latest original or `rescue1`. No candidate strategy report exists.

2026-06-16 update: `es_halloween_seasonal_premium` also failed at core after all five variants consumed exactly one stop/target rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 28 campaigns, 140 source variants, 140 one-time rescues, 298 raw variant-level reports, 0 passes, and no active variants missing a latest original or `rescue1`. No candidate strategy report exists.

2026-06-16 update: `es_quarterly_expiration_pressure` also failed before WFA after all five variants consumed exactly one stop/target rescue. The only core-surviving rescue failed the random-placebo monkey gate. Do not proceed to chart review.

2026-06-16 verification: active sweep found 29 campaigns, 145 source variants, 145 one-time rescues, 308 raw variant-level reports, 0 passes, and no active variants missing a latest original or `rescue1`. No candidate strategy report exists.

2026-06-16 update: `es_preholiday_effect` also failed at core after all five variants consumed exactly one parameter-space/fixed-parameter rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 30 campaigns, 150 source variants, 150 one-time rescues, 318 raw variant-level reports, 0 passes, and no active variants missing a latest original or `rescue1`. No candidate strategy report exists.

2026-06-16 update: `es_turn_of_year_effect` also failed at core after all five variants consumed exactly one parameter-space/fixed-parameter rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 31 campaigns, 155 source variants, 155 one-time rescues, 328 raw variant-level reports, 0 passes, and no active variants missing a latest original or `rescue1`. No candidate strategy report exists.

2026-06-16 update: `es_bls_macro_release_day_drift` also failed at core after all five variants consumed exactly one parameter-space/fixed-parameter rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 32 campaigns, 160 source variants, 160 one-time rescues, 338 raw variant-level reports, 0 passes, and no active variants missing a latest original or `rescue1`. No candidate strategy report exists.

2026-06-16 update: `es_term_structure_lead_lag_feedback` also failed at core after all five variants consumed exactly one parameter-space rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 33 campaigns, 165 source variants, 165 one-time rescues, 348 raw variant-level reports, 0 passes, and no active variants missing any original run or `rescue1`. No candidate strategy report exists.

2026-06-16 update: `es_monthly_opex_pressure` also failed at core after all five variants consumed exactly one stop/target parameter-space rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 34 campaigns, 170 source variants, 170 one-time rescues, 358 raw variant-level reports, 0 passes, and no active variants missing any original run or `rescue1`. No candidate strategy report exists.

2026-06-16 update: `es_vix_expiration_pressure` also failed at core after all five variants consumed exactly one stop/target parameter-space rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 35 campaigns, 175 source variants, 175 one-time rescues, 368 raw variant-level reports, 0 passes, and no active variants missing any original run or `rescue1`. No candidate strategy report exists.
