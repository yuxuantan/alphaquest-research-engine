# ES Prior LVN Orderflow Rejection Campaign Summary

Decision: **FAIL**

All five original variants failed limited_core_grid_test. Each failed variant received exactly one parameter-space/fixed-parameter rescue preserving the same prior-LVN rejection mechanic; all five rescues also failed limited_core_grid_test. No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation.

Best core run: `morning_signed_two_sided_lvn_rejection/run1` with profitable-combo rate `0.30864197530864196`, passing `12/81`, top net `3577.5`, PF `1.2357495881383855`, MAR `1.4460835971947001`.

Fixed-config mechanics log for best run: `backtest-campaigns/es_prior_lvn_orderflow_rejection/morning_signed_two_sided_lvn_rejection/ES/run1/limited_core_grid_test/fixed_config_core_trade_log.csv`

No WFA, Monte Carlo, incubation, or validation stage was reached.

Results CSV: `backtest-campaigns/es_prior_lvn_orderflow_rejection/campaign_results.csv`
