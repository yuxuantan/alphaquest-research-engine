# ES Prior Value-Area Orderflow Rejection Campaign Summary

Decision: FAIL

All five originals and all five one-time parameter-space/fixed-parameter rescues failed limited_core_grid_test. Every run had 0 profitable combinations and 0 benchmark-passing combinations after costs, with zero apex rule violations. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

## Best Runs

- Best original: morning_signed_vah_rejection_short run1 top_net=-252.5 PF=0.950803701899659 trades=68 tpy=44.83409696323921 profitable_combo_rate=0.0
- Best rescue: afternoon_large20_two_sided_rejection rescue1 top_net=-1344.9999999999523 PF=0.7318045862412856 trades=101 tpy=66.11731906154708 profitable_combo_rate=0.0

## Notes

- The pre-PnL raw density audit was useful for avoiding obviously sparse entry thresholds, but staged limited-core `signal_density` is the authoritative tradable-frequency measure because the engine skips new signals while already in a position.
- No paid or external market data was downloaded.
- No `candidate_strategy_report.md` was created because no run passed limited core.
