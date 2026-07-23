# Historical Remediation Review Boundary

Created: `2026-07-15T06:31:35.877195+00:00`

Historical run evidence was not edited. No performance rerun or human approval was written.

## Coverage

- Registered runs: `2535`
- Runs classified in this scope: `2535`
- Coverage complete: `True`
- Automatic dispositions: `2534`
- Manual review items: `1`

## Disposition Counts

- `MANUAL_REVIEW_REQUIRED`: `1`
- `RETAIN_INVALID_HISTORICAL_RUN`: `1`
- `RETAIN_REJECTED_HISTORICAL_RUN`: `2532`
- `RETAIN_SUPERSEDED_INCOMPLETE_RUN`: `1`

## Non-Standard Automatic Dispositions

- `f13cace2-19c3-4198-b6f6-ae647231427b` — **RETAIN_SUPERSEDED_INCOMPLETE_RUN** — This zero/no-evidence run is superseded for decision purposes by a later same-variant ledger rejection; do not backfill or rerun it.
- `16b0b7f6-4469-403c-b3ee-e20de29ab9c9` — **RETAIN_INVALID_HISTORICAL_RUN** — A rejected historical run has a hash mismatch. Do not repair or rerun it for promotion.

## Manual Review Queue

### 1. es_video_aoi_lvn_orderflow_playbook / video_model1_range_midpoint_scid_intrabar_poc_3m_1500

- Run UID: `a5be3b58-a664-4ed8-8cab-7ef18698ba8d`
- Run: `backtest-campaigns/es_video_aoi_lvn_orderflow_playbook/video_model1_range_midpoint_scid_intrabar_poc_3m_1500/ES/run11_poc`
- Review type: `trade_mechanics_and_requalification_disposition`
- Latest ledger decision: `NOT_A_CANDIDATE_WITHOUT_COMPLETED_STAGE`
- Validation evidence: `backtest-campaigns/es_video_aoi_lvn_orderflow_playbook/video_model1_range_midpoint_scid_intrabar_poc_3m_1500/ES/run11_poc/validation_runs/core`
- Review queue: `research_artifacts/remediation/historical_review_20260715/review_queues/a5be3b58-a664-4ed8-8cab-7ef18698ba8d.csv`
- Required human action: Review the deterministic trade queues, then decide whether to reject/archive the POC or authorize a new frozen-mechanics requalification attempt. Do not approve the historical run itself.
- Promotion blockers:
  - historical validation metadata is not a current hash-bound promotion-gate decision
  - campaign is closed and no active/candidate campaign exists
  - validation_lane is absent from historical metadata
  - automated validation categories missing: reconciliation

## Stop Boundary

Choose reject/archive or explicitly authorize a new frozen-mechanics requalification attempt for each queue item. Do not change an historical verdict and do not mark an old POC `approved_for_testing`.

**NEEDS MANUAL REVIEW**
