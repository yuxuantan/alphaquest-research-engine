# NQ NY Fed RRP Liquidity State Campaign Summary

Verdict: FAIL

All five predeclared RRP drain variants failed the staged validation flow. The 10:00 short passed limited core but failed limited monkey robustness: core net-profit beat rate was 0.89775 versus the 0.90 threshold, and max-drawdown beat rate was 0.7525 versus 0.90. The 11:30, 13:30, 14:30, and 15:00 variants failed limited core.

No candidate_strategy_report.md was created because no variant reached promotion criteria. No NQ rescue was authorized or used.

Key artifacts:

- `backtest-campaigns/nq_nyfed_rrp_liquidity_state/campaign_test_summary.json`
- `backtest-campaigns/nq_nyfed_rrp_liquidity_state/campaign_results.csv`
- `campaigns/nq_nyfed_rrp_liquidity_state/methodology_audit.md`
