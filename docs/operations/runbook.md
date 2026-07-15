# Operations Runbook

## Daily Research

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

## After A Run

```bash
make research-workspace
alphaquest campaign show <campaign_id>
make qualify
```

## Failure Handling

- Preserve the failed run and its effective config.
- Diagnose the first failed stage.
- Do not use later stale folders as evidence.
- Do not retune on acceptance data.
- Record an explicitly authorized rescue as a new attempt and run ID.
