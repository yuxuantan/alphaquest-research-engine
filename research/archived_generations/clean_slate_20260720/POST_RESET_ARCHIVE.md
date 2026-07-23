# Post-reset archival notes

The clean-slate reset itself is recorded in
`research_artifacts/governance/research_reset_clean_slate_20260720.json`.

Two recoverable follow-up archives were added while integrating the first new
campaign:

- `legacy_code/` contains the retired Yush-specific backtest modules and runner.
  The active implementation now uses the registered generic event-replay lane.
- `corrected_mechanics_evidence/` contains the first mechanics-only export,
  which was superseded because the generic validator incorrectly applied
  bar-window checks to event-replay evidence and hashed relative source paths
  differently from resolved paths.

Neither follow-up archive is eligible research evidence. The current authored
campaign and current mechanics-review evidence remain under the configured
active and evidence roots.
