# NQ Treasury Auction Pressure Event-Density Audit - 2026-07-02

Verdict: PASS for the five predeclared NQ transfer variants.

Calendar: `data/external/nq_treasury_coupon_auction_sessions_20110103_20260612.csv`

Source rule: include nominal Treasury Note/Bond auction rows only when `announcemt_date < auction_date`; auction outcomes are not available to the entry module.

Date range: 2011-01-11 to 2026-06-09

Rows: 1322 all-coupon auction sessions, 1034 note sessions, 293 bond sessions.

Estimated density over 15.41 years:

- all_coupon: 85.80 sessions/year
- note_only: 67.11 sessions/year
- bond_only: 19.02 sessions/year

Decision: all_coupon and note_only scopes satisfy the 50-trades/year feasibility screen used by the staged workflow. Bond-only is intentionally not used as a standalone variant because it is materially sparser and was already identified as sparse in the ES campaign. No NQ PnL was inspected for this audit.

## Prior Density-Screen Reconciliation

This recheck found `research_artifacts/nq_treasury_auction_pressure_density_rejection_20260630.md`, which rejected the NQ port before PnL by interpreting the ES staged counts of roughly 100-121 trades as full-history counts. The local ES and NQ auction-calendar CSVs both contain about 86 all-coupon sessions/year and 67 note-only sessions/year over 2011-2026. The staged ES/NQ summaries also report trades-per-year above 50 for all-coupon and note-only variants. Therefore the earlier rejection is superseded only on event-density feasibility. The subsequent NQ staged run still failed closed at WFA.
