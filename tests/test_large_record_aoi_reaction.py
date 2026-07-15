from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.large_record_aoi_reaction import LargeRecordAoiReactionEntry


def _bar(
    timestamp: str,
    *,
    session_date: str = "2024-01-03",
    open_: float = 100.0,
    high: float = 100.5,
    low: float = 99.5,
    close: float = 100.25,
    volume: float = 1000.0,
    signed_volume: float = -100.0,
    prev_rth_high: float = 101.0,
    prev_rth_low: float = 100.0,
    large_record_max_volume: float | None = 225.0,
    large_record_volume: float = 225.0,
    large_record_signed_volume: float = -225.0,
    large_record_count: float = 1.0,
) -> pd.Series:
    values = {
        "timestamp": pd.Timestamp(timestamp),
        "session_date": pd.Timestamp(session_date),
        "session_label": "RTH",
        "is_rth": True,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "signed_volume": signed_volume,
        "prev_rth_high": prev_rth_high,
        "prev_rth_low": prev_rth_low,
        "large200_record_volume": large_record_volume,
        "large200_record_signed_volume": large_record_signed_volume,
        "large200_record_count": large_record_count,
    }
    if large_record_max_volume is not None:
        values["large200_record_max_volume"] = large_record_max_volume
    return pd.Series(values)


def _install_profile_state(entry: LargeRecordAoiReactionEntry, opening_bars: int = 0) -> None:
    entry.current_session = pd.Timestamp("2024-01-03")
    entry.prior_profile = {
        "session_date": pd.Timestamp("2024-01-02"),
        "poc": 101.0,
        "vah": 102.0,
        "val": 100.0,
        "total_volume": 100000.0,
        "bar_count": 390,
        "levels": [
            {"type": "poc", "price": 101.0},
            {"type": "vah", "price": 102.0},
            {"type": "val", "price": 100.0},
            {"type": "lvn", "price": 99.0},
            {"type": "lvn", "price": 103.0},
        ],
    }
    entry.current_session_bars = [
        _bar(
            f"2024-01-03 09:{30 + minute:02d}:00",
            open_=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            signed_volume=0.0,
            large_record_max_volume=0.0,
            large_record_volume=0.0,
            large_record_signed_volume=0.0,
            large_record_count=0.0,
        )
        for minute in range(opening_bars)
    ]


def test_market_aoi_seller_trap_uses_next_bar_timestamp_and_large_record_proxy():
    entry = LargeRecordAoiReactionEntry(
        {
            "setup_mode": "market_aoi_large_record_two_sided_trap",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "max_profile_distance_ticks": 4,
            "min_large200_record_volume": 200,
        }
    )
    _install_profile_state(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:01:00",
            open_=99.75,
            high=100.5,
            low=99.5,
            close=100.25,
            prev_rth_low=100.0,
            large_record_signed_volume=-225.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:02:00")
    assert signal.report_fields["reaction_model"] == "trap"
    assert signal.report_fields["aoi_type"] == "prior_rth_low"
    assert signal.report_fields["large200_record_max_volume"] == 225.0
    assert "not vendor-equivalent print data" in signal.report_fields["source_quality_label"]


def test_large_record_reaction_rejects_when_proxy_field_is_absent():
    entry = LargeRecordAoiReactionEntry(
        {
            "setup_mode": "market_aoi_large_record_two_sided_trap",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "max_profile_distance_ticks": 4,
        }
    )
    _install_profile_state(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:01:00",
            open_=99.75,
            high=100.5,
            low=99.5,
            close=100.25,
            prev_rth_low=100.0,
            large_record_max_volume=None,
        )
    )

    assert signal is None


def test_market_aoi_continuation_waits_for_completed_opening_range():
    params = {
        "setup_mode": "market_aoi_large_record_two_sided_continuation",
        "start_time": "09:30:00",
        "end_time": "16:00:00",
        "opening_range_minutes": 30,
        "max_profile_distance_ticks": 4,
    }
    early = LargeRecordAoiReactionEntry(params)
    _install_profile_state(early, opening_bars=29)
    assert (
        early.on_bar_close(
            _bar(
                "2024-01-03 10:00:00",
                open_=100.75,
                high=101.5,
                low=100.75,
                close=101.25,
                prev_rth_high=110.0,
                prev_rth_low=90.0,
                large_record_signed_volume=225.0,
            )
        )
        is None
    )

    entry = LargeRecordAoiReactionEntry(params)
    _install_profile_state(entry, opening_bars=30)
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:00:00",
            open_=100.75,
            high=101.5,
            low=100.75,
            close=101.25,
            prev_rth_high=110.0,
            prev_rth_low=90.0,
            large_record_signed_volume=225.0,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["reaction_model"] == "continuation"
    assert signal.report_fields["aoi_type"] == "opening_range_high"


def test_profile_value_large_record_continuation_can_emit_short():
    entry = LargeRecordAoiReactionEntry(
        {
            "setup_mode": "profile_value_large_record_two_sided_continuation",
            "start_time": "09:30:00",
            "end_time": "16:00:00",
            "max_profile_distance_ticks": 4,
        }
    )
    _install_profile_state(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:05:00",
            open_=100.25,
            high=100.25,
            low=99.5,
            close=99.75,
            large_record_signed_volume=-250.0,
            large_record_max_volume=250.0,
            large_record_volume=250.0,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["aoi_type"] == "prior_value_area_low"
    assert signal.report_fields["large200_record_dominant_side"] == "sell"
