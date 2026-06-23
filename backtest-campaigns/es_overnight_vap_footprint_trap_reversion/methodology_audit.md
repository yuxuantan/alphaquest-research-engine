# ES Overnight VAP Footprint Trap Reversion Methodology Audit

Date: 2026-06-22

Decision: FAIL

## Scope

Tested exactly five predeclared variants from `campaigns/es_overnight_vap_footprint_trap_reversion/campaign.yaml` using the bounded local Sierra footprint/VAP plus completed overnight AOI cache.

## Data And Leakage Controls

- Overnight high/low features end no later than 09:29 ET for the same RTH session.
- Prior true VAP levels are shifted from completed prior RTH sessions.
- Entry signals use only completed 1-minute bars and enter no earlier than the next 1-minute open.
- The cache validation report found zero bad overnight windows and zero duplicate timestamps.
- Six 2014 RTH sessions have null overnight AOIs; the entry module fails closed on those sessions.

## Stage Outcome

| Variant | Profitable iterations | Benchmark-pass combos | Top net | Top PF | Top trades/year | Failure reason |
|---|---:|---:|---:|---:|---:|---|
| `overnight_vap_immediate_open_trap_two_sided_1500` | 0/81 | 0 | -697.50 | 0.936 | 82.8 | min_total_net_profit |
| `overnight_vap_two_sided_trap_1530` | 0/81 | 0 | -1147.50 | 0.899 | 86.1 | min_total_net_profit |
| `overnight_vap_confirmed_reclaim_two_sided_1530` | 0/81 | 0 | -1665.00 | 0.830 | 70.4 | min_total_net_profit;max_consecutive_losses |
| `overnight_vap_deep_probe_two_sided_1530` | 0/81 | 0 | -1592.50 | 0.835 | 72.4 | min_total_net_profit;max_consecutive_losses |
| `overnight_vap_morning_trap_two_sided_1200` | 3/81 | 0 | 290.00 | 1.036 | 60.0 | max_best_day_concentration |

## Rejection Rationale

The campaign failed closed at limited_core_grid_test. Four variants had zero profitable parameter combinations. The morning-only variant had three profitable combinations, but no benchmark-passing combinations and the best row failed best-day concentration. No monkey, WFA, Monte Carlo, or simulated incubation stage was reached.

No rescue was applied. Any future rescue would require explicit user authorization and must remain parameter-only within the same mechanics family.
