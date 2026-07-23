from __future__ import annotations

import pandas as pd

from tools.audit_sierra_vs_databento_full_sessions import (
    compare_event_frames,
    full_session_window,
    render_report,
    segment_window,
)


def _events(sides: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp_ns": [
                pd.Timestamp("2025-07-13 18:00:00", tz="America/New_York").tz_convert("UTC").value,
                pd.Timestamp("2025-07-13 18:00:00.001", tz="America/New_York")
                .tz_convert("UTC")
                .value,
            ],
            "source_ordinal": [0, 1],
            "price": [6000.0, 6000.25],
            "size": [10, 3],
            "side": sides,
            "buy_volume": [0 if side == "A" else (10 if index == 0 else 3) for index, side in enumerate(sides)],
            "sell_volume": [10 if side == "A" and index == 0 else (3 if side == "A" else 0) for index, side in enumerate(sides)],
            "signed_size": [
                (-1 if side == "A" else (1 if side == "B" else 0)) * (10 if index == 0 else 3)
                for index, side in enumerate(sides)
            ],
        }
    )


def test_full_session_windows_use_new_york_calendar_boundaries() -> None:
    start, end = full_session_window("2025-11-03")
    assert str(start) == "2025-11-02 16:00:00-05:00"
    assert str(end) == "2025-11-03 16:00:00-05:00"
    assert segment_window("2025-11-03", "ETH")[1].hour == 9
    assert segment_window("2025-11-03", "RTH")[0].hour == 9


def test_databento_neutral_side_is_recorded_as_reference_gap_not_sierra_mismatch() -> None:
    sierra = _events(["A", "B"])
    databento = _events(["N", "B"])

    result, _minutes, mismatches = compare_event_frames(
        session_date="2025-07-14",
        segment="ETH",
        sierra_contract="ESU25",
        sc=sierra,
        db_events=databento,
    )

    assert result["price_size_sequence_exact"] is True
    assert result["side_sequence_exact_where_databento_labeled"] is True
    assert result["comparison_status"] == "DATABENTO_EQUIVALENT_WITH_REFERENCE_GAPS"
    assert result["failure_reason"] == "databento_neutral_aggressor_side_reference_gap"
    assert mismatches[0]["databento_side"] == "N"


def test_report_preserves_segment_specific_exception_reason() -> None:
    summary = {
        "verdict": "NEEDS MANUAL REVIEW",
        "scope": {"sessions_compared": 1},
        "outcome": {
            "sessions_event_equivalent": 0,
            "sessions_reference_gap_only": 0,
            "sessions_not_equivalent": 1,
            "sessions_error": 0,
            "session_segments_market_ohlc_exact": 2,
            "session_segments_market_ohlc_compared": 2,
            "session_segments_market_volume_exact": 2,
        },
        "runtime": {"processing_mode": "full_audit", "elapsed_seconds": 1.0},
        "historical_inference": {
            "directly_validated_period": "2025-07-14 through 2026-06-10"
        },
    }
    by_session = pd.DataFrame(
        [
            {
                "session_date": "2025-08-28",
                "sierra_contract": "ESU25",
                "comparison_status": "NOT_EVENT_EQUIVALENT",
                "failure_reason": "aggressor_side_mismatch",
            }
        ]
    )
    by_segment = pd.DataFrame(
        [
            {
                "session_date": "2025-08-28",
                "segment": "ETH",
                "sierra_contract": "ESU25",
                "comparison_status": "DATABENTO_EQUIVALENT_WITH_REFERENCE_GAPS",
                "failure_reason": "databento_neutral_aggressor_side_reference_gap",
            },
            {
                "session_date": "2025-08-28",
                "segment": "RTH",
                "sierra_contract": "ESU25",
                "comparison_status": "NOT_EVENT_EQUIVALENT",
                "failure_reason": "feature_mismatch:large_200_100ms_exact",
            },
        ]
    )

    report = render_report(summary, by_session, by_segment)

    assert "feature_mismatch:large_200_100ms_exact" in report
    assert "aggressor_side_mismatch" not in report
