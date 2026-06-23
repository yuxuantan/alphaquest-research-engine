# ES Overnight VAP Orderflow Breakout Continuation Methodology Audit

Date: 2026-06-22

Decision: FAIL

## Scope

Tested exactly five predeclared variants from `campaigns/es_overnight_vap_orderflow_breakout_continuation/campaign.yaml` using local Sierra footprint/VAP plus completed overnight AOI cache.

## Stage Outcome

| Variant | Profitable iterations | Benchmark-pass combos | Top net | Top PF | Top trades/year | Failure reason |
|---|---:|---:|---:|---:|---:|---|
| `overnight_vap_immediate_breakout_two_sided_1500` | 0/81 | 0 | -2182.50 | 0.740 | 78.6 | min_total_net_profit |
| `overnight_vap_two_sided_breakout_1530` | 0/81 | 0 | -3537.50 | 0.607 | 79.3 | min_total_net_profit |
| `overnight_vap_morning_breakout_two_sided_1200` | 0/81 | 0 | -3360.00 | 0.561 | 64.1 | min_total_net_profit |
| `overnight_large10_vap_breakout_two_sided_1530` | 0/81 | 0 | -3412.50 | 0.617 | 79.3 | min_total_net_profit |
| `overnight_large20_vap_breakout_two_sided_1530` | 0/81 | 0 | -3412.50 | 0.617 | 79.3 | min_total_net_profit;max_consecutive_losses |

## Rejection Rationale

The campaign failed closed at limited_core_grid_test. No variant produced a benchmark-passing core combination, so monkey, WFA, Monte Carlo, and incubation stages were not reached. No rescue was applied.
