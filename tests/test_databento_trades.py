import pandas as pd

from alphaquest.data.databento_trades import aggregate_trade_orderflow_1m


def test_aggregate_trade_orderflow_selects_active_contract_and_signed_volume():
    raw = pd.DataFrame(
        [
            # ESM5 has lower session volume and should be dropped.
            {"ts_event": "2025-06-09T13:30:05Z", "action": "T", "symbol": "ESM5", "price": 6000.0, "size": 3, "side": "B"},
            {"ts_event": "2025-06-09T13:31:05Z", "action": "T", "symbol": "ESM5", "price": 6001.0, "size": 3, "side": "A"},
            # ESU5 is the active contract for the session.
            {"ts_event": "2025-06-09T13:30:10Z", "action": "T", "symbol": "ESU5", "price": 6010.0, "size": 8, "side": "B"},
            {"ts_event": "2025-06-09T13:30:40Z", "action": "T", "symbol": "ESU5", "price": 6011.0, "size": 12, "side": "A"},
            {"ts_event": "2025-06-09T13:31:10Z", "action": "T", "symbol": "ESU5", "price": 6012.0, "size": 20, "side": "B"},
            {"ts_event": "2025-06-09T13:31:40Z", "action": "T", "symbol": "ESU5", "price": 6011.5, "size": 5, "side": "N"},
        ]
    )

    bars = aggregate_trade_orderflow_1m(
        raw,
        rth_start="09:30:00",
        rth_end="09:32:00",
        complete_session_end="09:31:00",
        large_trade_sizes=[10, 20],
    )

    assert list(bars["contract_symbol"].unique()) == ["ESU5"]
    first = bars.iloc[0]
    assert first["timestamp"] == pd.Timestamp("2025-06-09 09:30:00")
    assert first["open"] == 6010.0
    assert first["high"] == 6011.0
    assert first["low"] == 6010.0
    assert first["close"] == 6011.0
    assert first["volume"] == 20.0
    assert first["buy_volume"] == 8.0
    assert first["sell_volume"] == 12.0
    assert first["signed_volume"] == -4.0
    assert first["large10_signed_volume"] == -12.0
    assert first["large10_volume"] == 12.0
    assert first["large20_signed_volume"] == 0.0
    assert first["large20_volume"] == 0.0

    second = bars.iloc[1]
    assert second["volume"] == 25.0
    assert second["signed_volume"] == 20.0
    assert second["large20_signed_volume"] == 20.0
    assert second["large20_volume"] == 20.0


def test_aggregate_trade_orderflow_drops_incomplete_sessions():
    raw = pd.DataFrame(
        [
            {"ts_event": "2025-06-09T13:30:05Z", "action": "T", "symbol": "ESM5", "price": 6000.0, "size": 10, "side": "B"},
            {"ts_event": "2025-06-10T13:30:05Z", "action": "T", "symbol": "ESM5", "price": 6010.0, "size": 10, "side": "B"},
            {"ts_event": "2025-06-10T13:31:05Z", "action": "T", "symbol": "ESM5", "price": 6011.0, "size": 10, "side": "B"},
        ]
    )

    bars = aggregate_trade_orderflow_1m(
        raw,
        rth_start="09:30:00",
        rth_end="09:32:00",
        complete_session_end="09:31:00",
    )

    assert bars["timestamp"].dt.date.unique().tolist() == [pd.Timestamp("2025-06-10").date()]
