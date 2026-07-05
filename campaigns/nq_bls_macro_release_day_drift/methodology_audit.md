# Methodology Audit: nq_bls_macro_release_day_drift

This campaign is a pre-PnL NQ port of `es_bls_macro_release_day_drift`. The five variants preserve the original ES source release-date mechanics, release-type sets, setup modes, entry times, stop module, target module, and declared grids; only NQ data/economics and NQ-facing metadata were changed before any NQ PnL inspection.

Duplicate screen: distinct from existing NQ FOMC, EMV macro-news, import/export price-pressure, CFNAI, consumer sentiment, and generic seasonality families because it trades only the public CPI and Employment Situation release-date calendar after the 08:30 ET release.

Lookahead controls: release dates are public before RTH; entries use completed one-minute bars only and enter at next bar open; momentum/range filters use completed session state up to the signal bar; release values, surprises, revisions, final VWAP, daily high/low, and final day return are not used.

Risk caveat: release effects may be exhausted before RTH, event reactions can flip by inflation/rate regime, and any NQ result must pass the full staged gates without NQ rescue.
