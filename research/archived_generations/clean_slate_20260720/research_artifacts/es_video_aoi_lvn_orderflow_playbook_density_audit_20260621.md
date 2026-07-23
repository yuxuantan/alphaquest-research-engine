# ES Video AOI LVN Orderflow Playbook Density Audit

Date: 2026-06-21

This audit counted raw signal opportunities before any PnL, stop, target, or staged backtest result was viewed. It used the local Sierra ES 1-minute footprint imbalance cache and derived RTH session, prior RTH high/low, opening range, and approximate prior-session profile levels from completed bars only.

## Data Gate

- True ES prints above 200 lots are not available as a vendor-equivalent full-history field in the validated local cache. The campaign does not claim to test that feature.
- The footprint cache is RTH-only, so overnight high/low variants are not tested.

## Strict Confluence Screen

Using separate market-generated level confluence plus profile edge/LVN plus footprint absorption was too sparse for most range expressions. At max profile/AOI distance 64 ticks, minimum absorption volume 20, and adverse delta threshold 0.05:

| Variant proxy | Signals | Signals/year |
|---|---:|---:|
| Range VAL seller trap long | 236 | 15.28 |
| Range VAH buyer trap short | 256 | 16.58 |
| Range two-sided through 12:00 | 240 | 15.54 |
| Trend LVN seller trap long | 699 | 45.26 |
| Trend LVN buyer trap short | 495 | 32.05 |

## Testable Trend Screen

For the video trend model, the prior LVN is treated as the area of interest and footprint absorption is the orderflow confirmation. With max LVN distance 96 ticks, minimum absorption volume 20, no separate aggregate-delta threshold, and an 8-tick minimum accepted trend move:

| Variant proxy | Signals | Signals/year |
|---|---:|---:|
| Trend LVN seller trap long | 1132 | 73.30 |
| Trend LVN buyer trap short | 789 | 51.09 |
| Trend LVN two-sided continuation | approximately 1921 | approximately 124.39 |

The stronger-trend two-sided variant uses a 20-tick minimum accepted trend move; the same screen produced about 60.54 long signals/year and 45.97 short signals/year before one-trade-per-day two-sided combination.

Decision before PnL: approve five variants for staged testing, with a warning that the range model is retained for strategy fidelity but is expected to be frequency-fragile.
