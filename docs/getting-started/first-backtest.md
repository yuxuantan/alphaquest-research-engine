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
alphaquest campaign run <campaign_id> --variant <variant_id>
make research-workspace
alphaquest campaign show <campaign_id>
```

Never edit generated `effective_config.yaml` or result summaries as source. Change the authored config, rerun under a new run ID, and preserve prior evidence.
