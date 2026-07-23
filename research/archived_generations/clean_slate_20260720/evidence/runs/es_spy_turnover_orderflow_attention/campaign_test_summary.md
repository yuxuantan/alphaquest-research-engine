# es_spy_turnover_orderflow_attention Campaign Test Summary

Decision: FAIL

All five original variants failed limited core. All five failed variants received exactly one parameter-space-only rescue. TP was not adjusted because every `target_r_multiple` was already at least `1.0R`; no sub-1R target exists in the original or rescue grids.

Best original: `spy_5d_volume_attention_continuation_1530/run1` with profitable-combo rate `0.38271604938271603`, benchmark-passing combinations `13/81`, top net `2355.0`, PF `1.1702204553668232`, MAR `0.5894761822531764`, trades/year `67.9285940478482`.

Best rescue: `spy_3d_absret_attention_continuation_1530/rescue1` with profitable-combo rate `0.9629629629629629`, benchmark-passing combinations `63/81`, top net `4900.0`, PF `1.330522765598651`, MAR `2.7292390054229503`, trades/year `78.77600724132766`.

The deepest-progressing rescue was `spy_3d_absret_attention_continuation_1530/rescue1`: it passed limited core and limited monkey, then failed WFA by early exit with stitched OOS PF `0.9450324342779105`, MAR `-0.16161731136310653`, trades/year `52.17242192103712`, net profit `-805.0`, and total trades `101`.

The `spy_5d_volume_attention_continuation_1530/rescue1` run passed limited core but failed limited monkey/stress because max-drawdown robustness was `0.86` against the `0.90` threshold and one-tick-worse net profit was `-560.0`.

No run reached Monte Carlo, simulated incubation, frozen validation, or candidate reporting.
