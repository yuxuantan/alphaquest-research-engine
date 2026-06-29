# Methodology Audit

Verdict: FAIL.

- Campaign mechanics were frozen before PnL testing: completed opening-window VAP levels plus completed-bar signed-volume/footprint absorption or acceptance evidence, next-bar execution, sweep-extreme stop, and cost-adjusted fixed-R target.
- The opening VAP cache was built from local Sierra raw trade price-volume rows and verified with no opening30 levels before 10:00 ET and no opening60 levels before 10:30 ET.
- Pre-PnL density audit approved eight variants under the updated cap because every strict corner exceeded 50 signal sessions per year.
- The unsandboxed staged run completed all 8 x 54 limited-core combinations; the earlier sandboxed `Operation not permitted` artifacts were superseded by real completed core-grid results.
- Aggregate result: 4/432 profitable core combinations, 0 benchmark-passing combinations, 0 Apex rule violations.
- Best top row: `ovap60_poc_reclaim_1500` net 302.5, PF 1.0438564697354114, MAR 0.09474234839420437; still failed `max_consecutive_losses;max_best_day_concentration`.
- No variant reached monkey, WFA, WFA OOS monkey, Monte Carlo, simulated incubation, acceptance OOS, or candidate reporting.
- No candidate_strategy_report.md was created because the campaign failed before promotion.

Research caveat: Sierra footprint and signed-volume fields are completed-bar proxies, not true MBO/order-book sequencing or discretionary tape-reading evidence. The campaign is rejected on its own staged backtest results.
