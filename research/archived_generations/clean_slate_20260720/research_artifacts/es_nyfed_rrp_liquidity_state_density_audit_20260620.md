# ES NY Fed RRP Liquidity State Density Audit - 2026-06-20

This is a pre-PnL signal-density audit using the lag-one local RRP feature file. It counts at most one possible fixed-time signal per session and does not inspect trade outcomes.

Full window: 2014-08-11 through 2026-05-29. Seeded limited-core window: 2014-09-30 through 2015-12-04.

| Variant | Threshold grid | Full min signals/year | Limited-core min signals/year | Decision |
|---|---:|---:|---:|---|
| `rrp_drain_short_1000` | `>= [0.0, 0.125, 0.25]` | 74.0 | 85.8 | approve for staged testing |
| `rrp_drain_short_1330` | `>= [0.0, 0.125, 0.25]` | 74.0 | 85.8 | approve for staged testing |
| `rrp_drain_short_1500` | `>= [0.0, 0.125, 0.25]` | 74.0 | 85.8 | approve for staged testing |
| `rrp_release_long_1000` | `<= [0.0, -0.125, -0.25]` | 75.5 | 119.8 | approve for staged testing |
| `rrp_release_long_1330` | `<= [0.0, -0.125, -0.25]` | 75.5 | 119.8 | approve for staged testing |
