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

Paid data rule: never run a non-dry-run paid vendor download unless the user explicitly approves the exact pull. Databento trade downloads are now guarded by `--paid-data-approved`; metadata/cost dry runs remain allowed.

Data-source rule: the 2026-06-16 Databento-vs-Sierra ES audit
(`research_artifacts/databento_sierra_es_trades_discrepancy_20260616.md`)
supports validated Sierra caches for completed-bar OHLCV and aggregate
signed-volume research, but not for print-level sequencing, trade-count,
trade-fragmentation, or large-print features. Any future candidate using those
fields from Sierra SCID-derived caches needs independent print-source
verification or must be marked `NEEDS MANUAL REVIEW`. The stopped Databento
daily ES directory `data/raw/ES/databento-es-trades-2020-2026` is diagnostic
only until it is resumed, completed, and validated.

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

2026-06-16 update: `es_realized_skewness_reversal` also failed at core after all five variants consumed exactly one parameter-space/fixed-parameter rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 36 campaigns, 180 source variants, 180 one-time rescues, 378 raw variant-level reports, 0 passes, and no active variants missing any original run or `rescue1`. No candidate strategy report exists.

2026-06-16 update: `es_variance_risk_premium_intraday` also failed at core after all five variants consumed exactly one parameter-space/fixed-parameter rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 37 campaigns, 185 source variants, 185 one-time rescues, 388 raw variant-level reports, 0 passes, and no active variants missing any original run or `rescue1`. No candidate strategy report exists.

2026-06-16 update: `es_realized_jump_variation_premium` failed before WFA after all five variants consumed exactly one parameter-space/fixed-parameter rescue. Do not proceed to chart review.

2026-06-16 verification: active sweep found 38 campaigns, 190 source variants, 190 one-time rescues, 398 raw variant-level reports, 0 passes, and no active variants missing any original run or `rescue1`. No candidate strategy report exists.

2026-06-16 continuation gate refresh: `research_artifacts/es_active_set_data_gate_refresh_20260616.md` confirms the active local set still has 0 passes and no missing rescue coverage. Manual chart review / paper incubation remains unauthorized for any active campaign. The retained next branches require missing 2020-start ES/MES divergence caches or the missing ES TBBO liquidity cache; no paid data was downloaded.

2026-06-16 Treasury-rate update: `es_treasury_rate_shock_intraday` also failed before WFA. All five originals and all five parameter-space-only rescues failed `limited_core_grid_test`; best rescue profitable-combo rate was `0.08333333333333333`, far below the required `0.70`. No candidate strategy report exists.

2026-06-16 video-edge queue review: `research_artifacts/es_video_edge_queue_review_20260616.md` reviewed earnings surprise drift, initial balance/ORB, politician tracking, option premium harvesting, and blockchain intelligence. None is queued as an immediate non-duplicate ES futures campaign under the current local/free-data constraints.

2026-06-16 OFR financial-stress update: `es_ofr_financial_stress_intraday` also failed at core after all five variants consumed exactly one parameter-space rescue. Best rescue profitable-combo rate was `0.5185185185185185`, below the required `0.70`, with zero benchmark-passing combinations. Do not proceed to chart review.

2026-06-16 verification: active sweep found 40 campaigns, 200 source variants, 200 one-time rescues, 418 raw variant-level reports, 0 passes, and no active variants missing `rescue1`. No candidate strategy report exists.

2026-06-16 VVIX tail-risk update: `es_vvix_tail_risk_intraday` also failed before WFA after all five variants consumed exactly one parameter-space rescue. `low_vvix_long_1030/rescue1` passed core but failed monkey with random-placebo profitable rate `0.31666666666666665` and median net profit `-1482.5`. Do not proceed to chart review.

2026-06-16 EPU policy-uncertainty update: `es_epu_policy_uncertainty_intraday` also failed at core after all five variants consumed exactly one parameter-space rescue. Best rescue was `low_epu_long_1030/rescue1` with profitable-combo rate `0.4074074074074074`, zero benchmark-passing combinations, top net `2170.625`, and top PF `1.1913709499669385`. Do not proceed to chart review.

2026-06-16 consumer-sentiment update: `es_consumer_sentiment_state_intraday` also failed at core after all five variants consumed exactly one parameter-space rescue. Best rescue was `high_sentiment_short_1030/rescue1` with profitable-combo rate `0.07407407407407407`, zero benchmark-passing combinations, top net `140.0`, top PF `1.1454545454545455`, and only `12` top-combo trades. Do not proceed to chart review.

2026-06-16 Cboe put/call update: `es_cboe_put_call_sentiment_intraday` also failed before WFA after all five variants consumed exactly one parameter-space rescue. Two rescues passed core but failed limited monkey: `falling_total_pc_long_1130/rescue1` had random-monkey profitable rate `0.19666666666666666` and median net `-2727.5`; `high_total_vs_equity_pc_short_1330/rescue1` had random-monkey profitable rate `0.06666666666666667`, median net `-3923.75`, and failed one-tick-worse stress. Do not proceed to chart review.

2026-06-17 oil-shock update: `es_oil_price_shock_spillover` also failed before WFA after all five variants consumed exactly one parameter-space rescue. `wti_up_risk_off_short_1030/rescue1` passed core but failed limited monkey with random-monkey profitable rate `0.17`, median net `-3905.0`, trade-path stress profitable rate `0.15666666666666668`, and one-tick-worse stress not profitable. Do not proceed to chart review.

2026-06-18 update: `es_ema_pullback_orderflow_continuation` also failed at limited core after all five variants consumed exactly one parameter-space/fixed-parameter rescue. The best rescue still had 0/81 profitable combinations, top net `-1498.75`, and PF `0.891962515768607`. Do not proceed to chart review.

2026-06-18 feasibility note: footprint/CVD absorption-initiation is not yet a candidate strategy. It is queued only as a future data-contract/feature-build branch; true footprint diagonal imbalance requires validated local raw Sierra price-level bid/ask-volume features before campaign testing.

2026-06-21 update: `es_profile_aoi_footprint_trap_confluence` failed at limited core without a rescue. All five predeclared AOI/profile/footprint-absorption variants had 0/81 profitable combinations and 0 benchmark-passing combinations; no variant reached WFA, Monte Carlo, simulated incubation, or acceptance OOS. Do not proceed to chart review.

2026-06-21 update: `es_video_aoi_lvn_orderflow_playbook`, derived from the supplied Chart Fanatics / Trader Yush orderflow notes, failed at limited core without a rescue. Four trend-LVN variants had 0/81 profitable combinations; the range value-edge variant had only 4/81 profitable combinations and 0 benchmark-passing combinations. The true >200-lot ES print component and overnight-high/low component remain data-gated in the current local cache. Do not proceed to chart review.

2026-06-22 data gate: `research_artifacts/es_aoi_orderflow_local_data_gate_20260622.md` confirms the local Sierra-only AOI/orderflow inventory remains exhausted after the profile/AOI footprint and video-derived campaigns. The next non-duplicate branch requires explicit approval to complete/validate Databento ES `trades` for true >200-lot features or to run the bounded ES TBBO/quote-liquidity pilot. Do not launch another local Sierra-only AOI/orderflow campaign without a genuinely new source-supported mechanism.

2026-06-22 large-record proxy update: `es_large200_record_aoi_profile_reaction` tested a stricter Sierra SCID large-record proxy branch after a separate source-quality audit (`volume >= 200`, `num_trades == 1`, exact side-volume coverage). All five predeclared variants failed `limited_core_grid_test` with 0/27 profitable combinations and 0 benchmark-passing combinations. This does not validate or reject true vendor-equivalent >200-lot ES prints; that branch still requires independent print-source data approval. Do not proceed to chart review.

2026-06-22 TBBO prep update: the Databento RTH downloader now writes schema-specific filenames, so an approved `--schema tbbo` pull will produce `*.rth.tbbo.dbn.zst` files that `propstack.build_tbbo_liquidity_cache` can actually read. `research_artifacts/es_quote_liquidity_sweep_pilot_protocol_20260614.md` has been refreshed with current dry-run, paid-download, cache-build, and staged-run commands. This is infrastructure prep only; no TBBO data was downloaded and no quote-liquidity campaign has been tested.
