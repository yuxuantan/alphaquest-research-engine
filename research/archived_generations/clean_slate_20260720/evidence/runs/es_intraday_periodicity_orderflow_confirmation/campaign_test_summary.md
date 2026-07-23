# ES Intraday Periodicity Orderflow Confirmation - Campaign Summary

Decision: FAIL

All five original variants failed `limited_core_grid_test`. Each failed variant received one logged parameter-space/fixed-parameter rescue preserving the same entry, stop, target, slot, flow mode, data, costs, fills, sessions, and benchmark gates.

Best rescue: `morning_1030_large10_confirmed_slot/rescue1` with 29/81 profitable combinations (35.8%), top net `$1890.0`, PF `1.3108552631578947`, MAR `1.278178203219572`, and `82.22` trades/year.

No run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Results CSV: `backtest-campaigns/es_intraday_periodicity_orderflow_confirmation/campaign_results.csv`.
