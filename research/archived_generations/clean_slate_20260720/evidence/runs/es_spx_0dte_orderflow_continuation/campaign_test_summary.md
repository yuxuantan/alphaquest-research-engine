# ES SPX 0DTE Orderflow Continuation Campaign Summary

Decision: FAIL

All five original variants failed limited_core_grid_test. Each failed variant received exactly one logged parameter-space/fixed-parameter rescue preserving the SPX 0DTE orderflow-continuation mechanic. All five rescues also failed limited_core_grid_test; the best rescue reached 37/81 profitable combinations, below the 70% profitable-combination gate. No run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best run: `late_morning_large20_flow_continuation_1030/rescue1` top net `1332.5`, PF `1.1483027267668335`, trades/year `78.17907295130061`, profitable-combo rate `0.4567901234567901`.
