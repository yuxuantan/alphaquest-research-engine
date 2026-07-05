# nq_chartfanatics_jadecap_session_liquidity_fvg Methodology Audit

Final verdict: FAIL.

## Source and Edge

This campaign was launched from the ChartFanatics/JadeCap Intraday Liquidity & Volatility Model page after screening the remaining ChartFanatics ES/NQ strategy pages for duplicates and local data gates. The tested edge is the locally reproducible subset: NQ sweeps of frozen pre-RTH Asian/London session highs or lows followed by completed-bar failed continuation or FVG retest rejection.

The source is practitioner material, so it was not treated as standalone proof. Osler (2003) and Lo/Mamaysky/Wang (2000) were used as general support for clustered visible-level orders and deterministic conversion of chart patterns into tests.

## Duplicate Check

The edge was considered distinct from prior RTH liquidity inversion/FVG, overnight range compression, overnight return, rolling-range sweep, prior-day stop-run, and prior-session flip/retest campaigns because the traded levels are Asian/London pre-RTH highs and lows frozen before the New York session.

It is not a Bookmap/depth recreation. The source references discretionary context that the local cache cannot reproduce, so this campaign tests only an auditable completed-bar subset.

## Timing and Lookahead

- Asian session levels use ETH bars from the prior evening through 02:59 ET.
- London session levels use bars from 03:00 through 09:29 ET.
- Levels are frozen before any RTH signal can be evaluated.
- Sweep, reclaim, FVG creation, and FVG retest conditions use completed five-minute RTH bars only.
- The backtest engine fills no earlier than the next bar after signal emission.
- No final session high/low, final VWAP, future FVG, future orderflow, or post-entry path is used in the signal.
- Configs force same-day flattening and forbid overnight exposure.

## Parameter Freeze

Five variants were declared before staged PnL. Each used at most two entry tunables, one stop tunable, and one take-profit tunable. Each variant had 54 combinations.

Variants tested:
- asia_high_failed_sweep_short_1130: 54 combos, profitable_combo_rate=0.0, benchmark_pass_rate=0.0
- asia_high_fvg_reject_short_1200: 54 combos, profitable_combo_rate=0.0, benchmark_pass_rate=0.0
- asia_low_failed_sweep_long_1130: 54 combos, profitable_combo_rate=0.0, benchmark_pass_rate=0.0
- asia_low_fvg_reject_long_1200: 54 combos, profitable_combo_rate=0.07407407407407407, benchmark_pass_rate=0.0
- london_two_sided_fvg_reject_1200: 54 combos, profitable_combo_rate=0.0, benchmark_pass_rate=0.0

## Density Gate

Pre-PnL density passed: 45/45 declared entry rows and 5/5 variants passed the signal-density screen. Artifacts: `research_artifacts/nq_chartfanatics_jadecap_session_liquidity_fvg_density_audit_20260701.md`, `research_artifacts/nq_chartfanatics_jadecap_session_liquidity_fvg_density_summary_20260701.csv`.

## Staged Validation

All five variants failed `limited_core_grid_test`. The common rejection criterion was `summary.percentage_profitable_iterations < 0.70`; the best branch had 4/54 profitable combinations and still 0/54 benchmark-passing combinations.

No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting. No rescue was authorized or run.

## Artifact Manifest

- Campaign summary: `backtest-campaigns/nq_chartfanatics_jadecap_session_liquidity_fvg/campaign_test_summary.json`
- Result table: `backtest-campaigns/nq_chartfanatics_jadecap_session_liquidity_fvg/campaign_results.csv`
- Trade log manifest: `backtest-campaigns/nq_chartfanatics_jadecap_session_liquidity_fvg/trade_logs_manifest.csv`
- Equity curve manifest: `backtest-campaigns/nq_chartfanatics_jadecap_session_liquidity_fvg/equity_curves_manifest.csv`
- WFA table placeholder: `backtest-campaigns/nq_chartfanatics_jadecap_session_liquidity_fvg/wfa_table.csv`
- WFA stitched OOS placeholder: `backtest-campaigns/nq_chartfanatics_jadecap_session_liquidity_fvg/wfa_stitched_oos_trade_log.csv`
- Monte Carlo summary: `backtest-campaigns/nq_chartfanatics_jadecap_session_liquidity_fvg/monte_carlo_summary.json`

## Final Decision

FAIL. The edge cleared source, duplicate, timing, density, and preflight gates, but failed the first staged PnL robustness gate across all five variants. It is rejected unless the user explicitly authorizes a single rescue attempt within the same mechanics family.
