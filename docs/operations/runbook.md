# Operations Runbook

## Daily Research

The novice workflow runs entirely in Research Studio. Operators can inspect the durable local processes and queue with:

```bash
alphaquest studio status
```

Expert registry commands remain:

```bash
make research-workspace
alphaquest research status
alphaquest research search --verdict NEEDS_MANUAL_REVIEW
```

## Before A Run

```bash
alphaquest campaign validate <campaign_id>
make smoke
```

Complete the deterministic mechanics export and hash-bound `approved_for_testing` decision before invoking the staged performance command.

## After A Run

```bash
make research-workspace
alphaquest campaign show <campaign_id>
alphaquest campaign show <campaign_id> --explain --run <run_uid> --write-card
make qualify
```

## Failure Handling

- Preserve the failed run and its effective config.
- Diagnose the first failed stage.
- Do not use later stale folders as evidence.
- Do not retune on acceptance data.
- Record an explicitly authorized rescue as a new attempt and run ID.
