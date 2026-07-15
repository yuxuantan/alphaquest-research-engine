# Exact Databento Yush range mechanics contract

This is a separate canonical trade-event implementation. It does not reuse the
bar-scanning `yush_range_27` approximation.

For every Databento trade message, in exchange-timestamp order with source-order
tie breaking, the replay:

1. Updates the developing one-tick 70% RTH volume profile, one- and four-tick
   RTH delta profiles, the developing three-minute four-tick delta bubble, the
   strict same-price/same-side uninterrupted 100 ms large-trade chain, the RTH
   range, completed three-minute bars, and the first-32-second opening range.
2. Rebuilds at most one VAL AOI and one VAH AOI. Each is anchored by its live
   value-area edge and must contain at least one of the market, RTH delta-profile,
   or persistent big-trade categories inside a maximum three-point box.
3. Maximizes additional category count, minimizes box width, minimizes midpoint
   distance to the value edge, then applies the accepted deterministic tie-break.
4. Preserves tap/order state and reprices an overlapping AOI lineage. A
   non-overlapping replacement starts a new lineage. A filled lineage is locked.
5. Enforces strict causal separation: AOI eligibility, tap, entry bubble, and
   stop-market fill must occur on four strictly ordered events. A newly repriced
   order is active only from the next event.
6. Allows either a live `abs(delta) > 300` developing three-minute four-tick
   bucket or a strict aggregate size `> 200` big-trade snapshot after the tap.
   Delta eligibility is rechecked at the fill event; big-trade snapshots persist.
7. Applies the variable range formula, centered POC, accepted failed-breakout
   rule, and two-overlapping-reversal rule at the fill event.
8. Fills entry and exits at the requested prices with zero slippage, per the
   user's instruction. Initial stop is two ticks outside the opposite AOI edge.
9. Once price has reached both the live value-area midpoint and entry plus/minus
   1.25 points, schedules that requested stop and the then-current opposite value
   edge as frozen stop/target values for the next event. Requiring price to trade
   through the requested stop avoids placing a marketable stop on the wrong side
   of the current market when the midpoint is closer than 1.25 points.
10. Requires the opposite direction only after an unmanaged initial full stop.
    It allows at most three trades and flattens at 11:00 America/New_York.

PDH/PDL/PDC and overnight levels are derived from the same active-contract
Databento archive. Previous-day levels are suppressed across roll boundaries.

The historical high-impact USD calendar is not present. Therefore the required
T-5-minute flatten and T-5-minute-through-T entry block remain an explicit
fail-closed data gap even after the canonical event mechanics pass tests.

When supplied, `event_filters.high_impact_usd_news.calendar` must reference a
CSV with `release_timestamp`, `currency`, and `impact` columns. Release
timestamps must contain an explicit UTC offset or `Z`; rows are filtered to
high-impact USD events. At T-5 minutes the replay flattens, clears AOI tap and
pending-trigger state, and blocks entries through T inclusive. Developing
profiles and persistent big-trade snapshots remain intact, and the first new
tap may occur only on an event strictly after T.

## Canonical-engine migration compatibility notes

The reusable event lane rejects inverted or already-marketable dynamic brackets
by default. This frozen strategy explicitly opts into its historical midpoint
behavior so migration does not change the 281-trade reference result: the
requested +1.25-point managed stop can be beyond the frozen opposite-value-edge
target, and that target may already have traded when the amendment becomes
active. Both conditions are exported per trade and counted in run metrics. They
must be reviewed as strategy mechanics, not treated as normal engine behavior.

Two pre-existing trigger ambiguities are also preserved rather than silently
changed after results were known:

- A persistent big-trade snapshot is keyed by price. An older pre-tap snapshot
  at that price can mask a later qualifying post-tap snapshot.
- The developing three-minute delta bucket is evaluated from its current
  cumulative value. A bucket that first crossed the threshold before the tap
  can therefore be recognized as the post-tap trigger while it remains above
  threshold.

Any correction to these two rules is a mechanics revision and requires an
explicitly authorized rerun; it is not part of the execution-lane migration.
