# Composite Edge Policy - 2026-06-17

Decision: allow constrained composite-edge campaigns.

This policy updates the campaign search process after the user explicitly allowed
mixing compatible edges, filters, and conditions. The staged benchmarks remain
unchanged.

## Allowed Structure

A composite campaign may combine:

- one primary economic edge; and
- at most two secondary conditions that are independently justified before
  testing.

Examples of acceptable secondary conditions:

- multi-timeframe direction filter, such as higher highs/higher lows allowing
  longs only and lower highs/lower lows allowing shorts only;
- ex-ante volatility, liquidity, or calendar regime filter;
- cross-market confirmation when the confirmation market is part of the thesis,
  not an after-the-fact performance patch.

## Not Allowed

Do not use composite logic to disguise overfitting:

- no adding a new filter as a rescue after a failed run;
- no trying many filters against the same failed variant until one works;
- no selecting a filter because it would have saved the known losing trades;
- no stacking more than two secondary conditions;
- no changing the same composite mechanics after seeing original results except
  the one allowed parameter-space/fixed-parameter rescue per failed variant;
- no using the final holdout to choose filters, timeframes, thresholds, or
  direction rules.

If a failed single-edge campaign inspires a composite campaign, the composite
must be logged as a new campaign with a new thesis. The prior failure remains
failed and the composite must explain why the combination is an economic
mechanism, not a renamed rescue.

## Tunables

The existing tunable caps still apply:

- maximum 2 entry tunables;
- maximum 1 stop tunable;
- maximum 1 target/exit tunable;
- normally 8 to 120 total combinations, unless there are no tunables.

Secondary filters should be fixed whenever possible. If a filter threshold is
tunable, it consumes one of the entry tunables.

For a multi-timeframe direction filter, the default implementation should use
fixed, predeclared trend definitions, not optimized trend lengths. Example:

- a higher-timeframe uptrend requires the latest completed 30-minute and
  120-minute swing states to show higher high and higher low, or a close above
  both prior completed swing anchors;
- a higher-timeframe downtrend requires lower high and lower low, or a close
  below both prior completed swing anchors;
- ambiguous trend state means no trade.

The exact trend definition must be documented in `campaign.yaml` before the
first run.

## Density Gate

Before testing PnL, every composite variant needs a density audit:

- estimate pre-cost signal count over the available history;
- reject or redesign before testing if strictest planned filters are unlikely
  to clear 50 trades/year;
- prefer dense primary edges when adding filters, because every condition cuts
  opportunity count.

## Source And Duplicate Rules

Composite campaigns still need research support. The primary edge must have a
source. Each secondary condition must either have a separate source or a clear
mechanistic role tied to the primary source.

Duplicate checks remain active-scope-only and ignore `_archived`. However,
active failed campaigns matter:

- reusing one active failed edge plus a generic filter is not enough by itself;
- the composite must change the economic hypothesis, not merely narrow the old
  trade set;
- if the only justification is "this filter might improve the old failure,"
  source a different edge instead.

## Stop Rule For Infinite Combinations

For each primary edge family:

1. Run at most one composite campaign with a given secondary filter family.
2. If all five variants and their one rescues fail, retire that primary-plus-
   filter family.
3. Do not test a second filter on the same primary edge unless a new source
   specifically supports that interaction.
4. After two failed composite campaigns derived from the same primary edge,
   stop using that primary edge and source a new edge.

## Initial Queue Decision

Do not proceed with ES/MES same-direction flow confirmation as the next campaign:
the density audit showed realistic dual-confirmation thresholds produce only
about 7 to 15 signals/year for most fixed-time variants, below the 50 trades/year
floor.

The next reasonable composite campaign should use a dense primary edge and a
fixed trend-direction condition. The strongest current candidate is SPX 0DTE
calendar pressure plus multi-timeframe ES trend alignment, because the primary
edge has near-daily opportunity after full weekday 0DTE listing and the trend
filter is a predeclared risk-state/direction condition rather than a new exit or
trade-management tweak.
