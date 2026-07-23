# ES VWAP deviation orderflow reversion campaign summary

Decision: FAIL

All five original variants failed limited_core_grid_test with 0.0 profitable-combo rate. Each failed variant received exactly one parameter-space/fixed-parameter rescue preserving the VWAP-deviation counterflow reversion mechanic. All five rescues also failed limited_core_grid_test with 0.0 profitable-combo rate and negative top-combo net profit; no run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best run: `midday_signed_counterflow_1400/rescue1` top net `-1858.75`, PF `0.39882757226601984`, trades/year `60.450316066562436`.

No candidate strategy report was created.
