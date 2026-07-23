# Methodology Audit - NQ Halloween Seasonal Premium

Verdict: FAIL. No variant is a candidate strategy.

Scope and timing:
- Five variants were predeclared under one edge: Halloween/Sell-in-May half-year seasonality applied to NQ intraday exposure.
- The signal used only known calendar month and completed 1-minute NQ RTH bars.
- No overnight holding was allowed, even though the original anomaly is commonly measured over longer horizons.
- No NQ rescue, month-definition change, exclusion, or mechanics change was made after results.

Gate outcomes:
- All five variants failed limited core.
- The strongest top row was `summer_afternoon_short_1330`, but only 4/12 combinations were profitable, below the 70% gate.

Rejection rationale:
- The seasonal effect did not survive intraday-only NQ execution and costs across neighboring parameters.
- No variant reached the robustness gates.

Durable artifacts:
- Aggregate summary: `backtest-campaigns/nq_halloween_seasonal_premium/campaign_test_summary.json`
- Results CSV: `backtest-campaigns/nq_halloween_seasonal_premium/campaign_results.csv`
