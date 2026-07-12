# System Overview

```text
authored campaign config
        |
        v
fail-closed preflight -----> data contract and causal checks
        |
        v
staged runner ------------> core -> monkey -> WFA -> OOS stress -> incubation -> acceptance
        |
        v
immutable run evidence ---> registry ---> views / CLI / dashboard
```

The backtest engine owns execution semantics. Strategy modules produce signals; the engine owns fill timing, costs, exits, sizing, and forced flattening. Research stages own parameter selection and promotion gates. The registry is an index, never the source of a result.

## Package Boundaries

- `backtest/`: fills, positions, metrics, equity, sizing.
- `data/`: loaders, hashing, feature preparation, subsets, timeframes.
- `strategy_modules/`: auditable entry, stop, and target modules.
- `research/`: grids, WFA, Monte Carlo, policy, schemas, registry, run store.
- `validation/`: exported mechanics evidence and automated checks.
- `prop/`: configurable prop-rule simulation.
