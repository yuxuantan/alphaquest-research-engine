#!/usr/bin/env python3
"""
Databento-backed ES trading signal engine.

This script is an alerting engine, not an order router. It reads one or more
campaign-style strategy YAML files, warms them from historical Databento trades
or cached 1-minute orderflow bars, then watches live Databento trade ticks. When
a strategy signals on a completed bar, the engine emits an actionable
ENTRY_SIGNAL on the next tradable tick/open with direction, size, stop, and
target.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import math
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover - runtime dependency guard.
    pd = None
    PANDAS_IMPORT_ERROR: ImportError | None = exc
else:
    PANDAS_IMPORT_ERROR = None

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime dependency guard.
    yaml = None
    YAML_IMPORT_ERROR: ImportError | None = exc
else:
    YAML_IMPORT_ERROR = None


DEFAULT_CONFIG = "signal_engine.example.yaml"
DEFAULT_TIMEZONE = "America/New_York"
DEFAULT_DATASET = "GLBX.MDP3"
DEFAULT_SCHEMA = "trades"
DEFAULT_SYMBOL = "ES"
DEFAULT_DATABENTO_SYMBOLS = "ES.FUT"
DEFAULT_STYPE_IN = "parent"
DEFAULT_STYPE_OUT = "raw_symbol"
DEFAULT_ALERT_PREFIX = "ENTRY_SIGNAL"
PROJECT_FILE_REFERENCE_KEYS = {
    "cache_dir",
    "data_dir",
    "directory",
    "dir",
    "feature_file",
    "file",
    "output_dir",
    "path",
    "raw_dir",
    "raw_parquet",
    "roll_calendar",
}


@dataclass(frozen=True)
class TradeTick:
    timestamp_utc: Any
    price: float
    size: float
    side: str
    contract_symbol: str
    action: str = "T"


@dataclass(frozen=True)
class SourceMinuteBar:
    timestamp_utc: Any
    symbol: str
    contract_symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    signed_volume: float
    buy_volume: float
    sell_volume: float
    trades: int
    large: dict[str, float] = field(default_factory=dict)
    source: str = ""

    def key(self) -> tuple[int, str]:
        return (int(self.timestamp_utc.timestamp()), self.contract_symbol)


@dataclass
class MinuteAccumulator:
    minute_utc: Any
    contract_symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    signed_volume: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0
    trades: int = 0
    large: dict[str, float] = field(default_factory=dict)

    @classmethod
    def start(cls, tick: TradeTick, large_trade_sizes: list[int]) -> "MinuteAccumulator":
        large = {}
        for threshold in large_trade_sizes:
            large[f"large{threshold}_signed_volume"] = 0.0
            large[f"large{threshold}_volume"] = 0.0
        acc = cls(
            minute_utc=tick.timestamp_utc.floor("min"),
            contract_symbol=tick.contract_symbol,
            open=tick.price,
            high=tick.price,
            low=tick.price,
            close=tick.price,
            large=large,
        )
        acc.add(tick, large_trade_sizes)
        return acc

    def add(self, tick: TradeTick, large_trade_sizes: list[int]) -> None:
        self.high = max(self.high, tick.price)
        self.low = min(self.low, tick.price)
        self.close = tick.price
        self.volume += tick.size
        self.trades += 1
        side = normalize_side(tick.side)
        if side == "B":
            self.buy_volume += tick.size
            self.signed_volume += tick.size
            signed = tick.size
        elif side == "A":
            self.sell_volume += tick.size
            self.signed_volume -= tick.size
            signed = -tick.size
        else:
            signed = 0.0
        for threshold in large_trade_sizes:
            if tick.size >= threshold:
                self.large[f"large{threshold}_signed_volume"] += signed
                self.large[f"large{threshold}_volume"] += tick.size

    def to_bar(self, root_symbol: str, source: str) -> SourceMinuteBar:
        return SourceMinuteBar(
            timestamp_utc=self.minute_utc,
            symbol=root_symbol,
            contract_symbol=self.contract_symbol,
            open=float(self.open),
            high=float(self.high),
            low=float(self.low),
            close=float(self.close),
            volume=float(self.volume),
            signed_volume=float(self.signed_volume),
            buy_volume=float(self.buy_volume),
            sell_volume=float(self.sell_volume),
            trades=int(self.trades),
            large=dict(self.large),
            source=source,
        )


class TradeBarBuilder:
    def __init__(
        self,
        *,
        root_symbol: str,
        timezone: str,
        large_trade_sizes: list[int],
        active_contract_mode: str = "highest_session_volume",
    ) -> None:
        self.root_symbol = root_symbol
        self.timezone = timezone
        self.large_trade_sizes = large_trade_sizes
        self.active_contract_mode = active_contract_mode
        self._current: dict[str, MinuteAccumulator] = {}
        self._session_volume: dict[tuple[str, str], float] = {}

    def update(self, tick: TradeTick) -> list[SourceMinuteBar]:
        if tick.action and normalize_action(tick.action) != "T":
            return []
        tick_minute = tick.timestamp_utc.floor("min")
        completed: list[SourceMinuteBar] = []
        for contract, acc in list(self._current.items()):
            if acc.minute_utc < tick_minute:
                bar = acc.to_bar(self.root_symbol, "live")
                completed.append(bar)
                self._add_session_volume(bar)
                del self._current[contract]

        acc = self._current.get(tick.contract_symbol)
        if acc is None:
            self._current[tick.contract_symbol] = MinuteAccumulator.start(tick, self.large_trade_sizes)
        elif acc.minute_utc == tick_minute:
            acc.add(tick, self.large_trade_sizes)
        elif acc.minute_utc > tick_minute:
            return self._select_active_bars(completed)
        else:
            bar = acc.to_bar(self.root_symbol, "live")
            completed.append(bar)
            self._add_session_volume(bar)
            self._current[tick.contract_symbol] = MinuteAccumulator.start(tick, self.large_trade_sizes)
        return self._select_active_bars(completed)

    def _add_session_volume(self, bar: SourceMinuteBar) -> None:
        session_date = local_session_date(bar.timestamp_utc, self.timezone)
        key = (session_date, bar.contract_symbol)
        self._session_volume[key] = self._session_volume.get(key, 0.0) + bar.volume

    def _select_active_bars(self, bars: list[SourceMinuteBar]) -> list[SourceMinuteBar]:
        if not bars or self.active_contract_mode == "emit_all":
            return bars
        selected: list[SourceMinuteBar] = []
        by_minute: dict[Any, list[SourceMinuteBar]] = {}
        for bar in bars:
            by_minute.setdefault(bar.timestamp_utc, []).append(bar)
        for minute, group in sorted(by_minute.items(), key=lambda item: item[0]):
            if len(group) == 1:
                selected.append(group[0])
                continue
            if self.active_contract_mode == "highest_minute_volume":
                selected.append(max(group, key=lambda bar: (bar.volume, bar.contract_symbol)))
                continue
            session_date = local_session_date(minute, self.timezone)
            selected.append(
                max(
                    group,
                    key=lambda bar: (
                        self._session_volume.get((session_date, bar.contract_symbol), 0.0),
                        bar.volume,
                        bar.contract_symbol,
                    ),
                )
            )
        return selected


class BarStore:
    def __init__(self, max_bars: int) -> None:
        self.max_bars = max_bars
        self._bars: dict[tuple[int, str], SourceMinuteBar] = {}

    def add(self, bar: SourceMinuteBar) -> bool:
        key = bar.key()
        existing = self._bars.get(key)
        self._bars[key] = bar
        self._trim()
        return existing != bar

    def add_many(self, bars: list[SourceMinuteBar]) -> int:
        changed = 0
        for bar in bars:
            if self.add(bar):
                changed += 1
        return changed

    def bars(self) -> list[SourceMinuteBar]:
        return [self._bars[key] for key in sorted(self._bars)]

    def latest_source_end(self, market_timezone: str) -> Any | None:
        bars = self.bars()
        if not bars:
            return None
        latest = max(bar.timestamp_utc for bar in bars)
        return latest.tz_convert(market_timezone) + pd.Timedelta(minutes=1)

    def to_dataframe(self, *, market_timezone: str, root_symbol: str) -> Any:
        rows: list[dict[str, Any]] = []
        for bar in self.bars():
            timestamp_utc = pd.Timestamp(bar.timestamp_utc).tz_convert("UTC")
            row = {
                "timestamp": timestamp_utc.tz_convert(market_timezone),
                "timestamp_utc": timestamp_utc,
                "symbol": root_symbol,
                "contract_symbol": bar.contract_symbol,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
                "signed_volume": float(bar.signed_volume),
                "buy_volume": float(bar.buy_volume),
                "sell_volume": float(bar.sell_volume),
                "trades": int(bar.trades),
                "source": bar.source,
            }
            row.update(bar.large)
            rows.append(row)
        if not rows:
            return pd.DataFrame(columns=["timestamp", "timestamp_utc", "symbol", "open", "high", "low", "close"])
        return pd.DataFrame(rows).sort_values(["timestamp", "contract_symbol"]).reset_index(drop=True)

    def _trim(self) -> None:
        overflow = len(self._bars) - self.max_bars
        if overflow <= 0:
            return
        for key in sorted(self._bars)[:overflow]:
            del self._bars[key]


@dataclass
class PendingSignal:
    strategy: "StrategyRuntime"
    row: Any
    signal_obj: Any
    due_utc: Any
    queued_at_utc: Any
    key: str


class StrategyRuntime:
    def __init__(
        self,
        *,
        project_root: Path,
        config_dir: Path,
        strategy_spec: dict[str, Any],
        engine_config: dict[str, Any],
    ) -> None:
        self.project_root = project_root
        self.config_dir = config_dir
        self.strategy_spec = strategy_spec
        self.engine_config = engine_config
        self.strategy_config_path = resolve_strategy_path(
            project_root,
            config_dir,
            required_spec_value(strategy_spec, "config"),
        )
        self.variant_config = resolve_project_file_references(
            load_yaml(self.strategy_config_path),
            project_root,
        )
        self.strategy_id = str(
            strategy_spec.get("id")
            or self.variant_config.get("variant_id")
            or self.variant_config.get("strategy_name")
            or self.strategy_config_path.stem
        )
        self.data_config = dict(self.variant_config.get("data", {}))
        self.symbol = str(
            strategy_spec.get("symbol")
            or self.variant_config.get("symbol")
            or self.data_config.get("symbol")
            or engine_config.get("symbol")
            or DEFAULT_SYMBOL
        )
        self.timezone = str(
            strategy_spec.get("timezone")
            or self.data_config.get("timezone")
            or engine_config.get("timezone")
            or DEFAULT_TIMEZONE
        )
        self.timeframe = self.variant_config.get("timeframe") or self.data_config.get("timeframe") or "1m"
        self.timeframe_minutes = parse_timeframe_minutes(self.timeframe)
        self.strategy = self._build_strategy()
        self.last_processed_strategy_timestamp: Any | None = None
        self.trades_by_session: dict[str, int] = {}
        self.sent_signal_keys: set[str] = set()
        self.warnings = validate_strategy_variant(self.variant_config, self.strategy_config_path, self.project_root)

    def preflight_report(self) -> dict[str, Any]:
        strategy = self.variant_config.get("strategy", {})
        return {
            "id": self.strategy_id,
            "strategy_name": self.variant_config.get("strategy_name", getattr(self.strategy, "name", None)),
            "config": str(self.strategy_config_path),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timeframe_minutes": self.timeframe_minutes,
            "modules": {
                "entry": nested_get(strategy, "entry", "module"),
                "sl": nested_get(strategy, "sl", "module"),
                "tp": nested_get(strategy, "tp", "module"),
            },
            "warnings": self.warnings,
        }

    def hydrate(self, store: BarStore, *, count_historical_signals: bool) -> int:
        pending = self.process_new_completed_bars(store, live=False)
        if count_historical_signals:
            for item in pending:
                self._record_trade(item.row)
        return len(pending)

    def process_new_completed_bars(self, store: BarStore, *, live: bool) -> list[PendingSignal]:
        features = self.completed_features(store)
        if features.empty:
            return []
        new_rows = features
        if self.last_processed_strategy_timestamp is not None:
            new_rows = features[features["timestamp"] > self.last_processed_strategy_timestamp]
        queued: list[PendingSignal] = []
        for _, row in new_rows.iterrows():
            timestamp = row["timestamp"]
            session_key = session_key_from_row(row)
            trades_today = self.trades_by_session.get(session_key, 0)
            signal_obj = self.strategy.on_bar_close(row, trades_today=trades_today)
            self.last_processed_strategy_timestamp = timestamp
            if signal_obj is None:
                continue
            pending = self._pending_from_signal(row, signal_obj)
            if live:
                queued.append(pending)
            else:
                queued.append(pending)
        return queued

    def completed_features(self, store: BarStore) -> Any:
        features = self.current_features(store)
        if features.empty:
            return features
        latest_source_end = store.latest_source_end(self.timezone)
        if latest_source_end is None:
            return features.iloc[0:0].copy()
        completed = features[
            features["timestamp"] + pd.Timedelta(minutes=self.timeframe_minutes) <= latest_source_end
        ]
        return completed.sort_values("timestamp").reset_index(drop=True)

    def current_features(self, store: BarStore) -> Any:
        add_project_src_to_path(self.project_root)
        from propstack.data.features import build_features
        from propstack.data.sessions import assign_sessions, filter_trading_sessions
        from propstack.data.timeframe import aggregate_timeframe

        source = store.to_dataframe(market_timezone=self.timezone, root_symbol=self.symbol)
        if source.empty:
            return source
        sessionized = assign_sessions(source, self.data_config)
        sessionized = filter_trading_sessions(sessionized)
        strategy_bars = aggregate_timeframe(sessionized, self.data_config, self.timeframe)
        features = build_features(strategy_bars, self.data_config)
        return features.sort_values("timestamp").reset_index(drop=True)

    def build_alert(self, pending: PendingSignal, tick: TradeTick, account: dict[str, Any]) -> dict[str, Any] | None:
        direction = str(getattr(pending.signal_obj, "direction", "")).lower()
        if direction not in {"long", "short"}:
            self.emit_reject(pending, "strategy signal direction is not long or short")
            return None
        side = "buy" if direction == "long" else "sell"
        core = copy.deepcopy(self.variant_config.get("core", {}))
        tick_size = float(core.get("tick_size", self.data_config.get("tick_size", 0.25)))
        tick_value = float(core.get("tick_value", 12.5))
        slippage_ticks = float(account.get("slippage_ticks", core.get("slippage_ticks", 0.0)))
        entry_price = estimated_market_entry(tick.price, direction, tick_size, slippage_ticks)

        stop_price = self.strategy.stop_price(
            pending.signal_obj,
            direction,
            tick_size,
            entry_price=entry_price,
        )
        stop_price = finite_float(stop_price)
        if stop_price is None:
            self.emit_reject(pending, "strategy did not produce a finite stop price")
            return None
        target_price = self.strategy.target_price(entry_price, stop_price, direction, signal=pending.signal_obj)
        target_price = finite_float(target_price)
        if target_price is None:
            self.emit_reject(pending, "strategy did not produce a finite target price")
            return None

        stop_points = abs(entry_price - stop_price)
        target_points = abs(target_price - entry_price)
        if stop_points <= 0 or target_points <= 0:
            self.emit_reject(pending, "stop/target distance is non-positive")
            return None
        if direction == "long" and not (stop_price < entry_price < target_price):
            self.emit_reject(pending, "long stop/target are not on opposite sides of entry")
            return None
        if direction == "short" and not (target_price < entry_price < stop_price):
            self.emit_reject(pending, "short stop/target are not on opposite sides of entry")
            return None

        sizing = self._size_position(core, stop_points, tick_size, tick_value, account)
        suggested_quantity = int(sizing.contracts)
        max_contracts = int(account.get("max_contracts", suggested_quantity or 0) or 0)
        min_contracts = int(account.get("min_contracts", 1) or 1)
        quantity = min(suggested_quantity, max_contracts) if max_contracts > 0 else suggested_quantity
        if quantity < min_contracts:
            self.emit_reject(
                pending,
                "sizing produced quantity below minimum",
                extra={"suggested_quantity": suggested_quantity, "min_contracts": min_contracts},
            )
            return None

        self._record_trade(pending.row)
        self.sent_signal_keys.add(pending.key)
        alert_id = alert_hash(
            self.strategy_id,
            str(pending.row["timestamp"]),
            direction,
            str(getattr(pending.signal_obj, "level_type", "")),
            str(tick.timestamp_utc),
        )
        row_timestamp = pd.Timestamp(pending.row["timestamp"])
        entry_timestamp = pd.Timestamp(tick.timestamp_utc)
        return {
            "event": "entry_signal",
            "alert_id": alert_id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.variant_config.get("strategy_name", getattr(self.strategy, "name", None)),
            "strategy_config": str(self.strategy_config_path),
            "symbol": self.symbol,
            "contract_symbol": tick.contract_symbol,
            "timeframe": self.timeframe,
            "signal_timestamp": format_timestamp(row_timestamp),
            "entry_timestamp": format_timestamp(entry_timestamp),
            "entry_timestamp_utc": format_timestamp(entry_timestamp.tz_convert("UTC")),
            "session_date": str(pending.row.get("session_date", "")),
            "direction": direction,
            "side": side,
            "quantity": int(quantity),
            "suggested_quantity": int(suggested_quantity),
            "order_type": "market",
            "entry_price": round_to_tick(entry_price, tick_size),
            "entry_basis_price": round_to_tick(tick.price, tick_size),
            "entry_slippage_ticks": slippage_ticks,
            "take_profit_price": round_to_tick(target_price, tick_size),
            "stop_loss_price": round_to_tick(stop_price, tick_size),
            "take_profit_points": float(target_points),
            "stop_loss_points": float(stop_points),
            "tick_size": tick_size,
            "tick_value": tick_value,
            "risk_dollars": float(stop_points / tick_size * tick_value * quantity),
            "reward_dollars": float(target_points / tick_size * tick_value * quantity),
            "signal": signal_report(pending.signal_obj),
            "sizing": sizing.report_fields(),
        }

    def emit_reject(self, pending: PendingSignal, reason: str, extra: dict[str, Any] | None = None) -> None:
        payload = {
            "event": "signal_rejected",
            "strategy_id": self.strategy_id,
            "strategy_name": self.variant_config.get("strategy_name", getattr(self.strategy, "name", None)),
            "timestamp": str(pending.row.get("timestamp", "")),
            "session_date": str(pending.row.get("session_date", "")),
            "reason": reason,
            "signal": signal_report(pending.signal_obj),
        }
        if extra:
            payload.update(extra)
        print_json(payload, prefix="SIGNAL_REJECTED")

    def _build_strategy(self) -> Any:
        add_project_src_to_path(self.project_root)
        from propstack.strategy import ModularStrategy

        strategy_config = copy.deepcopy(self.variant_config.get("strategy", {}))
        if "strategy_name" not in strategy_config and self.variant_config.get("strategy_name"):
            strategy_config["strategy_name"] = self.variant_config["strategy_name"]
        params = strategy_config.setdefault("entry", {}).setdefault("params", {})
        self._validate_or_set_timeframe_param(params, "bar_interval_minutes")
        if "timeframe_minutes" in params:
            self._validate_or_set_timeframe_param(params, "timeframe_minutes")
        return ModularStrategy(strategy_config)

    def _validate_or_set_timeframe_param(self, params: dict[str, Any], key: str) -> None:
        if key not in params:
            params[key] = self.timeframe_minutes
            return
        configured = float(params[key])
        if not math.isclose(configured, float(self.timeframe_minutes)):
            raise ValueError(
                f"{self.strategy_id}: strategy.entry.params.{key} ({configured:g}) must match "
                f"variant timeframe ({self.timeframe_minutes:g} minutes)."
            )

    def _pending_from_signal(self, row: Any, signal_obj: Any) -> PendingSignal:
        row_timestamp = pd.Timestamp(row["timestamp"])
        due_local = row_timestamp + pd.Timedelta(minutes=self.timeframe_minutes)
        due_utc = due_local.tz_convert("UTC") if due_local.tzinfo else due_local.tz_localize(self.timezone).tz_convert("UTC")
        key = alert_hash(
            self.strategy_id,
            str(row_timestamp),
            str(getattr(signal_obj, "direction", "")),
            str(getattr(signal_obj, "level_type", "")),
            str(getattr(signal_obj, "metadata", {})),
        )
        return PendingSignal(
            strategy=self,
            row=row.copy(),
            signal_obj=signal_obj,
            due_utc=due_utc,
            queued_at_utc=pd.Timestamp.utcnow(),
            key=key,
        )

    def _record_trade(self, row: Any) -> None:
        session_key = session_key_from_row(row)
        self.trades_by_session[session_key] = self.trades_by_session.get(session_key, 0) + 1

    def _size_position(
        self,
        core: dict[str, Any],
        stop_points: float,
        tick_size: float,
        tick_value: float,
        account: dict[str, Any],
    ) -> Any:
        add_project_src_to_path(self.project_root)
        from propstack.backtest.sizing import size_position

        if "position_sizing" not in core:
            core["position_sizing"] = {"mode": "fixed_contracts", "contracts": 1}
        net_liq = account.get("net_liq")
        if net_liq is None:
            net_liq = account.get("equity")
        return size_position(core, stop_points, tick_size, tick_value, net_liq=float(net_liq) if net_liq else None)


class SignalEngine:
    def __init__(self, config: dict[str, Any], config_path: Path) -> None:
        if pd is None:
            raise RuntimeError("Missing dependency: pandas")
        self.config = config
        self.config_path = config_path
        self.config_dir = config_path.parent
        self.project_root = resolve_project_root(config, self.config_dir)
        self.engine_config = dict(config.get("engine", {}))
        self.databento_config = dict(config.get("databento", {}))
        self.symbol = str(self.engine_config.get("symbol") or self.databento_config.get("root_symbol") or DEFAULT_SYMBOL)
        self.timezone = str(self.engine_config.get("timezone") or self.databento_config.get("timezone") or DEFAULT_TIMEZONE)
        self.store = BarStore(int(self.engine_config.get("max_source_bars", 50000)))
        self.account = dict(self.engine_config.get("account", {}))
        self.alert_prefix = str(self.engine_config.get("alert_prefix", DEFAULT_ALERT_PREFIX))
        self.alerts_path = resolve_optional_path(self.config_dir, self.engine_config.get("alerts_path"))
        self.pending: list[PendingSignal] = []
        self.alert_count = 0
        self.lock = threading.RLock()
        self.strategies = self._load_strategies()

    def preflight_report(self) -> dict[str, Any]:
        historical = dict(self.databento_config.get("historical", {}))
        live = dict(self.databento_config.get("live", {}))
        return {
            "event": "preflight",
            "config": str(self.config_path),
            "project_root": str(self.project_root),
            "symbol": self.symbol,
            "timezone": self.timezone,
            "databento": {
                "dataset": self.databento_config.get("dataset", DEFAULT_DATASET),
                "schema": self.databento_config.get("schema", DEFAULT_SCHEMA),
                "symbols": self.databento_config.get("symbols", DEFAULT_DATABENTO_SYMBOLS),
                "stype_in": self.databento_config.get("stype_in", DEFAULT_STYPE_IN),
                "historical_enabled": bool(historical.get("enabled", True)),
                "historical_cache_path": historical.get("cache_path"),
                "live_enabled": bool(live.get("enabled", True)),
            },
            "alerts_path": str(self.alerts_path) if self.alerts_path else None,
            "strategies": [strategy.preflight_report() for strategy in self.strategies],
        }

    def seed(self, bars: list[SourceMinuteBar], *, source: str) -> None:
        with self.lock:
            changed = self.store.add_many(bars)
            count_historical = bool(self.engine_config.get("count_historical_signals", True))
            hydrated_signals = 0
            for strategy in self.strategies:
                hydrated_signals += strategy.hydrate(self.store, count_historical_signals=count_historical)
            print_json(
                {
                    "event": "seed_complete",
                    "source": source,
                    "bars": len(bars),
                    "new_or_updated_bars": changed,
                    "hydrated_historical_signals": hydrated_signals if count_historical else 0,
                }
            )

    def on_completed_source_bar(self, bar: SourceMinuteBar) -> None:
        with self.lock:
            changed = self.store.add(bar)
            if not changed:
                return
            queued = 0
            for strategy in self.strategies:
                for pending in strategy.process_new_completed_bars(self.store, live=True):
                    if pending.key not in strategy.sent_signal_keys:
                        self.pending.append(pending)
                        queued += 1
            if queued:
                print_json(
                    {
                        "event": "signals_queued",
                        "source_bar_timestamp": format_timestamp(bar.timestamp_utc),
                        "queued": queued,
                    }
                )

    def on_entry_tick(self, tick: TradeTick) -> None:
        with self.lock:
            if not self.pending:
                return
            max_lag = float(self.engine_config.get("max_entry_lag_seconds", 120))
            still_pending: list[PendingSignal] = []
            for pending in self.pending:
                if pending.key in pending.strategy.sent_signal_keys:
                    continue
                lag = (tick.timestamp_utc - pending.due_utc).total_seconds()
                if lag < -0.001:
                    still_pending.append(pending)
                    continue
                if lag > max_lag:
                    pending.strategy.emit_reject(
                        pending,
                        f"next entry tick arrived {lag:.1f}s after due time, beyond max_entry_lag_seconds",
                    )
                    continue
                alert = pending.strategy.build_alert(pending, tick, self.account)
                if alert is None:
                    continue
                self.emit_alert(alert)
            self.pending = still_pending

    def emit_alert(self, alert: dict[str, Any]) -> None:
        self.alert_count += 1
        print_json(alert, prefix=self.alert_prefix)
        if self.alerts_path:
            self.alerts_path.parent.mkdir(parents=True, exist_ok=True)
            with self.alerts_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(alert, sort_keys=True, default=json_default) + "\n")

    def _load_strategies(self) -> list[StrategyRuntime]:
        specs = self.config.get("strategies")
        if not isinstance(specs, list) or not specs:
            raise ValueError("config must define a non-empty strategies list")
        strategies = []
        for raw_spec in specs:
            spec = {"config": raw_spec} if isinstance(raw_spec, str) else dict(raw_spec)
            if not bool(spec.get("enabled", True)):
                continue
            strategies.append(
                StrategyRuntime(
                    project_root=self.project_root,
                    config_dir=self.config_dir,
                    strategy_spec=spec,
                    engine_config={**self.engine_config, "symbol": self.symbol, "timezone": self.timezone},
                )
            )
        if not strategies:
            raise ValueError("all configured strategies are disabled")
        return strategies


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Databento historical/live ticks through propstack strategy YAMLs.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Signal-engine YAML config.")
    parser.add_argument("--project-root", help="Project root containing src/ and configs/.")
    parser.add_argument("--strategy-config", action="append", help="Add/override with a campaign strategy YAML path.")
    parser.add_argument("--preflight-only", action="store_true", help="Validate config and exit without Databento access.")
    parser.add_argument("--seed-only", action="store_true", help="Load/fetch historical seed bars, hydrate strategies, then exit.")
    parser.add_argument("--replay-bars", help="Replay cached 1-minute orderflow bars as live source bars.")
    parser.add_argument("--replay-stop-after-signal", action="store_true", help="Stop replay after the first ENTRY_SIGNAL.")
    parser.add_argument("--max-replay-bars", type=int, default=0, help="Cap replayed bars after the seed; 0 means no cap.")
    parser.add_argument("--skip-historical", action="store_true", help="Do not fetch/load historical seed data.")
    parser.add_argument("--refresh-historical", action="store_true", help="Ignore historical cache and refetch from Databento.")
    parser.add_argument("--live", action="store_true", help="Start live Databento streaming after seeding.")
    parser.add_argument("--once", action="store_true", help="Stop after the first live source bar completes.")
    parser.add_argument("--max-runtime", type=float, default=0.0, help="Optional live runtime limit in seconds.")
    parser.add_argument("--databento-symbols", help="Override databento.symbols, e.g. ESM6 or ES.FUT.")
    parser.add_argument("--databento-stype-in", help="Override databento.stype_in.")
    return parser.parse_args()


def run() -> int:
    if PANDAS_IMPORT_ERROR is not None:
        print("Missing dependency: python3 -m pip install pandas", file=sys.stderr)
        return 2
    if YAML_IMPORT_ERROR is not None:
        print("Missing dependency: python3 -m pip install pyyaml", file=sys.stderr)
        return 2

    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    config = apply_cli_overrides(load_yaml(config_path), args)
    engine = SignalEngine(config, config_path)
    print_json(engine.preflight_report())
    if args.preflight_only:
        return 0

    if not args.skip_historical:
        seed_bars = load_historical_seed_bars(engine, refresh=args.refresh_historical)
        if seed_bars:
            engine.seed(seed_bars, source="historical")
    if args.seed_only:
        return 0
    if args.replay_bars:
        replay_bars(engine, resolve_path(config_path.parent, args.replay_bars), args)
        return 0
    live_enabled = args.live or bool(engine.databento_config.get("live", {}).get("enabled", True))
    if not live_enabled:
        return 0
    return run_live(engine, once=args.once, max_runtime=args.max_runtime)


def apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    config = copy.deepcopy(config)
    if args.project_root:
        config["project_root"] = args.project_root
    if args.strategy_config:
        config["strategies"] = [{"config": path, "enabled": True} for path in args.strategy_config]
    databento = config.setdefault("databento", {})
    if args.databento_symbols:
        databento["symbols"] = args.databento_symbols
    if args.databento_stype_in:
        databento["stype_in"] = args.databento_stype_in
    return config


def load_historical_seed_bars(engine: SignalEngine, *, refresh: bool = False) -> list[SourceMinuteBar]:
    hist_cfg = dict(engine.databento_config.get("historical", {}))
    if not bool(hist_cfg.get("enabled", True)):
        return []
    cache_path = resolve_optional_path(engine.config_dir, hist_cfg.get("cache_path"))
    if cache_path and cache_path.exists() and not refresh and not bool(hist_cfg.get("refresh", False)):
        bars = read_bars_file(cache_path, root_symbol=engine.symbol, timezone=engine.timezone, source="historical_cache")
        print_json({"event": "historical_cache_loaded", "path": str(cache_path), "bars": len(bars)})
        return bars

    seed_bars_path = resolve_optional_path(engine.config_dir, hist_cfg.get("seed_bars_path"))
    if seed_bars_path:
        bars = read_bars_file(seed_bars_path, root_symbol=engine.symbol, timezone=engine.timezone, source="historical_file")
        print_json({"event": "historical_seed_file_loaded", "path": str(seed_bars_path), "bars": len(bars)})
        if cache_path:
            write_bars_file(cache_path, bars, timezone=engine.timezone)
        return bars

    bars = fetch_databento_historical_bars(engine, hist_cfg)
    if cache_path and bars:
        write_bars_file(cache_path, bars, timezone=engine.timezone)
        print_json({"event": "historical_cache_written", "path": str(cache_path), "bars": len(bars)})
    return bars


def fetch_databento_historical_bars(engine: SignalEngine, hist_cfg: dict[str, Any]) -> list[SourceMinuteBar]:
    add_project_src_to_path(engine.project_root)
    from propstack.data.databento_trades import aggregate_trade_orderflow_1m

    import databento as db

    api_key = databento_api_key(engine.databento_config)
    dataset = str(engine.databento_config.get("dataset", DEFAULT_DATASET))
    schema = str(engine.databento_config.get("schema", DEFAULT_SCHEMA))
    symbols = engine.databento_config.get("symbols", DEFAULT_DATABENTO_SYMBOLS)
    stype_in = str(engine.databento_config.get("stype_in", DEFAULT_STYPE_IN))
    stype_out = str(engine.databento_config.get("stype_out", DEFAULT_STYPE_OUT))
    start, end = historical_bounds(hist_cfg, engine.timezone)
    print_json(
        {
            "event": "historical_fetch_start",
            "dataset": dataset,
            "schema": schema,
            "symbols": symbols,
            "stype_in": stype_in,
            "stype_out": stype_out,
            "start": str(start),
            "end": str(end),
        }
    )
    client = db.Historical(api_key)
    store = client.timeseries.get_range(
        dataset=dataset,
        symbols=symbols,
        schema=schema,
        stype_in=stype_in,
        stype_out=stype_out,
        start=start,
        end=end,
        limit=hist_cfg.get("limit"),
    )
    trades = store.to_df().reset_index()
    if trades.empty:
        return []
    bars = aggregate_trade_orderflow_1m(
        trades,
        timezone=engine.timezone,
        root_symbol=engine.symbol,
        contract_symbol_regex=str(engine.databento_config.get("contract_symbol_regex", r"^ES[HMUZ]\d$")),
        rth_start=str(engine.databento_config.get("rth_start", "09:30:00")),
        rth_end=str(engine.databento_config.get("rth_end", "16:00:00")),
        complete_session_end=hist_cfg.get("complete_session_end"),
        large_trade_sizes=engine_large_trade_sizes(engine.databento_config),
    )
    out = bars_from_orderflow_frame(bars, root_symbol=engine.symbol, timezone=engine.timezone, source="historical")
    max_seed_bars = int(hist_cfg.get("max_seed_bars", 0) or 0)
    if max_seed_bars > 0:
        out = out[-max_seed_bars:]
    print_json({"event": "historical_fetch_complete", "trades": len(trades), "bars": len(out)})
    return out


def replay_bars(engine: SignalEngine, path: Path, args: argparse.Namespace) -> None:
    bars = read_bars_file(path, root_symbol=engine.symbol, timezone=engine.timezone, source="replay")
    if len(bars) < 2:
        raise RuntimeError(f"replay requires at least two bars: {path}")
    seed_count = int(engine.engine_config.get("replay_seed_bars", 1000))
    seed_count = max(0, min(seed_count, len(bars) - 1))
    if seed_count:
        engine.seed([replace_bar_source(bar, "replay_seed") for bar in bars[:seed_count]], source="replay_seed")
    replayed = 0
    starting_alerts = engine.alert_count
    previous = bars[seed_count]
    for current in bars[seed_count + 1 :]:
        if args.max_replay_bars and replayed >= args.max_replay_bars:
            break
        engine.on_completed_source_bar(replace_bar_source(previous, "replay_live"))
        entry_tick = TradeTick(
            timestamp_utc=current.timestamp_utc,
            price=current.open,
            size=0.0,
            side="N",
            contract_symbol=current.contract_symbol,
        )
        engine.on_entry_tick(entry_tick)
        replayed += 1
        if args.replay_stop_after_signal and engine.alert_count > starting_alerts:
            break
        previous = current
    print_json(
        {
            "event": "replay_complete",
            "path": str(path),
            "source_bars": len(bars),
            "seed_bars": seed_count,
            "replayed_bars": replayed,
            "entry_alerts": engine.alert_count - starting_alerts,
        }
    )


def run_live(engine: SignalEngine, *, once: bool, max_runtime: float) -> int:
    import databento as db

    api_key = databento_api_key(engine.databento_config)
    live_cfg = dict(engine.databento_config.get("live", {}))
    builder = TradeBarBuilder(
        root_symbol=engine.symbol,
        timezone=engine.timezone,
        large_trade_sizes=engine_large_trade_sizes(engine.databento_config),
        active_contract_mode=str(engine.databento_config.get("active_contract_mode", "highest_session_volume")),
    )
    client = db.Live(
        key=api_key,
        reconnect_policy=str(live_cfg.get("reconnect_policy", "reconnect")),
        heartbeat_interval_s=live_cfg.get("heartbeat_interval_s"),
    )
    completed_count = 0
    stop_requested = threading.Event()

    def handle_record(record: Any) -> None:
        nonlocal completed_count
        tick = live_record_to_tick(
            record,
            default_contract_symbol=str(engine.databento_config.get("symbols", engine.symbol)),
            symbology_map=getattr(client, "symbology_map", None),
        )
        if tick is None:
            return
        completed = builder.update(tick)
        for bar in completed:
            engine.on_completed_source_bar(bar)
            completed_count += 1
        engine.on_entry_tick(tick)
        if once and completed_count > 0:
            stop_requested.set()
            client.stop()

    def handle_exception(exc: Exception) -> None:
        print_json({"event": "live_exception", "error": str(exc)}, prefix="LIVE_ERROR")

    client.add_callback(handle_record, handle_exception)
    subscribe_args = {
        "dataset": str(engine.databento_config.get("dataset", DEFAULT_DATASET)),
        "schema": str(engine.databento_config.get("schema", DEFAULT_SCHEMA)),
        "symbols": engine.databento_config.get("symbols", DEFAULT_DATABENTO_SYMBOLS),
        "stype_in": str(engine.databento_config.get("stype_in", DEFAULT_STYPE_IN)),
    }
    if live_cfg.get("start"):
        subscribe_args["start"] = live_cfg["start"]
    print_json({"event": "live_subscribe", **subscribe_args})
    client.subscribe(**subscribe_args)
    client.start()

    interrupted = False

    def request_stop(*_: Any) -> None:
        nonlocal interrupted
        interrupted = True
        stop_requested.set()
        client.stop()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    deadline = time.monotonic() + max_runtime if max_runtime > 0 else None
    while not stop_requested.is_set():
        if deadline is not None and time.monotonic() >= deadline:
            stop_requested.set()
            client.stop()
            break
        client.block_for_close(timeout=1.0)
        is_connected = client.is_connected() if callable(client.is_connected) else bool(client.is_connected)
        if not is_connected:
            break
    try:
        client.stop()
    except Exception:
        pass
    return 130 if interrupted else 0


def read_bars_file(path: Path, *, root_symbol: str, timezone: str, source: str) -> list[SourceMinuteBar]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    return bars_from_orderflow_frame(frame, root_symbol=root_symbol, timezone=timezone, source=source)


def write_bars_file(path: Path, bars: list[SourceMinuteBar], *, timezone: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for bar in bars:
        row = {
            "timestamp": format_timestamp(bar.timestamp_utc.tz_convert(timezone)),
            "timestamp_utc": format_timestamp(bar.timestamp_utc.tz_convert("UTC")),
            "symbol": bar.symbol,
            "contract_symbol": bar.contract_symbol,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "signed_volume": bar.signed_volume,
            "buy_volume": bar.buy_volume,
            "sell_volume": bar.sell_volume,
            "trades": bar.trades,
            "source": bar.source,
        }
        row.update(bar.large)
        rows.append(row)
    frame = pd.DataFrame(rows)
    if path.suffix.lower() in {".parquet", ".pq"}:
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False)


def bars_from_orderflow_frame(
    frame: Any,
    *,
    root_symbol: str,
    timezone: str,
    source: str,
) -> list[SourceMinuteBar]:
    if frame.empty:
        return []
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"bar file is missing required columns: {sorted(missing)}")
    out = frame.copy()
    if "timestamp_utc" in out.columns:
        timestamps = pd.to_datetime(out["timestamp_utc"], utc=True)
    else:
        timestamps = pd.to_datetime(out["timestamp"])
        if getattr(timestamps.dt, "tz", None) is None:
            timestamps = timestamps.dt.tz_localize(timezone)
        timestamps = timestamps.dt.tz_convert("UTC")
    bars: list[SourceMinuteBar] = []
    large_columns = [col for col in out.columns if col.startswith("large") and col.endswith(("_volume", "_signed_volume"))]
    for position, (_, row) in enumerate(out.iterrows()):
        large = {column: float(row.get(column, 0.0) or 0.0) for column in large_columns}
        signed = float(row.get("signed_volume", row.get("delta", 0.0)) or 0.0)
        buy_volume = float(row.get("buy_volume", max(signed, 0.0)) or 0.0)
        sell_volume = float(row.get("sell_volume", max(-signed, 0.0)) or 0.0)
        bars.append(
            SourceMinuteBar(
                timestamp_utc=pd.Timestamp(timestamps.iloc[position]).tz_convert("UTC"),
                symbol=str(row.get("symbol") or root_symbol),
                contract_symbol=str(row.get("contract_symbol") or row.get("symbol") or root_symbol),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                signed_volume=signed,
                buy_volume=buy_volume,
                sell_volume=sell_volume,
                trades=int(row.get("trades", row.get("count", 0)) or 0),
                large=large,
                source=source,
            )
        )
    return sorted(bars, key=lambda bar: (bar.timestamp_utc, bar.contract_symbol))


def live_record_to_tick(
    record: Any,
    *,
    default_contract_symbol: str,
    symbology_map: dict[Any, Any] | None = None,
) -> TradeTick | None:
    if not hasattr(record, "price") or not hasattr(record, "size") or not hasattr(record, "ts_event"):
        return None
    action = normalize_action(getattr(record, "action", "T"))
    if action and action != "T":
        return None
    price = record_price(record)
    size = finite_float(getattr(record, "size", None))
    timestamp = record_timestamp(getattr(record, "ts_event", None))
    if price is None or size is None or timestamp is None or size <= 0:
        return None
    symbol = record_symbol(record, default_contract_symbol, symbology_map=symbology_map)
    return TradeTick(
        timestamp_utc=timestamp,
        price=price,
        size=size,
        side=normalize_side(getattr(record, "side", "N")),
        contract_symbol=symbol,
        action=action or "T",
    )


def record_price(record: Any) -> float | None:
    pretty = getattr(record, "pretty_price", None)
    value = pretty() if callable(pretty) else pretty
    parsed = finite_float(value)
    if parsed is not None:
        return parsed
    raw = finite_float(getattr(record, "price", None))
    if raw is None:
        return None
    return raw / 1_000_000_000.0 if abs(raw) > 1_000_000 else raw


def record_timestamp(value: Any) -> Any | None:
    try:
        timestamp = pd.Timestamp(value, unit="ns", tz="UTC")
    except Exception:
        try:
            timestamp = pd.Timestamp(value)
        except Exception:
            return None
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")
    return timestamp


def record_symbol(
    record: Any,
    default_contract_symbol: str,
    *,
    symbology_map: dict[Any, Any] | None = None,
) -> str:
    for name in ("symbol", "raw_symbol", "contract_symbol"):
        value = getattr(record, name, None)
        if value:
            return str(value)
    instrument_id = getattr(record, "instrument_id", None)
    mapped_symbol = mapped_instrument_symbol(instrument_id, symbology_map)
    if mapped_symbol:
        return mapped_symbol
    if instrument_id is not None and default_contract_symbol not in {"ES.FUT", "ALL_SYMBOLS"}:
        return str(default_contract_symbol)
    if instrument_id is not None:
        return str(instrument_id)
    return str(default_contract_symbol)


def mapped_instrument_symbol(instrument_id: Any, symbology_map: dict[Any, Any] | None) -> str | None:
    if instrument_id is None or not symbology_map:
        return None
    for key in (instrument_id, str(instrument_id)):
        if key in symbology_map:
            return extract_symbol_value(symbology_map[key])
    return None


def extract_symbol_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int)):
        text = str(value)
        return text if text else None
    if isinstance(value, dict):
        for key in ("symbol", "raw_symbol", "stype_out_symbol", "s"):
            if key in value:
                found = extract_symbol_value(value[key])
                if found:
                    return found
        for item in value.values():
            found = extract_symbol_value(item)
            if found:
                return found
    if isinstance(value, (list, tuple)):
        for item in reversed(value):
            found = extract_symbol_value(item)
            if found:
                return found
    return None


def historical_bounds(hist_cfg: dict[str, Any], timezone: str) -> tuple[Any, Any]:
    end = hist_cfg.get("end")
    if end is None:
        end_ts = pd.Timestamp.now(tz="UTC")
    else:
        end_ts = pd.Timestamp(end)
        end_ts = end_ts.tz_localize(timezone).tz_convert("UTC") if end_ts.tzinfo is None else end_ts.tz_convert("UTC")
    start = hist_cfg.get("start")
    if start is None:
        lookback_days = int(hist_cfg.get("lookback_days", 70))
        start_ts = end_ts - pd.Timedelta(days=lookback_days)
    else:
        start_ts = pd.Timestamp(start)
        start_ts = start_ts.tz_localize(timezone).tz_convert("UTC") if start_ts.tzinfo is None else start_ts.tz_convert("UTC")
    return start_ts, end_ts


def databento_api_key(config: dict[str, Any]) -> str:
    direct = config.get("api_key")
    if direct:
        return str(direct)
    env_name = str(config.get("api_key_env", "DATABENTO_API_KEY"))
    value = os.getenv(env_name)
    if not value:
        raise RuntimeError(f"Missing Databento API key. Set ${env_name} or databento.api_key.")
    return value


def engine_large_trade_sizes(databento_config: dict[str, Any]) -> list[int]:
    values = databento_config.get("large_trade_sizes", [])
    if values is None:
        return []
    return [int(value) for value in values]


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("Missing dependency: pyyaml")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"config not found: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"YAML must be a mapping: {path}")
    return data


def validate_strategy_variant(config: dict[str, Any], path: Path, project_root: Path) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        relative = path.resolve().relative_to(project_root.resolve())
    except ValueError:
        warnings.append(f"strategy config is outside project_root: {path}")
    else:
        parts = relative.parts
        if len(parts) < 3 or parts[0] != "configs" or parts[1] != "campaigns":
            warnings.append(f"strategy config is not under configs/campaigns: {relative}")
    if not config.get("timeframe"):
        errors.append("top-level timeframe is required")
    if not config.get("symbol"):
        errors.append("top-level symbol is required")
    strategy = config.get("strategy")
    if not isinstance(strategy, dict):
        errors.append("strategy mapping is required")
        strategy = {}
    for section in ("entry", "sl", "tp"):
        value = strategy.get(section)
        if not isinstance(value, dict):
            errors.append(f"strategy.{section} must be a mapping")
            continue
        if not value.get("module"):
            errors.append(f"strategy.{section}.module is required")
        if "params" not in value or not isinstance(value.get("params"), dict):
            errors.append(f"strategy.{section}.params mapping is required")
    if errors:
        raise ValueError(f"Strategy preflight failed for {path}: {'; '.join(errors)}")
    return warnings


def resolve_project_root(config: dict[str, Any], config_dir: Path) -> Path:
    value = config.get("project_root")
    if value:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        return (config_dir / path).resolve()
    candidate = (config_dir / "..").resolve()
    return candidate


def resolve_path(base: Path, value: str | os.PathLike[str]) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base / path).resolve()


def resolve_optional_path(base: Path, value: Any) -> Path | None:
    if not value:
        return None
    return resolve_path(base, str(value))


def resolve_strategy_path(project_root: Path, config_dir: Path, value: str | os.PathLike[str]) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    config_relative = (config_dir / path).resolve()
    if config_relative.exists():
        return config_relative
    return (project_root / path).resolve()


def resolve_project_file_references(value: Any, project_root: Path, *, key: str = "") -> Any:
    if isinstance(value, dict):
        return {
            item_key: resolve_project_file_references(item_value, project_root, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [resolve_project_file_references(item, project_root, key=key) for item in value]
    if isinstance(value, str) and is_project_file_reference_key(key):
        path = Path(value).expanduser()
        if path.is_absolute() or "://" in value:
            return value
        candidate = (project_root / path).resolve()
        if candidate.exists():
            return str(candidate)
    return value


def is_project_file_reference_key(key: str) -> bool:
    normalized = key.strip().lower()
    return (
        normalized in PROJECT_FILE_REFERENCE_KEYS
        or normalized.endswith("_file")
        or normalized.endswith("_path")
        or normalized.endswith("_dir")
    )


def parse_timeframe_minutes(value: Any) -> int:
    text = str(value).strip().lower()
    for suffix in ("minutes", "minute", "mins", "min", "m"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
            break
    else:
        for suffix in ("hours", "hour", "hrs", "hr", "h"):
            if text.endswith(suffix):
                text = str(float(text[: -len(suffix)].strip()) * 60)
                break
    minutes = int(float(text))
    if minutes <= 0:
        raise ValueError("timeframe must resolve to positive minutes")
    return minutes


def add_project_src_to_path(project_root: Path) -> None:
    src = str(project_root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def normalize_side(value: Any) -> str:
    text = enumish_to_string(value).upper()
    if text in {"B", "BUY", "BID"}:
        return "B"
    if text in {"A", "ASK", "SELL"}:
        return "A"
    return "N"


def normalize_action(value: Any) -> str:
    text = enumish_to_string(value).upper()
    return text[0] if text else ""


def enumish_to_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("ascii", errors="ignore")
    text = str(value)
    if "." in text:
        text = text.rsplit(".", 1)[-1]
    return text.strip("'\"")


def finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def estimated_market_entry(price: float, direction: str, tick_size: float, slippage_ticks: float) -> float:
    slip = tick_size * slippage_ticks
    return price + slip if direction == "long" else price - slip


def round_to_tick(value: float, tick_size: float) -> float:
    if tick_size <= 0:
        return float(value)
    return float(round(round(value / tick_size) * tick_size, 10))


def local_session_date(timestamp_utc: Any, timezone: str) -> str:
    return str(pd.Timestamp(timestamp_utc).tz_convert(timezone).date())


def session_key_from_row(row: Any) -> str:
    return str(row.get("session_date", ""))


def signal_report(signal_obj: Any) -> dict[str, Any]:
    return {
        "direction": str(getattr(signal_obj, "direction", "")),
        "level_type": str(getattr(signal_obj, "level_type", "")),
        "swept_level": getattr(signal_obj, "swept_level", None),
        "metadata": getattr(signal_obj, "metadata", {}),
        "report_fields": getattr(signal_obj, "report_fields", {}),
    }


def alert_hash(*parts: str) -> str:
    data = "|".join(parts).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:20]


def format_timestamp(value: Any) -> str:
    timestamp = pd.Timestamp(value)
    return timestamp.isoformat()


def replace_bar_source(bar: SourceMinuteBar, source: str) -> SourceMinuteBar:
    return SourceMinuteBar(
        timestamp_utc=bar.timestamp_utc,
        symbol=bar.symbol,
        contract_symbol=bar.contract_symbol,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
        signed_volume=bar.signed_volume,
        buy_volume=bar.buy_volume,
        sell_volume=bar.sell_volume,
        trades=bar.trades,
        large=dict(bar.large),
        source=source,
    )


def nested_get(mapping: dict[str, Any], *keys: str) -> Any:
    value: Any = mapping
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def required_spec_value(spec: dict[str, Any], key: str) -> Any:
    if key not in spec or spec[key] in {None, ""}:
        raise ValueError(f"strategy spec must define {key!r}")
    return spec[key]


def print_json(payload: dict[str, Any], *, prefix: str | None = None) -> None:
    text = json.dumps(payload, sort_keys=True, default=json_default)
    print(f"{prefix} {text}" if prefix else text, flush=True)


def json_default(value: Any) -> Any:
    if pd is not None:
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        if isinstance(value, pd.Timedelta):
            return value.total_seconds()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, (dt.date, dt.datetime, dt.time)):
        return value.isoformat()
    return str(value)


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001 - keep CLI failures readable.
        print(f"fatal: {exc}", file=sys.stderr)
        raise SystemExit(1)
