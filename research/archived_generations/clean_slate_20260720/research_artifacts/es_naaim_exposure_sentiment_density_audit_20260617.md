# ES NAAIM Exposure Sentiment Density Audit - 2026-06-17

## Data

- NAAIM workbook: `data/external/naaim_exposure_index_20260610.xlsx`
- Feature builder: `tools/build_es_naaim_exposure_features.py`
- Feature file: `data/external/es_naaim_exposure_features_20110103_20260609.csv`
- ES sessions: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Availability rule: first ES RTH session at least two business days after the NAAIM observation date.
- Output rows: 805 weekly signal sessions from 2011-01-03 through 2026-06-05.

## Signal Density

| setup_mode | eligible signals | annualized signals/year | first signal | last signal |
|---|---:|---:|---|---|
| `level_median_contrarian` | 805 | 52.21 | 2011-01-03 | 2026-06-05 |
| `level_rank_contrarian` | 805 | 52.21 | 2011-01-03 | 2026-06-05 |
| `change_sign_contrarian` | 805 | 52.21 | 2011-01-03 | 2026-06-05 |
| `zscore_sign_contrarian` | 805 | 52.21 | 2011-01-03 | 2026-06-05 |
| `ma_distance_contrarian` | 805 | 52.21 | 2011-01-03 | 2026-06-05 |

## Eligibility Decision

Eligible to test as a campaign, but borderline on density. The edge is weekly,
so all variants must remain two-sided and must not add filters that reduce the
signal count below the 50 trades/year gate.

## Duplicate-Edge Check

Active archived tests are ignored per user instruction. Active campaign scan
found related sentiment/positioning campaigns but no active NAAIM exposure
campaign. This is not a duplicate of:

- `es_consumer_sentiment_state_intraday`: monthly consumer survey sentiment.
- `es_cboe_put_call_sentiment_intraday`: option-volume put/call sentiment.
- `es_finra_margin_leverage`: monthly margin debt/free-credit leverage state.
- `es_cboe_vix_level_state_intraday`, `es_vvix_tail_risk_intraday`, and related
  Cboe campaigns: volatility or tail-risk states, not active-manager exposure.

The campaign remains in the broad sentiment/positioning family, so it should be
treated as an incremental active-manager-exposure test, not independent evidence
that generic sentiment already works on ES.
