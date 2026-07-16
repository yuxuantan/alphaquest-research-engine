# First Backtest

# First Backtest · Expert CLI

Researchers should normally use [Research Studio](research-studio.md). This page documents the expert/operator equivalent.

Use the synthetic tutorial first. It does not claim an edge and does not update the production research ledger. Inside its disposable generated workspace it exercises the governed importer, draft compiler, transactional publisher, mechanics queue and approvals, authoritative core/monkey engines, and strict result bundles. Its operational run passes, while its research verdict deliberately ends `FAIL` because promising core PnL does not beat seeded randomized entries.

```bash
make tutorial
```

Then inspect the five-variant stage matrix:

```bash
cat examples/tutorial_campaign/generated/tutorial_manifest.json
cat examples/tutorial_campaign/generated/stage_matrix.csv
```

The tutorial does not reserve a real attempt or pretend that ten synthetic sessions completed WFA, Monte Carlo, incubation, or locked acceptance. Those production stages remain `NOT_RUN` and the output is permanently non-promotable.

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

`--skip-validation`, `--no-acceptance`, `--fast-runtime-defaults`, or a shortened stage set are diagnostic-only. They resolve to `NEEDS MANUAL REVIEW` and cannot create a candidate package.

Never edit generated `effective_config.yaml` or result summaries as source. Change the authored config, rerun under a new run ID, and preserve prior evidence.
