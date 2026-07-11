# Engine Qualification

Software status: **PASS**

Engine contract: `2026.07.11.1`
Git commit: `f33988a3223b61a4b2b1e4bcab1d3484ae7eae8c`
Dirty worktree: `true`
Policy SHA-256: `3285c4ca078a03d255cd03cc7944eaf31ea42bdb91ad15f337c9ebeb3ca0f0f2`

This is a software-verification result. It is not evidence that any candidate strategy is tradeable.

## Control Evidence

- `market_data_integrity`: Rejects naive/duplicate primary timestamps, invalid OHLC, and non-finite prices. Evidence: `tests/test_backtest_contracts.py`
- `execution_accounting`: Validates execution assumptions and adverse round-trip cost accounting. Evidence: `tests/test_backtest_contracts.py tests/test_backtest_engine.py`
- `causal_entry_and_exit_ordering`: Checks next-bar entry, intrabar ordering, pessimistic conflicts, and forced flattening. Evidence: `tests/test_backtest_engine.py`
- `deterministic_replay`: Pins a golden result signature and verifies input-order normalization. Evidence: `tests/test_golden_reproducibility.py tests/test_backtest_contracts.py`
- `backtest_execution_parity_contract`: Compares signal identity, timestamp instants, prices, size, and flatten instructions. Evidence: `tests/test_backtest_live_parity.py`
- `staged_research_governance`: Fails closed on invalid configs/artifacts and preserves staged promotion gates. Evidence: `tests/test_campaign_stages.py tests/test_preflight.py tests/test_research_schemas.py`

## Model Limitations

- OHLC runs do not model exchange queue position or order-book priority.
- SCID record replay is ordered trade-record evidence, not exchange-native MBO sequencing.
- Latency, partial fills, market impact, and capacity require venue/broker-specific calibration.
- A passing software qualification does not make any strategy tradeable or live-ready.
- Historical artifacts created before the current engine contract version must be rerun to inherit it.

## Test Output

```text
........................................................................ [  4%]
........................................................................ [  9%]
........................................................................ [ 14%]
........................................................................ [ 19%]
........................................................................ [ 24%]
........................................................................ [ 29%]
........................................................................ [ 34%]
........................................................................ [ 39%]
........................................................................ [ 44%]
........................................................................ [ 48%]
........................................................................ [ 53%]
........................................................................ [ 58%]
........................................................................ [ 63%]
........................................................................ [ 68%]
........................................................................ [ 73%]
........................................................................ [ 78%]
........................................................................ [ 83%]
........................................................................ [ 88%]
........................................................................ [ 92%]
........................................................................ [ 97%]
................................                                         [100%]
1472 passed in 23.41s
```
