# nq_prior_session_flip_retest_orderflow / midday_signed_aligned_two_sided_flip

NQ port of the ES prior-session S/R flip retest orderflow variant. The variant records a completed break beyond the previous RTH high/low, waits for a later completed retest that holds on the breakout side, and requires completed retest-bar aggregate orderflow confirmation before next-bar-open execution.

Source ES config: `campaigns/es_prior_session_flip_retest_orderflow/variants/midday_signed_aligned_two_sided_flip/config.yaml`.
Status: pending pre-PnL density screen; no NQ PnL inspected at authoring.
