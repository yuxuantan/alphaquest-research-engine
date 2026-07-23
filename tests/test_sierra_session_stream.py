from __future__ import annotations

import pandas as pd
import pytest

from alphaquest.data.sierra_session_stream import iter_sierra_trade_sessions


def _event_part(contract: str = "ESM25") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2025-06-09 09:30:00-04:00", "2025-06-09 09:30:00.001-04:00"],
                format="mixed",
            ),
            "source_ordinal": [0, 1],
            "contract_symbol": [contract, contract],
            "close": [6000.0, 6000.25],
            "volume": [2, 3],
            "side": ["A", "B"],
            "signed_volume": [-2, 3],
        }
    )


def _levels(path, *, contract: str = "ESM25") -> None:
    pd.DataFrame(
        [
            {
                "session_date": "2025-06-09",
                "contract_symbol": contract,
                "previous_rth_session_date": "2025-06-06",
                "previous_rth_contract_symbol": contract,
                "previous_rth_high": 5995.0,
                "previous_rth_low": 5975.0,
                "previous_rth_close": 5990.0,
                "overnight_high": 6002.0,
                "overnight_low": 5988.0,
            }
        ]
    ).to_parquet(path, index=False)


def test_sierra_session_adapter_binds_causal_levels_and_canonical_events(
    tmp_path, monkeypatch
) -> None:
    levels = tmp_path / "levels.parquet"
    _levels(levels)
    monkeypatch.setattr(
        "alphaquest.data.sierra_session_stream.iter_scid_record_execution_sessions",
        lambda *_args, **_kwargs: iter([("2025-06-09", _event_part())]),
    )

    sessions = list(
        iter_sierra_trade_sessions(
            {
                "session_levels": str(levels),
                "ineligible_session_policy": "error",
            },
            start_date="2025-06-09",
            end_date="2025-06-09",
        )
    )

    assert len(sessions) == 1
    session = sessions[0]
    assert session.previous_rth is not None
    assert session.previous_rth.session_date.isoformat() == "2025-06-06"
    assert session.previous_rth.high == 5995.0
    assert session.overnight_high == 6002.0
    assert session.overnight_low == 5988.0
    assert session.events[["price", "size", "side", "signed_size"]].to_dict("records") == [
        {"price": 6000.0, "size": 2, "side": "A", "signed_size": -2},
        {"price": 6000.25, "size": 3, "side": "B", "signed_size": 3},
    ]


def test_sierra_session_adapter_fails_closed_on_level_contract_mismatch(
    tmp_path, monkeypatch
) -> None:
    levels = tmp_path / "levels.parquet"
    _levels(levels, contract="ESU25")
    monkeypatch.setattr(
        "alphaquest.data.sierra_session_stream.iter_scid_record_execution_sessions",
        lambda *_args, **_kwargs: iter([("2025-06-09", _event_part("ESM25"))]),
    )

    with pytest.raises(ValueError, match="contract mismatch"):
        list(
            iter_sierra_trade_sessions(
                {
                    "session_levels": str(levels),
                    "ineligible_session_policy": "error",
                },
                start_date="2025-06-09",
                end_date="2025-06-09",
            )
        )
