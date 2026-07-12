# Contributing

## Before Editing

1. Read [START_HERE.md](START_HERE.md) and [ARCHITECTURE.md](ARCHITECTURE.md).
2. Identify whether the file is authored source, generated evidence, or a rebuildable view.
3. Never edit generated results to change a verdict.

## Development Workflow

```bash
make setup
pre-commit install
make smoke
make test
make preflight
```

Run `pre-commit run --all-files` before opening a pull request. Hooks check basic file hygiene, YAML/JSON syntax, and the repository's Ruff policy.

Add focused tests for behavioral changes. Engine changes must cover entry timing, exit ordering, costs, forced flattening, and no-lookahead behavior where relevant.

## Pull Requests

- State the research or engineering objective.
- Identify data, config, engine, and artifact-contract changes.
- Report exact tests and preflight commands.
- Declare whether historical evidence was rewritten.
- Use candidate language; never claim a backtest alone is tradeable.

Do not combine unrelated refactors with strategy mechanics changes. Preserve failed research and ledger history.
