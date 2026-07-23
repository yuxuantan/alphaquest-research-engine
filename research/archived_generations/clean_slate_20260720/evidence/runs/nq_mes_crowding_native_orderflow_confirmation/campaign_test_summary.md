# Campaign Test Summary: nq_mes_crowding_native_orderflow_confirmation

Decision: FAIL

All five frozen variants passed limited core but failed limited monkey. No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, frozen validation, acceptance, or candidate reporting.

## Variant Results

- `absret5_1030_notional_signed_window15_pressure_reversal`: FAIL at `limited_monkey_test`; core top net=21155.0; core PF=1.884221525600836; core benchmark pass=56/81; monkey net-beat=0.79475; monkey DD-beat=0.468625; median monkey net=-525.0.
- `absret5_1030_signed_window15_pressure_reversal`: FAIL at `limited_monkey_test`; core top net=24475.0; core PF=1.9827343906846016; core benchmark pass=67/81; monkey net-beat=0.854875; monkey DD-beat=0.663375; median monkey net=-390.0.
- `downside20_1030_signed_window15_pressure_reversal`: FAIL at `limited_monkey_test`; core top net=16060.0; core PF=1.7878341918077016; core benchmark pass=59/81; monkey net-beat=0.882125; monkey DD-beat=0.579375; median monkey net=-435.0.
- `range10_1030_signed_window15_pressure_reversal`: FAIL at `limited_monkey_test`; core top net=20320.0; core PF=1.937701892016613; core benchmark pass=43/81; monkey net-beat=0.799875; monkey DD-beat=0.524625; median monkey net=-527.5.
- `vol20_1030_signed_window15_pressure_reversal`: FAIL at `limited_monkey_test`; core top net=13045.0; core PF=1.5056201550387598; core benchmark pass=53/81; monkey net-beat=0.874; monkey DD-beat=0.739875; median monkey net=-240.0.

No `candidate_strategy_report.md` was created.
