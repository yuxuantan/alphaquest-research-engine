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


def load_execution_config(name: str) -> dict:
    return engine.load_yaml(EXECUTION_DIR / name)


def sample_entry_alert() -> dict:
    alert = {
        "event": "entry_signal",
        "alert_contract_version": engine.ALERT_CONTRACT_VERSION,
        "alert_id": "abc",
        "strategy_id": "dummy",
        "strategy_name": "dummy_delta_interval",
        "strategy_config": "builtin:builtin_delta_interval",
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
    alert["execution_intent"] = engine.build_execution_intent(alert, max_entry_lag_seconds=120)
    return alert


def sample_pending_setup(strategy: object) -> engine.PendingSignal:
    return engine.PendingSignal(
        strategy=strategy,
        row={
            "timestamp": pd.Timestamp("2026-06-11 09:30:00", tz="America/New_York"),
            "timestamp_utc": ts("2026-06-11 13:30:00"),
            "session_date": "2026-06-11",
            "contract_symbol": "ESM6",
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
        return [{"name": "ts_event"}, {"name": "price"}, {"name": "size"}, {"name": "side"}]

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


def test_databento_metadata_check_uses_metadata_only_and_succeeds() -> None:
    cfg = load_execution_config("signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "signal_engine.example.yaml")

    report = engine.check_databento_metadata(signal_engine, client=FakeClient(cost=0.0))

    assert report["ok"] is True
    assert report["timeseries_download_attempted"] is False
    assert report["live_subscription_attempted"] is False
    assert report["checks"]["dataset_range"]["ok"] is True
    assert report["checks"]["schemas"]["ok"] is True
    assert report["checks"]["fields"]["ok"] is True
    assert report["checks"]["symbology"]["ok"] is True
    assert report["checks"]["symbology"]["mapping_count"] == 1
    assert report["checks"]["symbology"]["stype_out"] == "instrument_id"
    assert report["checks"]["historical_cost_guard"]["estimated_cost_usd"] == 0.0


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
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Historical cost guard check failed"):
        engine.check_databento_metadata(signal_engine, client=FakeClient(cost=0.01))


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
        123: "NQM6",
    }

    symbols = engine.resolved_raw_subscription_symbols(
        mapping,
        contract_symbol_regex=r"^ES[HMUZ]\d$",
    )

    assert symbols == ["ESM6", "ESU6"]


def test_run_live_maps_instrument_id_records_to_raw_contract_symbols(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
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


def test_run_live_fails_fast_when_client_disconnects_at_startup(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
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


def test_run_live_short_run_starts_and_stops_cleanly(capsys: pytest.CaptureFixture[str]) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
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
    assert holder["client"].started is True
    assert holder["client"].stopped is True
    assert holder["client"].wait_for_close_timeout == 0.25
    assert holder["client"].subscribe_args == {
        "dataset": "GLBX.MDP3",
        "schema": "trades",
        "symbols": "ES.FUT",
        "stype_in": "parent",
    }


def test_run_live_restores_process_signal_handlers() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["api_key"] = "test-key"
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
    cfg["engine"]["alerts_path"] = str(tmp_path / "entry_signals.jsonl")
    cfg["engine"]["execution_intents"]["enabled"] = False
    cfg["databento"]["live"]["metadata_preflight"] = False
    cfg["databento"]["live"]["resolve_instrument_symbols"] = False
    cfg["databento"]["live"]["startup_grace_seconds"] = 0
    cfg["databento"]["live"]["shutdown_grace_seconds"] = 0
    cfg["databento"]["live"]["maintenance_interval_seconds"] = 0
    cfg["databento"]["live"]["status_interval_seconds"] = 0
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


def test_preflight_rejects_operator_sound_cleanup_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["engine"]["operator"]["sound"]["cleanup_on_exit"] = "true"

    with pytest.raises(ValueError, match="cleanup_on_exit must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


def test_preflight_rejects_historical_cache_metadata_string_boolean_config() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    cfg["databento"]["historical"] = {
        "enabled": True,
        "cache_metadata": {"enabled": "true"},
    }

    with pytest.raises(ValueError, match="enabled must be a YAML boolean"):
        engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")


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
    assert "Entry    : 5,000.25" in readout
    assert "Stop     : 4,999.25" in readout
    assert "Target   : 5,001.25" in readout


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
    assert intent["schema_version"] == engine.EXECUTION_INTENT_VERSION
    assert intent["intent_id"] == alert["alert_id"]
    assert intent["intent_type"] == "entry"
    assert intent["status"] == "ready_for_manual_or_future_router"
    assert intent["order"]["estimated_entry_price"] == alert["entry_price"]
    assert intent["bracket"]["stop_loss_price"] == alert["stop_loss_price"]
    assert intent["bracket"]["take_profit_price"] == alert["take_profit_price"]
    assert intent["risk"]["risk_dollars"] == alert["risk_dollars"]
    assert intent["price_normalization"] == alert["price_normalization"]
    assert alert["price_normalization"]["normalized"] is False


def test_setup_notice_contract_is_valid_and_non_executable() -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")
    pending = sample_pending_setup(signal_engine.strategies[0])

    notice = pending.strategy.build_setup_notice(pending)

    engine.validate_setup_notice_contract(notice)
    assert notice["setup_contract_version"] == engine.SETUP_NOTICE_CONTRACT_VERSION
    assert notice["event"] == "trade_setup"
    assert notice["setup_id"]
    assert notice["direction"] == "long"
    assert notice["side"] == "buy"
    assert notice["due_timestamp_utc"] == "2026-06-11T13:31:00+00:00"
    assert "entry_price" not in notice
    assert "execution_intent" not in notice


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
    engine.validate_setup_notice_contract(notice)
    engine.validate_entry_alert_contract(alert)


def test_entry_alert_contract_rejects_malformed_intent() -> None:
    alert = sample_entry_alert()
    alert["execution_intent"]["quantity"] = 99

    with pytest.raises(ValueError, match="execution_intent.quantity must match"):
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


def test_execution_intent_record_contract_is_valid() -> None:
    alert = sample_entry_alert()

    record = engine.build_execution_intent_record(alert)
    engine.validate_execution_intent_record(record, alert)

    assert record["event"] == "execution_intent_ready"
    assert record["record_schema_version"] == engine.EXECUTION_INTENT_RECORD_VERSION
    assert record["alert_id"] == alert["alert_id"]
    assert record["execution_intent"]["intent_id"] == alert["alert_id"]


def test_execution_intent_record_rejects_mismatched_alert() -> None:
    alert = sample_entry_alert()
    record = engine.build_execution_intent_record(alert)
    record["alert_id"] = "different"

    with pytest.raises(ValueError, match="alert_id must match alert"):
        engine.validate_execution_intent_record(record, alert)


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
    assert status["entry_contract_match_required"] is True
    assert status["entry_contract_mismatch_skips"] == 0
    assert status["last_entry_contract_mismatch"] is None


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
    alert = sample_entry_alert()

    signal_engine.emit_alert(alert)

    assert signal_engine.alert_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.writes_succeeded == 1
    records = [json.loads(line) for line in intents_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["event"] == "execution_intent_ready"
    assert records[0]["alert_id"] == alert["alert_id"]
    assert records[0]["execution_intent"]["intent_id"] == alert["alert_id"]


def test_execution_intent_outbox_suppresses_existing_duplicate_alert_id(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("dummy_delta_signal_engine.example.yaml")
    alerts_path = tmp_path / "entry_signals.jsonl"
    intents_path = tmp_path / "execution_intents.jsonl"
    alert = sample_entry_alert()
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
    alert = sample_entry_alert()

    signal_engine.emit_alert(copy.deepcopy(alert))
    signal_engine.emit_alert(copy.deepcopy(alert))

    records = [json.loads(line) for line in intents_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert signal_engine.execution_intent_sink.writes_succeeded == 1
    assert signal_engine.execution_intent_sink.duplicates_skipped == 1
    assert signal_engine.alert_count == 2


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

    signal_engine.emit_alert(sample_entry_alert())

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
    }
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "dummy_delta_signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Execution intent write failed"):
        signal_engine.emit_alert(sample_entry_alert())

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


def test_live_status_payload_includes_alert_sink_health() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    sink = engine.AlertSinkHealth(
        writes_succeeded=2,
        writes_failed=1,
        duplicates_skipped=4,
        last_success_utc="2026-06-11T13:31:00+00:00",
        last_duplicate_utc="2026-06-11T13:31:30+00:00",
        last_duplicate_alert_id="abc",
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
    assert payload["setup_alert_last_error_type"] == "OSError"
    assert payload["setup_alert_last_error"] == "read only"


def test_live_status_payload_includes_execution_intent_sink_health() -> None:
    health = engine.LiveHealth(started_monotonic=100.0)
    sink = engine.AlertSinkHealth(
        writes_succeeded=3,
        writes_failed=1,
        duplicates_skipped=2,
        last_success_utc="2026-06-11T13:31:00+00:00",
        last_duplicate_utc="2026-06-11T13:31:30+00:00",
        last_duplicate_alert_id="xyz",
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
    assert payload["execution_intent_last_duplicate_alert_id"] == "xyz"
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


def test_runtime_warmup_audit_warns_when_live_starts_without_seed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cfg = load_execution_config("signal_engine.example.yaml")
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "signal_engine.example.yaml")

    signal_engine.audit_runtime_warmup(source="live_startup")

    captured = capsys.readouterr()
    assert "SYSTEM_ALERT" in captured.out
    assert "insufficient_warmup_history" in captured.out
    assert '"source": "live_startup"' in captured.out
    assert '"available_sessions": 0' in captured.out
    assert '"required_sessions": 42' in captured.out


def test_runtime_warmup_audit_can_fail_fast_when_live_starts_without_seed() -> None:
    cfg = load_execution_config("signal_engine.example.yaml")
    cfg["engine"]["fail_on_insufficient_warmup"] = True
    signal_engine = engine.SignalEngine(cfg, EXECUTION_DIR / "signal_engine.example.yaml")

    with pytest.raises(RuntimeError, match="Insufficient warmup history for live_startup"):
        signal_engine.audit_runtime_warmup(source="live_startup")
