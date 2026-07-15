# Trace Research End To End

The normal navigation path is one command, not manual browsing through `research/evidence/runs/`:

```bash
make research-workspace
alphaquest research search --query video_aoi --limit 10
alphaquest campaign show es_video_aoi_lvn_orderflow_playbook \
  --explain \
  --run 594f2309-1e8e-43ca-bd10-34d85b5edbcf \
  --write-card
```

The generated card resolves this chain:

```text
campaign.yaml
-> economic edge and sources
-> five authored variant configs and mechanics locks
-> selected run UID and source/effective snapshots
-> hashes, data manifest, date/session/contract/cost assumptions
-> validation lane, automated checks, and manual approval
-> ordered stage results and first failure
-> authoritative artifacts
-> PASS / FAIL / NEEDS MANUAL REVIEW
```

For the worked historical run above, the recorded performance verdict is `FAIL`. Its modern lineage review may independently be `NEEDS MANUAL REVIEW` where historical vendor, session, or hash-bound manual-approval evidence is absent. The command keeps those two facts separate and does not rewrite historical evidence.

Cards under `views/run_cards/` are disposable projections. `campaign.yaml`, source/effective config snapshots, run/data manifests, hashes, stage summaries, validation decisions, and terminal summaries remain authoritative.
