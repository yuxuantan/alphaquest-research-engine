# Synthetic Tutorial Campaign

This tutorial exercises the real backtest engine with deterministic synthetic ES-like bars. It does not represent an economic edge, does not touch the production research ledger, and is never eligible for promotion.

Run it with:

```bash
make tutorial
```

Generated files are written under `examples/tutorial_campaign/generated/`:

- ten synthetic sessions
- five example variant configs
- one executed core run
- trade log, daily results, metrics, and tutorial manifest

The command reports operational `PASS` when the tutorial executes correctly. Its research verdict remains `NEEDS MANUAL REVIEW` by construction.
