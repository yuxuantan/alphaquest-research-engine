import copy
import random

import pandas as pd
import pytest

from alphaquest.backtest.contracts import ExecutionAssumptions, validate_market_data_contract
from alphaquest.backtest.engine import BacktestEngine
from alphaquest.backtest.fills import entry_price, exit_price, stop_target_hit
from alphaquest.research.golden import backtest_result_signature
from alphaquest.version import ENGINE_CONTRACT_VERSION
from tests.test_backtest_engine import BASE_CFG, _features


def _bars() -> pd.DataFrame:
    timestamps = pd.date_range("2024-01-03 09:30", periods=3, freq="1min", tz="America/New_York")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "session_date": [timestamp.date() for timestamp in timestamps],
            "open": [100.0, 100.25, 100.5],
            "high": [100.5, 100.75, 101.0],
            "low": [99.75, 100.0, 100.25],
            "close": [100.25, 100.5, 100.75],
        }
    )


def test_market_data_contract_records_order_and_timezone():
    bars = _bars().iloc[::-1]

    contract = validate_market_data_contract(
        bars,
        label="fixture",
        require_session_date=True,
    )

    assert contract["rows"] == 3
    assert contract["timezone"] == "America/New_York"
    assert contract["input_was_monotonic"] is False
    assert contract["duplicate_timestamps"] == 0


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda frame: frame.assign(timestamp=frame["timestamp"].dt.tz_localize(None)), "timezone-aware"),
        (lambda frame: pd.concat([frame, frame.iloc[[0]]], ignore_index=True), "duplicate timestamps"),
        (lambda frame: frame.assign(high=[99.0, 100.75, 101.0]), "invalid OHLC"),
        (lambda frame: frame.assign(close=[100.25, float("nan"), 100.75]), "non-finite"),
    ],
)
def test_market_data_contract_fails_closed(mutation, message):
    with pytest.raises(ValueError, match=message):
        validate_market_data_contract(
            mutation(_bars()),
            label="fixture",
            require_session_date=True,
        )


def test_execution_assumptions_reject_inconsistent_tick_and_point_values():
    with pytest.raises(ValueError, match=r"point_value \* core.tick_size"):
        ExecutionAssumptions.from_core_config(
            {
                "tick_size": 0.25,
                "point_value": 50.0,
                "tick_value": 10.0,
                "commission_per_contract": 2.5,
                "slippage_ticks": 1,
            }
        )


@pytest.mark.parametrize("field", ["commission_per_contract", "slippage_ticks"])
def test_execution_assumptions_reject_negative_costs(field):
    core = {
        "tick_size": 0.25,
        "point_value": 50.0,
        "commission_per_contract": 2.5,
        "slippage_ticks": 1,
    }
    core[field] = -1

    with pytest.raises(ValueError, match=field):
        ExecutionAssumptions.from_core_config(core)


def test_fill_cost_invariant_over_deterministic_random_cases():
    rng = random.Random(20260711)
    for _ in range(500):
        tick_size = rng.choice([0.01, 0.25, 0.5])
        point_value = rng.choice([5.0, 20.0, 50.0, 100.0])
        tick_value = tick_size * point_value
        slippage_ticks = rng.uniform(0.0, 4.0)
        contracts = rng.randint(1, 10)
        raw_price = rng.uniform(10.0, 10000.0)
        expected_cost = 2.0 * slippage_ticks * tick_value * contracts
        for direction in ("long", "short"):
            opened = entry_price(raw_price, direction, tick_size, slippage_ticks)
            closed = exit_price(raw_price, direction, tick_size, slippage_ticks)
            point_pnl = closed - opened if direction == "long" else opened - closed
            actual_cost = -(point_pnl / tick_size * tick_value * contracts)
            assert actual_cost == pytest.approx(expected_cost)


def test_fill_conflicts_are_pessimistic_for_both_directions():
    bar = {"high": 102.0, "low": 98.0}

    assert stop_target_hit(bar, "long", 99.0, 101.0) == ("stop", 99.0)
    assert stop_target_hit(bar, "short", 101.0, 99.0) == ("stop", 101.0)


@pytest.mark.parametrize(
    ("bar", "direction", "stop_price", "target_price", "expected"),
    [
        ({"open": 98.0, "high": 100.0, "low": 97.5}, "long", 99.0, 101.0, 98.0),
        ({"open": 102.0, "high": 102.5, "low": 100.0}, "short", 101.0, 99.0, 102.0),
    ],
)
def test_carried_stop_gap_fills_at_adverse_open(bar, direction, stop_price, target_price, expected):
    assert stop_target_hit(
        bar,
        direction,
        stop_price,
        target_price,
        allow_open_gap_fill=True,
    ) == ("stop", expected)


def test_engine_replay_metadata_and_sorted_input_are_deterministic():
    features = _features()
    shuffled = features.sample(frac=1.0, random_state=7).reset_index(drop=True)

    ordered_result = BacktestEngine(BASE_CFG).run(features)
    shuffled_result = BacktestEngine(BASE_CFG).run(shuffled)

    assert backtest_result_signature(ordered_result) == backtest_result_signature(shuffled_result)
    replay = shuffled_result["reproducibility"]
    assert replay["engine_contract_version"] == ENGINE_CONTRACT_VERSION
    assert replay["data_contract"]["input_was_monotonic"] is False
    assert replay["execution_assumptions"]["tick_value_source"] == "tick_value"


def test_engine_rejects_duplicate_primary_bars_before_simulation():
    features = _features()
    duplicated = pd.concat([features, features.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="duplicate timestamps"):
        BacktestEngine(copy.deepcopy(BASE_CFG)).run(duplicated)
