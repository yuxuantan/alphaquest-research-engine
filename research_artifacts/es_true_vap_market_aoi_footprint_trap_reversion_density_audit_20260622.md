# ES True VAP Market AOI Footprint Trap Reversion Density Audit - 2026-06-22

Decision: approve for staged testing before PnL.

## Scope

This audit checks whether a true-VAP footprint trap/reversion expression has
enough pre-PnL signal density to justify a five-variant campaign.

The campaign is distinct from `es_true_vap_aoi_breakout_continuation`, which
tested accepted breakout continuation. This campaign tests failed probes back
inside market-generated AOIs after completed footprint absorption.

## Data

- Source cache: `data/cache/orderflow/es_sierra_footprint_vap_profile_1m_20101214_20260610_full_rth_ny.parquet`
- Staged subset: `2011-01-03` through `2026-06-09`, RTH, `America/New_York`
- Rows loaded during module-level density pass: `1,488,630`
- First timestamp: `2011-01-03 09:30:00-05:00`
- Last timestamp: `2026-06-09 15:59:00-04:00`

## No-Lookahead Controls

- Prior VAP levels are shifted from completed prior RTH sessions.
- Prior RTH high/low are built from completed prior RTH sessions.
- Opening-range levels are used only after the first 30 completed RTH bars.
- Footprint absorption and signed-volume imbalance are read from the completed signal bar.
- Engine entry remains next-bar open.

## Density Evidence

The existing `profile_aoi_footprint_trap` module with `profile_source:
cached_prior_vap` produced this pre-PnL module-density result before campaign
staging:

- `prior_profile_two_sided_trap`, `09:45` to `15:00`, no fixed adverse-delta
  threshold, `max_profile_distance_ticks=8`, `min_absorption_volume=50`:
  `1,392` signals, about `90.34` signals/year, `627` long and `765` short.

A faster vectorized approximation was then used only to reject sparse variants
before writing configs. It showed that single-side prior variants and strict
morning-only variants were too sparse for the staged benchmark, while combined
market-AOI variants should have sufficient density.

## Added Setup Mode

`market_profile_two_sided_trap` was added before any PnL result for this
campaign. It combines these existing AOI candidates under the same footprint
trap and profile-confluence logic:

- prior RTH low seller-trap long
- prior RTH high buyer-trap short
- opening-range low seller-trap long
- opening-range high buyer-trap short

The change does not alter the existing prior-only or opening-only setup modes.

## Caveat

This is not true delta-at-price profile or vendor-equivalent >200-lot print
sequencing. It is a completed-bar Sierra footprint/VAP candidate strategy that
still requires the full staged workflow before any promotion language is allowed.
