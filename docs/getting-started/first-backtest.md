# First Backtest

Use the synthetic tutorial first. It does not claim an edge and does not update the production research ledger.

```bash
make tutorial
```

Then inspect:

```bash
cat examples/tutorial_campaign/generated/tutorial_manifest.json
cat examples/tutorial_campaign/generated/runs/v01/metrics.json
```

For a real authored campaign:

```bash
alphaquest campaign validate <campaign_id>
alphaquest campaign validate-mechanics <campaign_id> --variant <variant_id>
# Review the lane-correct evidence and write the declared approval.json.
alphaquest campaign run <campaign_id> --variant <variant_id>
make research-workspace
alphaquest campaign show <campaign_id> --explain --run <run_uid>
```

The staged performance command fails closed until a governance-v2 variant's lane-correct evidence and hash-bound manual decision are `approved_for_testing`.

Never edit generated `effective_config.yaml` or result summaries as source. Change the authored config, rerun under a new run ID, and preserve prior evidence.
