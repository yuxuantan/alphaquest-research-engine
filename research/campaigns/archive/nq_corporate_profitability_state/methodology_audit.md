# NQ Corporate Profitability State Methodology Audit

Date: 2026-07-01

Verdict before PnL: PASS for staged testing only.

This campaign tests one edge: strictly lagged BEA/FRED corporate-profit growth and profit-margin state as a macro profitability variable for NQ intraday risk appetite. It is distinct from style-factor rotation and productivity/ULC campaigns because it uses aggregate NIPA corporate-profit and GDP levels, not cross-sectional factor returns or labor-cost productivity ratios.

Availability rule: each NQ session can use only the latest quarterly CPROFIT/CPATAX/GDP observation with observation_date on or before session_date minus 120 calendar days. The feature builder computes rolling ranks on quarterly observations before the as-of join. Entry is evaluated on the completed one-minute bar ending at the configured decision time and is intended for next-bar execution.

Pre-PnL density: research_artifacts/nq_corporate_profitability_state_density_audit_20260701.md shows 45/45 declared rows passing the 50 signals/year floor across full history, limited-core, and latest-252-session windows. The audit did not inspect PnL, stops, targets, or trade outcomes.

Parameter discipline: all five variants use the same declared grid before staged testing: entry rank_min [0.50, 0.55, 0.60], stop_pct [0.003, 0.004, 0.005], and target_r_multiple [1.5, 2.0, 2.5]. No rescue is authorized.

Required verdict rule: after staged testing, report PASS, FAIL, or NEEDS MANUAL REVIEW only. Do not describe any branch as ready to trade.
