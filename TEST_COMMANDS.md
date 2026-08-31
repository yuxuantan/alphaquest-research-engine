# Engineering Validation

Run commands from the repository root. Strategy campaign execution is not part
of the hermetic engineering baseline and must not be used merely to make CI
green.

## Reference setup

The CI reference environment is Python 3.12.14 with direct dependency versions
constrained by `constraints/dev.txt`:

```bash
python3 -m venv .venv
source .venv/bin/activate
make setup
python -m playwright install chromium
```

Frontend work uses Node.js 22.8.0 and the committed npm lockfile:

```bash
make studio-ui-setup
```

Do not update dependency versions as part of an unrelated CI repair. Change
`pyproject.toml`, the applicable lock/constraint file, and CI together in a
separately reviewed modernization change.

## Canonical commands

```bash
make smoke             # 65 fast CLI, registry, preflight, and engine tests
make test-python       # every test collected under tests/
make test-execution    # every test under execution_system/tests/
make test              # complete Python surface: both directories above
make studio-ui-check   # TypeScript build check plus locked Vitest suite
make validate          # lint, docs, smoke, complete Python, and Studio UI
```

`python -m pytest` is also a complete Python command because `pyproject.toml`
declares both test roots. Use the explicit per-root commands when isolating a
failure.

## Independent CI categories

GitHub Actions reports these jobs independently, so an early failure cannot
prevent unrelated qualification from running:

1. lint and static checks;
2. documentation validation;
3. CLI and smoke tests;
4. the governed Python suite under `tests/`;
5. the execution-system suite;
6. Studio UI typechecking and Vitest.
7. the required integration gate, which fails unless all six categories above
   succeeded.

Every Python CI job installs through `constraints/dev.txt`. The governed Python
job also installs Chromium because the no-code browser flow is part of that
suite.

## Methodology regression

This focused, hermetic command covers frozen policy, WFA/OOS selection, Monte
Carlo, attempt/run lineage and immutability, strategy certification, validation
promotion, and data identity:

```bash
python -m pytest -q \
  tests/test_research_policy.py \
  tests/test_research_governance.py \
  tests/test_campaign_stages.py \
  tests/test_wfa.py \
  tests/test_monte_carlo.py \
  tests/test_research_execution.py \
  tests/test_run_store.py \
  tests/test_experiment_registry.py \
  tests/test_strategy_certification.py \
  tests/test_execution_certification.py \
  tests/test_validation_promotion_gate.py \
  tests/test_data_source_hash.py
```

## Causal and execution regression

This focused, hermetic command covers timestamp/data contracts, next-bar signal
timing, fills and costs, pessimistic stop/target ordering, sessions, roll
handling, forced flatten, event replay, position sizing, and backtest/live
parity:

```bash
python -m pytest -q \
  tests/test_backtest_contracts.py \
  tests/test_backtest_engine.py \
  tests/test_order_simulation.py \
  tests/test_sessions.py \
  tests/test_event_replay.py \
  tests/test_event_replay_partial_exit.py \
  tests/test_position_sizing.py \
  tests/test_backtest_live_parity.py \
  tests/test_forward_reconciliation.py \
  tests/test_studio_execution_contract.py
```

## Workstation and data qualification

`make preflight` audits the currently authored campaign configs without
rerunning research. `make qualify` runs the complete Python surface and rewrites
the durable software-qualification report under `research_artifacts/`. The
report fails release qualification for a dirty worktree and binds the exact
commit, package and engine versions, methodology version and hashes, reference
environment hashes, commands, and test result. Run it only when intentionally
recording qualification for a reviewed revision.

The branch, protection, methodology-change, and annotated-tag procedure is in
[release governance](docs/operations/release-governance.md).

A repository preflight failure on frozen historical attempts or a drifted
strategy certification is a governed research/manual-review result, not an
engineering permission to edit old configs, recertify silently, or weaken the
gate. Record it separately from the hermetic CI result and create only the
explicit successor/certification lifecycle authorized by research governance.

Checks that open private/local DBN, SCID, broker, or large market-data paths are
workstation qualification. Missing private data is an explicit external/manual
boundary, not permission to weaken, skip, regenerate, or rewrite governed
evidence. An engineering-green checkout means every hermetic CI category above
passes; it does not mean a candidate strategy is approved, certified for
deployment, or tradeable.
