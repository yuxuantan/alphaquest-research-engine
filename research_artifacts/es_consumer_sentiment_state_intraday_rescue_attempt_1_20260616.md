# ES Consumer Sentiment State Intraday Rescue Attempt 1 - 2026-06-16

Decision: FAIL.

Scope: `campaigns/es_consumer_sentiment_state_intraday`.

Rescue rule:
- Each failed original variant received exactly one rescue run.
- Rescue changed only fixed parameters and declared parameter spaces inside the existing modules.
- The UMCSENT availability rule, setup mode, direction, entry time, entry module, stop-loss module, target module, data window, timeframe, costs, fills, sessions, prop rules, and stage criteria were unchanged.

Rescue grids:

| Variant | Entry parameter space | Stop space | Target space |
| --- | --- | --- | --- |
| low_sentiment_long_1000 | `sentiment_rank_max=[0.35,0.30,0.25]` | `[0.003,0.004,0.006]` | `[0.75,1.0,1.25]` |
| high_sentiment_short_1030 | `sentiment_rank_min=[0.45,0.50,0.55]` | `[0.001,0.0015,0.0025]` | `[1.0,1.5,2.0]` |
| rising_sentiment_long_1130 | `sentiment_change_rank_min=[0.50,0.55,0.60]` | `[0.003,0.004,0.006]` | `[0.75,1.0,1.25]` |
| falling_sentiment_short_1200 | `sentiment_change_rank_max=[0.35,0.30,0.25]` | `[0.003,0.004,0.006]` | `[1.0,1.5,2.0]` |
| low_sentiment_ma_long_1330 | `sentiment_ma_rank_max=[0.35,0.30,0.25]` | `[0.003,0.004,0.006]` | `[0.75,1.0,1.25]` |

Outcome:
- All five rescues failed `limited_core_grid_test`.
- Best rescue: `high_sentiment_short_1030/rescue1`.
- Best rescue profitable-combo rate: `0.07407407407407407`, below the required `0.70`.
- Best rescue benchmark-passing combinations: `0`.
- Best rescue top net: `140.0`.
- Best rescue top PF: `1.1454545454545455`.
- Best rescue top trades: `12`, below the trade-count gate.
- No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation.

Conclusion:
- The lagged University of Michigan consumer-sentiment intraday edge is rejected under the current methodology.
- No candidate strategy report should be created.
