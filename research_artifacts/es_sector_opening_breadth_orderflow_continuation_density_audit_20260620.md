# ES Sector Opening Breadth Orderflow Continuation Density Audit - 2026-06-20

Decision: eligible for authored campaign testing.

This is a pre-PnL signal-density and duplicate-mechanics screen. It did not inspect
trade outcomes, stops, targets, grid results, WFA, or Monte Carlo outputs.

## Data

- ES source: `data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet`
- Sector ETF source: existing local Yahoo daily CSVs in `data/external/yahoo_sector_etfs/`
- Feature output: `data/external/es_sector_opening_breadth_features_20110103_20260609.csv`
- Full density period: 2010-12-29 to 2026-06-09, 3819 ES sessions, about 15.44 years
- Limited-core reference period: 2011-02-22 to 2012-09-06, about 1.54 years
- Lookahead rule: same-day ETF `Open` is treated as available only after the 09:30 ET cash open; all ES confirmation uses completed RTH bars ending before the configured signal timestamp.

## Density Results

| proposed variant | slots | full signals | full signals/year | limited signals | limited signals/year |
|---|---:|---:|---:|---:|---:|
| broad_up_early_signed_long_1000 | 10:00, 10:30 | 943 | 61.06 | 95 | 61.74 |
| broad_down_morning_signed_short_1130 | 10:00, 10:30, 11:30 | 795 | 51.48 | 100 | 64.99 |
| cyclical_up_morning_signed_long_1130 | 10:00, 10:30, 11:30 | 1020 | 66.04 | 104 | 67.59 |
| riskoff_cycdown_midday_signed_short_1230 | 10:00, 10:30, 11:30, 12:30 | 780 | 50.50 | 107 | 69.54 |
| broad_two_sided_morning_large10_1130 | 10:00, 10:30, 11:30 | 1789 | 115.84 | 200 | 129.98 |

All five proposed variants clear the 50 trades/year plausibility screen in both
the full sample and the limited-core reference period.

## Duplicate Check

Active duplicate checks ignore `_archived`.

This edge is distinct from:

- `es_sector_rotation_risk_appetite`, which used lagged daily sector ETF closes as a pre-session state and fixed-time entries.
- `es_sector_rotation_orderflow_pullback`, which used lagged sector rankings plus ES VWAP/EMA pullback triggers.
- Pure ES orderflow continuation, VWAP pullback, ORB, and opening-gap campaigns, which did not use same-day cash sector opening breadth.

This campaign remains related to sector-rotation research, so it should be
treated as a bounded composite and not evidence for a standalone sector edge.

## Caveats

- Yahoo ETF raw `Open` and prior raw `Close` are no-cost research proxies and are not a point-in-time exchange-grade archive.
- Ex-dividend ETF opens can create sector gaps that may not represent pure risk appetite.
- The edge must fail closed if results are concentrated in a small number of regimes or if same-day ETF open availability proves unsuitable for execution.
