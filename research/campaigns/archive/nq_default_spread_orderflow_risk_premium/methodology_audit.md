# Methodology Audit: nq_default_spread_orderflow_risk_premium

Date: 2026-06-23

Verdict: FAIL.

This campaign was a pre-PnL NQ port of `es_default_spread_orderflow_risk_premium`, starting from the ES parameter-space rescue configs that had the strongest remaining ES core-grid evidence among untried NQ macro/orderflow candidates.

## Pre-PnL Density Control

The NQ density audit failed before any NQ PnL inspection: `research_artifacts/nq_default_spread_orderflow_risk_premium_density_audit_20260623.md`.

Only `two_sided_spread_change_large10_1130` cleared both the >=50 full-history signals/year screen and the >=50 latest-252-session screen across declared entry-grid corners. The high default-spread long variants generated zero latest-252 signals at all declared entry-grid corners. Because one passing variant is not a valid five-variant campaign, no staged testing was run.

## No-Lookahead Controls

- A session dated D only uses the latest FRED Aaa/Baa observation on or before D minus two business days.
- Signals use completed NQ 5-minute bars and cumulative orderflow only through the completed confirmation bar.
- Engine entries would be next-bar-open or later; no same-bar close entry is assumed.
- No same-day credit observation, final session high/low, final VWAP, future orderflow, or post-entry path is used for signal generation.

## Execution Controls

- NQ tick size 0.25, point value 20.0, tick value 5.0.
- Commission 2.5 per contract and 1 tick slippage are configured in every variant.
- All variants configure same-day flatten at 15:55 ET and Apex-style no-overnight checks.
- Same-bar stop/target conflicts would be pessimistic in the engine, but no PnL stage was reached.

## Outcome

The campaign failed closed at the pre-PnL density screen. No rescue was run, no staged results were produced, and no `candidate_strategy_report.md` was created.
