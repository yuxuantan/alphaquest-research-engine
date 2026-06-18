# ES trend-filtered prior-session breakout orderflow density audit - 2026-06-18

This is a pre-PnL signal-density audit. It counts entry-module signals only and does not inspect trade PnL, stops, targets, or equity curves.

Preliminary rejected formulation: fresh first-break and retest variants were rejected before staged PnL because all five variants produced only 5.39 to 36.39 signals/year on the limited-core window.

Retained formulation: completed prior-session high/low hold/acceptance with fixed completed-bar trend alignment and same-bar aggregate orderflow confirmation.

Limited-core benchmark subset: `{'start_date': '2011-02-22', 'end_date': '2012-09-06', 'session_labels': ['RTH']}`.

| Variant | Window | Min signals/year | Max signals/year | Min raw signals | Verdict |
|---|---|---:|---:|---:|---|
| `all_day_large10_trend_hold_two_sided` | `full_history` | 181.62 | 193.24 | 2751 | PASS density |
| `all_day_large10_trend_hold_two_sided` | `limited_core_window` | 191.36 | 202.81 | 284 | PASS density |
| `all_day_signed_high_volume_trend_hold_two_sided` | `full_history` | 140.62 | 145.05 | 2130 | PASS density |
| `all_day_signed_high_volume_trend_hold_two_sided` | `limited_core_window` | 161.04 | 164.41 | 239 | PASS density |
| `all_day_signed_trend_hold_two_sided` | `full_history` | 188.88 | 194.23 | 2861 | PASS density |
| `all_day_signed_trend_hold_two_sided` | `limited_core_window` | 196.75 | 204.16 | 292 | PASS density |
| `first_half_large10_trend_hold_two_sided` | `full_history` | 161.42 | 176.47 | 2445 | PASS density |
| `first_half_large10_trend_hold_two_sided` | `limited_core_window` | 173.84 | 188.66 | 258 | PASS density |
| `first_half_signed_trend_hold_two_sided` | `full_history` | 171.72 | 177.33 | 2601 | PASS density |
| `first_half_signed_trend_hold_two_sided` | `limited_core_window` | 182.60 | 189.34 | 271 | PASS density |

Overall pre-PnL density decision: `PASS`.

CSV: `research_artifacts/es_trend_filtered_prior_session_breakout_orderflow_density_audit_20260618.csv`
