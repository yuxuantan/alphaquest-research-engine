# ES opening-drive VWAP orderflow pullback campaign summary

Decision: FAIL

All five original variants failed limited_core_grid_test with 0.0 profitable-combo rate. Each failed variant received exactly one parameter-space/fixed-parameter rescue preserving the opening-drive VWAP pullback/reclaim plus aligned aggregate-orderflow mechanic. All five rescues also failed limited_core_grid_test with 0.0 profitable-combo rate and negative top-combo net profit; no run reached limited monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best run: `drive30_large20_pullback_1230/rescue1` top net `-747.5`, PF `0.8987127371273713`, trades/year `60.11494167194664`.

No candidate strategy report was created.
