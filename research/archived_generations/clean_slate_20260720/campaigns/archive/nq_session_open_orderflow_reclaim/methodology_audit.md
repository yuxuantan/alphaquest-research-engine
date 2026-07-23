# NQ Session Open Orderflow Reclaim Methodology Audit

Status: failed the pre-PnL density gate on 2026-06-30. No staged PnL was inspected.

- One campaign, one edge: current RTH open-anchor reclaim/rejection after a prior completed excursion with completed aggregate orderflow confirmation.
- Duplicate screen: distinct from NQ opening gap, opening drive, opening range, prior-session level, round-number, session-extreme, and VWAP families.
- Instrument scaling: ES min_open_extension_ticks [6, 8, 12] scaled by the pre-PnL NQ/ES median open-excursion ratio to [20, 28, 40].
- Timing: the RTH open is known from the first regular-session bar; excursion evidence must exist on a prior completed bar; reclaim/rejection flow is used only after the signal bar completes; entries are next 1-minute open or later.
- Parameter discipline: 27 combinations per variant, with two entry tunables, one stop tunable, and fixed 1R target.
- Rescue policy: no rescue authorized for this NQ search unless the user explicitly allows it after a failure.

Final density verdict: FAIL. Three of five variants had sparse entry-grid rows in the limited-core proxy window; the weakest row had 39.50 signals/year. Dropping the sparse direction/window rows or tightening the declared campaign after observing density would change the five-variant edge.
