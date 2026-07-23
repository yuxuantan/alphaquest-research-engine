# NQ MES Participation Crowding Reversion Density Audit - 2026-06-22

Purpose: count raw entry signals before any PnL inspection so sparse parameter spaces are rejected before staged testing rather than interpreted as expectancy evidence.

Method:
- Uses authored configs under `campaigns/nq_mes_participation_crowding_reversion/variants/*/config.yaml`.
- Expands declared `core_grid.parameters` exactly as authored.
- Prepares the same one-minute RTH NQ/MES participation cache as the staged runner with `prepare_data`.
- Applies entry conditions vectorially: prior same-clock MES participation rank, completed NQ return over the lookback, fixed decision checkpoint or predeclared first-signal window, and one signal per day.
- Does not inspect fills, stops, targets, trade PnL, equity curves, or future data.

Limited-core window: `2021-07-13` to `2022-03-28`. Full core-history window: `2019-05-06` to `2026-06-12`.

Initial fixed-checkpoint density rejection preserved at `research_artifacts/nq_mes_participation_crowding_reversion_initial_density_rejected_20260622.md`.

Density guideline: every variant should have at least 50 limited-core signals/year before staged testing.

| variant | window | combos | min signals | median signals | max signals | min signals/year | median signals/year | max signals/year | density pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| afternoon_trade_down_reversal_long_1400 | limited_core_window | 54 | 40 | 49 | 61 | 56.41 | 69.10 | 86.02 | true |
| afternoon_trade_down_reversal_long_1400 | full_available_history | 54 | 338 | 422 | 509 | 47.57 | 59.40 | 71.64 | false |
| afternoon_trade_up_reversal_short_1400 | limited_core_window | 54 | 67 | 85 | 99 | 94.49 | 119.87 | 139.61 | true |
| afternoon_trade_up_reversal_short_1400 | full_available_history | 54 | 517 | 725 | 920 | 72.77 | 102.04 | 129.49 | true |
| midday_notional_two_sided_reversal_1200 | limited_core_window | 81 | 40 | 60 | 76 | 56.41 | 84.61 | 107.18 | true |
| midday_notional_two_sided_reversal_1200 | full_available_history | 81 | 392 | 589 | 761 | 55.17 | 82.90 | 107.11 | true |
| morning_notional_down_reversal_long_1030 | limited_core_window | 81 | 40 | 48 | 52 | 56.41 | 67.69 | 73.33 | true |
| morning_notional_down_reversal_long_1030 | full_available_history | 81 | 291 | 383 | 455 | 40.96 | 53.91 | 64.04 | false |
| morning_notional_up_reversal_short_1030 | limited_core_window | 54 | 65 | 91 | 111 | 91.67 | 128.33 | 156.54 | true |
| morning_notional_up_reversal_short_1030 | full_available_history | 54 | 637 | 875 | 1038 | 89.66 | 123.16 | 146.10 | true |

CSV: `research_artifacts/nq_mes_participation_crowding_reversion_density_audit_20260622.csv`
