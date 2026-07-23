# es_high_semivariance_mes_trend_pullback_crowding Campaign Test Summary

Decision: FAIL

All five originals failed before WFA. The allowed stop/target-widen rescue was run once for every failed variant; three rescues failed limited_core_grid_test, and the midday/afternoon rescues passed limited core but failed limited_monkey_test. No run reached WFA, Monte Carlo, simulated incubation, frozen validation, or candidate reporting.

Best original: `midday60_notional_high_downside_window_1430/run1` with profitable-combo rate `0.14814814814814814`, benchmark-passing combinations `4/54`, top net `6772.5`, PF `1.1705275084980487`, MAR `1.6069036998484771`, and trades/year `147.227996812312`.

Best rescue: `afternoon60_notional_high_downside_window_1530/stop_target_widen_rescue1` with profitable-combo rate `0.8888888888888888`, benchmark-passing combinations `33/54`, top net `22503.75`, PF `1.5694989244590662`, MAR `3.7326684044050786`, and trades/year `124.69594874446213`. It failed limited monkey with net-profit beat rate `0.8733333333333333` and max-drawdown beat rate `0.76` versus the `0.90` gate.

Fixed-config core trade logs and equity curves were written for all originals and rescues. No `candidate_strategy_report.md` was created.
