# Methodology Audit: nq_intraday_capitulation_mean_reversion

Verdict: FAIL.

## Pre-PnL Controls

- Initial signed-sell-imbalance grid failed opportunity-density screening before PnL and was preserved at `research_artifacts/nq_intraday_capitulation_mean_reversion_initial_density_rejected_20260623.md`.
- Final grid passed runner-matched density screening at `research_artifacts/nq_intraday_capitulation_mean_reversion_density_audit_20260623.md`.
- `run1` halted before PnL because strategy timeframe did not match entry timeframe.
- `run2` omitted the VWAP feature set and produced invalid zero-signal staged output.
- Valid staged results are `run3` only.

## Stage Outcome

All five variants failed `limited_core_grid_test`; best profitable-combination rate was 0.4074, below the 0.70 gate. No later robustness stage was reached.

## Failure Reason

All five valid run3 NQ intraday capitulation mean-reversion variants failed limited_core_grid_test. The best branch, full_session_15m_structural_flush_reclaim_long_1530, had 33/81 profitable combinations (40.7%) and 16 benchmark-passing combinations, below the 70% profitable-combination gate. No monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting stage was reached.
