# Methodology Audit: nq_52week_anchor_momentum

Verdict before PnL: APPROVE FOR DENSITY/PREFLIGHT ONLY.

This campaign tests a distinct 52-week-high anchor edge from George and Hwang (2004). It is not a generic trend-following or weekly-stage campaign: the required state is nearness to the completed prior 252-session high, and the current session is excluded from the anchor calculation.

## Pre-PnL Density Revision

An initial draft included tight new-high breakout and far-from-high breakdown variants. The pre-PnL opportunity-count audit rejected those mechanics as structurally sparse before any PnL was inspected. The frozen campaign uses five long-only near-anchor variants with density-viable top-anchor bands.

## No-Lookahead Contract

- The module records completed RTH daily bars only after the configured RTH close.
- The 252-session high/low and prior close are drawn only from sessions before the signal session.
- Intraday triggers use completed 5-minute bars and staged next-bar execution.
- Stops, targets, flatten time, commissions, slippage, tick size, and point value are declared in each config.

## Duplicate Review

Checked against NQ daily time-series momentum, short-term reversal, weekly stage, market-structure pivot, prior-session breakout, and round-number barrier campaigns. Those do not use the completed prior 252-session high as the primary state variable.

## Failure Rules

If density, preflight, limited core, monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS fails, the campaign is FAIL. No rescue is authorized.

## Config Correction Before Valid PnL

The first generated run (`run1`) halted before valid PnL because the source configs used the descriptive label `completed_intraday_bars_plus_internal_prior_252_session_anchor` for `data.feature_set`, while the runner only accepts built-in feature-set labels. Because the anchor is computed inside the entry module, the configs were corrected to `data.feature_set: none` and rerun as `run2`. The invalid `run1` directories are preserved as config-error evidence.

## Final Staged Verdict

Verdict: FAIL.

All five frozen variants passed density and preflight, then failed `limited_core_grid_test` in `run2`. Each variant tested 81 official parameter combinations; every variant had 0 benchmark-passing combinations and profitable-iteration rates below the 0.70 threshold. No variant reached limited monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
