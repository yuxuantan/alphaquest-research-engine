# Superseded mechanics evidence

This evidence was archived before implementing exact-fingerprint AOI lineage.

- The prior implementation preserved an AOI eligibility timestamp when a newly calculated AOI merely overlapped the previous box.
- That made the timestamp identify a geometric lineage rather than the exact price envelope and selected confluences later shown for the trade.
- The saved manual annotation is preserved inside `declared_validation_evidence/validation_runs/core/manual_review.parquet` for audit only.
- None of this evidence is eligible for mechanics approval or performance testing.

Replacement evidence must reset AOI eligibility whenever the exact envelope or selected confluence identity changes, require a later directed tap, freeze the tapped snapshot, and invalidate it if the developing-value anchor leaves the box.
