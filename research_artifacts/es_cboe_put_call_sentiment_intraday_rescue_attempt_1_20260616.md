# ES Cboe Put/Call Sentiment Rescue Attempt 1 - 2026-06-16

Decision: FAIL.

Scope: all five original variants in `es_cboe_put_call_sentiment_intraday`
failed. Each failed variant received exactly one parameter-space-only rescue.
No rescue changed the core option-volume put/call sentiment mechanic, Cboe
strict-prior-date availability rule, setup mode, direction, entry time, entry
module, stop module, target module, timeframe, data window, costs, fill
assumptions, forced-flatten rule, or validation gates.

| Variant | Rescue terminal stage | Core profitable rate | Top net | Top PF | Top trades | Monkey result |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `low_equity_pc_long_1000` | `limited_core_grid_test` | `0.037037037037037035` | `85.0` | `1.005031074282332` | `108` | Not reached |
| `high_equity_pc_short_1030` | `limited_core_grid_test` | `0.6296296296296297` | `3870.0` | `1.138560687432868` | `146` | Not reached |
| `falling_total_pc_long_1130` | `limited_monkey_test` | `1.0` | `5652.5` | `1.353060587133042` | `117` | Failed: random monkey profitable rate `0.19666666666666666`, median net `-2727.5`; trade-path stress profitable rate `0.98` and one-tick-worse profitable |
| `rising_total_pc_short_1200` | `limited_core_grid_test` | `0.5925925925925926` | `4730.0` | `1.2826411711980878` | `114` | Not reached |
| `high_total_vs_equity_pc_short_1330` | `limited_monkey_test` | `0.8888888888888888` | `4675.0` | `1.2595780122154359` | `135` | Failed: random monkey profitable rate `0.06666666666666667`, median net `-3923.75`, one-tick-worse stress not profitable |

Outcome:
- Three rescues failed `limited_core_grid_test`.
- Two rescues passed core but failed `limited_monkey_test`.
- No run reached WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or
  frozen validation.
- No `candidate_strategy_report.md` was created.

Conclusion: the active Cboe put/call sentiment edge is rejected under the
current methodology and should not be relaunched under a new active name without
a materially different thesis approved before testing.
