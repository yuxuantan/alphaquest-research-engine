# Architecture

The system has four strict ownership layers:

1. **Authored research:** `campaigns/`, policy, and reference configuration.
2. **Engine:** reusable deterministic code under `src/alphaquest/`.
3. **Generated evidence:** immutable run outputs under `backtest-campaigns/`.
4. **Indexes and views:** rebuildable registry, exports, and navigation.

Detailed diagrams and contracts are in [docs/architecture](docs/architecture/system-overview.md). Architecture changes that alter causality, fill semantics, stage gates, data availability, or artifact lineage require an ADR under `docs/architecture/decisions/` and focused regression tests.
