# Contributing

## Before Editing

1. Read [START_HERE.md](START_HERE.md) and [ARCHITECTURE.md](ARCHITECTURE.md).
2. Identify whether the file is authored source, generated evidence, or a rebuildable view.
3. Never edit generated results to change a verdict.

## Development Workflow

`main` is the sole stable/default branch. Perform work on a temporary
`feat/`, `fix/`, or `docs/` branch and integrate it through a pull request after
the required CI gate succeeds. See [release governance](docs/operations/release-governance.md)
for branch protection, methodology-version changes, qualification, and tagging.

```bash
make setup
pre-commit install
make smoke
make validate
make preflight
```

`make validate` covers both Python test roots and the Studio UI suite. See
[the complete test surface](TEST_COMMANDS.md) for independent commands and the
private-data boundary.

Run `pre-commit run --all-files` before opening a pull request. Hooks check basic file hygiene, YAML/JSON syntax, and the repository's Ruff policy.

Add focused tests for behavioral changes. Engine changes must cover entry timing, exit ordering, costs, forced flattening, and no-lookahead behavior where relevant.

## Pull Requests

- State the research or engineering objective.
- Identify data, config, engine, and artifact-contract changes.
- Report exact tests and preflight commands.
- Declare whether historical evidence was rewritten.
- Require the `Required integration gate` check before merge.
- Use candidate language; never claim a backtest alone is tradeable.

Do not combine unrelated refactors with strategy mechanics changes. Preserve failed research and ledger history.
