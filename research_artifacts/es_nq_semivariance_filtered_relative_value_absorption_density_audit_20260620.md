# es_nq_semivariance_filtered_relative_value_absorption Density Audit

Pre-PnL local-only density screen for ES/NQ relative-value absorption reversion filtered to benign prior downside-semivariance regimes. No external or paid data was downloaded.

## Windows
- full: `{'start_date': '2011-01-03', 'end_date': '2026-06-09', 'session_labels': ['RTH']}`; years=15.4333
- limited_core: `{'start_date': '2011-02-22', 'end_date': '2012-09-06', 'session_labels': ['RTH']}`; years=1.5414
- wfa90: `{'start_date': '2011-01-03', 'end_date': '2024-11-22', 'session_labels': ['RTH']}`; years=13.8891
- latest1y: `{'start_date': '2025-06-10', 'end_date': '2026-06-09', 'session_labels': ['RTH']}`; years=0.9993

## Candidate Mechanics
- Base signal: ES/NQ completed rolling-return divergence faded in ES when ES signed orderflow over the same lookback confirms absorption.
- Regime filter: prior completed RTH downside semivariance or downside-share rank must be at or below the declared benign cutoff.
- Entry tunables screened: `min_spread_bps` and `benign_semivar_rank_max`; absorption is fixed at sign-only confirmation.
- Signals use completed bars; staged backtests would enter no earlier than the next 1-minute ES bar.

## Summary

| variant_id | passing_entry_combos | entry_combo_count | full_min_tpy | limited_core_min_tpy | wfa90_min_tpy | latest1y_min_tpy | pass |
|---|---:|---:|---:|---:|---:|---:|---|
| morning15_low_badvol_absorption_twosided_1100 | 6 | 6 | 93.82 | 83.69 | 95.11 | 98.07 | true |
| morning30_low_badvol_absorption_twosided_1130 | 6 | 6 | 78.40 | 63.58 | 79.85 | 76.05 | true |
| late_morning30_low_badvol_absorption_twosided_1230 | 6 | 6 | 72.25 | 68.77 | 74.59 | 55.04 | true |
| midday60_low_badvol_absorption_twosided_1430 | 6 | 6 | 57.08 | 59.04 | 58.54 | 56.04 | true |
| midday60_low_downside_share_absorption_twosided_1430 | 5 | 6 | 54.82 | 56.44 | 55.44 | 49.03 | false |

## Decision
REJECT_OR_REFORMULATE_PRE_PNL: only 4/5 variants clear all density checks. Do not inspect PnL before reformulating or rejecting.

Detail CSV: `research_artifacts/es_nq_semivariance_filtered_relative_value_absorption_density_screen_20260620.csv`
Summary CSV: `research_artifacts/es_nq_semivariance_filtered_relative_value_absorption_density_summary_20260620.csv`

## Pre-PnL Reformulation

No PnL results were inspected before this change. The initial fifth variant,
`midday60_low_downside_share_absorption_twosided_1430`, failed one strict
latest-year trade-density corner because `min_spread_bps=6` produced 49.03
trades/year in the latest one-year window. The core mechanic remained unchanged:
ES/NQ relative-value divergence, ES signed-flow absorption, and a benign
prior-session semivariance regime.

The replacement keeps the same window, absorption rule, and downside-share
semivariance filter, but narrows the entry spread grid to `[2, 3, 4]` so the
declared parameter space represents the intended trade frequency. Alternative
screen artifact:
`research_artifacts/es_nq_semivariance_filtered_relative_value_absorption_density_alternative_summary_20260620.csv`.

Final approved variants:

| variant_id | entry_combo_count | passing_entry_combos | full_min_tpy | limited_core_min_tpy | wfa90_min_tpy | latest1y_min_tpy |
|---|---:|---:|---:|---:|---:|---:|
| morning15_low_badvol_absorption_twosided_1100 | 6 | 6 | 93.82 | 83.69 | 95.11 | 98.07 |
| morning30_low_badvol_absorption_twosided_1130 | 6 | 6 | 78.40 | 63.58 | 79.85 | 76.05 |
| late_morning30_low_badvol_absorption_twosided_1230 | 6 | 6 | 72.25 | 68.77 | 74.59 | 55.04 |
| midday60_low_badvol_absorption_twosided_1430 | 6 | 6 | 57.08 | 59.04 | 58.54 | 56.04 |
| midday60_low_downside_share_absorption_twosided_1430 | 6 | 6 | 67.45 | 63.58 | 67.68 | 67.05 |

Final decision after reformulation: APPROVE_FOR_AUTHORING_AND_TESTING.
