# absret5_1030_notional_signed_window15_pressure_reversal

At 10:30 ET, fade a larger completed NQ 15-minute trend-pullback when MES notional-equivalent participation crowding is elevated, prior NQ trend is opposite the pullback, lagged absret5 volatility is not extreme, and completed native NQ 15-minute signed flow confirms pullback pressure.

Declared before PnL testing. Entry grid: share_rank_min [0.35, 0.45, 0.55], min_orderflow_imbalance [0.0, 0.005, 0.01]. Stop grid: [0.003, 0.004, 0.006]. Target grid: [1.5, 2.0, 2.5].
