from __future__ import annotations

import pandas as pd

from alphaquest.backtest.event_replay_cache import (
    event_replay_cache_key,
    load_event_replay_cache,
    write_event_replay_cache,
)


def _result():
    return {
        "trades": pd.DataFrame([{"trade_id": 1, "net_pnl": 10.0}]),
        "daily": pd.DataFrame([{"session_date": "2026-01-02", "net_pnl": 10.0}]),
        "session_audits": pd.DataFrame([{"session_date": "2026-01-02", "events": 5}]),
        "event_transitions": pd.DataFrame([{"event_index": 3, "transition": "entry_filled"}]),
        "metrics": {"total_trades": 1},
        "diagnostics": {"events": 5},
        "reproducibility": {"engine_lane": "canonical_event_replay"},
    }


def test_event_replay_result_cache_is_hash_bound_and_detects_tampering(tmp_path):
    config = {"strategy_name": "demo", "core": {"initial_balance": 50_000}}
    key = write_event_replay_cache(config, "input-hash", _result(), project_root=tmp_path)
    assert key == event_replay_cache_key(config, "input-hash")

    loaded = load_event_replay_cache(config, "input-hash", project_root=tmp_path)
    assert loaded is not None
    assert loaded["metrics"]["total_trades"] == 1
    assert loaded["reproducibility"]["result_cache_hit"] is True

    trades = tmp_path / "run-store" / "event-replay-cache" / key / "trades.parquet"
    trades.write_bytes(trades.read_bytes() + b"drift")
    assert load_event_replay_cache(config, "input-hash", project_root=tmp_path) is None


def test_event_replay_result_cache_misses_when_config_or_data_changes(tmp_path):
    config = {
        "strategy": {"event": {"module": "demo", "params": {"threshold": 10}}},
        "core": {"initial_balance": 50_000},
    }
    write_event_replay_cache(config, "input-hash", _result(), project_root=tmp_path)

    changed = {
        "strategy": {"event": {"module": "demo", "params": {"threshold": 11}}},
        "core": {"initial_balance": 50_000},
    }
    assert load_event_replay_cache(changed, "input-hash", project_root=tmp_path) is None
    assert load_event_replay_cache(config, "other-input", project_root=tmp_path) is None


def test_event_replay_cache_reuses_outputs_across_attempt_identity_and_worker_count(tmp_path):
    first = {
        "attempt_id": "first",
        "research_metadata": {"validation_gate": {"evidence_dir": "first"}},
        "symbol": "ES",
        "strategy": {"event": {"module": "demo", "params": {"threshold": 10}}},
        "core": {
            "initial_balance": 50_000,
            "event_replay_result_cache": True,
            "event_replay_session_workers": 4,
        },
    }
    second = {
        **first,
        "attempt_id": "second",
        "research_metadata": {"validation_gate": {"evidence_dir": "second"}},
        "core": {
            **first["core"],
            "event_replay_session_workers": 2,
            "event_replay_idle_batch": False,
            "event_replay_strategy_hints": False,
        },
    }
    key = write_event_replay_cache(first, "input-hash", _result(), project_root=tmp_path)

    assert event_replay_cache_key(second, "input-hash") == key
    assert load_event_replay_cache(second, "input-hash", project_root=tmp_path) is not None

    changed = {
        **second,
        "strategy": {"event": {"module": "demo", "params": {"threshold": 11}}},
    }
    assert load_event_replay_cache(changed, "input-hash", project_root=tmp_path) is None

    lean_grid = {
        **second,
        "core": {
            **second["core"],
            "event_replay_collect_transitions": False,
        },
    }
    assert event_replay_cache_key(lean_grid, "input-hash") != key
    assert load_event_replay_cache(lean_grid, "input-hash", project_root=tmp_path) is None
