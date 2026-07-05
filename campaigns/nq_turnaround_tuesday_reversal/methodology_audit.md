# NQ Turnaround Tuesday Reversal Methodology Audit

Verdict: FAIL before staged PnL.

The campaign tested exactly five predeclared Tuesday-only reversal variants. Signals require completed prior RTH closes recorded before the Tuesday signal session; current-session close, future high/low, final VWAP, and future volume are not used.

Duplicate-edge review: this was allowed only as a conditional calendar/reversal edge. It is not the same as unconditional day-of-week seasonality or raw daily short-term reversal, but the density screen failed before any PnL was inspected.

Density gate: every declared entry row had to clear at least 40 signals/year in full history, at least 40 signals/year in the limited-core proxy window, and at least 40 signals in the latest 252 sessions. The best full-history density was below 22 signals/year and the best latest-252 count was 32, so no staged PnL was run.
