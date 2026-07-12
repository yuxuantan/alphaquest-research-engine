# Operations Runbook

## Daily Research

```bash
make research-workspace
propstack research status
propstack research search --verdict NEEDS_MANUAL_REVIEW
```

## Before A Run

```bash
propstack campaign validate <campaign_id>
make smoke
```

## After A Run

```bash
make research-workspace
propstack campaign show <campaign_id>
make qualify
```

## Failure Handling

- Preserve the failed run and its effective config.
- Diagnose the first failed stage.
- Do not use later stale folders as evidence.
- Do not retune on acceptance data.
- Record an explicitly authorized rescue as a new attempt and run ID.
