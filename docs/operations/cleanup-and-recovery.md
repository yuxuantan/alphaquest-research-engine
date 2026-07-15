# Cleanup And Recovery

Cleanup is evidence-sensitive. Dry-run first:

```bash
make cleanup-generated
```

Only remove reproducible bulk payloads, caches, junk, or exact error runs superseded by the same effective config. Retain authored definitions, configs, summaries, ledgers, fixed-config trade logs, WFA stitched OOS logs, Monte Carlo summaries, and methodology audits.

The JSON cleanup audit is the deletion manifest. Every candidate records path, class, size, references, reproducibility, decision, and reason. On `--apply`, the tool writes an `APPROVED_PENDING_APPLY` manifest before deleting and rewrites it as `APPLIED` afterward. Unknown, referenced, interrupted, or provenance-bearing files are never candidates.

Rebuild disposable navigation at any time:

```bash
make research-workspace
```

Interrupted runs are resumable evidence. Diagnose their stage summaries before rerunning or deleting anything.
