# ES Default-Spread Orderflow Risk-Premium Density Audit - 2026-06-20

Decision: eligible for authored campaign testing.

This is a pre-PnL density/history/duplicate screen. It did not inspect trade
outcomes, stops, targets, grid results, WFA, or Monte Carlo outputs.

## Data

- ES source: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Credit source: free FRED CSVs downloaded from official FRED graph endpoints for Moody's seasoned Aaa and Baa corporate bond yields:
  - `data/external/fred_default_spread/fred_daaa_aaa_corporate_yield.csv`
  - `data/external/fred_default_spread/fred_dbaa_baa_corporate_yield.csv`
- Feature builder: `tools/build_es_default_spread_features.py`
- Feature output: `data/external/es_default_spread_features_20110103_20260609.csv`
- Availability rule: latest Aaa/Baa observation on or before `session_date - 2 business days`
- Valid feature coverage: 2011-01-03 to 2026-06-09, 3817 valid ranked rows
- Limited-core reference period: 2011-02-22 to 2012-09-06

## Density Results

| proposed variant | slots | full signals | full signals/year | limited signals | limited signals/year |
|---|---:|---:|---:|---:|---:|
| high_spread_signed_long_1230 | 10:00, 10:30, 11:30, 12:30 | 812 | 52.58 | 128 | 83.19 |
| high_spread_large10_long_1230 | 10:00, 10:30, 11:30, 12:30 | 781 | 50.57 | 121 | 78.64 |
| widening_spread_signed_short_1230 | 10:00, 10:30, 11:30, 12:30 | 813 | 52.64 | 94 | 61.09 |
| tightening_spread_signed_long_1130 | 10:00, 10:30, 11:30 | 835 | 54.07 | 78 | 50.69 |
| two_sided_spread_change_large10_1130 | 10:00, 10:30, 11:30 | 1510 | 97.77 | 160 | 103.99 |

All five proposed variants clear the 50 trades/year plausibility screen in both
the full sample and the limited-core reference period.

## Duplicate Check

Active duplicate checks ignore `_archived`.

This is related to, but distinct from, `es_ofr_financial_stress_intraday`:

- OFR campaign: composite systemic stress index and subcomponent stress states, mostly short-side, using OFR's two-business-day lag.
- This campaign: Moody's Aaa/Baa default-spread state from free FRED history, with 252-day ranks, conservative two-business-day lag, and mandatory completed ES price/orderflow confirmation.

The short BAML OAS file under `data/external/es_credit_spread_features_20110103_20260609.csv`
is not used because ranked coverage begins only in September 2023 and cannot support the
4-year IS plus 1-year OOS WFA methodology.

## Caveats

- FRED corporate-yield observations are daily macro/credit proxies, not intraday tradable quotes.
- A two-business-day availability lag is conservative but does not model exact historical FRED release timestamps.
- Default-spread risk premia may be slow-moving and may not transfer to same-day ES RTH returns.
- Same-bar stop/target conflicts must remain pessimistic because no tick path is used.
