# Campaign Test Summary: nq_signed_orderflow_persistence

Decision: FAIL

Terminal stage: pre_pnl_density_screen

Rejected before staged NQ PnL: only 20/45 declared signed-flow entry-grid rows passed the pre-PnL density screen. The weakest declared corners produced 32.77 full-history signals/year, 38.28 limited-core proxy signals/year, and 7 latest-window signals. Narrowing the grid to the passing rows after this density screen would change the declared five-variant edge after observing signal availability, so no staged PnL was run.

No staged PnL, monkey, WFA, Monte Carlo, simulated incubation, acceptance OOS, or candidate report was run.
