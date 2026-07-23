from __future__ import annotations

import pytest
import pandas as pd

from tools.audit_yush_sierra_strategy_concordance import (
    _compare_session_audits,
    _load_databento_checkpoint,
    _selected_session_dates,
    _write_databento_checkpoint,
)


def test_stratified_concordance_selection_is_deterministic_and_keeps_required_dates() -> None:
    eligible = [f"2025-07-{day:02d}" for day in range(1, 11)]

    selected = _selected_session_dates(
        eligible,
        count=3,
        required=["2025-07-03"],
    )

    assert selected == {
        "2025-07-01",
        "2025-07-03",
        "2025-07-05",
        "2025-07-10",
    }


def test_stratified_concordance_selection_rejects_ineligible_required_date() -> None:
    with pytest.raises(ValueError, match="not eligible"):
        _selected_session_dates(
            ["2025-07-01"],
            count=1,
            required=["2025-07-02"],
        )


def test_databento_checkpoint_is_hash_and_session_bound(tmp_path) -> None:
    levels = [
        {
            "session_date": "2025-07-15",
            "contract_symbol": "ESU5",
            "previous_rth_session_date": "2025-07-14",
            "previous_rth_contract_symbol": "ESU5",
            "previous_rth_high": 6300.0,
            "previous_rth_low": 6200.0,
            "previous_rth_close": 6250.0,
            "overnight_high": 6275.0,
            "overnight_low": 6230.0,
        }
    ]
    _write_databento_checkpoint(
        tmp_path,
        config_sha256="a" * 64,
        capability_sha256="b" * 64,
        session_dates={"2025-07-15"},
        trades=pd.DataFrame({"trade_id": ["1"]}),
        session_audits=pd.DataFrame({"session_date": ["2025-07-15"]}),
        levels=levels,
    )

    trades, audits, restored_levels = _load_databento_checkpoint(
        tmp_path,
        config_sha256="a" * 64,
        capability_sha256="b" * 64,
        session_dates={"2025-07-15"},
    )

    assert len(trades) == 1
    assert len(audits) == 1
    assert restored_levels[0]["contract_symbol"] == "ESU5"
    with pytest.raises(ValueError, match="does not match"):
        _load_databento_checkpoint(
            tmp_path,
            config_sha256="c" * 64,
            capability_sha256="b" * 64,
            session_dates={"2025-07-15"},
        )


def test_exploratory_counter_drift_does_not_hide_decision_path_equality() -> None:
    base = {
        "session_date": "2025-07-15",
        "contract_symbol": "ESU5",
        "events": 100,
        "orders_armed": 2,
        "trades": 1,
        "taps": 5,
        "delta_bubbles": 7,
        "wrong_approach_rejections": 11,
    }
    other = {
        **base,
        "contract_symbol": "ESU25",
        "taps": 6,
        "delta_bubbles": 8,
        "wrong_approach_rejections": 12,
    }

    compared = _compare_session_audits(pd.DataFrame([base]), pd.DataFrame([other]))

    assert bool(compared.iloc[0]["decision_path_exact"]) is True
    assert bool(compared.iloc[0]["exact"]) is False
