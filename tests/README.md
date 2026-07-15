# Test Suite

Tests remain top-level because the package and CI deliberately configure `testpaths = ["tests"]`. After `alphaquest workspace build`, the collection is indexed by domain under `views/code/tests/`.

New tests should follow the source ownership boundary:

- backtest execution and accounting
- data and cache contracts
- research stages and methodology
- strategy modules
- validation and dashboard behavior
- prop rules

Run `make smoke` while iterating and `make test` before merging.
