# NQ Turn-of-Year Effect Methodology Audit

Verdict: FAIL.

The campaign was rejected before staged PnL. The density audit counted only deterministic calendar signal opportunities on prepared one-minute NQ bars; no stop/target outcomes, trade net, benchmark rows, WFA, Monte Carlo, simulated incubation, or acceptance OOS were inspected.

Rejected before staged NQ PnL: all five declared turn-of-year variants failed the 50 signals/year density standard across full history, limited-core reference, and latest-252-session checks. Best full-history density was 6.799867 signals/year, best limited-core density was 4.533245 signals/year, and best latest-252 count was 7. Faithfully widening the last-five-December/first-two-January rule enough to pass would change the edge into a broader calendar strategy. No NQ PnL was inspected.

The source edge is distinct from the existing NQ turn-of-month, Halloween half-year, and weekday-bias campaigns, but its faithful annual window is structurally too sparse for the repo's current 50 trades/year downstream evidence gates.

No candidate strategy report was created.
