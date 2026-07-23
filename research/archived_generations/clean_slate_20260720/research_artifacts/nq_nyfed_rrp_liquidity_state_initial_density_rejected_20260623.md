# NQ NY Fed RRP Liquidity State Initial Pre-PnL Density Screen

Date: 2026-06-23

Verdict: NEEDS PRE-PNL REFORM

This initial screen counted only entry signals for the first NQ port of `es_nyfed_rrp_liquidity_state`; no NQ PnL, stop, target, monkey, WFA, Monte Carlo, prop simulation, or holdout result was inspected.

Prepared data: 229,086 NQ 5-minute RTH bars, 2,937 sessions, 2014-08-11 through 2026-05-29.

Issue found before PnL:

- All full-history corners cleared 50 signals/year.
- Latest-252 density failed for the release-long side: maximum latest-252 count was 27 and strict release count was 12.
- The strict 0.375 drain threshold also failed latest-252 density with 28 signals.

Pre-PnL reform applied:

- Archived `rrp_release_long_1000` and `rrp_release_long_1330` under `campaigns/nq_nyfed_rrp_liquidity_state/rejected_pre_pnl_density/`.
- Trimmed drain threshold grid from `[0.125, 0.25, 0.375]` to `[0.125, 0.25]`.
- Added 11:30 and 14:30 drain timing variants so the final campaign still has exactly five variants, all within the same RRP drain short mechanic.

CSV: `research_artifacts/nq_nyfed_rrp_liquidity_state_initial_density_rejected_20260623.csv`
