from __future__ import annotations

import pandas as pd

from propstack.validation import audit_trade_exit_path, enrich_exit_audits


TZ = "America/New_York"


def _trade(**overrides):
    row = {
        "trade_id": 1,
        "direction": "long",
        "entry_time": pd.Timestamp("2024-01-03 09:31:00", tz=TZ),
        "entry_price": 100.0,
        "stop_price": 99.0,
        "target_price": 101.0,
        "exit_time": pd.Timestamp("2024-01-03 09:31:03", tz=TZ),
        "exit_price": 101.0,
        "exit_reason": "target",
    }
    row.update(overrides)
    return pd.Series(row)


def _ticks(prices):
    start = pd.Timestamp("2024-01-03 09:31:00", tz=TZ)
    return pd.DataFrame(
        [
            {
                "trade_id": 1,
                "timestamp": start + pd.Timedelta(seconds=index),
                "price": price,
                "volume": 1,
            }
            for index, price in enumerate(prices)
        ]
    )


def test_exit_path_audit_long_target_first():
    audit = audit_trade_exit_path(_trade(), _ticks([100.0, 100.5, 101.0]), tick_size=0.25)

    assert audit["first_touch_decision"] == "target"
    assert audit["first_touch_tp_price"] == 101.0
    assert audit["first_touch_sl_time"] is None
    assert audit["mfe_ticks"] == 4
    assert audit["mae_ticks"] == 0
    assert audit["engine_exit_matches_path"] is True


def test_exit_path_audit_long_stop_first():
    audit = audit_trade_exit_path(
        _trade(exit_price=99.0, exit_reason="stop"),
        _ticks([100.0, 99.5, 99.0, 101.0]),
        tick_size=0.25,
    )

    assert audit["first_touch_decision"] == "stop"
    assert audit["first_touch_sl_price"] == 99.0
    assert audit["first_touch_tp_price"] == 101.0
    assert audit["engine_exit_matches_path"] is True


def test_exit_path_audit_same_bar_target_first_by_tick():
    existing = pd.Series({"trade_id": 1, "same_bar_ambiguous": True, "ambiguity_resolution": "pessimistic_stop_first"})

    audit = audit_trade_exit_path(_trade(), _ticks([100.0, 101.0, 99.0]), tick_size=0.25, existing_audit=existing)

    assert audit["first_touch_decision"] == "target"
    assert audit["first_touch_tp_price"] == 101.0
    assert audit["first_touch_sl_price"] == 99.0
    assert audit["engine_exit_matches_path"] is True
    assert "same_bar_resolved_by_tick_path" in audit["warning_flags"]


def test_exit_path_audit_same_bar_stop_first_by_tick_detects_mismatch():
    existing = pd.Series({"trade_id": 1, "same_bar_ambiguous": True, "ambiguity_resolution": "detail_data"})

    audit = audit_trade_exit_path(_trade(exit_reason="target"), _ticks([100.0, 99.0, 101.0]), tick_size=0.25, existing_audit=existing)

    assert audit["first_touch_decision"] == "stop"
    assert audit["engine_exit_matches_path"] is False
    assert "engine_target_but_tick_stop_first" in audit["warning_flags"]


def test_exit_path_audit_neither_touched_forced_flatten():
    audit = audit_trade_exit_path(
        _trade(exit_price=100.25, exit_reason="forced_apex_flatten"),
        _ticks([100.0, 100.25, 100.5]),
        tick_size=0.25,
    )

    assert audit["first_touch_decision"] is None
    assert audit["tick_count_checked"] == 3
    assert audit["engine_exit_matches_path"] is None
    assert not audit["warning_flags"] or "forced_flatten_after_normal_exit_touch" not in audit["warning_flags"]


def test_exit_path_audit_forced_flatten_after_normal_touch_warns():
    audit = audit_trade_exit_path(
        _trade(exit_price=100.75, exit_reason="forced_apex_flatten"),
        _ticks([100.0, 101.0, 100.75]),
        tick_size=0.25,
    )

    assert audit["first_touch_decision"] == "target"
    assert "forced_flatten_after_normal_exit_touch" in audit["warning_flags"]


def test_exit_path_audit_gap_through_stop_edge_case():
    audit = audit_trade_exit_path(
        _trade(exit_price=98.5, exit_reason="stop"),
        _ticks([98.5, 98.75]),
        tick_size=0.25,
    )

    assert audit["first_touch_decision"] == "stop"
    assert audit["first_touch_sl_price"] == 98.5
    assert "first_tick_through_stop" in audit["warning_flags"]


def test_enrich_exit_audits_adds_path_fields_to_existing_audit():
    trades = pd.DataFrame([_trade()])
    existing = pd.DataFrame([{"trade_id": 1, "same_bar_ambiguous": False}])

    enriched = enrich_exit_audits(trades, existing, _ticks([100.0, 101.0]), tick_size=0.25)

    assert enriched.loc[0, "trade_id"] == 1
    assert enriched.loc[0, "first_touch_decision"] == "target"
    assert enriched.loc[0, "tick_count_checked"] == 2
    assert bool(enriched.loc[0, "engine_exit_matches_path"]) is True
