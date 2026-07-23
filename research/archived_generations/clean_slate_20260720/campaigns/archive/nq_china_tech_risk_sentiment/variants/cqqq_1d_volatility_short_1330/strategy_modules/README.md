# cqqq_1d_volatility_short_1330

Entry module: `nq_china_tech_risk_sentiment`.

Mechanic: at 13:30 ET, short NQ when prior-business-day absolute CQQQ one-day return ranks in the upper volatility tail.

Timing: ETF features are known from completed daily closes no later than one business day before the NQ session; the NQ signal is evaluated on a completed one-minute RTH bar and entered by the engine on the next bar.
