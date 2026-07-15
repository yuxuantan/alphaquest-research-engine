# NQ Labor Market Slack State Methodology Audit

Date: 2026-07-02

Verdict before PnL: PASS for staged testing only.

This campaign tests one edge: strictly lagged monthly labor-market slack and participation-repair state. It is not a duplicate of weekly jobless claims, BLS release-day drift, CFNAI, wage/inflation, or payroll-growth event timing.

Availability rule: each NQ session can use only the latest monthly UNRATE/U6RATE/EMRATIO/CIVPART observation with observation_date on or before session_date minus 45 calendar days. The feature builder computes rolling ranks on monthly observations before the as-of join. Entry is evaluated on the completed one-minute bar ending at the configured decision time and is intended for next-bar execution.

Pre-PnL density: research_artifacts/nq_labor_market_slack_state_density_audit_20260702.md shows 45/45 declared rows passing the 50 signals/year floor across full history, limited-core, and latest-252-session windows. The audit did not inspect PnL, stops, targets, or trade outcomes.

Parameter discipline: all five variants use the same declared grid before staged testing: entry rank_threshold [0.50, 0.55, 0.60], stop_pct [0.003, 0.004, 0.005], and target_r_multiple [1.5, 2.0, 2.5]. No rescue is authorized.
