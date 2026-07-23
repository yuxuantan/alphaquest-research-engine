# Methodology Audit - ES Profile-AOI Footprint Trap Confluence

Final decision: FAIL

## Scope

This campaign tested five predeclared ES 1-minute variants requiring confluence between a market-generated AOI, an approximate frozen prior-session profile level, and completed footprint absorption/trapped-flow evidence. It did not use true ES >200-lot print logic because the validated full-history local cache does not contain a vendor-equivalent field for that feature.

## Data And Leakage Controls

- Data source: validated local Sierra ES 1-minute footprint imbalance cache in America/New_York.
- Prior profile, POC, VAH, VAL, and LVNs were built only from completed prior RTH bars.
- Opening range levels became available only after the configured opening-range bars completed.
- Signals used completed signal-bar footprint fields and entered no earlier than the next 1-minute bar open.
- No final current-session profile, final VWAP, future high/low, future orderflow, or future footprint field was used.

## Stage Result

All five variants failed `limited_core_grid_test`; none reached monkey, WFA, Monte Carlo, simulated incubation, or acceptance OOS.

| Variant | Profitable iterations | Benchmark passes | Apex violations | Top net | Top PF | Top MAR | Top trades/year | Failure |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| opening_profile_two_sided_morning_trap_1200 | 0/81 | 0 | 0 | -1555.0 | 0.811229 | -0.339169 | 69.13 | min_total_net_profit;max_consecutive_losses |
| opening_profile_two_sided_trap_1500 | 0/81 | 0 | 0 | -2637.5 | 0.744366 | -0.452382 | 84.79 | min_total_net_profit;max_consecutive_losses |
| orh_profile_buyer_trap_short_1500 | 0/81 | 0 | 0 | -830.0 | 0.884522 | -0.337332 | 56.18 | min_total_net_profit;max_consecutive_losses |
| orl_profile_seller_trap_long_1500 | 0/81 | 0 | 0 | -1592.5 | 0.760346 | -0.516870 | 56.60 | min_total_net_profit;max_consecutive_losses |
| prior_extreme_profile_two_sided_trap_1500 | 0/81 | 0 | 0 | -4332.5 | 0.328555 | -0.638817 | 61.86 | min_total_net_profit;max_consecutive_losses |

## Verdict

FAIL. The edge was rejected before robustness testing because the predeclared parameter space produced no profitable combinations and no benchmark-passing combinations. No candidate strategy report was created.
