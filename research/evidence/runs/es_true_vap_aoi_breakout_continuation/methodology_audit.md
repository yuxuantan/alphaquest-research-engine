# Methodology Audit - ES True VAP AOI Breakout Continuation

Final decision: FAIL

## Source Translation

This campaign tested whether ES breakouts through market-generated AOIs become more selective when the AOI is near a frozen previous-session true Sierra volume-at-price level and the completed breakout bar shows same-direction orderflow participation.

## Data Gates

- Previous-session POC, VAH, VAL, and high/low LVNs were built from Sierra SCID volume-at-price records, not an OHLCV uniform profile approximation.
- Sierra SCID-derived VAP is still not market-by-order, queue reconstruction, or vendor-equivalent print sequencing.
- Signed-volume, large10/large20, and footprint imbalance fields are completed-bar research proxies.
- True ES >200-lot vendor-equivalent print data and TBBO/depth liquidity were not available locally and were not inferred.

## Leakage Controls

- Prior VAP levels are shifted from the completed prior RTH session and are unavailable on the first session.
- Prior RTH high/low are shifted completed-session levels.
- Opening-range levels are unavailable until the configured opening range has fully closed.
- Breakout and orderflow confirmation use only the completed signal bar; entry is no earlier than the next one-minute open.
- No current-session final profile, final VWAP, final daily range, future high/low, future orderflow, or post-entry information is used.

## Stage Result

All five variants failed `limited_core_grid_test`; none reached monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Valid run | Profitable iterations | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| prior_high_true_vap_breakout_long_1200 | run1 | 0/81 | 0 | 0 | -1247.5 | 0.920288 | -0.200720 | 105.85 | min_total_net_profit;max_consecutive_losses |
| prior_low_true_vap_breakdown_short_1200 | run1 | 0/81 | 0 | 0 | -3960.0 | 0.635443 | -0.646701 | 89.36 | min_total_net_profit;max_consecutive_losses |
| prior_extreme_large10_true_vap_two_sided_1500 | run2 | 0/81 | 0 | 0 | -11070.0 | 0.670854 | -0.641523 | 210.58 | min_total_net_profit;max_consecutive_losses |
| opening_range_true_vap_two_sided_1130 | run2 | 0/81 | 0 | 0 | -2125.0 | 0.857788 | -0.348421 | 84.92 | min_total_net_profit;max_consecutive_losses |
| combined_large20_true_vap_two_sided_1500 | run1 | 0/81 | 0 | 0 | -9752.5 | 0.756735 | -0.613894 | 242.43 | min_total_net_profit;max_consecutive_losses |

## Setup Correction

The first `run1` attempts for `prior_extreme_large10_true_vap_two_sided_1500` and `opening_range_true_vap_two_sided_1130` failed before strategy evaluation because unquoted YAML `10:00:00` was parsed as integer `36000`. The source configs were corrected by quoting time literals; valid evidence for those two variants is in `run2`.

## Verdict

FAIL. The true VAP AOI breakout-continuation edge did not produce a candidate strategy under the staged ES methodology. No candidate strategy report was created.
