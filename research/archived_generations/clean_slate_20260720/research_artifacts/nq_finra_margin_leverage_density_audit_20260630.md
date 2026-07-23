# NQ FINRA Margin Leverage Density Audit

Created: 2026-06-30

This audit was completed before any NQ PnL staged run for `nq_finra_margin_leverage`.

Feature file: `data/external/nq_finra_margin_leverage_features_20110103_20260612.csv`

Predeclared staged start: 2014-03-07, the first session where all official 120-month FINRA rank features are non-null.

All five variant shapes clear the 50 signals/year pre-PnL density floor after that availability start. The thinnest declared corner is `rapid_margin_3m_expansion_short_1130` at 60.58 signals/year.
