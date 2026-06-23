# NQ Pivot/MES Native Orderflow Confirmation Density Audit

Date: 2026-06-23

Pre-PnL signal-density screen only. No PnL, stop/target outcome, WFA, monkey, or trade result was inspected.

Mechanic screened: existing completed pivot-filtered MES crowding signal, then wait for the first pivot/MES signal in the declared window whose completed 30-minute native NQ large-trade signed-flow imbalance agrees with the proposed fade direction. Entry remains next-bar open or later under the staged engine.

Decision: PASS for the selected five variants. Every selected entry-grid corner clears 50 signals/year over 2019-05-06 through 2026-06-12.

## Variant Summary

| variant_id | min_signals_per_year | median_signals_per_year | max_signals_per_year | min_signals | max_signals |
| --- | ---: | ---: | ---: | ---: | ---: |
| morning_notional_large10_first_confirmed_reversal_window_1130 | 66.716185 | 79.102312 | 90.362428 | 474 | 642 |
| morning_notional_large20_first_confirmed_reversal_window_1130 | 63.338150 | 75.302023 | 86.843642 | 450 | 617 |
| afternoon_trade_large10_first_confirmed_reversal_window_1500 | 60.523121 | 73.472254 | 80.932081 | 430 | 575 |
| late_morning_trade_large10_first_confirmed_reversal_window_1200 | 54.470809 | 65.449422 | 74.457514 | 387 | 529 |
| late_morning_trade_large20_first_confirmed_reversal_window_1200 | 51.655780 | 62.634393 | 70.657225 | 367 | 502 |

## Controls

- Counts use completed RTH 1-minute rows only.
- Pivot bias is computed with the same completed-pivot state machine used by `market_structure_filtered_entry`.
- The base MES participation module uses `return_column_prefix: nq` from the source NQ campaign configs.
- `consume_unconfirmed_base_signal` is fixed to `false`: unconfirmed pivot/MES candidates are vetoed and the variant waits for the first confirmed candidate in the same declared signal window.
- Orderflow mode/window/threshold is fixed per variant; no PnL-driven orderflow threshold tuning is used.

Detailed CSV: `research_artifacts/nq_pivot_mes_orderflow_confirmation_density_audit_20260623.csv`
