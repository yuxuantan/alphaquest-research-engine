# vol_norm_trend_1000_two_sided

This variant requires the prior ES trend to clear a volatility-normalized z-score before taking the next RTH intraday trade. The signal uses prior completed RTH closes only, enters on the next bar open, and flattens same day.

Tunable parameters are fixed before testing: two entry parameters, one percent stop, and one fixed-R target.
