# NQ Intraday Periodicity Orderflow Confirmation Campaign Summary

Verdict: FAIL.

All five predeclared variants failed `limited_core_grid_test`; no WFA, monkey, Monte Carlo, simulated incubation, or acceptance stage was reached.

| variant | combos | profitable | benchmark pass | top net | top PF | top trades/year | top failure |
|---|---:|---:|---:|---:|---:|---:|---|
| afternoon_1330_large20_confirmed_slot | 54 | 4 | 0 | 657.50 | 1.0974 | 112.19 | max_best_day_concentration |
| late_afternoon_1430_large20_confirmed_slot | 54 | 0 | 0 | -1720.00 | 0.7199 | 112.44 | min_total_net_profit |
| late_morning_1130_signed_confirmed_slot | 54 | 0 | 0 | -1650.00 | 0.7727 | 85.67 | min_total_net_profit |
| morning_1000_signed_confirmed_slot | 54 | 3 | 0 | 427.50 | 1.0586 | 92.33 | max_best_day_concentration |
| morning_1030_large10_confirmed_slot | 54 | 0 | 0 | -432.50 | 0.9442 | 98.90 | min_total_net_profit |

Best top core row by net profit: `afternoon_1330_large20_confirmed_slot` with net `657.50`, PF `1.0974`, and failure reason `max_best_day_concentration`.

No `candidate_strategy_report.md` was created because nothing passed.
