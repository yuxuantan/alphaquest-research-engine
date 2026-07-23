# NQ Tech Plus Low-Volatility Momentum Density Rejection

Generated on 2026-06-23 before PnL testing.

Composite tested in density only: completed 09:30-10:30 NQ upside momentum, lagged NQ low-volatility gate, and lagged XLK/SPY technology leadership gate. Tech threshold was fixed at rank >= 0.55 to keep the entry grid within two parameters.

| Variant | Signals/year range |
|---|---:|
| range10_tech5d_1030_long | 6.44-16.62 |
| vol20_tech5d_1030_long | 6.44-16.56 |
| absret5_tech5d_1030_long | 6.81-16.38 |
| range10_tech1d_1030_long | 5.88-16.62 |
| range10_attention_1030_long | 6.06-16.69 |

Decision: FAIL before PnL. The composite is too sparse for the staged WFA/prop-rule workflow, with only about 6-17 signals/year across the predeclared density grid.
