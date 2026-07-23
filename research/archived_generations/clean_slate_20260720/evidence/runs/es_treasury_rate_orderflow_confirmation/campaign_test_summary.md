# es_treasury_rate_orderflow_confirmation Campaign Test Summary

Decision: FAIL

All five original variants failed limited core. All five failed variants received exactly one parameter-space-only rescue. TP was not adjusted because every `target_r_multiple` was already at least `1.0R`; no sub-1R target exists in the original or rescue grids.

Best original: `teny_1d_large10_rate_confirmation_1530/run1` with profitable-combo rate `0.0`, benchmark-passing combinations `0/81`, top net `-1130.0`, PF `0.8375853395616242`, MAR `-0.35126421938203733`, trades/year `59.25980122823977`.

Best rescue: `curve_1d_signed_rate_confirmation_1530/rescue1` with profitable-combo rate `0.0`, benchmark-passing combinations `0/81`, top net `-15.0`, PF `0.9951417004048583`, MAR `-0.007965771559462615`, trades/year `24.29954639637117`.

Every rescue failed the limited core gate before monkey/WFA. No run reached Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
