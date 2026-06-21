# ES Variance-Ratio Orderflow Regime Density Audit

Date: 2026-06-19

No PnL, stop, target, or trade outcome fields were evaluated. This audit only counted completed-bar signals from the predeclared entry parameter grid, grouped by session and capped at the configured max trades per day.

## afternoon_high_vr_signed_continuation_1530

- Entry combinations: 9
- Full-window signals/year: min 47.95, median 126.61, max 214.08
- Limited-core signals/year: min 64.23, median 114.18, max 171.92
- Limited-core period: 2011-02-22 09:30:00-05:00 through 2012-09-06 15:59:00-04:00

## midday_high_vr_large10_continuation_1400

- Entry combinations: 9
- Full-window signals/year: min 130.63, median 215.25, max 301.88
- Limited-core signals/year: min 120.02, median 205.66, max 276.37
- Limited-core period: 2011-02-22 09:30:00-05:00 through 2012-09-06 15:59:00-04:00

## midday_low_vr_large10_reversion_1430

- Entry combinations: 9
- Full-window signals/year: min 234.69, median 341.66, max 409.63
- Limited-core signals/year: min 234.20, median 341.25, max 397.69
- Limited-core period: 2011-02-22 09:30:00-05:00 through 2012-09-06 15:59:00-04:00

## morning_high_vr_signed_continuation_1130

- Entry combinations: 9
- Full-window signals/year: min 8.55, median 28.45, max 84.30
- Limited-core signals/year: min 20.76, median 44.12, max 95.37
- Limited-core period: 2011-02-22 09:30:00-05:00 through 2012-09-06 15:59:00-04:00

## morning_low_vr_signed_reversion_1130

- Entry combinations: 9
- Full-window signals/year: min 7.13, median 27.34, max 83.97
- Limited-core signals/year: min 15.57, median 50.60, max 99.26
- Limited-core period: 2011-02-22 09:30:00-05:00 through 2012-09-06 15:59:00-04:00

## Decision

FAIL for pre-PnL density: minimum full 7.13; minimum limited 15.57.

CSV: `research_artifacts/es_variance_ratio_orderflow_regime_density_audit_20260619.csv`
