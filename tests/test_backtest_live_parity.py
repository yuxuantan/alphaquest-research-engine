import pandas as pd
import pytest

from alphaquest.research.parity import assert_trade_intent_parity, backtest_trade_intents, compare_trade_intents


def test_backtest_trade_intent_parity_accepts_matching_rows():
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "entry_timestamp": pd.Timestamp("2024-01-03 09:31:00", tz="America/New_York"),
                "direction": "long",
                "entry_price": 100.25,
                "stop_price": 99.25,
                "target_price": 102.25,
                "contracts": 1,
            }
        ]
    )
    intents = backtest_trade_intents(trades)

    assert_trade_intent_parity(intents, [dict(intents[0])])


def test_backtest_trade_intent_parity_reports_price_mismatch():
    expected = [
        {
            "entry_timestamp": "2024-01-03T09:31:00-05:00",
            "direction": "long",
            "entry_price": 100.25,
            "stop_price": 99.25,
            "target_price": 102.25,
            "contracts": 1,
        }
    ]
    actual = [dict(expected[0], target_price=102.50)]

    mismatches = compare_trade_intents(expected, actual, price_tolerance=0.0)

    assert len(mismatches) == 1
    assert mismatches[0].field == "target_price"
    with pytest.raises(AssertionError, match="target_price"):
        assert_trade_intent_parity(expected, actual, price_tolerance=0.0)


def test_backtest_trade_intent_parity_compares_timestamp_instants_across_timezones():
    expected = [
        {
            "signal_timestamp": "2024-01-03T09:30:00-05:00",
            "entry_timestamp": "2024-01-03T09:31:00-05:00",
            "direction": "long",
            "entry_price": 100.25,
            "stop_price": 99.25,
            "target_price": 102.25,
            "contracts": 1,
        }
    ]
    actual = [
        {
            **expected[0],
            "signal_timestamp": "2024-01-03T14:30:00+00:00",
            "entry_timestamp": "2024-01-03T14:31:00+00:00",
        }
    ]

    assert compare_trade_intents(expected, actual) == []


def test_backtest_trade_intent_parity_rejects_naive_timestamps():
    intent = [
        {
            "entry_timestamp": "2024-01-03 09:31:00",
            "direction": "long",
            "entry_price": 100.25,
            "stop_price": 99.25,
            "target_price": 102.25,
            "contracts": 1,
        }
    ]

    with pytest.raises(ValueError, match="timezone-aware"):
        compare_trade_intents(intent, intent)
