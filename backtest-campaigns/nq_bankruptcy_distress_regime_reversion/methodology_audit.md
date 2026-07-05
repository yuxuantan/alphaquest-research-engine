# NQ Bankruptcy Distress Regime Reversion Methodology Audit

Verdict: FAIL.

This campaign tested exactly five NQ variants expressing one edge: bankruptcy/default-distress regime conditioned intraday reversion after prior-session directional moves. The source was the corrected ES bankruptcy-distress campaign, ported before any NQ PnL inspection. Rescue was disabled.

No-lookahead review: the U.S. Courts F-2 feature file is selected by `effective_date` on or before the session date, so unreleased future quarters are unavailable to the signal. Each signal uses completed 5-minute bars, prior recorded RTH session closes, and next-bar-open entry. No final session high/low, final VWAP, future return, future volume profile, or unreleased bankruptcy value is used.

Pre-PnL gate: the local NQ bar cache had complete signal and entry bars for all declared rows, but the declared bankruptcy thresholds were too sparse. Only 5/15 threshold rows passed the density gate. Every variant had only 1/3 threshold rows passing; the weakest full-history density was 12.928303 signals/year, the weakest latest-1260 density was 20.741617 signals/year, and the weakest latest-252 count was 0.

Scientific-integrity decision: staged PnL was not run. Dropping the sparse thresholds, retaining only the passing threshold in each variant, or changing feature timing after this screen would be post-result narrowing of the predeclared five-variant edge. The campaign is closed as failed.
