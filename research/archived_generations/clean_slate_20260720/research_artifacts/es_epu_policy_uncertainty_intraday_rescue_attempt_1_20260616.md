# ES EPU Policy Uncertainty Intraday Rescue Attempt 1 - 2026-06-16

Decision: FAIL.

Scope: `campaigns/es_epu_policy_uncertainty_intraday`.

Rescue rule:
- Each failed original variant received exactly one rescue run.
- Rescue changed only fixed parameters and declared parameter spaces inside the existing modules.
- The EPU availability rule, setup mode, direction, entry time, entry module, stop-loss module, target module, data window, timeframe, costs, fills, sessions, prop rules, and stage criteria were unchanged.

Rescue grids:

| Variant | Entry parameter space | Stop space | Target space |
| --- | --- | --- | --- |
| high_epu_short_1000 | `epu_rank_min=[0.65,0.70,0.75]` | `[0.001,0.0015,0.0025]` | `[1.0,1.5,2.0]` |
| low_epu_long_1030 | `epu_rank_max=[0.35,0.30,0.25]` | `[0.003,0.004,0.006]` | `[0.75,1.0,1.25]` |
| rising_epu_short_1130 | `epu_change_rank_min=[0.50,0.55,0.60]` | `[0.003,0.004,0.006]` | `[1.0,1.5,2.0]` |
| falling_epu_long_1200 | `epu_change_rank_max=[0.35,0.30,0.25]` | `[0.003,0.004,0.006]` | `[0.75,1.0,1.25]` |
| high_epu_ma_short_1330 | `epu_ma_rank_min=[0.65,0.70,0.75]` | `[0.001,0.0015,0.0025]` | `[1.0,1.5,2.0]` |

Outcome:
- All five rescues failed `limited_core_grid_test`.
- Best rescue: `low_epu_long_1030/rescue1`.
- Best rescue profitable-combo rate: `0.4074074074074074`, below the required `0.70`.
- Best rescue benchmark-passing combinations: `0`.
- Best rescue top net: `2170.625`.
- Best rescue top PF: `1.1913709499669385`.
- Best rescue top trades: `99`.
- No run reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, or frozen validation.

Conclusion:
- The lagged Daily U.S. EPU intraday edge is rejected under the current methodology.
- No candidate strategy report should be created.
