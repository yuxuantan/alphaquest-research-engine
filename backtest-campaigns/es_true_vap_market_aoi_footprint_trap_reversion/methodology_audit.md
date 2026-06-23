# Methodology Audit - ES True VAP Market AOI Footprint Trap Reversion

Decision: FAIL.

## Scope

This campaign tested five predeclared variants of a true Sierra VAP market-AOI footprint trap/reversion edge on ES 1-minute RTH data.

## Controls

- Prior RTH high/low and prior VAP levels are shifted from completed prior sessions.
- Opening-range levels are unavailable until the first 30 RTH bars have closed.
- Entry signals use completed signal bars and are filled no earlier than next-bar open.
- Costs include $2.50 commission per contract and one tick of slippage.
- Same-bar stop/target ambiguity uses the existing pessimistic staged runner path.
- Prop-rule flatten and no-overnight checks remained enabled.

## Result

All five variants failed `limited_core_grid_test`. No variant reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Profitable combos | Benchmark combos | Apex violations | Top net | Top PF | Top trades/year |
|---|---:|---:|---:|---:|---:|---:|
| `prior_vap_extreme_trap_two_sided_1500` | 0/81 | 0 | 0 | -4700.0 | 0.43202416918429004 | 81.66999582612844 |
| `opening_vap_aoi_trap_two_sided_1500` | 0/81 | 0 | 0 | -585.0 | 0.9200819672131147 | 64.0572242185911 |
| `market_vap_aoi_trap_two_sided_1500` | 0/81 | 0 | 0 | -4920.0 | 0.5954779033915725 | 113.6733375730355 |
| `market_vap_aoi_delta_trap_two_sided_1500` | 0/81 | 0 | 0 | -1010.0 | 0.8283772302463891 | 56.93518063444465 |
| `market_vap_aoi_morning_trap_two_sided_1200` | 0/81 | 0 | 0 | -2787.5 | 0.679228998849252 | 84.92835565801502 |

## Verdict

The local true-VAP footprint-trap expression is rejected. It does not reject true vendor-equivalent >200-lot ES print sequencing or quote/depth-liquidity branches, which remain data-gated.
