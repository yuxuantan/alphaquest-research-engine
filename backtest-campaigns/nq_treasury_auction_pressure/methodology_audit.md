# nq_treasury_auction_pressure Methodology Audit

Decision before testing: approved for staged NQ testing as a frozen nonduplicate transfer.

This campaign uses only preannounced nominal U.S. Treasury Note/Bond auction dates. It is distinct from the already failed NQ Treasury-rate and Treasury-rate/orderflow campaigns because those use lagged Treasury yield states, while this campaign uses the auction calendar itself as the ex-ante event variable.

No-lookahead controls:
- Auction rows are included only when the announcement date is before the auction date.
- The entry module reads only `signal_date`, note/bond counts, and terms from the derived calendar.
- Auction outcome fields such as high yield, tail, bid-to-cover, accepted amount, and dealer awards are not in the entry feature file.
- Entry decisions use completed one-minute NQ RTH bars only, with next-bar execution handled by the engine.
- No final session high/low, VWAP, future NQ return, post-entry orderflow, or same-day Treasury-yield observation is used.

Event-density result:
- Detail: `research_artifacts/nq_treasury_auction_pressure_event_density_20260702.csv`
- Markdown: `research_artifacts/nq_treasury_auction_pressure_event_density_20260702.md`
- all_coupon and note_only scopes clear the 50/year feasibility screen; bond_only is not used as a standalone variant.

Prior density-screen reconciliation:
- `research_artifacts/nq_treasury_auction_pressure_density_rejection_20260630.md` was found after campaign execution.
- That artifact treated ES staged counts of roughly 100-121 trades as full-history counts.
- Rechecking the local auction calendars gives about 86 all-coupon sessions/year and 67 note-only sessions/year, and staged ES/NQ summaries report trades-per-year above 50 for those scopes.
- The older density rejection is superseded only for density feasibility; the completed NQ staged campaign still failed WFA and remains rejected.

Rescue policy: none authorized after NQ testing begins. If the campaign fails any staged gate, reject it unless the user explicitly authorizes a rescue.
