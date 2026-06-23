import pandas as pd

from propstack.strategy_modules.entry.nq_pivot_mes_orderflow_confirmation import (
    NqPivotMesOrderflowConfirmationEntry,
)


def test_nq_pivot_mes_orderflow_confirmation_passes_matching_completed_flow():
    entry = NqPivotMesOrderflowConfirmationEntry(_params())

    signal = None
    for bar in _enriched_pivot_bars(signed_volume=500):
        signal = entry.on_bar_close(bar)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["market_structure_filter_direction"] == "long"
    assert signal.report_fields["nq_pivot_mes_orderflow_confirmation_result"] == "passed"
    assert signal.report_fields["nq_orderflow_signed_directional_imbalance"] > 0


def test_nq_pivot_mes_orderflow_confirmation_rejects_opposite_completed_flow():
    entry = NqPivotMesOrderflowConfirmationEntry(_params())

    signal = None
    for bar in _enriched_pivot_bars(signed_volume=-500):
        signal = entry.on_bar_close(bar)

    assert signal is None


def test_nq_pivot_mes_orderflow_confirmation_consumes_first_unconfirmed_base_signal():
    entry = NqPivotMesOrderflowConfirmationEntry(
        {
            **_params(),
            "market_structure_params": {
                **_market_structure_params(),
                "base_params": {
                    **_base_params(),
                    "signal_mode": "first_signal_in_window",
                    "start_time": "10:15:00",
                    "end_time": "10:20:00",
                },
            },
        }
    )
    bars = _enriched_pivot_bars(signed_volume=-500)
    extra = bars[-1].copy()
    extra["timestamp"] = pd.Timestamp("2024-01-03 10:15:00")
    extra["open"] = 101.0
    extra["high"] = 103.5
    extra["low"] = 100.5
    extra["close"] = 101.0
    extra["signed_volume"] = 500
    bars.append(extra)

    signals = [entry.on_bar_close(bar) for bar in bars]

    assert signals[-2] is None
    assert signals[-1] is None


def test_nq_pivot_mes_orderflow_confirmation_can_wait_for_first_confirmed_signal():
    entry = NqPivotMesOrderflowConfirmationEntry(
        {
            **_params(),
            "consume_unconfirmed_base_signal": False,
            "orderflow_window_minutes": 5,
            "market_structure_params": {
                **_market_structure_params(),
                "base_params": {
                    **_base_params(),
                    "signal_mode": "first_signal_in_window",
                    "start_time": "10:15:00",
                    "end_time": "10:20:00",
                },
            },
        }
    )
    bars = _enriched_pivot_bars(signed_volume=-500)
    extra = bars[-1].copy()
    extra["timestamp"] = pd.Timestamp("2024-01-03 10:15:00")
    extra["open"] = 101.0
    extra["high"] = 103.5
    extra["low"] = 100.5
    extra["close"] = 101.0
    extra["signed_volume"] = 500
    bars.append(extra)

    signals = [entry.on_bar_close(bar) for bar in bars]

    assert signals[-2] is None
    assert signals[-1] is not None
    assert signals[-1].report_fields["nq_orderflow_consume_unconfirmed_base_signal"] is False


def _params() -> dict:
    return {
        **_market_structure_params(),
        "orderflow_window_minutes": 30,
        "flow_mode": "signed_imbalance",
        "min_orderflow_imbalance": 0.05,
        "consume_unconfirmed_base_signal": True,
    }


def _market_structure_params() -> dict:
    return {
        "bar_interval_minutes": 5,
        "timeframes_minutes": [5],
        "min_aligned_timeframes": 1,
        "pivot_left_bars": 1,
        "pivot_right_bars": 1,
        "min_pivot_move_ticks": 0,
        "tick_size": 0.25,
        "base_module": "mes_participation_crowding",
        "base_params": _base_params(),
    }


def _base_params() -> dict:
    return {
        "entry_time": "10:15:00",
        "bar_interval_minutes": 5,
        "lookback_minutes": 30,
        "share_mode": "notional",
        "direction": "long",
        "share_rank_min": 0.5,
        "min_abs_return_ticks": 4,
    }


def _enriched_pivot_bars(signed_volume: float) -> list[pd.Series]:
    bars = []
    for bar in _pivot_bars():
        enriched = bar.copy()
        enriched["mes_participation_share_30"] = 0.1
        enriched["mes_participation_share_30_rank252"] = 0.8
        enriched["es_return_ticks_30"] = -6.0
        enriched["signed_volume"] = signed_volume
        enriched["large10_volume"] = 1000
        enriched["large10_signed_volume"] = signed_volume
        enriched["large20_volume"] = 1000
        enriched["large20_signed_volume"] = signed_volume
        bars.append(enriched)
    return bars


def _pivot_bars() -> list[pd.Series]:
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=9, freq="5min")
    return [
        pd.Series(
            {
                "timestamp": ts,
                "session_date": ts.date(),
                "session_label": "RTH",
                "is_rth": True,
                "volume": 1000,
                **row,
            }
        )
        for ts, row in zip(timestamps, _pivot_ohlc_rows())
    ]


def _pivot_ohlc_rows() -> list[dict]:
    return [
        {"open": 100.0, "high": 100.5, "low": 99.0, "close": 100.0},
        {"open": 100.0, "high": 102.0, "low": 100.0, "close": 101.5},
        {"open": 101.5, "high": 101.0, "low": 99.5, "close": 100.0},
        {"open": 100.0, "high": 101.0, "low": 98.0, "close": 99.0},
        {"open": 99.0, "high": 100.0, "low": 99.0, "close": 99.5},
        {"open": 99.5, "high": 103.0, "low": 100.0, "close": 102.0},
        {"open": 102.0, "high": 102.0, "low": 99.5, "close": 100.5},
        {"open": 100.5, "high": 101.0, "low": 99.0, "close": 100.0},
        {"open": 100.0, "high": 102.0, "low": 100.0, "close": 101.0},
    ]
