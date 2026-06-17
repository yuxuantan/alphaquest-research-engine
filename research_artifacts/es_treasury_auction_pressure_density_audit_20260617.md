# ES Treasury Auction Pressure Density Audit

Date: 2026-06-17

Data sources:

- Local ES Sierra RTH cache:
  `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Free official FiscalData Treasury Securities Auctions Data API:
  `https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/`

Generated files:

- Raw free FiscalData cache:
  `data/external/treasury_auctions_query_20110101_20260609.csv`
- ES nominal coupon auction calendar:
  `data/external/es_treasury_coupon_auction_sessions_20110103_20260609.csv`
- Builder:
  `tools/build_es_treasury_auction_calendar.py`

No paid data was downloaded. The source is a public government API.

## No-Lookahead Construction

The calendar includes only nominal Treasury `Note` and `Bond` rows where:

- `announcemt_date < auction_date`
- `auction_date` is an ES local RTH session date
- `security_type` is `Note` or `Bond`

The strategy modules are allowed to use only the auction session date and broad
coupon scope/count fields. Auction outcomes such as high yield, bid-to-cover,
tails, dealer awards, total tenders, and total accepted are not signal inputs.

## Density

Calendar output:

- Rows: 1,324 auction sessions
- Date range: 2011-01-11 through 2026-06-09
- Event density: 85.9 all-coupon auction days/year
- Note days: 1,036, or 67.2/year
- Bond days: 293, or 19.0/year

Decision:

- All-coupon variants are density-eligible.
- Note-only variants are density-eligible.
- Bond-only variants are not density-eligible as standalone variants under the
  >=50 trades/year rule.

## Campaign Eligibility

`es_treasury_auction_pressure` is eligible as a campaign if all variants use
all-coupon or note-only scopes. It is distinct from
`es_treasury_rate_shock_intraday`, which tested lagged yield/curve movements
rather than the announced auction-supply event calendar.
