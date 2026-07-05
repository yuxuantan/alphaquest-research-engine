# NQ SLOOS Bank Lending Survey State Methodology Audit

Date: 2026-07-01

Verdict before PnL: PASS for staged testing only.

This campaign tests one edge: strictly lagged Federal Reserve Senior Loan Officer Opinion Survey commercial-and-industrial loan-demand strength as a state variable for NQ intraday risk appetite. It is not a duplicate of the H.8 bank-credit quantity campaign because the primary driver is survey-reported borrower demand, not commercial-bank balance-sheet levels or growth.

Availability rule: each NQ session can use only the latest quarterly SLOOS observation with observation_date on or before session_date minus 75 calendar days. The feature builder computes rolling ranks on quarterly observations before the as-of join. Entry is evaluated on the completed one-minute bar ending at the configured decision time and is intended for next-bar execution.

Pre-PnL density: research_artifacts/nq_sloos_bank_lending_survey_state_density_audit_20260701.md shows 45/45 declared rows passing the 50 signals/year floor across full history, limited-core, and latest-252-session windows. The audit did not inspect PnL, stops, targets, or trade outcomes.

Parameter discipline: all five variants use the same declared grid before staged testing: entry rank_min [0.50, 0.55, 0.60], stop_pct [0.003, 0.004, 0.005], and target_r_multiple [1.5, 2.0, 2.5]. No rescue is authorized.

Required verdict rule: after staged testing, report PASS, FAIL, or NEEDS MANUAL REVIEW only. Do not describe any branch as ready to trade.
