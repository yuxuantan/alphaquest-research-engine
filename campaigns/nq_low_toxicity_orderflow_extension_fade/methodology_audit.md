# NQ Low-Toxicity Orderflow Extension Fade Methodology Audit

Verdict: FAIL.

The campaign was rejected before staged PnL. The density audit counted deterministic entry opportunities on prepared five-minute NQ Sierra orderflow bars across the declared entry-parameter grid; no stop/target outcomes, trade net, benchmark rows, WFA, Monte Carlo, simulated incubation, or acceptance OOS were inspected.

Rejected before staged NQ PnL: 2/45 declared entry-grid rows failed the 50 signals/year limited-core density gate. The three-slot long, three-slot short, and two-slot late balanced variants cleared full-history, limited-core, and latest-252-session density, but the two-slot midday and two-slot morning variants each had the rank_threshold=0.25/min_return_ticks=6 corner below 50 signals/year in the limited-core window. Dropping those sparse corners or variants after this screen would be post-result narrowing of the declared five-variant edge. No NQ PnL was inspected.

The density-passing variants are recorded as variant-only manual-review rows in the ledger, but the official campaign remains failed because one campaign must carry all five predeclared variants. Selecting only the dense rows after seeing this screen would violate the declared research protocol.

No candidate strategy report was created.
