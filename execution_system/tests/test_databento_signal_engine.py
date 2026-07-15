from __future__ import annotations

import copy
import importlib.util
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path

import pandas as pd
import pytest


ENGINE_PATH = Path(__file__).resolve().parents[1] / "databento_signal_engine.py"
EXECUTION_DIR = ENGINE_PATH.parent
SPEC = importlib.util.spec_from_file_location("databento_signal_engine", ENGINE_PATH)
engine = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = engine
SPEC.loader.exec_module(engine)


def ts(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="UTC")


def prefixed_json_line(output: str, prefix: str) -> dict:
    marker = f"{prefix} "
    for line in output.splitlines():
        if line.startswith(marker) and line[len(marker) :].startswith("{"):
            return json.loads(line[len(marker) :])
    raise AssertionError(f"{prefix} JSON line not found in output:\n{output}")


def load_execution_config(name: str) -> dict:
    cfg = engine.load_yaml(EXECUTION_DIR / name)
    cfg.setdefault("engine", {}).setdefault("console", {})["debug"] = True
    cfg["engine"].setdefault("process_lock", {})["path"] = str(
        Path("/tmp") / f"alphaquest_signal_engine_test_{os.getpid()}_{name}.lock"
    )
    if name == "dummy_delta_signal_engine.example.yaml":
        cost_guard = cfg.setdefault("databento", {}).setdefault("live", {}).setdefault("cost_guard", {})
        cost_guard["allow_live_subscription"] = False
        cost_guard["acknowledge_live_data_may_be_billable"] = False
    return cfg


def allow_test_live_subscription(cfg: dict) -> None:
    cfg["databento"]["live"]["allow_live_without_metadata_preflight"] = True
    cfg["databento"]["live"].setdefault("cost_guard", {}).update(
        {
            "enabled": True,
            "allow_live_subscription": True,
            "acknowledge_live_data_may_be_billable": True,
        }
    )


def test_databento_api_key_missing_mentions_shell_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CUSTOM_DATABENTO_KEY", raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        engine.databento_api_key({"api_key_env": "CUSTOM_DATABENTO_KEY"})

    message = str(excinfo.value)
    assert "$CUSTOM_DATABENTO_KEY" in message
    assert "databento.api_key" in message
    assert "sourced that profile" in message


def test_databento_api_key_status_is_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUSTOM_DATABENTO_KEY", "secret-test-key")

    status = engine.databento_api_key_status({"api_key_env": "CUSTOM_DATABENTO_KEY"}, required=True)

    assert status == {
        "ok": True,
        "required": True,
        "api_key_env": "CUSTOM_DATABENTO_KEY",
        "source": "$CUSTOM_DATABENTO_KEY",
        "configured_directly": False,
        "env_present": True,
        "key_present": True,
        "key_length": len("secret-test-key"),
        "value_redacted": True,
    }
    assert "secret-test-key" not in json.dumps(status)


def test_preflight_report_includes_redacted_databento_key_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUSTOM_DATABENTO_KEY", "secret-test-key")
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key_env"] = "CUSTOM_DATABENTO_KEY"
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    api_key_status = signal_engine.preflight_report()["databento"]["api_key"]

    assert api_key_status["ok"] is True
    assert api_key_status["required"] is False
    assert api_key_status["source"] == "$CUSTOM_DATABENTO_KEY"
    assert api_key_status["key_present"] is True
    assert api_key_status["value_redacted"] is True
    assert "secret-test-key" not in json.dumps(api_key_status)


def test_example_configs_write_runtime_outputs_under_ignored_runtime_dir() -> None:
    gitignore_text = (EXECUTION_DIR / ".gitignore").read_text(encoding="utf-8")
    assert "data/runtime/" in gitignore_text
    assert "data/alerts/*.jsonl" in gitignore_text

    for config_name in [
        "signal_engine.example.yaml",
        "dummy_delta_signal_engine.example.yaml",
        "morning_orderflow_momentum_signal_engine.example.yaml",
    ]:
        cfg = load_execution_config(config_name)
        engine_cfg = cfg["engine"]
        output_paths = [
            engine_cfg["alerts_path"],
            engine_cfg["setup_alerts"]["path"],
            engine_cfg["execution_intents"]["path"],
        ]
        assert all(path.startswith("data/runtime/alerts/") for path in output_paths)
        assert not any(path.startswith("data/alerts/") for path in output_paths)


def test_example_configs_default_to_compact_console() -> None:
    for config_name in [
        "signal_engine.example.yaml",
        "dummy_delta_signal_engine.example.yaml",
        "morning_orderflow_momentum_signal_engine.example.yaml",
    ]:
        cfg = engine.load_yaml(EXECUTION_DIR / config_name)

        normalized = engine.normalize_console_config(cfg["engine"].get("console", {}))
        assert normalized["debug"] is False

    morning_cfg = engine.load_yaml(EXECUTION_DIR / "morning_orderflow_momentum_signal_engine.example.yaml")
    live_stream = engine.normalize_console_config(morning_cfg["engine"].get("console", {}))["live_stream"]
    assert live_stream == {
        "enabled": True,
        "print_trade_ticks": True,
        "print_completed_bars": True,
        "print_session_metrics": True,
        "tick_throttle_seconds": 1.0,
    }


def test_console_live_stream_config_defaults_to_off_when_missing() -> None:
    assert engine.normalize_console_config({"debug": False}) == {"debug": False}
    assert engine.normalize_live_console_stream_config({}) == {
        "enabled": False,
        "print_trade_ticks": True,
        "print_completed_bars": True,
        "print_session_metrics": True,
        "tick_throttle_seconds": 1.0,
    }


def test_console_compact_mode_suppresses_raw_json(capsys: pytest.CaptureFixture[str]) -> None:
    previous_debug = engine.CONSOLE_DEBUG_JSON
    try:
        engine.configure_console_output({"debug": False})

        engine.print_json(
            {
                "event": "historical_timeseries_get_range_blocked_by_guard",
                "reason": "cost guard approval was missing",
                "timeseries_get_range_attempted": False,
            },
            prefix="SYSTEM_ALERT",
        )

        captured = capsys.readouterr().out.strip()
        assert captured.startswith("SYSTEM_ALERT historical_timeseries_get_range_blocked_by_guard")
        assert "timeseries_get_range_attempted=false" in captured
        assert "{" not in captured
        assert '"event"' not in captured
    finally:
        engine.configure_console_output({"debug": previous_debug})


def test_console_debug_mode_preserves_full_json(capsys: pytest.CaptureFixture[str]) -> None:
    previous_debug = engine.CONSOLE_DEBUG_JSON
    try:
        engine.configure_console_output({"debug": True})

        engine.print_json(
            {"event": "historical_timeseries_get_range_blocked_by_guard", "timeseries_get_range_attempted": False},
            prefix="SYSTEM_ALERT",
        )

        captured = capsys.readouterr().out.strip()
        assert captured.startswith("SYSTEM_ALERT {")
        assert '"event": "historical_timeseries_get_range_blocked_by_guard"' in captured
        assert '"timeseries_get_range_attempted": false' in captured
    finally:
        engine.configure_console_output({"debug": previous_debug})


def test_read_bars_file_treats_plain_timestamp_as_market_timezone(tmp_path: Path) -> None:
    path = tmp_path / "local_timestamp_bars.csv"
    pd.DataFrame(
        [
            {
                "timestamp": "2026-06-11 09:30:00",
                "symbol": "ES",
                "contract_symbol": "ESM6",
                "open": 5000.0,
                "high": 5001.0,
                "low": 4999.5,
                "close": 5000.25,
                "volume": 100.0,
                "signed_volume": 10.0,
                "buy_volume": 55.0,
                "sell_volume": 45.0,
                "trades": 25,
            }
        ]
    ).to_csv(path, index=False)

    bars = engine.read_bars_file(
        path,
        root_symbol="ES",
        timezone="America/New_York",
        source="test",
        required_source_columns=("timestamp", "open", "high", "low", "close", "volume", "signed_volume"),
    )

    assert len(bars) == 1
    assert bars[0].timestamp_utc == ts("2026-06-11 13:30:00")


def test_execution_system_has_no_legacy_broker_entrypoint() -> None:
    assert not (EXECUTION_DIR / "strategy_execution_bridge.py").exists()


def test_preflight_report_includes_live_safety_stop_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = signal_engine.preflight_report()
    safety_stops = report["databento"]["live_safety_stops"]

    assert report["databento"]["live_metadata_preflight"] is True
    assert report["databento"]["live_cost_guard"] == {
        "enabled": True,
        "allowed": False,
        "allow_live_subscription": False,
        "acknowledge_live_data_may_be_billable": False,
    }
    assert safety_stops == {
        "stop_on_disconnect": True,
        "stop_on_no_records": True,
        "stop_on_no_trade_ticks": True,
        "stop_on_no_completed_bars": True,
        "stop_on_no_evaluable_strategies": True,
        "stop_on_partial_unevaluable_strategies": True,
        "stop_on_stale_trade_tick": True,
        "stop_on_future_trade_tick": True,
        "stop_on_unmatched_contract_symbol": True,
        "stop_on_state_lock_timeout": False,
    }
    assert report["databento"]["live_stop_on_unmatched_contract_symbol"] is True


def test_preflight_report_includes_delta_unclassified_quality_guard() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = signal_engine.preflight_report()
    guard = report["data_quality"]["delta_unclassified"]

    assert guard == {
        "enabled": True,
        "delta_methods": ["price_vs_quote"],
        "max_selected_unclassified_fraction": 0.25,
        "min_checked_volume": 1.0,
        "require_diagnostic": True,
        "severity": "error",
    }


def test_preflight_defaults_live_disabled_when_live_config_is_missing() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"].pop("live", None)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = signal_engine.preflight_report()

    assert report["databento"]["live_enabled"] is False
    assert report["databento"]["live_cost_guard"]["allowed"] is False


def test_cli_live_and_skip_historical_are_reflected_in_effective_preflight() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["historical"]["enabled"] = True
    args = engine.argparse.Namespace(
        project_root=None,
        strategy_config=None,
        dry_run_alerts=False,
        skip_historical=True,
        refresh_historical=False,
        live=True,
        databento_symbols=None,
        databento_stype_in=None,
        databento_stype_out=None,
    )

    effective = engine.apply_cli_overrides(cfg, args)
    signal_engine = engine.SignalEngine(effective, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    report = signal_engine.preflight_report()

    assert cfg["databento"]["historical"]["enabled"] is True
    assert cfg["databento"]["live"]["enabled"] is False
    assert effective["databento"]["historical"]["enabled"] is False
    assert effective["databento"]["live"]["enabled"] is True
    assert report["databento"]["historical_enabled"] is False
    assert report["databento"]["live_enabled"] is True


def test_cli_refresh_historical_is_reflected_in_effective_preflight() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["historical"] = {"enabled": True, "refresh": False}
    args = engine.argparse.Namespace(
        project_root=None,
        strategy_config=None,
        dry_run_alerts=False,
        skip_historical=False,
        refresh_historical=True,
        live=False,
        databento_symbols=None,
        databento_stype_in=None,
        databento_stype_out=None,
    )

    effective = engine.apply_cli_overrides(cfg, args)
    signal_engine = engine.SignalEngine(effective, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    assert cfg["databento"]["historical"]["refresh"] is False
    assert effective["databento"]["historical"]["refresh"] is True
    assert signal_engine.preflight_report()["databento"]["historical_enabled"] is True


def sample_entry_alert() -> dict:
    alert = {
        "event": "entry_signal",
        "alert_contract_version": engine.ALERT_CONTRACT_VERSION,
        "alert_id": "abc",
        "setup_id": "setup-abc",
        "pending_signal_key": "pending-abc",
        "strategy_id": "dummy",
        "strategy_name": "dummy_delta_interval",
        "strategy_config": "builtin:builtin_delta_interval",
        "engine_config": "execution_system/dummy_delta_signal_engine.example.yaml",
        "symbol": "ES",
        "contract_symbol": "ESM6",
        "timeframe": "1m",
        "delta_method": "aggressor_side",
        "signal_timestamp": "2026-06-11T09:30:00-04:00",
        "entry_timestamp": "2026-06-11T13:31:00+00:00",
        "entry_timestamp_utc": "2026-06-11T13:31:00+00:00",
        "session_date": "2026-06-11",
        "direction": "long",
        "side": "buy",
        "quantity": 2,
        "suggested_quantity": 2,
        "order_type": "market",
        "entry_price": 5000.25,
        "entry_basis_price": 5000.25,
        "entry_slippage_ticks": 0.0,
        "stop_loss_price": 4999.25,
        "take_profit_price": 5001.25,
        "stop_loss_points": 1.0,
        "take_profit_points": 1.0,
        "tick_size": 0.25,
        "tick_value": 12.5,
        "risk_dollars": 100.0,
        "reward_dollars": 100.0,
        "signal": {"metadata": {"delta": 42, "latest_completed_bar_volume": 1000}},
        "sizing": {"position_sizing_mode": "fixed_contracts"},
    }
    alert["price_normalization"] = engine.price_normalization_report(
        tick_size=alert["tick_size"],
        entry_basis_price_raw=alert["entry_basis_price"],
        entry_price_raw=alert["entry_price"],
        stop_loss_price_raw=alert["stop_loss_price"],
        take_profit_price_raw=alert["take_profit_price"],
        entry_basis_price=alert["entry_basis_price"],
        entry_price=alert["entry_price"],
        stop_loss_price=alert["stop_loss_price"],
        take_profit_price=alert["take_profit_price"],
    )
    alert["strategy_config_fingerprint"] = engine.config_fingerprint_payload(
        {"strategy_id": alert["strategy_id"], "strategy_name": alert["strategy_name"]},
        kind="test_strategy",
        path=alert["strategy_config"],
    )
    alert["engine_config_fingerprint"] = engine.config_fingerprint_payload(
        {"engine": {"symbol": alert["symbol"]}, "databento": {"delta_method": alert["delta_method"]}},
        kind="test_engine",
        path=alert["engine_config"],
    )
    alert["execution_intent"] = engine.build_execution_intent(alert, max_entry_lag_seconds=120)
    return alert


def sample_entry_alert_with_entry_timestamp(
    entry_utc: object,
    *,
    intent_ttl_seconds: float = 120.0,
    max_entry_lag_seconds: float = 120.0,
) -> dict:
    alert = sample_entry_alert()
    entry_ts = engine.normalize_utc_timestamp(entry_utc)
    signal_ts = entry_ts - pd.Timedelta(minutes=1)
    alert["signal_timestamp"] = engine.format_timestamp(signal_ts)
    alert["entry_timestamp"] = engine.format_timestamp(entry_ts)
    alert["entry_timestamp_utc"] = engine.format_timestamp(entry_ts)
    alert["execution_intent"] = engine.build_execution_intent(
        alert,
        max_entry_lag_seconds=max_entry_lag_seconds,
        intent_ttl_seconds=intent_ttl_seconds,
    )
    return alert


def sample_fresh_entry_alert() -> dict:
    return sample_entry_alert_with_entry_timestamp(
        pd.Timestamp.utcnow() - pd.Timedelta(seconds=5),
        intent_ttl_seconds=30.0,
    )


def sample_pending_setup(strategy: object) -> engine.PendingSignal:
    return engine.PendingSignal(
        strategy=strategy,
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
            "timestamp_utc": ts("2026-06-11 13:30:00"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6",
            "close": 5000.25,
        },
        signal_obj=engine.EngineSignal(
            direction="long",
            level_type="dummy_delta_interval",
            metadata={
                "delta": 42,
                "latest_completed_bar_low": 4999.25,
                "latest_completed_bar_high": 5001.0,
            },
        ),
        due_utc=ts("2026-06-11 13:31:00"),
        queued_at_utc=ts("2026-06-11 13:30:01"),
        key="dummy-setup-key",
    )


def sample_source_bar(**overrides: object) -> engine.SourceMinuteBar:
    values = {
        "timestamp_utc": ts("2026-06-11 13:30:00"),
        "symbol": "ES",
        "contract_symbol": "ESM6",
        "open": 5000.0,
        "high": 5001.0,
        "low": 4999.5,
        "close": 5000.25,
        "volume": 100.0,
        "signed_volume": 10.0,
        "buy_volume": 55.0,
        "sell_volume": 45.0,
        "trades": 25,
        "large": {},
        "source": "test",
    }
    values.update(overrides)
    return engine.SourceMinuteBar(**values)


def morning_orderflow_replay_bars(*, signed_volume: float = 5.0, final_price: float = 5003.25) -> list[engine.SourceMinuteBar]:
    bars: list[engine.SourceMinuteBar] = []
    for index, timestamp in enumerate(pd.date_range("2026-06-11 13:30:00", periods=61, freq="min", tz="UTC")):
        open_price = 5000.0 + min(index, 13) * 0.25
        close_price = 5000.25 + min(index, 12) * 0.25
        if index >= 13:
            close_price = final_price
        bars.append(
            sample_source_bar(
                timestamp_utc=pd.Timestamp(timestamp),
                open=open_price,
                high=max(open_price, close_price) + 0.25,
                low=min(open_price, close_price) - 0.25,
                close=close_price,
                volume=100.0,
                signed_volume=signed_volume,
                buy_volume=(100.0 + signed_volume) / 2.0,
                sell_volume=(100.0 - signed_volume) / 2.0,
                trades=20,
            )
        )
    return bars


def write_large_flow_strategy_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "campaign_id": "test_large_flow",
                "variant_id": "large20_flow",
                "strategy_name": "trade_orderflow_multi_pressure",
                "symbol": "ES",
                "timeframe": "1m",
                "data": {
                    "dataset_id": "test",
                    "source_timeframe": "1m",
                    "source": "csv",
                    "raw_csv": "data/test.csv",
                    "symbol": "ES",
                    "timezone": "America/New_York",
                    "exchange_timezone": "America/New_York",
                    "rth_start": "09:30:00",
                    "rth_end": "15:59:00",
                    "trade_orderflow_features": {
                        "enabled": True,
                        "windows": [5],
                        "large_trade_sizes": [],
                        "min_period_fraction": 1.0,
                    },
                },
                "strategy": {
                    "entry": {
                        "module": "trade_orderflow_multi_pressure",
                        "params": {
                            "slots": [
                                {
                                    "slot_id": "large20_1000_5m",
                                    "entry_time": "10:00:00",
                                    "flow_column": "trade_orderflow_large20_imbalance_5",
                                    "flow_threshold": 0.1,
                                    "stop_pct": 0.006,
                                    "target_r_multiple": 1.0,
                                }
                            ]
                        },
                    },
                    "sl": {"module": "signal_percent_from_entry", "params": {"default_stop_pct": 0.006}},
                    "tp": {"module": "signal_fixed_r", "params": {"default_target_r_multiple": 1.0}},
                },
                "core": {
                    "initial_balance": 150000,
                    "tick_size": 0.25,
                    "tick_value": 12.5,
                    "slippage_ticks": 1,
                    "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
                },
            }
        ),
        encoding="utf-8",
    )


def test_replay_require_signal_reports_failure_when_no_entry_signal(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["dry_run_alerts"] = True
    cfg["engine"]["replay_seed_bars"] = 0
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    replay_path = tmp_path / "no_signal_replay.csv"
    engine.write_bars_file(
        replay_path,
        [
            sample_source_bar(signed_volume=0.0, buy_volume=50.0, sell_volume=50.0),
            sample_source_bar(timestamp_utc=ts("2026-06-11 13:31:00"), open=5000.25),
        ],
        timezone="America/New_York",
    )
    args = engine.argparse.Namespace(
        max_replay_bars=0,
        replay_stop_after_signal=False,
        replay_require_signal=True,
    )

    report = engine.replay_bars(signal_engine, replay_path, args)

    captured = capsys.readouterr()
    assert "replay_required_signal_missing" in captured.out
    assert report["ok"] is False
    assert report["entry_alerts"] == 0
    assert report["require_signal"] is True


def test_replay_require_signal_passes_when_entry_signal_emits(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["dry_run_alerts"] = True
    cfg["engine"]["replay_seed_bars"] = 0
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    replay_path = tmp_path / "signal_replay.csv"
    engine.write_bars_file(
        replay_path,
        [
            sample_source_bar(signed_volume=10.0),
            sample_source_bar(timestamp_utc=ts("2026-06-11 13:31:00"), open=5000.25),
        ],
        timezone="America/New_York",
    )
    args = engine.argparse.Namespace(
        max_replay_bars=0,
        replay_stop_after_signal=True,
        replay_require_signal=True,
        replay_require_healthy_strategies=True,
    )

    report = engine.replay_bars(signal_engine, replay_path, args)

    captured = capsys.readouterr()
    assert "replay_required_signal_missing" not in captured.out
    assert "ENTRY_SIGNAL" in captured.out
    assert report["ok"] is True
    assert report["entry_alerts"] == 1
    assert report["require_signal"] is True
    assert report["require_healthy_strategies"] is True
    assert report["strategy_health_ok"] is True
    assert report["replay_health_ok"] is True
    assert report["active_strategy_count"] == 1
    assert report["disabled_strategy_count"] == 0
    assert report["runtime_error_strategy_count"] == 0
    assert report["unevaluated_active_strategy_count"] == 0
    assert report["source_contract_filter_starved"] is False
    assert report["dry_run_alerts"] is True
    assert report["trade_setups"] == 1
    assert report["pending_signals"] == 0
    assert report["pending_status"]["count"] == 0
    assert report["strategy_health"][0]["evaluated_strategy_row_count"] == 1
    assert report["alert_file"]["writes_succeeded"] == 0
    assert report["setup_alerts"]["writes_succeeded"] == 0
    assert report["execution_intents"]["writes_succeeded"] == 0
    assert report["source_contract_filter"]["enabled"] is True


def test_dummy_delta_config_evaluates_eth_bars(capsys: pytest.CaptureFixture[str]) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["dry_run_alerts"] = True
    cfg["engine"]["operator"]["sound"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.on_completed_source_bar(sample_source_bar(timestamp_utc=ts("2026-06-11 20:00:00")))
    signal_engine.on_completed_source_bar(
        sample_source_bar(
            timestamp_utc=ts("2026-06-11 20:01:00"),
            open=5000.25,
            high=5001.25,
            low=5000.0,
            close=5000.5,
        )
    )

    captured = capsys.readouterr()
    strategy_health = signal_engine.strategy_health_report()[0]
    assert strategy_health["evaluated_strategy_row_count"] >= 2
    assert strategy_health["last_evaluated_strategy_timestamp"] == "2026-06-11T16:01:00-04:00"
    assert signal_engine.setup_notice_count == 1
    assert "TRADE_SETUP" in captured.out


def test_morning_orderflow_config_matches_live_tracker_params() -> None:
    cfg = load_execution_config("morning_orderflow_momentum_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "morning_orderflow_momentum_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]
    params = strategy.variant_config["strategy"]["entry"]["params"]

    assert params["setup_mode"] == "two_sided_signed_flow_continuation"
    assert params["direction_mode"] == "two_sided_continuation"
    assert params["flow_mode"] == "signed_imbalance"
    assert params["signal_time"] == "10:30:00"
    assert params["flatten_time"] == "15:30:00"
    assert params["min_signal_return_ticks"] == 12
    assert params["min_orderflow_imbalance"] == 0.01
    assert params["stop_pct"] == 0.0025
    assert params["target_r_multiple"] == 3.0
    assert params["pre_trade_warning"] == {"enabled": True, "bars_before_entry": 1, "play_sound": True}
    assert params["max_trades_per_day"] == 1

    requirement = signal_engine.data_requirements[0]
    assert "morning_orderflow_momentum" in requirement.feature_families
    assert "trade_orderflow" in requirement.feature_families
    assert requirement.max_feature_window_bars >= 60
    assert requirement.recommended_source_bars >= 60
    assert {"open", "high", "low", "close", "volume", "signed_volume"}.issubset(requirement.source_columns)
    assert "large10_signed_volume" not in requirement.source_columns
    assert "large20_signed_volume" not in requirement.source_columns

    runtime_columns = set(strategy.required_runtime_feature_columns())
    assert {
        "timestamp",
        "contract_symbol",
        "session_date",
        "is_rth",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "signed_volume",
    }.issubset(runtime_columns)


def test_morning_orderflow_replay_emits_trade_warning_one_bar_before_entry(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("morning_orderflow_momentum_signal_engine.example.yaml")
    cfg["engine"]["dry_run_alerts"] = True
    cfg["engine"]["replay_seed_bars"] = 0
    cfg["databento"]["historical"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "morning_orderflow_momentum_signal_engine.example.yaml")
    replay_path = tmp_path / "morning_orderflow_warning.csv"
    engine.write_bars_file(replay_path, morning_orderflow_replay_bars(), timezone="America/New_York")
    args = engine.argparse.Namespace(
        max_replay_bars=0,
        replay_stop_after_signal=True,
        replay_require_signal=True,
        replay_require_healthy_strategies=True,
    )

    report = engine.replay_bars(signal_engine, replay_path, args)

    captured = capsys.readouterr()
    warning = prefixed_json_line(captured.out, "TRADE_WARNING")
    setup = prefixed_json_line(captured.out, "TRADE_SETUP")
    entry = prefixed_json_line(captured.out, "ENTRY_SIGNAL")
    assert captured.out.index("TRADE_WARNING") < captured.out.index("TRADE_SETUP") < captured.out.index("ENTRY_SIGNAL")
    assert report["ok"] is True
    assert report["trade_warnings"] == 1
    assert warning["strategy_id"] == "morning_orderflow_momentum_two_sided_signed_flow_continuation_live"
    assert warning["direction"] == "long"
    assert warning["status"] == "prepare_only_not_actionable"
    assert warning["warning_timestamp_utc"] == "2026-06-11T14:29:00+00:00"
    assert warning["expected_entry_timestamp_utc"] == "2026-06-11T14:30:00+00:00"
    assert warning["warning_lead_bars"] == 1
    assert warning["warning_lead_seconds"] == 60.0
    assert warning["trade_plan_preview"]["status"] == "estimated"
    assert warning["trade_plan_preview"]["estimated_entry_price"] == 5003.5
    assert warning["trade_plan_preview"]["quantity"] == 1
    warning_fields = warning["signal"]["report_fields"]
    assert warning_fields["warning_non_time_conditions_satisfied"] is True
    assert warning_fields["warning_time_condition_satisfied"] is False
    assert warning_fields["source_window_return_ticks"] >= 12.0
    assert warning_fields["primary_orderflow_imbalance"] >= 0.01
    assert setup["due_timestamp_utc"] == entry["entry_timestamp_utc"]


def test_morning_orderflow_replay_emits_entry_signal_at_1030_open(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("morning_orderflow_momentum_signal_engine.example.yaml")
    cfg["engine"]["dry_run_alerts"] = True
    cfg["engine"]["replay_seed_bars"] = 0
    cfg["databento"]["historical"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "morning_orderflow_momentum_signal_engine.example.yaml")
    replay_path = tmp_path / "morning_orderflow_signal.csv"
    engine.write_bars_file(replay_path, morning_orderflow_replay_bars(), timezone="America/New_York")
    args = engine.argparse.Namespace(
        max_replay_bars=0,
        replay_stop_after_signal=True,
        replay_require_signal=True,
        replay_require_healthy_strategies=True,
    )

    report = engine.replay_bars(signal_engine, replay_path, args)

    captured = capsys.readouterr()
    alert = prefixed_json_line(captured.out, "ENTRY_SIGNAL")
    report_fields = alert["signal"]["report_fields"]
    assert report["ok"] is True
    assert report["entry_alerts"] == 1
    assert report["trade_setups"] == 1
    assert report["strategy_health_ok"] is True
    assert alert["strategy_id"] == "morning_orderflow_momentum_two_sided_signed_flow_continuation_live"
    assert alert["direction"] == "long"
    assert alert["quantity"] == 1
    assert alert["signal_timestamp"] == "2026-06-11T10:29:00-04:00"
    assert alert["entry_timestamp_utc"] == "2026-06-11T14:30:00+00:00"
    assert alert["entry_price"] == 5003.5
    assert alert["stop_loss_price"] == 4990.75
    assert alert["take_profit_price"] == 5041.75
    assert report_fields["min_signal_return_ticks"] == 12.0
    assert report_fields["min_orderflow_imbalance"] == 0.01
    assert report_fields["source_window_return_ticks"] >= 12.0
    assert report_fields["primary_orderflow_imbalance"] >= 0.01
    assert report_fields["morning_orderflow_intended_entry_timestamp"] == "2026-06-11T10:30:00-04:00"


def test_morning_orderflow_replay_does_not_emit_when_imbalance_threshold_misses(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("morning_orderflow_momentum_signal_engine.example.yaml")
    cfg["engine"]["dry_run_alerts"] = True
    cfg["engine"]["replay_seed_bars"] = 0
    cfg["databento"]["historical"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "morning_orderflow_momentum_signal_engine.example.yaml")
    replay_path = tmp_path / "morning_orderflow_no_signal.csv"
    engine.write_bars_file(
        replay_path,
        morning_orderflow_replay_bars(signed_volume=0.5),
        timezone="America/New_York",
    )
    args = engine.argparse.Namespace(
        max_replay_bars=0,
        replay_stop_after_signal=False,
        replay_require_signal=False,
        replay_require_healthy_strategies=True,
    )

    report = engine.replay_bars(signal_engine, replay_path, args)

    captured = capsys.readouterr()
    assert "TRADE_WARNING" not in captured.out
    assert "ENTRY_SIGNAL" not in captured.out
    assert report["ok"] is True
    assert report["trade_warnings"] == 0
    assert report["entry_alerts"] == 0
    assert report["trade_setups"] == 0
    assert report["strategy_health_ok"] is True
    assert report["strategy_health"][0]["evaluated_strategy_row_count"] >= 60


def test_morning_orderflow_live_startup_backfills_missing_current_session_context(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("morning_orderflow_momentum_signal_engine.example.yaml")
    cfg["databento"]["historical"]["enabled"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "morning_orderflow_momentum_signal_engine.example.yaml")
    fetched: list[dict] = []

    def fake_fetch(_: engine.SignalEngine, hist_cfg: dict) -> list[engine.SourceMinuteBar]:
        fetched.append(dict(hist_cfg))
        return morning_orderflow_replay_bars()[:30]

    monkeypatch.setattr(engine, "fetch_databento_historical_bars", fake_fetch)

    report = engine.ensure_live_startup_session_coverage(
        signal_engine,
        historical_skipped=False,
        now_utc=ts("2026-06-11 14:00:30"),
    )

    captured = capsys.readouterr()
    assert report["ok"] is True
    assert report["backfill_attempted"] is True
    assert report["accepted_backfill_bars"] == 30
    assert report["requirements"][0]["expected_bar_count"] == 30
    assert fetched
    assert fetched[0]["start"] == ts("2026-06-11 13:30:00")
    assert fetched[0]["end"] == ts("2026-06-11 14:00:00")
    assert "seed_bars_path" not in fetched[0]
    assert "cache_path" not in fetched[0]
    assert "live_startup_current_session_backfill_start" in captured.out
    assert "live_startup_session_coverage_ok" in captured.out


def test_morning_orderflow_live_startup_fails_when_historical_skipped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("morning_orderflow_momentum_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "morning_orderflow_momentum_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="current-session coverage failed"):
        engine.ensure_live_startup_session_coverage(
            signal_engine,
            historical_skipped=True,
            now_utc=ts("2026-06-11 14:00:30"),
        )

    captured = capsys.readouterr()
    assert "live_startup_session_coverage_failed" in captured.out
    assert '"historical_skipped": true' in captured.out
    assert '"missing_bar_count": 30' in captured.out


def test_morning_orderflow_live_startup_compact_failure_includes_coverage_details(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("morning_orderflow_momentum_signal_engine.example.yaml")
    cfg["engine"]["console"]["debug"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "morning_orderflow_momentum_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="current-session coverage failed"):
        engine.ensure_live_startup_session_coverage(
            signal_engine,
            historical_skipped=True,
            now_utc=ts("2026-06-11 14:00:30"),
        )

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT live_startup_session_coverage_failed" in captured.out
    assert "expected_bar_count=30" in captured.out
    assert "available_bar_count=0" in captured.out
    assert "missing_bar_count=30" in captured.out
    assert "required_start_utc=2026-06-11T13:30:00+00:00" in captured.out
    assert "required_end_utc=2026-06-11T13:59:00+00:00" in captured.out
    assert "first_missing_bar_utc=2026-06-11T13:30:00+00:00" in captured.out
    assert "last_missing_bar_utc=2026-06-11T13:59:00+00:00" in captured.out
    assert "historical_skipped=true" in captured.out
    assert "backfill_attempted=false" in captured.out


def test_morning_orderflow_live_startup_detects_current_session_gap(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("morning_orderflow_momentum_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "morning_orderflow_momentum_signal_engine.example.yaml")
    bars = [
        bar
        for bar in morning_orderflow_replay_bars()[:30]
        if engine.source_bar_timestamp_utc(bar) != ts("2026-06-11 13:45:00")
    ]
    signal_engine.seed(bars, source="historical")

    with pytest.raises(RuntimeError, match="current-session coverage failed"):
        engine.ensure_live_startup_session_coverage(
            signal_engine,
            historical_skipped=True,
            now_utc=ts("2026-06-11 14:00:30"),
        )

    captured = capsys.readouterr()
    assert "live_startup_session_coverage_failed" in captured.out
    assert '"missing_bar_count": 1' in captured.out
    assert "2026-06-11T13:45:00+00:00" in captured.out


def test_morning_orderflow_live_startup_requires_no_current_session_context_before_open(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("morning_orderflow_momentum_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "morning_orderflow_momentum_signal_engine.example.yaml")

    report = engine.ensure_live_startup_session_coverage(
        signal_engine,
        historical_skipped=True,
        now_utc=ts("2026-06-11 13:29:30"),
    )

    captured = capsys.readouterr()
    assert report["ok"] is True
    assert report["requirements"] == []
    assert "live_startup_session_coverage_not_required" in captured.out


def test_deferred_strategy_evaluation_buffers_live_bars_without_signals(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["dry_run_alerts"] = True
    cfg["engine"]["operator"]["sound"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.defer_strategy_evaluation_for_catchup(
        {
            "missing_bar_count": 1,
            "required_start_utc": "2026-06-11T13:30:00+00:00",
            "required_end_utc": "2026-06-11T13:30:00+00:00",
            "first_missing_bar_utc": "2026-06-11T13:30:00+00:00",
            "last_missing_bar_utc": "2026-06-11T13:30:00+00:00",
        }
    )
    capsys.readouterr()

    signal_engine.on_completed_source_bar(sample_source_bar(signed_volume=10.0, source="live"))

    captured = capsys.readouterr()
    assert "TRADE_SETUP" not in captured.out
    assert "ENTRY_SIGNAL" not in captured.out
    assert len(signal_engine.store.bars()) == 1
    assert signal_engine.strategy_evaluation_deferred is True
    assert signal_engine.strategy_evaluation_deferred_bars == 1


def test_run_live_catchup_retry_activates_deferred_strategy_evaluation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0
    cfg["databento"]["historical"]["current_session_backfill"] = {
        "enabled": True,
        "startup_mode": "defer_until_complete",
        "retry_interval_seconds": 1,
        "max_wait_seconds": 0,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    signal_engine.defer_strategy_evaluation_for_catchup(
        {
            "missing_bar_count": 1,
            "required_start_utc": "2026-06-11T13:30:00+00:00",
            "required_end_utc": "2026-06-11T13:30:00+00:00",
            "first_missing_bar_utc": "2026-06-11T13:30:00+00:00",
            "last_missing_bar_utc": "2026-06-11T13:30:00+00:00",
        }
    )
    calls: list[dict[str, object]] = []

    def fake_coverage_check(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "event": "live_startup_session_coverage_ok",
            "ok": True,
            "missing_bar_count": 0,
            "required_start_utc": "2026-06-11T13:30:00+00:00",
            "required_end_utc": "2026-06-11T13:30:00+00:00",
            "requirements": [],
        }

    monkeypatch.setattr(engine, "ensure_live_startup_session_coverage", fake_coverage_check)
    capsys.readouterr()

    rc = engine.run_live(
        signal_engine,
        once=False,
        max_runtime=0.1,
        live_client_factory=lambda **kwargs: FakeLiveClient(connected_after_start=True, **kwargs),
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert calls
    assert calls[0]["historical_skipped"] is False
    assert calls[0]["raise_on_failure"] is False
    assert "live_catchup_backfill_retry" in captured.out
    assert "live_strategy_evaluation_activated" in captured.out
    assert signal_engine.strategy_evaluation_deferred is False


def test_replay_require_healthy_strategies_reports_disabled_strategy_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["dry_run_alerts"] = True
    cfg["engine"]["replay_seed_bars"] = 0
    cfg["engine"]["strategy_errors"]["fail_when_all_strategies_disabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]

    def fail_process(_: engine.BarStore, *, live: bool) -> list[engine.PendingSignal]:
        assert live is True
        raise RuntimeError("replay feature build broke")

    strategy.process_new_completed_bars = fail_process  # type: ignore[method-assign]
    replay_path = tmp_path / "unhealthy_replay.csv"
    engine.write_bars_file(
        replay_path,
        [
            sample_source_bar(signed_volume=10.0),
            sample_source_bar(timestamp_utc=ts("2026-06-11 13:31:00"), open=5000.25),
        ],
        timezone="America/New_York",
    )
    args = engine.argparse.Namespace(
        max_replay_bars=0,
        replay_stop_after_signal=False,
        replay_require_signal=False,
        replay_require_healthy_strategies=True,
    )

    report = engine.replay_bars(signal_engine, replay_path, args)

    captured = capsys.readouterr()
    assert "strategy_runtime_error" in captured.out
    assert "all_strategies_disabled" in captured.out
    assert "replay_strategy_health_failed" in captured.out
    assert report["ok"] is False
    assert report["entry_alerts"] == 0
    assert report["require_healthy_strategies"] is True
    assert report["strategy_health_ok"] is False
    assert report["replay_health_ok"] is False
    assert report["active_strategy_count"] == 0
    assert report["disabled_strategy_count"] == 1
    assert report["runtime_error_strategy_count"] == 1
    assert report["unevaluated_active_strategy_count"] == 0
    assert report["strategy_health"][0]["disabled"] is True
    assert report["strategy_health"][0]["runtime_error_count"] == 1


def test_replay_require_healthy_strategies_fails_when_contract_filter_starves_replay(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["dry_run_alerts"] = True
    cfg["engine"]["replay_seed_bars"] = 1
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    replay_path = tmp_path / "contract_starved_replay.csv"
    engine.write_bars_file(
        replay_path,
        [
            sample_source_bar(contract_symbol="ESM6", signed_volume=10.0),
            sample_source_bar(
                timestamp_utc=ts("2026-06-11 13:31:00"),
                contract_symbol="ESM6-ESU6",
                signed_volume=10.0,
            ),
            sample_source_bar(
                timestamp_utc=ts("2026-06-11 13:32:00"),
                contract_symbol="ESM6-ESU6",
                open=5000.25,
            ),
        ],
        timezone="America/New_York",
    )
    args = engine.argparse.Namespace(
        max_replay_bars=0,
        replay_stop_after_signal=False,
        replay_require_signal=False,
        replay_require_healthy_strategies=True,
    )

    report = engine.replay_bars(signal_engine, replay_path, args)

    captured = capsys.readouterr()
    assert "source_bar_contract_symbol_filtered" in captured.out
    assert "replay_strategy_health_failed" in captured.out
    assert report["ok"] is False
    assert report["require_healthy_strategies"] is True
    assert report["replay_health_ok"] is False
    assert report["accepted_replay_source_bars"] == 0
    assert report["source_contract_filter_replay_drops"] == 1
    assert report["source_contract_filter_starved"] is True
    assert report["source_contract_filter"]["last_source_contract_filter_report"]["dropped_contracts"] == {
        "ESM6-ESU6": 1
    }


def test_replay_require_healthy_strategies_fails_when_data_quality_drops_replay_bar(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["dry_run_alerts"] = True
    cfg["engine"]["replay_seed_bars"] = 1
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    replay_path = tmp_path / "quality_degraded_replay.csv"
    engine.write_bars_file(
        replay_path,
        [
            sample_source_bar(signed_volume=10.0),
            sample_source_bar(
                timestamp_utc=ts("2026-06-11 13:31:00"),
                volume=10.0,
                signed_volume=12.0,
                buy_volume=11.0,
                sell_volume=0.0,
            ),
            sample_source_bar(
                timestamp_utc=ts("2026-06-11 13:32:00"),
                open=5000.25,
            ),
        ],
        timezone="America/New_York",
    )
    args = engine.argparse.Namespace(
        max_replay_bars=0,
        replay_stop_after_signal=False,
        replay_require_signal=False,
        replay_require_healthy_strategies=True,
    )

    report = engine.replay_bars(signal_engine, replay_path, args)

    captured = capsys.readouterr()
    assert "source_bar_quality_issues" in captured.out
    assert "signed_volume_exceeds_volume" in captured.out
    assert "replay_strategy_health_failed" in captured.out
    assert report["ok"] is False
    assert report["require_healthy_strategies"] is True
    assert report["replay_health_ok"] is False
    assert report["accepted_replay_source_bars"] == 0
    assert report["source_bar_quality_replay_drops"] == 1
    assert report["source_bar_quality_starved"] is True
    assert report["source_bar_quality_degraded"] is True
    assert report["last_source_bar_quality_report"]["bars_dropped"] == 1


def test_price_vs_quote_delta_keeps_diagnostics_separate() -> None:
    builder = engine.TradeBarBuilder(
        root_symbol="ES",
        timezone="America/New_York",
        large_trade_sizes=[],
        delta_method="price_vs_quote",
    )
    builder.update(
        engine.TradeTick(
            timestamp_utc=ts("2026-06-11 13:30:05"),
            price=5000.25,
            size=7,
            side="A",
            contract_symbol="ESM6",
            bid_price=5000.0,
            ask_price=5000.25,
        )
    )
    bars = builder.update(
        engine.TradeTick(
            timestamp_utc=ts("2026-06-11 13:31:00"),
            price=5000.5,
            size=1,
            side="B",
            contract_symbol="ESM6",
            bid_price=5000.25,
            ask_price=5000.5,
        )
    )

    assert len(bars) == 1
    bar = bars[0]
    assert bar.signed_volume == 7
    assert bar.buy_volume == 7
    assert bar.sell_volume == 0
    assert bar.large["quote_delta"] == 7
    assert bar.large["databento_aggressor_delta"] == -7


def test_price_vs_quote_missing_quotes_are_selected_unclassified_not_aggressor_fallback() -> None:
    builder = engine.TradeBarBuilder(
        root_symbol="ES",
        timezone="America/New_York",
        large_trade_sizes=[],
        delta_method="price_vs_quote",
    )
    builder.update(
        engine.TradeTick(
            timestamp_utc=ts("2026-06-11 13:30:05"),
            price=5000.25,
            size=7,
            side="B",
            contract_symbol="ESM6",
        )
    )
    bars = builder.update(
        engine.TradeTick(
            timestamp_utc=ts("2026-06-11 13:31:00"),
            price=5000.5,
            size=1,
            side="B",
            contract_symbol="ESM6",
            bid_price=5000.25,
            ask_price=5000.5,
        )
    )

    assert len(bars) == 1
    bar = bars[0]
    assert bar.signed_volume == 0
    assert bar.buy_volume == 0
    assert bar.sell_volume == 0
    assert bar.large["selected_delta_unclassified_volume"] == 7
    assert bar.large["quote_unclassified_volume"] == 7
    assert bar.large["databento_aggressor_delta"] == 7


def test_price_vs_quote_mid_spread_trades_are_selected_unclassified() -> None:
    builder = engine.TradeBarBuilder(
        root_symbol="ES",
        timezone="America/New_York",
        large_trade_sizes=[],
        delta_method="price_vs_quote",
    )
    builder.update(
        engine.TradeTick(
            timestamp_utc=ts("2026-06-11 13:30:05"),
            price=5000.25,
            size=7,
            side="B",
            contract_symbol="ESM6",
            bid_price=5000.0,
            ask_price=5000.5,
        )
    )
    bars = builder.update(
        engine.TradeTick(
            timestamp_utc=ts("2026-06-11 13:31:00"),
            price=5000.5,
            size=1,
            side="B",
            contract_symbol="ESM6",
            bid_price=5000.25,
            ask_price=5000.5,
        )
    )

    assert len(bars) == 1
    bar = bars[0]
    assert bar.signed_volume == 0
    assert bar.buy_volume == 0
    assert bar.sell_volume == 0
    assert bar.large["selected_delta_unclassified_volume"] == 7
    assert bar.large["quote_unclassified_volume"] == 7
    assert bar.large["databento_aggressor_delta"] == 7


def test_tick_rule_delta_uses_last_non_zero_price_change() -> None:
    builder = engine.TradeBarBuilder(
        root_symbol="ES",
        timezone="America/New_York",
        large_trade_sizes=[],
        delta_method="tick_rule",
    )
    builder.update(
        engine.TradeTick(ts("2026-06-11 13:30:01"), 5000.0, 2, "N", "ESM6")
    )
    builder.update(
        engine.TradeTick(ts("2026-06-11 13:30:02"), 5000.25, 3, "N", "ESM6")
    )
    builder.update(
        engine.TradeTick(ts("2026-06-11 13:30:03"), 5000.25, 5, "N", "ESM6")
    )
    bars = builder.update(
        engine.TradeTick(ts("2026-06-11 13:31:00"), 5000.0, 1, "N", "ESM6")
    )

    assert len(bars) == 1
    assert bars[0].signed_volume == 8
    assert bars[0].large["tick_rule_delta"] == 8
    assert bars[0].large["tick_rule_unclassified_volume"] == 2


def test_live_record_to_tick_requires_explicit_trade_action_for_mbp_records() -> None:
    record = FakeTradeRecord(
        timestamp=ts("2026-06-11 13:30:05"),
        price=5000.25,
        size=7,
        side="B",
        symbol="ESM6",
    )
    delattr(record, "action")

    assert engine.live_record_to_tick(
        record,
        default_contract_symbol="ES.FUT",
        require_trade_action=True,
    ) is None

    tick = engine.live_record_to_tick(
        record,
        default_contract_symbol="ES.FUT",
        require_trade_action=False,
    )

    assert tick is not None
    assert tick.contract_symbol == "ESM6"


def test_live_record_to_tick_extracts_top_of_book_from_mbp_levels() -> None:
    class FakeMbpLevel:
        def __init__(self, bid_px: float, ask_px: float) -> None:
            self.bid_px = int(bid_px * 1_000_000_000)
            self.ask_px = int(ask_px * 1_000_000_000)

    record = FakeTradeRecord(
        timestamp=ts("2026-06-11 13:30:05"),
        price=5000.25,
        size=7,
        side="B",
        symbol="ESM6",
        action="T",
    )
    record.levels = [FakeMbpLevel(5000.0, 5000.25)]

    tick = engine.live_record_to_tick(
        record,
        default_contract_symbol="ES.FUT",
        require_trade_action=True,
    )

    assert tick is not None
    assert tick.bid_price == 5000.0
    assert tick.ask_price == 5000.25


def test_trade_bar_builder_heartbeat_flushes_after_delay() -> None:
    builder = engine.TradeBarBuilder(
        root_symbol="ES",
        timezone="America/New_York",
        large_trade_sizes=[],
    )
    builder.update(engine.TradeTick(ts("2026-06-11 13:30:05"), 5000.0, 2, "B", "ESM6"))

    too_early = builder.flush_completed_bars(
        now_utc=ts("2026-06-11 13:31:01.999"),
        flush_delay_seconds=2,
    )
    flushed = builder.flush_completed_bars(
        now_utc=ts("2026-06-11 13:31:02"),
        flush_delay_seconds=2,
    )
    duplicate = builder.flush_completed_bars(
        now_utc=ts("2026-06-11 13:31:10"),
        flush_delay_seconds=2,
    )

    assert too_early == []
    assert duplicate == []
    assert len(flushed) == 1
    assert flushed[0].timestamp_utc == ts("2026-06-11 13:30:00")
    assert flushed[0].source == "live_heartbeat"
    assert flushed[0].volume == 2
    assert flushed[0].signed_volume == 2


def test_trade_bar_builder_ignores_late_tick_after_heartbeat_flush() -> None:
    builder = engine.TradeBarBuilder(
        root_symbol="ES",
        timezone="America/New_York",
        large_trade_sizes=[],
    )
    builder.update(engine.TradeTick(ts("2026-06-11 13:30:05"), 5000.0, 2, "B", "ESM6"))
    flushed = builder.flush_completed_bars(
        now_utc=ts("2026-06-11 13:31:02"),
        flush_delay_seconds=2,
    )
    late = builder.update(engine.TradeTick(ts("2026-06-11 13:30:45"), 4999.75, 99, "A", "ESM6"))
    builder.update(engine.TradeTick(ts("2026-06-11 13:31:05"), 5000.25, 3, "B", "ESM6"))
    next_minute = builder.update(engine.TradeTick(ts("2026-06-11 13:32:00"), 5000.5, 1, "B", "ESM6"))

    assert len(flushed) == 1
    assert late == []
    assert builder.late_ticks_ignored == 1
    assert builder.last_late_tick == {
        "timestamp_utc": "2026-06-11T13:30:45+00:00",
        "minute_utc": "2026-06-11T13:30:00+00:00",
        "contract_symbol": "ESM6",
        "price": 4999.75,
        "size": 99.0,
        "reason": "minute_already_flushed",
    }
    assert len(next_minute) == 1
    assert next_minute[0].timestamp_utc == ts("2026-06-11 13:31:00")
    assert next_minute[0].volume == 3


def test_trade_bar_builder_filters_unmatched_contract_symbols() -> None:
    builder = engine.TradeBarBuilder(
        root_symbol="ES",
        timezone="America/New_York",
        large_trade_sizes=[],
        contract_symbol_regex=r"^ES[HMUZ]\d$",
    )

    rejected = builder.update(
        engine.TradeTick(ts("2026-06-11 13:30:05"), 5000.0, 2, "B", "ESM6-ESU6")
    )
    builder.update(engine.TradeTick(ts("2026-06-11 13:30:10"), 5000.25, 3, "B", "ESM6"))
    completed = builder.update(engine.TradeTick(ts("2026-06-11 13:31:00"), 5000.5, 1, "B", "ESM6"))

    assert rejected == []
    assert len(completed) == 1
    assert completed[0].contract_symbol == "ESM6"
    assert completed[0].volume == 3
    assert builder.accepted_contract_ticks == {"ESM6": 2}
    assert builder.unmatched_contract_ticks_ignored == 1
    assert builder.unmatched_contract_ticks == {"ESM6-ESU6": 1}
    assert builder.last_unmatched_contract_tick == {
        "timestamp_utc": "2026-06-11T13:30:05+00:00",
        "contract_symbol": "ESM6-ESU6",
        "price": 5000.0,
        "size": 2.0,
        "contract_symbol_regex": r"^ES[HMUZ]\d$",
        "reason": "contract_symbol did not match configured databento.contract_symbol_regex",
    }


def test_active_contract_filter_keeps_highest_minute_volume_per_timestamp() -> None:
    frame = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
                "timestamp_utc": ts("2026-06-11 13:30:00"),
                "contract_symbol": "ESM6",
                "volume": 100,
                "signed_volume": 10,
            },
            {
                "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
                "timestamp_utc": ts("2026-06-11 13:30:00"),
                "contract_symbol": "ESU6",
                "volume": 10,
                "signed_volume": -2,
            },
            {
                "timestamp": pd.Timestamp("2026-06-11 09:31:00", tz="America/New_York"),
                "timestamp_utc": ts("2026-06-11 13:31:00"),
                "contract_symbol": "ESM6",
                "volume": 25,
                "signed_volume": 4,
            },
            {
                "timestamp": pd.Timestamp("2026-06-11 09:31:00", tz="America/New_York"),
                "timestamp_utc": ts("2026-06-11 13:31:00"),
                "contract_symbol": "ESU6",
                "volume": 300,
                "signed_volume": -50,
            },
        ]
    )

    filtered, report = engine.active_contract_source_filter_report(
        frame,
        mode="highest_minute_volume",
        timezone="America/New_York",
    )

    assert list(filtered["contract_symbol"]) == ["ESM6", "ESU6"]
    assert list(filtered["volume"]) == [100, 300]
    assert report["dropped_rows"] == 2
    assert report["selected_contracts"] == {"ESM6": 1, "ESU6": 1}
    assert report["dropped_contracts"] == {"ESU6": 1, "ESM6": 1}


def test_active_contract_filter_keeps_highest_cumulative_session_volume_without_lookahead() -> None:
    frame = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
                "timestamp_utc": ts("2026-06-11 13:30:00"),
                "contract_symbol": "ESM6",
                "volume": 10,
            },
            {
                "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
                "timestamp_utc": ts("2026-06-11 13:30:00"),
                "contract_symbol": "ESU6",
                "volume": 9,
            },
            {
                "timestamp": pd.Timestamp("2026-06-11 09:31:00", tz="America/New_York"),
                "timestamp_utc": ts("2026-06-11 13:31:00"),
                "contract_symbol": "ESM6",
                "volume": 1,
            },
            {
                "timestamp": pd.Timestamp("2026-06-11 09:31:00", tz="America/New_York"),
                "timestamp_utc": ts("2026-06-11 13:31:00"),
                "contract_symbol": "ESU6",
                "volume": 50,
            },
        ]
    )

    filtered, report = engine.active_contract_source_filter_report(
        frame,
        mode="highest_session_volume",
        timezone="America/New_York",
    )

    assert list(filtered["contract_symbol"]) == ["ESM6", "ESU6"]
    assert list(filtered["volume"]) == [10, 50]
    assert report["dropped_rows"] == 2


def test_strategy_active_contract_filter_reports_dropped_contracts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["active_contract_mode"] = "highest_minute_volume"
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]
    frame = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
                "timestamp_utc": ts("2026-06-11 13:30:00"),
                "contract_symbol": "ESM6",
                "volume": 10,
                "signed_volume": 2,
            },
            {
                "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
                "timestamp_utc": ts("2026-06-11 13:30:00"),
                "contract_symbol": "ESU6",
                "volume": 100,
                "signed_volume": -25,
            },
        ]
    )

    filtered = strategy.filter_active_contract_source(frame)

    captured = capsys.readouterr()
    assert list(filtered["contract_symbol"]) == ["ESU6"]
    assert "SYSTEM_ALERT" in captured.out
    assert "non_active_contract_bars_filtered" in captured.out
    assert strategy.non_active_contract_filter_drops == 1
    health = signal_engine.strategy_health_report()[0]
    assert health["active_contract_mode"] == "highest_minute_volume"
    assert health["non_active_contract_filter_drops"] == 1
    assert health["last_contract_filter_report"]["dropped_rows"] == 1


class FakeMetadata:
    def __init__(self, cost: float, billable_size: int = 1234) -> None:
        self.cost = cost
        self.billable_size = billable_size

    def get_dataset_range(self, dataset: str) -> dict[str, str]:
        assert dataset == "GLBX.MDP3"
        return {"start": "2020-01-01T00:00:00Z", "end": "2026-06-10T16:50:00Z"}

    def list_schemas(self, dataset: str) -> list[str]:
        assert dataset == "GLBX.MDP3"
        return ["trades", "mbp-1"]

    def list_fields(self, schema: str, encoding: str) -> list[dict[str, str]]:
        assert schema in {"trades", "mbp-1"}
        assert encoding == "dbn"
        fields = [{"name": "ts_event"}, {"name": "price"}, {"name": "size"}, {"name": "side"}, {"name": "instrument_id"}]
        if schema == "mbp-1":
            fields.extend([{"name": "action"}, {"name": "bid_px_00"}, {"name": "ask_px_00"}])
        return fields

    def get_cost(self, **_: object) -> float:
        return self.cost

    def get_billable_size(self, **_: object) -> int:
        return self.billable_size


class FakeSymbology:
    def __init__(self, response: dict | None = None) -> None:
        self.response = response or {
            "result": {"ESM6": [{"d0": "2026-06-11", "d1": "2026-06-12", "s": "42140864"}]},
            "symbols": ["ES.FUT"],
            "stype_in": "parent",
            "stype_out": "instrument_id",
            "partial": [],
            "not_found": [],
            "message": "OK",
            "status": 0,
        }
        self.requests: list[dict[str, object]] = []

    def resolve(self, **kwargs: object) -> dict:
        self.requests.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, cost: float, symbology_response: dict | None = None) -> None:
        self.metadata = FakeMetadata(cost)
        self.symbology = FakeSymbology(symbology_response)


class CountingFakeMetadata(FakeMetadata):
    def __init__(self, cost: float, billable_size: int = 1234) -> None:
        super().__init__(cost, billable_size=billable_size)
        self.cost_calls = 0
        self.billable_size_calls = 0

    def get_cost(self, **kwargs: object) -> float:
        self.cost_calls += 1
        return super().get_cost(**kwargs)

    def get_billable_size(self, **kwargs: object) -> int:
        self.billable_size_calls += 1
        return super().get_billable_size(**kwargs)


class CountingFakeClient(FakeClient):
    def __init__(self, cost: float, symbology_response: dict | None = None) -> None:
        self.metadata = CountingFakeMetadata(cost)
        self.symbology = FakeSymbology(symbology_response)


class MissingSideMetadata(FakeMetadata):
    def list_fields(self, schema: str, encoding: str) -> list[dict[str, str]]:
        assert schema == "trades"
        assert encoding == "dbn"
        return [{"name": "ts_event"}, {"name": "price"}, {"name": "size"}, {"name": "instrument_id"}]


class MissingSideClient(FakeClient):
    def __init__(self) -> None:
        self.metadata = MissingSideMetadata(cost=0.0)
        self.symbology = FakeSymbology()


class EmptyFieldsMetadata(FakeMetadata):
    def list_fields(self, schema: str, encoding: str) -> list[dict[str, str]]:
        assert schema == "trades"
        assert encoding == "dbn"
        return []


class EmptyFieldsClient(FakeClient):
    def __init__(self) -> None:
        self.metadata = EmptyFieldsMetadata(cost=0.0)
        self.symbology = FakeSymbology()


class FieldListingErrorMetadata(FakeMetadata):
    def list_fields(self, schema: str, encoding: str) -> list[dict[str, str]]:
        assert schema == "trades"
        assert encoding == "dbn"
        raise RuntimeError("metadata fields unavailable")


class FieldListingErrorClient(FakeClient):
    def __init__(self) -> None:
        self.metadata = FieldListingErrorMetadata(cost=0.0)
        self.symbology = FakeSymbology()


class MissingActionMetadata(FakeMetadata):
    def list_fields(self, schema: str, encoding: str) -> list[dict[str, str]]:
        assert schema == "mbp-1"
        assert encoding == "dbn"
        return [
            {"name": "ts_event"},
            {"name": "price"},
            {"name": "size"},
            {"name": "side"},
            {"name": "instrument_id"},
            {"name": "bid_px_00"},
            {"name": "ask_px_00"},
        ]


class MissingActionClient(FakeClient):
    def __init__(self) -> None:
        self.metadata = MissingActionMetadata(cost=0.0)
        self.symbology = FakeSymbology()


class FakeTradeRecord:
    def __init__(
        self,
        *,
        timestamp: pd.Timestamp,
        price: float,
        size: int,
        side: str,
        symbol: str | None = None,
        instrument_id: int | None = None,
        action: str = "T",
    ) -> None:
        self.ts_event = timestamp
        self._price = price
        self.price = int(price * 1_000_000_000)
        self.size = size
        self.side = side
        self.action = action
        if symbol is not None:
            self.symbol = symbol
        if instrument_id is not None:
            self.instrument_id = instrument_id

    def pretty_price(self) -> float:
        return self._price


class FakeLiveClient:
    def __init__(
        self,
        *,
        connected_after_start: bool,
        records: list[object] | None = None,
        record_delay_seconds: float = 0.0,
        **kwargs: object,
    ) -> None:
        self.connected_after_start = connected_after_start
        self.records = records or []
        self.record_delay_seconds = record_delay_seconds
        self.kwargs = kwargs
        self.callbacks: list[object] = []
        self.exception_callbacks: list[object] = []
        self.subscribe_args: dict[str, object] | None = None
        self.started = False
        self.stopped = False
        self.wait_for_close_timeout: float | None = None

    def add_callback(self, record_callback: object, exception_callback: object | None = None) -> None:
        self.callbacks.append(record_callback)
        self.exception_callbacks.append(exception_callback)

    def subscribe(self, **kwargs: object) -> int:
        self.subscribe_args = kwargs
        return 1

    def start(self) -> None:
        self.started = True
        if self.records:
            thread = threading.Thread(target=self._emit_records, daemon=True)
            thread.start()

    def _emit_records(self) -> None:
        if self.record_delay_seconds:
            time.sleep(self.record_delay_seconds)
        for record in self.records:
            if self.stopped:
                break
            for callback in list(self.callbacks):
                callback(record)

    def stop(self) -> None:
        self.stopped = True

    def wait_for_close(self, timeout: float | None = None) -> None:
        self.wait_for_close_timeout = timeout

    def is_connected(self) -> bool:
        return bool(self.started and self.connected_after_start and not self.stopped)


def test_cost_guard_blocks_paid_historical_fetch() -> None:
    with pytest.raises(RuntimeError, match="Refusing Databento historical fetch"):
        engine.enforce_historical_cost_guard(
            FakeClient(cost=0.01),
            {"cost_guard": {"enabled": True, "allow_paid_downloads": False, "max_cost_usd": 0.0}},
            dataset="GLBX.MDP3",
            symbols="ES.FUT",
            schema="trades",
            stype_in="parent",
            start=ts("2026-06-10 13:30:00"),
            end=ts("2026-06-10 13:31:00"),
        )


def test_cost_guard_blocks_positive_cost_even_when_paid_downloads_are_enabled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(RuntimeError, match="Refusing Databento historical fetch"):
        engine.enforce_historical_cost_guard(
            FakeClient(cost=0.01),
            {
                "cost_guard": {
                    "enabled": True,
                    "allow_paid_downloads": True,
                    "require_zero_cost": True,
                    "max_cost_usd": 1.0,
                }
            },
            dataset="GLBX.MDP3",
            symbols="ES.FUT",
            schema="trades",
            stype_in="parent",
            start=ts("2026-06-10 13:30:00"),
            end=ts("2026-06-10 13:31:00"),
        )

    captured = capsys.readouterr()
    assert "historical_fetch_blocked_by_cost_guard" in captured.out
    assert "require_zero_cost" in captured.out


def test_cost_guard_disabled_blocks_historical_fetch(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(RuntimeError, match="cost guard is disabled"):
        engine.enforce_historical_cost_guard(
            FakeClient(cost=0.0),
            {"cost_guard": {"enabled": False}},
            dataset="GLBX.MDP3",
            symbols="ES.FUT",
            schema="trades",
            stype_in="parent",
            start=ts("2026-06-10 13:30:00"),
            end=ts("2026-06-10 13:31:00"),
        )

    captured = capsys.readouterr()
    assert "historical_fetch_blocked_by_disabled_cost_guard" in captured.out


def test_cost_guard_unavailable_estimate_fails_when_zero_cost_is_required(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class CostUnavailableMetadata(FakeMetadata):
        def get_cost(self, **_: object) -> float:
            raise RuntimeError("cost endpoint unavailable")

    class Client(FakeClient):
        def __init__(self) -> None:
            self.metadata = CostUnavailableMetadata(cost=0.0)
            self.symbology = FakeSymbology()

    with pytest.raises(RuntimeError, match="zero cost cannot be proven"):
        engine.enforce_historical_cost_guard(
            Client(),
            {
                "cost_guard": {
                    "enabled": True,
                    "allow_paid_downloads": False,
                    "require_zero_cost": True,
                    "max_cost_usd": 0.0,
                    "fail_if_estimate_unavailable": False,
                }
            },
            dataset="GLBX.MDP3",
            symbols="ES.FUT",
            schema="trades",
            stype_in="parent",
            start=ts("2026-06-10 13:30:00"),
            end=ts("2026-06-10 13:31:00"),
        )

    captured = capsys.readouterr()
    assert "historical_cost_estimate_unavailable" in captured.out
    assert '"timeseries_get_range_attempted": false' in captured.out


def test_cost_guard_allows_zero_cost_historical_fetch() -> None:
    report = engine.enforce_historical_cost_guard(
        FakeClient(cost=0.0),
        {"cost_guard": {"enabled": True, "allow_paid_downloads": False, "max_cost_usd": 0.0}},
        dataset="GLBX.MDP3",
        symbols="ES.FUT",
        schema="trades",
        stype_in="parent",
        start=ts("2026-06-10 13:30:00"),
        end=ts("2026-06-10 13:31:00"),
    )

    assert report["allowed"] is True
    assert report["estimated_cost_usd"] == 0.0
    assert report["billable_size_bytes"] == 1234
    assert report["metadata_only"] is True
    assert report["databento_api_calls_attempted"] == [
        "metadata.get_cost",
        "metadata.get_billable_size",
    ]
    assert report["timeseries_get_range_attempted"] is False
    assert report["guarded_operation"] == "timeseries.get_range"


def test_historical_get_range_requires_cost_guard_before_timeseries_call(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class Timeseries:
        calls = 0

        def get_range(self, **_: object) -> object:
            self.calls += 1
            raise AssertionError("timeseries.get_range should not be called without a guard")

    class Client:
        def __init__(self) -> None:
            self.timeseries = Timeseries()

    client = Client()

    with pytest.raises(RuntimeError, match="cost-guard approval"):
        engine.historical_get_range(
            client,
            dataset="GLBX.MDP3",
            symbols="ES.FUT",
            schema="trades",
            stype_in="parent",
            stype_out="instrument_id",
            start=ts("2026-06-10 13:30:00"),
            end=ts("2026-06-10 13:31:00"),
        )

    captured = capsys.readouterr()
    assert "historical_timeseries_get_range_blocked_by_guard" in captured.out
    assert '"timeseries_get_range_attempted": false' in captured.out
    assert client.timeseries.calls == 0


def test_historical_get_range_accepts_valid_zero_cost_guard() -> None:
    class Store:
        pass

    class Timeseries:
        def __init__(self) -> None:
            self.calls = 0

        def get_range(self, **_: object) -> object:
            self.calls += 1
            return Store()

    class Client:
        def __init__(self) -> None:
            self.timeseries = Timeseries()

    client = Client()
    guard = {
        "enabled": True,
        "allowed": True,
        "estimated_cost_usd": 0.0,
        "allow_paid_downloads": False,
        "require_zero_cost": True,
        "max_cost_usd": 0.0,
        "timeseries_get_range_attempted": False,
        "guarded_operation": "timeseries.get_range",
    }

    store, stype_out = engine.historical_get_range(
        client,
        dataset="GLBX.MDP3",
        symbols="ES.FUT",
        schema="trades",
        stype_in="parent",
        stype_out="instrument_id",
        start=ts("2026-06-10 13:30:00"),
        end=ts("2026-06-10 13:31:00"),
        cost_guard_report=guard,
    )

    assert isinstance(store, Store)
    assert stype_out == "instrument_id"
    assert client.timeseries.calls == 1


def test_live_cost_guard_blocks_unacknowledged_subscription(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(RuntimeError, match="live cost guard"):
        engine.enforce_live_subscription_cost_guard(
            {"cost_guard": {"enabled": True}},
            dataset="GLBX.MDP3",
            symbols="ES.FUT",
            schema="trades",
            stype_in="parent",
        )

    captured = capsys.readouterr()
    assert "live_subscription_blocked_by_cost_guard" in captured.out
    assert '"live_subscription_attempted": false' in captured.out


def test_live_cost_guard_disabled_blocks_subscription(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(RuntimeError, match="live cost guard"):
        engine.enforce_live_subscription_cost_guard(
            {"cost_guard": {"enabled": False}},
            dataset="GLBX.MDP3",
            symbols="ES.FUT",
            schema="trades",
            stype_in="parent",
        )

    captured = capsys.readouterr()
    assert "live_subscription_blocked_by_cost_guard" in captured.out
    assert "live cost guard is disabled" in captured.out
    assert '"live_subscription_attempted": false' in captured.out


def test_live_cost_guard_allows_explicitly_acknowledged_subscription() -> None:
    report = engine.enforce_live_subscription_cost_guard(
        {
            "cost_guard": {
                "enabled": True,
                "allow_live_subscription": True,
                "acknowledge_live_data_may_be_billable": True,
            }
        },
        dataset="GLBX.MDP3",
        symbols="ES.FUT",
        schema="trades",
        stype_in="parent",
    )

    assert report["enabled"] is True
    assert report["allowed"] is True
    assert report["allow_live_subscription"] is True
    assert report["acknowledge_live_data_may_be_billable"] is True


def test_prelock_live_cost_guard_blocks_before_process_lock(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    lock_path = tmp_path / "signal_engine.lock"
    cfg["engine"]["process_lock"]["path"] = str(lock_path)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    args = engine.argparse.Namespace(live=True, seed_only=False, replay_bars=None)

    with pytest.raises(RuntimeError, match="live cost guard"):
        engine.enforce_live_subscription_cost_guard_before_process_lock(signal_engine, args)

    captured = capsys.readouterr()
    assert "live_subscription_blocked_by_cost_guard" in captured.out
    assert "process_lock" not in captured.out
    assert not lock_path.exists()
    assert signal_engine.process_lock_acquired is False


def test_prelock_live_cost_guard_is_silent_when_live_acknowledged(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    allow_test_live_subscription(cfg)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    args = engine.argparse.Namespace(live=True, seed_only=False, replay_bars=None)

    report = engine.enforce_live_subscription_cost_guard_before_process_lock(signal_engine, args)

    captured = capsys.readouterr()
    assert report is None
    assert "live_cost_guard" not in captured.out
    assert signal_engine.process_lock_acquired is False


def test_prelock_live_cost_guard_skips_seed_replay_and_non_live_modes() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    seed_args = engine.argparse.Namespace(live=True, seed_only=True, replay_bars=None)
    replay_args = engine.argparse.Namespace(live=True, seed_only=False, replay_bars="seed.csv")
    non_live_args = engine.argparse.Namespace(live=False, seed_only=False, replay_bars=None)

    assert engine.should_check_live_cost_guard_before_process_lock(signal_engine, seed_args) is False
    assert engine.should_check_live_cost_guard_before_process_lock(signal_engine, replay_args) is False
    assert engine.should_check_live_cost_guard_before_process_lock(signal_engine, non_live_args) is False


def test_prelock_live_metadata_preflight_guard_blocks_before_process_lock(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    lock_path = tmp_path / "signal_engine.lock"
    cfg["engine"]["process_lock"]["path"] = str(lock_path)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"].setdefault("cost_guard", {}).update(
        {
            "enabled": True,
            "allow_live_subscription": True,
            "acknowledge_live_data_may_be_billable": True,
        }
    )
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    args = engine.argparse.Namespace(live=True, seed_only=False, replay_bars=None)

    with pytest.raises(RuntimeError, match="metadata preflight"):
        engine.enforce_live_metadata_preflight_before_process_lock(signal_engine, args)

    captured = capsys.readouterr()
    assert "live_metadata_preflight_disabled" in captured.out
    assert '"live_subscription_attempted": false' in captured.out
    assert "process_lock" not in captured.out
    assert not lock_path.exists()
    assert signal_engine.process_lock_acquired is False


def test_live_metadata_preflight_guard_reports_explicit_diagnostic_bypass(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["allow_live_without_metadata_preflight"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.enforce_live_metadata_preflight_guard(signal_engine)

    captured = capsys.readouterr()
    assert report["ok"] is True
    assert report["metadata_preflight"] is False
    assert report["allow_live_without_metadata_preflight"] is True
    assert "live_metadata_preflight_bypass_acknowledged" in captured.out
    assert '"live_subscription_attempted": false' in captured.out


def test_live_output_sink_safety_blocks_before_client_factory(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["engine"]["alert_file"]["fail_on_write_error"] = False
    cfg["databento"]["live"]["metadata_preflight"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    factory_called = False

    def factory(**kwargs: object) -> FakeLiveClient:
        nonlocal factory_called
        factory_called = True
        return FakeLiveClient(connected_after_start=True, **kwargs)

    with pytest.raises(RuntimeError, match="output sink safety"):
        engine.run_live(signal_engine, once=False, max_runtime=1, live_client_factory=factory)

    captured = capsys.readouterr()
    assert "live_output_sink_safety_failed" in captured.out
    assert "entry_alerts.fail_on_write_error" in captured.out
    assert '"live_subscription_attempted": false' in captured.out
    assert "live_subscribe" not in captured.out
    assert factory_called is False


def test_historical_contract_regex_keeps_matching_symbols() -> None:
    trades = pd.DataFrame({"symbol": ["ESM6", "ESM6-ESU6"]})

    selected = engine.effective_contract_symbol_regex(trades, r"^ES[HMUZ]\d$")

    assert selected == r"^ES[HMUZ]\d$"


def test_historical_contract_regex_mismatch_fails_closed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    trades = pd.DataFrame({"symbol": ["123456", "789012"]})

    with pytest.raises(RuntimeError, match="contract_symbol_regex"):
        engine.effective_contract_symbol_regex(
            trades,
            r"^ES[HMUZ]\d$",
            context={"dataset": "GLBX.MDP3", "stype_out": "instrument_id"},
        )

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "historical_symbol_regex_unmatched" in captured.out
    assert "allow_contract_symbol_regex_relaxation" in captured.out


def test_historical_contract_regex_mismatch_can_be_explicitly_relaxed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    trades = pd.DataFrame({"symbol": ["123456", "789012"]})

    selected = engine.effective_contract_symbol_regex(
        trades,
        r"^ES[HMUZ]\d$",
        allow_relaxation=True,
        context={"dataset": "GLBX.MDP3", "stype_out": "instrument_id"},
    )

    captured = capsys.readouterr()
    assert selected == r".+"
    assert "SYSTEM_ALERT" in captured.out
    assert "historical_symbol_regex_relaxed" in captured.out
    assert "allowed_by_config" in captured.out


def test_store_symbol_mapping_inverts_raw_symbol_keyed_instrument_mapping() -> None:
    raw_mapping = {
        "ESM6": [{"d0": "2026-06-11", "d1": "2026-06-12", "s": "123456"}],
        "ESM6-ESU6": [{"d0": "2026-06-11", "d1": "2026-06-12", "s": "789012"}],
    }
    mapping: dict[str, str] = {}

    engine.collect_symbol_mapping(raw_mapping, mapping)

    assert mapping["123456"] == "ESM6"
    assert mapping["789012"] == "ESM6-ESU6"


def test_ensure_trade_symbol_column_maps_instrument_ids_to_raw_symbols() -> None:
    class Store:
        symbology = {
            "ESM6": [{"d0": "2026-06-11", "d1": "2026-06-12", "s": "123456"}],
        }

    frame = pd.DataFrame({"instrument_id": [123456], "price": [5000.25]})

    out = engine.ensure_trade_symbol_column(frame, Store())

    assert out["symbol"].tolist() == ["ESM6"]


def test_historical_cache_metadata_validates_matching_cache(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cache_path = tmp_path / "seed.csv"
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": False},
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    engine.write_historical_cache(signal_engine, cache_path, [sample_source_bar()], source="test")

    bars = engine.load_historical_seed_bars(signal_engine)

    captured = capsys.readouterr()
    assert len(bars) == 1
    assert "historical_cache_metadata_written" in captured.out
    assert "historical_cache_metadata_valid" in captured.out
    metadata_path = engine.historical_cache_metadata_path(cache_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["config"]["delta_method"] == "aggressor_side"
    assert metadata["bars"]["bar_count"] == 1
    assert len(metadata["bars"]["content_sha256"]) == 64


def test_historical_cache_missing_metadata_warns_without_fail_fast(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cache_path = tmp_path / "seed.csv"
    engine.write_bars_file(cache_path, [sample_source_bar()], timezone="America/New_York")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": False},
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    bars = engine.load_historical_seed_bars(signal_engine)

    captured = capsys.readouterr()
    assert len(bars) == 1
    assert "SYSTEM_ALERT" in captured.out
    assert "historical_cache_metadata_missing" in captured.out


def test_historical_seed_file_metadata_validates_matching_sidecar(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    seed_path = tmp_path / "seed_file.csv"
    cfg["databento"]["historical"] = {
        "enabled": True,
        "seed_bars_path": str(seed_path),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": True},
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    engine.write_historical_cache(signal_engine, seed_path, [sample_source_bar()], source="prebuilt_seed")
    capsys.readouterr()

    bars = engine.load_historical_seed_bars(signal_engine)

    captured = capsys.readouterr()
    assert len(bars) == 1
    assert "historical_seed_file_metadata_valid" in captured.out
    assert "historical_seed_file_loaded" in captured.out


def test_historical_seed_file_missing_metadata_can_fail_fast(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    seed_path = tmp_path / "seed_file.csv"
    engine.write_bars_file(seed_path, [sample_source_bar()], timezone="America/New_York")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "seed_bars_path": str(seed_path),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": True},
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Historical seed file metadata is missing"):
        engine.load_historical_seed_bars(signal_engine)

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "historical_seed_file_metadata_missing" in captured.out


def test_historical_cache_metadata_mismatch_can_fail_fast(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cache_path = tmp_path / "seed.csv"
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": True},
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    engine.write_historical_cache(signal_engine, cache_path, [sample_source_bar()], source="test")
    metadata_path = engine.historical_cache_metadata_path(cache_path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["config"]["schema"] = "mbp-1"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(RuntimeError, match="Historical cache metadata mismatch"):
        engine.load_historical_seed_bars(signal_engine)


def test_historical_cache_metadata_detects_same_shape_content_drift(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cache_path = tmp_path / "seed.csv"
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": True},
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    engine.write_historical_cache(signal_engine, cache_path, [sample_source_bar(close=5000.25)], source="test")
    engine.write_bars_file(cache_path, [sample_source_bar(close=5000.5)], timezone="America/New_York")

    with pytest.raises(RuntimeError, match="Historical cache metadata mismatch"):
        engine.load_historical_seed_bars(signal_engine)


def test_historical_cache_staleness_issue_reports_old_cache() -> None:
    issue = engine.historical_cache_staleness_issue(
        [sample_source_bar(timestamp_utc=ts("2026-06-01 13:30:00"))],
        max_staleness_days=7,
        now_utc=ts("2026-06-12 13:30:00"),
    )

    assert issue is not None
    assert issue["last_timestamp_utc"] == "2026-06-01T13:30:00+00:00"
    assert issue["age_days"] == 11.0
    assert issue["max_staleness_days"] == 7.0


def test_historical_cache_metadata_stale_cache_can_fail_fast(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cache_path = tmp_path / "seed.csv"
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "cache_metadata": {
            "enabled": True,
            "fail_on_mismatch": True,
            "max_staleness_days": 1,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    engine.write_historical_cache(
        signal_engine,
        cache_path,
        [sample_source_bar(timestamp_utc=ts("2020-01-02 13:30:00"))],
        source="test",
    )

    with pytest.raises(RuntimeError, match="Historical cache is stale"):
        engine.load_historical_seed_bars(signal_engine)


def test_matching_cache_can_warm_quote_delta_config(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cache_path = tmp_path / "quote_seed.csv"
    cfg["databento"]["schema"] = "mbp-1"
    cfg["databento"]["delta_method"] = "price_vs_quote"
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": True},
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    engine.write_historical_cache(signal_engine, cache_path, [sample_source_bar()], source="test")

    bars = engine.load_historical_seed_bars(signal_engine)

    assert len(bars) == 1


def test_refresh_historical_bypasses_configured_seed_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed_path = tmp_path / "seed.csv"
    engine.write_bars_file(seed_path, [sample_source_bar(close=5000.25)], timezone="America/New_York")
    fetched_bar = sample_source_bar(close=6000.25, source="databento_historical")
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "seed_bars_path": str(seed_path),
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    fetch_calls: list[dict[str, object]] = []

    def fake_fetch(fetch_engine: engine.SignalEngine, hist_cfg: dict[str, object]) -> list[engine.SourceMinuteBar]:
        fetch_calls.append({"engine": fetch_engine, "hist_cfg": hist_cfg})
        return [fetched_bar]

    monkeypatch.setattr(engine, "fetch_databento_historical_bars", fake_fetch)

    bars = engine.load_historical_seed_bars(signal_engine, refresh=True)

    captured = capsys.readouterr()
    assert bars == [fetched_bar]
    assert len(fetch_calls) == 1
    assert "historical_seed_file_bypassed_for_refresh" in captured.out
    assert "historical_seed_file_loaded" not in captured.out


def test_historical_refresh_makes_seed_file_unsupported_contract_require_download_before_cost(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    seed_path = tmp_path / "seed.csv"
    engine.write_bars_file(seed_path, [sample_source_bar()], timezone="America/New_York")
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["schema"] = "mbp-1"
    cfg["databento"]["delta_method"] = "price_vs_quote"
    cfg["databento"]["historical"] = {
        "enabled": True,
        "seed_bars_path": str(seed_path),
        "refresh": True,
        "cost_guard": {
            "enabled": True,
            "allow_paid_downloads": False,
            "max_cost_usd": 0.0,
            "fail_if_estimate_unavailable": True,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    client = CountingFakeClient(cost=0.0)

    with pytest.raises(RuntimeError, match="Historical Databento download is required but unsupported"):
        engine.check_databento_metadata(signal_engine, client=client)

    captured = capsys.readouterr()
    assert "historical_fetch_contract_unsupported" in captured.out
    assert client.metadata.cost_calls == 0
    assert client.metadata.billable_size_calls == 0
    contract = engine.databento_historical_fetch_contract_report(signal_engine)
    assert contract["fetch_required"] is True
    assert contract["source"] == "databento_historical"
    assert contract["historical_source"]["seed_file_configured"] is True
    assert contract["historical_source"]["seed_file_usable"] is False


def test_seed_only_completion_report_succeeds_after_accepted_seed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["historical"] = {"enabled": True}
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    signal_engine.seed([sample_source_bar()], source="historical")
    capsys.readouterr()

    report = engine.seed_only_completion_report(
        signal_engine,
        historical_skipped=False,
        raw_seed_bars=1,
        accepted_seed_bars=1,
    )

    captured = capsys.readouterr()
    assert "seed_only_complete" in captured.out
    assert "SYSTEM_ALERT" not in captured.out
    assert report["ok"] is True
    assert report["raw_seed_bars"] == 1
    assert report["accepted_seed_bars"] == 1


def test_seed_only_completion_report_fails_when_historical_is_skipped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.seed_only_completion_report(
        signal_engine,
        historical_skipped=True,
        raw_seed_bars=0,
        accepted_seed_bars=0,
    )

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "seed_only_failed" in captured.out
    assert "--skip-historical was set" in captured.out
    assert report["ok"] is False
    assert report["historical_skipped"] is True


def test_seed_only_completion_report_fails_when_loaded_bars_are_filtered(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    signal_engine.seed([sample_source_bar(contract_symbol="ESM6-ESU6")], source="historical")
    capsys.readouterr()

    report = engine.seed_only_completion_report(
        signal_engine,
        historical_skipped=False,
        raw_seed_bars=1,
        accepted_seed_bars=0,
    )

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "seed_only_failed" in captured.out
    assert "no historical seed bars survived source quality and contract filters" in captured.out
    assert report["ok"] is False
    assert report["raw_seed_bars"] == 1
    assert report["accepted_seed_bars"] == 0
    assert report["source_contract_filter"]["source_contract_filter_drops"] == 1


def test_readiness_fails_when_cache_missing_required_orderflow_columns(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cache_path = tmp_path / "missing_orderflow_seed.csv"
    pd.DataFrame(
        [
            {
                "timestamp": "2026-06-11 09:30:00-04:00",
                "timestamp_utc": "2026-06-11 13:30:00+00:00",
                "symbol": "ES",
                "contract_symbol": "ESM6",
                "open": 5000.0,
                "high": 5001.0,
                "low": 4999.5,
                "close": 5000.25,
                "volume": 100.0,
            }
        ]
    ).to_csv(cache_path, index=False)
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "cache_metadata": {"enabled": False},
        "cost_guard": {
            "enabled": True,
            "allow_paid_downloads": False,
            "max_cost_usd": 0.0,
            "fail_if_estimate_unavailable": True,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(ValueError, match="required strategy source column groups"):
        engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "source_bar_file_missing_required_columns" in captured.out
    assert "source column signed_volume" in captured.out
    assert "source column trades" in captured.out


def test_read_bars_file_maps_supported_orderflow_aliases(tmp_path: Path) -> None:
    path = tmp_path / "alias_seed.csv"
    pd.DataFrame(
        [
            {
                "timestamp": "2026-06-11 09:30:00-04:00",
                "symbol": "ESM6",
                "Open": 5000.0,
                "High": 5001.0,
                "Low": 4999.5,
                "Last": 5000.25,
                "Volume": 100.0,
                "Delta": 10.0,
                "AskVolume": 55.0,
                "BidVolume": 45.0,
                "NumberOfTrades": 25,
            }
        ]
    ).to_csv(path, index=False)

    bars = engine.read_bars_file(
        path,
        root_symbol="ES",
        timezone="America/New_York",
        source="test",
        required_source_columns=[
            "timestamp",
            "contract_symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "signed_volume",
            "buy_volume",
            "sell_volume",
            "trades",
        ],
    )

    assert len(bars) == 1
    assert bars[0].contract_symbol == "ESM6"
    assert bars[0].open == 5000.0
    assert bars[0].close == 5000.25
    assert bars[0].signed_volume == 10.0
    assert bars[0].buy_volume == 55.0
    assert bars[0].sell_volume == 45.0
    assert bars[0].trades == 25


def test_historical_fetch_rejects_quote_delta_before_api_key_lookup(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["schema"] = "mbp-1"
    cfg["databento"]["delta_method"] = "price_vs_quote"
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    monkeypatch.setattr(
        engine,
        "databento_api_key",
        lambda _: pytest.fail("api key lookup should not run for unsupported historical fetch"),
    )

    with pytest.raises(RuntimeError, match="unsupported"):
        engine.fetch_databento_historical_bars(signal_engine, {"enabled": True})

    captured = capsys.readouterr()
    assert "historical_fetch_unsupported_data_contract" in captured.out
    assert "timeseries_download_attempted" in captured.out


def test_historical_fetch_rejects_mbp1_schema_before_api_key_lookup(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["schema"] = "mbp-1"
    cfg["databento"]["delta_method"] = "aggressor_side"
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    monkeypatch.setattr(
        engine,
        "databento_api_key",
        lambda _: pytest.fail("api key lookup should not run for unsupported historical fetch"),
    )

    with pytest.raises(RuntimeError, match="unsupported"):
        engine.fetch_databento_historical_bars(signal_engine, {"enabled": True})

    captured = capsys.readouterr()
    assert "historical_fetch_unsupported_data_contract" in captured.out
    assert "schema" in captured.out


def test_databento_metadata_check_uses_metadata_only_and_succeeds() -> None:
    cfg = load_execution_config("signal_engine.example.yaml")
    cfg["databento"]["historical"].pop("cache_path", None)
    cfg["databento"]["historical"].pop("seed_bars_path", None)
    cfg["databento"]["historical"]["refresh"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "signal_engine.example.yaml")

    report = engine.check_databento_metadata(signal_engine, client=FakeClient(cost=0.0))

    assert report["ok"] is True
    assert report["operation_mode"] == "metadata_only"
    assert report["metadata_only"] is True
    assert report["api_key"]["client_injected"] is True
    assert report["api_key"]["required"] is False
    assert report["checks"]["api_key"] == report["api_key"]
    assert report["timeseries_download_attempted"] is False
    assert report["live_subscription_attempted"] is False
    assert report["metadata_operations_attempted"] == [
        "metadata.get_dataset_range",
        "metadata.list_schemas",
        "metadata.list_fields",
        "symbology.resolve",
        "metadata.get_cost",
        "metadata.get_billable_size",
    ]
    assert report["databento_api_audit"] == {
        "metadata_only": True,
        "metadata_operations_attempted": report["metadata_operations_attempted"],
        "timeseries_get_range_attempted": False,
        "live_subscribe_attempted": False,
        "guarded_timeseries_operation": "timeseries.get_range",
        "guarded_live_operation": "Live.subscribe",
    }
    assert report["checks"]["dataset_range"]["ok"] is True
    assert report["checks"]["schemas"]["ok"] is True
    assert report["checks"]["fields"]["ok"] is True
    assert report["checks"]["fields"]["missing_required_field_groups"] == []
    assert report["checks"]["symbology"]["ok"] is True
    assert report["checks"]["symbology"]["mapping_count"] == 1
    assert report["checks"]["symbology"]["stype_out"] == "instrument_id"
    assert report["checks"]["symbology"]["start_date"] == "2026-06-09"
    assert report["checks"]["symbology"]["end_date"] == "2026-06-10"
    assert report["checks"]["historical_cost_guard"]["estimated_cost_usd"] == 0.0
    assert report["checks"]["historical_cost_guard"]["metadata_only"] is True
    assert report["checks"]["historical_cost_guard"]["timeseries_get_range_attempted"] is False
    assert report["checks"]["historical_cost_guard"]["guarded_operation"] == "timeseries.get_range"
    assert report["checks"]["live_cost_guard"]["ok"] is True
    assert report["checks"]["live_cost_guard"]["live_enabled"] is False
    assert report["checks"]["live_cost_guard"]["allowed"] is False


def test_databento_metadata_check_missing_api_key_fails_before_client_import(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"].pop("api_key", None)
    cfg["databento"]["api_key_env"] = "MISSING_DATABENTO_KEY_FOR_METADATA_TEST"
    monkeypatch.delenv("MISSING_DATABENTO_KEY_FOR_METADATA_TEST", raising=False)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Missing Databento API key"):
        engine.check_databento_metadata(signal_engine)

    captured = capsys.readouterr()
    assert "databento_api_key_missing" in captured.out
    assert "MISSING_DATABENTO_KEY_FOR_METADATA_TEST" in captured.out
    assert "timeseries.get_range" not in captured.out
    assert "Live.subscribe" not in captured.out


def test_symbology_check_date_window_uses_strictly_prior_available_day() -> None:
    start_date, end_date = engine.symbology_check_date_window(
        available_end=pd.Timestamp("2026-06-12 16:50:00", tz="UTC")
    )

    assert start_date == "2026-06-11"
    assert end_date == "2026-06-12"


def test_databento_metadata_check_fails_when_live_enabled_without_cost_acknowledgement() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["live"]["enabled"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="live cost guard is not explicitly acknowledged"):
        engine.check_databento_metadata(signal_engine, client=FakeClient(cost=0.0))


def test_databento_metadata_check_allows_live_enabled_with_cost_acknowledgement() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["live"]["enabled"] = True
    allow_test_live_subscription(cfg)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.check_databento_metadata(signal_engine, client=FakeClient(cost=0.0))

    assert report["ok"] is True
    assert report["timeseries_download_attempted"] is False
    assert report["live_subscription_attempted"] is False
    assert report["databento_api_audit"]["live_subscribe_attempted"] is False
    assert report["databento_api_audit"]["guarded_live_operation"] == "Live.subscribe"
    assert report["checks"]["live_cost_guard"]["ok"] is True
    assert report["checks"]["live_cost_guard"]["live_enabled"] is True
    assert report["checks"]["live_cost_guard"]["allowed"] is True


def test_databento_metadata_check_fails_unsupported_historical_download_before_cost(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["schema"] = "mbp-1"
    cfg["databento"]["delta_method"] = "price_vs_quote"
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cost_guard": {
            "enabled": True,
            "allow_paid_downloads": False,
            "max_cost_usd": 0.0,
            "fail_if_estimate_unavailable": True,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    client = CountingFakeClient(cost=0.0)

    with pytest.raises(RuntimeError, match="Historical Databento download is required but unsupported"):
        engine.check_databento_metadata(signal_engine, client=client)

    captured = capsys.readouterr()
    assert "historical_fetch_contract_unsupported" in captured.out
    assert '"timeseries_download_attempted": false' in captured.out
    assert client.metadata.cost_calls == 0
    assert client.metadata.billable_size_calls == 0


def test_databento_metadata_check_allows_unsupported_builtin_fetch_when_cache_is_prebuilt(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "quote_delta_seed.csv"
    cache_path.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["schema"] = "mbp-1"
    cfg["databento"]["delta_method"] = "price_vs_quote"
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "cache_metadata": {"enabled": False},
        "cost_guard": {
            "enabled": True,
            "allow_paid_downloads": False,
            "max_cost_usd": 0.0,
            "fail_if_estimate_unavailable": True,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    client = CountingFakeClient(cost=0.0)

    report = engine.check_databento_metadata(signal_engine, client=client)

    contract = report["checks"]["historical_fetch_contract"]
    assert report["ok"] is True
    assert contract["ok"] is True
    assert contract["fetch_supported"] is False
    assert contract["fetch_required"] is False
    assert contract["source"] == "historical_cache"
    assert report["checks"]["historical_cost_guard"]["ok"] is True
    assert report["checks"]["historical_cost_guard"]["skipped"] is True
    assert report["checks"]["historical_cost_guard"]["source"] == "historical_cache"
    assert client.metadata.cost_calls == 0
    assert client.metadata.billable_size_calls == 0


def test_databento_metadata_check_skips_historical_cost_when_local_seed_file_is_prebuilt(
    tmp_path: Path,
) -> None:
    seed_path = tmp_path / "prebuilt_seed.csv"
    seed_path.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "seed_bars_path": str(seed_path),
        "cache_metadata": {"enabled": False},
        "cost_guard": {
            "enabled": True,
            "allow_paid_downloads": False,
            "max_cost_usd": 0.0,
            "fail_if_estimate_unavailable": True,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    client = CountingFakeClient(cost=999.0)

    report = engine.check_databento_metadata(signal_engine, client=client)

    contract = report["checks"]["historical_fetch_contract"]
    assert report["ok"] is True
    assert contract["fetch_required"] is False
    assert contract["source"] == "historical_file"
    assert report["checks"]["historical_cost_guard"]["ok"] is True
    assert report["checks"]["historical_cost_guard"]["skipped"] is True
    assert report["checks"]["historical_cost_guard"]["source"] == "historical_file"
    assert client.metadata.cost_calls == 0
    assert client.metadata.billable_size_calls == 0


def test_databento_metadata_check_runs_historical_cost_when_refresh_requires_download(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "seed.csv"
    cache_path.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "refresh": True,
        "cost_guard": {
            "enabled": True,
            "allow_paid_downloads": False,
            "max_cost_usd": 0.0,
            "fail_if_estimate_unavailable": True,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    client = CountingFakeClient(cost=0.0)

    report = engine.check_databento_metadata(signal_engine, client=client)

    contract = report["checks"]["historical_fetch_contract"]
    assert report["ok"] is True
    assert contract["fetch_required"] is True
    assert contract["source"] == "databento_historical"
    assert report["checks"]["historical_cost_guard"]["ok"] is True
    assert report["checks"]["historical_cost_guard"]["skipped"] is False
    assert client.metadata.cost_calls == 1
    assert client.metadata.billable_size_calls == 1


def test_databento_metadata_check_fails_when_required_live_fields_are_missing() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="missing required live field"):
        engine.check_databento_metadata(signal_engine, client=MissingSideClient())


def test_databento_metadata_check_fails_when_field_list_is_empty() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="required live fields could not be verified"):
        engine.check_databento_metadata(signal_engine, client=EmptyFieldsClient())


def test_databento_metadata_check_fails_when_field_listing_errors() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Unable to list Databento fields"):
        engine.check_databento_metadata(signal_engine, client=FieldListingErrorClient())


def test_live_schema_field_requirement_report_allows_tick_rule_without_side() -> None:
    report = engine.live_schema_field_requirement_report(
        ["ts_event", "price", "size", "instrument_id"],
        delta_method="tick_rule",
        contract_symbol_regex=r"^ES[HMUZ]\d$",
    )

    assert report["ok"] is True
    assert report["missing_required_field_groups"] == []


def test_live_schema_field_requirement_report_requires_quote_fields_for_quote_delta() -> None:
    report = engine.live_schema_field_requirement_report(
        ["ts_event", "price", "size", "side", "instrument_id"],
        delta_method="price_vs_quote",
        contract_symbol_regex=r"^ES[HMUZ]\d$",
    )

    assert report["ok"] is False
    assert {item["label"] for item in report["missing_required_field_groups"]} == {
        "best bid price",
        "best ask price",
    }


def test_live_schema_field_requirement_report_requires_action_for_mbp1() -> None:
    report = engine.live_schema_field_requirement_report(
        ["ts_event", "price", "size", "side", "instrument_id", "bid_px_00", "ask_px_00"],
        delta_method="price_vs_quote",
        contract_symbol_regex=r"^ES[HMUZ]\d$",
        schema="mbp-1",
    )

    assert report["ok"] is False
    assert {item["label"] for item in report["missing_required_field_groups"]} == {"trade action"}


def test_databento_metadata_check_fails_when_mbp1_action_field_is_missing() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["schema"] = "mbp-1"
    cfg["databento"]["delta_method"] = "price_vs_quote"
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="missing required live field"):
        engine.check_databento_metadata(signal_engine, client=MissingActionClient())


def test_databento_metadata_check_fails_on_unresolved_symbology() -> None:
    cfg = load_execution_config("signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "signal_engine.example.yaml")
    client = FakeClient(
        cost=0.0,
        symbology_response={
            "result": {},
            "symbols": ["BAD.FUT"],
            "stype_in": "parent",
            "stype_out": "instrument_id",
            "partial": [],
            "not_found": ["BAD.FUT"],
            "message": "No mappings",
            "status": 0,
        },
    )

    with pytest.raises(RuntimeError, match="symbology"):
        engine.check_databento_metadata(signal_engine, client=client)


def test_databento_metadata_check_blocks_paid_historical_request() -> None:
    cfg = load_execution_config("signal_engine.example.yaml")
    cfg["databento"]["historical"].pop("cache_path", None)
    cfg["databento"]["historical"].pop("seed_bars_path", None)
    cfg["databento"]["historical"]["refresh"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Historical cost guard check failed"):
        engine.check_databento_metadata(signal_engine, client=FakeClient(cost=0.01))


def test_readiness_check_validates_cache_metadata_and_avoids_outbox_writes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cache_path = tmp_path / "seed.csv"
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["engine"]["operator"]["sound"]["enabled"] = True
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": True},
        "cost_guard": {
            "enabled": True,
            "allow_paid_downloads": False,
            "max_cost_usd": 0.0,
            "fail_if_estimate_unavailable": True,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    engine.write_historical_cache(signal_engine, cache_path, [sample_source_bar()], source="test")
    capsys.readouterr()

    payload = engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "readiness_data_plan_ok" in captured.out
    assert "readiness_live_safety_stops_ok" in captured.out
    assert "readiness_process_lock_ok" in captured.out
    assert "readiness_output_paths_ok" in captured.out
    assert "readiness_output_sink_safety_ok" in captured.out
    assert "readiness_operator_sound_ok" in captured.out
    assert "readiness_historical_cache_loaded" in captured.out
    assert "readiness_check_ok" in captured.out
    assert payload["ok"] is True
    assert payload["databento"]["operation_mode"] == "metadata_only"
    assert payload["databento"]["metadata_only"] is True
    assert payload["databento"]["databento_api_audit"]["timeseries_get_range_attempted"] is False
    assert payload["databento"]["databento_api_audit"]["live_subscribe_attempted"] is False
    assert payload["databento"]["timeseries_download_attempted"] is False
    assert payload["databento"]["live_subscription_attempted"] is False
    assert payload["databento"]["live_cost_guard"]["ok"] is True
    assert payload["databento"]["live_cost_guard"]["live_enabled"] is False
    assert payload["databento"]["live_safety_stops"] == engine.live_safety_stop_config(
        cfg["databento"]["live"]
    )
    assert payload["databento"]["live_safety_stop_readiness"]["ok"] is True
    assert payload["databento"]["live_safety_stop_readiness"]["disabled_required_stops"] == []
    assert payload["data_plan"]["ok"] is True
    assert "signed_volume" in payload["data_plan"]["source_columns"]
    assert payload["data_plan"]["required_source_column_groups"]
    live_field_labels = {item["label"] for item in payload["data_plan"]["required_live_field_groups"]}
    assert "aggressor side" in live_field_labels
    assert "trade price" in live_field_labels
    assert payload["historical_seed"]["source_bars"] == 1
    assert payload["strategies"]["active"] == 1
    assert payload["strategies"]["evaluated_strategy_rows"] >= 1
    assert payload["strategies"]["per_strategy"][0]["evaluated_strategy_row_count"] >= 1
    assert payload["alerts"]["entry_alerts_emitted"] == 0
    assert payload["alerts"]["alert_file_writes"] == 0
    assert payload["alerts"]["output_paths"]["ok"] is True
    assert payload["alerts"]["output_sink_safety"]["ok"] is True
    assert payload["alerts"]["output_sink_safety"]["required"] is True
    assert payload["alerts"]["execution_intent_contract"]["ok"] is True
    assert payload["alerts"]["execution_intent_contract"]["checked"] is True
    assert payload["alerts"]["execution_intent_contract"]["probes_checked"] == 2
    assert payload["operator"]["sound"]["ok"] is True
    assert payload["operator"]["sound"]["checks"][0]["reason"] == "sound command executable is available"
    assert payload["operator"]["sound"]["checks"][0]["executable"] == "/usr/bin/afplay"
    assert payload["process_lock"]["ok"] is True
    assert payload["process_lock"]["status"] == "available"
    assert {
        item["label"]: item["checked"] for item in payload["alerts"]["output_paths"]["checks"]
    } == {
        "entry_alerts": True,
        "setup_alerts": True,
        "execution_intents": True,
    }
    assert signal_engine.operator_sound_health.attempts == 0
    assert not (tmp_path / "entry_signals.jsonl").exists()
    assert not (tmp_path / "trade_setups.jsonl").exists()
    assert not (tmp_path / "execution_intents.jsonl").exists()


def test_readiness_check_accepts_seed_file_with_matching_metadata(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    seed_path = tmp_path / "seed_file.csv"
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["engine"]["process_lock"]["path"] = str(tmp_path / "signal_engine.lock")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "seed_bars_path": str(seed_path),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": True},
        "cost_guard": {
            "enabled": True,
            "allow_paid_downloads": False,
            "max_cost_usd": 0.0,
            "fail_if_estimate_unavailable": True,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    engine.write_historical_cache(signal_engine, seed_path, [sample_source_bar()], source="prebuilt_seed")
    capsys.readouterr()

    payload = engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert payload["ok"] is True
    assert "historical_seed_file_metadata_valid" in captured.out
    assert "readiness_historical_seed_file_loaded" in captured.out
    assert "readiness_check_ok" in captured.out
    assert payload["historical_seed"]["source_bars"] == 1
    assert payload["strategies"]["evaluated_strategy_rows"] >= 1
    assert not (tmp_path / "entry_signals.jsonl").exists()
    assert not (tmp_path / "trade_setups.jsonl").exists()
    assert not (tmp_path / "execution_intents.jsonl").exists()


def test_readiness_check_degrades_when_local_seed_has_source_quality_drops(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cache_path = tmp_path / "seed.csv"
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["engine"]["process_lock"]["path"] = str(tmp_path / "signal_engine.lock")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": True},
        "cost_guard": {
            "enabled": True,
            "allow_paid_downloads": False,
            "max_cost_usd": 0.0,
            "fail_if_estimate_unavailable": True,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    engine.write_historical_cache(
        signal_engine,
        cache_path,
        [
            sample_source_bar(volume=10.0, signed_volume=12.0, buy_volume=11.0, sell_volume=0.0),
            sample_source_bar(timestamp_utc=ts("2026-06-11 13:31:00"), signed_volume=10.0),
        ],
        source="test",
    )
    capsys.readouterr()

    payload = engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "source_bar_quality_issues" in captured.out
    assert "readiness_check_degraded" in captured.out
    assert payload["ok"] is False
    assert "historical seed bars were dropped by source-bar quality checks" in payload["degraded_reasons"]
    assert payload["historical_seed"]["source_bars"] == 2
    assert payload["historical_seed"]["accepted_source_bars"] == 1
    assert payload["historical_seed"]["source_bar_quality_drops"] == 1
    assert payload["historical_seed"]["source_bar_quality"]["source_bar_quality_drops"] == 1
    assert payload["historical_seed"]["source_bar_quality"]["last_source_bar_quality_report"]["bars_dropped"] == 1


def test_readiness_check_degrades_when_data_plan_has_warnings(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["databento"]["historical"] = {"enabled": False}
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    signal_engine.data_plan["warnings"].append("test warning")

    payload = engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "readiness_data_plan_degraded" in captured.out
    assert payload["event"] == "readiness_check_degraded"
    assert "strategy data plan has warnings" in payload["degraded_reasons"]
    assert payload["data_plan"]["ok"] is False
    assert payload["data_plan"]["warnings"] == ["test warning"]


def test_readiness_process_lock_report_checks_available_lock_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    lock_path = tmp_path / "runtime" / "engine.lock"
    cfg["engine"]["process_lock"]["path"] = str(lock_path)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.readiness_process_lock_report(signal_engine)

    captured = capsys.readouterr()
    assert "readiness_process_lock_ok" in captured.out
    assert report["ok"] is True
    assert report["checked"] is True
    assert report["status"] == "available"
    assert report["probe_file_created"] is True
    assert not lock_path.exists()
    assert not list(lock_path.parent.glob(".*.readiness_probe.*"))


def test_readiness_process_lock_report_flags_active_lock(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    lock_path = tmp_path / "engine.lock"
    lock_path.write_text(json.dumps({"pid": os.getpid(), "token": "active"}) + "\n", encoding="utf-8")
    cfg["engine"]["process_lock"]["path"] = str(lock_path)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.readiness_process_lock_report(signal_engine)

    captured = capsys.readouterr()
    assert "readiness_process_lock_failed" in captured.out
    assert report["ok"] is False
    assert report["status"] == "active_lock_present"
    assert report["error_type"] == "ProcessLockHeld"
    assert report["existing_lock"]["pid"] == os.getpid()


def test_readiness_process_lock_report_allows_stale_lock(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    lock_path = tmp_path / "engine.lock"
    lock_path.write_text(json.dumps({"pid": 99999999, "token": "stale"}) + "\n", encoding="utf-8")
    cfg["engine"]["process_lock"]["path"] = str(lock_path)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.readiness_process_lock_report(signal_engine)

    captured = capsys.readouterr()
    assert "readiness_process_lock_stale" in captured.out
    assert report["ok"] is True
    assert report["status"] == "stale_replaceable"
    assert lock_path.exists()


def test_readiness_check_degrades_when_process_lock_is_active(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    lock_path = tmp_path / "engine.lock"
    lock_path.write_text(json.dumps({"pid": os.getpid(), "token": "active"}) + "\n", encoding="utf-8")
    cfg["engine"]["process_lock"]["path"] = str(lock_path)
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["databento"]["historical"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    capsys.readouterr()

    payload = engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "readiness_process_lock_failed" in captured.out
    assert "readiness_check_degraded" in captured.out
    assert payload["event"] == "readiness_check_degraded"
    assert payload["ok"] is False
    assert payload["degraded_reasons"] == ["runtime process lock is not ready"]
    assert payload["process_lock"]["status"] == "active_lock_present"


def test_readiness_output_sink_safety_report_requires_fail_closed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["alert_file"]["fail_on_write_error"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.readiness_output_sink_safety_report(signal_engine)

    captured = capsys.readouterr()
    assert "readiness_output_sink_safety_failed" in captured.out
    assert report["ok"] is False
    assert report["required"] is True
    assert report["checked"] is True
    assert "entry_alerts.fail_on_write_error" in report["failed_checks"]


def test_readiness_output_sink_safety_report_allows_explicit_diagnostic_skip(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["output_path_readiness"]["require_fail_closed_sinks"] = False
    cfg["engine"]["alert_file"]["fail_on_write_error"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.readiness_output_sink_safety_report(signal_engine)

    captured = capsys.readouterr()
    assert "readiness_output_sink_safety_skipped" in captured.out
    assert report["ok"] is True
    assert report["required"] is False
    assert report["checked"] is False
    assert report["failed_checks"] == []


def test_readiness_check_degrades_when_output_sinks_are_not_fail_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["engine"]["execution_intents"]["fail_on_write_error"] = False
    cfg["databento"]["historical"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    capsys.readouterr()

    payload = engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "readiness_output_sink_safety_failed" in captured.out
    assert "readiness_check_degraded" in captured.out
    assert payload["event"] == "readiness_check_degraded"
    assert payload["ok"] is False
    assert payload["degraded_reasons"] == ["configured alert/outbox sinks are not fail-closed"]
    assert payload["alerts"]["output_sink_safety"]["ok"] is False
    assert "execution_intents.fail_on_write_error" in payload["alerts"]["output_sink_safety"]["failed_checks"]


def test_readiness_live_metadata_preflight_report_requires_guard_when_live_enabled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["enabled"] = True
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["allow_live_without_metadata_preflight"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.readiness_live_metadata_preflight_report(signal_engine)

    captured = capsys.readouterr()
    assert "readiness_live_metadata_preflight_failed" in captured.out
    assert report["ok"] is False
    assert report["checked"] is True
    assert report["live_enabled"] is True
    assert report["metadata_preflight"] is False
    assert report["allow_live_without_metadata_preflight"] is False


def test_readiness_check_degrades_when_live_metadata_preflight_is_disabled(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["enabled"] = True
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["allow_live_without_metadata_preflight"] = False
    cfg["databento"]["historical"]["enabled"] = False
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    payload = engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "readiness_live_metadata_preflight_failed" in captured.out
    assert "readiness_check_degraded" in captured.out
    assert payload["event"] == "readiness_check_degraded"
    assert payload["ok"] is False
    assert "live metadata preflight guard is not enabled" in payload["degraded_reasons"]
    report = payload["databento"]["live_metadata_preflight_readiness"]
    assert report["ok"] is False
    assert report["live_enabled"] is True
    assert report["metadata_preflight"] is False


def test_readiness_live_safety_stop_report_requires_fail_closed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["live"]["stop_on_no_trade_ticks"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.readiness_live_safety_stop_report(signal_engine)

    captured = capsys.readouterr()
    assert "readiness_live_safety_stops_failed" in captured.out
    assert report["ok"] is False
    assert report["checked"] is True
    assert report["required"] is True
    assert report["disabled_required_stops"] == ["stop_on_no_trade_ticks"]


def test_readiness_live_safety_stop_report_treats_state_lock_watchdog_as_optional(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["live"]["stop_on_state_lock_timeout"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.readiness_live_safety_stop_report(signal_engine)

    captured = capsys.readouterr()
    assert "readiness_live_safety_stops_ok" in captured.out
    assert report["ok"] is True
    assert report["checked"] is True
    assert report["required"] is True
    assert report["safety_stops"]["stop_on_state_lock_timeout"] is False
    assert report["disabled_required_stops"] == []


def test_readiness_live_safety_stop_report_allows_explicit_diagnostic_skip(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["live"]["require_fail_closed_safety_stops"] = False
    cfg["databento"]["live"]["stop_on_no_trade_ticks"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.readiness_live_safety_stop_report(signal_engine)

    captured = capsys.readouterr()
    assert "readiness_live_safety_stops_skipped" in captured.out
    assert report["ok"] is True
    assert report["required"] is False
    assert report["disabled_required_stops"] == []


def test_readiness_check_degrades_when_live_safety_stops_not_fail_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["databento"]["historical"]["enabled"] = False
    cfg["databento"]["live"]["stop_on_no_trade_ticks"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    capsys.readouterr()

    payload = engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "readiness_live_safety_stops_failed" in captured.out
    assert "readiness_check_degraded" in captured.out
    assert payload["event"] == "readiness_check_degraded"
    assert payload["ok"] is False
    assert payload["degraded_reasons"] == ["live safety stops are not fail-closed"]
    assert payload["databento"]["live_safety_stop_readiness"]["ok"] is False
    assert payload["databento"]["live_safety_stop_readiness"]["disabled_required_stops"] == [
        "stop_on_no_trade_ticks"
    ]


def test_readiness_execution_intent_contract_report_validates_active_strategy_directions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy_runtime = signal_engine.strategies[0]
    trades_by_session_before = copy.deepcopy(strategy_runtime.trades_by_session)
    sent_signal_keys_before = set(strategy_runtime.sent_signal_keys)

    report = engine.readiness_execution_intent_contract_report(signal_engine)

    captured = capsys.readouterr()
    assert "readiness_execution_intent_contract_ok" in captured.out
    assert report["ok"] is True
    assert report["enabled"] is True
    assert report["checked"] is True
    assert report["probe_mode"] == "strategy_runtime_build_alert"
    assert report["strategies_checked"] == 1
    assert report["probes_checked"] == 2
    assert report["strategies"][0]["directions_checked"] == ["long", "short"]
    assert report["strategies"][0]["errors"] == []
    assert strategy_runtime.trades_by_session == trades_by_session_before
    assert strategy_runtime.sent_signal_keys == sent_signal_keys_before


def test_readiness_execution_intent_contract_report_skips_when_disabled() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["execution_intents"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.readiness_execution_intent_contract_report(signal_engine)

    assert report["ok"] is True
    assert report["enabled"] is False
    assert report["checked"] is False
    assert report["probes_checked"] == 0
    assert report["reason"] == "execution_intents.enabled is false"


def test_readiness_execution_intent_contract_report_catches_contract_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    original_builder = engine.build_execution_intent

    def broken_build_execution_intent(*args: object, **kwargs: object) -> dict:
        intent = original_builder(*args, **kwargs)
        intent["schema_version"] = "execution_intent.broken"
        return intent

    monkeypatch.setattr(engine, "build_execution_intent", broken_build_execution_intent)

    report = engine.readiness_execution_intent_contract_report(signal_engine)

    captured = capsys.readouterr()
    assert "readiness_execution_intent_contract_failed" in captured.out
    assert report["ok"] is False
    assert report["checked"] is True
    assert report["errors"]
    assert report["errors"][0]["error_type"] == "ValueError"
    assert "unsupported execution intent version" in report["errors"][0]["error"]


def test_readiness_execution_intent_contract_report_catches_trade_sanity_rejection(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["operator"]["print_rejection_readable"] = False
    cfg["engine"]["trade_sanity"]["max_stop_points"] = 0.5
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.readiness_execution_intent_contract_report(signal_engine)

    captured = capsys.readouterr()
    assert "SIGNAL_REJECTED" in captured.out
    assert "readiness_execution_intent_contract_failed" in captured.out
    assert report["ok"] is False
    assert report["probe_mode"] == "strategy_runtime_build_alert"
    assert report["errors"]
    assert report["errors"][0]["error_type"] == "ValueError"
    assert "strategy build_alert returned no alert" in report["errors"][0]["error"]


def test_readiness_check_fails_when_execution_intent_contract_probe_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["databento"]["historical"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    original_builder = engine.build_execution_intent

    def broken_build_execution_intent(*args: object, **kwargs: object) -> dict:
        intent = original_builder(*args, **kwargs)
        intent.pop("timing", None)
        return intent

    monkeypatch.setattr(engine, "build_execution_intent", broken_build_execution_intent)

    with pytest.raises(RuntimeError, match="execution-intent contract check failed"):
        engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))


def test_readiness_check_fails_when_live_enabled_without_cost_acknowledgement() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["historical"]["enabled"] = False
    cfg["databento"]["live"]["enabled"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="live cost guard is not explicitly acknowledged"):
        engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))


def test_readiness_check_fails_when_output_path_is_directory(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    bad_alert_path = tmp_path / "entry_signals.jsonl"
    bad_alert_path.mkdir()
    cfg["engine"]["alerts_path"] = str(bad_alert_path)
    cfg["engine"]["alert_file"]["fail_on_write_error"] = False
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["engine"]["operator"]["sound"]["enabled"] = True
    cfg["databento"]["historical"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    capsys.readouterr()

    with pytest.raises(RuntimeError, match="Readiness output path check failed: entry_alerts"):
        engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "readiness_output_path_check_failed" in captured.out
    assert "IsADirectoryError" in captured.out
    assert str(bad_alert_path) in captured.out
    assert signal_engine.operator_sound_health.attempts == 0


def test_readiness_check_reports_degraded_when_output_path_failure_is_nonfatal(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    bad_alert_path = tmp_path / "entry_signals.jsonl"
    bad_alert_path.mkdir()
    cfg["engine"]["alerts_path"] = str(bad_alert_path)
    cfg["engine"]["alert_file"]["fail_on_write_error"] = False
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["engine"]["output_path_readiness"]["fail_on_error"] = False
    cfg["engine"]["output_path_readiness"]["require_fail_closed_sinks"] = False
    cfg["databento"]["historical"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    capsys.readouterr()

    payload = engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "readiness_output_path_check_failed" in captured.out
    assert "readiness_check_degraded" in captured.out
    assert "readiness_check_ok" not in captured.out
    assert payload["event"] == "readiness_check_degraded"
    assert payload["ok"] is False
    assert payload["alerts"]["output_paths"]["ok"] is False
    assert payload["degraded_reasons"] == [
        "one or more configured alert/outbox output paths are not writable"
    ]


def test_readiness_check_reports_degraded_when_operator_sound_command_is_missing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["engine"]["operator"]["sound"] = {
        "enabled": True,
        "bell": False,
        "on_setup": True,
        "on_entry": True,
        "on_system": True,
        "cleanup_on_exit": True,
        "command": "/definitely/missing/operator-sound-player",
    }
    cfg["databento"]["historical"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    capsys.readouterr()

    payload = engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "readiness_operator_sound_check_failed" in captured.out
    assert "readiness_check_degraded" in captured.out
    assert payload["event"] == "readiness_check_degraded"
    assert payload["ok"] is False
    assert payload["operator"]["sound"]["ok"] is False
    assert payload["operator"]["sound"]["checks"][0]["error_type"] == "FileNotFoundError"
    assert payload["degraded_reasons"] == ["operator sound alerting is not ready"]
    assert signal_engine.operator_sound_health.attempts == 0


def test_readiness_check_reports_degraded_when_operator_sound_has_no_audible_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["engine"]["operator"]["sound"] = {
        "enabled": True,
        "bell": False,
        "on_setup": True,
        "on_entry": True,
        "on_system": True,
        "cleanup_on_exit": True,
        "command": "/bin/echo ding",
        "max_active_commands": 0,
    }
    cfg["databento"]["historical"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    capsys.readouterr()

    payload = engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "readiness_operator_sound_check_failed" in captured.out
    assert "readiness_check_degraded" in captured.out
    assert payload["event"] == "readiness_check_degraded"
    assert payload["operator"]["sound"]["ok"] is False
    assert payload["operator"]["sound"]["max_active_commands"] == 0
    assert payload["operator"]["sound"]["checks"][0]["error_type"] == "ConfigError"
    assert payload["operator"]["sound"]["checks"][0]["reason"] == (
        "external sound commands are disabled and terminal bell is disabled"
    )


def test_output_path_readiness_disabled_does_not_probe(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    output_dir = tmp_path / "missing_runtime" / "alerts"
    cfg["engine"]["output_path_readiness"]["enabled"] = False
    cfg["engine"]["alerts_path"] = str(output_dir / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(output_dir / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(output_dir / "execution_intents.jsonl")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.readiness_output_path_report(signal_engine)

    assert report["ok"] is True
    assert all(item["checked"] is False for item in report["checks"])
    assert all(item["reason"] == "output_path_readiness disabled" for item in report["checks"])
    assert not output_dir.exists()


def test_readiness_check_requires_configured_cache_when_historical_enabled(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(tmp_path / "missing_seed.csv"),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": True},
        "cost_guard": {
            "enabled": True,
            "allow_paid_downloads": False,
            "max_cost_usd": 0.0,
            "fail_if_estimate_unavailable": True,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="historical cache not found"):
        engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))


def test_readiness_check_fails_when_cache_produces_no_evaluable_strategy_rows(
    tmp_path: Path,
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cache_path = tmp_path / "seed.csv"
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": True},
        "cost_guard": {
            "enabled": True,
            "allow_paid_downloads": False,
            "max_cost_usd": 0.0,
            "fail_if_estimate_unavailable": True,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    engine.write_historical_cache(signal_engine, cache_path, [sample_source_bar()], source="test")
    strategy = signal_engine.strategies[0]
    strategy.completed_features = lambda _: pd.DataFrame(  # type: ignore[method-assign]
        [
            {
                "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
                "contract_symbol": "ESM6",
                "session_date": "2026-06-11",
                "high": 5001.0,
                "low": 4999.0,
                "signed_volume": float("nan"),
            }
        ]
    )

    with pytest.raises(RuntimeError, match="did not evaluate any complete feature rows"):
        engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    assert strategy.feature_quality_skip_count == 1
    assert strategy.evaluated_strategy_row_count == 0


def test_readiness_check_fails_when_contract_filter_rejects_all_cache_rows(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cache_path = tmp_path / "seed.csv"
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_path": str(cache_path),
        "cache_metadata": {"enabled": True, "fail_on_mismatch": True},
        "cost_guard": {
            "enabled": True,
            "allow_paid_downloads": False,
            "max_cost_usd": 0.0,
            "fail_if_estimate_unavailable": True,
        },
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    engine.write_historical_cache(
        signal_engine,
        cache_path,
        [sample_source_bar(contract_symbol="ESM6-ESU6")],
        source="test",
    )
    capsys.readouterr()

    with pytest.raises(RuntimeError, match="contract_symbol_regex"):
        engine.run_readiness_check(signal_engine, metadata_client=FakeClient(cost=0.0))

    captured = capsys.readouterr()
    assert "source_bar_contract_symbol_filtered" in captured.out
    assert "readiness_source_contract_filter_starved" in captured.out
    assert "ESM6-ESU6" in captured.out
    assert signal_engine.source_contract_filter_drops == 1
    assert signal_engine.store.bars() == []


def test_instrument_symbol_map_from_symbology_result_maps_ids_to_raw_symbols() -> None:
    result = {
        "ESM6": [{"d0": "2026-06-11", "d1": "2026-06-12", "s": "42140864"}],
        "ESU6": [{"d0": "2026-06-11", "d1": "2026-06-12", "s": 42140865}],
    }

    mapping = engine.instrument_symbol_map_from_symbology_result(result)

    assert mapping["42140864"] == "ESM6"
    assert mapping[42140864] == "ESM6"
    assert mapping["42140865"] == "ESU6"
    assert mapping[42140865] == "ESU6"


def test_instrument_symbol_map_from_instrument_id_result_maps_raw_symbols() -> None:
    result = {
        "42140864": [{"d0": "2026-06-11", "d1": "2026-06-12", "s": "ESM6"}],
        42140865: [{"d0": "2026-06-11", "d1": "2026-06-12", "s": "ESU6"}],
    }

    mapping = engine.instrument_symbol_map_from_instrument_id_result(result)

    assert mapping["42140864"] == "ESM6"
    assert mapping[42140864] == "ESM6"
    assert mapping["42140865"] == "ESU6"
    assert mapping[42140865] == "ESU6"


def test_resolved_raw_subscription_symbols_filters_spreads() -> None:
    mapping = {
        42140864: "ESM6",
        42140865: "ESU6",
        42004810: "ESM6-ESU6",
        55555555: "ESZ9",
        123: "NQM6",
    }

    symbols = engine.resolved_raw_subscription_symbols(
        mapping,
        contract_symbol_regex=r"^ES[HMUZ]\d$",
        reference_utc=ts("2026-06-11 12:00:00"),
        max_symbols=2,
    )

    assert symbols == ["ESM6", "ESU6"]


def test_futures_contract_maturity_date_infers_decade_from_reference() -> None:
    assert engine.futures_contract_maturity_date(
        "ESM6",
        reference_utc=ts("2026-06-11 12:00:00"),
    ) == pd.Timestamp("2026-06-19").date()
    assert engine.futures_contract_maturity_date(
        "ESH0",
        reference_utc=ts("2026-06-11 12:00:00"),
    ) == pd.Timestamp("2030-03-15").date()


def test_run_live_maps_instrument_id_records_to_raw_contract_symbols(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["enabled"] = False
    cfg["engine"]["execution_intents"]["enabled"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0
    cfg["databento"]["live"]["drop_partial_first_live_bar"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    records = [
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:30:05"),
            price=5000.0,
            size=10,
            side="B",
            instrument_id=42140864,
        ),
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:31:00"),
            price=5000.25,
            size=1,
            side="B",
            instrument_id=42140864,
        ),
    ]
    holder: dict[str, FakeLiveClient] = {}

    def factory(**kwargs: object) -> FakeLiveClient:
        client = FakeLiveClient(
            connected_after_start=True,
            records=records,
            record_delay_seconds=0.01,
            **kwargs,
        )
        holder["client"] = client
        return client

    rc = engine.run_live(
        signal_engine,
        once=False,
        max_runtime=0.1,
        live_client_factory=factory,
        metadata_client=FakeClient(cost=0.0),
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert "live_instrument_symbol_map_ready" in captured.out
    assert "live_resolved_raw_symbol_subscription" in captured.out
    assert "live_unmatched_contract_symbol_ignored" not in captured.out
    assert "ENTRY_SIGNAL" in captured.out
    assert '"contract_symbol": "ESM6"' in captured.out
    assert signal_engine.alert_count == 1
    assert holder["client"].subscribe_args == {
        "dataset": "GLBX.MDP3",
        "schema": "trades",
        "symbols": ["ESM6"],
        "stype_in": "raw_symbol",
    }


def test_run_live_callback_entry_writes_all_router_contracts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["engine"]["execution_intents"]["enforce_freshness"] = False
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0
    cfg["databento"]["live"]["drop_partial_first_live_bar"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    records = [
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:30:05"),
            price=5000.0,
            size=10,
            side="B",
            symbol="ESM6",
        ),
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:31:00"),
            price=5000.25,
            size=1,
            side="B",
            symbol="ESM6",
        ),
    ]

    def factory(**kwargs: object) -> FakeLiveClient:
        return FakeLiveClient(
            connected_after_start=True,
            records=records,
            record_delay_seconds=0.01,
            **kwargs,
        )

    rc = engine.run_live(signal_engine, once=False, max_runtime=0.1, live_client_factory=factory)

    captured = capsys.readouterr()
    assert rc == 0
    assert "TRADE_SETUP" in captured.out
    assert "ENTRY_SIGNAL" in captured.out
    assert '"event": "live_stopped"' in captured.out
    assert '"entry_alerts": 1' in captured.out
    assert signal_engine.setup_notice_sink.writes_succeeded == 1
    assert signal_engine.alert_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.writes_succeeded == 1

    setup_records = [
        json.loads(line)
        for line in (tmp_path / "trade_setups.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    alert_records = [
        json.loads(line)
        for line in (tmp_path / "entry_signals.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    intent_records = [
        json.loads(line)
        for line in (tmp_path / "execution_intents.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(setup_records) == 1
    assert len(alert_records) == 1
    assert len(intent_records) == 1
    engine.validate_setup_notice_contract(setup_records[0])
    engine.validate_entry_alert_contract(alert_records[0])
    engine.validate_execution_intent_ready_record(intent_records[0])
    assert intent_records[0]["alert_id"] == alert_records[0]["alert_id"]
    assert intent_records[0]["setup_id"] == setup_records[0]["setup_id"] == alert_records[0]["setup_id"]

    check_time = engine.normalize_utc_timestamp(intent_records[0]["entry_timestamp_utc"]) + pd.Timedelta(seconds=5)
    outbox = engine.load_actionable_execution_intents(
        tmp_path / "execution_intents.jsonl",
        now_utc=check_time,
        fail_on_error=True,
    )
    assert outbox["actionable_count"] == 1
    assert outbox["duplicate_alert_id_count"] == 0
    assert outbox["duplicate_setup_id_count"] == 0
    assert outbox["records"][0]["alert_id"] == alert_records[0]["alert_id"]


def test_run_live_console_stream_prints_ticks_and_completed_bars(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0
    cfg["databento"]["live"]["drop_partial_first_live_bar"] = False
    cfg["engine"]["dry_run_alerts"] = True
    cfg["engine"]["operator"]["sound"]["enabled"] = False
    cfg["engine"]["console"]["debug"] = False
    cfg["engine"]["console"]["live_stream"] = {
        "enabled": True,
        "print_trade_ticks": True,
        "print_completed_bars": True,
        "tick_throttle_seconds": 0.0,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    records = [
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:30:05"),
            price=5000.0,
            size=10,
            side="B",
            symbol="ESM6",
        ),
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:31:00"),
            price=5000.25,
            size=1,
            side="B",
            symbol="ESM6",
        ),
    ]

    rc = engine.run_live(
        signal_engine,
        once=False,
        max_runtime=0.1,
        live_client_factory=lambda **kwargs: FakeLiveClient(
            connected_after_start=True,
            records=records,
            record_delay_seconds=0.01,
            **kwargs,
        ),
    )

    captured = capsys.readouterr()
    assert rc == 0
    assert "LIVE_TICK event=live_trade_tick" in captured.out
    assert "LIVE_BAR event=live_source_bar_completed" in captured.out
    assert "LIVE_SESSION event=live_session_metrics" in captured.out
    assert "market_open_price=5,000" in captured.out
    assert "current_price=5,000" in captured.out
    assert "cumulative_delta=10" in captured.out
    assert "total_volume=10" in captured.out
    assert "price=5,000" in captured.out
    assert "volume=10" in captured.out


def test_run_live_metadata_preflight_failure_blocks_subscription(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    factory_called = False

    def factory(**kwargs: object) -> FakeLiveClient:
        nonlocal factory_called
        factory_called = True
        return FakeLiveClient(connected_after_start=True, **kwargs)

    with pytest.raises(RuntimeError, match="missing required live field"):
        engine.run_live(
            signal_engine,
            once=False,
            max_runtime=1,
            live_client_factory=factory,
            metadata_client=MissingSideClient(),
        )

    captured = capsys.readouterr()
    assert "live_metadata_preflight_failed" in captured.out
    assert '"timeseries_download_attempted": false' in captured.out
    assert '"live_subscription_attempted": false' in captured.out
    assert "live_subscribe" not in captured.out
    assert factory_called is False


def test_run_live_metadata_preflight_disabled_blocks_before_api_key_lookup(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"].pop("api_key", None)
    cfg["databento"]["api_key_env"] = "MISSING_DATABENTO_KEY_FOR_METADATA_PREFLIGHT_TEST"
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"].setdefault("cost_guard", {}).update(
        {
            "enabled": True,
            "allow_live_subscription": True,
            "acknowledge_live_data_may_be_billable": True,
        }
    )
    monkeypatch.delenv("MISSING_DATABENTO_KEY_FOR_METADATA_PREFLIGHT_TEST", raising=False)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    factory_called = False

    def factory(**kwargs: object) -> FakeLiveClient:
        nonlocal factory_called
        factory_called = True
        return FakeLiveClient(connected_after_start=True, **kwargs)

    with pytest.raises(RuntimeError, match="metadata preflight"):
        engine.run_live(signal_engine, once=False, max_runtime=1, live_client_factory=factory)

    captured = capsys.readouterr()
    assert "live_metadata_preflight_disabled" in captured.out
    assert '"timeseries_download_attempted": false' in captured.out
    assert '"live_subscription_attempted": false' in captured.out
    assert "Missing Databento API key" not in captured.out
    assert "live_subscribe" not in captured.out
    assert factory_called is False


def test_run_live_cost_guard_blocks_before_client_factory(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    cfg["databento"]["live"]["metadata_preflight"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    factory_called = False

    def factory(**kwargs: object) -> FakeLiveClient:
        nonlocal factory_called
        factory_called = True
        return FakeLiveClient(connected_after_start=True, **kwargs)

    with pytest.raises(RuntimeError, match="live cost guard"):
        engine.run_live(signal_engine, once=False, max_runtime=1, live_client_factory=factory)

    captured = capsys.readouterr()
    assert "live_subscription_blocked_by_cost_guard" in captured.out
    assert "live_subscribe" not in captured.out
    assert factory_called is False


def test_run_live_cost_guard_blocks_before_api_key_lookup(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"].pop("api_key", None)
    cfg["databento"]["api_key_env"] = "MISSING_DATABENTO_KEY_FOR_TEST"
    cfg["databento"]["live"]["metadata_preflight"] = False
    monkeypatch.delenv("MISSING_DATABENTO_KEY_FOR_TEST", raising=False)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    factory_called = False

    def factory(**kwargs: object) -> FakeLiveClient:
        nonlocal factory_called
        factory_called = True
        return FakeLiveClient(connected_after_start=True, **kwargs)

    with pytest.raises(RuntimeError, match="live cost guard"):
        engine.run_live(signal_engine, once=False, max_runtime=1, live_client_factory=factory)

    captured = capsys.readouterr()
    assert "live_subscription_blocked_by_cost_guard" in captured.out
    assert "Missing Databento API key" not in captured.out
    assert "live_subscribe" not in captured.out
    assert factory_called is False


def test_run_live_fails_fast_when_client_disconnects_at_startup(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    holder: dict[str, FakeLiveClient] = {}

    def factory(**kwargs: object) -> FakeLiveClient:
        client = FakeLiveClient(connected_after_start=False, **kwargs)
        holder["client"] = client
        return client

    with pytest.raises(RuntimeError, match="not connected after startup"):
        engine.run_live(signal_engine, once=False, max_runtime=1, live_client_factory=factory)

    captured = capsys.readouterr()
    assert "live_subscribe" in captured.out
    assert "live_startup_disconnected" in captured.out
    assert holder["client"].started is True
    assert holder["client"].stopped is True


def test_run_live_reports_subscribe_failure_and_stops_client(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FailingSubscribeClient(FakeLiveClient):
        def subscribe(self, **kwargs: object) -> int:
            self.subscribe_args = kwargs
            raise RuntimeError("subscribe boom")

    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0.25
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    holder: dict[str, FailingSubscribeClient] = {}

    def factory(**kwargs: object) -> FailingSubscribeClient:
        client = FailingSubscribeClient(connected_after_start=True, **kwargs)
        holder["client"] = client
        return client

    with pytest.raises(RuntimeError, match="live subscribe failed"):
        engine.run_live(signal_engine, once=False, max_runtime=1, live_client_factory=factory)

    captured = capsys.readouterr()
    assert "live_subscribe" in captured.out
    assert "live_subscribe_failed" in captured.out
    assert "subscribe boom" in captured.out
    assert holder["client"].started is False
    assert holder["client"].stopped is True
    assert holder["client"].wait_for_close_timeout == 0.25


def test_run_live_reports_start_failure_and_stops_client(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FailingStartClient(FakeLiveClient):
        def start(self) -> None:
            raise RuntimeError("start boom")

    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0.25
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    holder: dict[str, FailingStartClient] = {}

    def factory(**kwargs: object) -> FailingStartClient:
        client = FailingStartClient(connected_after_start=True, **kwargs)
        holder["client"] = client
        return client

    with pytest.raises(RuntimeError, match="live start failed"):
        engine.run_live(signal_engine, once=False, max_runtime=1, live_client_factory=factory)

    captured = capsys.readouterr()
    assert "live_subscribe" in captured.out
    assert "live_start_failed" in captured.out
    assert "start boom" in captured.out
    assert holder["client"].subscribe_args == {
        "dataset": "GLBX.MDP3",
        "schema": "trades",
        "symbols": "ES.FUT",
        "stype_in": "parent",
    }
    assert holder["client"].stopped is True
    assert holder["client"].wait_for_close_timeout == 0.25


def test_run_live_short_run_starts_and_stops_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0.25
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    holder: dict[str, FakeLiveClient] = {}

    def factory(**kwargs: object) -> FakeLiveClient:
        client = FakeLiveClient(connected_after_start=True, **kwargs)
        holder["client"] = client
        return client

    rc = engine.run_live(signal_engine, once=False, max_runtime=0.01, live_client_factory=factory)

    captured = capsys.readouterr()
    assert rc == 0
    assert "live_started" in captured.out
    assert "live_stopped" in captured.out
    assert '"reason": "max_runtime"' in captured.out
    assert '"exit_code": 0' in captured.out
    assert holder["client"].started is True
    assert holder["client"].stopped is True
    assert holder["client"].wait_for_close_timeout == 0.25
    assert holder["client"].subscribe_args == {
        "dataset": "GLBX.MDP3",
        "schema": "trades",
        "symbols": "ES.FUT",
        "stype_in": "parent",
    }


def test_run_live_stop_on_disconnect_returns_failure(capsys: pytest.CaptureFixture[str]) -> None:
    class DisconnectingLiveClient(FakeLiveClient):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(connected_after_start=True, **kwargs)
            self.connection_checks = 0

        def is_connected(self) -> bool:
            self.connection_checks += 1
            return self.connection_checks == 1

    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0.001
    cfg["databento"]["live"]["stop_on_disconnect"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    rc = engine.run_live(
        signal_engine,
        once=False,
        max_runtime=1,
        live_client_factory=lambda **kwargs: DisconnectingLiveClient(**kwargs),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "live_disconnected" in captured.out
    assert '"reason": "live_disconnected"' in captured.out
    assert '"exit_code": 1' in captured.out


def test_run_live_callback_error_emits_system_alert_and_sound(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0
    cfg["engine"]["operator"]["sound"]["enabled"] = True
    cfg["engine"]["operator"]["sound"]["bell"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    records = [
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:31:00"),
            price=5000.0,
            size=1,
            side="B",
            symbol="ESM6",
        )
    ]

    def raise_on_entry_tick(_: engine.TradeTick) -> None:
        raise RuntimeError("entry tick boom")

    signal_engine.on_entry_tick = raise_on_entry_tick  # type: ignore[method-assign]

    rc = engine.run_live(
        signal_engine,
        once=False,
        max_runtime=1,
        live_client_factory=lambda **kwargs: FakeLiveClient(
            connected_after_start=True,
            records=records,
            record_delay_seconds=0.01,
            **kwargs,
        ),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "SYSTEM_ALERT" in captured.out
    assert "live_callback_error" in captured.out
    assert "entry tick boom" in captured.out
    assert '"reason": "live_callback_error"' in captured.out
    assert '"exit_code": 1' in captured.out
    assert signal_engine.operator_sound_health.attempts == 1
    assert signal_engine.operator_sound_health.last_kind == "system"


def test_run_live_exception_callback_emits_system_alert_and_sound(
    capsys: pytest.CaptureFixture[str],
) -> None:
    class ExceptionCallbackClient(FakeLiveClient):
        def start(self) -> None:
            self.started = True
            thread = threading.Thread(target=self._emit_exception, daemon=True)
            thread.start()

        def _emit_exception(self) -> None:
            time.sleep(0.01)
            for callback in list(self.exception_callbacks):
                callback(RuntimeError("stream boom"))

    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0
    cfg["engine"]["operator"]["sound"]["enabled"] = True
    cfg["engine"]["operator"]["sound"]["bell"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    rc = engine.run_live(
        signal_engine,
        once=False,
        max_runtime=1,
        live_client_factory=lambda **kwargs: ExceptionCallbackClient(connected_after_start=True, **kwargs),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "SYSTEM_ALERT" in captured.out
    assert "live_exception" in captured.out
    assert "stream boom" in captured.out
    assert '"reason": "live_exception"' in captured.out
    assert '"exit_code": 1' in captured.out
    assert signal_engine.operator_sound_health.attempts == 1
    assert signal_engine.operator_sound_health.last_kind == "system"


def test_run_live_stop_on_no_records_returns_failure(capsys: pytest.CaptureFixture[str]) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0.001
    cfg["databento"]["live"]["no_records_alert_seconds"] = 0.001
    cfg["databento"]["live"]["no_trade_ticks_alert_seconds"] = 0
    cfg["databento"]["live"]["no_completed_bar_alert_seconds"] = 0
    cfg["databento"]["live"]["session_aware_stale_alerts"] = False
    cfg["databento"]["live"]["stop_on_no_records"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    rc = engine.run_live(
        signal_engine,
        once=False,
        max_runtime=1,
        live_client_factory=lambda **kwargs: FakeLiveClient(connected_after_start=True, **kwargs),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "live_no_records_received" in captured.out
    assert '"reason": "live_no_records_received"' in captured.out
    assert '"exit_code": 1' in captured.out


def test_run_live_state_lock_timeout_returns_failure(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0.001
    cfg["databento"]["live"]["state_lock_timeout_seconds"] = 0.01
    cfg["databento"]["live"]["stop_on_state_lock_timeout"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    records = [
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:31:00"),
            price=5000.0,
            size=1,
            side="B",
            symbol="ESM6",
        )
    ]

    original_update = engine.TradeBarBuilder.update

    def slow_update(builder: engine.TradeBarBuilder, tick: engine.TradeTick) -> list[engine.SourceMinuteBar]:
        time.sleep(0.75)
        return original_update(builder, tick)

    monkeypatch.setattr(engine.TradeBarBuilder, "update", slow_update)

    rc = engine.run_live(
        signal_engine,
        once=False,
        max_runtime=2,
        live_client_factory=lambda **kwargs: FakeLiveClient(
            connected_after_start=True,
            records=records,
            record_delay_seconds=0.01,
            **kwargs,
        ),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "live_state_lock_timeout" in captured.out
    assert '"reason": "live_state_lock_timeout"' in captured.out
    assert '"exit_code": 1' in captured.out


def test_run_live_restores_process_signal_handlers() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    original_sigint = signal.getsignal(signal.SIGINT)
    original_sigterm = signal.getsignal(signal.SIGTERM)

    rc = engine.run_live(
        signal_engine,
        once=False,
        max_runtime=0.01,
        live_client_factory=lambda **kwargs: FakeLiveClient(connected_after_start=True, **kwargs),
    )

    assert rc == 0
    assert signal.getsignal(signal.SIGINT) == original_sigint
    assert signal.getsignal(signal.SIGTERM) == original_sigterm


def test_run_live_drops_first_partial_minute_for_all_contracts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["databento"]["active_contract_mode"] = "emit_all"
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["execution_intents"]["enabled"] = False
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0
    cfg["databento"]["live"]["drop_partial_first_live_bar"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    records = [
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:30:05"),
            price=5000.0,
            size=10,
            side="B",
            symbol="ESM6",
        ),
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:30:06"),
            price=5001.0,
            size=20,
            side="A",
            symbol="ESU6",
        ),
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:31:00"),
            price=5000.25,
            size=1,
            side="B",
            symbol="ESM6",
        ),
    ]

    def factory(**kwargs: object) -> FakeLiveClient:
        return FakeLiveClient(
            connected_after_start=True,
            records=records,
            record_delay_seconds=0.01,
            **kwargs,
        )

    rc = engine.run_live(signal_engine, once=False, max_runtime=0.1, live_client_factory=factory)

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.count('"event": "live_partial_first_bar_dropped"') == 2
    assert '"drop_scope": "first_completed_minute"' in captured.out
    assert '"first_dropped_minute_utc": "2026-06-11T13:30:00+00:00"' in captured.out
    assert '"dropped_partial_bars": 2' in captured.out
    assert '"completed_source_bars": 0' in captured.out
    assert signal_engine.store.bars() == []
    assert signal_engine.alert_count == 0


def test_run_live_ignores_unmatched_contract_tick_as_entry_trigger(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["execution_intents"]["enabled"] = False
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0
    cfg["databento"]["live"]["stop_on_unmatched_contract_symbol"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]
    pending = engine.PendingSignal(
        strategy=strategy,
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6",
        },
        signal_obj=engine.EngineSignal(direction="long", level_type="test"),
        due_utc=ts("2026-06-11 13:31:00"),
        queued_at_utc=ts("2026-06-11 13:30:01"),
        key="pending-unmatched-live",
    )
    signal_engine.pending.append(pending)
    records = [
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:31:00"),
            price=5000.0,
            size=1,
            side="B",
            symbol="ESM6-ESU6",
        )
    ]

    def factory(**kwargs: object) -> FakeLiveClient:
        return FakeLiveClient(
            connected_after_start=True,
            records=records,
            record_delay_seconds=0.01,
            **kwargs,
        )

    rc = engine.run_live(signal_engine, once=False, max_runtime=0.1, live_client_factory=factory)

    captured = capsys.readouterr()
    assert rc == 0
    assert "live_unmatched_contract_symbol_ignored" in captured.out
    assert "ENTRY_SIGNAL" not in captured.out
    assert signal_engine.alert_count == 0
    assert signal_engine.pending == [pending]


def test_run_live_stop_on_unmatched_contract_symbol_returns_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
    allow_test_live_subscription(cfg)
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["execution_intents"]["enabled"] = False
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0
    cfg["databento"]["live"]["stop_on_unmatched_contract_symbol"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    records = [
        FakeTradeRecord(
            timestamp=ts("2026-06-11 13:31:00"),
            price=5000.0,
            size=1,
            side="B",
            symbol="ESM6-ESU6",
        )
    ]

    rc = engine.run_live(
        signal_engine,
        once=False,
        max_runtime=1,
        live_client_factory=lambda **kwargs: FakeLiveClient(
            connected_after_start=True,
            records=records,
            record_delay_seconds=0.01,
            **kwargs,
        ),
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "live_unmatched_contract_symbol_ignored" in captured.out
    assert '"reason": "unmatched_contract_symbol"' in captured.out
    assert '"exit_code": 1' in captured.out
    assert "ENTRY_SIGNAL" not in captured.out
    assert signal_engine.alert_count == 0


def test_stop_live_client_awaits_async_wait_for_close() -> None:
    class AsyncWaitClient:
        def __init__(self) -> None:
            self.stopped = False
            self.waited = False
            self.timeout: float | None = None

        def stop(self) -> None:
            self.stopped = True

        async def wait_for_close(self, timeout: float | None = None) -> None:
            self.waited = True
            self.timeout = timeout

    client = AsyncWaitClient()

    report = engine.stop_live_client(client, shutdown_grace_seconds=0.25)

    assert client.stopped is True
    assert client.waited is True
    assert client.timeout == 0.25
    assert report["client_close_method"] == "wait_for_close"
    assert report["client_wait_error_type"] is None


def test_preflight_rejects_duplicate_strategy_ids() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["strategies"] = [copy.deepcopy(cfg["strategies"][0]), copy.deepcopy(cfg["strategies"][0])]

    with pytest.raises(ValueError, match="strategy ids must be unique"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_invalid_account_contract_bounds() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["account"]["min_contracts"] = 3
    cfg["engine"]["account"]["max_contracts"] = 2

    with pytest.raises(ValueError, match="max_contracts must be >= min_contracts"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_unsupported_strategy_position_sizing_mode() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["strategies"][0]["core"]["position_sizing"]["mode"] = "kelly"

    with pytest.raises(ValueError, match="unsupported core.position_sizing.mode"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_invalid_strategy_risk_position_sizing() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["strategies"][0]["core"]["position_sizing"] = {
        "mode": "risk_percent_net_liq",
        "risk_fraction": 0,
    }

    with pytest.raises(ValueError, match="risk_fraction must be >="):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_invalid_trade_sanity_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["trade_sanity"]["enabled"] = "true"

    with pytest.raises(ValueError, match="trade_sanity.*enabled must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["data_quality"]["enabled"] = "false"

    with pytest.raises(ValueError, match="enabled must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_negative_live_maintenance_interval() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["live"]["maintenance_interval_seconds"] = -1

    with pytest.raises(ValueError, match="maintenance_interval_seconds must be >= 0"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_negative_live_state_lock_timeout() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["live"]["state_lock_timeout_seconds"] = -1

    with pytest.raises(ValueError, match="state_lock_timeout_seconds must be >= 0"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_live_health_stop_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["live"]["stop_on_no_records"] = "true"

    with pytest.raises(ValueError, match="stop_on_no_records must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_enabled_execution_intents_without_path() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["execution_intents"] = {"enabled": True}

    with pytest.raises(ValueError, match="execution_intents.path must be configured"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_execution_intent_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["execution_intents"]["enabled"] = "true"

    with pytest.raises(ValueError, match="enabled must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_execution_intent_setup_duplicate_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["execution_intents"]["suppress_duplicate_setup_ids"] = "true"

    with pytest.raises(ValueError, match="suppress_duplicate_setup_ids must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_invalid_execution_intent_ttl() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["execution_intents"]["intent_ttl_seconds"] = 0

    with pytest.raises(ValueError, match="intent_ttl_seconds must be >="):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_invalid_execution_intent_freshness_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["execution_intents"]["freshness_grace_seconds"] = -1

    with pytest.raises(ValueError, match="freshness_grace_seconds must be >="):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_enabled_setup_alerts_without_path() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["setup_alerts"] = {"enabled": True}

    with pytest.raises(ValueError, match="setup_alerts.path must be configured"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_setup_alerts_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["setup_alerts"]["enabled"] = "true"

    with pytest.raises(ValueError, match="enabled must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_output_path_readiness_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["output_path_readiness"]["enabled"] = "true"

    with pytest.raises(ValueError, match="output_path_readiness.*enabled must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_console_debug_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["console"]["debug"] = "true"

    with pytest.raises(ValueError, match="engine.console.*debug must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_console_live_stream_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["console"]["live_stream"] = {"enabled": "true"}

    with pytest.raises(ValueError, match="engine.console.*enabled must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_operator_sound_cleanup_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["operator"]["sound"]["cleanup_on_exit"] = "true"

    with pytest.raises(ValueError, match="cleanup_on_exit must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_operator_sound_fail_on_error_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["operator"]["sound"]["fail_on_error"] = "true"

    with pytest.raises(ValueError, match="fail_on_error must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_invalid_operator_sound_active_command_limit() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["operator"]["sound"]["max_active_commands"] = -1

    with pytest.raises(ValueError, match="max_active_commands must be >="):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_historical_cache_metadata_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_metadata": {"enabled": "true"},
    }

    with pytest.raises(ValueError, match="enabled must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_historical_cache_metadata_string_staleness_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_metadata": {"max_staleness_days": "7"},
    }

    with pytest.raises(ValueError, match="max_staleness_days must be numeric"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_current_session_backfill_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "current_session_backfill": {"enabled": "true"},
    }

    with pytest.raises(ValueError, match="enabled must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_pre_trade_warning_string_boolean_config() -> None:
    cfg = load_execution_config("morning_orderflow_momentum_signal_engine.example.yaml")
    strategy_cfg = engine.load_yaml(
        EXECUTION_DIR / "strategies/morning_orderflow_momentum_two_sided_signed_flow_continuation_live.yaml"
    )
    strategy_cfg["strategy"]["entry"]["params"]["pre_trade_warning"]["enabled"] = "true"
    temp_path = EXECUTION_DIR / "strategies/__tmp_invalid_warning.yaml"
    try:
        temp_path.write_text(json.dumps(strategy_cfg), encoding="utf-8")
        cfg["strategies"][0]["config"] = "strategies/__tmp_invalid_warning.yaml"
        with pytest.raises(ValueError, match="pre_trade_warning.*enabled must be a YAML boolean"):
            engine.SignalEngine(cfg, EXECUTION_DIR / "morning_orderflow_momentum_signal_engine.example.yaml")
    finally:
        temp_path.unlink(missing_ok=True)


def test_preflight_rejects_enabled_process_lock_without_path() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["process_lock"] = {"enabled": True}

    with pytest.raises(ValueError, match="process_lock.path must be configured"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_process_lock_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["process_lock"]["enabled"] = "true"

    with pytest.raises(ValueError, match="enabled must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_process_lock_acquire_and_release(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    lock_path = tmp_path / "signal_engine.lock"
    cfg["engine"]["process_lock"] = {
        "enabled": True,
        "path": str(lock_path),
        "stale_after_seconds": 86400,
        "fail_if_locked": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.acquire_process_lock()

    assert signal_engine.process_lock_acquired is True
    assert lock_path.exists()
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    assert payload["pid"] == os.getpid()
    assert payload["config"] == str(EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.release_process_lock()

    assert signal_engine.process_lock_acquired is False
    assert not lock_path.exists()


def test_process_lock_refuses_active_existing_lock(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    lock_path = tmp_path / "signal_engine.lock"
    lock_path.write_text(json.dumps({"token": "other", "pid": os.getpid()}) + "\n", encoding="utf-8")
    cfg["engine"]["process_lock"] = {
        "enabled": True,
        "path": str(lock_path),
        "stale_after_seconds": 86400,
        "fail_if_locked": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="process lock is already held"):
        signal_engine.acquire_process_lock()

    assert signal_engine.process_lock_acquired is False
    assert json.loads(lock_path.read_text(encoding="utf-8"))["token"] == "other"


def test_process_lock_replaces_stale_dead_pid_lock(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    lock_path = tmp_path / "signal_engine.lock"
    lock_path.write_text(json.dumps({"token": "old", "pid": 999999999}) + "\n", encoding="utf-8")
    cfg["engine"]["process_lock"] = {
        "enabled": True,
        "path": str(lock_path),
        "stale_after_seconds": 86400,
        "fail_if_locked": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.acquire_process_lock()

    captured = capsys.readouterr()
    assert "stale_process_lock_replaced" in captured.out
    assert signal_engine.process_lock_acquired is True
    assert json.loads(lock_path.read_text(encoding="utf-8"))["pid"] == os.getpid()
    signal_engine.release_process_lock()


def test_entry_readout_contains_manual_trade_fields() -> None:
    readout = engine.format_entry_alert_readout(sample_entry_alert())

    assert "ENTRY SIGNAL - TAKE TRADE NOW" in readout
    assert "LONG / BUY" in readout
    assert "Quantity : 2 contract(s)" in readout
    assert "Order    : MARKET (estimated market)" in readout
    assert "Entry    : 5,000.25" in readout
    assert "Stop     : 4,999.25" in readout
    assert "Target   : 5,001.25" in readout
    assert "Expires  : 2026-06-11T13:33:00+00:00 (120s TTL)" in readout
    assert "R/R      : 1R" in readout


def test_rejection_readout_contains_debug_fields() -> None:
    readout = engine.format_rejection_readout(
        {
            "strategy_id": "dummy",
            "timestamp": "2026-06-11T09:30:00-04:00",
            "session_date": "2026-06-11",
            "reason": "pending entry expired",
            "due_timestamp_utc": "2026-06-11T13:31:00+00:00",
            "checked_timestamp_utc": "2026-06-11T13:33:01+00:00",
            "signal": {"direction": "long", "metadata": {"delta": 42}},
        }
    )

    assert "SIGNAL REJECTED" in readout
    assert "Strategy : dummy" in readout
    assert "Reason   : pending entry expired" in readout
    assert "Direction: LONG" in readout
    assert "Due UTC  : 2026-06-11T13:31:00+00:00" in readout
    assert "Delta    : 42" in readout


def test_entry_alert_contract_and_execution_intent_are_valid() -> None:
    alert = sample_entry_alert()

    engine.validate_entry_alert_contract(alert)

    intent = alert["execution_intent"]
    assert engine.ALERT_CONTRACT_VERSION == "entry_signal.v5"
    assert alert["alert_contract_version"] == engine.ALERT_CONTRACT_VERSION
    assert alert["setup_id"] == "setup-abc"
    assert alert["pending_signal_key"] == "pending-abc"
    assert alert["strategy_config_fingerprint"]["schema_version"] == engine.CONFIG_FINGERPRINT_VERSION
    assert alert["strategy_config_fingerprint"]["path"] == alert["strategy_config"]
    assert len(alert["strategy_config_fingerprint"]["sha256"]) == 64
    assert alert["engine_config_fingerprint"]["schema_version"] == engine.CONFIG_FINGERPRINT_VERSION
    assert alert["engine_config_fingerprint"]["path"] == alert["engine_config"]
    assert len(alert["engine_config_fingerprint"]["sha256"]) == 64
    assert engine.EXECUTION_INTENT_VERSION == "execution_intent.v5"
    assert intent["schema_version"] == engine.EXECUTION_INTENT_VERSION
    assert intent["intent_id"] == alert["alert_id"]
    assert intent["intent_type"] == "entry"
    assert intent["status"] == "ready_for_manual_or_future_router"
    assert intent["order"]["estimated_entry_price"] == alert["entry_price"]
    assert intent["bracket"]["stop_loss_price"] == alert["stop_loss_price"]
    assert intent["bracket"]["take_profit_price"] == alert["take_profit_price"]
    assert intent["risk"]["risk_dollars"] == alert["risk_dollars"]
    assert intent["price_normalization"] == alert["price_normalization"]
    assert intent["timing"]["valid_from_utc"] == alert["entry_timestamp_utc"]
    assert intent["timing"]["expires_at_utc"] == "2026-06-11T13:33:00+00:00"
    assert intent["timing"]["intent_ttl_seconds"] == 120.0
    assert intent["source"]["setup_id"] == alert["setup_id"]
    assert intent["source"]["pending_signal_key"] == alert["pending_signal_key"]
    assert intent["source"]["strategy_config_fingerprint"] == alert["strategy_config_fingerprint"]
    assert intent["source"]["engine_config"] == alert["engine_config"]
    assert intent["source"]["engine_config_fingerprint"] == alert["engine_config_fingerprint"]
    assert alert["price_normalization"]["normalized"] is False


def test_setup_notice_contract_is_valid_and_non_executable() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    pending = sample_pending_setup(signal_engine.strategies[0])

    notice = pending.strategy.build_setup_notice(pending)

    engine.validate_setup_notice_contract(notice)
    assert notice["setup_contract_version"] == engine.SETUP_NOTICE_CONTRACT_VERSION
    assert notice["strategy_config_fingerprint"]["schema_version"] == engine.CONFIG_FINGERPRINT_VERSION
    assert notice["strategy_config_fingerprint"]["path"] == notice["strategy_config"]
    assert len(notice["strategy_config_fingerprint"]["sha256"]) == 64
    assert notice["engine_config"] == str(EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    assert notice["engine_config_fingerprint"]["schema_version"] == engine.CONFIG_FINGERPRINT_VERSION
    assert notice["engine_config_fingerprint"]["path"] == notice["engine_config"]
    assert len(notice["engine_config_fingerprint"]["sha256"]) == 64
    assert notice["event"] == "trade_setup"
    assert notice["setup_id"]
    assert notice["direction"] == "long"
    assert notice["side"] == "buy"
    assert notice["due_timestamp_utc"] == "2026-06-11T13:31:00+00:00"
    assert notice["expires_at_utc"] == "2026-06-11T13:33:00+00:00"
    assert notice["entry_window"] == {
        "entry_trigger": "first_matching_trade_tick_at_or_after_due_timestamp",
        "valid_from_utc": "2026-06-11T13:31:00+00:00",
        "expires_at_utc": "2026-06-11T13:33:00+00:00",
        "max_entry_lag_seconds": 120.0,
    }
    preview = notice["trade_plan_preview"]
    assert preview["schema_version"] == "trade_plan_preview.v1"
    assert preview["status"] == "estimated"
    assert preview["executable"] is False
    assert preview["entry_price_basis"] == "latest_completed_bar_close"
    assert preview["entry_price_type"] == "estimated_market_at_completed_bar_close"
    assert preview["estimated_entry_basis_price"] == 5000.25
    assert preview["estimated_entry_price"] == 5000.25
    assert preview["stop_loss_price"] == 4999.25
    assert preview["take_profit_price"] == 5001.25
    assert preview["stop_loss_points"] == 1.0
    assert preview["take_profit_points"] == 1.0
    assert preview["quantity"] == 1
    assert preview["risk_dollars"] == 50.0
    assert preview["reward_dollars"] == 50.0
    assert "entry_price" not in notice
    assert "execution_intent" not in notice


def test_setup_notice_readout_includes_entry_window() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    notice = signal_engine.build_validated_setup_notice(sample_pending_setup(signal_engine.strategies[0]))

    readout = engine.format_setup_readout(notice)

    assert "TRADE SETUP" in readout
    assert "Status   : PREP ONLY - WAIT FOR ENTRY TRIGGER" in readout
    assert "Due UTC  : 2026-06-11T13:31:00+00:00" in readout
    assert "Expires  : 2026-06-11T13:33:00+00:00" in readout
    assert "Entry    : first matching trade tick at or after due timestamp" in readout
    assert "Window   : 120s after due time" in readout
    assert "Plan     : ESTIMATE ONLY - final entry waits for trigger" in readout
    assert "Est entry: 5,000.25" in readout
    assert "Est stop : 4,999.25" in readout
    assert "Est tgt  : 5,001.25" in readout
    assert "Est qty  : 1 contract(s)" in readout
    assert "Est R/R  : $50 / $50" in readout


def test_setup_notice_preview_can_report_unavailable_without_blocking_setup() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    pending = sample_pending_setup(signal_engine.strategies[0])
    pending.row.pop("close")

    notice = signal_engine.build_validated_setup_notice(pending)
    readout = engine.format_setup_readout(notice)

    assert notice["trade_plan_preview"]["status"] == "unavailable"
    assert notice["trade_plan_preview"]["executable"] is False
    assert notice["trade_plan_preview"]["reason"] == "completed strategy row has no finite close price"
    assert "Plan     : unavailable - completed strategy row has no finite close price" in readout


def test_setup_notice_id_is_namespaced_away_from_entry_alert_id() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    pending = sample_pending_setup(signal_engine.strategies[0])
    notice = pending.strategy.build_setup_notice(pending)
    tick = engine.TradeTick(
        timestamp_utc=pending.due_utc,
        price=5000.25,
        size=1,
        side="B",
        contract_symbol="ESM6",
    )

    alert = pending.strategy.build_alert(pending, tick, signal_engine.account)

    assert alert is not None
    assert notice["setup_id"] != alert["alert_id"]
    assert alert["setup_id"] == notice["setup_id"]
    assert alert["pending_signal_key"] == notice["pending_signal_key"]
    assert alert["execution_intent"]["source"]["setup_id"] == notice["setup_id"]
    assert alert["execution_intent"]["source"]["pending_signal_key"] == notice["pending_signal_key"]
    assert alert["execution_intent"]["timing"]["intent_ttl_seconds"] == 30.0
    assert alert["execution_intent"]["timing"]["valid_from_utc"] == "2026-06-11T13:31:00+00:00"
    assert alert["execution_intent"]["timing"]["expires_at_utc"] == "2026-06-11T13:31:30+00:00"
    engine.validate_setup_notice_contract(notice)
    engine.validate_entry_alert_contract(alert)


def test_entry_alert_contract_rejects_malformed_intent() -> None:
    alert = sample_entry_alert()
    alert["execution_intent"]["quantity"] = 99

    with pytest.raises(ValueError, match="execution_intent.risk.risk_dollars must match"):
        engine.validate_entry_alert_contract(alert)


def test_entry_alert_contract_rejects_intent_missing_router_payload_field() -> None:
    alert = sample_entry_alert()
    alert["execution_intent"].pop("status")

    with pytest.raises(ValueError, match="execution_intent missing required field"):
        engine.validate_entry_alert_contract(alert)


def test_entry_alert_contract_rejects_mismatched_config_fingerprint() -> None:
    alert = sample_entry_alert()
    alert["execution_intent"]["source"]["strategy_config_fingerprint"] = engine.config_fingerprint_payload(
        {"strategy_id": "other"},
        kind="test_strategy",
        path=alert["strategy_config"],
    )

    with pytest.raises(ValueError, match="strategy_config_fingerprint must match alert"):
        engine.validate_entry_alert_contract(alert)


def test_entry_alert_contract_rejects_mismatched_engine_config_fingerprint() -> None:
    alert = sample_entry_alert()
    alert["execution_intent"]["source"]["engine_config_fingerprint"] = engine.config_fingerprint_payload(
        {"engine": {"symbol": "NQ"}},
        kind="test_engine",
        path=alert["engine_config"],
    )

    with pytest.raises(ValueError, match="engine_config_fingerprint must match alert"):
        engine.validate_entry_alert_contract(alert)


def test_entry_alert_contract_rejects_mismatched_setup_link() -> None:
    alert = sample_entry_alert()
    alert["execution_intent"]["source"]["setup_id"] = "different-setup"

    with pytest.raises(ValueError, match="source.setup_id must match alert"):
        engine.validate_entry_alert_contract(alert)


def test_entry_alert_contract_rejects_malformed_intent_expiry() -> None:
    alert = sample_entry_alert()
    alert["execution_intent"]["timing"]["expires_at_utc"] = alert["entry_timestamp_utc"]

    with pytest.raises(ValueError, match="expires_at_utc must be after"):
        engine.validate_entry_alert_contract(alert)


def test_entry_alert_contract_rejects_off_tick_executable_price() -> None:
    alert = sample_entry_alert()
    alert["entry_price"] = 5000.10
    alert["execution_intent"] = engine.build_execution_intent(alert, max_entry_lag_seconds=120)

    with pytest.raises(ValueError, match="entry_price.*tick grid"):
        engine.validate_entry_alert_contract(alert)


def test_entry_alert_contract_rejects_risk_that_does_not_match_executable_prices() -> None:
    alert = sample_entry_alert()
    alert["risk_dollars"] = 99.0
    alert["execution_intent"] = engine.build_execution_intent(alert, max_entry_lag_seconds=120)

    with pytest.raises(ValueError, match="risk_dollars must match executable stop distance"):
        engine.validate_entry_alert_contract(alert)


def test_strategy_alert_normalizes_prices_and_sizes_from_executable_stop_distance() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy_runtime = signal_engine.strategies[0]
    strategy_runtime.strategy.stop_price = lambda *args, **kwargs: 4999.37  # type: ignore[method-assign]
    strategy_runtime.strategy.target_price = lambda *args, **kwargs: 5001.12  # type: ignore[method-assign]
    pending = engine.PendingSignal(
        strategy=strategy_runtime,
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6",
        },
        signal_obj=engine.EngineSignal(direction="long", level_type="test"),
        due_utc=ts("2026-06-11 13:31:00"),
        queued_at_utc=ts("2026-06-11 13:30:01"),
        key="normalize-test",
    )
    tick = engine.TradeTick(
        timestamp_utc=ts("2026-06-11 13:31:00"),
        price=5000.01,
        size=1,
        side="B",
        contract_symbol="ESM6",
    )

    alert = strategy_runtime.build_alert(pending, tick, signal_engine.account)

    assert alert is not None
    assert alert["entry_basis_price"] == 5000.0
    assert alert["entry_price"] == 5000.0
    assert alert["stop_loss_price"] == 4999.25
    assert alert["take_profit_price"] == 5001.0
    assert alert["stop_loss_points"] == 0.75
    assert alert["take_profit_points"] == 1.0
    assert alert["risk_dollars"] == 37.5
    assert alert["reward_dollars"] == 50.0
    assert alert["price_normalization"]["normalized"] is True
    engine.validate_entry_alert_contract(alert)


def test_strategy_alert_uses_configured_risk_percent_position_sizing() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["account"]["net_liq"] = 150000
    cfg["engine"]["account"]["max_contracts"] = 10
    cfg["strategies"][0]["core"]["position_sizing"] = {
        "mode": "risk_percent_net_liq",
        "risk_fraction": 0.001,
        "rounding": "floor",
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy_runtime = signal_engine.strategies[0]
    strategy_runtime.strategy.stop_price = lambda *args, **kwargs: 4999.0  # type: ignore[method-assign]
    strategy_runtime.strategy.target_price = lambda *args, **kwargs: 5001.0  # type: ignore[method-assign]
    pending = engine.PendingSignal(
        strategy=strategy_runtime,
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6",
        },
        signal_obj=engine.EngineSignal(direction="long", level_type="test"),
        due_utc=ts("2026-06-11 13:31:00"),
        queued_at_utc=ts("2026-06-11 13:30:01"),
        key="risk-sizing-test",
    )
    tick = engine.TradeTick(
        timestamp_utc=ts("2026-06-11 13:31:00"),
        price=5000.0,
        size=1,
        side="B",
        contract_symbol="ESM6",
    )

    alert = strategy_runtime.build_alert(pending, tick, signal_engine.account)

    assert alert is not None
    assert alert["quantity"] == 3
    assert alert["suggested_quantity"] == 3
    assert alert["risk_dollars"] == 150.0
    assert alert["reward_dollars"] == 150.0
    assert alert["sizing"]["position_sizing_mode"] == "risk_percent_net_liq"
    assert alert["sizing"]["target_risk_amount"] == 150.0
    assert alert["sizing"]["dollar_risk_per_contract"] == 50.0
    assert alert["sizing"]["planned_dollar_risk"] == 150.0
    engine.validate_entry_alert_contract(alert)


def test_strategy_alert_rejects_trade_sanity_stop_distance_violation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["trade_sanity"] = {
        "enabled": True,
        "max_stop_points": 5,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy_runtime = signal_engine.strategies[0]
    strategy_runtime.strategy.stop_price = lambda *args, **kwargs: 4980.0  # type: ignore[method-assign]
    strategy_runtime.strategy.target_price = lambda *args, **kwargs: 5020.0  # type: ignore[method-assign]
    pending = engine.PendingSignal(
        strategy=strategy_runtime,
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6",
        },
        signal_obj=engine.EngineSignal(direction="long", level_type="test"),
        due_utc=ts("2026-06-11 13:31:00"),
        queued_at_utc=ts("2026-06-11 13:30:01"),
        key="trade-sanity-stop-test",
    )
    tick = engine.TradeTick(
        timestamp_utc=ts("2026-06-11 13:31:00"),
        price=5000.0,
        size=1,
        side="B",
        contract_symbol="ESM6",
    )

    alert = strategy_runtime.build_alert(pending, tick, signal_engine.account)

    captured = capsys.readouterr()
    assert alert is None
    assert "SIGNAL_REJECTED" in captured.out
    assert "trade_sanity max_stop_points exceeded" in captured.out
    assert "ENTRY_SIGNAL" not in captured.out
    assert strategy_runtime.sent_signal_keys == set()
    assert strategy_runtime.trades_by_session == {}


def test_strategy_alert_allows_trade_sanity_when_disabled() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["trade_sanity"] = {
        "enabled": False,
        "max_stop_points": 5,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy_runtime = signal_engine.strategies[0]
    strategy_runtime.strategy.stop_price = lambda *args, **kwargs: 4980.0  # type: ignore[method-assign]
    strategy_runtime.strategy.target_price = lambda *args, **kwargs: 5020.0  # type: ignore[method-assign]
    pending = engine.PendingSignal(
        strategy=strategy_runtime,
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6",
        },
        signal_obj=engine.EngineSignal(direction="long", level_type="test"),
        due_utc=ts("2026-06-11 13:31:00"),
        queued_at_utc=ts("2026-06-11 13:30:01"),
        key="trade-sanity-disabled-test",
    )

    alert = strategy_runtime.build_alert(
        pending,
        engine.TradeTick(ts("2026-06-11 13:31:00"), 5000.0, 1, "B", "ESM6"),
        signal_engine.account,
    )

    assert alert is not None
    assert alert["stop_loss_points"] == 20.0
    engine.validate_entry_alert_contract(alert)


def test_execution_intent_record_contract_is_valid() -> None:
    alert = sample_entry_alert()

    record = engine.build_execution_intent_record(alert)
    engine.validate_execution_intent_record(record, alert)

    assert record["event"] == "execution_intent_ready"
    assert record["record_schema_version"] == engine.EXECUTION_INTENT_RECORD_VERSION
    assert record["alert_id"] == alert["alert_id"]
    assert record["setup_id"] == alert["setup_id"]
    assert record["pending_signal_key"] == alert["pending_signal_key"]
    assert record["strategy_config_fingerprint"] == alert["strategy_config_fingerprint"]
    assert record["engine_config"] == alert["engine_config"]
    assert record["engine_config_fingerprint"] == alert["engine_config_fingerprint"]
    assert record["execution_intent"]["intent_id"] == alert["alert_id"]
    assert record["execution_intent"]["source"]["setup_id"] == alert["setup_id"]
    assert record["execution_intent"]["source"]["pending_signal_key"] == alert["pending_signal_key"]
    assert record["execution_intent"]["source"]["strategy_config_fingerprint"] == alert["strategy_config_fingerprint"]
    assert record["execution_intent"]["source"]["engine_config_fingerprint"] == alert["engine_config_fingerprint"]


def test_execution_intent_record_rejects_mismatched_alert() -> None:
    alert = sample_entry_alert()
    record = engine.build_execution_intent_record(alert)
    record["alert_id"] = "different"

    with pytest.raises(ValueError, match="alert_id must match alert"):
        engine.validate_execution_intent_record(record, alert)


def test_execution_intent_ready_record_is_valid_without_full_alert() -> None:
    alert = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:00+00:00",
        intent_ttl_seconds=30.0,
    )
    record = engine.build_execution_intent_record(alert)

    engine.validate_execution_intent_ready_record(record)
    report = engine.execution_intent_record_actionability_report(
        record,
        now_utc="2026-06-11T13:31:05+00:00",
    )

    assert report["actionable"] is True
    assert report["state"] == "ready"
    assert report["alert_id"] == alert["alert_id"]
    assert report["freshness"]["state"] == "fresh"


def test_execution_intent_ready_record_rejects_old_record_schema() -> None:
    alert = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:00+00:00",
        intent_ttl_seconds=30.0,
    )
    record = engine.build_execution_intent_record(alert)
    record["record_schema_version"] = "execution_intent_record.v1"

    with pytest.raises(ValueError, match="unsupported execution intent record version"):
        engine.validate_execution_intent_ready_record(record)

    report = engine.execution_intent_record_actionability_report(
        record,
        now_utc="2026-06-11T13:31:05+00:00",
    )
    assert report["actionable"] is False
    assert report["state"] == "invalid_contract"
    assert report["error_type"] == "ValueError"


def test_execution_intent_ready_record_rejects_inconsistent_risk() -> None:
    alert = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:00+00:00",
        intent_ttl_seconds=30.0,
    )
    record = engine.build_execution_intent_record(alert)
    record["execution_intent"]["risk"]["risk_dollars"] = 1.0

    with pytest.raises(ValueError, match="risk_dollars must match"):
        engine.validate_execution_intent_ready_record(record)


def test_load_actionable_execution_intents_filters_non_actionable_records(tmp_path: Path) -> None:
    path = tmp_path / "execution_intents.jsonl"
    fresh = engine.build_execution_intent_record(
        sample_entry_alert_with_entry_timestamp(
            "2026-06-11T13:31:00+00:00",
            intent_ttl_seconds=30.0,
        )
    )
    expired = engine.build_execution_intent_record(
        sample_entry_alert_with_entry_timestamp(
            "2026-06-11T13:30:00+00:00",
            intent_ttl_seconds=30.0,
        )
    )
    old_schema = copy.deepcopy(fresh)
    old_schema["alert_id"] = "old-schema"
    old_schema["execution_intent"]["intent_id"] = "old-schema"
    old_schema["record_schema_version"] = "execution_intent_record.v1"
    path.write_text(
        "\n".join(
            [
                json.dumps(fresh),
                json.dumps(expired),
                json.dumps(old_schema),
                "{not-json",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = engine.load_actionable_execution_intents(
        path,
        now_utc="2026-06-11T13:31:05+00:00",
    )

    assert result["records_read"] == 4
    assert result["actionable_count"] == 1
    assert result["malformed_count"] == 1
    assert [record["alert_id"] for record in result["records"]] == [fresh["alert_id"]]
    assert {item["state"] for item in result["rejected"]} == {
        "expired",
        "invalid_contract",
        "malformed_json",
    }


def test_load_actionable_execution_intents_dedupes_actionable_alert_ids(tmp_path: Path) -> None:
    path = tmp_path / "execution_intents.jsonl"
    alert = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:00+00:00",
        intent_ttl_seconds=30.0,
    )
    first = engine.build_execution_intent_record(alert)
    duplicate = copy.deepcopy(first)
    duplicate["created_at_utc"] = "2026-06-11T13:31:02+00:00"
    path.write_text(json.dumps(first) + "\n" + json.dumps(duplicate) + "\n", encoding="utf-8")

    result = engine.load_actionable_execution_intents(
        path,
        now_utc="2026-06-11T13:31:05+00:00",
    )

    assert result["records_read"] == 2
    assert result["actionable_count"] == 1
    assert [record["alert_id"] for record in result["records"]] == [first["alert_id"]]
    assert result["rejected_count"] == 1
    assert result["duplicate_alert_id_count"] == 1
    assert result["duplicate_setup_id_count"] == 0
    assert result["rejected"][0]["state"] == "duplicate_alert_id"
    assert result["rejected"][0]["line_number"] == 2
    assert result["rejected"][0]["first_line_number"] == 1


def test_load_actionable_execution_intents_dedupes_actionable_setup_ids(tmp_path: Path) -> None:
    path = tmp_path / "execution_intents.jsonl"
    alert = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:00+00:00",
        intent_ttl_seconds=30.0,
    )
    first = engine.build_execution_intent_record(alert)
    duplicate_setup = copy.deepcopy(first)
    duplicate_setup["alert_id"] = "second-alert-same-setup"
    duplicate_setup["execution_intent"]["intent_id"] = "second-alert-same-setup"
    duplicate_setup["created_at_utc"] = "2026-06-11T13:31:02+00:00"
    path.write_text(json.dumps(first) + "\n" + json.dumps(duplicate_setup) + "\n", encoding="utf-8")

    result = engine.load_actionable_execution_intents(
        path,
        now_utc="2026-06-11T13:31:05+00:00",
    )

    assert result["records_read"] == 2
    assert result["actionable_count"] == 1
    assert [record["alert_id"] for record in result["records"]] == [first["alert_id"]]
    assert result["rejected_count"] == 1
    assert result["duplicate_alert_id_count"] == 0
    assert result["duplicate_setup_id_count"] == 1
    assert result["rejected"][0]["state"] == "duplicate_setup_id"
    assert result["rejected"][0]["line_number"] == 2
    assert result["rejected"][0]["first_line_number"] == 1


def test_load_actionable_execution_intents_can_fail_fast_on_duplicate_actionable_alert_id(
    tmp_path: Path,
) -> None:
    path = tmp_path / "execution_intents.jsonl"
    alert = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:00+00:00",
        intent_ttl_seconds=30.0,
    )
    record = engine.build_execution_intent_record(alert)
    path.write_text(json.dumps(record) + "\n" + json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Duplicate actionable execution-intent alert_id"):
        engine.load_actionable_execution_intents(
            path,
            now_utc="2026-06-11T13:31:05+00:00",
            fail_on_error=True,
        )


def test_load_actionable_execution_intents_can_fail_fast_on_duplicate_actionable_setup_id(
    tmp_path: Path,
) -> None:
    path = tmp_path / "execution_intents.jsonl"
    alert = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:00+00:00",
        intent_ttl_seconds=30.0,
    )
    first = engine.build_execution_intent_record(alert)
    duplicate_setup = copy.deepcopy(first)
    duplicate_setup["alert_id"] = "second-alert-same-setup"
    duplicate_setup["execution_intent"]["intent_id"] = "second-alert-same-setup"
    path.write_text(json.dumps(first) + "\n" + json.dumps(duplicate_setup) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Duplicate actionable execution-intent setup_id"):
        engine.load_actionable_execution_intents(
            path,
            now_utc="2026-06-11T13:31:05+00:00",
            fail_on_error=True,
        )


def test_load_actionable_execution_intents_can_fail_fast_on_non_actionable_record(tmp_path: Path) -> None:
    path = tmp_path / "execution_intents.jsonl"
    expired = engine.build_execution_intent_record(
        sample_entry_alert_with_entry_timestamp(
            "2026-06-11T13:30:00+00:00",
            intent_ttl_seconds=30.0,
        )
    )
    path.write_text(json.dumps(expired) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Non-actionable execution-intent record"):
        engine.load_actionable_execution_intents(
            path,
            now_utc="2026-06-11T13:31:05+00:00",
            fail_on_error=True,
        )


def test_check_execution_intents_outbox_reports_actionable_records(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "execution_intents.jsonl"
    alert = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:00+00:00",
        intent_ttl_seconds=30.0,
    )
    record = engine.build_execution_intent_record(alert)
    path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["execution_intents"]["path"] = str(path)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.check_execution_intents_outbox(
        signal_engine,
        now_utc="2026-06-11T13:31:05+00:00",
        require_actionable=True,
    )

    captured = capsys.readouterr()
    assert "execution_intent_outbox_check" in captured.out
    assert "execution_intent_outbox_check_failed" not in captured.out
    assert report["ok"] is True
    assert report["path"] == str(path)
    assert report["actionable_count"] == 1
    assert report["rejected_count"] == 0
    assert report["records"][0]["alert_id"] == alert["alert_id"]
    summary = report["actionable_summary"]
    assert summary["actionable_count"] == 1
    assert summary["expired_but_within_grace_count"] == 0
    assert summary["soonest_expires_at_utc"] == "2026-06-11T13:31:30+00:00"
    assert summary["seconds_until_soonest_expiry"] == 25.0
    next_intent = summary["next_expiring_intent"]
    assert next_intent["alert_id"] == alert["alert_id"]
    assert next_intent["setup_id"] == alert["setup_id"]
    assert next_intent["direction"] == "long"
    assert next_intent["quantity"] == 2
    assert next_intent["entry_price"] == 5000.25
    assert next_intent["stop_loss_price"] == 4999.25
    assert next_intent["take_profit_price"] == 5001.25
    assert next_intent["risk_dollars"] == 100.0
    assert next_intent["reward_dollars"] == 100.0


def test_check_execution_intents_outbox_summary_orders_next_expiring_intent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "execution_intents.jsonl"
    first = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:00+00:00",
        intent_ttl_seconds=60.0,
    )
    second = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:10+00:00",
        intent_ttl_seconds=30.0,
    )
    second["alert_id"] = "later-entry-earlier-expiry"
    second["setup_id"] = "setup-later-entry-earlier-expiry"
    second["pending_signal_key"] = "pending-later-entry-earlier-expiry"
    second["execution_intent"] = engine.build_execution_intent(
        second,
        max_entry_lag_seconds=120.0,
        intent_ttl_seconds=30.0,
    )
    path.write_text(
        json.dumps(engine.build_execution_intent_record(first))
        + "\n"
        + json.dumps(engine.build_execution_intent_record(second))
        + "\n",
        encoding="utf-8",
    )
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["execution_intents"]["path"] = str(path)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.check_execution_intents_outbox(
        signal_engine,
        now_utc="2026-06-11T13:31:15+00:00",
        require_actionable=True,
    )

    summary = report["actionable_summary"]
    assert report["ok"] is True
    assert summary["actionable_count"] == 2
    assert [item["alert_id"] for item in summary["records"]] == [
        "later-entry-earlier-expiry",
        "abc",
    ]
    assert summary["next_expiring_intent"]["alert_id"] == "later-entry-earlier-expiry"
    assert summary["soonest_expires_at_utc"] == "2026-06-11T13:31:40+00:00"
    assert summary["seconds_until_soonest_expiry"] == 25.0
    assert summary["latest_expires_at_utc"] == "2026-06-11T13:32:00+00:00"


def test_check_execution_intents_outbox_summary_flags_expired_grace_actionable(
    tmp_path: Path,
) -> None:
    path = tmp_path / "execution_intents.jsonl"
    alert = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:00+00:00",
        intent_ttl_seconds=30.0,
    )
    path.write_text(json.dumps(engine.build_execution_intent_record(alert)) + "\n", encoding="utf-8")
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["execution_intents"]["path"] = str(path)
    cfg["engine"]["execution_intents"]["freshness_grace_seconds"] = 10.0
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.check_execution_intents_outbox(
        signal_engine,
        now_utc="2026-06-11T13:31:35+00:00",
        require_actionable=True,
    )

    assert report["ok"] is True
    assert report["actionable_count"] == 1
    summary = report["actionable_summary"]
    assert summary["actionable_count"] == 1
    assert summary["expired_but_within_grace_count"] == 1
    assert summary["seconds_until_soonest_expiry"] == -5.0
    assert summary["next_expiring_intent"]["expires_at_utc"] == "2026-06-11T13:31:30+00:00"


def test_check_execution_intents_outbox_can_require_actionable_record(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "missing_execution_intents.jsonl"
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["execution_intents"]["path"] = str(path)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.check_execution_intents_outbox(
        signal_engine,
        now_utc="2026-06-11T13:31:05+00:00",
        require_actionable=True,
    )

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "execution_intent_outbox_check_failed" in captured.out
    assert report["ok"] is False
    assert report["actionable_count"] == 0
    assert report["failure_reasons"] == ["required_actionable_intent_missing"]


def test_check_execution_intents_outbox_strict_mode_rejects_non_actionable_records(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "execution_intents.jsonl"
    expired = engine.build_execution_intent_record(
        sample_entry_alert_with_entry_timestamp(
            "2026-06-11T13:30:00+00:00",
            intent_ttl_seconds=30.0,
        )
    )
    path.write_text(json.dumps(expired) + "\n", encoding="utf-8")
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["execution_intents"]["path"] = str(path)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.check_execution_intents_outbox(
        signal_engine,
        now_utc="2026-06-11T13:31:05+00:00",
        strict=True,
    )

    captured = capsys.readouterr()
    assert "execution_intent_outbox_check_failed" in captured.out
    assert report["ok"] is False
    assert report["actionable_count"] == 0
    assert report["rejected_count"] == 1
    assert report["rejected"][0]["state"] == "expired"
    assert report["failure_reasons"] == ["strict_rejected_records_present"]


def test_check_execution_intents_outbox_strict_mode_rejects_duplicate_setup_ids(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "execution_intents.jsonl"
    alert = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:00+00:00",
        intent_ttl_seconds=30.0,
    )
    first = engine.build_execution_intent_record(alert)
    duplicate_setup = copy.deepcopy(first)
    duplicate_setup["alert_id"] = "second-alert-same-setup"
    duplicate_setup["execution_intent"]["intent_id"] = "second-alert-same-setup"
    duplicate_setup["created_at_utc"] = "2026-06-11T13:31:02+00:00"
    path.write_text(json.dumps(first) + "\n" + json.dumps(duplicate_setup) + "\n", encoding="utf-8")
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["execution_intents"]["path"] = str(path)
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    report = engine.check_execution_intents_outbox(
        signal_engine,
        now_utc="2026-06-11T13:31:05+00:00",
        strict=True,
    )

    captured = capsys.readouterr()
    assert "execution_intent_outbox_check_failed" in captured.out
    assert report["ok"] is False
    assert report["actionable_count"] == 1
    assert report["rejected_count"] == 1
    assert report["duplicate_setup_id_count"] == 1
    assert report["rejected"][0]["state"] == "duplicate_setup_id"
    assert report["failure_reasons"] == ["strict_rejected_records_present"]


def test_execution_intent_freshness_report_classifies_time_window() -> None:
    alert = sample_entry_alert_with_entry_timestamp(
        "2026-06-11T13:31:00+00:00",
        intent_ttl_seconds=30.0,
    )
    intent = alert["execution_intent"]

    fresh = engine.execution_intent_freshness_report(
        intent,
        now_utc="2026-06-11T13:31:05+00:00",
    )
    expired = engine.execution_intent_freshness_report(
        intent,
        now_utc="2026-06-11T13:31:35+00:00",
    )
    future = engine.execution_intent_freshness_report(
        intent,
        now_utc="2026-06-11T13:30:55+00:00",
    )
    future_with_grace = engine.execution_intent_freshness_report(
        intent,
        now_utc="2026-06-11T13:30:59+00:00",
        grace_seconds=1.0,
    )

    assert fresh["actionable"] is True
    assert fresh["state"] == "fresh"
    assert expired["actionable"] is False
    assert expired["state"] == "expired"
    assert future["actionable"] is False
    assert future["state"] == "not_yet_valid"
    assert future_with_grace["actionable"] is True
    assert future_with_grace["state"] == "fresh"


def test_source_bar_quality_flags_bad_ohlc_and_delta_bounds() -> None:
    bad_bar = sample_source_bar(high=4999.75, close=5000.25, volume=10.0, signed_volume=12.0)

    issues = engine.validate_source_bars_quality(
        [bad_bar],
        timezone="America/New_York",
        config=engine.normalize_source_bar_quality_config({}),
    )

    codes = {issue.code for issue in issues}
    assert "high_below_open_or_close" in codes
    assert "signed_volume_exceeds_volume" in codes
    severities_by_code = {issue.code: issue.severity for issue in issues}
    assert severities_by_code["high_below_open_or_close"] == "error"
    assert severities_by_code["signed_volume_exceeds_volume"] == "error"


def test_source_bar_quality_flags_missing_quote_delta_diagnostics() -> None:
    bar = sample_source_bar()

    issues = engine.validate_source_bars_quality(
        [bar],
        timezone="America/New_York",
        config=engine.normalize_source_bar_quality_config({}),
        delta_method="price_vs_quote",
    )

    codes = {issue.code for issue in issues}
    assert "missing_selected_delta_unclassified_volume" in codes


def test_source_bar_quality_flags_excessive_quote_delta_unclassified_fraction() -> None:
    bad_bar = sample_source_bar(
        volume=100.0,
        signed_volume=0.0,
        buy_volume=0.0,
        sell_volume=0.0,
        large={
            "selected_delta_unclassified_volume": 40.0,
            "quote_unclassified_volume": 40.0,
        },
    )
    good_bar = sample_source_bar(
        timestamp_utc=ts("2026-06-11 13:31:00"),
        volume=100.0,
        signed_volume=76.0,
        buy_volume=76.0,
        sell_volume=0.0,
        large={
            "selected_delta_unclassified_volume": 24.0,
            "quote_unclassified_volume": 24.0,
        },
    )

    bad_issues = engine.validate_source_bars_quality(
        [bad_bar],
        timezone="America/New_York",
        config=engine.normalize_source_bar_quality_config({}),
        delta_method="price_vs_quote",
    )
    good_issues = engine.validate_source_bars_quality(
        [good_bar],
        timezone="America/New_York",
        config=engine.normalize_source_bar_quality_config({}),
        delta_method="price_vs_quote",
    )
    ignored_for_aggressor = engine.validate_source_bars_quality(
        [bad_bar],
        timezone="America/New_York",
        config=engine.normalize_source_bar_quality_config({}),
        delta_method="aggressor_side",
    )

    assert {issue.code for issue in bad_issues} == {"selected_delta_unclassified_fraction_exceeded"}
    assert good_issues == []
    assert ignored_for_aggressor == []


def test_engine_drops_invalid_completed_source_bar_and_alerts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    bad_bar = sample_source_bar(volume=10.0, signed_volume=12.0)

    signal_engine.on_completed_source_bar(bad_bar)

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "source_bar_quality_issues" in captured.out
    assert "signed_volume_exceeds_volume" in captured.out
    assert signal_engine.store.bars() == []
    assert signal_engine.pending == []


def test_engine_drops_completed_quote_delta_bar_with_excessive_unclassified_volume(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["schema"] = "mbp-1"
    cfg["databento"]["delta_method"] = "price_vs_quote"
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    bad_bar = sample_source_bar(
        volume=100.0,
        signed_volume=0.0,
        buy_volume=0.0,
        sell_volume=0.0,
        large={
            "selected_delta_unclassified_volume": 75.0,
            "quote_unclassified_volume": 75.0,
        },
    )

    signal_engine.on_completed_source_bar(bad_bar)

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "source_bar_quality_issues" in captured.out
    assert "selected_delta_unclassified_fraction_exceeded" in captured.out
    assert signal_engine.store.bars() == []
    assert signal_engine.pending == []


def test_engine_can_fail_fast_on_source_bar_quality_error() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["data_quality"]["fail_on_error"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    bad_bar = sample_source_bar(volume=10.0, signed_volume=12.0)

    with pytest.raises(RuntimeError, match="Source bar quality check failed"):
        signal_engine.on_completed_source_bar(bad_bar)

    assert signal_engine.store.bars() == []


def test_engine_filters_source_bars_that_do_not_match_contract_regex(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    good_bar = sample_source_bar(contract_symbol="ESM6")
    spread_bar = sample_source_bar(
        contract_symbol="ESM6-ESU6",
        volume=500.0,
        signed_volume=-100.0,
        buy_volume=200.0,
        sell_volume=300.0,
    )

    signal_engine.seed([spread_bar, good_bar], source="test_cache")

    captured = capsys.readouterr()
    stored = signal_engine.store.bars()
    assert len(stored) == 1
    assert stored[0].contract_symbol == "ESM6"
    assert signal_engine.source_contract_filter_drops == 1
    assert signal_engine.last_source_contract_filter_report["bars_dropped"] == 1
    assert signal_engine.last_source_contract_filter_report["dropped_contracts"] == {"ESM6-ESU6": 1}
    assert "SYSTEM_ALERT" in captured.out
    assert "source_bar_contract_symbol_filtered" in captured.out
    assert "ESM6-ESU6" in captured.out


def test_engine_filters_completed_source_bar_that_does_not_match_contract_regex(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    spread_bar = sample_source_bar(contract_symbol="ESM6-ESU6")

    signal_engine.on_completed_source_bar(spread_bar)

    captured = capsys.readouterr()
    assert signal_engine.store.bars() == []
    assert signal_engine.pending == []
    assert signal_engine.source_contract_filter_drops == 1
    assert "source_bar_contract_symbol_filtered" in captured.out


def test_strategy_skips_non_finite_required_feature_row(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]
    features = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
                "contract_symbol": "ESM6",
                "session_date": "2026-06-11",
                "high": 5001.0,
                "low": 4999.0,
                "signed_volume": float("nan"),
            }
        ]
    )
    strategy.completed_features = lambda _: features  # type: ignore[method-assign]

    pending = strategy.process_new_completed_bars(signal_engine.store, live=True)

    captured = capsys.readouterr()
    assert pending == []
    assert "SYSTEM_ALERT" in captured.out
    assert "strategy_feature_row_not_ready" in captured.out
    assert "signed_volume" in captured.out
    assert strategy.feature_quality_skip_count == 1
    assert strategy.evaluated_strategy_row_count == 0
    assert strategy.last_processed_strategy_timestamp == features.iloc[0]["timestamp"]
    assert len(strategy.processed_strategy_row_keys) == 1


def test_strategy_missing_required_feature_column_can_fail_fast() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]
    features = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
                "contract_symbol": "ESM6",
                "session_date": "2026-06-11",
                "high": 5001.0,
                "low": 4999.0,
            }
        ]
    )
    strategy.completed_features = lambda _: features  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="missing required column"):
        strategy.process_new_completed_bars(signal_engine.store, live=True)

    assert strategy.feature_quality_skip_count == 1


def test_strategy_processes_same_timestamp_rows_for_different_contracts() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["strategies"][0]["params"]["interval_bars"] = 1
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]
    features = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
                "contract_symbol": "ESM6",
                "session_date": "2026-06-11",
                "high": 5001.0,
                "low": 4999.0,
                "signed_volume": 10.0,
            },
            {
                "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
                "contract_symbol": "ESU6",
                "session_date": "2026-06-11",
                "high": 5002.0,
                "low": 5000.0,
                "signed_volume": -12.0,
            },
        ]
    )
    strategy.completed_features = lambda _: features  # type: ignore[method-assign]

    pending = strategy.process_new_completed_bars(signal_engine.store, live=True)

    assert len(pending) == 2
    assert {item.row["contract_symbol"] for item in pending} == {"ESM6", "ESU6"}
    assert {item.signal_obj.direction for item in pending} == {"long", "short"}
    assert len(strategy.processed_strategy_row_keys) == 2
    assert strategy.evaluated_strategy_row_count == 2
    assert strategy.last_evaluated_strategy_timestamp == features.iloc[-1]["timestamp"]
    assert strategy.duplicate_strategy_row_skips == 0


def test_strategy_skips_already_processed_same_timestamp_contract_row() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]
    features = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
                "contract_symbol": "ESM6",
                "session_date": "2026-06-11",
                "high": 5001.0,
                "low": 4999.0,
                "signed_volume": 10.0,
            }
        ]
    )
    strategy.completed_features = lambda _: features  # type: ignore[method-assign]

    first = strategy.process_new_completed_bars(signal_engine.store, live=True)
    second = strategy.process_new_completed_bars(signal_engine.store, live=True)

    assert len(first) == 1
    assert second == []
    assert len(strategy.processed_strategy_row_keys) == 1
    assert strategy.evaluated_strategy_row_count == 1
    assert strategy.duplicate_strategy_row_skips == 1


def test_strategy_runtime_error_disables_strategy_and_alerts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["strategy_errors"]["fail_when_all_strategies_disabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]

    def fail_process(_: engine.BarStore, *, live: bool) -> list[engine.PendingSignal]:
        assert live is True
        raise RuntimeError("feature build broke")

    strategy.process_new_completed_bars = fail_process  # type: ignore[method-assign]

    signal_engine.on_completed_source_bar(sample_source_bar())

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "strategy_runtime_error" in captured.out
    assert "feature build broke" in captured.out
    assert strategy.disabled is True
    assert strategy.error_count == 1
    assert signal_engine.active_strategy_count() == 0
    assert signal_engine.pending == []


def test_malformed_setup_notice_uses_strategy_error_policy(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["strategy_errors"]["fail_when_all_strategies_disabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]
    strategy.strategy.on_bar_close = lambda row, trades_today=0: engine.EngineSignal(  # type: ignore[method-assign]
        direction="sideways",
        level_type="bad_direction",
    )

    signal_engine.on_completed_source_bar(sample_source_bar())

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "strategy_runtime_error" in captured.out
    assert "build_setup_notice" in captured.out
    assert "setup notice direction must be long or short" in captured.out
    assert "TRADE_SETUP" not in captured.out
    assert strategy.disabled is True
    assert strategy.error_count == 1
    assert signal_engine.pending == []
    assert signal_engine.setup_notice_count == 0


def test_malformed_setup_notice_rejects_inconsistent_entry_window() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    notice = signal_engine.build_validated_setup_notice(sample_pending_setup(signal_engine.strategies[0]))
    notice["entry_window"]["expires_at_utc"] = "2026-06-11T13:34:00+00:00"

    with pytest.raises(ValueError, match="entry_window.expires_at_utc must match"):
        engine.validate_setup_notice_contract(notice)


def test_strategy_runtime_error_can_fail_fast() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["strategy_errors"]["fail_fast"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]

    def fail_process(_: engine.BarStore, *, live: bool) -> list[engine.PendingSignal]:
        raise RuntimeError("strategy exploded")

    strategy.process_new_completed_bars = fail_process  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="Strategy dummy_delta_every_5m_1r failed"):
        signal_engine.on_completed_source_bar(sample_source_bar())

    assert strategy.error_count == 1


def test_pending_signal_expiry_rejects_without_entry_tick(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["max_entry_lag_seconds"] = 120
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]
    signal = engine.EngineSignal(direction="long", level_type="test")
    pending = engine.PendingSignal(
        strategy=strategy,
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
            "session_date": "2026-06-11",
        },
        signal_obj=signal,
        due_utc=ts("2026-06-11 13:31:00"),
        queued_at_utc=ts("2026-06-11 13:30:01"),
        key="pending-test",
    )
    signal_engine.pending.append(pending)

    expired = signal_engine.expire_stale_pending_signals(
        now_utc=ts("2026-06-11 13:33:01"),
        source="test_heartbeat",
    )

    captured = capsys.readouterr()
    assert expired == 1
    assert signal_engine.pending == []
    assert "SIGNAL_REJECTED" in captured.out
    assert "SIGNAL REJECTED" in captured.out
    assert "pending entry expired" in captured.out
    assert "Due UTC  : 2026-06-11T13:31:00+00:00" in captured.out
    assert "pending_signals_expired" in captured.out


def test_on_entry_tick_requires_pending_contract_match(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["execution_intents"]["enabled"] = False
    cfg["engine"]["entry_contract_mismatch_alert_repeat_seconds"] = 0
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]
    pending = engine.PendingSignal(
        strategy=strategy,
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6",
        },
        signal_obj=engine.EngineSignal(
            direction="long",
            level_type="test",
            metadata={"latest_completed_bar_low": 4999.0, "latest_completed_bar_high": 5001.0},
        ),
        due_utc=ts("2026-06-11 13:31:00"),
        queued_at_utc=ts("2026-06-11 13:30:01"),
        key="pending-contract-match",
    )
    signal_engine.pending.append(pending)

    signal_engine.on_entry_tick(
        engine.TradeTick(ts("2026-06-11 13:31:00"), 5000.0, 1, "B", "ESU6")
    )

    mismatch_output = capsys.readouterr().out
    assert "entry_tick_contract_mismatch_skipped" in mismatch_output
    assert signal_engine.alert_count == 0
    assert signal_engine.pending == [pending]
    assert signal_engine.entry_contract_mismatch_skips == 1
    assert signal_engine.last_entry_contract_mismatch == {
        "strategy_id": "dummy_delta_every_5m_1r",
        "pending_signal_key": "pending-contract-match",
        "expected_contract_symbol": "ESM6",
        "entry_tick_contract_symbol": "ESU6",
        "entry_tick_timestamp_utc": "2026-06-11T13:31:00+00:00",
        "due_timestamp_utc": "2026-06-11T13:31:00+00:00",
        "lag_seconds": 0.0,
    }

    signal_engine.on_entry_tick(
        engine.TradeTick(ts("2026-06-11 13:31:01"), 5000.0, 1, "B", "ESM6")
    )

    entry_output = capsys.readouterr().out
    assert "ENTRY_SIGNAL" in entry_output
    assert signal_engine.alert_count == 1
    assert signal_engine.pending == []


def test_on_entry_tick_expired_contract_mismatch_emits_pending_expiry_alert(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["execution_intents"]["enabled"] = False
    cfg["engine"]["max_entry_lag_seconds"] = 30
    cfg["engine"]["entry_contract_mismatch_alert_repeat_seconds"] = 0
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    pending = engine.PendingSignal(
        strategy=signal_engine.strategies[0],
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6",
        },
        signal_obj=engine.EngineSignal(
            direction="long",
            level_type="test",
            metadata={"latest_completed_bar_low": 4999.0, "latest_completed_bar_high": 5001.0},
        ),
        due_utc=ts("2026-06-11 13:31:00"),
        queued_at_utc=ts("2026-06-11 13:30:01"),
        key="pending-expired-contract-mismatch",
    )
    signal_engine.pending.append(pending)

    signal_engine.on_entry_tick(
        engine.TradeTick(ts("2026-06-11 13:31:31"), 5000.0, 1, "B", "ESU6")
    )

    captured = capsys.readouterr().out
    assert "entry_tick_contract_mismatch_skipped" in captured
    assert "SIGNAL_REJECTED" in captured
    assert "no matching ESM6 entry tick arrived within max_entry_lag_seconds" in captured
    assert "pending_signals_expired" in captured
    assert '"source": "entry_tick"' in captured
    assert '"total_expired": 1' in captured
    assert "ENTRY_SIGNAL" not in captured
    assert signal_engine.alert_count == 0
    assert signal_engine.pending == []
    assert signal_engine.pending_expired_count == 1


def test_on_entry_tick_rejects_pending_contract_symbol_that_violates_regex(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["execution_intents"]["enabled"] = False
    cfg["engine"]["entry_contract_mismatch_alert_repeat_seconds"] = 0
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    pending = engine.PendingSignal(
        strategy=signal_engine.strategies[0],
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:35:00", tz="America/New_York"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6-ESU6",
        },
        signal_obj=engine.EngineSignal(
            direction="short",
            level_type="test",
            metadata={"latest_completed_bar_low": 7288.75, "latest_completed_bar_high": 7293.5},
        ),
        due_utc=ts("2026-06-11 13:36:00"),
        queued_at_utc=ts("2026-06-11 13:35:01"),
        key="pending-spread-contract",
    )
    signal_engine.pending.append(pending)

    signal_engine.on_entry_tick(
        engine.TradeTick(ts("2026-06-11 13:36:00"), 61.0, 1, "A", "ESM6-ESU6")
    )

    captured = capsys.readouterr().out
    assert "entry_contract_symbol_regex_filtered" in captured
    assert "pending setup contract_symbol does not match databento.contract_symbol_regex" in captured
    assert "ENTRY_SIGNAL" not in captured
    assert signal_engine.alert_count == 0
    assert signal_engine.pending == []
    assert signal_engine.entry_contract_regex_skips == 1
    assert signal_engine.last_entry_contract_regex_skip["rejected_contract_symbol"] == "ESM6-ESU6"
    assert not (tmp_path / "entry_signals.jsonl").exists()


def test_on_entry_tick_ignores_entry_tick_contract_symbol_that_violates_regex(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["execution_intents"]["enabled"] = False
    cfg["engine"]["entry_contract_mismatch_alert_repeat_seconds"] = 0
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    pending = engine.PendingSignal(
        strategy=signal_engine.strategies[0],
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:35:00", tz="America/New_York"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6",
        },
        signal_obj=engine.EngineSignal(
            direction="short",
            level_type="test",
            metadata={"latest_completed_bar_low": 7288.75, "latest_completed_bar_high": 7293.5},
        ),
        due_utc=ts("2026-06-11 13:36:00"),
        queued_at_utc=ts("2026-06-11 13:35:01"),
        key="pending-valid-contract",
    )
    signal_engine.pending.append(pending)

    signal_engine.on_entry_tick(
        engine.TradeTick(ts("2026-06-11 13:36:00"), 61.0, 1, "A", "ESM6-ESU6")
    )

    invalid_output = capsys.readouterr().out
    assert "entry_contract_symbol_regex_filtered" in invalid_output
    assert "ENTRY_SIGNAL" not in invalid_output
    assert signal_engine.alert_count == 0
    assert signal_engine.pending == [pending]
    assert signal_engine.entry_contract_regex_skips == 1

    signal_engine.on_entry_tick(
        engine.TradeTick(ts("2026-06-11 13:36:01"), 7290.0, 1, "A", "ESM6")
    )

    valid_output = capsys.readouterr().out
    assert "ENTRY_SIGNAL" in valid_output
    assert signal_engine.alert_count == 1
    assert signal_engine.pending == []


def test_build_alert_rejects_cross_contract_tick_directly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy_runtime = signal_engine.strategies[0]
    pending = engine.PendingSignal(
        strategy=strategy_runtime,
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6",
        },
        signal_obj=engine.EngineSignal(
            direction="long",
            level_type="test",
            metadata={"latest_completed_bar_low": 4999.0, "latest_completed_bar_high": 5001.0},
        ),
        due_utc=ts("2026-06-11 13:31:00"),
        queued_at_utc=ts("2026-06-11 13:30:01"),
        key="pending-build-alert-contract-mismatch",
    )

    alert = strategy_runtime.build_alert(
        pending,
        engine.TradeTick(ts("2026-06-11 13:31:00"), 5000.0, 1, "B", "ESU6"),
        signal_engine.account,
    )

    captured = capsys.readouterr()
    assert alert is None
    assert "SIGNAL_REJECTED" in captured.out
    assert "entry tick contract_symbol does not match pending setup contract_symbol" in captured.out


def test_build_alert_rejects_spread_contract_symbol_directly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy_runtime = signal_engine.strategies[0]
    pending = engine.PendingSignal(
        strategy=strategy_runtime,
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:35:00", tz="America/New_York"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6-ESU6",
        },
        signal_obj=engine.EngineSignal(
            direction="short",
            level_type="test",
            metadata={"latest_completed_bar_low": 7288.75, "latest_completed_bar_high": 7293.5},
        ),
        due_utc=ts("2026-06-11 13:36:00"),
        queued_at_utc=ts("2026-06-11 13:35:01"),
        key="pending-direct-spread",
    )

    alert = strategy_runtime.build_alert(
        pending,
        engine.TradeTick(ts("2026-06-11 13:36:00"), 61.0, 1, "A", "ESM6-ESU6"),
        signal_engine.account,
    )

    captured = capsys.readouterr()
    assert alert is None
    assert "SIGNAL_REJECTED" in captured.out
    assert "pending setup contract_symbol does not match databento.contract_symbol_regex" in captured.out


def test_pending_status_reports_oldest_due_and_overdue_count() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    strategy = signal_engine.strategies[0]
    signal_engine.pending.extend(
        [
            engine.PendingSignal(
                strategy=strategy,
                row={"timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York")},
                signal_obj=engine.EngineSignal(direction="long", level_type="test"),
                due_utc=ts("2026-06-11 13:31:00"),
                queued_at_utc=ts("2026-06-11 13:30:01"),
                key="pending-a",
            ),
            engine.PendingSignal(
                strategy=strategy,
                row={"timestamp": pd.Timestamp("2026-06-11 09:31:00", tz="America/New_York")},
                signal_obj=engine.EngineSignal(direction="short", level_type="test"),
                due_utc=ts("2026-06-11 13:32:00"),
                queued_at_utc=ts("2026-06-11 13:31:01"),
                key="pending-b",
            ),
        ]
    )

    status = signal_engine.pending_status(now_utc=ts("2026-06-11 13:31:30"))

    assert status["count"] == 2
    assert status["oldest_due_timestamp_utc"] == "2026-06-11T13:31:00+00:00"
    assert status["oldest_seconds_until_due"] == -30.0
    assert status["overdue_count"] == 1
    assert status["soonest_expires_at_utc"] == "2026-06-11T13:33:00+00:00"
    assert status["soonest_seconds_until_expiry"] == 90.0
    assert status["expired_count"] == 0
    assert status["max_entry_lag_seconds"] == 120.0
    assert status["total_expired_count"] == 0
    assert status["entry_contract_match_required"] is True
    assert status["entry_contract_mismatch_skips"] == 0
    assert status["last_entry_contract_mismatch"] is None
    assert status["entry_contract_regex_skips"] == 0
    assert status["last_entry_contract_regex_skip"] is None

    expired_status = signal_engine.pending_status(now_utc=ts("2026-06-11 13:33:01"))
    assert expired_status["expired_count"] == 1
    assert expired_status["soonest_seconds_until_expiry"] == -1.0


def test_operator_sound_tracks_command_success_and_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProcess:
        def __init__(self) -> None:
            self.terminated = False
            self.killed = False
            self.done = False

        def poll(self) -> int | None:
            return 0 if self.done else None

        def terminate(self) -> None:
            self.terminated = True

        def wait(self, timeout: float | None = None) -> int:
            assert timeout == 0.5
            self.done = True
            return 0

        def kill(self) -> None:
            self.killed = True
            self.done = True

    created: list[FakeProcess] = []

    def fake_popen(*args: object, **kwargs: object) -> FakeProcess:
        assert args[0] == ["fake-player", "ding"]
        process = FakeProcess()
        created.append(process)
        return process

    monkeypatch.setattr(engine.subprocess, "Popen", fake_popen)
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["operator"]["sound"] = {
        "enabled": True,
        "bell": False,
        "on_entry": True,
        "command": "fake-player ding",
        "cleanup_on_exit": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.play_operator_sound("entry")
    report_before = signal_engine.operator_sound_health_report()
    signal_engine.cleanup_operator_sound_processes(terminate_running=True)
    report_after = signal_engine.operator_sound_health_report()

    assert len(created) == 1
    assert created[0].terminated is True
    assert created[0].killed is False
    assert report_before["commands_started"] == 1
    assert report_before["active_command_processes"] == 1
    assert report_after["active_command_processes"] == 0
    assert report_after["cleanup_terminated"] == 1


def test_operator_sound_skips_external_command_when_active_limit_reached(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeProcess:
        def __init__(self) -> None:
            self.terminated = False
            self.done = False

        def poll(self) -> int | None:
            return 0 if self.done else None

        def terminate(self) -> None:
            self.terminated = True
            self.done = True

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def kill(self) -> None:
            self.done = True

    created: list[FakeProcess] = []

    def fake_popen(*args: object, **kwargs: object) -> FakeProcess:
        assert args[0] == ["fake-player", "ding"]
        process = FakeProcess()
        created.append(process)
        return process

    monkeypatch.setattr(engine.subprocess, "Popen", fake_popen)
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["operator"]["sound"] = {
        "enabled": True,
        "bell": False,
        "on_entry": True,
        "command": "fake-player ding",
        "max_active_commands": 1,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.play_operator_sound("entry")
    signal_engine.play_operator_sound("entry")

    captured = capsys.readouterr()
    report = signal_engine.operator_sound_health_report()
    assert "SYSTEM_ALERT" in captured.out
    assert "operator_sound_command_limit" in captured.out
    assert len(created) == 1
    assert report["commands_started"] == 1
    assert report["command_skips"] == 1
    assert report["active_command_processes"] == 1
    assert report["max_active_commands"] == 1
    assert "1/1 active" in report["last_skip_reason"]
    signal_engine.cleanup_operator_sound_processes(terminate_running=True)


def test_operator_sound_command_limit_can_fail_fast(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unexpected_popen(*_: object, **__: object) -> object:
        raise AssertionError("sound command should not launch after the limit is reached")

    monkeypatch.setattr(engine.subprocess, "Popen", unexpected_popen)
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["operator"]["sound"] = {
        "enabled": True,
        "bell": False,
        "on_entry": True,
        "command": "fake-player ding",
        "max_active_commands": 0,
        "fail_on_error": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Operator sound command limit reached for entry"):
        signal_engine.play_operator_sound("entry")

    captured = capsys.readouterr()
    report = signal_engine.operator_sound_health_report()
    assert "operator_sound_command_limit" in captured.out
    assert '"fail_on_error": true' in captured.out
    assert report["commands_started"] == 0
    assert report["command_skips"] == 1
    assert report["max_active_commands"] == 0
    assert report["last_skip_reason"] == "operator sound command limit reached: 0/0 active"


def test_operator_sound_reports_command_launch_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_popen(*_: object, **__: object) -> object:
        raise OSError("player missing")

    monkeypatch.setattr(engine.subprocess, "Popen", fail_popen)
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["operator"]["sound"] = {
        "enabled": True,
        "bell": False,
        "on_entry": True,
        "command": "missing-player ding",
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.play_operator_sound("entry")

    captured = capsys.readouterr()
    report = signal_engine.operator_sound_health_report()
    assert "SYSTEM_ALERT" in captured.out
    assert "operator_sound_error" in captured.out
    assert report["attempts"] == 1
    assert report["commands_started"] == 0
    assert report["command_failures"] == 1
    assert report["last_error_type"] == "OSError"
    assert report["fail_on_error"] is False


def test_operator_sound_can_fail_fast_on_command_launch_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_popen(*_: object, **__: object) -> object:
        raise OSError("player missing")

    monkeypatch.setattr(engine.subprocess, "Popen", fail_popen)
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["operator"]["sound"] = {
        "enabled": True,
        "bell": False,
        "on_entry": True,
        "command": "missing-player ding",
        "fail_on_error": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Operator sound alert failed for entry"):
        signal_engine.play_operator_sound("entry")

    captured = capsys.readouterr()
    report = signal_engine.operator_sound_health_report()
    assert "operator_sound_error" in captured.out
    assert '"fail_on_error": true' in captured.out
    assert report["attempts"] == 1
    assert report["commands_started"] == 0
    assert report["command_failures"] == 1
    assert report["last_error_type"] == "OSError"
    assert report["fail_on_error"] is True


def test_operator_sound_test_plays_configured_kind(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeProcess:
        def poll(self) -> int:
            return 0

        def terminate(self) -> None:
            raise AssertionError("completed sound command should not be terminated")

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def kill(self) -> None:
            raise AssertionError("completed sound command should not be killed")

    created: list[list[str]] = []

    def fake_popen(*args: object, **kwargs: object) -> FakeProcess:
        created.append(list(args[0]))  # type: ignore[arg-type]
        assert kwargs["stdout"] == engine.subprocess.DEVNULL
        assert kwargs["stderr"] == engine.subprocess.DEVNULL
        return FakeProcess()

    monkeypatch.setattr(engine.subprocess, "Popen", fake_popen)
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["operator"]["sound"] = {
        "enabled": True,
        "bell": False,
        "on_setup": True,
        "on_entry": True,
        "on_system": True,
        "setup_command": "/bin/echo setup-sound",
        "entry_command": "/bin/echo entry-sound",
        "system_command": "/bin/echo system-sound",
        "max_active_commands": 3,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    exit_code = engine.run_operator_sound_test(signal_engine, "entry")

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "readiness_operator_sound_ok" in captured.out
    assert "operator_sound_test_playing" in captured.out
    assert "operator_sound_test_ok" in captured.out
    assert created == [["/bin/echo", "entry-sound"]]
    assert signal_engine.operator_sound_health.attempts == 1
    assert signal_engine.operator_sound_health.commands_started == 1


def test_operator_sound_test_rejects_dry_run_alerts(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def unexpected_popen(*_: object, **__: object) -> object:
        raise AssertionError("dry-run sound test should not launch a command")

    monkeypatch.setattr(engine.subprocess, "Popen", unexpected_popen)
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["dry_run_alerts"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    exit_code = engine.run_operator_sound_test(signal_engine, "entry")

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "operator_sound_test_failed" in captured.out
    assert "--dry-run-alerts suppresses operator sounds" in captured.out
    assert signal_engine.operator_sound_health.attempts == 0


def test_operator_sound_test_fails_on_nonzero_player_exit(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeProcess:
        pid = 12345

        def poll(self) -> int:
            return 1

        def terminate(self) -> None:
            raise AssertionError("completed failed command should not be terminated")

        def wait(self, timeout: float | None = None) -> int:
            return 1

        def kill(self) -> None:
            raise AssertionError("completed failed command should not be killed")

    def fake_popen(*_: object, **__: object) -> FakeProcess:
        return FakeProcess()

    monkeypatch.setattr(engine.subprocess, "Popen", fake_popen)
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["operator"]["sound"] = {
        "enabled": True,
        "bell": False,
        "on_entry": True,
        "entry_command": "/bin/echo entry-sound",
        "max_active_commands": 3,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    exit_code = engine.run_operator_sound_test(signal_engine, "entry")

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "operator_sound_test_failed" in captured.out
    assert "operator sound command exited non-zero" in captured.out
    assert '"returncode": 1' in captured.out
    assert signal_engine.operator_sound_health.commands_started == 1


def test_emit_alert_persists_outboxes_before_fatal_operator_sound_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_popen(*_: object, **__: object) -> object:
        raise OSError("player missing")

    monkeypatch.setattr(engine.subprocess, "Popen", fail_popen)
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    intents_path = tmp_path / "execution_intents.jsonl"
    cfg["engine"]["alerts_path"] = str(alerts_path)
    cfg["engine"]["execution_intents"]["path"] = str(intents_path)
    cfg["engine"]["operator"]["sound"] = {
        "enabled": True,
        "bell": False,
        "on_entry": True,
        "command": "missing-player ding",
        "fail_on_error": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    alert = sample_fresh_entry_alert()

    with pytest.raises(RuntimeError, match="Operator sound alert failed for entry"):
        signal_engine.emit_alert(alert)

    alert_records = [json.loads(line) for line in alerts_path.read_text(encoding="utf-8").splitlines()]
    intent_records = [json.loads(line) for line in intents_path.read_text(encoding="utf-8").splitlines()]
    assert len(alert_records) == 1
    assert len(intent_records) == 1
    assert alert_records[0]["alert_id"] == alert["alert_id"]
    assert intent_records[0]["alert_id"] == alert["alert_id"]
    assert signal_engine.alert_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.writes_succeeded == 1
    assert signal_engine.operator_sound_health.command_failures == 1


def test_emit_setup_notice_persists_record_before_fatal_operator_sound_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_popen(*_: object, **__: object) -> object:
        raise OSError("player missing")

    monkeypatch.setattr(engine.subprocess, "Popen", fail_popen)
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    setup_path = tmp_path / "trade_setups.jsonl"
    cfg["engine"]["setup_alerts"]["path"] = str(setup_path)
    cfg["engine"]["operator"]["sound"] = {
        "enabled": True,
        "bell": False,
        "on_setup": True,
        "command": "missing-player ding",
        "fail_on_error": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Operator sound alert failed for setup"):
        signal_engine.emit_setup_notice(sample_pending_setup(signal_engine.strategies[0]))

    records = [json.loads(line) for line in setup_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["event"] == "trade_setup"
    assert records[0]["setup_id"]
    assert signal_engine.setup_notice_sink.writes_succeeded == 1
    assert signal_engine.operator_sound_health.command_failures == 1


def test_emit_alert_reports_alert_file_write_failure_without_crashing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    bad_alert_path = tmp_path / "alerts_path_is_a_directory"
    bad_alert_path.mkdir()
    cfg["engine"]["alerts_path"] = str(bad_alert_path)
    cfg["engine"]["alert_file"] = {"fsync": False, "fail_on_write_error": False}
    cfg["engine"]["execution_intents"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.emit_alert(sample_entry_alert())

    captured = capsys.readouterr()
    assert "ENTRY_SIGNAL" in captured.out
    assert "SYSTEM_ALERT" in captured.out
    assert "alert_file_write_failed" in captured.out
    assert signal_engine.alert_count == 1
    assert signal_engine.alert_sink.writes_succeeded == 0
    assert signal_engine.alert_sink.writes_failed == 1
    assert signal_engine.alert_sink.last_error_type is not None


def test_emit_setup_notice_writes_setup_alert_and_suppresses_duplicate(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    setup_path = tmp_path / "trade_setups.jsonl"
    cfg["engine"]["setup_alerts"] = {
        "enabled": True,
        "path": str(setup_path),
        "fsync": False,
        "fail_on_write_error": False,
        "suppress_duplicate_setup_ids": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    pending = sample_pending_setup(signal_engine.strategies[0])

    signal_engine.emit_setup_notice(pending)
    signal_engine.emit_setup_notice(pending)

    captured = capsys.readouterr()
    records = [json.loads(line) for line in setup_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["event"] == "trade_setup"
    assert records[0]["setup_contract_version"] == engine.SETUP_NOTICE_CONTRACT_VERSION
    assert records[0]["setup_id"]
    assert "entry_price" not in records[0]
    assert "execution_intent" not in records[0]
    assert signal_engine.setup_notice_sink.writes_succeeded == 1
    assert signal_engine.setup_notice_sink.duplicates_skipped == 1
    assert signal_engine.setup_notice_count == 2
    assert "TRADE_SETUP" in captured.out
    assert "setup_alerts_duplicate_setup_id_skipped" in captured.out


def test_emit_setup_notice_reports_write_failure_without_crashing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    bad_setup_path = tmp_path / "setup_path_is_a_directory"
    bad_setup_path.mkdir()
    cfg["engine"]["setup_alerts"] = {
        "enabled": True,
        "path": str(bad_setup_path),
        "fsync": False,
        "fail_on_write_error": False,
        "suppress_duplicate_setup_ids": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.emit_setup_notice(sample_pending_setup(signal_engine.strategies[0]))

    captured = capsys.readouterr()
    assert "TRADE_SETUP" in captured.out
    assert "SYSTEM_ALERT" in captured.out
    assert "setup_alert_write_failed" in captured.out
    assert signal_engine.setup_notice_sink.writes_succeeded == 0
    assert signal_engine.setup_notice_sink.writes_failed == 1
    assert signal_engine.setup_notice_sink.last_error_type is not None


def test_dry_run_alerts_prints_without_writing_outboxes_or_sound(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["dry_run_alerts"] = True
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["setup_alerts"]["path"] = str(tmp_path / "trade_setups.jsonl")
    cfg["engine"]["execution_intents"]["path"] = str(tmp_path / "execution_intents.jsonl")
    cfg["engine"]["operator"]["sound"]["enabled"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.emit_setup_notice(sample_pending_setup(signal_engine.strategies[0]))
    signal_engine.emit_alert(sample_entry_alert())

    captured = capsys.readouterr()
    assert "TRADE_SETUP" in captured.out
    assert "ENTRY_SIGNAL" in captured.out
    assert captured.out.count('"event": "dry_run_outputs_skipped"') == 2
    assert '"record_type": "trade_setup"' in captured.out
    assert '"record_type": "entry_signal"' in captured.out
    dry_run_payloads = [
        json.loads(line.removeprefix("SYSTEM_ALERT "))
        for line in captured.out.splitlines()
        if '"event": "dry_run_outputs_skipped"' in line
    ]
    setup_payload = next(item for item in dry_run_payloads if item["record_type"] == "trade_setup")
    entry_payload = next(item for item in dry_run_payloads if item["record_type"] == "entry_signal")
    assert setup_payload["setup_alerts"]["would_write"] is False
    assert setup_payload["setup_alerts"]["would_write_without_dry_run"] is True
    assert setup_payload["setup_alerts"]["write_suppressed_by_dry_run"] is True
    assert setup_payload["entry_alerts"]["would_write"] is False
    assert setup_payload["execution_intents"]["would_write"] is False
    assert setup_payload["operator_sound"]["would_play"] is False
    assert setup_payload["operator_sound"]["would_play_without_dry_run"] is True
    assert setup_payload["operator_sound"]["sound_suppressed_by_dry_run"] is True
    assert entry_payload["entry_alerts"]["would_write"] is False
    assert entry_payload["entry_alerts"]["would_write_without_dry_run"] is True
    assert entry_payload["entry_alerts"]["write_suppressed_by_dry_run"] is True
    assert entry_payload["execution_intents"]["would_write"] is False
    assert entry_payload["execution_intents"]["would_write_without_dry_run"] is True
    assert entry_payload["execution_intents"]["write_suppressed_by_dry_run"] is True
    assert entry_payload["setup_alerts"]["would_write"] is False
    assert entry_payload["operator_sound"]["would_play"] is False
    assert entry_payload["operator_sound"]["would_play_without_dry_run"] is True
    assert entry_payload["operator_sound"]["sound_suppressed_by_dry_run"] is True
    assert not (tmp_path / "entry_signals.jsonl").exists()
    assert not (tmp_path / "trade_setups.jsonl").exists()
    assert not (tmp_path / "execution_intents.jsonl").exists()
    assert signal_engine.setup_notice_count == 1
    assert signal_engine.alert_count == 1
    assert signal_engine.setup_notice_sink.writes_succeeded == 0
    assert signal_engine.alert_sink.writes_succeeded == 0
    assert signal_engine.execution_intent_sink.writes_succeeded == 0
    assert signal_engine.operator_sound_health.attempts == 0


def test_emit_alert_can_fail_fast_on_alert_file_write_error(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    bad_alert_path = tmp_path / "alerts_path_is_a_directory"
    bad_alert_path.mkdir()
    cfg["engine"]["alerts_path"] = str(bad_alert_path)
    cfg["engine"]["alert_file"] = {"fsync": False, "fail_on_write_error": True}
    cfg["engine"]["execution_intents"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Alert file write failed"):
        signal_engine.emit_alert(sample_entry_alert())

    assert signal_engine.alert_count == 1
    assert signal_engine.alert_sink.writes_failed == 1


def test_alert_file_suppresses_existing_duplicate_alert_id(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    alert = sample_entry_alert()
    alerts_path.write_text(json.dumps(alert) + "\n", encoding="utf-8")
    cfg["engine"]["alerts_path"] = str(alerts_path)
    cfg["engine"]["alert_file"] = {
        "fsync": False,
        "fail_on_write_error": False,
        "suppress_duplicate_alert_ids": True,
    }
    cfg["engine"]["execution_intents"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.emit_alert(copy.deepcopy(alert))

    captured = capsys.readouterr()
    assert "alert_file_duplicate_alert_id_skipped" in captured.out
    assert len(alerts_path.read_text(encoding="utf-8").splitlines()) == 1
    assert signal_engine.alert_sink.writes_succeeded == 0
    assert signal_engine.alert_sink.duplicates_skipped == 1
    assert signal_engine.alert_sink.last_duplicate_alert_id == alert["alert_id"]


def test_alert_file_does_not_suppress_older_alert_contract_version(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    alert = sample_entry_alert()
    old_alert = copy.deepcopy(alert)
    old_alert["alert_contract_version"] = "entry_signal.v1"
    alerts_path.write_text(json.dumps(old_alert) + "\n", encoding="utf-8")
    cfg["engine"]["alerts_path"] = str(alerts_path)
    cfg["engine"]["alert_file"] = {
        "fsync": False,
        "fail_on_write_error": False,
        "suppress_duplicate_alert_ids": True,
    }
    cfg["engine"]["execution_intents"]["enabled"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.emit_alert(copy.deepcopy(alert))

    captured = capsys.readouterr()
    records = [json.loads(line) for line in alerts_path.read_text(encoding="utf-8").splitlines()]
    assert "alert_file_duplicate_alert_id_skipped" not in captured.out
    assert len(records) == 2
    assert records[0]["alert_contract_version"] == "entry_signal.v1"
    assert records[1]["alert_contract_version"] == engine.ALERT_CONTRACT_VERSION
    assert signal_engine.alert_sink.writes_succeeded == 1
    assert signal_engine.alert_sink.duplicates_skipped == 0


def test_emit_alert_writes_execution_intent_outbox(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    intents_path = tmp_path / "execution_intents.jsonl"
    cfg["engine"]["alerts_path"] = str(alerts_path)
    cfg["engine"]["execution_intents"] = {
        "enabled": True,
        "path": str(intents_path),
        "fsync": False,
        "fail_on_write_error": False,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    alert = sample_fresh_entry_alert()

    signal_engine.emit_alert(alert)

    assert signal_engine.alert_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.writes_succeeded == 1
    records = [json.loads(line) for line in intents_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["event"] == "execution_intent_ready"
    assert records[0]["record_schema_version"] == engine.EXECUTION_INTENT_RECORD_VERSION
    assert records[0]["alert_id"] == alert["alert_id"]
    assert records[0]["execution_intent"]["intent_id"] == alert["alert_id"]


def test_execution_intent_outbox_skips_expired_intent_by_default(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    intents_path = tmp_path / "execution_intents.jsonl"
    cfg["engine"]["alerts_path"] = str(alerts_path)
    cfg["engine"]["execution_intents"] = {
        "enabled": True,
        "path": str(intents_path),
        "fsync": False,
        "fail_on_write_error": False,
        "suppress_duplicate_alert_ids": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    alert = sample_entry_alert_with_entry_timestamp(
        pd.Timestamp.utcnow() - pd.Timedelta(minutes=5),
        intent_ttl_seconds=30.0,
    )

    signal_engine.emit_alert(alert)

    captured = capsys.readouterr()
    assert "execution_intents_non_actionable_intent_skipped" in captured.out
    assert '"state": "expired"' in captured.out
    assert alerts_path.exists()
    assert not intents_path.exists()
    assert signal_engine.alert_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.writes_succeeded == 0
    assert signal_engine.execution_intent_sink.freshness_skipped == 1
    assert signal_engine.execution_intent_sink.last_freshness_skip_alert_id == alert["alert_id"]
    assert signal_engine.execution_intent_sink.last_freshness_skip_reason == "expired"


def test_execution_intent_outbox_can_fail_fast_on_expired_intent(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    intents_path = tmp_path / "execution_intents.jsonl"
    cfg["engine"]["alerts_path"] = str(alerts_path)
    cfg["engine"]["execution_intents"] = {
        "enabled": True,
        "path": str(intents_path),
        "fsync": False,
        "fail_on_write_error": False,
        "suppress_duplicate_alert_ids": True,
        "fail_on_freshness_error": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    alert = sample_entry_alert_with_entry_timestamp(
        pd.Timestamp.utcnow() - pd.Timedelta(minutes=5),
        intent_ttl_seconds=30.0,
    )

    with pytest.raises(RuntimeError, match="freshness check failed"):
        signal_engine.emit_alert(alert)

    assert signal_engine.alert_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.writes_succeeded == 0
    assert signal_engine.execution_intent_sink.freshness_skipped == 1
    assert not intents_path.exists()


def test_execution_intent_outbox_suppresses_existing_duplicate_alert_id(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    intents_path = tmp_path / "execution_intents.jsonl"
    alert = sample_fresh_entry_alert()
    intents_path.write_text(json.dumps(engine.build_execution_intent_record(alert)) + "\n", encoding="utf-8")
    cfg["engine"]["alerts_path"] = str(alerts_path)
    cfg["engine"]["execution_intents"] = {
        "enabled": True,
        "path": str(intents_path),
        "fsync": False,
        "fail_on_write_error": False,
        "suppress_duplicate_alert_ids": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.emit_alert(copy.deepcopy(alert))

    captured = capsys.readouterr()
    assert "execution_intents_duplicate_alert_id_skipped" in captured.out
    assert len(intents_path.read_text(encoding="utf-8").splitlines()) == 1
    assert signal_engine.alert_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.writes_succeeded == 0
    assert signal_engine.execution_intent_sink.duplicates_skipped == 1
    assert signal_engine.execution_intent_sink.last_duplicate_alert_id == alert["alert_id"]
    assert signal_engine.execution_intent_sink.last_duplicate_id_field == "alert_id"


def test_execution_intent_outbox_suppresses_existing_duplicate_setup_id(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    intents_path = tmp_path / "execution_intents.jsonl"
    original = sample_fresh_entry_alert()
    duplicate_setup = copy.deepcopy(original)
    duplicate_setup["alert_id"] = "new-alert-for-same-setup"
    duplicate_setup["execution_intent"] = engine.build_execution_intent(
        duplicate_setup,
        max_entry_lag_seconds=120.0,
        intent_ttl_seconds=30.0,
    )
    intents_path.write_text(json.dumps(engine.build_execution_intent_record(original)) + "\n", encoding="utf-8")
    cfg["engine"]["alerts_path"] = str(alerts_path)
    cfg["engine"]["execution_intents"] = {
        "enabled": True,
        "path": str(intents_path),
        "fsync": False,
        "fail_on_write_error": False,
        "suppress_duplicate_alert_ids": True,
        "suppress_duplicate_setup_ids": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.emit_alert(duplicate_setup)

    captured = capsys.readouterr()
    assert "execution_intents_duplicate_alert_id_skipped" not in captured.out
    assert "execution_intents_duplicate_setup_id_skipped" in captured.out
    assert len(intents_path.read_text(encoding="utf-8").splitlines()) == 1
    assert signal_engine.alert_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.writes_succeeded == 0
    assert signal_engine.execution_intent_sink.duplicates_skipped == 1
    assert signal_engine.execution_intent_sink.last_duplicate_alert_id == original["setup_id"]
    assert signal_engine.execution_intent_sink.last_duplicate_id_field == "setup_id"


def test_execution_intent_outbox_can_allow_duplicate_setup_id_when_explicitly_disabled(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    intents_path = tmp_path / "execution_intents.jsonl"
    original = sample_fresh_entry_alert()
    duplicate_setup = copy.deepcopy(original)
    duplicate_setup["alert_id"] = "new-alert-for-same-setup"
    duplicate_setup["execution_intent"] = engine.build_execution_intent(
        duplicate_setup,
        max_entry_lag_seconds=120.0,
        intent_ttl_seconds=30.0,
    )
    intents_path.write_text(json.dumps(engine.build_execution_intent_record(original)) + "\n", encoding="utf-8")
    cfg["engine"]["alerts_path"] = str(alerts_path)
    cfg["engine"]["execution_intents"] = {
        "enabled": True,
        "path": str(intents_path),
        "fsync": False,
        "fail_on_write_error": False,
        "suppress_duplicate_alert_ids": True,
        "suppress_duplicate_setup_ids": False,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.emit_alert(duplicate_setup)

    captured = capsys.readouterr()
    records = [json.loads(line) for line in intents_path.read_text(encoding="utf-8").splitlines()]
    assert "execution_intents_duplicate_setup_id_skipped" not in captured.out
    assert len(records) == 2
    assert records[0]["setup_id"] == records[1]["setup_id"]
    assert records[0]["alert_id"] != records[1]["alert_id"]
    assert signal_engine.execution_intent_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.duplicates_skipped == 0


def test_execution_intent_outbox_does_not_suppress_older_record_schema_version(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    intents_path = tmp_path / "execution_intents.jsonl"
    alert = sample_fresh_entry_alert()
    old_record = engine.build_execution_intent_record(alert)
    old_record["record_schema_version"] = "execution_intent_record.v1"
    old_record["execution_intent"]["schema_version"] = "execution_intent.v1"
    intents_path.write_text(json.dumps(old_record) + "\n", encoding="utf-8")
    cfg["engine"]["alerts_path"] = str(alerts_path)
    cfg["engine"]["execution_intents"] = {
        "enabled": True,
        "path": str(intents_path),
        "fsync": False,
        "fail_on_write_error": False,
        "suppress_duplicate_alert_ids": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.emit_alert(copy.deepcopy(alert))

    captured = capsys.readouterr()
    records = [json.loads(line) for line in intents_path.read_text(encoding="utf-8").splitlines()]
    assert "execution_intents_duplicate_alert_id_skipped" not in captured.out
    assert len(records) == 2
    assert records[0]["record_schema_version"] == "execution_intent_record.v1"
    assert records[1]["record_schema_version"] == engine.EXECUTION_INTENT_RECORD_VERSION
    assert records[1]["execution_intent"]["schema_version"] == engine.EXECUTION_INTENT_VERSION
    assert signal_engine.execution_intent_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.duplicates_skipped == 0


def test_execution_intent_outbox_suppresses_duplicate_alert_id_in_same_run(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    intents_path = tmp_path / "execution_intents.jsonl"
    cfg["engine"]["alerts_path"] = None
    cfg["engine"]["execution_intents"] = {
        "enabled": True,
        "path": str(intents_path),
        "fsync": False,
        "fail_on_write_error": False,
        "suppress_duplicate_alert_ids": True,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    alert = sample_fresh_entry_alert()

    signal_engine.emit_alert(copy.deepcopy(alert))
    signal_engine.emit_alert(copy.deepcopy(alert))

    records = [json.loads(line) for line in intents_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert signal_engine.execution_intent_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.duplicates_skipped == 1
    assert signal_engine.alert_count == 2


def test_preflight_reports_nonfatal_execution_intent_duplicate_index_errors(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    intents_path = tmp_path / "execution_intents.jsonl"
    alert = sample_fresh_entry_alert()
    intents_path.write_text(
        json.dumps(engine.build_execution_intent_record(alert)) + "\n{not-json\n",
        encoding="utf-8",
    )
    cfg["engine"]["execution_intents"] = {
        "enabled": True,
        "path": str(intents_path),
        "fsync": False,
        "fail_on_write_error": False,
        "suppress_duplicate_alert_ids": True,
        "suppress_duplicate_setup_ids": True,
    }

    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    report = signal_engine.preflight_report()

    captured = capsys.readouterr()
    assert "execution_intents_duplicate_index_malformed_lines" in captured.out
    assert report["execution_intents"]["loaded_existing_duplicate_ids"] == 2
    assert report["execution_intents"]["duplicate_index_last_error_type"] == "MalformedJSONL"
    assert "malformed line" in report["execution_intents"]["duplicate_index_last_error"]
    assert report["execution_intents"]["duplicate_index_last_error_utc"] is not None


def test_execution_intent_duplicate_index_can_fail_fast(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    bad_intents_path = tmp_path / "execution_intents_path_is_a_directory"
    bad_intents_path.mkdir()
    cfg["engine"]["execution_intents"] = {
        "enabled": True,
        "path": str(bad_intents_path),
        "fsync": False,
        "fail_on_write_error": True,
        "suppress_duplicate_alert_ids": True,
    }

    with pytest.raises(RuntimeError, match="Failed to index existing JSONL alert ids"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_emit_alert_reports_execution_intent_write_failure_without_crashing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    bad_intents_path = tmp_path / "execution_intents_path_is_a_directory"
    bad_intents_path.mkdir()
    cfg["engine"]["alerts_path"] = str(alerts_path)
    cfg["engine"]["execution_intents"] = {
        "enabled": True,
        "path": str(bad_intents_path),
        "fsync": False,
        "fail_on_write_error": False,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    signal_engine.emit_alert(sample_fresh_entry_alert())

    captured = capsys.readouterr()
    assert "ENTRY_SIGNAL" in captured.out
    assert "SYSTEM_ALERT" in captured.out
    assert "execution_intent_write_failed" in captured.out
    assert signal_engine.alert_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.writes_succeeded == 0
    assert signal_engine.execution_intent_sink.writes_failed == 1
    assert signal_engine.execution_intent_sink.last_error_type is not None


def test_emit_alert_can_fail_fast_on_execution_intent_write_error(tmp_path: Path) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    bad_intents_path = tmp_path / "execution_intents_path_is_a_directory"
    bad_intents_path.mkdir()
    cfg["engine"]["alerts_path"] = str(alerts_path)
    cfg["engine"]["execution_intents"] = {
        "enabled": True,
        "path": str(bad_intents_path),
        "fsync": False,
        "fail_on_write_error": True,
        "suppress_duplicate_alert_ids": False,
        "suppress_duplicate_setup_ids": False,
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Execution intent write failed"):
        signal_engine.emit_alert(sample_fresh_entry_alert())

    assert signal_engine.alert_count == 1
    assert signal_engine.alert_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.writes_failed == 1


def test_bar_extreme_stop_preview_does_not_need_entry_price() -> None:
    strategy = engine.DeltaIntervalStrategy(
        {
            "params": {
                "stop_mode": "bar_extreme",
                "stop_points": 1.0,
                "target_r_multiple": 1.0,
            }
        }
    )

    long_signal = engine.EngineSignal(
        direction="long",
        level_type="test",
        metadata={"latest_completed_bar_low": 4999.25, "latest_completed_bar_high": 5001.25},
    )
    short_signal = engine.EngineSignal(
        direction="short",
        level_type="test",
        metadata={"latest_completed_bar_low": 4999.25, "latest_completed_bar_high": 5001.25},
    )

    assert strategy.stop_price(long_signal, "long", 0.25, entry_price=None) == 4999.25
    assert strategy.stop_price(short_signal, "short", 0.25, entry_price=None) == 5001.25


def test_live_health_alerts_detect_and_throttle_no_records() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    cfg = {
        "no_records_alert_seconds": 30,
        "no_trade_ticks_alert_seconds": 0,
        "no_completed_bar_alert_seconds": 0,
        "alert_repeat_seconds": 120,
    }

    alerts = engine.live_health_alerts(health, cfg, now=131.0, connected=True)
    assert [alert["event"] for alert in alerts] == ["live_no_records_received"]

    throttled = engine.live_health_alerts(health, cfg, now=150.0, connected=True)
    assert throttled == []

    repeated = engine.live_health_alerts(health, cfg, now=252.0, connected=True)
    assert [alert["event"] for alert in repeated] == ["live_no_records_received"]


def test_live_health_alert_stop_enabled_maps_events_to_config_keys() -> None:
    cfg = {
        "stop_on_disconnect": True,
        "stop_on_no_records": True,
        "stop_on_no_trade_ticks": True,
        "stop_on_no_completed_bars": True,
        "stop_on_no_evaluable_strategies": True,
        "stop_on_partial_unevaluable_strategies": True,
        "stop_on_stale_trade_tick": True,
        "stop_on_future_trade_tick": True,
        "stop_on_unmatched_contract_symbol": True,
    }

    assert engine.live_health_alert_stop_enabled("live_disconnected", cfg) is True
    assert engine.live_health_alert_stop_enabled("live_no_records_received", cfg) is True
    assert engine.live_health_alert_stop_enabled("live_no_trade_ticks", cfg) is True
    assert engine.live_health_alert_stop_enabled("live_no_completed_bars", cfg) is True
    assert engine.live_health_alert_stop_enabled("live_no_evaluable_strategies", cfg) is True
    assert engine.live_health_alert_stop_enabled("live_partially_unevaluable_strategies", cfg) is True
    assert engine.live_health_alert_stop_enabled("live_trade_tick_stale_timestamp", cfg) is True
    assert engine.live_health_alert_stop_enabled("live_trade_tick_future_timestamp", cfg) is True
    assert engine.live_health_alert_stop_enabled("live_unmatched_contract_symbol_ignored", cfg) is True
    assert engine.live_health_alert_stop_enabled("live_unknown", cfg) is False
    assert engine.live_health_alert_stop_enabled("live_no_records_received", {}) is False


def test_live_health_alerts_detect_no_completed_bars_after_ticks() -> None:
    health = engine.LiveHealth(started_monotonic=100.0, records_received=5, ticks_received=5)
    health.last_record_monotonic = 150.0
    health.last_tick_monotonic = 150.0
    cfg = {
        "no_records_alert_seconds": 0,
        "no_trade_ticks_alert_seconds": 0,
        "no_completed_bar_alert_seconds": 180,
        "alert_repeat_seconds": 60,
    }

    alerts = engine.live_health_alerts(health, cfg, now=281.0, connected=True)
    assert [alert["event"] for alert in alerts] == ["live_no_completed_bars"]
    assert alerts[0]["trade_ticks_received"] == 5


def test_live_strategy_evaluation_summary_detects_no_new_evaluable_rows() -> None:
    strategy_health = [
        {
            "strategy_id": "alpha",
            "disabled": False,
            "processed_strategy_row_count": 10,
            "evaluated_strategy_row_count": 3,
            "feature_quality_skip_count": 0,
            "runtime_error_count": 0,
        },
        {
            "strategy_id": "beta",
            "disabled": False,
            "processed_strategy_row_count": 2,
            "evaluated_strategy_row_count": 0,
            "feature_quality_skip_count": 2,
            "runtime_error_count": 0,
        },
    ]
    baseline = {
        "processed_strategy_rows": 10,
        "evaluated_strategy_rows": 3,
        "per_strategy_processed_rows": {"alpha": 10},
        "per_strategy_evaluated_rows": {"alpha": 3},
    }

    summary = engine.live_strategy_evaluation_summary(
        strategy_health,
        completed_source_bars=5,
        data_plan={"warmup": {"recommended_source_bars": 5}},
        live_cfg={},
        baseline=baseline,
    )

    assert summary["new_processed_strategy_rows"] == 2
    assert summary["new_evaluated_strategy_rows"] == 0
    assert summary["alert_after_completed_source_bars"] == 5
    assert summary["alert_threshold_source"] == "data_plan.recommended_source_bars"
    assert summary["no_evaluable_strategies"] is True
    assert summary["partially_unevaluable_strategies"] is False
    assert summary["unevaluated_active_strategy_ids"] == ["alpha", "beta"]
    assert summary["feature_quality_skips"] == 2


def test_live_strategy_evaluation_summary_detects_partial_unevaluable_strategy() -> None:
    strategy_health = [
        {
            "strategy_id": "alpha",
            "disabled": False,
            "processed_strategy_row_count": 11,
            "evaluated_strategy_row_count": 4,
            "feature_quality_skip_count": 0,
            "runtime_error_count": 0,
        },
        {
            "strategy_id": "beta",
            "disabled": False,
            "processed_strategy_row_count": 2,
            "evaluated_strategy_row_count": 0,
            "feature_quality_skip_count": 2,
            "runtime_error_count": 0,
        },
    ]
    baseline = {
        "processed_strategy_rows": 10,
        "evaluated_strategy_rows": 3,
        "per_strategy_processed_rows": {"alpha": 10},
        "per_strategy_evaluated_rows": {"alpha": 3},
    }

    summary = engine.live_strategy_evaluation_summary(
        strategy_health,
        completed_source_bars=5,
        data_plan={"warmup": {"recommended_source_bars": 5}},
        live_cfg={},
        baseline=baseline,
    )

    assert summary["new_processed_strategy_rows"] == 3
    assert summary["new_evaluated_strategy_rows"] == 1
    assert summary["per_strategy_new_evaluated_rows"] == {"alpha": 1, "beta": 0}
    assert summary["no_evaluable_strategies"] is False
    assert summary["partially_unevaluable_strategies"] is True
    assert summary["unevaluated_active_strategy_ids"] == ["beta"]


def test_live_health_alerts_detect_no_evaluable_strategies() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    cfg = {
        "alert_repeat_seconds": 120,
        "max_trade_tick_lag_seconds": 0,
        "max_trade_tick_future_seconds": 0,
        "no_records_alert_seconds": 0,
        "no_trade_ticks_alert_seconds": 0,
        "no_completed_bar_alert_seconds": 0,
    }
    strategy_evaluation = {
        "no_evaluable_strategies": True,
        "completed_source_bars": 5,
        "alert_after_completed_source_bars": 5,
        "alert_threshold_source": "data_plan.recommended_source_bars",
        "active_strategy_count": 2,
        "new_processed_strategy_rows": 2,
        "new_evaluated_strategy_rows": 0,
        "unevaluated_active_strategy_ids": ["alpha", "beta"],
        "feature_quality_skips": 2,
        "runtime_errors": 0,
    }

    alerts = engine.live_health_alerts(
        health,
        cfg,
        now=200.0,
        connected=True,
        strategy_evaluation=strategy_evaluation,
    )
    throttled = engine.live_health_alerts(
        health,
        cfg,
        now=250.0,
        connected=True,
        strategy_evaluation=strategy_evaluation,
    )

    assert [alert["event"] for alert in alerts] == ["live_no_evaluable_strategies"]
    assert alerts[0]["new_evaluated_strategy_rows"] == 0
    assert alerts[0]["unevaluated_active_strategy_ids"] == ["alpha", "beta"]
    assert "unable to produce valid setup or entry signals" in alerts[0]["impact"]
    assert throttled == []


def test_live_health_alerts_detect_partially_unevaluable_strategies() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    cfg = {
        "alert_repeat_seconds": 120,
        "max_trade_tick_lag_seconds": 0,
        "max_trade_tick_future_seconds": 0,
        "no_records_alert_seconds": 0,
        "no_trade_ticks_alert_seconds": 0,
        "no_completed_bar_alert_seconds": 0,
    }
    strategy_evaluation = {
        "no_evaluable_strategies": False,
        "partially_unevaluable_strategies": True,
        "completed_source_bars": 5,
        "alert_after_completed_source_bars": 5,
        "alert_threshold_source": "data_plan.recommended_source_bars",
        "active_strategy_count": 2,
        "new_processed_strategy_rows": 3,
        "new_evaluated_strategy_rows": 1,
        "per_strategy_new_evaluated_rows": {"alpha": 1, "beta": 0},
        "unevaluated_active_strategy_ids": ["beta"],
        "feature_quality_skips": 2,
        "runtime_errors": 0,
    }

    alerts = engine.live_health_alerts(
        health,
        cfg,
        now=200.0,
        connected=True,
        strategy_evaluation=strategy_evaluation,
    )
    throttled = engine.live_health_alerts(
        health,
        cfg,
        now=250.0,
        connected=True,
        strategy_evaluation=strategy_evaluation,
    )

    assert [alert["event"] for alert in alerts] == ["live_partially_unevaluable_strategies"]
    assert alerts[0]["per_strategy_new_evaluated_rows"] == {"alpha": 1, "beta": 0}
    assert alerts[0]["unevaluated_active_strategy_ids"] == ["beta"]
    assert "only partially covering" in alerts[0]["impact"]
    assert throttled == []


def test_live_tick_clock_health_tracks_lag_and_future_skew() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)

    engine.update_live_tick_clock_health(
        health,
        engine.TradeTick(
            timestamp_utc=ts("2026-06-11 13:30:00"),
            price=5000.0,
            size=1,
            side="B",
            contract_symbol="ESM6",
        ),
        received_at_utc=ts("2026-06-11 13:30:12"),
    )
    engine.update_live_tick_clock_health(
        health,
        engine.TradeTick(
            timestamp_utc=ts("2026-06-11 13:30:20"),
            price=5000.0,
            size=1,
            side="B",
            contract_symbol="ESM6",
        ),
        received_at_utc=ts("2026-06-11 13:30:18"),
    )

    assert health.last_tick_event_timestamp_utc == "2026-06-11T13:30:20+00:00"
    assert health.last_tick_clock_lag_seconds == -2.0
    assert health.max_tick_clock_lag_seconds == 12.0
    assert health.max_tick_clock_future_seconds == 2.0


def test_live_health_alerts_detect_stale_tick_timestamp() -> None:
    health = engine.LiveHealth(
        started_monotonic=100.0,
        ticks_received=10,
        last_tick_clock_lag_seconds=12.5,
        last_tick_event_timestamp_utc="2026-06-11T13:30:00+00:00",
    )
    cfg = {
        "alert_repeat_seconds": 120,
        "max_trade_tick_lag_seconds": 10,
        "max_trade_tick_future_seconds": 2,
        "no_records_alert_seconds": 0,
        "no_trade_ticks_alert_seconds": 0,
        "no_completed_bar_alert_seconds": 0,
    }

    alerts = engine.live_health_alerts(health, cfg, now=200.0, connected=True)

    assert [alert["event"] for alert in alerts] == ["live_trade_tick_stale_timestamp"]
    assert alerts[0]["lag_seconds"] == 12.5


def test_live_health_alerts_detect_unmatched_contract_symbols() -> None:
    health = engine.LiveHealth(
        started_monotonic=100.0,
        accepted_contract_ticks={"ESM6": 2},
        unmatched_contract_ticks_ignored=1,
        unmatched_contract_ticks={"ESM6-ESU6": 1},
        last_unmatched_contract_tick={"contract_symbol": "ESM6-ESU6"},
        contract_symbol_regex=r"^ES[HMUZ]\d$",
    )
    cfg = {
        "alert_repeat_seconds": 120,
        "max_trade_tick_lag_seconds": 0,
        "max_trade_tick_future_seconds": 0,
        "no_records_alert_seconds": 0,
        "no_trade_ticks_alert_seconds": 0,
        "no_completed_bar_alert_seconds": 0,
    }

    alerts = engine.live_health_alerts(health, cfg, now=200.0, connected=True)
    throttled = engine.live_health_alerts(health, cfg, now=250.0, connected=True)

    assert [alert["event"] for alert in alerts] == ["live_unmatched_contract_symbol_ignored"]
    assert alerts[0]["unmatched_contract_ticks"] == {"ESM6-ESU6": 1}
    assert alerts[0]["accepted_contract_ticks"] == {"ESM6": 2}
    assert throttled == []


def test_live_health_alerts_detect_future_tick_timestamp_even_outside_session() -> None:
    health = engine.LiveHealth(
        started_monotonic=100.0,
        ticks_received=10,
        last_tick_clock_lag_seconds=-3.25,
        last_tick_event_timestamp_utc="2026-06-11T13:30:03.250000+00:00",
    )
    cfg = {
        "alert_repeat_seconds": 120,
        "max_trade_tick_lag_seconds": 10,
        "max_trade_tick_future_seconds": 2,
        "no_records_alert_seconds": 30,
        "no_trade_ticks_alert_seconds": 60,
        "no_completed_bar_alert_seconds": 180,
        "session_aware_stale_alerts": True,
        "stale_alert_session_start": "09:30:00",
        "stale_alert_session_end": "16:00:00",
        "stale_alert_session_timezone": "America/New_York",
        "stale_alert_weekdays": [0, 1, 2, 3, 4],
    }
    market_session = engine.live_market_session_state(
        cfg,
        {"timezone": "America/New_York"},
        now_utc=ts("2026-06-11 23:00:00"),
    )

    alerts = engine.live_health_alerts(health, cfg, now=200.0, connected=True, market_session=market_session)

    assert market_session["suppress_stale_alerts"] is True
    assert [alert["event"] for alert in alerts] == ["live_trade_tick_future_timestamp"]
    assert alerts[0]["future_seconds"] == 3.25


def test_live_health_suppresses_stale_alerts_outside_configured_session() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    cfg = {
        "no_records_alert_seconds": 30,
        "no_trade_ticks_alert_seconds": 60,
        "no_completed_bar_alert_seconds": 180,
        "alert_repeat_seconds": 120,
        "session_aware_stale_alerts": True,
        "stale_alert_session_start": "09:30:00",
        "stale_alert_session_end": "16:00:00",
        "stale_alert_session_timezone": "America/New_York",
        "stale_alert_weekdays": [0, 1, 2, 3, 4],
    }
    market_session = engine.live_market_session_state(
        cfg,
        {"timezone": "America/New_York"},
        now_utc=ts("2026-06-11 23:00:00"),
    )

    alerts = engine.live_health_alerts(health, cfg, now=200.0, connected=True, market_session=market_session)

    assert market_session["is_open"] is False
    assert market_session["suppress_stale_alerts"] is True
    assert alerts == []


def test_live_health_emits_stale_alerts_inside_configured_session() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    cfg = {
        "no_records_alert_seconds": 30,
        "no_trade_ticks_alert_seconds": 0,
        "no_completed_bar_alert_seconds": 0,
        "alert_repeat_seconds": 120,
        "session_aware_stale_alerts": True,
        "stale_alert_session_start": "09:30:00",
        "stale_alert_session_end": "16:00:00",
        "stale_alert_session_timezone": "America/New_York",
        "stale_alert_weekdays": [0, 1, 2, 3, 4],
    }
    market_session = engine.live_market_session_state(
        cfg,
        {"timezone": "America/New_York"},
        now_utc=ts("2026-06-11 14:00:00"),
    )

    alerts = engine.live_health_alerts(health, cfg, now=200.0, connected=True, market_session=market_session)

    assert market_session["is_open"] is True
    assert market_session["suppress_stale_alerts"] is False
    assert [alert["event"] for alert in alerts] == ["live_no_records_received"]


def test_live_status_payload_reports_ages_and_counts() -> None:
    health = engine.LiveHealth(
        started_monotonic=100.0,
        last_record_monotonic=125.0,
        last_tick_monotonic=126.0,
        last_completed_bar_monotonic=160.0,
        last_tick_event_timestamp_utc="2026-06-11T13:30:00+00:00",
        last_tick_clock_lag_seconds=1.23456,
        max_tick_clock_lag_seconds=2.34567,
        max_tick_clock_future_seconds=0.5,
        records_received=10,
        ticks_received=8,
        completed_bars=2,
        heartbeat_flushed_bars=1,
        dropped_partial_bars=1,
        late_trade_ticks_ignored=3,
        last_late_trade_tick={"contract_symbol": "ESM6", "minute_utc": "2026-06-11T13:30:00+00:00"},
        accepted_contract_ticks={"ESM6": 10, "ESU6": 2},
        unmatched_contract_ticks_ignored=4,
        unmatched_contract_ticks={"ESM6-ESU6": 3, "NQM6": 1},
        last_unmatched_contract_tick={"contract_symbol": "ESM6-ESU6"},
        contract_symbol_regex=r"^ES[HMUZ]\d$",
    )

    payload = engine.live_status_payload(
        health,
        now=170.0,
        connected=True,
        entry_alerts=3,
        pending_signals=4,
        strategy_evaluation={"no_evaluable_strategies": False, "new_evaluated_strategy_rows": 2},
        source_bar_quality={"source_bar_quality_drops": 2, "last_source_bar_quality_report": {"bars_dropped": 2}},
    )

    assert payload["connected"] is True
    assert payload["uptime_seconds"] == 70.0
    assert payload["records_received"] == 10
    assert payload["trade_ticks_received"] == 8
    assert payload["completed_source_bars"] == 2
    assert payload["heartbeat_flushed_source_bars"] == 1
    assert payload["dropped_partial_bars"] == 1
    assert payload["accepted_trade_ticks"] == 12
    assert payload["late_trade_ticks_ignored"] == 3
    assert payload["last_late_trade_tick"] == {
        "contract_symbol": "ESM6",
        "minute_utc": "2026-06-11T13:30:00+00:00",
    }
    assert payload["contract_symbol_regex"] == r"^ES[HMUZ]\d$"
    assert payload["accepted_contract_ticks"] == {"ESM6": 10, "ESU6": 2}
    assert payload["unmatched_contract_ticks_ignored"] == 4
    assert payload["unmatched_contract_ticks"] == {"ESM6-ESU6": 3, "NQM6": 1}
    assert payload["last_unmatched_contract_tick"] == {"contract_symbol": "ESM6-ESU6"}
    assert payload["seconds_since_last_record"] == 45.0
    assert payload["seconds_since_last_trade_tick"] == 44.0
    assert payload["seconds_since_last_completed_bar"] == 10.0
    assert payload["last_trade_tick_event_timestamp_utc"] == "2026-06-11T13:30:00+00:00"
    assert payload["last_trade_tick_clock_lag_seconds"] == 1.235
    assert payload["max_trade_tick_clock_lag_seconds"] == 2.346
    assert payload["max_trade_tick_clock_future_seconds"] == 0.5
    assert payload["entry_alerts"] == 3
    assert payload["pending_signals"] == 4
    assert payload["strategy_evaluation"] == {"no_evaluable_strategies": False, "new_evaluated_strategy_rows": 2}
    assert payload["source_bar_quality"] == {
        "source_bar_quality_drops": 2,
        "last_source_bar_quality_report": {"bars_dropped": 2},
    }


def test_live_status_payload_includes_alert_sink_health() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    sink = engine.AlertSinkHealth(
        writes_succeeded=2,
        writes_failed=1,
        duplicates_skipped=4,
        last_success_utc="2026-06-11T13:31:00+00:00",
        last_duplicate_utc="2026-06-11T13:31:30+00:00",
        last_duplicate_alert_id="abc",
        last_duplicate_id_field="alert_id",
        last_error_utc="2026-06-11T13:32:00+00:00",
        last_error_type="OSError",
        last_error="disk full",
    )

    payload = engine.live_status_payload(
        health,
        now=170.0,
        connected=True,
        entry_alerts=3,
        pending_signals=4,
        alert_sink=sink,
    )

    assert payload["alert_file_writes_succeeded"] == 2
    assert payload["alert_file_writes_failed"] == 1
    assert payload["alert_file_duplicates_skipped"] == 4
    assert payload["alert_file_last_duplicate_alert_id"] == "abc"
    assert payload["alert_file_last_duplicate_id_field"] == "alert_id"
    assert payload["alert_file_last_error_type"] == "OSError"
    assert payload["alert_file_last_error"] == "disk full"


def test_live_status_payload_includes_setup_alert_sink_health() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    sink = engine.AlertSinkHealth(
        writes_succeeded=5,
        writes_failed=1,
        duplicates_skipped=2,
        last_success_utc="2026-06-11T13:31:00+00:00",
        last_duplicate_utc="2026-06-11T13:31:30+00:00",
        last_duplicate_alert_id="setup-abc",
        last_duplicate_id_field="setup_id",
        last_error_utc="2026-06-11T13:32:00+00:00",
        last_error_type="OSError",
        last_error="read only",
    )

    payload = engine.live_status_payload(
        health,
        now=170.0,
        connected=True,
        entry_alerts=3,
        pending_signals=4,
        setup_notice_sink=sink,
    )

    assert payload["setup_alert_writes_succeeded"] == 5
    assert payload["setup_alert_writes_failed"] == 1
    assert payload["setup_alert_duplicates_skipped"] == 2
    assert payload["setup_alert_last_duplicate_setup_id"] == "setup-abc"
    assert payload["setup_alert_last_duplicate_id_field"] == "setup_id"
    assert payload["setup_alert_last_error_type"] == "OSError"
    assert payload["setup_alert_last_error"] == "read only"


def test_live_status_payload_includes_execution_intent_sink_health() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    sink = engine.AlertSinkHealth(
        writes_succeeded=3,
        writes_failed=1,
        duplicates_skipped=2,
        freshness_skipped=1,
        last_success_utc="2026-06-11T13:31:00+00:00",
        last_duplicate_utc="2026-06-11T13:31:30+00:00",
        last_duplicate_alert_id="xyz",
        last_duplicate_id_field="setup_id",
        last_freshness_skip_utc="2026-06-11T13:32:30+00:00",
        last_freshness_skip_alert_id="stale-xyz",
        last_freshness_skip_reason="expired",
        last_error_utc="2026-06-11T13:32:00+00:00",
        last_error_type="OSError",
        last_error="permission denied",
    )

    payload = engine.live_status_payload(
        health,
        now=170.0,
        connected=True,
        entry_alerts=3,
        pending_signals=4,
        execution_intent_sink=sink,
    )

    assert payload["execution_intent_writes_succeeded"] == 3
    assert payload["execution_intent_writes_failed"] == 1
    assert payload["execution_intent_duplicates_skipped"] == 2
    assert payload["execution_intent_freshness_skipped"] == 1
    assert payload["execution_intent_last_duplicate_alert_id"] == "xyz"
    assert payload["execution_intent_last_duplicate_id_field"] == "setup_id"
    assert payload["execution_intent_last_freshness_skip_alert_id"] == "stale-xyz"
    assert payload["execution_intent_last_freshness_skip_reason"] == "expired"
    assert payload["execution_intent_last_error_type"] == "OSError"
    assert payload["execution_intent_last_error"] == "permission denied"


def test_live_status_payload_includes_strategy_health() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    strategy_health = [
        {"strategy_id": "ok", "disabled": False, "runtime_error_count": 0},
        {"strategy_id": "bad", "disabled": True, "runtime_error_count": 1},
    ]

    payload = engine.live_status_payload(
        health,
        now=170.0,
        connected=True,
        entry_alerts=0,
        pending_signals=0,
        strategy_health=strategy_health,
    )

    assert payload["active_strategy_count"] == 1
    assert payload["disabled_strategy_count"] == 1
    assert payload["strategy_health"] == strategy_health


def test_live_status_payload_includes_market_session() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    market_session = {
        "enabled": True,
        "is_open": False,
        "suppress_stale_alerts": True,
        "reason": "outside_configured_stale_alert_session",
    }

    payload = engine.live_status_payload(
        health,
        now=170.0,
        connected=True,
        entry_alerts=0,
        pending_signals=0,
        market_session=market_session,
    )

    assert payload["market_session"] == market_session


def test_live_status_payload_includes_pending_status() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    pending_status = {
        "count": 1,
        "oldest_due_timestamp_utc": "2026-06-11T13:31:00+00:00",
        "oldest_seconds_until_due": -30.0,
        "overdue_count": 1,
    }

    payload = engine.live_status_payload(
        health,
        now=170.0,
        connected=True,
        entry_alerts=0,
        pending_signals=1,
        pending_status=pending_status,
    )

    assert payload["pending_status"] == pending_status


def test_live_status_payload_includes_operator_sound_health() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    operator_sound = {
        "enabled": True,
        "attempts": 2,
        "commands_started": 1,
        "command_failures": 1,
    }

    payload = engine.live_status_payload(
        health,
        now=170.0,
        connected=True,
        entry_alerts=0,
        pending_signals=0,
        operator_sound=operator_sound,
    )

    assert payload["operator_sound"] == operator_sound


def test_live_status_payload_includes_source_contract_filter_health() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    source_contract_filter = {
        "enabled": True,
        "contract_symbol_regex": r"^ES[HMUZ]\d$",
        "source_contract_filter_drops": 2,
        "last_source_contract_filter_report": {"dropped_contracts": {"ESM6-ESU6": 2}},
    }

    payload = engine.live_status_payload(
        health,
        now=170.0,
        connected=True,
        entry_alerts=0,
        pending_signals=0,
        source_contract_filter=source_contract_filter,
    )

    assert payload["source_contract_filter"] == source_contract_filter


def test_price_vs_quote_requires_mbp1_schema_in_preflight() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["delta_method"] = "price_vs_quote"
    cfg["databento"]["schema"] = "trades"

    with pytest.raises(ValueError, match="requires live databento.schema=mbp-1"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_invalid_contract_symbol_regex_fails_preflight() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["contract_symbol_regex"] = "["

    with pytest.raises(ValueError, match="contract_symbol_regex"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_active_campaign_data_plan_requires_orderflow_warmup() -> None:
    cfg = load_execution_config("signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "signal_engine.example.yaml")
    plan = signal_engine.data_plan

    assert plan["required_live_schema"] == "trades"
    assert "trade_orderflow" in plan["feature_families"]
    assert "same_clock_ranks" in plan["feature_families"]
    assert "signed_volume" in plan["source_columns"]
    assert "trades" in plan["source_columns"]
    assert plan["warmup"]["min_warmup_sessions"] == 42
    assert plan["warmup"]["recommended_source_bars"] >= 42 * 390
    live_field_labels = {item["label"] for item in plan["required_live_field_groups"]}
    assert live_field_labels == {
        "event timestamp",
        "trade price",
        "trade size",
        "aggressor side",
        "contract identity",
    }


def test_quote_delta_data_plan_exposes_mbp1_live_field_requirements() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["schema"] = "mbp-1"
    cfg["databento"]["delta_method"] = "price_vs_quote"

    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    plan = signal_engine.preflight_report()["data_plan"]

    assert plan["configured_schema"] == "mbp-1"
    assert plan["required_live_schema"] == "mbp-1"
    live_field_labels = {item["label"] for item in plan["required_live_field_groups"]}
    assert live_field_labels == {
        "event timestamp",
        "trade price",
        "trade size",
        "trade action",
        "best bid price",
        "best ask price",
        "contract identity",
    }


def test_flow_column_large_trade_reference_infers_required_live_threshold(tmp_path: Path) -> None:
    strategy_path = tmp_path / "large_flow_strategy.yaml"
    write_large_flow_strategy_config(strategy_path)
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["large_trade_sizes"] = []
    cfg["databento"]["historical"] = {"enabled": False}
    cfg["strategies"] = [{"config": str(strategy_path), "enabled": True}]

    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    plan = signal_engine.data_plan

    assert plan["large_trade_sizes"] == [20]
    assert engine.effective_large_trade_sizes(signal_engine) == [20]
    assert "large20_signed_volume" in plan["source_columns"]
    assert "large20_volume" in plan["source_columns"]
    assert "trade_orderflow_large20_imbalance_5" in plan["derived_feature_columns"]
    runtime = signal_engine.strategies[0]
    assert runtime.data_config["trade_orderflow_features"]["large_trade_sizes"] == [20]
    assert any(
        "Inferred missing data.trade_orderflow_features.large_trade_sizes" in warning
        for warning in runtime.warnings
    )


def test_configured_and_inferred_large_trade_sizes_are_merged(tmp_path: Path) -> None:
    strategy_path = tmp_path / "large_flow_strategy.yaml"
    write_large_flow_strategy_config(strategy_path)
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["large_trade_sizes"] = [10]
    cfg["databento"]["historical"] = {"enabled": False}
    cfg["strategies"] = [{"config": str(strategy_path), "enabled": True}]

    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    assert signal_engine.data_plan["large_trade_sizes"] == [20]
    assert engine.effective_large_trade_sizes(signal_engine) == [10, 20]


def test_seed_warmup_audit_warns_when_sessions_are_insufficient(capsys: pytest.CaptureFixture[str]) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    signal_engine.data_plan["warmup"]["min_warmup_sessions"] = 2
    bar = engine.SourceMinuteBar(
        timestamp_utc=ts("2026-06-10 13:30:00"),
        symbol="ES",
        contract_symbol="ESM6",
        open=5000.0,
        high=5000.25,
        low=4999.75,
        close=5000.0,
        volume=10,
        signed_volume=2,
        buy_volume=6,
        sell_volume=4,
        trades=5,
        source="test",
    )

    signal_engine.audit_seed_warmup([bar], source="test_seed")

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "insufficient_warmup_history" in captured.out
    assert '"available_sessions": 1' in captured.out
    assert '"required_sessions": 2' in captured.out


def test_runtime_warmup_audit_fails_when_live_starts_without_seed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Insufficient warmup history for live_startup"):
        signal_engine.audit_runtime_warmup(source="live_startup")

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "insufficient_warmup_history" in captured.out
    assert '"source": "live_startup"' in captured.out
    assert '"available_sessions": 0' in captured.out
    assert '"required_sessions": 42' in captured.out
    assert '"fail_on_insufficient_warmup": true' in captured.out


def test_runtime_warmup_audit_can_warn_when_fail_fast_disabled(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("signal_engine.example.yaml")
    cfg["engine"]["fail_on_insufficient_warmup"] = False
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "signal_engine.example.yaml")

    signal_engine.audit_runtime_warmup(source="live_startup")

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "insufficient_warmup_history" in captured.out
    assert '"source": "live_startup"' in captured.out
    assert '"fail_on_insufficient_warmup": false' in captured.out
