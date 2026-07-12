# Cleanup And Recovery

Cleanup is evidence-sensitive. Dry-run first:

```bash
make cleanup-generated
```

Only remove reproducible bulk payloads, caches, junk, or exact error runs superseded by the same effective config. Retain authored definitions, configs, summaries, ledgers, fixed-config trade logs, WFA stitched OOS logs, Monte Carlo summaries, and methodology audits.

Rebuild disposable navigation at any time:

```bash
make research-workspace
```

Interrupted runs are resumable evidence. Diagnose their stage summaries before rerunning or deleting anything.
