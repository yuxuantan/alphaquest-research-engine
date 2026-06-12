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
import asyncio
import copy
import datetime as dt
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import signal
import subprocess
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
DEFAULT_STYPE_OUT = "instrument_id"
DEFAULT_ALERT_PREFIX = "ENTRY_SIGNAL"
DEFAULT_OPERATOR_SOUND_MAX_ACTIVE_COMMANDS = 3
SETUP_NOTICE_CONTRACT_VERSION = "trade_setup.v3"
ALERT_CONTRACT_VERSION = "entry_signal.v5"
EXECUTION_INTENT_VERSION = "execution_intent.v5"
EXECUTION_INTENT_RECORD_VERSION = "execution_intent_record.v5"
CONFIG_FINGERPRINT_VERSION = "config_fingerprint.v1"
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
    bid_price: float | None = None
    ask_price: float | None = None


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
    delta_method: str = "aggressor_side"
    selected_unclassified_volume: float = 0.0
    databento_buy_aggressor_volume: float = 0.0
    databento_sell_aggressor_volume: float = 0.0
    databento_unknown_side_volume: float = 0.0
    quote_buy_volume: float = 0.0
    quote_sell_volume: float = 0.0
    quote_unclassified_volume: float = 0.0
    tick_rule_buy_volume: float = 0.0
    tick_rule_sell_volume: float = 0.0
    tick_rule_unclassified_volume: float = 0.0
    last_trade_price: float | None = None
    last_tick_rule_sign: int = 0

    @classmethod
    def start(cls, tick: TradeTick, large_trade_sizes: list[int], delta_method: str) -> "MinuteAccumulator":
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
            delta_method=delta_method,
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
        side_signed = signed_volume_from_aggressor_side(side, tick.size)
        quote_signed = signed_volume_from_quote(tick)
        tick_rule_signed = self._tick_rule_signed_volume(tick, fallback=side_signed)
        signed = select_delta_signed_volume(
            self.delta_method,
            side_signed=side_signed,
            quote_signed=quote_signed,
            tick_rule_signed=tick_rule_signed,
        )
        self._add_selected_volume(signed, tick.size)
        self._add_diagnostic_volume(
            side_signed,
            tick.size,
            buy_attr="databento_buy_aggressor_volume",
            sell_attr="databento_sell_aggressor_volume",
            unknown_attr="databento_unknown_side_volume",
        )
        self._add_diagnostic_volume(
            0.0 if quote_signed is None else quote_signed,
            tick.size,
            buy_attr="quote_buy_volume",
            sell_attr="quote_sell_volume",
            unknown_attr="quote_unclassified_volume",
        )
        self._add_diagnostic_volume(
            tick_rule_signed,
            tick.size,
            buy_attr="tick_rule_buy_volume",
            sell_attr="tick_rule_sell_volume",
            unknown_attr="tick_rule_unclassified_volume",
        )
        for threshold in large_trade_sizes:
            if tick.size >= threshold:
                self.large[f"large{threshold}_signed_volume"] += signed
                self.large[f"large{threshold}_volume"] += tick.size

    def _tick_rule_signed_volume(self, tick: TradeTick, *, fallback: float) -> float:
        sign = 0
        if self.last_trade_price is not None:
            if tick.price > self.last_trade_price:
                sign = 1
            elif tick.price < self.last_trade_price:
                sign = -1
            else:
                sign = self.last_tick_rule_sign
        if sign == 0:
            sign = 1 if fallback > 0 else -1 if fallback < 0 else 0
        self.last_trade_price = tick.price
        if sign:
            self.last_tick_rule_sign = sign
        return tick.size * sign if sign else 0.0

    def _add_selected_volume(self, signed: float, size: float) -> None:
        self.signed_volume += signed
        if signed > 0:
            self.buy_volume += size
        elif signed < 0:
            self.sell_volume += size
        else:
            self.selected_unclassified_volume += size

    def _add_diagnostic_volume(
        self,
        signed: float,
        size: float,
        *,
        buy_attr: str,
        sell_attr: str,
        unknown_attr: str,
    ) -> None:
        if signed > 0:
            setattr(self, buy_attr, getattr(self, buy_attr) + size)
        elif signed < 0:
            setattr(self, sell_attr, getattr(self, sell_attr) + size)
        else:
            setattr(self, unknown_attr, getattr(self, unknown_attr) + size)

    def to_bar(self, root_symbol: str, source: str) -> SourceMinuteBar:
        diagnostics = dict(self.large)
        diagnostics.update(
            {
                "selected_delta_unclassified_volume": float(self.selected_unclassified_volume),
                "databento_buy_aggressor_volume": float(self.databento_buy_aggressor_volume),
                "databento_sell_aggressor_volume": float(self.databento_sell_aggressor_volume),
                "databento_unknown_side_volume": float(self.databento_unknown_side_volume),
                "databento_aggressor_delta": float(
                    self.databento_buy_aggressor_volume - self.databento_sell_aggressor_volume
                ),
                "quote_buy_volume": float(self.quote_buy_volume),
                "quote_sell_volume": float(self.quote_sell_volume),
                "quote_unclassified_volume": float(self.quote_unclassified_volume),
                "quote_delta": float(self.quote_buy_volume - self.quote_sell_volume),
                "tick_rule_buy_volume": float(self.tick_rule_buy_volume),
                "tick_rule_sell_volume": float(self.tick_rule_sell_volume),
                "tick_rule_unclassified_volume": float(self.tick_rule_unclassified_volume),
                "tick_rule_delta": float(self.tick_rule_buy_volume - self.tick_rule_sell_volume),
            }
        )
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
            large=diagnostics,
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
        delta_method: str = "aggressor_side",
        contract_symbol_regex: str | None = None,
    ) -> None:
        self.root_symbol = root_symbol
        self.timezone = timezone
        self.large_trade_sizes = large_trade_sizes
        self.active_contract_mode = active_contract_mode
        self.delta_method = normalize_delta_method(delta_method)
        self.contract_symbol_regex = normalize_contract_symbol_regex(contract_symbol_regex)
        self._contract_symbol_pattern = (
            re.compile(self.contract_symbol_regex) if self.contract_symbol_regex else None
        )
        self._current: dict[str, MinuteAccumulator] = {}
        self._session_volume: dict[tuple[str, str], float] = {}
        self._last_flushed_minute_by_contract: dict[str, Any] = {}
        self.accepted_contract_ticks: dict[str, int] = {}
        self.unmatched_contract_ticks: dict[str, int] = {}
        self.unmatched_contract_ticks_ignored = 0
        self.last_unmatched_contract_tick: dict[str, Any] | None = None
        self.late_ticks_ignored = 0
        self.last_late_tick: dict[str, Any] | None = None

    def update(self, tick: TradeTick) -> list[SourceMinuteBar]:
        if tick.action and normalize_action(tick.action) != "T":
            return []
        if not self._accept_contract_symbol(tick):
            return []
        tick_minute = tick.timestamp_utc.floor("min")
        if self._was_minute_already_flushed(tick.contract_symbol, tick_minute):
            self._record_late_tick(tick, tick_minute, reason="minute_already_flushed")
            return []
        completed: list[SourceMinuteBar] = []
        for contract, acc in list(self._current.items()):
            if acc.minute_utc < tick_minute:
                bar = acc.to_bar(self.root_symbol, "live")
                completed.append(bar)
                self._record_completed_bar(bar)
                del self._current[contract]

        acc = self._current.get(tick.contract_symbol)
        if acc is None:
            self._current[tick.contract_symbol] = MinuteAccumulator.start(tick, self.large_trade_sizes, self.delta_method)
        elif acc.minute_utc == tick_minute:
            acc.add(tick, self.large_trade_sizes)
        elif acc.minute_utc > tick_minute:
            self._record_late_tick(tick, tick_minute, reason="older_than_current_accumulator")
            return self._select_active_bars(completed)
        else:
            bar = acc.to_bar(self.root_symbol, "live")
            completed.append(bar)
            self._record_completed_bar(bar)
            self._current[tick.contract_symbol] = MinuteAccumulator.start(tick, self.large_trade_sizes, self.delta_method)
        return self._select_active_bars(completed)

    def _accept_contract_symbol(self, tick: TradeTick) -> bool:
        symbol = str(tick.contract_symbol or "")
        if self._contract_symbol_pattern is None or self._contract_symbol_pattern.match(symbol):
            self.accepted_contract_ticks[symbol] = self.accepted_contract_ticks.get(symbol, 0) + 1
            return True
        self.unmatched_contract_ticks_ignored += 1
        self.unmatched_contract_ticks[symbol] = self.unmatched_contract_ticks.get(symbol, 0) + 1
        self.last_unmatched_contract_tick = {
            "timestamp_utc": format_timestamp(normalize_utc_timestamp(tick.timestamp_utc)),
            "contract_symbol": symbol,
            "price": float(tick.price),
            "size": float(tick.size),
            "contract_symbol_regex": self.contract_symbol_regex,
            "reason": "contract_symbol did not match configured databento.contract_symbol_regex",
        }
        return False

    def flush_completed_bars(
        self,
        *,
        now_utc: Any,
        flush_delay_seconds: float,
        source: str = "live_heartbeat",
    ) -> list[SourceMinuteBar]:
        now = normalize_utc_timestamp(now_utc)
        safe_through = now - pd.Timedelta(seconds=max(0.0, float(flush_delay_seconds)))
        completed: list[SourceMinuteBar] = []
        for contract, acc in list(self._current.items()):
            minute_end = acc.minute_utc + pd.Timedelta(minutes=1)
            if minute_end <= safe_through:
                bar = acc.to_bar(self.root_symbol, source)
                completed.append(bar)
                self._record_completed_bar(bar)
                del self._current[contract]
        return self._select_active_bars(completed)

    def _record_completed_bar(self, bar: SourceMinuteBar) -> None:
        self._add_session_volume(bar)
        current = self._last_flushed_minute_by_contract.get(bar.contract_symbol)
        if current is None or pd.Timestamp(bar.timestamp_utc) > pd.Timestamp(current):
            self._last_flushed_minute_by_contract[bar.contract_symbol] = bar.timestamp_utc

    def _was_minute_already_flushed(self, contract_symbol: str, tick_minute: Any) -> bool:
        last = self._last_flushed_minute_by_contract.get(contract_symbol)
        return last is not None and pd.Timestamp(tick_minute) <= pd.Timestamp(last)

    def _record_late_tick(self, tick: TradeTick, tick_minute: Any, *, reason: str) -> None:
        self.late_ticks_ignored += 1
        self.last_late_tick = {
            "timestamp_utc": format_timestamp(normalize_utc_timestamp(tick.timestamp_utc)),
            "minute_utc": format_timestamp(normalize_utc_timestamp(tick_minute)),
            "contract_symbol": tick.contract_symbol,
            "price": float(tick.price),
            "size": float(tick.size),
            "reason": reason,
        }

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


@dataclass
class LiveHealth:
    started_monotonic: float
    last_record_monotonic: float | None = None
    last_tick_monotonic: float | None = None
    last_completed_bar_monotonic: float | None = None
    last_tick_event_timestamp_utc: str | None = None
    last_tick_clock_lag_seconds: float | None = None
    max_tick_clock_lag_seconds: float = 0.0
    max_tick_clock_future_seconds: float = 0.0
    records_received: int = 0
    ticks_received: int = 0
    completed_bars: int = 0
    heartbeat_flushed_bars: int = 0
    dropped_partial_bars: int = 0
    late_trade_ticks_ignored: int = 0
    last_late_trade_tick: dict[str, Any] | None = None
    accepted_contract_ticks: dict[str, int] = field(default_factory=dict)
    unmatched_contract_ticks_ignored: int = 0
    unmatched_contract_ticks: dict[str, int] = field(default_factory=dict)
    last_unmatched_contract_tick: dict[str, Any] | None = None
    contract_symbol_regex: str | None = None
    alerts_emitted: dict[str, float] = field(default_factory=dict)


@dataclass
class AlertSinkHealth:
    writes_succeeded: int = 0
    writes_failed: int = 0
    duplicates_skipped: int = 0
    freshness_skipped: int = 0
    last_success_utc: str | None = None
    last_duplicate_utc: str | None = None
    last_duplicate_alert_id: str | None = None
    last_duplicate_id_field: str | None = None
    last_freshness_skip_utc: str | None = None
    last_freshness_skip_alert_id: str | None = None
    last_freshness_skip_reason: str | None = None
    last_error_utc: str | None = None
    last_error_type: str | None = None
    last_error: str | None = None


@dataclass
class OperatorSoundHealth:
    attempts: int = 0
    bells_written: int = 0
    commands_started: int = 0
    command_failures: int = 0
    command_skips: int = 0
    cleanup_terminated: int = 0
    cleanup_killed: int = 0
    last_kind: str | None = None
    last_command: str | None = None
    last_success_utc: str | None = None
    last_skip_utc: str | None = None
    last_skip_reason: str | None = None
    last_error_utc: str | None = None
    last_error_type: str | None = None
    last_error: str | None = None


@dataclass(frozen=True)
class SourceBarQualityIssue:
    severity: str
    code: str
    message: str
    bar_index: int | None = None
    timestamp_utc: str | None = None
    contract_symbol: str | None = None
    source: str | None = None


@dataclass(frozen=True)
class DataRequirement:
    strategy_id: str
    strategy_name: str
    timeframe: str
    source_timeframe: str
    feature_families: tuple[str, ...]
    source_columns: tuple[str, ...]
    derived_feature_columns: tuple[str, ...]
    large_trade_sizes: tuple[int, ...]
    max_feature_window_bars: int
    min_warmup_sessions: int
    recommended_source_bars: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EngineSignal:
    direction: str
    level_type: str
    swept_level: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    report_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReadinessProbeSignal:
    direction: str
    level_type: str
    swept_level: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    report_fields: dict[str, Any] = field(default_factory=dict)
    sweep_low: float | None = None
    sweep_high: float | None = None
    opening_range_low: float | None = None
    opening_range_high: float | None = None
    opening_range_width: float | None = None
    prev_rth_close: float | None = None


class DeltaIntervalStrategy:
    name = "dummy_delta_interval"

    def __init__(self, config: dict[str, Any]) -> None:
        params = dict(config.get("params", {}))
        self.params = params
        self.interval_bars = int(params.get("interval_bars", 5))
        self.delta_window_bars = int(params.get("delta_window_bars", self.interval_bars))
        self.delta_mode = str(params.get("delta_mode", "window_sum")).lower()
        self.delta_column = str(params.get("delta_column", "signed_volume"))
        self.min_abs_delta = float(params.get("min_abs_delta", 0.0))
        self.stop_mode = str(params.get("stop_mode", "bar_extreme")).lower()
        self.stop_points = float(params.get("stop_points", 1.0))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1000000))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.session_bar_counts: dict[str, int] = {}
        self.session_deltas: dict[str, list[float]] = {}
        if self.interval_bars <= 0:
            raise ValueError("builtin_delta_interval.params.interval_bars must be greater than 0.")
        if self.delta_window_bars <= 0:
            raise ValueError("builtin_delta_interval.params.delta_window_bars must be greater than 0.")
        if self.stop_points <= 0:
            raise ValueError("builtin_delta_interval.params.stop_points must be greater than 0.")
        if self.target_r_multiple <= 0:
            raise ValueError("builtin_delta_interval.params.target_r_multiple must be greater than 0.")

    def on_bar_close(self, bar: Any, trades_today: int = 0) -> EngineSignal | None:
        if trades_today >= self.max_trades_per_day:
            return None
        session_key = session_key_from_row(bar)
        bar_number = self.session_bar_counts.get(session_key, 0) + 1
        self.session_bar_counts[session_key] = bar_number
        current_delta = finite_float(bar.get(self.delta_column))
        current_delta = 0.0 if current_delta is None else current_delta
        deltas = self.session_deltas.setdefault(session_key, [])
        deltas.append(current_delta)
        if (bar_number - 1) % self.interval_bars != 0:
            return None
        if self.delta_mode in {"bar", "current_bar", "current"}:
            delta = current_delta
        elif self.delta_mode in {"window_sum", "sum", "rolling_sum"}:
            delta = float(sum(deltas[-self.delta_window_bars :]))
        else:
            raise ValueError("builtin_delta_interval.params.delta_mode must be window_sum or current_bar.")
        if abs(delta) <= self.min_abs_delta:
            return None
        direction = "long" if delta > 0 else "short"
        timestamp = str(bar.get("timestamp", ""))
        timestamp_utc = str(bar.get("timestamp_utc", ""))
        bar_high = finite_float(bar.get("high"))
        bar_low = finite_float(bar.get("low"))
        bar_volume = finite_float(bar.get("volume"))
        bar_buy_volume = finite_float(bar.get("buy_volume"))
        bar_sell_volume = finite_float(bar.get("sell_volume"))
        bar_trades = finite_float(bar.get("trades"))
        metadata = {
            "bar_number": bar_number,
            "interval_bars": self.interval_bars,
            "delta_column": self.delta_column,
            "delta": delta,
            "current_bar_delta": current_delta,
            "delta_mode": self.delta_mode,
            "delta_window_bars": self.delta_window_bars,
            "latest_completed_bar_timestamp": timestamp,
            "latest_completed_bar_timestamp_utc": timestamp_utc,
            "latest_completed_bar_high": bar_high,
            "latest_completed_bar_low": bar_low,
            "latest_completed_bar_volume": bar_volume,
            "latest_completed_bar_buy_volume": bar_buy_volume,
            "latest_completed_bar_sell_volume": bar_sell_volume,
            "latest_completed_bar_trades": bar_trades,
            "latest_completed_bar_selected_delta_unclassified_volume": finite_float(
                bar.get("selected_delta_unclassified_volume")
            ),
            "latest_completed_bar_databento_buy_aggressor_volume": finite_float(
                bar.get("databento_buy_aggressor_volume")
            ),
            "latest_completed_bar_databento_sell_aggressor_volume": finite_float(
                bar.get("databento_sell_aggressor_volume")
            ),
            "latest_completed_bar_databento_unknown_side_volume": finite_float(
                bar.get("databento_unknown_side_volume")
            ),
            "latest_completed_bar_databento_aggressor_delta": finite_float(bar.get("databento_aggressor_delta")),
            "latest_completed_bar_quote_buy_volume": finite_float(bar.get("quote_buy_volume")),
            "latest_completed_bar_quote_sell_volume": finite_float(bar.get("quote_sell_volume")),
            "latest_completed_bar_quote_unclassified_volume": finite_float(bar.get("quote_unclassified_volume")),
            "latest_completed_bar_quote_delta": finite_float(bar.get("quote_delta")),
            "latest_completed_bar_tick_rule_buy_volume": finite_float(bar.get("tick_rule_buy_volume")),
            "latest_completed_bar_tick_rule_sell_volume": finite_float(bar.get("tick_rule_sell_volume")),
            "latest_completed_bar_tick_rule_unclassified_volume": finite_float(
                bar.get("tick_rule_unclassified_volume")
            ),
            "latest_completed_bar_tick_rule_delta": finite_float(bar.get("tick_rule_delta")),
            "stop_mode": self.stop_mode,
            "stop_points": self.stop_points,
            "target_r_multiple": self.target_r_multiple,
            "rule": "trade first completed 1-minute bar, then every N bars; positive selected delta long, negative selected delta short",
        }
        return EngineSignal(
            direction=direction,
            level_type="dummy_delta_interval",
            metadata=metadata,
            report_fields={
                "dummy_bar_number": bar_number,
                "dummy_delta": delta,
                "dummy_signal_timestamp": timestamp,
            },
        )

    def stop_price(
        self,
        signal: EngineSignal,
        direction: str,
        tick_size: float,
        entry_price: float | None = None,
    ) -> float | None:
        if self.stop_mode in {"bar_extreme", "latest_bar_extreme", "completed_bar_extreme"}:
            key = "latest_completed_bar_low" if direction == "long" else "latest_completed_bar_high"
            raw = finite_float(signal.metadata.get(key))
            if raw is not None:
                return round_to_tick(raw, tick_size)
        if entry_price is None:
            return None
        stop_points = float(signal.metadata.get("stop_points", self.stop_points))
        raw = entry_price - stop_points if direction == "long" else entry_price + stop_points
        return round_to_tick(raw, tick_size)

    def target_price(
        self,
        entry_price: float,
        stop_price: float,
        direction: str,
        signal: EngineSignal | None = None,
    ) -> float:
        risk = abs(float(entry_price) - float(stop_price))
        multiple = self.target_r_multiple
        if signal is not None:
            multiple = float(signal.metadata.get("target_r_multiple", multiple))
        raw = entry_price + risk * multiple if direction == "long" else entry_price - risk * multiple
        return round_to_tick(raw, self.tick_size)


class StrategyRuntime:
    def __init__(
        self,
        *,
        project_root: Path,
        config_dir: Path,
        strategy_spec: dict[str, Any],
        engine_config: dict[str, Any],
        operator_config: dict[str, Any] | None = None,
    ) -> None:
        self.project_root = project_root
        self.config_dir = config_dir
        self.strategy_spec = strategy_spec
        self.engine_config = engine_config
        self.operator_config = dict(operator_config or {})
        self.strategy_type = str(strategy_spec.get("type", "campaign")).lower()
        self.is_builtin = self.strategy_type in {"builtin_delta_interval", "dummy_delta_interval", "delta_interval"}
        if self.is_builtin:
            self.strategy_config_path = None
            self.variant_config = build_builtin_variant_config(strategy_spec, engine_config)
        else:
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
            or (self.strategy_config_path.stem if self.strategy_config_path is not None else self.strategy_type)
        )
        self.strategy_config_label = (
            str(self.strategy_config_path) if self.strategy_config_path is not None else f"builtin:{self.strategy_type}"
        )
        self.engine_config_label = str(engine_config.get("_engine_config_label") or "<execution_engine_config>")
        engine_config_fingerprint = engine_config.get("_engine_config_fingerprint")
        self.engine_config_fingerprint = (
            copy.deepcopy(engine_config_fingerprint)
            if isinstance(engine_config_fingerprint, dict)
            else config_fingerprint_payload(engine_config, kind="execution_engine_config", path=self.engine_config_label)
        )
        self.strategy_config_fingerprint = config_fingerprint_payload(
            self.variant_config,
            kind="builtin_strategy" if self.is_builtin else "campaign_strategy",
            path=self.strategy_config_label,
        )
        validate_strategy_trade_mechanics(self.variant_config, strategy_id=self.strategy_id)
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
        self.active_contract_mode = validate_active_contract_mode(
            engine_config.get("active_contract_mode", "highest_session_volume")
        )
        self.contract_symbol_regex = normalize_contract_symbol_regex(engine_config.get("contract_symbol_regex"))
        self._contract_symbol_pattern = re.compile(self.contract_symbol_regex) if self.contract_symbol_regex else None
        self.trade_sanity_config = normalize_trade_sanity_config(engine_config.get("trade_sanity", {}))
        self.timeframe = self.variant_config.get("timeframe") or self.data_config.get("timeframe") or "1m"
        self.timeframe_minutes = parse_timeframe_minutes(self.timeframe)
        self.strategy = self._build_strategy()
        self.last_processed_strategy_timestamp: Any | None = None
        self.last_evaluated_strategy_timestamp: Any | None = None
        self.processed_strategy_row_keys: set[tuple[str, str]] = set()
        self.evaluated_strategy_row_count = 0
        self.duplicate_strategy_row_skips = 0
        self.non_active_contract_filter_drops = 0
        self.last_contract_filter_report: dict[str, Any] | None = None
        self._reported_non_active_contract_keys: set[tuple[str, str]] = set()
        self._last_contract_filter_alert_monotonic: float | None = None
        self.trades_by_session: dict[str, int] = {}
        self.sent_signal_keys: set[str] = set()
        self.feature_quality_config = normalize_feature_quality_config(engine_config.get("feature_quality", {}))
        self.feature_quality_skip_count = 0
        self.last_feature_quality_issue: dict[str, Any] | None = None
        self._last_feature_quality_alert_monotonic: float | None = None
        self.disabled = False
        self.disabled_reason: str | None = None
        self.error_count = 0
        self.last_error_utc: str | None = None
        self.last_error_type: str | None = None
        self.last_error: str | None = None
        self.warnings = (
            []
            if self.is_builtin
            else validate_strategy_variant(self.variant_config, self.strategy_config_path, self.project_root)
        )

    def preflight_report(self) -> dict[str, Any]:
        strategy = self.variant_config.get("strategy", {})
        return {
            "id": self.strategy_id,
            "strategy_name": self.variant_config.get("strategy_name", getattr(self.strategy, "name", None)),
            "config": self.strategy_config_label,
            "config_fingerprint": self.strategy_config_fingerprint,
            "engine_config": self.engine_config_label,
            "engine_config_fingerprint": self.engine_config_fingerprint,
            "type": self.strategy_type,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timeframe_minutes": self.timeframe_minutes,
            "disabled": self.disabled,
            "runtime_error_count": self.error_count,
            "feature_quality_skip_count": self.feature_quality_skip_count,
            "last_feature_quality_issue": self.last_feature_quality_issue,
            "processed_strategy_row_count": len(self.processed_strategy_row_keys),
            "evaluated_strategy_row_count": self.evaluated_strategy_row_count,
            "last_evaluated_strategy_timestamp": format_timestamp(self.last_evaluated_strategy_timestamp)
            if self.last_evaluated_strategy_timestamp is not None
            else None,
            "duplicate_strategy_row_skips": self.duplicate_strategy_row_skips,
            "active_contract_mode": self.active_contract_mode,
            "contract_symbol_regex": self.contract_symbol_regex,
            "non_active_contract_filter_drops": self.non_active_contract_filter_drops,
            "last_contract_filter_report": self.last_contract_filter_report,
            "modules": {
                "entry": nested_get(strategy, "entry", "module"),
                "sl": nested_get(strategy, "sl", "module"),
                "tp": nested_get(strategy, "tp", "module"),
            },
            "warnings": self.warnings,
        }

    def data_requirements(self) -> DataRequirement:
        data = self.data_config
        source_columns: set[str] = {
            "timestamp",
            "timestamp_utc",
            "symbol",
            "contract_symbol",
            "open",
            "high",
            "low",
            "close",
            "volume",
        }
        feature_families: set[str] = {"ohlcv"}
        derived_columns: set[str] = set()
        large_trade_sizes: set[int] = set()
        reasons: list[str] = []
        max_window = max(1, self.timeframe_minutes)
        min_warmup_sessions = 0
        source_timeframe = str(data.get("source_timeframe", "1m"))

        entry_cfg = nested_get(self.variant_config, "strategy", "entry") or {}
        entry_module = str(entry_cfg.get("module", ""))
        entry_params = dict(entry_cfg.get("params", {})) if isinstance(entry_cfg.get("params"), dict) else {}

        if self.is_builtin:
            delta_column = str(entry_params.get("delta_column", "signed_volume"))
            if delta_column not in {"open", "high", "low", "close", "volume"}:
                source_columns.add(delta_column)
                # These columns are included in setup/entry metadata and keep
                # diagnostic readouts from being built from inferred zeros.
                source_columns.update({"buy_volume", "sell_volume", "trades"})
                feature_families.add("trade_delta")
                reasons.append(f"builtin strategy uses delta_column={delta_column!r}")
            max_window = max(
                max_window,
                int(entry_params.get("delta_window_bars", entry_params.get("interval_bars", 1)) or 1),
            )

        trade_cfg = dict(data.get("trade_orderflow_features") or {})
        orderflow_combo_cfg = dict(data.get("orderflow_recent_pocket_combo_features") or {})
        referenced_feature_columns = collect_feature_column_references(entry_params)
        uses_trade_orderflow = (
            bool(trade_cfg.get("enabled", False))
            or bool(orderflow_combo_cfg.get("enabled", False))
            or "trade_orderflow" in entry_module
            or contains_trade_orderflow_reference(entry_params)
        )
        if uses_trade_orderflow:
            source_columns.update({"signed_volume", "buy_volume", "sell_volume", "trades"})
            feature_families.add("trade_orderflow")
            reasons.append("strategy uses trade-orderflow features or entry modules")
            windows = [int(value) for value in trade_cfg.get("windows", []) if int(value) > 0]
            if not windows and bool(orderflow_combo_cfg.get("enabled", False)):
                windows = [15, 30]
            if windows:
                max_window = max(max_window, max(windows))
                for window in windows:
                    derived_columns.update(
                        {
                            f"trade_orderflow_volume_{window}",
                            f"trade_orderflow_signed_volume_{window}",
                            f"trade_orderflow_imbalance_{window}",
                            f"trade_orderflow_abs_imbalance_{window}",
                            f"trade_orderflow_trades_{window}",
                            f"trade_orderflow_avg_trade_size_{window}",
                            f"trade_orderflow_effort_vs_result_{window}",
                        }
                    )
            large_trade_sizes.update(int(value) for value in trade_cfg.get("large_trade_sizes", []) if int(value) > 0)
            for size in large_trade_sizes:
                source_columns.update({f"large{size}_signed_volume", f"large{size}_volume"})
            rank_cfg = dict(trade_cfg.get("same_clock_ranks") or {})
            if bool(rank_cfg.get("enabled", False)):
                feature_families.add("same_clock_ranks")
                rank_windows = [int(value) for value in rank_cfg.get("rank_windows", []) if int(value) > 0]
                if rank_windows:
                    min_warmup_sessions = max(min_warmup_sessions, max(rank_windows))
                for column in rank_cfg.get("columns", []) or []:
                    derived_columns.add(str(column))
                    for rank_window in rank_windows:
                        derived_columns.add(f"{column}_rank{rank_window}")

        vpin_cfg = dict(data.get("vpin_toxicity_features") or {})
        if bool(vpin_cfg.get("enabled", False)):
            feature_families.add("vpin_toxicity")
            source_columns.update({"volume"})
            max_window = max(max_window, int(vpin_cfg.get("bucket_lookback", 50) or 50))
            min_warmup_sessions = max(
                min_warmup_sessions,
                int(vpin_cfg.get("vpin_rank_window", 21) or 21),
                int(vpin_cfg.get("drawdown_rank_window", 21) or 21),
            )
            reasons.append("strategy uses VPIN toxicity features")

        derived_columns.update(referenced_feature_columns)
        referenced_large_trade_sizes = large_trade_sizes_from_feature_columns(referenced_feature_columns)
        if referenced_large_trade_sizes:
            missing_large_trade_sizes = sorted(referenced_large_trade_sizes - large_trade_sizes)
            large_trade_sizes.update(referenced_large_trade_sizes)
            for size in referenced_large_trade_sizes:
                source_columns.update({f"large{size}_signed_volume", f"large{size}_volume"})
            reasons.append(
                "strategy references large-trade feature size(s): "
                + ",".join(str(size) for size in sorted(referenced_large_trade_sizes))
            )
            if missing_large_trade_sizes and uses_trade_orderflow and bool(trade_cfg.get("enabled", False)):
                configured = sorted(
                    {int(value) for value in trade_cfg.get("large_trade_sizes", []) if int(value) > 0}
                    | set(missing_large_trade_sizes)
                )
                trade_cfg["large_trade_sizes"] = configured
                self.data_config["trade_orderflow_features"] = trade_cfg
                self.warnings.append(
                    "Inferred missing data.trade_orderflow_features.large_trade_sizes from entry feature "
                    f"references: {missing_large_trade_sizes}"
                )
        session_bars = estimate_session_bars(data, source_timeframe)
        recommended_source_bars = max(max_window, min_warmup_sessions * session_bars + max_window)
        return DataRequirement(
            strategy_id=self.strategy_id,
            strategy_name=str(self.variant_config.get("strategy_name", getattr(self.strategy, "name", None))),
            timeframe=str(self.timeframe),
            source_timeframe=source_timeframe,
            feature_families=tuple(sorted(feature_families)),
            source_columns=tuple(sorted(source_columns)),
            derived_feature_columns=tuple(sorted(derived_columns)),
            large_trade_sizes=tuple(sorted(large_trade_sizes)),
            max_feature_window_bars=int(max_window),
            min_warmup_sessions=int(min_warmup_sessions),
            recommended_source_bars=int(recommended_source_bars),
            reasons=tuple(reasons),
        )

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
        queued: list[PendingSignal] = []
        for _, row in features.iterrows():
            timestamp = row["timestamp"]
            row_key = strategy_row_identity_key(row)
            if row_key in self.processed_strategy_row_keys:
                self.duplicate_strategy_row_skips += 1
                continue
            session_key = session_key_from_row(row)
            trades_today = self.trades_by_session.get(session_key, 0)
            feature_issue = self.feature_row_quality_issue(row)
            if feature_issue is not None:
                self.last_processed_strategy_timestamp = timestamp
                self.processed_strategy_row_keys.add(row_key)
                self.record_feature_quality_skip(row, feature_issue)
                if (
                    feature_issue.get("missing_columns")
                    and bool(self.feature_quality_config.get("fail_on_missing_columns", True))
                ):
                    raise RuntimeError(
                        f"{self.strategy_id}: strategy feature row is missing required column(s): "
                        f"{feature_issue['missing_columns']}"
                    )
                continue
            signal_obj = self.strategy.on_bar_close(row, trades_today=trades_today)
            self.last_processed_strategy_timestamp = timestamp
            self.last_evaluated_strategy_timestamp = timestamp
            self.evaluated_strategy_row_count += 1
            self.processed_strategy_row_keys.add(row_key)
            if signal_obj is None:
                continue
            pending = self._pending_from_signal(row, signal_obj)
            if live:
                queued.append(pending)
            else:
                queued.append(pending)
        return queued

    def feature_row_quality_issue(self, row: Any) -> dict[str, Any] | None:
        if not bool(self.feature_quality_config.get("enabled", True)):
            return None
        required_columns = self.required_runtime_feature_columns()
        if not required_columns:
            return None
        missing = [column for column in required_columns if not row_has_key(row, column)]
        non_finite = [
            column
            for column in required_columns
            if column not in {"timestamp", "contract_symbol", "symbol"}
            and row_has_key(row, column)
            and not feature_value_is_finite(row_get(row, column))
        ]
        blank_identity = [
            column
            for column in ("contract_symbol", "symbol")
            if column in required_columns
            and row_has_key(row, column)
            and not str(row_get(row, column) or "").strip()
        ]
        bad_timestamp = []
        if "timestamp" in required_columns and row_has_key(row, "timestamp"):
            try:
                pd.Timestamp(row_get(row, "timestamp"))
            except Exception:
                bad_timestamp.append("timestamp")
        if not missing and not non_finite and not blank_identity and not bad_timestamp:
            return None
        max_columns = int(self.feature_quality_config.get("max_reported_columns", 20) or 20)
        return {
            "missing_columns": missing[:max_columns],
            "missing_columns_truncated": max(0, len(missing) - max_columns),
            "non_finite_columns": non_finite[:max_columns],
            "non_finite_columns_truncated": max(0, len(non_finite) - max_columns),
            "blank_identity_columns": blank_identity[:max_columns],
            "bad_timestamp_columns": bad_timestamp[:max_columns],
            "required_column_count": len(required_columns),
        }

    def required_runtime_feature_columns(self) -> list[str]:
        columns = {"timestamp", "contract_symbol"}
        if self.is_builtin and isinstance(self.strategy, DeltaIntervalStrategy):
            columns.add(self.strategy.delta_column)
            if self.strategy.stop_mode in {"bar_extreme", "latest_bar_extreme", "completed_bar_extreme"}:
                columns.update({"high", "low"})
        else:
            entry_params = dict(nested_get(self.variant_config, "strategy", "entry", "params") or {})
            columns.update(collect_feature_column_references(entry_params))
            columns.update(self.data_requirements().derived_feature_columns)
        return sorted(str(column) for column in columns if str(column).strip())

    def record_feature_quality_skip(self, row: Any, issue: dict[str, Any]) -> None:
        self.feature_quality_skip_count += 1
        timestamp = row_get(row, "timestamp")
        contract_symbol = row_get(row, "contract_symbol")
        payload = {
            "event": "strategy_feature_row_not_ready",
            "strategy_id": self.strategy_id,
            "strategy_name": self.variant_config.get("strategy_name", getattr(self.strategy, "name", None)),
            "timestamp": format_timestamp(timestamp) if timestamp is not None else None,
            "contract_symbol": str(contract_symbol) if contract_symbol is not None else None,
            "feature_quality_skip_count": self.feature_quality_skip_count,
            "issue": issue,
            "reason": "A completed strategy feature row was missing required columns or contained non-finite values.",
            "impact": "The strategy was not evaluated for this bar, so no setup or entry signal can be emitted from incomplete features.",
        }
        self.last_feature_quality_issue = payload
        repeat_seconds = float(self.feature_quality_config.get("alert_repeat_seconds", 120.0))
        now = time.monotonic()
        if (
            self._last_feature_quality_alert_monotonic is not None
            and repeat_seconds > 0
            and now - self._last_feature_quality_alert_monotonic < repeat_seconds
        ):
            return
        self._last_feature_quality_alert_monotonic = now
        print_json(payload, prefix="SYSTEM_ALERT")

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
        source = self.filter_active_contract_source(source)
        if source.empty:
            return source
        sessionized = assign_sessions(source, self.data_config)
        sessionized = filter_trading_sessions(sessionized)
        strategy_bars = aggregate_timeframe(sessionized, self.data_config, self.timeframe)
        features = build_features(strategy_bars, self.data_config)
        return features.sort_values("timestamp").reset_index(drop=True)

    def filter_active_contract_source(self, source: Any) -> Any:
        filtered, report = active_contract_source_filter_report(
            source,
            mode=self.active_contract_mode,
            timezone=self.timezone,
        )
        self.record_active_contract_filter_report(report)
        return filtered

    def record_active_contract_filter_report(self, report: dict[str, Any]) -> None:
        if not report.get("dropped_rows"):
            return
        dropped_keys = {
            (str(item.get("timestamp_utc") or item.get("timestamp") or ""), str(item.get("contract_symbol") or ""))
            for item in report.get("sample_dropped_rows", [])
        }
        dropped_keys.update(tuple(item) for item in report.get("dropped_row_keys", []))
        new_keys = {key for key in dropped_keys if key not in self._reported_non_active_contract_keys}
        if not new_keys:
            return
        self._reported_non_active_contract_keys.update(new_keys)
        self.non_active_contract_filter_drops += len(new_keys)
        self.last_contract_filter_report = {
            key: value
            for key, value in report.items()
            if key != "dropped_row_keys"
        }
        self.last_contract_filter_report["new_dropped_rows"] = len(new_keys)
        repeat_seconds = float(self.feature_quality_config.get("alert_repeat_seconds", 120.0))
        now = time.monotonic()
        if (
            self._last_contract_filter_alert_monotonic is not None
            and repeat_seconds > 0
            and now - self._last_contract_filter_alert_monotonic < repeat_seconds
        ):
            return
        self._last_contract_filter_alert_monotonic = now
        print_json(
            {
                "event": "non_active_contract_bars_filtered",
                "strategy_id": self.strategy_id,
                "strategy_name": self.variant_config.get("strategy_name", getattr(self.strategy, "name", None)),
                "active_contract_mode": self.active_contract_mode,
                "non_active_contract_filter_drops": self.non_active_contract_filter_drops,
                "report": self.last_contract_filter_report,
                "reason": "Multiple ES contracts were present in the strategy source frame and the active-contract policy selected one tradable contract per bar timestamp.",
                "impact": "Filtered bars are retained in raw inputs but are not evaluated by this strategy, preventing duplicate or lower-priority contract signals.",
            },
            prefix="SYSTEM_ALERT",
        )

    def setup_id_for_pending(
        self,
        pending: PendingSignal,
        *,
        direction: str,
        row_timestamp: pd.Timestamp,
        due_timestamp: pd.Timestamp,
        max_entry_lag_seconds: float,
    ) -> str:
        return alert_hash(
            "trade_setup",
            self.strategy_id,
            str(row_timestamp),
            direction,
            str(getattr(pending.signal_obj, "level_type", "")),
            str(due_timestamp),
            str(max_entry_lag_seconds),
        )

    def build_setup_notice(self, pending: PendingSignal) -> dict[str, Any]:
        direction = str(getattr(pending.signal_obj, "direction", "")).lower()
        core = copy.deepcopy(self.variant_config.get("core", {}))
        tick_size = float(core.get("tick_size", self.data_config.get("tick_size", 0.25)))
        stop_preview = None
        try:
            stop_preview = self.strategy.stop_price(
                pending.signal_obj,
                direction,
                tick_size,
                entry_price=None,
            )
        except Exception:
            stop_preview = None
        trade_plan_preview = self.build_setup_trade_plan_preview(
            pending,
            direction=direction,
            tick_size=tick_size,
            stop_preview=stop_preview,
        )
        row_timestamp = pd.Timestamp(pending.row["timestamp"])
        due_timestamp = pd.Timestamp(pending.due_utc).tz_convert("UTC")
        max_entry_lag_seconds = float(self.engine_config.get("max_entry_lag_seconds", 120))
        expires_at_utc = due_timestamp + pd.Timedelta(seconds=max_entry_lag_seconds)
        setup_id = self.setup_id_for_pending(
            pending,
            direction=direction,
            row_timestamp=row_timestamp,
            due_timestamp=due_timestamp,
            max_entry_lag_seconds=max_entry_lag_seconds,
        )
        return {
            "event": "trade_setup",
            "setup_contract_version": SETUP_NOTICE_CONTRACT_VERSION,
            "setup_id": setup_id,
            "pending_signal_key": pending.key,
            "strategy_id": self.strategy_id,
            "strategy_name": self.variant_config.get("strategy_name", getattr(self.strategy, "name", None)),
            "strategy_config": self.strategy_config_label,
            "strategy_config_fingerprint": copy.deepcopy(self.strategy_config_fingerprint),
            "engine_config": self.engine_config_label,
            "engine_config_fingerprint": copy.deepcopy(self.engine_config_fingerprint),
            "symbol": self.symbol,
            "contract_symbol": str(pending.row.get("contract_symbol", "")),
            "timeframe": self.timeframe,
            "signal_timestamp": format_timestamp(row_timestamp),
            "due_timestamp_utc": format_timestamp(due_timestamp),
            "expires_at_utc": format_timestamp(expires_at_utc),
            "max_entry_lag_seconds": max_entry_lag_seconds,
            "entry_window": {
                "entry_trigger": "first_matching_trade_tick_at_or_after_due_timestamp",
                "valid_from_utc": format_timestamp(due_timestamp),
                "expires_at_utc": format_timestamp(expires_at_utc),
                "max_entry_lag_seconds": max_entry_lag_seconds,
            },
            "session_date": str(pending.row.get("session_date", "")),
            "direction": direction,
            "side": "buy" if direction == "long" else "sell" if direction == "short" else "",
            "stop_loss_price_preview": finite_float(stop_preview),
            "trade_plan_preview": trade_plan_preview,
            "signal": signal_report(pending.signal_obj),
        }

    def build_setup_trade_plan_preview(
        self,
        pending: PendingSignal,
        *,
        direction: str,
        tick_size: float,
        stop_preview: Any,
    ) -> dict[str, Any]:
        preview: dict[str, Any] = {
            "schema_version": "trade_plan_preview.v1",
            "status": "unavailable",
            "executable": False,
            "entry_price_basis": "latest_completed_bar_close",
            "entry_price_type": "estimated_market_at_completed_bar_close",
            "reason": None,
        }
        if direction not in {"long", "short"}:
            preview["reason"] = "strategy signal direction is not long or short"
            return preview
        if tick_size <= 0:
            preview["reason"] = "tick_size must be positive"
            return preview
        core = copy.deepcopy(self.variant_config.get("core", {}))
        tick_value = finite_float(core.get("tick_value", 12.5))
        if tick_value is None or tick_value <= 0:
            preview["reason"] = "tick_value must be positive"
            return preview
        basis_price = finite_float(row_get(pending.row, "close"))
        if basis_price is None:
            preview["reason"] = "completed strategy row has no finite close price"
            return preview
        account = self.engine_config.get("account", {})
        account = account if isinstance(account, dict) else {}
        slippage_ticks = float(account.get("slippage_ticks", core.get("slippage_ticks", 0.0)))
        try:
            entry_price = estimated_market_entry(basis_price, direction, tick_size, slippage_ticks)
            stop_price = finite_float(stop_preview)
            if stop_price is None:
                stop_price = finite_float(
                    self.strategy.stop_price(
                        pending.signal_obj,
                        direction,
                        tick_size,
                        entry_price=entry_price,
                    )
                )
            if stop_price is None:
                preview["reason"] = "strategy did not produce a finite stop price preview"
                return preview
            target_price = finite_float(
                self.strategy.target_price(entry_price, stop_price, direction, signal=pending.signal_obj)
            )
            if target_price is None:
                preview["reason"] = "strategy did not produce a finite target price preview"
                return preview
            rounded_entry_price = round_to_tick(entry_price, tick_size)
            rounded_basis_price = round_to_tick(basis_price, tick_size)
            rounded_stop_price = round_to_tick(stop_price, tick_size)
            rounded_target_price = round_to_tick(target_price, tick_size)
            stop_points = abs(rounded_entry_price - rounded_stop_price)
            target_points = abs(rounded_target_price - rounded_entry_price)
            if stop_points <= 0 or target_points <= 0:
                preview["reason"] = "stop/target distance is non-positive after tick rounding"
                return preview
            if direction == "long" and not (rounded_stop_price < rounded_entry_price < rounded_target_price):
                preview["reason"] = "long stop/target are not on opposite sides of estimated entry"
                return preview
            if direction == "short" and not (rounded_target_price < rounded_entry_price < rounded_stop_price):
                preview["reason"] = "short stop/target are not on opposite sides of estimated entry"
                return preview
            sizing = self._size_position(core, stop_points, tick_size, tick_value, account)
            suggested_quantity = int(sizing.contracts)
            max_contracts = int(account.get("max_contracts", suggested_quantity or 0) or 0)
            min_contracts = int(account.get("min_contracts", 1) or 1)
            quantity = min(suggested_quantity, max_contracts) if max_contracts > 0 else suggested_quantity
            if quantity < min_contracts:
                preview["reason"] = "sizing preview produced quantity below minimum"
                preview["suggested_quantity"] = suggested_quantity
                preview["min_contracts"] = min_contracts
                return preview
            trade_sanity_violation = trade_sanity_violation_report(
                self.trade_sanity_config,
                direction=direction,
                entry_price=rounded_entry_price,
                stop_loss_price=rounded_stop_price,
                take_profit_price=rounded_target_price,
                stop_loss_points=stop_points,
                take_profit_points=target_points,
                tick_size=tick_size,
                tick_value=tick_value,
                quantity=quantity,
            )
            if trade_sanity_violation is not None:
                preview["reason"] = str(trade_sanity_violation["reason"])
                preview["trade_sanity"] = trade_sanity_violation
                return preview
            preview.update(
                {
                    "status": "estimated",
                    "reason": (
                        "Estimated from the latest completed strategy bar close. "
                        "Final entry waits for the first matching trade tick at or after due_timestamp_utc."
                    ),
                    "estimated_entry_basis_price": rounded_basis_price,
                    "estimated_entry_price": rounded_entry_price,
                    "entry_slippage_ticks": slippage_ticks,
                    "stop_loss_price": rounded_stop_price,
                    "take_profit_price": rounded_target_price,
                    "stop_loss_points": float(stop_points),
                    "take_profit_points": float(target_points),
                    "quantity": int(quantity),
                    "suggested_quantity": int(suggested_quantity),
                    "tick_size": float(tick_size),
                    "tick_value": float(tick_value),
                    "risk_dollars": float(stop_points / tick_size * tick_value * quantity),
                    "reward_dollars": float(target_points / tick_size * tick_value * quantity),
                    "sizing": sizing.report_fields(),
                }
            )
            return preview
        except Exception as exc:
            preview["reason"] = str(exc)
            preview["error_type"] = type(exc).__name__
            return preview

    def build_alert(self, pending: PendingSignal, tick: TradeTick, account: dict[str, Any]) -> dict[str, Any] | None:
        direction = str(getattr(pending.signal_obj, "direction", "")).lower()
        if direction not in {"long", "short"}:
            self.emit_reject(pending, "strategy signal direction is not long or short")
            return None
        expected_contract_for_regex = pending_contract_symbol(pending)
        if expected_contract_for_regex and not contract_symbol_matches_regex(
            expected_contract_for_regex,
            self._contract_symbol_pattern,
        ):
            self.emit_reject(
                pending,
                "pending setup contract_symbol does not match databento.contract_symbol_regex",
                extra={
                    "pending_contract_symbol": expected_contract_for_regex,
                    "contract_symbol_regex": self.contract_symbol_regex,
                },
            )
            return None
        entry_contract_for_regex = str(tick.contract_symbol or "").strip()
        if not contract_symbol_matches_regex(entry_contract_for_regex, self._contract_symbol_pattern):
            self.emit_reject(
                pending,
                "entry tick contract_symbol does not match databento.contract_symbol_regex",
                extra={
                    "entry_tick_contract_symbol": entry_contract_for_regex,
                    "contract_symbol_regex": self.contract_symbol_regex,
                    "entry_timestamp_utc": format_timestamp(tick.timestamp_utc),
                },
            )
            return None
        if bool(self.engine_config.get("entry_contract_match_required", True)):
            expected_contract = pending_contract_symbol(pending)
            actual_contract = str(tick.contract_symbol or "").strip()
            if not expected_contract:
                self.emit_reject(pending, "pending signal has no contract_symbol for contract-matched entry")
                return None
            if actual_contract != expected_contract:
                self.emit_reject(
                    pending,
                    "entry tick contract_symbol does not match pending setup contract_symbol",
                    extra={
                        "expected_contract_symbol": expected_contract,
                        "entry_tick_contract_symbol": actual_contract,
                        "entry_timestamp_utc": format_timestamp(tick.timestamp_utc),
                    },
                )
                return None
        side = "buy" if direction == "long" else "sell"
        core = copy.deepcopy(self.variant_config.get("core", {}))
        tick_size = float(core.get("tick_size", self.data_config.get("tick_size", 0.25)))
        tick_value = float(core.get("tick_value", 12.5))
        if tick_size <= 0 or tick_value <= 0:
            self.emit_reject(pending, "tick_size and tick_value must be positive")
            return None
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

        rounded_entry_price = round_to_tick(entry_price, tick_size)
        rounded_basis_price = round_to_tick(tick.price, tick_size)
        rounded_target_price = round_to_tick(target_price, tick_size)
        rounded_stop_price = round_to_tick(stop_price, tick_size)
        stop_points = abs(rounded_entry_price - rounded_stop_price)
        target_points = abs(rounded_target_price - rounded_entry_price)
        if stop_points <= 0 or target_points <= 0:
            self.emit_reject(pending, "stop/target distance is non-positive after tick rounding")
            return None
        if direction == "long" and not (rounded_stop_price < rounded_entry_price < rounded_target_price):
            self.emit_reject(pending, "long stop/target are not on opposite sides of entry after tick rounding")
            return None
        if direction == "short" and not (rounded_target_price < rounded_entry_price < rounded_stop_price):
            self.emit_reject(pending, "short stop/target are not on opposite sides of entry after tick rounding")
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
        trade_sanity_violation = trade_sanity_violation_report(
            self.trade_sanity_config,
            direction=direction,
            entry_price=rounded_entry_price,
            stop_loss_price=rounded_stop_price,
            take_profit_price=rounded_target_price,
            stop_loss_points=stop_points,
            take_profit_points=target_points,
            tick_size=tick_size,
            tick_value=tick_value,
            quantity=quantity,
        )
        if trade_sanity_violation is not None:
            self.emit_reject(
                pending,
                str(trade_sanity_violation["reason"]),
                extra={"trade_sanity": trade_sanity_violation},
            )
            return None

        self._record_trade(pending.row)
        self.sent_signal_keys.add(pending.key)
        alert_id = alert_hash(
            "entry_signal",
            self.strategy_id,
            str(pending.row["timestamp"]),
            direction,
            str(getattr(pending.signal_obj, "level_type", "")),
            str(tick.timestamp_utc),
        )
        row_timestamp = pd.Timestamp(pending.row["timestamp"])
        due_timestamp = pd.Timestamp(pending.due_utc).tz_convert("UTC")
        max_entry_lag_seconds = float(self.engine_config.get("max_entry_lag_seconds", 120))
        setup_id = self.setup_id_for_pending(
            pending,
            direction=direction,
            row_timestamp=row_timestamp,
            due_timestamp=due_timestamp,
            max_entry_lag_seconds=max_entry_lag_seconds,
        )
        entry_timestamp = pd.Timestamp(tick.timestamp_utc)
        price_normalization = price_normalization_report(
            tick_size=tick_size,
            entry_basis_price_raw=tick.price,
            entry_price_raw=entry_price,
            stop_loss_price_raw=stop_price,
            take_profit_price_raw=target_price,
            entry_basis_price=rounded_basis_price,
            entry_price=rounded_entry_price,
            stop_loss_price=rounded_stop_price,
            take_profit_price=rounded_target_price,
        )
        alert = {
            "event": "entry_signal",
            "alert_contract_version": ALERT_CONTRACT_VERSION,
            "alert_id": alert_id,
            "setup_id": setup_id,
            "pending_signal_key": pending.key,
            "strategy_id": self.strategy_id,
            "strategy_name": self.variant_config.get("strategy_name", getattr(self.strategy, "name", None)),
            "strategy_config": self.strategy_config_label,
            "strategy_config_fingerprint": copy.deepcopy(self.strategy_config_fingerprint),
            "engine_config": self.engine_config_label,
            "engine_config_fingerprint": copy.deepcopy(self.engine_config_fingerprint),
            "symbol": self.symbol,
            "contract_symbol": tick.contract_symbol,
            "timeframe": self.timeframe,
            "delta_method": self.engine_config.get("delta_method"),
            "signal_timestamp": format_timestamp(row_timestamp),
            "entry_timestamp": format_timestamp(entry_timestamp),
            "entry_timestamp_utc": format_timestamp(entry_timestamp.tz_convert("UTC")),
            "session_date": str(pending.row.get("session_date", "")),
            "direction": direction,
            "side": side,
            "quantity": int(quantity),
            "suggested_quantity": int(suggested_quantity),
            "order_type": "market",
            "entry_price": rounded_entry_price,
            "entry_basis_price": rounded_basis_price,
            "entry_slippage_ticks": slippage_ticks,
            "take_profit_price": rounded_target_price,
            "stop_loss_price": rounded_stop_price,
            "take_profit_points": float(target_points),
            "stop_loss_points": float(stop_points),
            "tick_size": tick_size,
            "tick_value": tick_value,
            "risk_dollars": float(stop_points / tick_size * tick_value * quantity),
            "reward_dollars": float(target_points / tick_size * tick_value * quantity),
            "price_normalization": price_normalization,
            "signal": signal_report(pending.signal_obj),
            "sizing": sizing.report_fields(),
        }
        execution_intents_cfg = self.engine_config.get("execution_intents")
        execution_intents_cfg = execution_intents_cfg if isinstance(execution_intents_cfg, dict) else {}
        alert["execution_intent"] = build_execution_intent(
            alert,
            max_entry_lag_seconds=max_entry_lag_seconds,
            intent_ttl_seconds=float(execution_intents_cfg.get("intent_ttl_seconds", 30.0)),
        )
        return alert

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
        if bool(self.operator_config.get("print_rejection_readable", True)):
            print(format_rejection_readout(payload), flush=True)

    def _build_strategy(self) -> Any:
        if self.is_builtin:
            if self.strategy_type in {"builtin_delta_interval", "dummy_delta_interval", "delta_interval"}:
                return DeltaIntervalStrategy(self.variant_config.get("strategy", {}).get("entry", {}))
            raise ValueError(f"Unsupported builtin strategy type: {self.strategy_type}")

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
        validate_engine_runtime_config(self.engine_config, self.databento_config)
        self.engine_config_label = str(self.config_path)
        self.engine_config_fingerprint = config_fingerprint_payload(
            {
                "engine": self.engine_config,
                "databento": self.databento_config,
                "strategies": self.config.get("strategies", []),
            },
            kind="execution_engine_config",
            path=self.engine_config_label,
        )
        self.dry_run_alerts = bool(self.engine_config.get("dry_run_alerts", False))
        self.delta_method = normalize_delta_method(self.databento_config.get("delta_method", "aggressor_side"))
        self.symbol = str(self.engine_config.get("symbol") or self.databento_config.get("root_symbol") or DEFAULT_SYMBOL)
        self.timezone = str(self.engine_config.get("timezone") or self.databento_config.get("timezone") or DEFAULT_TIMEZONE)
        self.contract_symbol_regex = normalize_contract_symbol_regex(
            self.databento_config.get("contract_symbol_regex")
        )
        self._contract_symbol_pattern = re.compile(self.contract_symbol_regex) if self.contract_symbol_regex else None
        self.store = BarStore(config_int(self.engine_config, "max_source_bars", 50000, min_value=1))
        self.account = dict(self.engine_config.get("account", {}))
        self.alert_prefix = str(self.engine_config.get("alert_prefix", DEFAULT_ALERT_PREFIX))
        self.process_lock_config = normalize_process_lock_config(self.engine_config.get("process_lock", {}))
        self.process_lock_path = resolve_optional_path(self.config_dir, self.process_lock_config.get("path"))
        self.process_lock_token: str | None = None
        self.process_lock_acquired = False
        self.output_path_readiness_config = normalize_output_path_readiness_config(
            self.engine_config.get("output_path_readiness", {})
        )
        self.alerts_path = resolve_optional_path(self.config_dir, self.engine_config.get("alerts_path"))
        self.alert_file_config = normalize_alert_file_config(self.engine_config.get("alert_file", {}))
        self.alert_sink = AlertSinkHealth()
        self.alert_seen_ids = load_existing_jsonl_alert_ids(
            self.alerts_path,
            sink=self.alert_sink,
            sink_label="alert_file",
            fail_on_error=bool(self.alert_file_config.get("fail_on_write_error", False)),
            expected_version_field="alert_contract_version",
            expected_version_value=ALERT_CONTRACT_VERSION,
        ) if bool(self.alert_file_config.get("suppress_duplicate_alert_ids", False)) else set()
        self.setup_alerts_config = normalize_setup_alerts_config(self.engine_config.get("setup_alerts", {}))
        self.setup_alerts_path = resolve_optional_path(
            self.config_dir,
            self.setup_alerts_config.get("path"),
        )
        self.setup_notice_sink = AlertSinkHealth()
        self.setup_seen_ids = load_existing_jsonl_alert_ids(
            self.setup_alerts_path,
            sink=self.setup_notice_sink,
            sink_label="setup_alerts",
            fail_on_error=bool(self.setup_alerts_config.get("fail_on_write_error", False)),
            id_fields=("setup_id",),
        ) if bool(self.setup_alerts_config.get("suppress_duplicate_setup_ids", True)) else set()
        self.execution_intents_config = normalize_execution_intents_config(
            self.engine_config.get("execution_intents", {})
        )
        self.execution_intents_path = resolve_optional_path(
            self.config_dir,
            self.execution_intents_config.get("path"),
        )
        self.execution_intent_sink = AlertSinkHealth()
        self.execution_intent_seen_ids = load_existing_jsonl_alert_ids(
            self.execution_intents_path,
            sink=self.execution_intent_sink,
            sink_label="execution_intents",
            fail_on_error=bool(self.execution_intents_config.get("fail_on_write_error", False)),
            id_fields=execution_intent_duplicate_id_fields(self.execution_intents_config),
            expected_record_schema_version=EXECUTION_INTENT_RECORD_VERSION,
        ) if execution_intent_duplicate_suppression_enabled(self.execution_intents_config) else set()
        self.data_quality_config = normalize_source_bar_quality_config(self.engine_config.get("data_quality", {}))
        self.feature_quality_config = normalize_feature_quality_config(self.engine_config.get("feature_quality", {}))
        self.strategy_error_config = normalize_strategy_error_config(self.engine_config.get("strategy_errors", {}))
        self.trade_sanity_config = normalize_trade_sanity_config(self.engine_config.get("trade_sanity", {}))
        self.operator_config = dict(self.engine_config.get("operator", {}))
        self.operator_sound_health = OperatorSoundHealth()
        self.operator_sound_processes: list[Any] = []
        self.pending: list[PendingSignal] = []
        self.setup_notice_count = 0
        self.alert_count = 0
        self.source_bar_quality_drops = 0
        self.source_bar_quality_error_count = 0
        self.source_bar_quality_warning_count = 0
        self.last_source_bar_quality_report: dict[str, Any] | None = None
        self.source_contract_filter_drops = 0
        self.last_source_contract_filter_report: dict[str, Any] | None = None
        self._reported_source_contract_filter_keys: set[tuple[str, str]] = set()
        self._last_source_contract_filter_alert_monotonic: float | None = None
        self.entry_contract_mismatch_skips = 0
        self.last_entry_contract_mismatch: dict[str, Any] | None = None
        self._last_entry_contract_mismatch_alert_monotonic: float | None = None
        self.entry_contract_regex_skips = 0
        self.last_entry_contract_regex_skip: dict[str, Any] | None = None
        self._last_entry_contract_regex_alert_monotonic: float | None = None
        self.pending_expired_count = 0
        self.lock = threading.RLock()
        self.strategies = self._load_strategies()
        self.data_requirements = [strategy.data_requirements() for strategy in self.strategies]
        self.data_plan = build_engine_data_plan(self)
        validate_engine_data_plan(self)

    def preflight_report(self) -> dict[str, Any]:
        historical = dict(self.databento_config.get("historical", {}))
        live = dict(self.databento_config.get("live", {}))
        return {
            "event": "preflight",
            "config": str(self.config_path),
            "engine_config": self.engine_config_label,
            "engine_config_fingerprint": copy.deepcopy(self.engine_config_fingerprint),
            "project_root": str(self.project_root),
            "symbol": self.symbol,
            "timezone": self.timezone,
            "databento": {
                "dataset": self.databento_config.get("dataset", DEFAULT_DATASET),
                "schema": self.databento_config.get("schema", DEFAULT_SCHEMA),
                "symbols": self.databento_config.get("symbols", DEFAULT_DATABENTO_SYMBOLS),
                "stype_in": self.databento_config.get("stype_in", DEFAULT_STYPE_IN),
                "stype_out": self.databento_config.get("stype_out", DEFAULT_STYPE_OUT),
                "api_key": databento_api_key_status(self.databento_config, required=False),
                "delta_method": self.delta_method,
                "contract_symbol_regex": self.contract_symbol_regex,
                "active_contract_mode": validate_active_contract_mode(
                    self.databento_config.get("active_contract_mode", "highest_session_volume")
                ),
                "historical_enabled": bool(historical.get("enabled", True)),
                "historical_cache_path": historical.get("cache_path"),
                "historical_allow_contract_symbol_regex_relaxation": bool(
                    historical.get("allow_contract_symbol_regex_relaxation", False)
                ),
                "live_enabled": bool(live.get("enabled", False)),
                "live_metadata_preflight": bool(live.get("metadata_preflight", True)),
                "live_allow_without_metadata_preflight": bool(
                    live.get("allow_live_without_metadata_preflight", False)
                ),
                "live_metadata_preflight_guard": live_metadata_preflight_guard_report(live),
                "live_cost_guard": live_cost_guard_report(live),
                "live_safety_stops": live_safety_stop_config(live),
                "live_stop_on_unmatched_contract_symbol": bool(
                    live.get("stop_on_unmatched_contract_symbol", False)
                ),
            },
            "alerts_path": str(self.alerts_path) if self.alerts_path else None,
            "process_lock": {
                "enabled": bool(self.process_lock_config.get("enabled", False)),
                "path": str(self.process_lock_path) if self.process_lock_path else None,
                "stale_after_seconds": self.process_lock_config.get("stale_after_seconds"),
                "fail_if_locked": bool(self.process_lock_config.get("fail_if_locked", True)),
                "acquired": bool(self.process_lock_acquired),
            },
            "alert_file": {
                "enabled": self.alerts_path is not None,
                "path": str(self.alerts_path) if self.alerts_path else None,
                "fsync": bool(self.alert_file_config.get("fsync", False)),
                "fail_on_write_error": bool(self.alert_file_config.get("fail_on_write_error", False)),
                "suppress_duplicate_alert_ids": bool(
                    self.alert_file_config.get("suppress_duplicate_alert_ids", False)
                ),
                "loaded_existing_alert_ids": len(self.alert_seen_ids),
                "duplicate_index_last_error_utc": self.alert_sink.last_error_utc,
                "duplicate_index_last_error_type": self.alert_sink.last_error_type,
                "duplicate_index_last_error": self.alert_sink.last_error,
            },
            "output_path_readiness": self.output_path_readiness_config,
            "dry_run_alerts": self.dry_run_alerts,
            "setup_alerts": {
                "enabled": bool(self.setup_alerts_config.get("enabled", False)),
                "path": str(self.setup_alerts_path) if self.setup_alerts_path else None,
                "fsync": bool(self.setup_alerts_config.get("fsync", False)),
                "fail_on_write_error": bool(self.setup_alerts_config.get("fail_on_write_error", False)),
                "suppress_duplicate_setup_ids": bool(
                    self.setup_alerts_config.get("suppress_duplicate_setup_ids", True)
                ),
                "loaded_existing_setup_ids": len(self.setup_seen_ids),
                "duplicate_index_last_error_utc": self.setup_notice_sink.last_error_utc,
                "duplicate_index_last_error_type": self.setup_notice_sink.last_error_type,
                "duplicate_index_last_error": self.setup_notice_sink.last_error,
            },
            "execution_intents": {
                "enabled": bool(self.execution_intents_config.get("enabled", False)),
                "path": str(self.execution_intents_path) if self.execution_intents_path else None,
                "fsync": bool(self.execution_intents_config.get("fsync", False)),
                "fail_on_write_error": bool(self.execution_intents_config.get("fail_on_write_error", False)),
                "suppress_duplicate_alert_ids": bool(
                    self.execution_intents_config.get("suppress_duplicate_alert_ids", True)
                ),
                "suppress_duplicate_setup_ids": bool(
                    self.execution_intents_config.get("suppress_duplicate_setup_ids", True)
                ),
                "intent_ttl_seconds": float(self.execution_intents_config.get("intent_ttl_seconds", 30.0)),
                "enforce_freshness": bool(self.execution_intents_config.get("enforce_freshness", True)),
                "freshness_grace_seconds": float(
                    self.execution_intents_config.get("freshness_grace_seconds", 0.0)
                ),
                "fail_on_freshness_error": bool(
                    self.execution_intents_config.get("fail_on_freshness_error", False)
                ),
                "loaded_existing_alert_ids": len(self.execution_intent_seen_ids),
                "loaded_existing_duplicate_ids": len(self.execution_intent_seen_ids),
                "duplicate_index_last_error_utc": self.execution_intent_sink.last_error_utc,
                "duplicate_index_last_error_type": self.execution_intent_sink.last_error_type,
                "duplicate_index_last_error": self.execution_intent_sink.last_error,
            },
            "data_quality": {
                "enabled": bool(self.data_quality_config["enabled"]),
                "fail_on_error": bool(self.data_quality_config["fail_on_error"]),
                "allow_zero_volume": bool(self.data_quality_config["allow_zero_volume"]),
                "warn_on_time_gaps": bool(self.data_quality_config["warn_on_time_gaps"]),
                "max_bar_gap_minutes": self.data_quality_config["max_bar_gap_minutes"],
                "alert_repeat_seconds": self.data_quality_config["alert_repeat_seconds"],
                "delta_unclassified": self.data_quality_config["delta_unclassified"],
                "source_bar_quality_drops": self.source_bar_quality_drops,
                "source_bar_quality_error_count": self.source_bar_quality_error_count,
                "source_bar_quality_warning_count": self.source_bar_quality_warning_count,
                "last_source_bar_quality_report": self.last_source_bar_quality_report,
            },
        "source_contract_filter": {
            "enabled": self.contract_symbol_regex is not None,
            "contract_symbol_regex": self.contract_symbol_regex,
            "source_contract_filter_drops": self.source_contract_filter_drops,
            "last_source_contract_filter_report": self.last_source_contract_filter_report,
        },
        "source_bar_quality": self.source_bar_quality_report(),
            "feature_quality": {
                "enabled": bool(self.feature_quality_config["enabled"]),
                "fail_on_missing_columns": bool(self.feature_quality_config["fail_on_missing_columns"]),
                "alert_repeat_seconds": self.feature_quality_config["alert_repeat_seconds"],
                "max_reported_columns": self.feature_quality_config["max_reported_columns"],
            },
            "operator_sound": self.operator_sound_health_report(),
            "entry_timing": {
                "entry_contract_match_required": bool(
                    self.engine_config.get("entry_contract_match_required", True)
                ),
                "entry_contract_mismatch_alert_repeat_seconds": float(
                    self.engine_config.get("entry_contract_mismatch_alert_repeat_seconds", 120.0)
                ),
                "contract_symbol_regex": self.contract_symbol_regex,
                "entry_contract_regex_skips": self.entry_contract_regex_skips,
                "max_entry_lag_seconds": float(self.engine_config.get("max_entry_lag_seconds", 120.0)),
            },
            "strategy_errors": {
                "fail_fast": bool(self.strategy_error_config["fail_fast"]),
                "disable_strategy_on_error": bool(self.strategy_error_config["disable_strategy_on_error"]),
                "max_errors_per_strategy": self.strategy_error_config["max_errors_per_strategy"],
                "fail_when_all_strategies_disabled": bool(
                    self.strategy_error_config["fail_when_all_strategies_disabled"]
                ),
            },
            "trade_sanity": self.trade_sanity_config,
            "data_plan": self.data_plan,
            "strategies": [strategy.preflight_report() for strategy in self.strategies],
        }

    def seed(self, bars: list[SourceMinuteBar], *, source: str) -> None:
        with self.lock:
            accepted_bars = self.filter_source_bars_for_quality(bars, source=source, mode="seed")
            changed = self.store.add_many(accepted_bars)
            self.audit_seed_warmup(accepted_bars, source=source)
            count_historical = bool(self.engine_config.get("count_historical_signals", True))
            hydrated_signals = 0
            for strategy in self.strategies:
                if strategy.disabled:
                    continue
                try:
                    hydrated_signals += strategy.hydrate(self.store, count_historical_signals=count_historical)
                except Exception as exc:
                    self.handle_strategy_runtime_error(
                        strategy,
                        exc,
                        phase="hydrate",
                        extra={"source": source, "bars": len(accepted_bars)},
                    )
            print_json(
                {
                    "event": "seed_complete",
                    "source": source,
                    "bars": len(bars),
                    "accepted_bars": len(accepted_bars),
                    "dropped_bars": len(bars) - len(accepted_bars),
                    "new_or_updated_bars": changed,
                    "hydrated_historical_signals": hydrated_signals if count_historical else 0,
                }
            )

    def on_completed_source_bar(self, bar: SourceMinuteBar) -> None:
        with self.lock:
            accepted_bars = self.filter_source_bars_for_quality([bar], source=bar.source or "live", mode="live")
            if not accepted_bars:
                return
            bar = accepted_bars[0]
            changed = self.store.add(bar)
            if not changed:
                return
            queued = 0
            pending_setups: list[PendingSignal] = []
            for strategy in self.strategies:
                if strategy.disabled:
                    continue
                try:
                    pending_items = strategy.process_new_completed_bars(self.store, live=True)
                except Exception as exc:
                    self.handle_strategy_runtime_error(
                        strategy,
                        exc,
                        phase="process_completed_bar",
                        extra={
                            "source_bar_timestamp": format_timestamp(bar.timestamp_utc),
                            "contract_symbol": bar.contract_symbol,
                        },
                    )
                    continue
                for pending in pending_items:
                    if pending.key not in strategy.sent_signal_keys:
                        self.pending.append(pending)
                        pending_setups.append(pending)
                        queued += 1
            if queued:
                print_json(
                    {
                        "event": "signals_queued",
                        "source_bar_timestamp": format_timestamp(bar.timestamp_utc),
                        "queued": queued,
                    }
                )
            for pending in pending_setups:
                try:
                    notice = self.build_validated_setup_notice(pending)
                except Exception as exc:
                    self.pending = [item for item in self.pending if item is not pending]
                    self.handle_strategy_runtime_error(
                        pending.strategy,
                        exc,
                        phase="build_setup_notice",
                        extra={
                            "source_bar_timestamp": format_timestamp(bar.timestamp_utc),
                            "contract_symbol": bar.contract_symbol,
                            "pending_signal_key": pending.key,
                        },
                    )
                    continue
                self.emit_setup_notice_record(notice)

    def on_entry_tick(self, tick: TradeTick) -> None:
        with self.lock:
            if not self.pending:
                return
            max_lag = float(self.engine_config.get("max_entry_lag_seconds", 120))
            contract_match_required = bool(self.engine_config.get("entry_contract_match_required", True))
            still_pending: list[PendingSignal] = []
            expired_count = 0
            for pending in self.pending:
                if pending.key in pending.strategy.sent_signal_keys:
                    continue
                lag = (tick.timestamp_utc - pending.due_utc).total_seconds()
                if lag < -0.001:
                    still_pending.append(pending)
                    continue
                expected_contract = pending_contract_symbol(pending)
                actual_contract = str(tick.contract_symbol or "").strip()
                if expected_contract and not self.entry_contract_symbol_matches(expected_contract):
                    self.record_entry_contract_regex_skip(
                        pending=pending,
                        tick=tick,
                        contract_symbol=expected_contract,
                        reason="pending_setup_contract_symbol_unmatched",
                        lag_seconds=lag,
                    )
                    pending.strategy.emit_reject(
                        pending,
                        "pending setup contract_symbol does not match databento.contract_symbol_regex",
                        extra={
                            "pending_contract_symbol": expected_contract,
                            "entry_tick_contract_symbol": actual_contract,
                            "contract_symbol_regex": self.contract_symbol_regex,
                            "entry_timestamp_utc": format_timestamp(tick.timestamp_utc),
                            "lag_seconds": round(lag, 3),
                        },
                    )
                    continue
                if not self.entry_contract_symbol_matches(actual_contract):
                    self.record_entry_contract_regex_skip(
                        pending=pending,
                        tick=tick,
                        contract_symbol=actual_contract,
                        reason="entry_tick_contract_symbol_unmatched",
                        lag_seconds=lag,
                    )
                    if lag > max_lag:
                        pending.strategy.emit_reject(
                            pending,
                            "no entry tick matching databento.contract_symbol_regex arrived within max_entry_lag_seconds",
                            extra={
                                "last_entry_tick_contract_symbol": actual_contract,
                                "contract_symbol_regex": self.contract_symbol_regex,
                                "entry_timestamp_utc": format_timestamp(tick.timestamp_utc),
                                "lag_seconds": round(lag, 3),
                                "max_entry_lag_seconds": max_lag,
                            },
                        )
                        expired_count += 1
                        continue
                    still_pending.append(pending)
                    continue
                if contract_match_required:
                    if not expected_contract:
                        pending.strategy.emit_reject(
                            pending,
                            "pending signal has no contract_symbol for contract-matched entry",
                            extra={
                                "entry_timestamp_utc": format_timestamp(tick.timestamp_utc),
                                "entry_contract_symbol": actual_contract,
                            },
                        )
                        continue
                    if actual_contract != expected_contract:
                        self.record_entry_contract_mismatch(pending, tick, lag_seconds=lag)
                        if lag > max_lag:
                            pending.strategy.emit_reject(
                                pending,
                                f"no matching {expected_contract} entry tick arrived within max_entry_lag_seconds",
                                extra={
                                    "expected_contract_symbol": expected_contract,
                                    "last_entry_tick_contract_symbol": actual_contract,
                                    "entry_timestamp_utc": format_timestamp(tick.timestamp_utc),
                                    "lag_seconds": round(lag, 3),
                                    "max_entry_lag_seconds": max_lag,
                                },
                            )
                            expired_count += 1
                            continue
                        still_pending.append(pending)
                        continue
                if lag > max_lag:
                    pending.strategy.emit_reject(
                        pending,
                        f"matching entry tick arrived {lag:.1f}s after due time, beyond max_entry_lag_seconds",
                    )
                    expired_count += 1
                    continue
                try:
                    alert = pending.strategy.build_alert(pending, tick, self.account)
                except Exception as exc:
                    self.handle_strategy_runtime_error(
                        pending.strategy,
                        exc,
                        phase="build_entry_alert",
                        extra={
                            "entry_timestamp_utc": format_timestamp(tick.timestamp_utc),
                            "contract_symbol": tick.contract_symbol,
                            "pending_signal_key": pending.key,
                        },
                    )
                    continue
                if alert is None:
                    continue
                self.emit_alert(alert)
            self.pending = still_pending
            self.emit_pending_expiry_system_alert(source="entry_tick", expired=expired_count)

    def record_entry_contract_mismatch(
        self,
        pending: PendingSignal,
        tick: TradeTick,
        *,
        lag_seconds: float,
    ) -> None:
        expected_contract = pending_contract_symbol(pending)
        actual_contract = str(tick.contract_symbol or "").strip()
        self.entry_contract_mismatch_skips += 1
        self.last_entry_contract_mismatch = {
            "strategy_id": pending.strategy.strategy_id,
            "pending_signal_key": pending.key,
            "expected_contract_symbol": expected_contract,
            "entry_tick_contract_symbol": actual_contract,
            "entry_tick_timestamp_utc": format_timestamp(tick.timestamp_utc),
            "due_timestamp_utc": format_timestamp(pd.Timestamp(pending.due_utc).tz_convert("UTC")),
            "lag_seconds": round(lag_seconds, 3),
        }
        repeat_seconds = float(self.engine_config.get("entry_contract_mismatch_alert_repeat_seconds", 120.0))
        now = time.monotonic()
        if (
            self._last_entry_contract_mismatch_alert_monotonic is not None
            and repeat_seconds > 0
            and now - self._last_entry_contract_mismatch_alert_monotonic < repeat_seconds
        ):
            return
        self._last_entry_contract_mismatch_alert_monotonic = now
        print_json(
            {
                "event": "entry_tick_contract_mismatch_skipped",
                "entry_contract_mismatch_skips": self.entry_contract_mismatch_skips,
                "last_entry_contract_mismatch": self.last_entry_contract_mismatch,
                "reason": "A pending setup was waiting for a different contract symbol than the current entry tick.",
                "impact": "The entry tick was not used for this pending setup; the setup remains pending until a matching tick arrives or expires.",
            },
            prefix="SYSTEM_ALERT",
        )
        self.play_operator_sound("system")

    def entry_contract_symbol_matches(self, contract_symbol: str) -> bool:
        return contract_symbol_matches_regex(contract_symbol, self._contract_symbol_pattern)

    def record_entry_contract_regex_skip(
        self,
        *,
        pending: PendingSignal,
        tick: TradeTick,
        contract_symbol: str,
        reason: str,
        lag_seconds: float,
    ) -> None:
        self.entry_contract_regex_skips += 1
        self.last_entry_contract_regex_skip = {
            "strategy_id": pending.strategy.strategy_id,
            "pending_signal_key": pending.key,
            "pending_contract_symbol": pending_contract_symbol(pending),
            "entry_tick_contract_symbol": str(tick.contract_symbol or "").strip(),
            "rejected_contract_symbol": str(contract_symbol or "").strip(),
            "contract_symbol_regex": self.contract_symbol_regex,
            "entry_tick_timestamp_utc": format_timestamp(tick.timestamp_utc),
            "due_timestamp_utc": format_timestamp(pd.Timestamp(pending.due_utc).tz_convert("UTC")),
            "lag_seconds": round(lag_seconds, 3),
            "reason": reason,
        }
        repeat_seconds = float(self.engine_config.get("entry_contract_mismatch_alert_repeat_seconds", 120.0))
        now = time.monotonic()
        if (
            self._last_entry_contract_regex_alert_monotonic is not None
            and repeat_seconds > 0
            and now - self._last_entry_contract_regex_alert_monotonic < repeat_seconds
        ):
            return
        self._last_entry_contract_regex_alert_monotonic = now
        print_json(
            {
                "event": "entry_contract_symbol_regex_filtered",
                "entry_contract_regex_skips": self.entry_contract_regex_skips,
                "last_entry_contract_regex_skip": self.last_entry_contract_regex_skip,
                "reason": "A pending setup or entry tick had a contract symbol rejected by databento.contract_symbol_regex.",
                "impact": "The rejected symbol was not allowed to produce an entry alert or router-facing execution intent.",
            },
            prefix="SYSTEM_ALERT",
        )
        self.play_operator_sound("system")

    def expire_stale_pending_signals(self, *, now_utc: Any, source: str) -> int:
        with self.lock:
            if not self.pending:
                return 0
            timestamp = pd.Timestamp(now_utc)
            timestamp = timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")
            max_lag = float(self.engine_config.get("max_entry_lag_seconds", 120))
            still_pending: list[PendingSignal] = []
            expired = 0
            for pending in self.pending:
                if pending.key in pending.strategy.sent_signal_keys:
                    continue
                lag = (timestamp - pending.due_utc).total_seconds()
                if lag <= max_lag:
                    still_pending.append(pending)
                    continue
                pending.strategy.emit_reject(
                    pending,
                    f"pending entry expired {lag:.1f}s after due time without an entry tick",
                    extra={
                        "event_source": source,
                        "due_timestamp_utc": format_timestamp(pd.Timestamp(pending.due_utc).tz_convert("UTC")),
                        "checked_timestamp_utc": format_timestamp(timestamp),
                        "max_entry_lag_seconds": max_lag,
                    },
                )
                expired += 1
            self.pending = still_pending
            self.emit_pending_expiry_system_alert(source=source, expired=expired)
            return expired

    def emit_pending_expiry_system_alert(self, *, source: str, expired: int) -> None:
        if expired <= 0:
            return
        self.pending_expired_count += int(expired)
        print_json(
            {
                "event": "pending_signals_expired",
                "source": source,
                "expired": int(expired),
                "total_expired": self.pending_expired_count,
                "remaining_pending": len(self.pending),
            },
            prefix="SYSTEM_ALERT",
        )
        self.play_operator_sound("system")

    def pending_status(self, *, now_utc: Any) -> dict[str, Any]:
        with self.lock:
            timestamp = pd.Timestamp(now_utc)
            timestamp = timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")
            max_lag = float(self.engine_config.get("max_entry_lag_seconds", 120))
            if not self.pending:
                return {
                    "count": 0,
                    "oldest_due_timestamp_utc": None,
                    "oldest_seconds_until_due": None,
                    "overdue_count": 0,
                    "soonest_expires_at_utc": None,
                    "soonest_seconds_until_expiry": None,
                    "expired_count": 0,
                    "max_entry_lag_seconds": max_lag,
                    "total_expired_count": self.pending_expired_count,
                    "entry_contract_match_required": bool(
                        self.engine_config.get("entry_contract_match_required", True)
                    ),
                    "entry_contract_mismatch_skips": self.entry_contract_mismatch_skips,
                    "last_entry_contract_mismatch": self.last_entry_contract_mismatch,
                    "entry_contract_regex_skips": self.entry_contract_regex_skips,
                    "last_entry_contract_regex_skip": self.last_entry_contract_regex_skip,
                }
            due_times = [pd.Timestamp(pending.due_utc).tz_convert("UTC") for pending in self.pending]
            expiry_times = [due_time + pd.Timedelta(seconds=max_lag) for due_time in due_times]
            oldest_due = min(due_times)
            soonest_expiry = min(expiry_times)
            return {
                "count": len(self.pending),
                "oldest_due_timestamp_utc": format_timestamp(oldest_due),
                "oldest_seconds_until_due": round((oldest_due - timestamp).total_seconds(), 3),
                "overdue_count": sum(1 for due_time in due_times if timestamp > due_time),
                "soonest_expires_at_utc": format_timestamp(soonest_expiry),
                "soonest_seconds_until_expiry": round((soonest_expiry - timestamp).total_seconds(), 3),
                "expired_count": sum(1 for expiry_time in expiry_times if timestamp > expiry_time),
                "max_entry_lag_seconds": max_lag,
                "total_expired_count": self.pending_expired_count,
                "entry_contract_match_required": bool(
                    self.engine_config.get("entry_contract_match_required", True)
                ),
                "entry_contract_mismatch_skips": self.entry_contract_mismatch_skips,
                "last_entry_contract_mismatch": self.last_entry_contract_mismatch,
                "entry_contract_regex_skips": self.entry_contract_regex_skips,
                "last_entry_contract_regex_skip": self.last_entry_contract_regex_skip,
            }

    def emit_alert(self, alert: dict[str, Any]) -> None:
        validate_entry_alert_contract(alert)
        self.alert_count += 1
        print_json(alert, prefix=self.alert_prefix)
        if self.operator_enabled("print_human_readable", default=True):
            print(format_entry_alert_readout(alert), flush=True)
        if self.dry_run_alerts:
            self.emit_dry_run_outputs_skipped(
                record_type="entry_signal",
                sound_kind="entry",
                alert_id=alert.get("alert_id"),
                setup_id=alert.get("setup_id"),
            )
        self.persist_alert(alert)
        self.persist_execution_intent(alert)
        self.play_operator_sound("entry")

    def persist_setup_notice(self, notice: dict[str, Any]) -> None:
        if self.dry_run_alerts:
            return
        if not bool(self.setup_alerts_config.get("enabled", False)):
            return
        if self.setup_alerts_path is None:
            payload = {
                "event": "setup_alert_write_failed",
                "setup_id": notice.get("setup_id"),
                "path": None,
                "error_type": "ConfigError",
                "error": "engine.setup_alerts.enabled is true but no path is configured.",
                "writes_succeeded": self.setup_notice_sink.writes_succeeded,
                "writes_failed": self.setup_notice_sink.writes_failed + 1,
                "impact": "The setup notice was printed, but no durable setup-alert JSONL record was written.",
            }
            self.setup_notice_sink.writes_failed += 1
            self.setup_notice_sink.last_error_utc = utc_now_iso()
            self.setup_notice_sink.last_error_type = payload["error_type"]
            self.setup_notice_sink.last_error = payload["error"]
            print_json(payload, prefix="SYSTEM_ALERT")
            self.play_operator_sound("system")
            if bool(self.setup_alerts_config.get("fail_on_write_error", False)):
                raise RuntimeError(payload["error"])
            return
        setup_id = str(notice.get("setup_id") or "")
        if self.should_skip_duplicate_jsonl_record(
            setup_id,
            sink=self.setup_notice_sink,
            seen_ids=self.setup_seen_ids,
            sink_label="setup_alerts",
            path=self.setup_alerts_path,
            enabled=bool(self.setup_alerts_config.get("suppress_duplicate_setup_ids", True)),
            impact="The duplicate setup notice was printed to stdout, but was not appended again to the setup-alerts JSONL file.",
            id_field="setup_id",
            duplicate_event_suffix="duplicate_setup_id_skipped",
        ):
            return
        try:
            self.setup_alerts_path.parent.mkdir(parents=True, exist_ok=True)
            with self.setup_alerts_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(notice, sort_keys=True, default=json_default) + "\n")
                if bool(self.setup_alerts_config.get("fsync", False)):
                    handle.flush()
                    os.fsync(handle.fileno())
            self.setup_notice_sink.writes_succeeded += 1
            self.setup_notice_sink.last_success_utc = utc_now_iso()
            if setup_id:
                self.setup_seen_ids.add(setup_id)
        except Exception as exc:
            self.setup_notice_sink.writes_failed += 1
            self.setup_notice_sink.last_error_utc = utc_now_iso()
            self.setup_notice_sink.last_error_type = type(exc).__name__
            self.setup_notice_sink.last_error = str(exc)
            payload = {
                "event": "setup_alert_write_failed",
                "setup_id": notice.get("setup_id"),
                "path": str(self.setup_alerts_path),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "writes_succeeded": self.setup_notice_sink.writes_succeeded,
                "writes_failed": self.setup_notice_sink.writes_failed,
                "impact": "The setup notice was printed, but was not appended to the setup-alerts JSONL file.",
            }
            print_json(payload, prefix="SYSTEM_ALERT")
            self.play_operator_sound("system")
            if bool(self.setup_alerts_config.get("fail_on_write_error", False)):
                raise RuntimeError(f"Setup alert write failed for {self.setup_alerts_path}: {exc}") from exc

    def persist_alert(self, alert: dict[str, Any]) -> None:
        if self.dry_run_alerts:
            return
        if self.alerts_path:
            alert_id = str(alert.get("alert_id") or "")
            if self.should_skip_duplicate_jsonl_record(
                alert_id,
                sink=self.alert_sink,
                seen_ids=self.alert_seen_ids,
                sink_label="alert_file",
                path=self.alerts_path,
                enabled=bool(self.alert_file_config.get("suppress_duplicate_alert_ids", False)),
                impact="The duplicate entry signal was printed to stdout, but was not appended again to the alerts JSONL file.",
            ):
                return
            try:
                self.alerts_path.parent.mkdir(parents=True, exist_ok=True)
                with self.alerts_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(alert, sort_keys=True, default=json_default) + "\n")
                    if bool(self.alert_file_config.get("fsync", False)):
                        handle.flush()
                        os.fsync(handle.fileno())
                self.alert_sink.writes_succeeded += 1
                self.alert_sink.last_success_utc = utc_now_iso()
                if alert_id:
                    self.alert_seen_ids.add(alert_id)
            except Exception as exc:
                self.alert_sink.writes_failed += 1
                self.alert_sink.last_error_utc = utc_now_iso()
                self.alert_sink.last_error_type = type(exc).__name__
                self.alert_sink.last_error = str(exc)
                payload = {
                    "event": "alert_file_write_failed",
                    "alert_id": alert.get("alert_id"),
                    "path": str(self.alerts_path),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "writes_succeeded": self.alert_sink.writes_succeeded,
                    "writes_failed": self.alert_sink.writes_failed,
                    "impact": "The entry signal was printed to stdout, but was not appended to the JSONL alerts file.",
                }
                print_json(payload, prefix="SYSTEM_ALERT")
                self.play_operator_sound("system")
                if bool(self.alert_file_config.get("fail_on_write_error", False)):
                    raise RuntimeError(f"Alert file write failed for {self.alerts_path}: {exc}") from exc

    def persist_execution_intent(self, alert: dict[str, Any]) -> None:
        if self.dry_run_alerts:
            return
        if not bool(self.execution_intents_config.get("enabled", False)):
            return
        if self.execution_intents_path is None:
            payload = {
                "event": "execution_intent_write_failed",
                "alert_id": alert.get("alert_id"),
                "path": None,
                "error_type": "ConfigError",
                "error": "engine.execution_intents.enabled is true but no path is configured.",
                "writes_succeeded": self.execution_intent_sink.writes_succeeded,
                "writes_failed": self.execution_intent_sink.writes_failed + 1,
                "impact": "The entry signal was printed, but no router-facing execution-intent JSONL record was written.",
            }
            self.execution_intent_sink.writes_failed += 1
            self.execution_intent_sink.last_error_utc = utc_now_iso()
            self.execution_intent_sink.last_error_type = payload["error_type"]
            self.execution_intent_sink.last_error = payload["error"]
            print_json(payload, prefix="SYSTEM_ALERT")
            self.play_operator_sound("system")
            if bool(self.execution_intents_config.get("fail_on_write_error", False)):
                raise RuntimeError(payload["error"])
            return
        record = build_execution_intent_record(alert)
        validate_execution_intent_record(record, alert)
        alert_id = str(alert.get("alert_id") or "")
        setup_id = str(alert.get("setup_id") or "")
        if self.should_skip_non_actionable_execution_intent(record, alert_id=alert_id):
            return
        if self.should_skip_duplicate_jsonl_record(
            alert_id,
            sink=self.execution_intent_sink,
            seen_ids=self.execution_intent_seen_ids,
            sink_label="execution_intents",
            path=self.execution_intents_path,
            enabled=bool(self.execution_intents_config.get("suppress_duplicate_alert_ids", True)),
            impact="The duplicate entry signal was printed, but the router-facing execution intent was not appended again.",
        ):
            return
        if self.should_skip_duplicate_jsonl_record(
            setup_id,
            sink=self.execution_intent_sink,
            seen_ids=self.execution_intent_seen_ids,
            sink_label="execution_intents",
            path=self.execution_intents_path,
            enabled=bool(self.execution_intents_config.get("suppress_duplicate_setup_ids", True)),
            impact=(
                "The entry signal was printed, but a router-facing execution intent for the same setup_id "
                "already exists and was not appended again."
            ),
            id_field="setup_id",
            duplicate_event_suffix="duplicate_setup_id_skipped",
        ):
            return
        try:
            self.execution_intents_path.parent.mkdir(parents=True, exist_ok=True)
            with self.execution_intents_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, sort_keys=True, default=json_default) + "\n")
                if bool(self.execution_intents_config.get("fsync", False)):
                    handle.flush()
                    os.fsync(handle.fileno())
            self.execution_intent_sink.writes_succeeded += 1
            self.execution_intent_sink.last_success_utc = utc_now_iso()
            if alert_id:
                self.execution_intent_seen_ids.add(alert_id)
            if setup_id:
                self.execution_intent_seen_ids.add(setup_id)
        except Exception as exc:
            self.execution_intent_sink.writes_failed += 1
            self.execution_intent_sink.last_error_utc = utc_now_iso()
            self.execution_intent_sink.last_error_type = type(exc).__name__
            self.execution_intent_sink.last_error = str(exc)
            payload = {
                "event": "execution_intent_write_failed",
                "alert_id": alert.get("alert_id"),
                "path": str(self.execution_intents_path),
                "error_type": type(exc).__name__,
                "error": str(exc),
                "writes_succeeded": self.execution_intent_sink.writes_succeeded,
                "writes_failed": self.execution_intent_sink.writes_failed,
                "impact": "The entry signal was printed, but no router-facing execution-intent JSONL record was written.",
            }
            print_json(payload, prefix="SYSTEM_ALERT")
            self.play_operator_sound("system")
            if bool(self.execution_intents_config.get("fail_on_write_error", False)):
                raise RuntimeError(f"Execution intent write failed for {self.execution_intents_path}: {exc}") from exc

    def should_skip_non_actionable_execution_intent(self, record: dict[str, Any], *, alert_id: str) -> bool:
        if not bool(self.execution_intents_config.get("enforce_freshness", True)):
            return False
        freshness = execution_intent_freshness_report(
            record.get("execution_intent"),
            now_utc=pd.Timestamp.utcnow(),
            grace_seconds=float(self.execution_intents_config.get("freshness_grace_seconds", 0.0)),
        )
        if bool(freshness.get("actionable", False)):
            return False
        self.execution_intent_sink.freshness_skipped += 1
        self.execution_intent_sink.last_freshness_skip_utc = utc_now_iso()
        self.execution_intent_sink.last_freshness_skip_alert_id = alert_id or None
        self.execution_intent_sink.last_freshness_skip_reason = str(freshness.get("state") or "non_actionable")
        payload = {
            "event": "execution_intents_non_actionable_intent_skipped",
            "alert_id": alert_id or None,
            "path": str(self.execution_intents_path) if self.execution_intents_path else None,
            "freshness": freshness,
            "freshness_skipped": self.execution_intent_sink.freshness_skipped,
            "reason": "The execution intent is not actionable at local UTC wall-clock time.",
            "impact": "The manual ENTRY_SIGNAL was printed, but no router-facing execution-intent JSONL record was written.",
        }
        print_json(payload, prefix="SYSTEM_ALERT")
        self.play_operator_sound("system")
        if bool(self.execution_intents_config.get("fail_on_freshness_error", False)):
            raise RuntimeError(
                "Execution intent freshness check failed: "
                f"{freshness.get('state')} for alert_id={alert_id or '<missing>'}"
            )
        return True

    def should_skip_duplicate_jsonl_record(
        self,
        record_id: str,
        *,
        sink: AlertSinkHealth,
        seen_ids: set[str],
        sink_label: str,
        path: Path,
        enabled: bool,
        impact: str,
        id_field: str = "alert_id",
        duplicate_event_suffix: str = "duplicate_alert_id_skipped",
    ) -> bool:
        if not enabled or not record_id or record_id not in seen_ids:
            return False
        sink.duplicates_skipped += 1
        sink.last_duplicate_utc = utc_now_iso()
        sink.last_duplicate_alert_id = record_id
        sink.last_duplicate_id_field = id_field
        print_json(
            {
                "event": f"{sink_label}_{duplicate_event_suffix}",
                id_field: record_id,
                "record_id": record_id,
                "path": str(path),
                "duplicates_skipped": sink.duplicates_skipped,
                "impact": impact,
            },
            prefix="SYSTEM_ALERT",
        )
        self.play_operator_sound("system")
        return True

    def filter_source_bars_for_quality(
        self,
        bars: list[SourceMinuteBar],
        *,
        source: str,
        mode: str,
    ) -> list[SourceMinuteBar]:
        bars = self.filter_source_bars_for_contract_symbol(bars, source=source, mode=mode)
        if not bars or not bool(self.data_quality_config.get("enabled", True)):
            return bars
        issues = validate_source_bars_quality(
            bars,
            timezone=self.timezone,
            config=self.data_quality_config,
            delta_method=self.delta_method,
        )
        error_indices = {
            issue.bar_index
            for issue in issues
            if issue.severity == "error" and issue.bar_index is not None
        }
        if issues:
            self.emit_source_bar_quality_alert(
                issues,
                source=source,
                mode=mode,
                bars_received=len(bars),
                bars_accepted=len(bars) - len(error_indices),
            )
        errors = [issue for issue in issues if issue.severity == "error"]
        if errors and bool(self.data_quality_config.get("fail_on_error", False)):
            raise RuntimeError(
                f"Source bar quality check failed with {len(errors)} error(s); "
                "refusing to continue with invalid market data."
            )
        if not error_indices:
            return bars
        return [bar for index, bar in enumerate(bars) if index not in error_indices]

    def filter_source_bars_for_contract_symbol(
        self,
        bars: list[SourceMinuteBar],
        *,
        source: str,
        mode: str,
    ) -> list[SourceMinuteBar]:
        if not bars or self._contract_symbol_pattern is None:
            return bars
        accepted: list[SourceMinuteBar] = []
        dropped: list[SourceMinuteBar] = []
        for bar in bars:
            contract_symbol = str(bar.contract_symbol or "").strip()
            if self._contract_symbol_pattern.match(contract_symbol):
                accepted.append(bar)
            else:
                dropped.append(bar)
        if dropped:
            self.emit_source_contract_filter_alert(
                dropped,
                source=source,
                mode=mode,
                bars_received=len(bars),
                bars_accepted=len(accepted),
            )
        return accepted

    def emit_source_contract_filter_alert(
        self,
        dropped: list[SourceMinuteBar],
        *,
        source: str,
        mode: str,
        bars_received: int,
        bars_accepted: int,
    ) -> None:
        dropped_keys = {
            (format_timestamp(pd.Timestamp(bar.timestamp_utc).tz_convert("UTC")), str(bar.contract_symbol or ""))
            for bar in dropped
        }
        new_keys = {key for key in dropped_keys if key not in self._reported_source_contract_filter_keys}
        if not new_keys:
            return
        self._reported_source_contract_filter_keys.update(new_keys)
        self.source_contract_filter_drops += len(new_keys)
        counts: dict[str, int] = {}
        for _, contract_symbol in dropped_keys:
            counts[contract_symbol] = counts.get(contract_symbol, 0) + 1
        report = {
            "source": source,
            "mode": mode,
            "contract_symbol_regex": self.contract_symbol_regex,
            "bars_received": bars_received,
            "bars_accepted": bars_accepted,
            "bars_dropped": len(dropped_keys),
            "new_bars_dropped": len(new_keys),
            "dropped_contracts": top_count_items(counts),
            "sample_dropped_bars": [
                {
                    "timestamp_utc": format_timestamp(pd.Timestamp(bar.timestamp_utc).tz_convert("UTC")),
                    "contract_symbol": str(bar.contract_symbol or ""),
                    "volume": float(bar.volume),
                    "source": bar.source,
                }
                for bar in dropped[:10]
            ],
        }
        self.last_source_contract_filter_report = report
        repeat_seconds = float(self.data_quality_config.get("alert_repeat_seconds", 120.0) or 120.0)
        now = time.monotonic()
        if (
            self._last_source_contract_filter_alert_monotonic is not None
            and repeat_seconds > 0
            and now - self._last_source_contract_filter_alert_monotonic < repeat_seconds
        ):
            return
        self._last_source_contract_filter_alert_monotonic = now
        print_json(
            {
                "event": "source_bar_contract_symbol_filtered",
                "source_contract_filter_drops": self.source_contract_filter_drops,
                "report": report,
                "reason": "One or more cached/replay/historical source bars did not match databento.contract_symbol_regex.",
                "impact": "Filtered bars were not added to the source store and cannot produce setups or entry signals.",
            },
            prefix="SYSTEM_ALERT",
        )
        self.play_operator_sound("system")

    def emit_source_bar_quality_alert(
        self,
        issues: list[SourceBarQualityIssue],
        *,
        source: str,
        mode: str,
        bars_received: int,
        bars_accepted: int,
    ) -> None:
        max_reported = int(self.data_quality_config.get("max_reported_issues", 10) or 10)
        errors = [issue for issue in issues if issue.severity == "error"]
        warnings = [issue for issue in issues if issue.severity == "warning"]
        payload = {
            "event": "source_bar_quality_issues",
            "source": source,
            "mode": mode,
            "bars_received": bars_received,
            "bars_accepted": bars_accepted,
            "bars_dropped": max(0, bars_received - bars_accepted),
            "error_count": len(errors),
            "warning_count": len(warnings),
            "fail_on_error": bool(self.data_quality_config.get("fail_on_error", False)),
            "issues": [source_bar_quality_issue_report(issue) for issue in issues[:max_reported]],
            "issues_truncated": max(0, len(issues) - max_reported),
        }
        self.source_bar_quality_drops += payload["bars_dropped"]
        self.source_bar_quality_error_count += len(errors)
        self.source_bar_quality_warning_count += len(warnings)
        self.last_source_bar_quality_report = payload
        print_json(payload, prefix="SYSTEM_ALERT")
        self.play_operator_sound("system")

    def handle_strategy_runtime_error(
        self,
        strategy: StrategyRuntime,
        exc: Exception,
        *,
        phase: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        strategy.error_count += 1
        strategy.last_error_utc = utc_now_iso()
        strategy.last_error_type = type(exc).__name__
        strategy.last_error = str(exc)
        disabled_now = False
        if (
            bool(self.strategy_error_config.get("disable_strategy_on_error", True))
            and strategy.error_count >= int(self.strategy_error_config.get("max_errors_per_strategy", 1))
        ):
            strategy.disabled = True
            strategy.disabled_reason = f"{phase}: {type(exc).__name__}: {exc}"
            disabled_now = True
            self.pending = [pending for pending in self.pending if pending.strategy is not strategy]
        payload = {
            "event": "strategy_runtime_error",
            "strategy_id": strategy.strategy_id,
            "strategy_name": strategy.variant_config.get("strategy_name", getattr(strategy.strategy, "name", None)),
            "strategy_config": str(strategy.strategy_config_path)
            if strategy.strategy_config_path is not None
            else f"builtin:{strategy.strategy_type}",
            "phase": phase,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "error_count": strategy.error_count,
            "strategy_disabled": bool(strategy.disabled),
            "disabled_now": disabled_now,
            "active_strategy_count": self.active_strategy_count(),
        }
        if extra:
            payload.update(extra)
        print_json(payload, prefix="SYSTEM_ALERT")
        self.play_operator_sound("system")
        if bool(self.strategy_error_config.get("fail_fast", False)):
            raise RuntimeError(f"Strategy {strategy.strategy_id} failed during {phase}: {exc}") from exc
        if self.active_strategy_count() == 0:
            no_active_payload = {
                "event": "all_strategies_disabled",
                "reason": "No active strategies remain after a strategy runtime error.",
                "strategy_health": self.strategy_health_report(),
                "fail_when_all_strategies_disabled": bool(
                    self.strategy_error_config.get("fail_when_all_strategies_disabled", True)
                ),
            }
            print_json(no_active_payload, prefix="SYSTEM_ALERT")
            self.play_operator_sound("system")
            if bool(self.strategy_error_config.get("fail_when_all_strategies_disabled", True)):
                raise RuntimeError("All strategies are disabled after runtime errors; stopping signal engine.")

    def active_strategy_count(self) -> int:
        return sum(1 for strategy in self.strategies if not strategy.disabled)

    def strategy_health_report(self) -> list[dict[str, Any]]:
        return [
            {
                "strategy_id": strategy.strategy_id,
                "strategy_name": strategy.variant_config.get("strategy_name", getattr(strategy.strategy, "name", None)),
                "disabled": strategy.disabled,
                "disabled_reason": strategy.disabled_reason,
                "runtime_error_count": strategy.error_count,
                "last_error_utc": strategy.last_error_utc,
                "last_error_type": strategy.last_error_type,
                "last_error": strategy.last_error,
                "feature_quality_skip_count": strategy.feature_quality_skip_count,
                "last_feature_quality_issue": strategy.last_feature_quality_issue,
                "processed_strategy_row_count": len(strategy.processed_strategy_row_keys),
                "evaluated_strategy_row_count": strategy.evaluated_strategy_row_count,
                "last_evaluated_strategy_timestamp": format_timestamp(strategy.last_evaluated_strategy_timestamp)
                if strategy.last_evaluated_strategy_timestamp is not None
                else None,
                "duplicate_strategy_row_skips": strategy.duplicate_strategy_row_skips,
                "active_contract_mode": strategy.active_contract_mode,
                "non_active_contract_filter_drops": strategy.non_active_contract_filter_drops,
                "last_contract_filter_report": strategy.last_contract_filter_report,
            }
            for strategy in self.strategies
        ]

    def source_contract_filter_report(self) -> dict[str, Any]:
        return {
            "enabled": self.contract_symbol_regex is not None,
            "contract_symbol_regex": self.contract_symbol_regex,
            "source_contract_filter_drops": self.source_contract_filter_drops,
            "last_source_contract_filter_report": self.last_source_contract_filter_report,
        }

    def source_bar_quality_report(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.data_quality_config.get("enabled", True)),
            "source_bar_quality_drops": self.source_bar_quality_drops,
            "source_bar_quality_error_count": self.source_bar_quality_error_count,
            "source_bar_quality_warning_count": self.source_bar_quality_warning_count,
            "last_source_bar_quality_report": self.last_source_bar_quality_report,
        }

    def audit_seed_warmup(self, bars: list[SourceMinuteBar], *, source: str) -> None:
        if not bars:
            return
        self.audit_warmup_bars(bars, source=source)

    def audit_runtime_warmup(self, *, source: str) -> None:
        self.audit_warmup_bars(self.store.bars(), source=source)

    def audit_warmup_bars(self, bars: list[SourceMinuteBar], *, source: str) -> None:
        required_sessions = int(self.data_plan.get("warmup", {}).get("min_warmup_sessions", 0) or 0)
        if required_sessions <= 0:
            return
        sessions = count_bar_sessions(bars, self.timezone) if bars else 0
        if sessions >= required_sessions:
            return
        recommended_bars = int(self.data_plan.get("warmup", {}).get("recommended_source_bars", 0) or 0)
        payload = {
            "event": "insufficient_warmup_history",
            "source": source,
            "available_sessions": sessions,
            "required_sessions": required_sessions,
            "available_source_bars": len(bars),
            "recommended_source_bars": recommended_bars,
            "fail_on_insufficient_warmup": bool(self.engine_config.get("fail_on_insufficient_warmup", False)),
            "reason": "Selected strategy data requirements need more prior sessions than the loaded seed contains.",
            "impact": "Rank/window features may be NaN or unstable until enough live sessions accumulate.",
        }
        print_json(payload, prefix="SYSTEM_ALERT")
        if bool(self.engine_config.get("fail_on_insufficient_warmup", False)):
            raise RuntimeError(
                f"Insufficient warmup history for {source}: loaded {sessions} sessions, "
                f"but selected strategies require {required_sessions}."
            )

    def emit_setup_notice(self, pending: PendingSignal) -> None:
        notice = self.build_validated_setup_notice(pending)
        self.emit_setup_notice_record(notice)

    def build_validated_setup_notice(self, pending: PendingSignal) -> dict[str, Any]:
        notice = pending.strategy.build_setup_notice(pending)
        validate_setup_notice_contract(notice)
        return notice

    def emit_setup_notice_record(self, notice: dict[str, Any]) -> None:
        self.setup_notice_count += 1
        print_json(notice, prefix="TRADE_SETUP")
        if self.operator_enabled("print_setup_readable", default=True):
            print(format_setup_readout(notice), flush=True)
        if self.dry_run_alerts:
            self.emit_dry_run_outputs_skipped(
                record_type="trade_setup",
                sound_kind="setup",
                alert_id=None,
                setup_id=notice.get("setup_id"),
            )
        self.persist_setup_notice(notice)
        self.play_operator_sound("setup")

    def operator_enabled(self, key: str, *, default: bool) -> bool:
        return bool(self.operator_config.get(key, default))

    def emit_dry_run_outputs_skipped(
        self,
        *,
        record_type: str,
        sound_kind: str,
        alert_id: Any,
        setup_id: Any,
    ) -> None:
        sound = dict(self.operator_config.get("sound", {}))
        entry_alert_would_write = record_type == "entry_signal" and self.alerts_path is not None
        setup_alert_would_write = (
            record_type == "trade_setup"
            and bool(self.setup_alerts_config.get("enabled", False))
            and self.setup_alerts_path is not None
        )
        execution_intent_would_write = (
            record_type == "entry_signal"
            and bool(self.execution_intents_config.get("enabled", False))
            and self.execution_intents_path is not None
        )
        sound_would_play = bool(sound.get("enabled", False)) and bool(sound.get(f"on_{sound_kind}", True))
        print_json(
            {
                "event": "dry_run_outputs_skipped",
                "record_type": record_type,
                "dry_run_alerts": True,
                "alert_id": alert_id,
                "setup_id": setup_id,
                "entry_alerts": {
                    "would_write": False,
                    "would_write_without_dry_run": entry_alert_would_write,
                    "write_suppressed_by_dry_run": entry_alert_would_write,
                    "path": str(self.alerts_path) if self.alerts_path else None,
                },
                "setup_alerts": {
                    "would_write": False,
                    "would_write_without_dry_run": setup_alert_would_write,
                    "write_suppressed_by_dry_run": setup_alert_would_write,
                    "enabled": bool(self.setup_alerts_config.get("enabled", False)),
                    "path": str(self.setup_alerts_path) if self.setup_alerts_path else None,
                },
                "execution_intents": {
                    "would_write": False,
                    "would_write_without_dry_run": execution_intent_would_write,
                    "write_suppressed_by_dry_run": execution_intent_would_write,
                    "enabled": bool(self.execution_intents_config.get("enabled", False)),
                    "path": str(self.execution_intents_path) if self.execution_intents_path else None,
                },
                "operator_sound": {
                    "would_play": False,
                    "would_play_without_dry_run": sound_would_play,
                    "sound_suppressed_by_dry_run": sound_would_play,
                    "enabled": bool(sound.get("enabled", False)),
                    "kind": sound_kind,
                    "bell": bool(sound.get("bell", True)),
                    "command": sound.get(f"{sound_kind}_command") or sound.get("command"),
                },
                "impact": (
                    "This is a dry-run alert. The signal was printed and validated, but no JSONL output "
                    "or operator sound was produced."
                ),
            },
            prefix="SYSTEM_ALERT",
        )

    def play_operator_sound(self, kind: str) -> None:
        if self.dry_run_alerts:
            return
        sound = dict(self.operator_config.get("sound", {}))
        if not bool(sound.get("enabled", False)):
            return
        if not bool(sound.get(f"on_{kind}", True)):
            return
        self.cleanup_operator_sound_processes(terminate_running=False)
        self.operator_sound_health.attempts += 1
        self.operator_sound_health.last_kind = kind
        if bool(sound.get("bell", True)):
            sys.stdout.write("\a")
            sys.stdout.flush()
            self.operator_sound_health.bells_written += 1
        command = sound.get(f"{kind}_command") or sound.get("command")
        if not command:
            return
        max_active_commands = config_int(
            sound,
            "max_active_commands",
            DEFAULT_OPERATOR_SOUND_MAX_ACTIVE_COMMANDS,
            min_value=0,
        )
        active_commands = len(self.operator_sound_processes)
        if active_commands >= max_active_commands:
            self.operator_sound_health.command_skips += 1
            self.operator_sound_health.last_skip_utc = utc_now_iso()
            self.operator_sound_health.last_skip_reason = (
                f"operator sound command limit reached: {active_commands}/{max_active_commands} active"
            )
            print_json(
                {
                    "event": "operator_sound_command_limit",
                    "kind": kind,
                    "command": str(command),
                    "active_command_processes": active_commands,
                    "max_active_commands": max_active_commands,
                    "command_skips": self.operator_sound_health.command_skips,
                    "fail_on_error": bool(sound.get("fail_on_error", False)),
                    "impact": (
                        "The terminal bell may have been written, but no external sound command was "
                        "launched because existing sound commands are still running."
                    ),
                },
                prefix="SYSTEM_ALERT",
            )
            if bool(sound.get("fail_on_error", False)):
                raise RuntimeError(
                    f"Operator sound command limit reached for {kind}: "
                    f"{active_commands}/{max_active_commands} active"
                )
            return
        try:
            process = subprocess.Popen(
                shlex.split(str(command)),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.operator_sound_processes.append(process)
            self.operator_sound_health.commands_started += 1
            self.operator_sound_health.last_command = str(command)
            self.operator_sound_health.last_success_utc = utc_now_iso()
        except Exception as exc:
            self.operator_sound_health.command_failures += 1
            self.operator_sound_health.last_error_utc = utc_now_iso()
            self.operator_sound_health.last_error_type = type(exc).__name__
            self.operator_sound_health.last_error = str(exc)
            print_json(
                {
                    "event": "operator_sound_error",
                    "kind": kind,
                    "command": str(command),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "fail_on_error": bool(sound.get("fail_on_error", False)),
                },
                prefix="SYSTEM_ALERT",
            )
            if bool(sound.get("fail_on_error", False)):
                raise RuntimeError(f"Operator sound alert failed for {kind}: {exc}") from exc

    def cleanup_operator_sound_processes(self, *, terminate_running: bool) -> None:
        if not self.operator_sound_processes:
            return
        remaining = []
        for process in self.operator_sound_processes:
            try:
                if process.poll() is not None:
                    continue
                if not terminate_running:
                    remaining.append(process)
                    continue
                process.terminate()
                try:
                    process.wait(timeout=0.5)
                    self.operator_sound_health.cleanup_terminated += 1
                except Exception:
                    process.kill()
                    self.operator_sound_health.cleanup_killed += 1
            except Exception as exc:
                self.operator_sound_health.last_error_utc = utc_now_iso()
                self.operator_sound_health.last_error_type = type(exc).__name__
                self.operator_sound_health.last_error = str(exc)
        self.operator_sound_processes = remaining

    def operator_sound_health_report(self) -> dict[str, Any]:
        self.cleanup_operator_sound_processes(terminate_running=False)
        sound = dict(self.operator_config.get("sound", {}))
        max_active_commands = config_int(
            sound,
            "max_active_commands",
            DEFAULT_OPERATOR_SOUND_MAX_ACTIVE_COMMANDS,
            min_value=0,
        )
        return {
            "enabled": bool(sound.get("enabled", False)),
            "bell": bool(sound.get("bell", True)),
            "cleanup_on_exit": bool(sound.get("cleanup_on_exit", True)),
            "fail_on_error": bool(sound.get("fail_on_error", False)),
            "max_active_commands": max_active_commands,
            "attempts": self.operator_sound_health.attempts,
            "bells_written": self.operator_sound_health.bells_written,
            "commands_started": self.operator_sound_health.commands_started,
            "command_failures": self.operator_sound_health.command_failures,
            "command_skips": self.operator_sound_health.command_skips,
            "active_command_processes": len(self.operator_sound_processes),
            "cleanup_terminated": self.operator_sound_health.cleanup_terminated,
            "cleanup_killed": self.operator_sound_health.cleanup_killed,
            "last_kind": self.operator_sound_health.last_kind,
            "last_command": self.operator_sound_health.last_command,
            "last_success_utc": self.operator_sound_health.last_success_utc,
            "last_skip_utc": self.operator_sound_health.last_skip_utc,
            "last_skip_reason": self.operator_sound_health.last_skip_reason,
            "last_error_utc": self.operator_sound_health.last_error_utc,
            "last_error_type": self.operator_sound_health.last_error_type,
            "last_error": self.operator_sound_health.last_error,
        }

    def acquire_process_lock(self) -> None:
        if not bool(self.process_lock_config.get("enabled", False)):
            return
        if self.process_lock_path is None:
            raise RuntimeError("engine.process_lock.enabled is true but no lock path is configured.")
        if self.process_lock_acquired:
            return
        stale_after_seconds = float(self.process_lock_config.get("stale_after_seconds", 86400.0))
        fail_if_locked = bool(self.process_lock_config.get("fail_if_locked", True))
        self.process_lock_path.parent.mkdir(parents=True, exist_ok=True)
        token = alert_hash(str(os.getpid()), str(time.time_ns()), str(self.config_path))
        payload = {
            "schema_version": "process_lock.v1",
            "token": token,
            "pid": os.getpid(),
            "created_at_utc": utc_now_iso(),
            "config": str(self.config_path),
            "alerts_path": str(self.alerts_path) if self.alerts_path else None,
            "execution_intents_path": str(self.execution_intents_path) if self.execution_intents_path else None,
        }
        while True:
            try:
                fd = os.open(str(self.process_lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(json.dumps(payload, sort_keys=True, default=json_default) + "\n")
                self.process_lock_token = token
                self.process_lock_acquired = True
                print_json(
                    {
                        "event": "process_lock_acquired",
                        "path": str(self.process_lock_path),
                        "pid": os.getpid(),
                    }
                )
                return
            except FileExistsError:
                existing = read_process_lock_file(self.process_lock_path)
                if is_process_lock_stale(self.process_lock_path, existing, stale_after_seconds=stale_after_seconds):
                    print_json(
                        {
                            "event": "stale_process_lock_replaced",
                            "path": str(self.process_lock_path),
                            "existing_lock": existing,
                        },
                        prefix="SYSTEM_ALERT",
                    )
                    try:
                        self.process_lock_path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                payload = {
                    "event": "process_lock_already_held",
                    "path": str(self.process_lock_path),
                    "existing_lock": existing,
                    "impact": "Another signal engine process appears to be active for this config/path.",
                }
                print_json(payload, prefix="SYSTEM_ALERT")
                self.play_operator_sound("system")
                if fail_if_locked:
                    raise RuntimeError(
                        f"Signal engine process lock is already held at {self.process_lock_path}; "
                        "refusing to start another writer."
                    )
                return

    def release_process_lock(self) -> None:
        if not self.process_lock_acquired or self.process_lock_path is None:
            return
        existing = read_process_lock_file(self.process_lock_path)
        if existing.get("token") == self.process_lock_token:
            try:
                self.process_lock_path.unlink()
                print_json({"event": "process_lock_released", "path": str(self.process_lock_path)})
            except FileNotFoundError:
                pass
        else:
            print_json(
                {
                    "event": "process_lock_release_skipped",
                    "path": str(self.process_lock_path),
                    "reason": "lock file token does not match this process",
                    "existing_lock": existing,
                },
                prefix="SYSTEM_ALERT",
            )
        self.process_lock_acquired = False
        self.process_lock_token = None

    def _load_strategies(self) -> list[StrategyRuntime]:
        specs = self.config.get("strategies")
        if not isinstance(specs, list) or not specs:
            raise ValueError("config must define a non-empty strategies list")
        strategies = []
        for raw_spec in specs:
            if isinstance(raw_spec, str):
                spec = {"config": raw_spec}
            elif isinstance(raw_spec, dict):
                spec = dict(raw_spec)
            else:
                raise ValueError("each strategy spec must be a config path string or mapping")
            if not bool(spec.get("enabled", True)):
                continue
            strategies.append(
                StrategyRuntime(
                    project_root=self.project_root,
                    config_dir=self.config_dir,
                    strategy_spec=spec,
                    engine_config={
                        **self.engine_config,
                        "symbol": self.symbol,
                        "timezone": self.timezone,
                        "delta_method": self.delta_method,
                        "active_contract_mode": validate_active_contract_mode(
                            self.databento_config.get("active_contract_mode", "highest_session_volume")
                        ),
                        "contract_symbol_regex": self.contract_symbol_regex,
                        "_engine_config_label": self.engine_config_label,
                        "_engine_config_fingerprint": self.engine_config_fingerprint,
                    },
                    operator_config=self.operator_config,
                )
            )
        if not strategies:
            raise ValueError("all configured strategies are disabled")
        validate_unique_strategy_ids(strategies)
        return strategies


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Databento historical/live ticks through propstack strategy YAMLs.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Signal-engine YAML config.")
    parser.add_argument("--project-root", help="Project root containing src/ and configs/.")
    parser.add_argument("--strategy-config", action="append", help="Add/override with a campaign strategy YAML path.")
    parser.add_argument("--preflight-only", action="store_true", help="Validate config and exit without Databento access.")
    parser.add_argument(
        "--check-databento-metadata",
        action="store_true",
        help="Validate Databento credentials/dataset/schema and estimate configured historical cost without downloading data.",
    )
    parser.add_argument(
        "--readiness-check",
        action="store_true",
        help=(
            "Validate config, Databento metadata/cost guard, historical cache metadata, "
            "output paths, operator sound commands, warmup, and strategy health without live subscription or alert writes."
        ),
    )
    parser.add_argument(
        "--check-execution-intents",
        action="store_true",
        help="Read and validate the router-facing execution-intent JSONL outbox without Databento access.",
    )
    parser.add_argument(
        "--execution-intents-path",
        help="Override engine.execution_intents.path for --check-execution-intents.",
    )
    parser.add_argument(
        "--require-actionable-intent",
        action="store_true",
        help="With --check-execution-intents, return non-zero when no currently actionable intent is present.",
    )
    parser.add_argument(
        "--strict-execution-intents",
        action="store_true",
        help="With --check-execution-intents, return non-zero when any outbox line is rejected or malformed.",
    )
    parser.add_argument("--seed-only", action="store_true", help="Load/fetch historical seed bars, hydrate strategies, then exit.")
    parser.add_argument("--replay-bars", help="Replay cached 1-minute orderflow bars as live source bars.")
    parser.add_argument("--replay-stop-after-signal", action="store_true", help="Stop replay after the first ENTRY_SIGNAL.")
    parser.add_argument(
        "--replay-require-signal",
        action="store_true",
        help="Return a non-zero exit code if replay completes without an ENTRY_SIGNAL.",
    )
    parser.add_argument(
        "--replay-require-healthy-strategies",
        action="store_true",
        help=(
            "Return a non-zero exit code if replay leaves any strategy disabled, records a strategy runtime error, "
            "has no active strategies, or an active strategy evaluates zero complete rows."
        ),
    )
    parser.add_argument("--max-replay-bars", type=int, default=0, help="Cap replayed bars after the seed; 0 means no cap.")
    parser.add_argument("--skip-historical", action="store_true", help="Do not fetch/load historical seed data.")
    parser.add_argument(
        "--refresh-historical",
        action="store_true",
        help="Ignore historical cache/seed file and refetch from Databento.",
    )
    parser.add_argument("--live", action="store_true", help="Start live Databento streaming after seeding.")
    parser.add_argument("--once", action="store_true", help="Stop after the first live source bar completes.")
    parser.add_argument("--max-runtime", type=float, default=0.0, help="Optional live runtime limit in seconds.")
    parser.add_argument(
        "--dry-run-alerts",
        action="store_true",
        help="Print and validate signals, but do not write JSONL outboxes or play sounds.",
    )
    parser.add_argument("--databento-symbols", help="Override databento.symbols, e.g. ESM6 or ES.FUT.")
    parser.add_argument("--databento-stype-in", help="Override databento.stype_in.")
    parser.add_argument("--databento-stype-out", help="Override historical databento.stype_out.")
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
    if args.check_databento_metadata:
        print_json(check_databento_metadata(engine))
        return 0
    if args.check_execution_intents:
        intent_report = check_execution_intents_outbox(
            engine,
            path_override=args.execution_intents_path,
            require_actionable=args.require_actionable_intent,
            strict=args.strict_execution_intents,
        )
        return 0 if bool(intent_report.get("ok", False)) else 1
    if args.readiness_check:
        readiness_report = run_readiness_check(engine)
        return 0 if bool(readiness_report.get("ok", False)) else 1

    enforce_live_subscription_cost_guard_before_process_lock(engine, args)
    enforce_live_metadata_preflight_before_process_lock(engine, args)
    enforce_output_sink_safety_before_process_lock(engine, args)
    engine.acquire_process_lock()
    try:
        seed_bars: list[SourceMinuteBar] = []
        accepted_seed_bars = 0
        if not args.skip_historical:
            seed_bars = load_historical_seed_bars(engine, refresh=args.refresh_historical)
            if seed_bars:
                seed_store_count_start = len(engine.store.bars())
                engine.seed(seed_bars, source="historical")
                accepted_seed_bars = max(0, len(engine.store.bars()) - seed_store_count_start)
        if args.seed_only:
            seed_report = seed_only_completion_report(
                engine,
                historical_skipped=bool(args.skip_historical),
                raw_seed_bars=len(seed_bars),
                accepted_seed_bars=accepted_seed_bars,
            )
            return 0 if bool(seed_report.get("ok", False)) else 1
        if args.replay_bars:
            replay_report = replay_bars(engine, resolve_cli_path(config_path.parent, args.replay_bars), args)
            return 0 if bool(replay_report.get("ok", True)) else 1
        live_enabled = live_startup_requested(engine, args)
        if not live_enabled:
            return 0
        engine.audit_runtime_warmup(source="live_startup")
        return run_live(engine, once=args.once, max_runtime=args.max_runtime)
    finally:
        sound = dict(engine.operator_config.get("sound", {}))
        engine.cleanup_operator_sound_processes(terminate_running=bool(sound.get("cleanup_on_exit", True)))
        engine.release_process_lock()


def seed_only_completion_report(
    engine: SignalEngine,
    *,
    historical_skipped: bool,
    raw_seed_bars: int,
    accepted_seed_bars: int,
) -> dict[str, Any]:
    hist_cfg = dict(engine.databento_config.get("historical", {}))
    historical_enabled = bool(hist_cfg.get("enabled", True))
    reasons: list[str] = []
    if historical_skipped:
        reasons.append("--skip-historical was set")
    if not historical_enabled:
        reasons.append("databento.historical.enabled is false")
    if raw_seed_bars <= 0:
        reasons.append("no historical seed bars were loaded or fetched")
    if raw_seed_bars > 0 and accepted_seed_bars <= 0:
        reasons.append("no historical seed bars survived source quality and contract filters")
    ok = not reasons
    payload = {
        "event": "seed_only_complete" if ok else "seed_only_failed",
        "ok": ok,
        "historical_skipped": historical_skipped,
        "historical_enabled": historical_enabled,
        "historical_cache_path": str(resolve_optional_path(engine.config_dir, hist_cfg.get("cache_path")))
        if hist_cfg.get("cache_path") is not None
        else None,
        "raw_seed_bars": raw_seed_bars,
        "accepted_seed_bars": accepted_seed_bars,
        "reason": "; ".join(reasons) if reasons else "historical seed context loaded and accepted",
        "source_contract_filter": engine.source_contract_filter_report(),
        "source_bar_quality": engine.source_bar_quality_report(),
        "strategy_health": engine.strategy_health_report(),
    }
    print_json(payload, prefix=None if ok else "SYSTEM_ALERT")
    return payload


def live_startup_requested(engine: SignalEngine, args: argparse.Namespace) -> bool:
    return bool(getattr(args, "live", False) or bool(engine.databento_config.get("live", {}).get("enabled", False)))


def should_check_live_cost_guard_before_process_lock(engine: SignalEngine, args: argparse.Namespace) -> bool:
    if not live_startup_requested(engine, args):
        return False
    if bool(getattr(args, "seed_only", False)):
        return False
    if getattr(args, "replay_bars", None):
        return False
    return True


def enforce_live_subscription_cost_guard_before_process_lock(
    engine: SignalEngine,
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    if not should_check_live_cost_guard_before_process_lock(engine, args):
        return None
    live_cfg = dict(engine.databento_config.get("live", {}))
    if live_cost_guard_report(live_cfg)["allowed"]:
        return None
    dataset = str(engine.databento_config.get("dataset", DEFAULT_DATASET))
    schema = str(engine.databento_config.get("schema", DEFAULT_SCHEMA))
    symbols = engine.databento_config.get("symbols", DEFAULT_DATABENTO_SYMBOLS)
    stype_in = str(engine.databento_config.get("stype_in", DEFAULT_STYPE_IN))
    return enforce_live_subscription_cost_guard(
        live_cfg,
        dataset=dataset,
        symbols=symbols,
        schema=schema,
        stype_in=stype_in,
    )


def should_check_live_metadata_preflight_before_process_lock(engine: SignalEngine, args: argparse.Namespace) -> bool:
    if not live_startup_requested(engine, args):
        return False
    if bool(getattr(args, "seed_only", False)):
        return False
    if getattr(args, "replay_bars", None):
        return False
    return True


def enforce_live_metadata_preflight_before_process_lock(
    engine: SignalEngine,
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    if not should_check_live_metadata_preflight_before_process_lock(engine, args):
        return None
    return enforce_live_metadata_preflight_guard(engine, emit_bypass_alert=False)


def should_check_output_sink_safety_before_process_lock(engine: SignalEngine, args: argparse.Namespace) -> bool:
    if not live_startup_requested(engine, args):
        return False
    if bool(getattr(args, "seed_only", False)):
        return False
    if getattr(args, "replay_bars", None):
        return False
    return True


def enforce_output_sink_safety_before_process_lock(
    engine: SignalEngine,
    args: argparse.Namespace,
) -> dict[str, Any] | None:
    if not should_check_output_sink_safety_before_process_lock(engine, args):
        return None
    return enforce_output_sink_safety_before_live(engine)


def enforce_output_sink_safety_before_live(engine: SignalEngine) -> dict[str, Any]:
    report = output_sink_safety_report(engine)
    if bool(report.get("ok", False)):
        return report
    print_json(
        {
            "event": "live_output_sink_safety_failed",
            **report,
            "live_subscription_attempted": False,
            "reason": "Live mode requires fail-closed alert/outbox sinks for this config.",
            "impact": (
                "The live subscription was not opened. Fix sink fail-fast, duplicate suppression, "
                "and freshness settings, or disable require_fail_closed_sinks for diagnostic-only runs."
            ),
        },
        prefix="SYSTEM_ALERT",
    )
    engine.play_operator_sound("system")
    raise RuntimeError("Live output sink safety check failed before subscription.")


def live_metadata_preflight_guard_report(live_cfg: dict[str, Any]) -> dict[str, Any]:
    metadata_preflight = bool(live_cfg.get("metadata_preflight", True))
    allow_bypass = bool(live_cfg.get("allow_live_without_metadata_preflight", False))
    ok = metadata_preflight or allow_bypass
    reason = (
        "metadata_preflight is enabled"
        if metadata_preflight
        else (
            "metadata_preflight is disabled with explicit diagnostic bypass"
            if allow_bypass
            else "metadata_preflight is disabled and no diagnostic bypass was acknowledged"
        )
    )
    return {
        "ok": ok,
        "metadata_preflight": metadata_preflight,
        "allow_live_without_metadata_preflight": allow_bypass,
        "required": True,
        "reason": reason,
    }


def enforce_live_metadata_preflight_guard(
    engine: SignalEngine,
    *,
    emit_bypass_alert: bool = True,
) -> dict[str, Any]:
    live_cfg = dict(engine.databento_config.get("live", {}))
    report = live_metadata_preflight_guard_report(live_cfg)
    if bool(report.get("ok", False)):
        if not bool(report.get("metadata_preflight", True)) and emit_bypass_alert:
            print_json(
                {
                    "event": "live_metadata_preflight_bypass_acknowledged",
                    **report,
                    "timeseries_download_attempted": False,
                    "live_subscription_attempted": False,
                    "impact": (
                        "Live startup will skip Databento metadata/schema/field/symbology checks. "
                        "Use this only for deterministic tests or diagnostic fake-live runs."
                    ),
                },
                prefix="SYSTEM_ALERT",
            )
        return report
    print_json(
        {
            "event": "live_metadata_preflight_disabled",
            **report,
            "timeseries_download_attempted": False,
            "live_subscription_attempted": False,
            "reason": (
                "Live mode requires metadata_preflight unless "
                "databento.live.allow_live_without_metadata_preflight is explicitly true."
            ),
            "impact": (
                "The live subscription was not opened. The engine cannot prove Databento schema, "
                "field, symbology, and cost-guard contracts without metadata preflight."
            ),
        },
        prefix="SYSTEM_ALERT",
    )
    engine.play_operator_sound("system")
    raise RuntimeError("Live metadata preflight is disabled; refusing to start live mode.")


def summarize_actionable_execution_intents(
    records: list[dict[str, Any]],
    *,
    now_utc: Any,
) -> dict[str, Any]:
    now = normalize_utc_timestamp(now_utc)
    compact_records: list[dict[str, Any]] = []
    expired_but_within_grace_count = 0

    for record in records:
        intent = record.get("execution_intent") if isinstance(record, dict) else {}
        intent = intent if isinstance(intent, dict) else {}
        timing = intent.get("timing") if isinstance(intent.get("timing"), dict) else {}
        source = intent.get("source") if isinstance(intent.get("source"), dict) else {}
        order = intent.get("order") if isinstance(intent.get("order"), dict) else {}
        bracket = intent.get("bracket") if isinstance(intent.get("bracket"), dict) else {}
        risk = intent.get("risk") if isinstance(intent.get("risk"), dict) else {}

        valid_from_utc = normalize_utc_timestamp(timing["valid_from_utc"])
        expires_at_utc = normalize_utc_timestamp(timing["expires_at_utc"])
        seconds_until_valid = (valid_from_utc - now).total_seconds()
        seconds_until_expiry = (expires_at_utc - now).total_seconds()
        if seconds_until_expiry < 0:
            expired_but_within_grace_count += 1

        compact_records.append(
            {
                "alert_id": record.get("alert_id") or intent.get("intent_id"),
                "setup_id": record.get("setup_id") or source.get("setup_id"),
                "strategy_id": record.get("strategy_id") or source.get("strategy_id"),
                "symbol": record.get("symbol") or intent.get("symbol"),
                "contract_symbol": record.get("contract_symbol") or intent.get("contract_symbol"),
                "timeframe": record.get("timeframe") or intent.get("timeframe"),
                "direction": intent.get("direction"),
                "side": intent.get("side"),
                "quantity": intent.get("quantity"),
                "entry_timestamp_utc": timing.get("entry_timestamp_utc") or record.get("entry_timestamp_utc"),
                "valid_from_utc": format_timestamp(valid_from_utc),
                "expires_at_utc": format_timestamp(expires_at_utc),
                "seconds_until_valid": round(seconds_until_valid, 6),
                "seconds_until_expiry": round(seconds_until_expiry, 6),
                "entry_price": order.get("estimated_entry_price"),
                "stop_loss_price": bracket.get("stop_loss_price"),
                "take_profit_price": bracket.get("take_profit_price"),
                "risk_dollars": risk.get("risk_dollars"),
                "reward_dollars": risk.get("reward_dollars"),
            }
        )

    compact_records.sort(
        key=lambda item: (
            normalize_utc_timestamp(item["expires_at_utc"]),
            normalize_utc_timestamp(item["valid_from_utc"]),
            str(item.get("alert_id") or ""),
        )
    )
    next_expiring = compact_records[0] if compact_records else None
    latest_expiring = compact_records[-1] if compact_records else None
    return {
        "actionable_count": len(compact_records),
        "expired_but_within_grace_count": expired_but_within_grace_count,
        "soonest_expires_at_utc": next_expiring["expires_at_utc"] if next_expiring else None,
        "seconds_until_soonest_expiry": (
            next_expiring["seconds_until_expiry"] if next_expiring else None
        ),
        "latest_expires_at_utc": latest_expiring["expires_at_utc"] if latest_expiring else None,
        "next_expiring_intent": next_expiring,
        "records": compact_records,
    }


def check_execution_intents_outbox(
    engine: SignalEngine,
    *,
    path_override: str | os.PathLike[str] | None = None,
    now_utc: Any | None = None,
    require_actionable: bool = False,
    strict: bool = False,
) -> dict[str, Any]:
    outbox_path = (
        resolve_cli_path(engine.config_dir, path_override)
        if path_override is not None
        else engine.execution_intents_path
    )
    configured_path = str(engine.execution_intents_path) if engine.execution_intents_path else None
    base_report = {
        "event": "execution_intent_outbox_check",
        "configured_path": configured_path,
        "path_override": str(path_override) if path_override is not None else None,
        "execution_intents_enabled": bool(engine.execution_intents_config.get("enabled", False)),
        "require_actionable_intent": bool(require_actionable),
        "strict": bool(strict),
        "freshness_grace_seconds": float(engine.execution_intents_config.get("freshness_grace_seconds", 0.0)),
    }
    check_now = normalize_utc_timestamp(now_utc if now_utc is not None else pd.Timestamp.utcnow())
    empty_actionable_summary = summarize_actionable_execution_intents([], now_utc=check_now)
    if outbox_path is None:
        report = {
            **base_report,
            "ok": False,
            "path": None,
            "now_utc": format_timestamp(check_now),
            "records_read": 0,
            "actionable_count": 0,
            "rejected_count": 0,
            "malformed_count": 0,
            "records": [],
            "rejected": [],
            "actionable_summary": empty_actionable_summary,
            "error_type": "ConfigError",
            "error": "No execution-intent outbox path is configured. Set engine.execution_intents.path or pass --execution-intents-path.",
        }
        print_json(report, prefix="SYSTEM_ALERT")
        return report

    try:
        read_report = load_actionable_execution_intents(
            outbox_path,
            now_utc=check_now,
            grace_seconds=float(engine.execution_intents_config.get("freshness_grace_seconds", 0.0)),
            include_rejected=True,
            fail_on_error=False,
            dedupe_alert_ids=True,
        )
    except Exception as exc:
        report = {
            **base_report,
            "ok": False,
            "path": str(outbox_path),
            "now_utc": format_timestamp(check_now),
            "records_read": 0,
            "actionable_count": 0,
            "rejected_count": 0,
            "malformed_count": 0,
            "records": [],
            "rejected": [],
            "actionable_summary": empty_actionable_summary,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        print_json(report, prefix="SYSTEM_ALERT")
        return report

    actionable_count = int(read_report.get("actionable_count", 0) or 0)
    rejected_count = int(read_report.get("rejected_count", 0) or 0)
    malformed_count = int(read_report.get("malformed_count", 0) or 0)
    duplicate_alert_id_count = int(read_report.get("duplicate_alert_id_count", 0) or 0)
    duplicate_setup_id_count = int(read_report.get("duplicate_setup_id_count", 0) or 0)
    ok = True
    failure_reasons: list[str] = []
    if require_actionable and actionable_count <= 0:
        ok = False
        failure_reasons.append("required_actionable_intent_missing")
    if strict and rejected_count > 0:
        ok = False
        failure_reasons.append("strict_rejected_records_present")
    if strict and malformed_count > 0 and "strict_rejected_records_present" not in failure_reasons:
        ok = False
        failure_reasons.append("strict_malformed_records_present")
    actionable_summary = summarize_actionable_execution_intents(
        list(read_report.get("records", []) or []),
        now_utc=check_now,
    )

    report = {
        **base_report,
        **read_report,
        "event": "execution_intent_outbox_check",
        "ok": ok,
        "path": str(outbox_path),
        "now_utc": format_timestamp(check_now),
        "failure_reasons": failure_reasons,
        "actionable_summary": actionable_summary,
    }
    print_json(report)
    if not ok:
        print_json(
            {
                "event": "execution_intent_outbox_check_failed",
                "path": str(outbox_path),
                "failure_reasons": failure_reasons,
                "actionable_count": actionable_count,
                "rejected_count": rejected_count,
                "malformed_count": malformed_count,
                "duplicate_alert_id_count": duplicate_alert_id_count,
                "duplicate_setup_id_count": duplicate_setup_id_count,
                "actionable_summary": actionable_summary,
                "impact": "Execution-intent outbox is not ready for the requested consumer gate.",
            },
            prefix="SYSTEM_ALERT",
        )
    return report


def apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    config = copy.deepcopy(config)
    if args.project_root:
        config["project_root"] = args.project_root
    if args.strategy_config:
        config["strategies"] = [{"config": path, "enabled": True} for path in args.strategy_config]
    if args.dry_run_alerts:
        config.setdefault("engine", {})["dry_run_alerts"] = True
    databento = config.setdefault("databento", {})
    if args.skip_historical:
        databento.setdefault("historical", {})["enabled"] = False
    if args.refresh_historical:
        databento.setdefault("historical", {})["refresh"] = True
    if args.live:
        databento.setdefault("live", {})["enabled"] = True
    if args.databento_symbols:
        databento["symbols"] = args.databento_symbols
    if args.databento_stype_in:
        databento["stype_in"] = args.databento_stype_in
    if args.databento_stype_out:
        databento["stype_out"] = args.databento_stype_out
    return config


def build_engine_data_plan(engine: SignalEngine) -> dict[str, Any]:
    strategy_reqs = [data_requirement_report(req) for req in engine.data_requirements]
    source_columns: set[str] = set()
    feature_families: set[str] = set()
    derived_columns: set[str] = set()
    large_trade_sizes: set[int] = set()
    min_warmup_sessions = 0
    recommended_source_bars = 0
    max_feature_window_bars = 1
    for req in engine.data_requirements:
        source_columns.update(req.source_columns)
        feature_families.update(req.feature_families)
        derived_columns.update(req.derived_feature_columns)
        large_trade_sizes.update(req.large_trade_sizes)
        min_warmup_sessions = max(min_warmup_sessions, req.min_warmup_sessions)
        recommended_source_bars = max(recommended_source_bars, req.recommended_source_bars)
        max_feature_window_bars = max(max_feature_window_bars, req.max_feature_window_bars)

    required_live_schema = required_schema_for_delta_method(engine.delta_method)
    configured_schema = str(engine.databento_config.get("schema", DEFAULT_SCHEMA))
    required_live_field_groups = live_schema_required_field_groups(
        delta_method=engine.delta_method,
        contract_symbol_regex=engine.contract_symbol_regex,
        schema=configured_schema,
    )
    warnings: list[str] = []
    max_source_bars = int(engine.engine_config.get("max_source_bars", 0) or 0)
    if max_source_bars and recommended_source_bars and max_source_bars < recommended_source_bars:
        warnings.append(
            f"engine.max_source_bars ({max_source_bars}) is below recommended_source_bars "
            f"({recommended_source_bars}) for selected strategy warmup requirements."
        )
    historical = dict(engine.databento_config.get("historical", {}))
    lookback_days = int(historical.get("lookback_days", 0) or 0)
    if lookback_days and min_warmup_sessions and lookback_days < min_warmup_sessions:
        warnings.append(
            f"historical.lookback_days ({lookback_days}) is below the inferred minimum warmup sessions "
            f"({min_warmup_sessions})."
        )
    if bool(historical.get("enabled", True)) and engine.delta_method != "aggressor_side":
        warnings.append(
            "historical signed_volume is already baked into cached/fetched bars; verify historical seed bars "
            f"were generated with delta_method={engine.delta_method!r} before comparing with live signals."
        )

    return {
        "configured_schema": configured_schema,
        "required_live_schema": required_live_schema,
        "required_live_field_groups": required_live_field_groups,
        "delta_method": engine.delta_method,
        "source_columns": sorted(source_columns),
        "feature_families": sorted(feature_families),
        "derived_feature_columns": sorted(derived_columns),
        "large_trade_sizes": sorted(large_trade_sizes),
        "warmup": {
            "max_feature_window_bars": int(max_feature_window_bars),
            "min_warmup_sessions": int(min_warmup_sessions),
            "recommended_source_bars": int(recommended_source_bars),
            "configured_max_source_bars": max_source_bars,
        },
        "strategies": strategy_reqs,
        "warnings": warnings,
    }


def validate_engine_data_plan(engine: SignalEngine) -> None:
    plan = engine.data_plan
    configured_schema = normalize_schema_name(plan.get("configured_schema"))
    required_schema = normalize_schema_name(plan.get("required_live_schema"))
    errors: list[str] = []
    if required_schema == "mbp-1" and configured_schema != "mbp-1":
        errors.append(
            "databento.delta_method=price_vs_quote requires live databento.schema=mbp-1 "
            "so bid/ask prices are available."
        )
    elif required_schema == "trades" and configured_schema not in {"trades", "mbp-1"}:
        errors.append(
            f"selected strategies require trade prints, but databento.schema={configured_schema!r} "
            "does not provide the required trade fields."
        )
    if errors:
        raise ValueError("Databento data preflight failed: " + "; ".join(errors))
    for warning in plan.get("warnings", []):
        print_json({"event": "data_plan_warning", "warning": warning}, prefix="SYSTEM_ALERT")


def check_databento_metadata(engine: SignalEngine, client: Any | None = None) -> dict[str, Any]:
    dataset = str(engine.databento_config.get("dataset", DEFAULT_DATASET))
    schema = str(engine.databento_config.get("schema", DEFAULT_SCHEMA))
    symbols = engine.databento_config.get("symbols", DEFAULT_DATABENTO_SYMBOLS)
    stype_in = str(engine.databento_config.get("stype_in", DEFAULT_STYPE_IN))
    live_cfg = dict(engine.databento_config.get("live", {}))
    hist_cfg = dict(engine.databento_config.get("historical", {}))
    live_enabled = bool(live_cfg.get("enabled", False))
    client_injected = client is not None
    api_key_status = databento_api_key_status(engine.databento_config, required=not client_injected)
    api_key_status["client_injected"] = client_injected
    metadata_operations_attempted: list[str] = []
    report: dict[str, Any] = {
        "event": "databento_metadata_check",
        "operation_mode": "metadata_only",
        "dataset": dataset,
        "schema": schema,
        "symbols": symbols,
        "stype_in": stype_in,
        "api_key": api_key_status,
        "checks": {},
        "warnings": [],
        "errors": [],
        "timeseries_download_attempted": False,
        "live_subscription_attempted": False,
        "metadata_only": True,
        "metadata_operations_attempted": metadata_operations_attempted,
        "databento_api_audit": {
            "metadata_only": True,
            "metadata_operations_attempted": metadata_operations_attempted,
            "timeseries_get_range_attempted": False,
            "live_subscribe_attempted": False,
            "guarded_timeseries_operation": "timeseries.get_range",
            "guarded_live_operation": "Live.subscribe",
        },
    }
    report["checks"]["api_key"] = api_key_status

    if not client_injected and not bool(api_key_status.get("ok", False)):
        print_json(
            {
                "event": "databento_api_key_missing",
                **api_key_status,
                "impact": (
                    "Databento metadata, historical, and live checks cannot run until the key is "
                    "available in this process environment."
                ),
            },
            prefix="SYSTEM_ALERT",
        )
        raise RuntimeError(str(api_key_status.get("error") or "Missing Databento API key."))

    if client is None:
        import databento as db

        client = db.Historical(databento_api_key(engine.databento_config))

    live_cost_guard = live_cost_guard_report(live_cfg)
    report["checks"]["live_cost_guard"] = {
        "ok": (not live_enabled) or bool(live_cost_guard.get("allowed", False)),
        "live_enabled": live_enabled,
        **live_cost_guard,
    }
    if live_enabled and not bool(live_cost_guard.get("allowed", False)):
        report["errors"].append(
            "Databento live is enabled but live cost guard is not explicitly acknowledged."
        )

    available_start = None
    available_end = None
    try:
        metadata_operations_attempted.append("metadata.get_dataset_range")
        raw_range = client.metadata.get_dataset_range(dataset)
        available_start = parse_available_range_timestamp(raw_range.get("start") or raw_range.get("start_date"))
        available_end = parse_available_range_timestamp(raw_range.get("end") or raw_range.get("end_date"))
        report["checks"]["dataset_range"] = {
            "ok": available_start is not None and available_end is not None,
            "start": str(available_start) if available_start is not None else None,
            "end": str(available_end) if available_end is not None else None,
            "raw": raw_range,
        }
        if available_start is None or available_end is None:
            report["warnings"].append("Databento dataset range response did not include parseable start/end timestamps.")
    except Exception as exc:
        report["checks"]["dataset_range"] = {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
        report["errors"].append(f"Unable to read Databento dataset range for {dataset}: {exc}")

    try:
        metadata_operations_attempted.append("metadata.list_schemas")
        schemas = [str(item) for item in client.metadata.list_schemas(dataset)]
        normalized_schemas = {normalize_schema_name(item) for item in schemas}
        schema_ok = normalize_schema_name(schema) in normalized_schemas
        report["checks"]["schemas"] = {
            "ok": schema_ok,
            "configured_schema": schema,
            "available_schemas": schemas,
        }
        if not schema_ok:
            report["errors"].append(f"Databento schema {schema!r} is not listed for dataset {dataset}.")
    except Exception as exc:
        report["checks"]["schemas"] = {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
        report["errors"].append(f"Unable to list Databento schemas for {dataset}: {exc}")

    try:
        metadata_operations_attempted.append("metadata.list_fields")
        fields = client.metadata.list_fields(schema=schema, encoding="dbn")
        field_names = sorted(str(item.get("name", "")) for item in fields if isinstance(item, dict) and item.get("name"))
        field_requirements = live_schema_field_requirement_report(
            field_names,
            delta_method=engine.delta_method,
            contract_symbol_regex=engine.contract_symbol_regex,
            schema=schema,
        )
        report["checks"]["fields"] = {
            "ok": bool(field_names) and bool(field_requirements.get("ok", False)),
            "schema": schema,
            "encoding": "dbn",
            "field_count": len(field_names),
            "sample_fields": field_names[:25],
            "required_field_groups": field_requirements["required_field_groups"],
            "missing_required_field_groups": field_requirements["missing_required_field_groups"],
        }
        if not field_names:
            report["errors"].append(
                f"Databento did not return any DBN fields for schema {schema!r}; "
                "required live fields could not be verified."
            )
        elif not bool(field_requirements.get("ok", False)):
            missing = ", ".join(
                str(item.get("label") or item.get("aliases"))
                for item in field_requirements["missing_required_field_groups"]
            )
            report["errors"].append(
                f"Databento schema {schema!r} is missing required live field group(s): {missing}."
            )
    except Exception as exc:
        report["checks"]["fields"] = {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
        report["errors"].append(
            f"Unable to list Databento fields for schema {schema!r}; required live fields could not be verified: {exc}"
        )

    try:
        metadata_operations_attempted.append("symbology.resolve")
        symbology_check = check_databento_symbology(
            client,
            dataset=dataset,
            symbols=symbols,
            stype_in=stype_in,
            stype_out=str(live_cfg.get("symbology_stype_out") or "instrument_id"),
            available_end=available_end,
        )
        report["checks"]["symbology"] = symbology_check
        if not bool(symbology_check.get("ok", False)):
            report["errors"].append(str(symbology_check.get("error") or "Databento symbology check failed."))
        elif symbology_check.get("partial"):
            report["warnings"].append("Databento symbology check returned partial mappings.")
    except Exception as exc:
        report["checks"]["symbology"] = {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
        report["errors"].append(f"Databento symbology check failed: {exc}")

    if bool(hist_cfg.get("enabled", True)):
        fetch_contract = databento_historical_fetch_contract_report(engine, hist_cfg)
        report["checks"]["historical_fetch_contract"] = fetch_contract
        if not bool(fetch_contract.get("ok", False)):
            errors = "; ".join(str(error) for error in fetch_contract.get("errors", []))
            print_json(
                {
                    "event": "historical_fetch_contract_unsupported",
                    **fetch_contract,
                    "reason": (
                        "The configured historical source would require a Databento timeseries download, "
                        "but the built-in historical fetcher cannot produce bars for this schema/delta method."
                    ),
                    "impact": (
                        "Metadata validation is failing before any historical cost estimate or download. "
                        "Use a prebuilt cache/seed file with matching metadata, or switch historical fetch "
                        "to schema=trades and delta_method=aggressor_side."
                    ),
                },
                prefix="SYSTEM_ALERT",
            )
            report["errors"].append(
                "Historical Databento download is required but unsupported by the built-in fetcher: "
                f"{errors}"
            )
            report["checks"]["historical_cost_guard"] = {
                "ok": False,
                "skipped": True,
                "reason": "historical fetch contract is unsupported",
                "timeseries_get_range_attempted": False,
                "guarded_operation": "timeseries.get_range",
            }
        else:
            if not bool(fetch_contract.get("fetch_required", False)):
                report["warnings"].append(
                    "Historical Databento download is not required for this configuration because "
                    f"historical source is {fetch_contract.get('source')!r}."
                )
                report["checks"]["historical_cost_guard"] = {
                    "ok": True,
                    "skipped": True,
                    "reason": "historical Databento download is not required",
                    "source": fetch_contract.get("source"),
                    "fetch_required": False,
                    "metadata_only": True,
                    "timeseries_get_range_attempted": False,
                    "guarded_operation": "timeseries.get_range",
                }
            else:
                try:
                    start, end = historical_bounds(hist_cfg, engine.timezone, max_end=available_end)
                    metadata_operations_attempted.append("metadata.get_cost")
                    metadata_operations_attempted.append("metadata.get_billable_size")
                    cost_report = enforce_historical_cost_guard(
                        client,
                        hist_cfg,
                        dataset=dataset,
                        symbols=symbols,
                        schema=schema,
                        stype_in=stype_in,
                        start=start,
                        end=end,
                        limit=hist_cfg.get("limit"),
                    )
                    report["checks"]["historical_cost_guard"] = {
                        "ok": bool(cost_report.get("allowed", not cost_report.get("enabled", True))),
                        "skipped": False,
                        "fetch_required": True,
                        "start": str(start),
                        "end": str(end),
                        **cost_report,
                    }
                except Exception as exc:
                    report["checks"]["historical_cost_guard"] = {
                        "ok": False,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    }
                    report["errors"].append(f"Historical cost guard check failed: {exc}")
    else:
        report["checks"]["historical_fetch_contract"] = {
            "ok": True,
            "skipped": True,
            "reason": "historical.enabled is false",
            "timeseries_download_attempted": False,
            "guarded_operation": "timeseries.get_range",
        }
        report["checks"]["historical_cost_guard"] = {"ok": True, "skipped": True, "reason": "historical.enabled is false"}

    if report["errors"]:
        raise RuntimeError("Databento metadata check failed: " + "; ".join(report["errors"]))
    report["ok"] = True
    return report


def run_readiness_check(engine: SignalEngine, metadata_client: Any | None = None) -> dict[str, Any]:
    metadata_report = check_databento_metadata(engine, client=metadata_client)
    data_plan_report = readiness_data_plan_report(engine)
    live_metadata_preflight_report = readiness_live_metadata_preflight_report(engine)
    live_safety_stop_report = readiness_live_safety_stop_report(engine)
    process_lock_report = readiness_process_lock_report(engine)
    output_path_report = readiness_output_path_report(engine)
    output_sink_safety_report = readiness_output_sink_safety_report(engine)
    operator_sound_report = readiness_operator_sound_report(engine)
    execution_intent_contract_report = readiness_execution_intent_contract_report(engine)
    if not bool(execution_intent_contract_report.get("ok", False)):
        raise RuntimeError("Readiness execution-intent contract check failed.")
    seed_bars = load_historical_seed_cache_for_readiness(engine)
    readiness_store_count_start = len(engine.store.bars())
    readiness_source_filter_drops_start = engine.source_contract_filter_drops
    readiness_source_quality_drops_start = engine.source_bar_quality_drops
    if seed_bars:
        engine.seed(seed_bars, source="readiness_cache")
    else:
        engine.audit_runtime_warmup(source="readiness_check")
    readiness_store_count_end = len(engine.store.bars())
    accepted_readiness_seed_bars = max(0, readiness_store_count_end - readiness_store_count_start)
    source_contract_filter_readiness_drops = max(
        0,
        engine.source_contract_filter_drops - readiness_source_filter_drops_start,
    )
    source_bar_quality_readiness_drops = max(
        0,
        engine.source_bar_quality_drops - readiness_source_quality_drops_start,
    )
    source_contract_filter_starved = (
        bool(seed_bars)
        and accepted_readiness_seed_bars <= 0
        and source_contract_filter_readiness_drops >= len(seed_bars)
    )
    if source_contract_filter_starved:
        print_json(
            {
                "event": "readiness_source_contract_filter_starved",
                "historical_seed_bars": len(seed_bars),
                "accepted_seed_bars": accepted_readiness_seed_bars,
                "source_contract_filter_drops": source_contract_filter_readiness_drops,
                "source_contract_filter": engine.source_contract_filter_report(),
                "source_bar_quality": engine.source_bar_quality_report(),
                "reason": (
                    "The historical readiness cache loaded, but every seed bar was rejected by "
                    "databento.contract_symbol_regex."
                ),
                "impact": (
                    "No cached bars reached strategy warmup/evaluation; live mode would likely appear idle "
                    "or unevaluable until matching contract symbols arrive."
                ),
            },
            prefix="SYSTEM_ALERT",
        )
        raise RuntimeError(
            "Readiness check failed: historical cache bars were all rejected by databento.contract_symbol_regex."
        )

    strategy_health = engine.strategy_health_report()
    disabled = [item for item in strategy_health if item.get("disabled")]
    active_count = sum(1 for item in strategy_health if not item.get("disabled"))
    if active_count <= 0:
        raise RuntimeError("Readiness check failed: no active strategies remain after warmup.")
    if disabled:
        raise RuntimeError("Readiness check failed: one or more strategies are disabled.")
    unevaluable = [
        item
        for item in strategy_health
        if not item.get("disabled") and int(item.get("evaluated_strategy_row_count", 0) or 0) <= 0
    ]
    if seed_bars and unevaluable:
        ids = ", ".join(str(item.get("strategy_id")) for item in unevaluable)
        raise RuntimeError(
            "Readiness check failed: active strategy did not evaluate any complete feature rows "
            f"from the historical cache: {ids}"
        )

    cost_guard = metadata_report.get("checks", {}).get("historical_cost_guard", {})
    sessions = count_bar_sessions(seed_bars, engine.timezone) if seed_bars else 0
    readiness_strategy_health = [
        {
            "strategy_id": item.get("strategy_id"),
            "strategy_name": item.get("strategy_name"),
            "disabled": bool(item.get("disabled")),
            "processed_strategy_row_count": int(item.get("processed_strategy_row_count", 0) or 0),
            "evaluated_strategy_row_count": int(item.get("evaluated_strategy_row_count", 0) or 0),
            "last_evaluated_strategy_timestamp": item.get("last_evaluated_strategy_timestamp"),
            "feature_quality_skip_count": int(item.get("feature_quality_skip_count", 0) or 0),
            "runtime_error_count": int(item.get("runtime_error_count", 0) or 0),
        }
        for item in strategy_health
    ]
    degraded_reasons: list[str] = []
    if not bool(data_plan_report.get("ok", False)):
        degraded_reasons.append("strategy data plan has warnings")
    if not bool(live_metadata_preflight_report.get("ok", False)):
        degraded_reasons.append("live metadata preflight guard is not enabled")
    if not bool(live_safety_stop_report.get("ok", False)):
        degraded_reasons.append("live safety stops are not fail-closed")
    if not bool(process_lock_report.get("ok", False)):
        degraded_reasons.append("runtime process lock is not ready")
    if not bool(output_path_report.get("ok", False)):
        degraded_reasons.append("one or more configured alert/outbox output paths are not writable")
    if not bool(output_sink_safety_report.get("ok", False)):
        degraded_reasons.append("configured alert/outbox sinks are not fail-closed")
    if not bool(operator_sound_report.get("ok", False)):
        degraded_reasons.append("operator sound alerting is not ready")
    if source_bar_quality_readiness_drops > 0:
        degraded_reasons.append("historical seed bars were dropped by source-bar quality checks")
    readiness_ok = not degraded_reasons
    payload = {
        "event": "readiness_check_ok" if readiness_ok else "readiness_check_degraded",
        "ok": readiness_ok,
        "degraded_reasons": degraded_reasons,
        "databento": {
            "metadata_ok": bool(metadata_report.get("ok", False)),
            "dataset": metadata_report.get("dataset"),
            "schema": metadata_report.get("schema"),
            "symbols": metadata_report.get("symbols"),
            "api_key": metadata_report.get("api_key", {}),
            "live_cost_guard": metadata_report.get("checks", {}).get("live_cost_guard", {}),
            "live_metadata_preflight_readiness": live_metadata_preflight_report,
            "live_safety_stops": live_safety_stop_config(engine.databento_config.get("live", {})),
            "live_safety_stop_readiness": live_safety_stop_report,
            "operation_mode": metadata_report.get("operation_mode"),
            "metadata_only": bool(metadata_report.get("metadata_only", False)),
            "metadata_operations_attempted": metadata_report.get("metadata_operations_attempted", []),
            "databento_api_audit": metadata_report.get("databento_api_audit", {}),
            "timeseries_download_attempted": bool(metadata_report.get("timeseries_download_attempted", False)),
            "live_subscription_attempted": bool(metadata_report.get("live_subscription_attempted", False)),
            "historical_cost_guard_ok": bool(cost_guard.get("ok", True)),
            "estimated_cost_usd": cost_guard.get("estimated_cost_usd"),
            "allow_paid_downloads": cost_guard.get("allow_paid_downloads"),
        },
        "data_plan": data_plan_report,
        "historical_seed": {
            "enabled": bool(engine.databento_config.get("historical", {}).get("enabled", True)),
            "source_bars": len(seed_bars),
            "accepted_source_bars": accepted_readiness_seed_bars,
            "source_contract_filter_drops": source_contract_filter_readiness_drops,
            "source_contract_filter_starved": source_contract_filter_starved,
            "source_bar_quality_drops": source_bar_quality_readiness_drops,
            "source_bar_quality": engine.source_bar_quality_report(),
            "sessions": sessions,
            "required_sessions": int(engine.data_plan.get("warmup", {}).get("min_warmup_sessions", 0) or 0),
            "recommended_source_bars": int(
                engine.data_plan.get("warmup", {}).get("recommended_source_bars", 0) or 0
            ),
        },
        "strategies": {
            "active": active_count,
            "disabled": len(disabled),
            "runtime_errors": sum(int(item.get("runtime_error_count", 0) or 0) for item in strategy_health),
            "feature_quality_skips": sum(int(item.get("feature_quality_skip_count", 0) or 0) for item in strategy_health),
            "evaluated_strategy_rows": sum(
                int(item.get("evaluated_strategy_row_count", 0) or 0) for item in strategy_health
            ),
            "per_strategy": readiness_strategy_health,
        },
        "alerts": {
            "dry_run_alerts": bool(engine.dry_run_alerts),
            "entry_alerts_emitted": engine.alert_count,
            "trade_setups_emitted": engine.setup_notice_count,
            "alert_file_writes": engine.alert_sink.writes_succeeded,
            "setup_alert_writes": engine.setup_notice_sink.writes_succeeded,
            "execution_intent_writes": engine.execution_intent_sink.writes_succeeded,
            "execution_intent_freshness_skips": engine.execution_intent_sink.freshness_skipped,
            "execution_intent_contract": execution_intent_contract_report,
            "output_paths": output_path_report,
            "output_sink_safety": output_sink_safety_report,
        },
        "operator": {
            "sound": operator_sound_report,
        },
        "process_lock": process_lock_report,
    }
    print_json(payload)
    return payload


def readiness_data_plan_report(engine: SignalEngine) -> dict[str, Any]:
    plan = copy.deepcopy(engine.data_plan)
    warnings = [str(item) for item in plan.get("warnings", [])]
    required_groups = source_frame_required_column_groups(plan.get("source_columns", []))
    report = {
        "checked": True,
        "ok": not warnings,
        "configured_schema": plan.get("configured_schema"),
        "required_live_schema": plan.get("required_live_schema"),
        "required_live_field_groups": plan.get("required_live_field_groups", []),
        "delta_method": plan.get("delta_method"),
        "feature_families": plan.get("feature_families", []),
        "source_columns": plan.get("source_columns", []),
        "required_source_column_groups": required_groups,
        "derived_feature_columns": plan.get("derived_feature_columns", []),
        "large_trade_sizes": plan.get("large_trade_sizes", []),
        "warmup": plan.get("warmup", {}),
        "strategy_count": len(plan.get("strategies", []) or []),
        "warnings": warnings,
    }
    if warnings:
        print_json({"event": "readiness_data_plan_degraded", **report}, prefix="SYSTEM_ALERT")
    else:
        print_json({"event": "readiness_data_plan_ok", **report})
    return report


def readiness_live_metadata_preflight_report(engine: SignalEngine) -> dict[str, Any]:
    live_cfg = dict(engine.databento_config.get("live", {}))
    live_enabled = bool(live_cfg.get("enabled", False))
    base_report = {
        "checked": live_enabled,
        "ok": True,
        "live_enabled": live_enabled,
        "required": live_enabled,
        "metadata_preflight": bool(live_cfg.get("metadata_preflight", True)),
        "allow_live_without_metadata_preflight": bool(
            live_cfg.get("allow_live_without_metadata_preflight", False)
        ),
        "reason": "live mode is disabled",
    }
    if not live_enabled:
        return base_report

    report = {**base_report, **live_metadata_preflight_guard_report(live_cfg), "checked": True}
    if bool(report.get("ok", False)):
        if bool(report.get("metadata_preflight", True)):
            print_json({"event": "readiness_live_metadata_preflight_ok", **report})
        else:
            print_json(
                {
                    "event": "readiness_live_metadata_preflight_bypassed",
                    **report,
                    "impact": (
                        "Readiness accepted an explicit diagnostic bypass; live startup will skip "
                        "Databento metadata/schema/field/symbology checks."
                    ),
                },
                prefix="SYSTEM_ALERT",
            )
        return report

    print_json(
        {
            "event": "readiness_live_metadata_preflight_failed",
            **report,
            "impact": (
                "Live startup would fail before subscription because metadata_preflight is disabled "
                "without an explicit diagnostic bypass."
            ),
        },
        prefix="SYSTEM_ALERT",
    )
    return report


def readiness_live_safety_stop_report(engine: SignalEngine) -> dict[str, Any]:
    live_cfg = engine.databento_config.get("live", {})
    report: dict[str, Any] = {
        "checked": False,
        "ok": True,
        "required": False,
        "reason": None,
        "safety_stops": {},
        "disabled_required_stops": [],
    }
    if is_missing_or_blank(live_cfg):
        report["reason"] = "databento.live config is missing or blank"
        return report
    if not isinstance(live_cfg, dict):
        report["ok"] = False
        report["reason"] = "databento.live config is not a mapping"
        print_json({"event": "readiness_live_safety_stops_failed", **report}, prefix="SYSTEM_ALERT")
        return report

    required = bool(live_cfg.get("require_fail_closed_safety_stops", True))
    stops = live_safety_stop_config(live_cfg)
    disabled = [key for key in LIVE_SAFETY_STOP_DEFAULTS if not bool(stops.get(key, False))]
    report.update(
        {
            "checked": True,
            "required": required,
            "safety_stops": stops,
            "disabled_required_stops": disabled if required else [],
        }
    )
    if not required:
        report["reason"] = "require_fail_closed_safety_stops is false"
        print_json({"event": "readiness_live_safety_stops_skipped", **report})
        return report
    if disabled:
        report["ok"] = False
        report["reason"] = "one or more required live safety stops are disabled"
        print_json({"event": "readiness_live_safety_stops_failed", **report}, prefix="SYSTEM_ALERT")
        return report
    report["reason"] = "all required live safety stops are fail-closed"
    print_json({"event": "readiness_live_safety_stops_ok", **report})
    return report


def readiness_process_lock_report(engine: SignalEngine) -> dict[str, Any]:
    enabled = bool(engine.process_lock_config.get("enabled", False))
    path = engine.process_lock_path
    fail_if_locked = bool(engine.process_lock_config.get("fail_if_locked", True))
    stale_after_seconds = float(engine.process_lock_config.get("stale_after_seconds", 86400.0))
    report: dict[str, Any] = {
        "enabled": enabled,
        "checked": False,
        "ok": True,
        "path": str(path) if path else None,
        "fail_if_locked": fail_if_locked,
        "stale_after_seconds": stale_after_seconds,
        "status": None,
        "reason": None,
        "existing_lock": None,
        "probe_file_created": False,
        "error_type": None,
        "error": None,
    }
    if not enabled:
        report["reason"] = "process_lock disabled"
        return report
    report["checked"] = True
    if path is None:
        report.update(
            {
                "ok": False,
                "status": "missing_path",
                "reason": "engine.process_lock.enabled is true but no lock path is configured",
                "error_type": "ConfigError",
                "error": "process_lock.path is required",
            }
        )
        print_json({"event": "readiness_process_lock_failed", **report}, prefix="SYSTEM_ALERT")
        return report

    if path.exists():
        existing = read_process_lock_file(path)
        stale = is_process_lock_stale(path, existing, stale_after_seconds=stale_after_seconds)
        report["existing_lock"] = existing
        report["status"] = "stale_replaceable" if stale else "active_lock_present"
        if stale:
            report["reason"] = "existing process lock is stale and would be replaced at startup"
            print_json({"event": "readiness_process_lock_stale", **report}, prefix="SYSTEM_ALERT")
            return report
        if fail_if_locked:
            report.update(
                {
                    "ok": False,
                    "reason": "active process lock would block live/replay startup",
                    "error_type": "ProcessLockHeld",
                    "error": f"process lock is already held at {path}",
                }
            )
            print_json({"event": "readiness_process_lock_failed", **report}, prefix="SYSTEM_ALERT")
            return report
        report["reason"] = "active process lock exists, but fail_if_locked is false"
        print_json({"event": "readiness_process_lock_ok", **report})
        return report

    probe_path = path.parent / f".{path.name}.readiness_probe.{os.getpid()}.{time.time_ns()}"
    fd = -1
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(probe_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("")
        finally:
            fd = -1
        report["probe_file_created"] = True
        probe_path.unlink()
        report["status"] = "available"
        report["reason"] = "process lock path is available and parent directory accepted a write probe"
        print_json({"event": "readiness_process_lock_ok", **report})
        return report
    except Exception as exc:
        if fd != -1:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            if probe_path.exists():
                probe_path.unlink()
        except OSError:
            pass
        report.update(
            {
                "ok": False,
                "status": "write_probe_failed",
                "reason": "process lock parent directory did not accept a write probe",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        print_json({"event": "readiness_process_lock_failed", **report}, prefix="SYSTEM_ALERT")
        return report


def readiness_execution_intent_contract_report(engine: SignalEngine) -> dict[str, Any]:
    enabled = bool(engine.execution_intents_config.get("enabled", False))
    active_strategies = [strategy for strategy in engine.strategies if not strategy.disabled]
    report: dict[str, Any] = {
        "enabled": enabled,
        "checked": False,
        "ok": True,
        "probe_mode": "strategy_runtime_build_alert",
        "record_schema_version": EXECUTION_INTENT_RECORD_VERSION,
        "intent_schema_version": EXECUTION_INTENT_VERSION,
        "alert_contract_version": ALERT_CONTRACT_VERSION,
        "strategies_checked": 0,
        "probes_checked": 0,
        "strategies": [],
        "errors": [],
        "reason": None,
    }
    if not enabled:
        report["reason"] = "execution_intents.enabled is false"
        return report
    report["checked"] = True
    if not active_strategies:
        report["ok"] = False
        report["reason"] = "no active strategies available for execution-intent contract probe"

    now_utc = normalize_utc_timestamp(pd.Timestamp.utcnow())
    for strategy in active_strategies:
        strategy_report = {
            "strategy_id": strategy.strategy_id,
            "strategy_name": strategy.variant_config.get("strategy_name", getattr(strategy.strategy, "name", None)),
            "strategy_config": strategy.strategy_config_label,
            "directions_checked": [],
            "ok": True,
            "errors": [],
        }
        for direction in ("long", "short"):
            try:
                alert = build_readiness_execution_intent_probe_alert(
                    engine,
                    strategy,
                    direction=direction,
                    entry_utc=now_utc,
                )
                validate_entry_alert_contract(alert)
                record = build_execution_intent_record(alert)
                validate_execution_intent_record(record, alert)
                validate_execution_intent_ready_record(record)
                actionability = execution_intent_record_actionability_report(record, now_utc=now_utc)
                if not bool(actionability.get("actionable", False)):
                    raise ValueError(f"execution intent probe is not actionable: {actionability}")
                strategy_report["directions_checked"].append(direction)
                report["probes_checked"] += 1
            except Exception as exc:  # noqa: BLE001 - readiness report must capture the exact contract failure.
                report["ok"] = False
                strategy_report["ok"] = False
                error = {
                    "strategy_id": strategy.strategy_id,
                    "direction": direction,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                strategy_report["errors"].append(error)
                report["errors"].append(error)
        report["strategies"].append(strategy_report)

    report["strategies_checked"] = len(active_strategies)
    if report["ok"]:
        report["reason"] = "execution-intent alert and outbox contracts validated for active strategies"
        print_json({"event": "readiness_execution_intent_contract_ok", **report})
    else:
        if report["reason"] is None:
            report["reason"] = "one or more execution-intent contract probes failed"
        print_json({"event": "readiness_execution_intent_contract_failed", **report}, prefix="SYSTEM_ALERT")
    return report


def build_readiness_execution_intent_probe_alert(
    engine: SignalEngine,
    strategy: StrategyRuntime,
    *,
    direction: str,
    entry_utc: Any,
) -> dict[str, Any]:
    normalized_direction = str(direction).lower()
    if normalized_direction not in {"long", "short"}:
        raise ValueError("readiness execution-intent probe direction must be long or short")
    core = dict(strategy.variant_config.get("core") or {})
    tick_size = config_float(core, "tick_size", 0.25, min_value=0.0000001)
    entry_timestamp_utc = normalize_utc_timestamp(entry_utc)
    signal_timestamp_utc = entry_timestamp_utc - pd.Timedelta(minutes=max(1, strategy.timeframe_minutes))
    entry_basis_price = round_to_tick(5000.0, tick_size)
    slippage_ticks = float(engine.account.get("slippage_ticks", core.get("slippage_ticks", 0.0)))
    expected_entry_price = round_to_tick(
        estimated_market_entry(entry_basis_price, normalized_direction, tick_size, slippage_ticks),
        tick_size,
    )
    contract_symbol = readiness_probe_contract_symbol(engine, strategy)
    signal_obj = build_readiness_probe_signal(
        strategy,
        direction=normalized_direction,
        entry_price=expected_entry_price,
        tick_size=tick_size,
    )
    pending_signal_key = alert_hash(
        "readiness_pending_signal_probe",
        strategy.strategy_id,
        normalized_direction,
        str(engine.engine_config_fingerprint.get("sha256")),
    )
    row = build_readiness_probe_row(
        strategy,
        signal_timestamp_utc=signal_timestamp_utc,
        entry_basis_price=entry_basis_price,
        contract_symbol=contract_symbol,
        signal_obj=signal_obj,
    )
    pending = PendingSignal(
        strategy=strategy,
        row=row,
        signal_obj=signal_obj,
        due_utc=entry_timestamp_utc,
        queued_at_utc=entry_timestamp_utc,
        key=pending_signal_key,
    )
    tick = TradeTick(
        timestamp_utc=entry_timestamp_utc,
        price=entry_basis_price,
        size=1.0,
        side="B" if normalized_direction == "long" else "A",
        contract_symbol=contract_symbol,
    )
    trades_by_session_before = copy.deepcopy(strategy.trades_by_session)
    sent_signal_keys_before = set(strategy.sent_signal_keys)
    try:
        alert = strategy.build_alert(pending, tick, copy.deepcopy(engine.account))
    finally:
        strategy.trades_by_session = trades_by_session_before
        strategy.sent_signal_keys = sent_signal_keys_before
    if alert is None:
        raise ValueError(
            "strategy build_alert returned no alert during readiness execution-intent probe; "
            "check stop/target/sizing/trade_sanity rejection output"
        )
    return alert


def build_readiness_probe_signal(
    strategy: StrategyRuntime,
    *,
    direction: str,
    entry_price: float,
    tick_size: float,
) -> ReadinessProbeSignal:
    distance = max(tick_size, round_to_tick(max(1.0, tick_size), tick_size))
    low = round_to_tick(float(entry_price) - distance, tick_size)
    high = round_to_tick(float(entry_price) + distance, tick_size)
    width = max(tick_size, round_to_tick(high - low, tick_size))
    metadata = {
        "probe": True,
        "strategy_id": strategy.strategy_id,
        "contract": "execution_intent_ready",
        "latest_completed_bar_low": low,
        "latest_completed_bar_high": high,
        "opening_range_low": low,
        "opening_range_high": high,
        "opening_range_width": width,
        "confirmation_close": float(entry_price),
        "prev_rth_close": round_to_tick(high + distance, tick_size)
        if direction == "long"
        else round_to_tick(low - distance, tick_size),
        "stop_points": distance,
    }
    strategy_config = strategy.variant_config.get("strategy")
    strategy_config = strategy_config if isinstance(strategy_config, dict) else {}
    entry_config = strategy_config.get("entry")
    entry_config = entry_config if isinstance(entry_config, dict) else {}
    entry_params = entry_config.get("params")
    entry_params = entry_params if isinstance(entry_params, dict) else {}
    sl_config = strategy_config.get("sl")
    sl_config = sl_config if isinstance(sl_config, dict) else {}
    sl_params = sl_config.get("params")
    sl_params = sl_params if isinstance(sl_params, dict) else {}
    tp_config = strategy_config.get("tp")
    tp_config = tp_config if isinstance(tp_config, dict) else {}
    tp_params = tp_config.get("params")
    tp_params = tp_params if isinstance(tp_params, dict) else {}
    sl_metadata_key = str(sl_params.get("metadata_key", "stop_pct"))
    tp_metadata_key = str(tp_params.get("metadata_key", "target_r_multiple"))
    if "stop_pct" in entry_params:
        metadata[sl_metadata_key] = entry_params["stop_pct"]
    if "target_r_multiple" in entry_params:
        metadata[tp_metadata_key] = entry_params["target_r_multiple"]
    report_fields = {
        "probe": True,
        "entry_price_context": float(entry_price),
        "sweep_low": low,
        "sweep_high": high,
        "opening_range_low": low,
        "opening_range_high": high,
        "opening_range_width": width,
        "prev_rth_close": metadata["prev_rth_close"],
    }
    swept_level = low if direction == "long" else high
    return ReadinessProbeSignal(
        direction=direction,
        level_type="readiness_execution_intent_probe",
        swept_level=swept_level,
        metadata=metadata,
        report_fields=report_fields,
        sweep_low=low,
        sweep_high=high,
        opening_range_low=low,
        opening_range_high=high,
        opening_range_width=width,
        prev_rth_close=float(metadata["prev_rth_close"]),
    )


def build_readiness_probe_row(
    strategy: StrategyRuntime,
    *,
    signal_timestamp_utc: Any,
    entry_basis_price: float,
    contract_symbol: str,
    signal_obj: ReadinessProbeSignal,
) -> dict[str, Any]:
    timestamp_utc = normalize_utc_timestamp(signal_timestamp_utc)
    timestamp_local = timestamp_utc.tz_convert(strategy.timezone)
    low = finite_float(signal_obj.metadata.get("latest_completed_bar_low"))
    high = finite_float(signal_obj.metadata.get("latest_completed_bar_high"))
    if low is None:
        low = float(entry_basis_price)
    if high is None:
        high = float(entry_basis_price)
    signed_volume = 25.0 if signal_obj.direction == "long" else -25.0
    buy_volume = 75.0 if signal_obj.direction == "long" else 25.0
    sell_volume = 25.0 if signal_obj.direction == "long" else 75.0
    return {
        "timestamp": timestamp_local,
        "timestamp_utc": timestamp_utc,
        "session_date": local_session_date(timestamp_utc, strategy.timezone),
        "symbol": strategy.symbol,
        "contract_symbol": contract_symbol,
        "open": float(entry_basis_price),
        "high": float(max(high, entry_basis_price)),
        "low": float(min(low, entry_basis_price)),
        "close": float(entry_basis_price),
        "volume": 100.0,
        "signed_volume": signed_volume,
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "trades": 10,
        "source": "readiness_execution_intent_probe",
    }


def readiness_probe_contract_symbol(engine: SignalEngine, strategy: StrategyRuntime | None = None) -> str:
    root = str((strategy.symbol if strategy is not None else engine.symbol) or DEFAULT_SYMBOL).strip().upper()
    root = root or DEFAULT_SYMBOL
    candidates = [f"{root}M6", f"{root}U6", root]
    pattern = re.compile(engine.contract_symbol_regex) if engine.contract_symbol_regex else None
    if pattern is None:
        return candidates[0]
    for candidate in candidates:
        if pattern.match(candidate):
            return candidate
    return candidates[0]


def readiness_operator_sound_report(engine: SignalEngine) -> dict[str, Any]:
    sound = dict(engine.operator_config.get("sound", {}))
    report: dict[str, Any] = {
        "enabled": bool(sound.get("enabled", False)),
        "ok": True,
        "dry_run_alerts": bool(engine.dry_run_alerts),
        "bell": bool(sound.get("bell", True)),
        "max_active_commands": config_int(
            sound,
            "max_active_commands",
            DEFAULT_OPERATOR_SOUND_MAX_ACTIVE_COMMANDS,
            min_value=0,
        ),
        "checks": [],
    }
    if engine.dry_run_alerts:
        report["checks"] = [
            skipped_operator_sound_readiness_check(kind, reason="dry_run_alerts is enabled")
            for kind in ("setup", "entry", "system")
        ]
        return report
    if not bool(sound.get("enabled", False)):
        report["checks"] = [
            skipped_operator_sound_readiness_check(kind, reason="operator sound is disabled")
            for kind in ("setup", "entry", "system")
        ]
        return report

    checks = []
    max_active_commands = config_int(
        sound,
        "max_active_commands",
        DEFAULT_OPERATOR_SOUND_MAX_ACTIVE_COMMANDS,
        min_value=0,
    )
    for kind in ("setup", "entry", "system"):
        if not bool(sound.get(f"on_{kind}", True)):
            checks.append(skipped_operator_sound_readiness_check(kind, reason=f"operator sound for {kind} is disabled"))
            continue
        command = sound.get(f"{kind}_command") or sound.get("command")
        checks.append(
            operator_sound_readiness_check(
                kind,
                command=command,
                bell=bool(sound.get("bell", True)),
                max_active_commands=max_active_commands,
            )
        )
    report["checks"] = checks
    failed = [item for item in checks if not bool(item.get("ok", False))]
    if failed:
        report["ok"] = False
        print_json(
            {
                "event": "readiness_operator_sound_check_failed",
                "checks": checks,
                "reason": "One or more configured operator sound alerts are not ready.",
                "impact": "The engine can still print alerts, but the manual-trading sound cue may be missing.",
            },
            prefix="SYSTEM_ALERT",
        )
        return report
    print_json({"event": "readiness_operator_sound_ok", "checks": checks})
    return report


def skipped_operator_sound_readiness_check(kind: str, *, reason: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "configured": False,
        "checked": False,
        "ok": True,
        "bell": None,
        "max_active_commands": None,
        "command": None,
        "executable": None,
        "resolved_executable": None,
        "reason": reason,
        "error_type": None,
        "error": None,
    }


def operator_sound_readiness_check(
    kind: str,
    *,
    command: Any,
    bell: bool,
    max_active_commands: int,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "kind": kind,
        "configured": True,
        "checked": True,
        "ok": True,
        "bell": bool(bell),
        "max_active_commands": int(max_active_commands),
        "command": str(command) if command else None,
        "executable": None,
        "resolved_executable": None,
        "reason": None,
        "error_type": None,
        "error": None,
    }
    if not command:
        if bell:
            report["reason"] = "terminal bell is enabled"
            return report
        report.update(
            {
                "ok": False,
                "reason": "no terminal bell or sound command is configured",
                "error_type": "ConfigError",
                "error": "operator.sound.bell is false and no command is configured",
            }
        )
        return report

    if max_active_commands <= 0 and not bell:
        report.update(
            {
                "ok": False,
                "reason": "external sound commands are disabled and terminal bell is disabled",
                "error_type": "ConfigError",
                "error": "operator.sound.max_active_commands is 0 and operator.sound.bell is false",
            }
        )
        return report

    try:
        parts = shlex.split(str(command))
    except Exception as exc:
        report.update(
            {
                "ok": False,
                "reason": "sound command could not be parsed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        return report
    if not parts:
        report.update(
            {
                "ok": False,
                "reason": "sound command is empty",
                "error_type": "ConfigError",
                "error": "empty operator sound command",
            }
        )
        return report

    executable = parts[0]
    report["executable"] = executable
    if "/" in executable:
        executable_path = Path(executable).expanduser()
        report["resolved_executable"] = str(executable_path)
        if not executable_path.exists():
            report.update(
                {
                    "ok": False,
                    "reason": "sound command executable does not exist",
                    "error_type": "FileNotFoundError",
                    "error": str(executable_path),
                }
            )
            return report
        if not executable_path.is_file() or not os.access(executable_path, os.X_OK):
            report.update(
                {
                    "ok": False,
                    "reason": "sound command executable is not executable",
                    "error_type": "PermissionError",
                    "error": str(executable_path),
                }
            )
            return report
        report["reason"] = "sound command executable is available"
        return report

    resolved = shutil.which(executable)
    report["resolved_executable"] = resolved
    if resolved is None:
        report.update(
            {
                "ok": False,
                "reason": "sound command executable was not found on PATH",
                "error_type": "FileNotFoundError",
                "error": executable,
            }
        )
        return report
    report["reason"] = "sound command executable is available"
    return report


def readiness_output_path_report(engine: SignalEngine) -> dict[str, Any]:
    config = engine.output_path_readiness_config
    targets = [
        ("entry_alerts", engine.alerts_path, engine.alerts_path is not None),
        ("setup_alerts", engine.setup_alerts_path, bool(engine.setup_alerts_config.get("enabled", False))),
        (
            "execution_intents",
            engine.execution_intents_path,
            bool(engine.execution_intents_config.get("enabled", False)),
        ),
    ]
    report = {
        "enabled": bool(config.get("enabled", True)),
        "ok": True,
        "dry_run_alerts": bool(engine.dry_run_alerts),
        "create_parent_dirs": bool(config.get("create_parent_dirs", True)),
        "checks": [],
    }
    if not bool(config.get("enabled", True)):
        report["checks"] = [
            skipped_output_path_readiness_check(label, path, configured, reason="output_path_readiness disabled")
            for label, path, configured in targets
        ]
        return report

    checks = [
        output_path_readiness_check(
            label,
            path,
            configured=configured,
            dry_run_alerts=engine.dry_run_alerts,
            create_parent_dirs=bool(config.get("create_parent_dirs", True)),
        )
        for label, path, configured in targets
    ]
    report["checks"] = checks

    failed = [item for item in checks if not bool(item.get("ok", False))]
    if failed:
        report["ok"] = False
        payload = {
            "event": "readiness_output_path_check_failed",
            "checks": checks,
            "reason": "One or more configured alert/outbox paths are not writable before live start.",
            "impact": (
                "The engine can print manual alerts to stdout, but durable alert or automation outbox "
                "records may be missing if live mode starts with these paths."
            ),
        }
        print_json(payload, prefix="SYSTEM_ALERT")
        if bool(config.get("fail_on_error", True)):
            labels = ", ".join(str(item.get("label")) for item in failed)
            raise RuntimeError(f"Readiness output path check failed: {labels}")
        return report

    print_json({"event": "readiness_output_paths_ok", "checks": checks})
    return report


def output_sink_safety_report(engine: SignalEngine) -> dict[str, Any]:
    config = engine.output_path_readiness_config
    required = bool(config.get("require_fail_closed_sinks", False))
    report: dict[str, Any] = {
        "ok": True,
        "required": required,
        "checked": False,
        "dry_run_alerts": bool(engine.dry_run_alerts),
        "checks": [],
        "failed_checks": [],
        "reason": None,
    }
    if not required:
        report["reason"] = "require_fail_closed_sinks is false"
        return report
    if engine.dry_run_alerts:
        report["reason"] = "dry_run_alerts is enabled"
        return report

    checks: list[dict[str, Any]] = []

    def add_check(
        label: str,
        *,
        ok: bool,
        sink: str,
        expected: Any,
        actual: Any,
        reason: str,
    ) -> None:
        checks.append(
            {
                "label": label,
                "sink": sink,
                "ok": bool(ok),
                "expected": expected,
                "actual": actual,
                "reason": reason,
            }
        )

    add_check(
        "entry_alerts.path_configured",
        sink="entry_alerts",
        ok=engine.alerts_path is not None,
        expected="configured JSONL file path",
        actual=str(engine.alerts_path) if engine.alerts_path is not None else None,
        reason="durable entry-alert JSONL output must be configured",
    )
    add_check(
        "entry_alerts.fail_on_write_error",
        sink="entry_alerts",
        ok=bool(engine.alert_file_config.get("fail_on_write_error", False)),
        expected=True,
        actual=bool(engine.alert_file_config.get("fail_on_write_error", False)),
        reason="entry-alert write failures must stop the engine instead of only printing to stdout",
    )
    add_check(
        "entry_alerts.suppress_duplicate_alert_ids",
        sink="entry_alerts",
        ok=bool(engine.alert_file_config.get("suppress_duplicate_alert_ids", False)),
        expected=True,
        actual=bool(engine.alert_file_config.get("suppress_duplicate_alert_ids", False)),
        reason="duplicate entry alerts must be suppressed by alert_id",
    )

    setup_enabled = bool(engine.setup_alerts_config.get("enabled", False))
    if setup_enabled:
        add_check(
            "setup_alerts.path_configured",
            sink="setup_alerts",
            ok=engine.setup_alerts_path is not None,
            expected="configured JSONL file path",
            actual=str(engine.setup_alerts_path) if engine.setup_alerts_path is not None else None,
            reason="enabled setup-alert JSONL output must be configured",
        )
        add_check(
            "setup_alerts.fail_on_write_error",
            sink="setup_alerts",
            ok=bool(engine.setup_alerts_config.get("fail_on_write_error", False)),
            expected=True,
            actual=bool(engine.setup_alerts_config.get("fail_on_write_error", False)),
            reason="setup-alert write failures must stop the engine instead of only printing to stdout",
        )
        add_check(
            "setup_alerts.suppress_duplicate_setup_ids",
            sink="setup_alerts",
            ok=bool(engine.setup_alerts_config.get("suppress_duplicate_setup_ids", True)),
            expected=True,
            actual=bool(engine.setup_alerts_config.get("suppress_duplicate_setup_ids", True)),
            reason="duplicate setup notices must be suppressed by setup_id",
        )
    else:
        add_check(
            "setup_alerts.enabled",
            sink="setup_alerts",
            ok=True,
            expected="optional",
            actual=False,
            reason="setup-alert sink is disabled",
        )

    intents_enabled = bool(engine.execution_intents_config.get("enabled", False))
    if intents_enabled:
        add_check(
            "execution_intents.path_configured",
            sink="execution_intents",
            ok=engine.execution_intents_path is not None,
            expected="configured JSONL file path",
            actual=str(engine.execution_intents_path) if engine.execution_intents_path is not None else None,
            reason="enabled execution-intent JSONL output must be configured",
        )
        add_check(
            "execution_intents.fail_on_write_error",
            sink="execution_intents",
            ok=bool(engine.execution_intents_config.get("fail_on_write_error", False)),
            expected=True,
            actual=bool(engine.execution_intents_config.get("fail_on_write_error", False)),
            reason="router-facing execution-intent write failures must stop the engine",
        )
        add_check(
            "execution_intents.suppress_duplicate_alert_ids",
            sink="execution_intents",
            ok=bool(engine.execution_intents_config.get("suppress_duplicate_alert_ids", True)),
            expected=True,
            actual=bool(engine.execution_intents_config.get("suppress_duplicate_alert_ids", True)),
            reason="duplicate router intents must be suppressed by alert_id",
        )
        add_check(
            "execution_intents.suppress_duplicate_setup_ids",
            sink="execution_intents",
            ok=bool(engine.execution_intents_config.get("suppress_duplicate_setup_ids", True)),
            expected=True,
            actual=bool(engine.execution_intents_config.get("suppress_duplicate_setup_ids", True)),
            reason="duplicate router intents must be suppressed by setup_id",
        )
        enforce_freshness = bool(engine.execution_intents_config.get("enforce_freshness", True))
        add_check(
            "execution_intents.fail_on_freshness_error",
            sink="execution_intents",
            ok=(not enforce_freshness)
            or bool(engine.execution_intents_config.get("fail_on_freshness_error", False)),
            expected=True if enforce_freshness else "not required when enforce_freshness is false",
            actual=bool(engine.execution_intents_config.get("fail_on_freshness_error", False)),
            reason="freshness-gated router intents must fail closed when they are stale or non-actionable",
        )
    else:
        add_check(
            "execution_intents.enabled",
            sink="execution_intents",
            ok=True,
            expected="optional",
            actual=False,
            reason="execution-intent sink is disabled",
        )

    failed = [item for item in checks if not bool(item.get("ok", False))]
    report["checked"] = True
    report["checks"] = checks
    report["failed_checks"] = [str(item.get("label")) for item in failed]
    report["ok"] = not failed
    if failed:
        report["reason"] = "one or more alert/outbox sinks are not configured to fail closed"
    else:
        report["reason"] = "all required alert/outbox sinks are fail-closed"
    return report


def readiness_output_sink_safety_report(engine: SignalEngine) -> dict[str, Any]:
    report = output_sink_safety_report(engine)
    if not bool(report.get("required", False)):
        print_json({"event": "readiness_output_sink_safety_skipped", **report})
        return report
    if not bool(report.get("checked", False)):
        print_json({"event": "readiness_output_sink_safety_skipped", **report})
        return report
    if bool(report.get("ok", False)):
        print_json({"event": "readiness_output_sink_safety_ok", **report})
    else:
        print_json(
            {
                "event": "readiness_output_sink_safety_failed",
                **report,
                "impact": (
                    "Live mode could print a manual signal while failing to persist the durable alert "
                    "or router-facing outbox record. Update the sink configs or explicitly disable "
                    "require_fail_closed_sinks for diagnostic-only runs."
                ),
            },
            prefix="SYSTEM_ALERT",
        )
    return report


def skipped_output_path_readiness_check(
    label: str,
    path: Path | None,
    configured: bool,
    *,
    reason: str,
) -> dict[str, Any]:
    return {
        "label": label,
        "configured": bool(configured),
        "path": str(path) if path is not None else None,
        "checked": False,
        "ok": True,
        "probe_file_created": False,
        "reason": reason,
        "error_type": None,
        "error": None,
    }


def output_path_readiness_check(
    label: str,
    path: Path | None,
    *,
    configured: bool,
    dry_run_alerts: bool,
    create_parent_dirs: bool,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "label": label,
        "configured": bool(configured),
        "path": str(path) if path is not None else None,
        "checked": False,
        "ok": True,
        "probe_file_created": False,
        "reason": None,
        "error_type": None,
        "error": None,
    }
    if not configured:
        report["reason"] = "output path is disabled"
        return report
    if dry_run_alerts:
        report["reason"] = "dry_run_alerts is enabled"
        return report
    if path is None:
        report.update(
            {
                "ok": False,
                "reason": "output path is configured but resolved to null",
                "error_type": "ConfigError",
                "error": "missing output path",
            }
        )
        return report

    report["checked"] = True
    probe_path: Path | None = None
    try:
        if path.exists():
            if path.is_dir():
                raise IsADirectoryError(f"{path} is a directory, expected a JSONL file path")
            with path.open("a", encoding="utf-8"):
                pass
            report["reason"] = "existing file opened for append"
            return report

        parent = path.parent
        if create_parent_dirs:
            parent.mkdir(parents=True, exist_ok=True)
        elif not parent.exists():
            raise FileNotFoundError(f"parent directory does not exist: {parent}")
        if not parent.is_dir():
            raise NotADirectoryError(f"parent path is not a directory: {parent}")

        probe_path = parent / f".{path.name}.readiness_probe.{os.getpid()}.{time.time_ns()}.tmp"
        fd = os.open(str(probe_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("readiness_probe\n")
            handle.flush()
            os.fsync(handle.fileno())
        report["probe_file_created"] = True
        report["reason"] = "parent directory accepted a temporary write probe"
    except Exception as exc:
        report.update(
            {
                "ok": False,
                "reason": "output path write probe failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
    finally:
        if probe_path is not None:
            try:
                probe_path.unlink(missing_ok=True)
            except Exception:
                pass
    return report


def load_historical_seed_cache_for_readiness(engine: SignalEngine) -> list[SourceMinuteBar]:
    hist_cfg = dict(engine.databento_config.get("historical", {}))
    if not bool(hist_cfg.get("enabled", True)):
        return []
    source_report = historical_seed_source_report(engine, hist_cfg, refresh=False)
    if bool(source_report.get("refresh_requested", False)):
        raise RuntimeError(
            "Readiness check cannot refresh historical data. Disable historical.refresh/--refresh-historical "
            "or run seed-only after a successful cost-guard check."
        )
    cache_path = resolve_optional_path(engine.config_dir, hist_cfg.get("cache_path"))
    seed_bars_path = resolve_optional_path(engine.config_dir, hist_cfg.get("seed_bars_path"))
    if bool(source_report.get("cache_usable", False)) and cache_path is not None:
        bars = read_bars_file(
            cache_path,
            root_symbol=engine.symbol,
            timezone=engine.timezone,
            source="readiness_cache",
            required_source_columns=engine.data_plan.get("source_columns", []),
        )
        validate_historical_cache_metadata(engine, cache_path, bars, hist_cfg)
        print_json({"event": "readiness_historical_cache_loaded", "path": str(cache_path), "bars": len(bars)})
        return bars
    if bool(source_report.get("seed_file_usable", False)) and seed_bars_path is not None:
        if not seed_bars_path.exists():
            raise RuntimeError(f"Readiness check historical seed file not found: {seed_bars_path}")
        bars = read_bars_file(
            seed_bars_path,
            root_symbol=engine.symbol,
            timezone=engine.timezone,
            source="readiness_seed_file",
            required_source_columns=engine.data_plan.get("source_columns", []),
        )
        validate_historical_seed_file_metadata(engine, seed_bars_path, bars, hist_cfg)
        print_json({"event": "readiness_historical_seed_file_loaded", "path": str(seed_bars_path), "bars": len(bars)})
        return bars
    if cache_path is not None:
        raise RuntimeError(f"Readiness check historical cache not found: {cache_path}")
    raise RuntimeError(
        "Readiness check requires a local databento.historical.cache_path or seed_bars_path when historical.enabled is true."
    )


def check_databento_symbology(
    client: Any,
    *,
    dataset: str,
    symbols: Any,
    stype_in: str,
    stype_out: str,
    available_end: Any | None = None,
) -> dict[str, Any]:
    if not hasattr(client, "symbology"):
        raise RuntimeError("Databento client does not expose a symbology API.")
    start_date, end_date = symbology_check_date_window(available_end=available_end)
    raw = client.symbology.resolve(
        dataset=dataset,
        symbols=symbols,
        stype_in=stype_in,
        stype_out=stype_out,
        start_date=start_date,
        end_date=end_date,
    )
    result = raw.get("result", {}) if isinstance(raw, dict) else {}
    not_found = raw.get("not_found", []) if isinstance(raw, dict) else []
    partial = raw.get("partial", []) if isinstance(raw, dict) else []
    mapping_count = symbology_mapping_count(result)
    ok = not not_found and mapping_count > 0 and int(raw.get("status", 0) if isinstance(raw, dict) else 0) == 0
    payload = {
        "ok": ok,
        "dataset": dataset,
        "symbols": symbols,
        "stype_in": stype_in,
        "stype_out": stype_out,
        "start_date": start_date,
        "end_date": end_date,
        "result_symbol_count": len(result) if isinstance(result, dict) else 0,
        "mapping_count": mapping_count,
        "sample_mappings": sample_symbology_mappings(result),
        "not_found": not_found,
        "partial": partial,
        "status": raw.get("status") if isinstance(raw, dict) else None,
        "message": raw.get("message") if isinstance(raw, dict) else None,
    }
    if not ok:
        payload["error"] = (
            "Databento symbology did not resolve the configured symbols/stype into any usable mappings."
        )
    return payload


def resolve_live_instrument_symbol_map(
    client: Any,
    *,
    dataset: str,
    symbols: Any,
    stype_in: str,
    available_end: Any | None = None,
) -> dict[Any, str]:
    if not hasattr(client, "symbology"):
        raise RuntimeError("Databento client does not expose a symbology API.")
    start_date, end_date = symbology_check_date_window(available_end=available_end)
    normalized_stype_in = str(stype_in or "").strip().lower()
    stype_out = "raw_symbol" if normalized_stype_in == "instrument_id" else "instrument_id"
    raw = client.symbology.resolve(
        dataset=dataset,
        symbols=symbols,
        stype_in=stype_in,
        stype_out=stype_out,
        start_date=start_date,
        end_date=end_date,
    )
    result = raw.get("result", {}) if isinstance(raw, dict) else {}
    if stype_out == "raw_symbol":
        mapping = instrument_symbol_map_from_instrument_id_result(result)
    else:
        mapping = instrument_symbol_map_from_symbology_result(result)
    if not mapping:
        raise RuntimeError(
            "Databento live symbology did not resolve instrument ids to raw contract symbols."
        )
    return mapping


def instrument_symbol_map_from_symbology_result(result: Any) -> dict[Any, str]:
    mapping: dict[Any, str] = {}
    if not isinstance(result, dict):
        return mapping
    for raw_symbol, intervals in result.items():
        symbol = str(raw_symbol or "").strip()
        if not symbol or symbol.isdigit():
            continue
        items = intervals if isinstance(intervals, list) else [intervals]
        for interval in items:
            if not isinstance(interval, dict):
                continue
            instrument_id = interval.get("s") or interval.get("instrument_id") or interval.get("instrumentId")
            if instrument_id is None:
                continue
            instrument_text = str(instrument_id).strip()
            if not instrument_text:
                continue
            mapping[instrument_text] = symbol
            try:
                mapping[int(instrument_text)] = symbol
            except ValueError:
                pass
    return mapping


def instrument_symbol_map_from_instrument_id_result(result: Any) -> dict[Any, str]:
    mapping: dict[Any, str] = {}
    if not isinstance(result, dict):
        return mapping
    for instrument_id, intervals in result.items():
        instrument_text = str(instrument_id or "").strip()
        if not instrument_text:
            continue
        items = intervals if isinstance(intervals, list) else [intervals]
        for interval in items:
            if not isinstance(interval, dict):
                continue
            symbol = extract_symbol_value(interval.get("s") or interval.get("raw_symbol") or interval.get("symbol"))
            if not symbol or symbol.isdigit():
                continue
            mapping[instrument_text] = symbol
            try:
                mapping[int(instrument_text)] = symbol
            except ValueError:
                pass
            break
    return mapping


def merged_symbol_maps(*maps: Any) -> dict[Any, Any]:
    merged: dict[Any, Any] = {}
    for item in maps:
        if isinstance(item, dict):
            merged.update(item)
    return merged


def sample_symbol_map(mapping: dict[Any, Any], max_items: int = 10) -> list[dict[str, str]]:
    samples = []
    seen: set[str] = set()
    for key, value in sorted(mapping.items(), key=lambda item: str(item[0])):
        key_text = str(key)
        if key_text in seen:
            continue
        seen.add(key_text)
        samples.append({"instrument_id": key_text, "symbol": str(value)})
        if len(samples) >= max_items:
            break
    return samples


def resolved_raw_subscription_symbols(
    instrument_symbol_map: dict[Any, Any],
    *,
    contract_symbol_regex: str | None,
    reference_utc: Any | None = None,
    max_symbols: int = 2,
) -> list[str]:
    symbols = set()
    pattern = re.compile(contract_symbol_regex) if contract_symbol_regex else None
    for raw in instrument_symbol_map.values():
        symbol = str(raw or "").strip()
        if not symbol:
            continue
        if pattern is not None and not pattern.match(symbol):
            continue
        symbols.add(symbol)
    ranked = sorted(
        symbols,
        key=lambda symbol: (
            futures_contract_maturity_date(symbol, reference_utc=reference_utc) or dt.date.max,
            symbol,
        ),
    )
    if max_symbols > 0:
        ranked = ranked[:max_symbols]
    return ranked


def futures_contract_maturity_date(symbol: str, *, reference_utc: Any | None = None) -> dt.date | None:
    match = re.search(r"([FGHJKMNQUVXZ])(\d)$", str(symbol or "").strip())
    if not match:
        return None
    month_code = match.group(1)
    month = {
        "F": 1,
        "G": 2,
        "H": 3,
        "J": 4,
        "K": 5,
        "M": 6,
        "N": 7,
        "Q": 8,
        "U": 9,
        "V": 10,
        "X": 11,
        "Z": 12,
    }.get(month_code)
    if month is None:
        return None
    reference = normalize_utc_timestamp(reference_utc) if reference_utc is not None else pd.Timestamp.utcnow()
    reference_date = reference.date()
    decade = (reference_date.year // 10) * 10
    year = decade + int(match.group(2))
    maturity = third_friday(year, month)
    while maturity < reference_date:
        year += 10
        maturity = third_friday(year, month)
    return maturity


def third_friday(year: int, month: int) -> dt.date:
    day = dt.date(year, month, 1)
    days_until_friday = (4 - day.weekday()) % 7
    first_friday = day + dt.timedelta(days=days_until_friday)
    return first_friday + dt.timedelta(days=14)


def symbology_check_date_window(*, available_end: Any | None = None) -> tuple[str, str]:
    reference = normalize_utc_timestamp(available_end) if available_end is not None else pd.Timestamp.utcnow()
    reference = normalize_utc_timestamp(reference)
    end_date = reference.date()
    start_date = end_date - dt.timedelta(days=1)
    return start_date.isoformat(), end_date.isoformat()


def symbology_mapping_count(result: Any) -> int:
    if not isinstance(result, dict):
        return 0
    count = 0
    for intervals in result.values():
        if isinstance(intervals, list):
            count += len(intervals)
        elif intervals:
            count += 1
    return count


def sample_symbology_mappings(result: Any, max_items: int = 10) -> list[dict[str, Any]]:
    if not isinstance(result, dict):
        return []
    samples: list[dict[str, Any]] = []
    for symbol, intervals in sorted(result.items(), key=lambda item: str(item[0])):
        items = intervals if isinstance(intervals, list) else [intervals]
        for interval in items:
            if not isinstance(interval, dict):
                continue
            samples.append(
                {
                    "symbol": str(symbol),
                    "d0": interval.get("d0"),
                    "d1": interval.get("d1"),
                    "s": interval.get("s"),
                }
            )
            if len(samples) >= max_items:
                return samples
    return samples


def data_requirement_report(req: DataRequirement) -> dict[str, Any]:
    return {
        "strategy_id": req.strategy_id,
        "strategy_name": req.strategy_name,
        "timeframe": req.timeframe,
        "source_timeframe": req.source_timeframe,
        "feature_families": list(req.feature_families),
        "source_columns": list(req.source_columns),
        "derived_feature_columns": list(req.derived_feature_columns),
        "large_trade_sizes": list(req.large_trade_sizes),
        "max_feature_window_bars": req.max_feature_window_bars,
        "min_warmup_sessions": req.min_warmup_sessions,
        "recommended_source_bars": req.recommended_source_bars,
        "reasons": list(req.reasons),
    }


def required_schema_for_delta_method(delta_method: str) -> str:
    method = normalize_delta_method(delta_method)
    return "mbp-1" if method == "price_vs_quote" else "trades"


def normalize_schema_name(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "-")


def live_schema_required_field_groups(
    *,
    delta_method: str,
    contract_symbol_regex: str | None,
    schema: str | None = None,
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = [
        {"label": "event timestamp", "aliases": ["ts_event"]},
        {"label": "trade price", "aliases": ["price"]},
        {"label": "trade size", "aliases": ["size"]},
    ]
    method = normalize_delta_method(delta_method)
    if normalize_schema_name(schema) == "mbp-1":
        groups.append({"label": "trade action", "aliases": ["action"]})
    if method == "aggressor_side":
        groups.append({"label": "aggressor side", "aliases": ["side"]})
    if method == "price_vs_quote":
        groups.extend(
            [
                {"label": "best bid price", "aliases": ["bid_px_00", "bid_price", "bid_px", "levels"]},
                {"label": "best ask price", "aliases": ["ask_px_00", "ask_price", "ask_px", "levels"]},
            ]
        )
    if contract_symbol_regex:
        groups.append({"label": "contract identity", "aliases": ["instrument_id", "symbol", "raw_symbol"]})
    return groups


def live_schema_field_requirement_report(
    field_names: list[str],
    *,
    delta_method: str,
    contract_symbol_regex: str | None,
    schema: str | None = None,
) -> dict[str, Any]:
    fields = {str(field).strip() for field in field_names if str(field).strip()}
    required_groups = live_schema_required_field_groups(
        delta_method=delta_method,
        contract_symbol_regex=contract_symbol_regex,
        schema=schema,
    )
    missing = [
        group
        for group in required_groups
        if not fields.intersection(str(alias) for alias in group["aliases"])
    ]
    return {
        "ok": not missing,
        "required_field_groups": required_groups,
        "missing_required_field_groups": missing,
    }


def validate_engine_runtime_config(engine_config: dict[str, Any], databento_config: dict[str, Any]) -> None:
    errors: list[str] = []

    def check(label: str, fn: Any) -> None:
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - accumulate config errors for one preflight report.
            errors.append(f"{label}: {exc}")

    for key in ("symbol", "timezone", "alert_prefix"):
        if key in engine_config:
            check(f"engine.{key}", lambda key=key: require_non_empty_string(engine_config, key))
    check("engine.timezone", lambda: validate_timezone(str(engine_config.get("timezone") or databento_config.get("timezone") or DEFAULT_TIMEZONE)))
    check("engine.max_source_bars", lambda: config_int(engine_config, "max_source_bars", 50000, min_value=1))
    check("engine.max_entry_lag_seconds", lambda: config_float(engine_config, "max_entry_lag_seconds", 120.0, min_value=0.001))
    check("engine.replay_seed_bars", lambda: config_int(engine_config, "replay_seed_bars", 1000, min_value=0))
    for key in (
        "count_historical_signals",
        "fail_on_insufficient_warmup",
        "entry_contract_match_required",
        "dry_run_alerts",
    ):
        if key in engine_config:
            check(f"engine.{key}", lambda key=key: config_bool(engine_config, key, False))
    check(
        "engine.entry_contract_mismatch_alert_repeat_seconds",
        lambda: config_float(
            engine_config,
            "entry_contract_mismatch_alert_repeat_seconds",
            120.0,
            min_value=0.0,
        ),
    )
    if "alerts_path" in engine_config and not is_missing_or_blank(engine_config.get("alerts_path")):
        check("engine.alerts_path", lambda: require_non_empty_string(engine_config, "alerts_path"))
    check("engine.process_lock", lambda: normalize_process_lock_config(engine_config.get("process_lock", {})))
    check(
        "engine.output_path_readiness",
        lambda: normalize_output_path_readiness_config(engine_config.get("output_path_readiness", {})),
    )
    check("engine.alert_file", lambda: normalize_alert_file_config(engine_config.get("alert_file", {})))
    check("engine.setup_alerts", lambda: normalize_setup_alerts_config(engine_config.get("setup_alerts", {})))
    check("engine.execution_intents", lambda: normalize_execution_intents_config(engine_config.get("execution_intents", {})))
    check("engine.data_quality", lambda: normalize_source_bar_quality_config(engine_config.get("data_quality", {})))
    check("engine.feature_quality", lambda: normalize_feature_quality_config(engine_config.get("feature_quality", {})))
    check("engine.strategy_errors", lambda: normalize_strategy_error_config(engine_config.get("strategy_errors", {})))
    check("engine.trade_sanity", lambda: normalize_trade_sanity_config(engine_config.get("trade_sanity", {})))
    check("engine.operator", lambda: validate_operator_config(engine_config.get("operator", {})))
    check("engine.account", lambda: validate_account_config(engine_config.get("account", {})))

    for key in ("dataset", "schema", "stype_in", "stype_out", "root_symbol", "timezone"):
        if key in databento_config:
            check(f"databento.{key}", lambda key=key: require_non_empty_string(databento_config, key))
    check("databento.symbols", lambda: validate_databento_symbols(databento_config.get("symbols", DEFAULT_DATABENTO_SYMBOLS)))
    check("databento.timezone", lambda: validate_timezone(str(databento_config.get("timezone") or engine_config.get("timezone") or DEFAULT_TIMEZONE)))
    check("databento.delta_method", lambda: normalize_delta_method(databento_config.get("delta_method", "aggressor_side")))
    check("databento.large_trade_sizes", lambda: validate_positive_int_list(databento_config.get("large_trade_sizes", [])))
    check("databento.active_contract_mode", lambda: validate_active_contract_mode(databento_config.get("active_contract_mode", "highest_session_volume")))
    if "contract_symbol_regex" in databento_config:
        check(
            "databento.contract_symbol_regex",
            lambda: normalize_contract_symbol_regex(databento_config.get("contract_symbol_regex")),
        )
    check("databento.historical", lambda: validate_historical_config(databento_config.get("historical", {})))
    check("databento.live", lambda: validate_live_config(databento_config.get("live", {})))

    if errors:
        raise ValueError("Execution config preflight failed: " + "; ".join(errors))


def config_bool(mapping: dict[str, Any], key: str, default: bool) -> bool:
    value = mapping.get(key, default)
    if isinstance(value, bool):
        return value
    raise ValueError(f"{key} must be a YAML boolean true/false, got {value!r}")


def is_missing_or_blank(value: Any) -> bool:
    return value is None or value == ""


def config_int(
    mapping: dict[str, Any],
    key: str,
    default: int,
    *,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    value = mapping.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer, got {value!r}")
    if min_value is not None and value < min_value:
        raise ValueError(f"{key} must be >= {min_value}, got {value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"{key} must be <= {max_value}, got {value}")
    return value


def config_float(
    mapping: dict[str, Any],
    key: str,
    default: float,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    value = mapping.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be numeric, got {value!r}")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{key} must be finite, got {value!r}")
    if min_value is not None and parsed < min_value:
        raise ValueError(f"{key} must be >= {min_value:g}, got {parsed:g}")
    if max_value is not None and parsed > max_value:
        raise ValueError(f"{key} must be <= {max_value:g}, got {parsed:g}")
    return parsed


def config_optional_float(
    mapping: dict[str, Any],
    key: str,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float | None:
    if key not in mapping or is_missing_or_blank(mapping.get(key)):
        return None
    return config_float(mapping, key, 0.0, min_value=min_value, max_value=max_value)


def require_non_empty_string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value.strip()


def validate_timezone(value: str) -> None:
    try:
        pd.Timestamp.now(tz="UTC").tz_convert(value)
    except Exception as exc:
        raise ValueError(f"timezone {value!r} is not recognized") from exc


def normalize_alert_file_config(raw_config: Any) -> dict[str, bool]:
    if is_missing_or_blank(raw_config):
        raw: dict[str, Any] = {}
    elif isinstance(raw_config, dict):
        raw = dict(raw_config)
    else:
        raise ValueError("alert_file must be a mapping")
    return {
        "fsync": config_bool(raw, "fsync", False),
        "fail_on_write_error": config_bool(raw, "fail_on_write_error", False),
        "suppress_duplicate_alert_ids": config_bool(raw, "suppress_duplicate_alert_ids", False),
    }


def normalize_process_lock_config(raw_config: Any) -> dict[str, Any]:
    if is_missing_or_blank(raw_config):
        raw: dict[str, Any] = {}
    elif isinstance(raw_config, dict):
        raw = dict(raw_config)
    else:
        raise ValueError("process_lock must be a mapping")
    enabled = config_bool(raw, "enabled", False)
    path = raw.get("path")
    if enabled and is_missing_or_blank(path):
        raise ValueError("process_lock.path must be configured when process_lock.enabled is true")
    if not is_missing_or_blank(path) and not isinstance(path, str):
        raise ValueError("process_lock.path must be a string when configured")
    return {
        "enabled": enabled,
        "path": path.strip() if isinstance(path, str) and path.strip() else None,
        "stale_after_seconds": config_float(raw, "stale_after_seconds", 86400.0, min_value=1.0),
        "fail_if_locked": config_bool(raw, "fail_if_locked", True),
    }


def normalize_output_path_readiness_config(raw_config: Any) -> dict[str, bool]:
    if is_missing_or_blank(raw_config):
        raw: dict[str, Any] = {}
    elif isinstance(raw_config, dict):
        raw = dict(raw_config)
    else:
        raise ValueError("output_path_readiness must be a mapping")
    return {
        "enabled": config_bool(raw, "enabled", True),
        "create_parent_dirs": config_bool(raw, "create_parent_dirs", True),
        "fail_on_error": config_bool(raw, "fail_on_error", True),
        "require_fail_closed_sinks": config_bool(raw, "require_fail_closed_sinks", False),
    }


def normalize_setup_alerts_config(raw_config: Any) -> dict[str, Any]:
    if is_missing_or_blank(raw_config):
        raw: dict[str, Any] = {}
    elif isinstance(raw_config, dict):
        raw = dict(raw_config)
    else:
        raise ValueError("setup_alerts must be a mapping")
    enabled = config_bool(raw, "enabled", False)
    path = raw.get("path")
    if enabled and is_missing_or_blank(path):
        raise ValueError("setup_alerts.path must be configured when setup_alerts.enabled is true")
    if not is_missing_or_blank(path) and not isinstance(path, str):
        raise ValueError("setup_alerts.path must be a string when configured")
    return {
        "enabled": enabled,
        "path": path.strip() if isinstance(path, str) and path.strip() else None,
        "fsync": config_bool(raw, "fsync", False),
        "fail_on_write_error": config_bool(raw, "fail_on_write_error", False),
        "suppress_duplicate_setup_ids": config_bool(raw, "suppress_duplicate_setup_ids", True),
    }


def normalize_execution_intents_config(raw_config: Any) -> dict[str, Any]:
    if is_missing_or_blank(raw_config):
        raw: dict[str, Any] = {}
    elif isinstance(raw_config, dict):
        raw = dict(raw_config)
    else:
        raise ValueError("execution_intents must be a mapping")
    enabled = config_bool(raw, "enabled", False)
    path = raw.get("path")
    if enabled and is_missing_or_blank(path):
        raise ValueError("execution_intents.path must be configured when execution_intents.enabled is true")
    if not is_missing_or_blank(path) and not isinstance(path, str):
        raise ValueError("execution_intents.path must be a string when configured")
    return {
        "enabled": enabled,
        "path": path.strip() if isinstance(path, str) and path.strip() else None,
        "fsync": config_bool(raw, "fsync", False),
        "fail_on_write_error": config_bool(raw, "fail_on_write_error", False),
        "suppress_duplicate_alert_ids": config_bool(raw, "suppress_duplicate_alert_ids", True),
        "suppress_duplicate_setup_ids": config_bool(raw, "suppress_duplicate_setup_ids", True),
        "intent_ttl_seconds": config_float(raw, "intent_ttl_seconds", 30.0, min_value=0.001),
        "enforce_freshness": config_bool(raw, "enforce_freshness", True),
        "freshness_grace_seconds": config_float(raw, "freshness_grace_seconds", 0.0, min_value=0.0),
        "fail_on_freshness_error": config_bool(raw, "fail_on_freshness_error", False),
    }


def execution_intent_duplicate_suppression_enabled(config: dict[str, Any]) -> bool:
    return bool(config.get("suppress_duplicate_alert_ids", True)) or bool(
        config.get("suppress_duplicate_setup_ids", True)
    )


def execution_intent_duplicate_id_fields(config: dict[str, Any]) -> tuple[str, ...]:
    fields: list[str] = []
    if bool(config.get("suppress_duplicate_alert_ids", True)):
        fields.append("alert_id")
    if bool(config.get("suppress_duplicate_setup_ids", True)):
        fields.append("setup_id")
    return tuple(fields)


def normalize_trade_sanity_config(raw_config: Any) -> dict[str, Any]:
    if is_missing_or_blank(raw_config):
        raw: dict[str, Any] = {}
    elif isinstance(raw_config, dict):
        raw = dict(raw_config)
    else:
        raise ValueError("trade_sanity must be a mapping")
    return {
        "enabled": config_bool(raw, "enabled", True),
        "max_stop_points": config_optional_float(raw, "max_stop_points", min_value=0.0000001),
        "max_take_profit_points": config_optional_float(raw, "max_take_profit_points", min_value=0.0000001),
        "max_stop_ticks": config_optional_float(raw, "max_stop_ticks", min_value=0.0000001),
        "max_take_profit_ticks": config_optional_float(raw, "max_take_profit_ticks", min_value=0.0000001),
        "max_stop_fraction_of_entry": config_optional_float(
            raw,
            "max_stop_fraction_of_entry",
            min_value=0.0000001,
            max_value=1.0,
        ),
        "max_take_profit_fraction_of_entry": config_optional_float(
            raw,
            "max_take_profit_fraction_of_entry",
            min_value=0.0000001,
            max_value=1.0,
        ),
        "max_risk_dollars": config_optional_float(raw, "max_risk_dollars", min_value=0.01),
        "max_reward_dollars": config_optional_float(raw, "max_reward_dollars", min_value=0.01),
    }


def trade_sanity_violation_report(
    config: dict[str, Any],
    *,
    direction: str,
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float,
    stop_loss_points: float,
    take_profit_points: float,
    tick_size: float,
    tick_value: float,
    quantity: int,
) -> dict[str, Any] | None:
    if not bool(config.get("enabled", True)):
        return None
    stop_ticks = stop_loss_points / tick_size
    take_profit_ticks = take_profit_points / tick_size
    stop_fraction = stop_loss_points / abs(entry_price) if entry_price else math.inf
    take_profit_fraction = take_profit_points / abs(entry_price) if entry_price else math.inf
    risk_dollars = stop_ticks * tick_value * quantity
    reward_dollars = take_profit_ticks * tick_value * quantity
    checks = [
        ("max_stop_points", stop_loss_points, config.get("max_stop_points"), "points"),
        ("max_take_profit_points", take_profit_points, config.get("max_take_profit_points"), "points"),
        ("max_stop_ticks", stop_ticks, config.get("max_stop_ticks"), "ticks"),
        ("max_take_profit_ticks", take_profit_ticks, config.get("max_take_profit_ticks"), "ticks"),
        ("max_stop_fraction_of_entry", stop_fraction, config.get("max_stop_fraction_of_entry"), "fraction"),
        (
            "max_take_profit_fraction_of_entry",
            take_profit_fraction,
            config.get("max_take_profit_fraction_of_entry"),
            "fraction",
        ),
        ("max_risk_dollars", risk_dollars, config.get("max_risk_dollars"), "dollars"),
        ("max_reward_dollars", reward_dollars, config.get("max_reward_dollars"), "dollars"),
    ]
    base = {
        "schema_version": "trade_sanity.v1",
        "enabled": True,
        "direction": direction,
        "entry_price": float(entry_price),
        "stop_loss_price": float(stop_loss_price),
        "take_profit_price": float(take_profit_price),
        "stop_loss_points": float(stop_loss_points),
        "take_profit_points": float(take_profit_points),
        "stop_loss_ticks": float(stop_ticks),
        "take_profit_ticks": float(take_profit_ticks),
        "stop_fraction_of_entry": float(stop_fraction),
        "take_profit_fraction_of_entry": float(take_profit_fraction),
        "quantity": int(quantity),
        "tick_size": float(tick_size),
        "tick_value": float(tick_value),
        "risk_dollars": float(risk_dollars),
        "reward_dollars": float(reward_dollars),
    }
    for field, actual, limit, unit in checks:
        if limit is None:
            continue
        if actual > float(limit) + 1e-9:
            return {
                **base,
                "reason": f"trade_sanity {field} exceeded",
                "field": field,
                "actual": float(actual),
                "limit": float(limit),
                "unit": unit,
            }
    return None


def normalize_feature_quality_config(raw_config: Any) -> dict[str, Any]:
    if is_missing_or_blank(raw_config):
        raw: dict[str, Any] = {}
    elif isinstance(raw_config, dict):
        raw = dict(raw_config)
    else:
        raise ValueError("feature_quality must be a mapping")
    return {
        "enabled": config_bool(raw, "enabled", True),
        "fail_on_missing_columns": config_bool(raw, "fail_on_missing_columns", True),
        "alert_repeat_seconds": config_float(raw, "alert_repeat_seconds", 120.0, min_value=0.0),
        "max_reported_columns": config_int(raw, "max_reported_columns", 20, min_value=1),
    }


def validate_operator_config(raw_config: Any) -> None:
    if is_missing_or_blank(raw_config):
        return
    if not isinstance(raw_config, dict):
        raise ValueError("operator must be a mapping")
    for key in ("print_human_readable", "print_setup_readable", "print_rejection_readable"):
        if key in raw_config:
            config_bool(raw_config, key, True)
    sound = raw_config.get("sound", {})
    if is_missing_or_blank(sound):
        return
    if not isinstance(sound, dict):
        raise ValueError("operator.sound must be a mapping")
    for key in ("enabled", "bell", "on_setup", "on_entry", "on_system", "cleanup_on_exit", "fail_on_error"):
        if key in sound:
            config_bool(sound, key, False)
    config_int(sound, "max_active_commands", DEFAULT_OPERATOR_SOUND_MAX_ACTIVE_COMMANDS, min_value=0)
    for key in ("command", "setup_command", "entry_command", "system_command"):
        if key in sound and not is_missing_or_blank(sound.get(key)) and not isinstance(sound.get(key), str):
            raise ValueError(f"operator.sound.{key} must be a string when configured")


def validate_account_config(raw_config: Any) -> None:
    if is_missing_or_blank(raw_config):
        return
    if not isinstance(raw_config, dict):
        raise ValueError("account must be a mapping")
    min_contracts = config_int(raw_config, "min_contracts", 1, min_value=1)
    max_contracts = config_int(raw_config, "max_contracts", min_contracts, min_value=1)
    if max_contracts < min_contracts:
        raise ValueError("max_contracts must be >= min_contracts")
    config_float(raw_config, "slippage_ticks", 0.0, min_value=0.0)
    if "net_liq" in raw_config:
        config_float(raw_config, "net_liq", 0.0, min_value=0.01)
    if "equity" in raw_config:
        config_float(raw_config, "equity", 0.0, min_value=0.01)


def validate_strategy_trade_mechanics(config: dict[str, Any], *, strategy_id: str) -> None:
    core = config.get("core", {})
    if is_missing_or_blank(core):
        return
    if not isinstance(core, dict):
        raise ValueError(f"{strategy_id}: core must be a mapping")
    if "tick_size" in core:
        config_float(core, "tick_size", 0.25, min_value=0.0000001)
    if "tick_value" in core:
        config_float(core, "tick_value", 12.5, min_value=0.0000001)
    if "slippage_ticks" in core:
        config_float(core, "slippage_ticks", 0.0, min_value=0.0)
    if "initial_balance" in core:
        config_float(core, "initial_balance", 0.0, min_value=0.01)
    sizing = normalize_position_sizing_config(core.get("position_sizing", {}), strategy_id=strategy_id)
    mode = str(sizing.get("mode", "fixed_contracts")).lower()
    if mode in {"fixed", "fixed_contracts"}:
        contracts_source = sizing if "contracts" in sizing else core
        config_int(contracts_source, "contracts", 1, min_value=1)
        return
    risk_modes = {
        "risk_percent_initial_balance",
        "initial_balance_risk",
        "risk_pct_initial_balance",
        "risk_percent_net_liq",
        "net_liq_risk",
        "risk_pct_net_liq",
    }
    if mode not in risk_modes:
        raise ValueError(f"{strategy_id}: unsupported core.position_sizing.mode: {mode}")
    config_float(core, "initial_balance", 0.0, min_value=0.01)
    validate_position_sizing_risk_fraction(sizing, strategy_id=strategy_id)
    if "rounding" in sizing and str(sizing.get("rounding", "")).lower() not in {"floor", "nearest", "ceil"}:
        raise ValueError(f"{strategy_id}: core.position_sizing.rounding must be one of: floor, nearest, ceil")
    if "min_contracts" in sizing:
        config_int(sizing, "min_contracts", 1, min_value=1)
    if "max_contracts" in sizing:
        config_int(sizing, "max_contracts", 1, min_value=1)
    if "min_contracts" in sizing and "max_contracts" in sizing:
        min_contracts = int(sizing["min_contracts"])
        max_contracts = int(sizing["max_contracts"])
        if max_contracts < min_contracts:
            raise ValueError(f"{strategy_id}: core.position_sizing.max_contracts must be >= min_contracts")


def normalize_position_sizing_config(raw_config: Any, *, strategy_id: str) -> dict[str, Any]:
    if is_missing_or_blank(raw_config):
        return {}
    if isinstance(raw_config, str):
        return {"mode": raw_config}
    if isinstance(raw_config, dict):
        return dict(raw_config)
    raise ValueError(f"{strategy_id}: core.position_sizing must be a mapping or mode string")


def validate_position_sizing_risk_fraction(sizing: dict[str, Any], *, strategy_id: str) -> None:
    configured = [key for key in ("risk_pct", "risk_fraction", "risk_percent") if key in sizing]
    if not configured:
        return
    if len(configured) > 1:
        raise ValueError(
            f"{strategy_id}: core.position_sizing must configure only one of risk_pct, risk_fraction, or risk_percent"
        )
    key = configured[0]
    value = config_float(sizing, key, 0.0, min_value=0.0000001)
    limit = 100.0 if key == "risk_percent" else 1.0
    if value > limit:
        raise ValueError(f"{strategy_id}: core.position_sizing.{key} must be <= {limit:g}")


def validate_positive_int_list(value: Any) -> list[int]:
    if is_missing_or_blank(value):
        return []
    if not isinstance(value, list):
        raise ValueError("must be a list of positive integers")
    out = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item <= 0:
            raise ValueError(f"must contain only positive integers, got {item!r}")
        out.append(item)
    return out


def validate_databento_symbols(value: Any) -> None:
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("symbols must be non-empty")
        return
    if isinstance(value, int) and not isinstance(value, bool):
        return
    if isinstance(value, list) and value:
        for item in value:
            if isinstance(item, str):
                if not item.strip():
                    raise ValueError("symbols list must not contain empty strings")
            elif not isinstance(item, int) or isinstance(item, bool):
                raise ValueError("symbols list must contain strings or integer instrument ids")
        return
    raise ValueError("symbols must be a non-empty string, integer instrument id, or list")


def validate_active_contract_mode(value: Any) -> str:
    mode = str(value or "highest_session_volume").strip()
    allowed = {"highest_session_volume", "highest_minute_volume", "emit_all"}
    if mode not in allowed:
        raise ValueError(f"active_contract_mode must be one of {sorted(allowed)}, got {value!r}")
    return mode


def normalize_contract_symbol_regex(value: Any) -> str | None:
    if is_missing_or_blank(value):
        return None
    if not isinstance(value, str):
        raise ValueError(f"contract_symbol_regex must be a string when configured, got {value!r}")
    text = value.strip()
    if not text:
        return None
    try:
        re.compile(text)
    except re.error as exc:
        raise ValueError(f"contract_symbol_regex is not a valid regex: {exc}") from exc
    return text


def contract_symbol_matches_regex(contract_symbol: Any, pattern: Any | None) -> bool:
    if pattern is None:
        return True
    text = str(contract_symbol or "").strip()
    if not text:
        return False
    return bool(pattern.match(text))


def validate_historical_config(raw_config: Any) -> None:
    if is_missing_or_blank(raw_config):
        return
    if not isinstance(raw_config, dict):
        raise ValueError("historical must be a mapping")
    for key in ("enabled", "clamp_end_to_available", "refresh", "allow_contract_symbol_regex_relaxation"):
        if key in raw_config:
            config_bool(raw_config, key, False)
    for key in ("lookback_days", "max_seed_bars"):
        if key in raw_config:
            config_int(raw_config, key, 0, min_value=0)
    if "limit" in raw_config and raw_config.get("limit") is not None:
        config_int(raw_config, "limit", 0, min_value=1)
    cache_metadata = raw_config.get("cache_metadata", {})
    if not is_missing_or_blank(cache_metadata):
        if not isinstance(cache_metadata, dict):
            raise ValueError("historical.cache_metadata must be a mapping")
        for key in ("enabled", "fail_on_mismatch"):
            if key in cache_metadata:
                config_bool(cache_metadata, key, False)
        if "max_staleness_days" in cache_metadata and cache_metadata.get("max_staleness_days") is not None:
            config_float(cache_metadata, "max_staleness_days", 0.0, min_value=0.0)
    guard = raw_config.get("cost_guard", {})
    if is_missing_or_blank(guard):
        return
    if not isinstance(guard, dict):
        raise ValueError("historical.cost_guard must be a mapping")
    for key in ("enabled", "allow_paid_downloads", "fail_if_estimate_unavailable"):
        if key in guard:
            config_bool(guard, key, False)
    if "max_cost_usd" in guard:
        config_float(guard, "max_cost_usd", 0.0, min_value=0.0)


def validate_live_config(raw_config: Any) -> None:
    if is_missing_or_blank(raw_config):
        return
    if not isinstance(raw_config, dict):
        raise ValueError("live must be a mapping")
    for key in (
        "enabled",
        "metadata_preflight",
        "allow_live_without_metadata_preflight",
        "require_fail_closed_safety_stops",
        "stop_on_disconnect",
        "stop_on_no_records",
        "stop_on_no_trade_ticks",
        "stop_on_no_completed_bars",
        "stop_on_no_evaluable_strategies",
        "stop_on_partial_unevaluable_strategies",
        "stop_on_stale_trade_tick",
        "stop_on_future_trade_tick",
        "stop_on_unmatched_contract_symbol",
        "stop_on_state_lock_timeout",
        "drop_partial_first_live_bar",
        "flush_completed_bars_on_heartbeat",
        "resolve_instrument_symbols",
        "fail_without_live_symbol_map",
        "subscribe_resolved_raw_symbols",
    ):
        if key in raw_config:
            config_bool(raw_config, key, False)
    for key in (
        "heartbeat_interval_s",
        "maintenance_interval_seconds",
        "status_interval_seconds",
        "startup_grace_seconds",
        "shutdown_grace_seconds",
        "state_lock_timeout_seconds",
        "alert_repeat_seconds",
        "no_records_alert_seconds",
        "no_trade_ticks_alert_seconds",
        "no_completed_bar_alert_seconds",
        "max_trade_tick_lag_seconds",
        "max_trade_tick_future_seconds",
        "bar_flush_delay_seconds",
    ):
        if key in raw_config and raw_config.get(key) is not None:
            config_float(raw_config, key, 0.0, min_value=0.0)
    if "no_evaluable_strategy_alert_bars" in raw_config and raw_config.get("no_evaluable_strategy_alert_bars") is not None:
        config_int(raw_config, "no_evaluable_strategy_alert_bars", 0, min_value=0)
    if "session_aware_stale_alerts" in raw_config:
        config_bool(raw_config, "session_aware_stale_alerts", True)
    for key in ("stale_alert_session_start", "stale_alert_session_end"):
        if key in raw_config and not is_missing_or_blank(raw_config.get(key)):
            parse_time_of_day(raw_config[key], key=key)
    if "stale_alert_session_timezone" in raw_config and not is_missing_or_blank(
        raw_config.get("stale_alert_session_timezone")
    ):
        validate_timezone(str(raw_config["stale_alert_session_timezone"]))
    if "stale_alert_weekdays" in raw_config and raw_config.get("stale_alert_weekdays") is not None:
        validate_weekdays(raw_config["stale_alert_weekdays"])
    if "reconnect_policy" in raw_config and not isinstance(raw_config.get("reconnect_policy"), str):
        raise ValueError("live.reconnect_policy must be a string")
    if "symbology_stype_out" in raw_config and not isinstance(raw_config.get("symbology_stype_out"), str):
        raise ValueError("live.symbology_stype_out must be a string")
    if "max_resolved_raw_symbols" in raw_config:
        config_int(raw_config, "max_resolved_raw_symbols", 2, min_value=0)
    if "start" in raw_config and not is_missing_or_blank(raw_config.get("start")):
        pd.Timestamp(raw_config["start"])
    guard = raw_config.get("cost_guard", {})
    if not is_missing_or_blank(guard):
        if not isinstance(guard, dict):
            raise ValueError("live.cost_guard must be a mapping")
        for key in ("enabled", "allow_live_subscription", "acknowledge_live_data_may_be_billable"):
            if key in guard:
                config_bool(guard, key, False)


def validate_unique_strategy_ids(strategies: list["StrategyRuntime"]) -> None:
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for strategy in strategies:
        strategy_id = strategy.strategy_id
        if strategy_id in seen:
            duplicates.append(strategy_id)
        seen[strategy_id] = strategy.preflight_report().get("config", "")
    if duplicates:
        raise ValueError(f"strategy ids must be unique; duplicate id(s): {sorted(set(duplicates))}")


def parse_time_of_day(value: Any, *, key: str) -> dt.time:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be HH:MM:SS or HH:MM")
    try:
        parsed = dt.time.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{key} must be HH:MM:SS or HH:MM, got {value!r}") from exc
    return parsed


def validate_weekdays(value: Any) -> list[int]:
    if not isinstance(value, list) or not value:
        raise ValueError("stale_alert_weekdays must be a non-empty list of weekday integers 0-6")
    out = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int) or item < 0 or item > 6:
            raise ValueError(f"stale_alert_weekdays must contain integers 0-6, got {item!r}")
        out.append(item)
    return out


def normalize_source_bar_quality_config(raw_config: Any) -> dict[str, Any]:
    if is_missing_or_blank(raw_config):
        raw: dict[str, Any] = {}
    elif isinstance(raw_config, dict):
        raw = dict(raw_config)
    else:
        raise ValueError("data_quality must be a mapping")
    return {
        "enabled": config_bool(raw, "enabled", True),
        "fail_on_error": config_bool(raw, "fail_on_error", False),
        "allow_zero_volume": config_bool(raw, "allow_zero_volume", False),
        "warn_on_time_gaps": config_bool(raw, "warn_on_time_gaps", True),
        "max_bar_gap_minutes": config_float(raw, "max_bar_gap_minutes", 5.0, min_value=0.0),
        "max_reported_issues": config_int(raw, "max_reported_issues", 10, min_value=1),
        "alert_repeat_seconds": config_float(raw, "alert_repeat_seconds", 120.0, min_value=0.0),
        "delta_unclassified": normalize_delta_unclassified_quality_config(raw.get("delta_unclassified", {})),
    }


def normalize_delta_unclassified_quality_config(raw_config: Any) -> dict[str, Any]:
    if is_missing_or_blank(raw_config):
        raw: dict[str, Any] = {}
    elif isinstance(raw_config, dict):
        raw = dict(raw_config)
    else:
        raise ValueError("data_quality.delta_unclassified must be a mapping")
    raw_methods = raw.get("delta_methods", ["price_vs_quote"])
    if isinstance(raw_methods, str):
        raw_method_list = [raw_methods]
    elif isinstance(raw_methods, list):
        raw_method_list = raw_methods
    else:
        raise ValueError("delta_unclassified.delta_methods must be a string or list")
    delta_methods = []
    for item in raw_method_list:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("delta_unclassified.delta_methods must contain non-empty strings")
        method = normalize_delta_method(item)
        if method not in delta_methods:
            delta_methods.append(method)
    severity = str(raw.get("severity", "error") or "error").strip().lower()
    if severity not in {"warning", "error"}:
        raise ValueError("delta_unclassified.severity must be 'warning' or 'error'")
    return {
        "enabled": config_bool(raw, "enabled", True),
        "delta_methods": delta_methods,
        "max_selected_unclassified_fraction": config_float(
            raw,
            "max_selected_unclassified_fraction",
            0.25,
            min_value=0.0,
            max_value=1.0,
        ),
        "min_checked_volume": config_float(raw, "min_checked_volume", 1.0, min_value=0.0),
        "require_diagnostic": config_bool(raw, "require_diagnostic", True),
        "severity": severity,
    }


def normalize_strategy_error_config(raw_config: Any) -> dict[str, Any]:
    if is_missing_or_blank(raw_config):
        raw: dict[str, Any] = {}
    elif isinstance(raw_config, dict):
        raw = dict(raw_config)
    else:
        raise ValueError("strategy_errors must be a mapping")
    return {
        "fail_fast": config_bool(raw, "fail_fast", False),
        "disable_strategy_on_error": config_bool(raw, "disable_strategy_on_error", True),
        "max_errors_per_strategy": config_int(raw, "max_errors_per_strategy", 1, min_value=1),
        "fail_when_all_strategies_disabled": config_bool(raw, "fail_when_all_strategies_disabled", True),
    }


def validate_source_bars_quality(
    bars: list[SourceMinuteBar],
    *,
    timezone: str,
    config: dict[str, Any],
    delta_method: str | None = None,
) -> list[SourceBarQualityIssue]:
    if not bool(config.get("enabled", True)):
        return []
    issues: list[SourceBarQualityIssue] = []
    seen_keys: dict[tuple[str, str], int] = {}
    sequence: dict[str, list[tuple[int, Any, SourceMinuteBar]]] = {}
    for index, bar in enumerate(bars):
        issues.extend(validate_source_bar_quality(bar, index=index, config=config, delta_method=delta_method))
        timestamp = source_bar_timestamp_utc(bar)
        if timestamp is None:
            continue
        key = (timestamp.isoformat(), str(bar.contract_symbol))
        if key in seen_keys:
            issues.append(
                source_bar_quality_issue(
                    bar,
                    index=index,
                    severity="error",
                    code="duplicate_source_bar",
                    message=(
                        "Duplicate source bar for the same timestamp and contract; "
                        f"first occurrence index={seen_keys[key]}."
                    ),
                )
            )
        else:
            seen_keys[key] = index
        sequence.setdefault(str(bar.contract_symbol), []).append((index, timestamp, bar))

    if bool(config.get("warn_on_time_gaps", True)):
        max_gap_minutes = float(config.get("max_bar_gap_minutes", 5.0) or 0.0)
        if max_gap_minutes > 0:
            issues.extend(source_bar_gap_warnings(sequence, timezone=timezone, max_gap_minutes=max_gap_minutes))
    return issues


def validate_source_bar_quality(
    bar: SourceMinuteBar,
    *,
    index: int,
    config: dict[str, Any],
    delta_method: str | None = None,
) -> list[SourceBarQualityIssue]:
    issues: list[SourceBarQualityIssue] = []
    timestamp = source_bar_timestamp_utc(bar)
    if timestamp is None:
        issues.append(
            source_bar_quality_issue(
                bar,
                index=index,
                severity="error",
                code="invalid_timestamp",
                message="Source bar timestamp_utc is missing, naive, or cannot be parsed as a UTC timestamp.",
            )
        )
    if not str(getattr(bar, "symbol", "") or "").strip():
        issues.append(
            source_bar_quality_issue(
                bar,
                index=index,
                severity="error",
                code="missing_symbol",
                message="Source bar symbol is empty.",
            )
        )
    if not str(getattr(bar, "contract_symbol", "") or "").strip():
        issues.append(
            source_bar_quality_issue(
                bar,
                index=index,
                severity="error",
                code="missing_contract_symbol",
                message="Source bar contract_symbol is empty.",
            )
        )

    open_price = finite_float(getattr(bar, "open", None))
    high_price = finite_float(getattr(bar, "high", None))
    low_price = finite_float(getattr(bar, "low", None))
    close_price = finite_float(getattr(bar, "close", None))
    prices = {
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
    }
    for name, value in prices.items():
        if value is None:
            issues.append(
                source_bar_quality_issue(
                    bar,
                    index=index,
                    severity="error",
                    code=f"invalid_{name}",
                    message=f"Source bar {name} price is not finite.",
                )
            )
        elif value <= 0:
            issues.append(
                source_bar_quality_issue(
                    bar,
                    index=index,
                    severity="error",
                    code=f"non_positive_{name}",
                    message=f"Source bar {name} price must be positive.",
                )
            )
    if all(value is not None for value in prices.values()):
        tolerance = 1e-9
        assert open_price is not None
        assert high_price is not None
        assert low_price is not None
        assert close_price is not None
        if high_price + tolerance < low_price:
            issues.append(
                source_bar_quality_issue(
                    bar,
                    index=index,
                    severity="error",
                    code="high_below_low",
                    message="Source bar high is below low.",
                )
            )
        if high_price + tolerance < max(open_price, close_price):
            issues.append(
                source_bar_quality_issue(
                    bar,
                    index=index,
                    severity="error",
                    code="high_below_open_or_close",
                    message="Source bar high is below open or close.",
                )
            )
        if low_price - tolerance > min(open_price, close_price):
            issues.append(
                source_bar_quality_issue(
                    bar,
                    index=index,
                    severity="error",
                    code="low_above_open_or_close",
                    message="Source bar low is above open or close.",
                )
            )

    volume = finite_float(getattr(bar, "volume", None))
    signed_volume = finite_float(getattr(bar, "signed_volume", None))
    buy_volume = finite_float(getattr(bar, "buy_volume", None))
    sell_volume = finite_float(getattr(bar, "sell_volume", None))
    trades = finite_float(getattr(bar, "trades", None))
    if volume is None:
        issues.append(
            source_bar_quality_issue(
                bar,
                index=index,
                severity="error",
                code="invalid_volume",
                message="Source bar volume is not finite.",
            )
        )
    elif volume < 0:
        issues.append(
            source_bar_quality_issue(
                bar,
                index=index,
                severity="error",
                code="negative_volume",
                message="Source bar volume is negative.",
            )
        )
    elif volume == 0 and not bool(config.get("allow_zero_volume", False)):
        issues.append(
            source_bar_quality_issue(
                bar,
                index=index,
                severity="error",
                code="zero_volume",
                message="Source bar volume is zero; refusing to let an empty ES bar drive strategy state.",
            )
        )
    for name, value in {
        "signed_volume": signed_volume,
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "trades": trades,
    }.items():
        if value is None:
            issues.append(
                source_bar_quality_issue(
                    bar,
                    index=index,
                    severity="error",
                    code=f"invalid_{name}",
                    message=f"Source bar {name} is not finite.",
                )
            )
    if buy_volume is not None and buy_volume < 0:
        issues.append(
            source_bar_quality_issue(
                bar,
                index=index,
                severity="error",
                code="negative_buy_volume",
                message="Source bar buy_volume is negative.",
            )
        )
    if sell_volume is not None and sell_volume < 0:
        issues.append(
            source_bar_quality_issue(
                bar,
                index=index,
                severity="error",
                code="negative_sell_volume",
                message="Source bar sell_volume is negative.",
            )
        )
    if trades is not None and trades < 0:
        issues.append(
            source_bar_quality_issue(
                bar,
                index=index,
                severity="error",
                code="negative_trades",
                message="Source bar trades is negative.",
            )
        )
    elif trades == 0 and volume not in {None, 0}:
        issues.append(
            source_bar_quality_issue(
                bar,
                index=index,
                severity="warning",
                code="zero_trades_with_volume",
                message="Source bar has positive volume but zero trades; cached data may be missing trade counts.",
            )
        )

    tolerance = 1e-9
    if volume is not None and signed_volume is not None and abs(signed_volume) > volume + tolerance:
        issues.append(
            source_bar_quality_issue(
                bar,
                index=index,
                severity="error",
                code="signed_volume_exceeds_volume",
                message="Source bar absolute signed_volume exceeds total volume.",
            )
        )
    if volume is not None and buy_volume is not None and sell_volume is not None:
        if buy_volume + sell_volume > volume + tolerance:
            issues.append(
                source_bar_quality_issue(
                    bar,
                    index=index,
                    severity="error",
                    code="classified_volume_exceeds_volume",
                    message="Source bar buy_volume + sell_volume exceeds total volume.",
                )
            )
        if signed_volume is not None and abs((buy_volume - sell_volume) - signed_volume) > tolerance:
            issues.append(
                source_bar_quality_issue(
                    bar,
                    index=index,
                    severity="warning",
                    code="signed_volume_reconciliation_mismatch",
                    message="Source bar signed_volume does not equal buy_volume - sell_volume.",
                )
            )
    issues.extend(
        validate_delta_unclassified_source_bar_quality(
            bar,
            index=index,
            config=config,
            delta_method=delta_method,
            volume=volume,
        )
    )
    return issues


def validate_delta_unclassified_source_bar_quality(
    bar: SourceMinuteBar,
    *,
    index: int,
    config: dict[str, Any],
    delta_method: str | None,
    volume: float | None,
) -> list[SourceBarQualityIssue]:
    guard = config.get("delta_unclassified", {})
    if not isinstance(guard, dict) or not bool(guard.get("enabled", True)):
        return []
    method = normalize_delta_method(delta_method or "aggressor_side")
    allowed_methods = [str(item) for item in guard.get("delta_methods", [])]
    if allowed_methods and method not in allowed_methods:
        return []
    if volume is None:
        return []
    min_checked_volume = float(guard.get("min_checked_volume", 1.0) or 0.0)
    if volume < min_checked_volume:
        return []
    severity = str(guard.get("severity", "error") or "error")
    large = getattr(bar, "large", {}) if isinstance(getattr(bar, "large", {}), dict) else {}
    selected = finite_float(large.get("selected_delta_unclassified_volume"))
    require_diagnostic = bool(guard.get("require_diagnostic", True))
    if selected is None:
        if not require_diagnostic:
            return []
        return [
            source_bar_quality_issue(
                bar,
                index=index,
                severity=severity,
                code="missing_selected_delta_unclassified_volume",
                message=(
                    f"Source bar is using delta_method={method} but does not include "
                    "selected_delta_unclassified_volume diagnostics; refusing to treat the selected "
                    "delta as verified."
                ),
            )
        ]
    if selected < 0:
        return [
            source_bar_quality_issue(
                bar,
                index=index,
                severity="error",
                code="negative_selected_delta_unclassified_volume",
                message="Source bar selected_delta_unclassified_volume is negative.",
            )
        ]
    if selected > volume + 1e-9:
        return [
            source_bar_quality_issue(
                bar,
                index=index,
                severity="error",
                code="selected_delta_unclassified_volume_exceeds_volume",
                message="Source bar selected_delta_unclassified_volume exceeds total volume.",
            )
        ]
    max_fraction = float(guard.get("max_selected_unclassified_fraction", 0.25))
    fraction = selected / volume if volume > 0 else 0.0
    if fraction <= max_fraction + 1e-12:
        return []
    return [
        source_bar_quality_issue(
            bar,
            index=index,
            severity=severity,
            code="selected_delta_unclassified_fraction_exceeded",
            message=(
                "Source bar selected unclassified delta volume fraction "
                f"{fraction:.4f} exceeded configured maximum {max_fraction:.4f} "
                f"for delta_method={method}; selected_delta_unclassified_volume={selected:g}, "
                f"volume={volume:g}."
            ),
        )
    ]


def source_bar_gap_warnings(
    sequence: dict[str, list[tuple[int, Any, SourceMinuteBar]]],
    *,
    timezone: str,
    max_gap_minutes: float,
) -> list[SourceBarQualityIssue]:
    issues: list[SourceBarQualityIssue] = []
    for contract_symbol, rows in sequence.items():
        previous: tuple[int, Any, SourceMinuteBar] | None = None
        for current in sorted(rows, key=lambda item: item[1]):
            if previous is None:
                previous = current
                continue
            previous_index, previous_timestamp, _previous_bar = previous
            current_index, current_timestamp, current_bar = current
            if local_session_date(previous_timestamp, timezone) != local_session_date(current_timestamp, timezone):
                previous = current
                continue
            gap_minutes = (current_timestamp - previous_timestamp).total_seconds() / 60.0
            if gap_minutes > max_gap_minutes:
                issues.append(
                    source_bar_quality_issue(
                        current_bar,
                        index=current_index,
                        severity="warning",
                        code="source_bar_time_gap",
                        message=(
                            f"Detected {gap_minutes:.1f} minute gap in {contract_symbol} source bars "
                            f"after input index {previous_index}."
                        ),
                    )
                )
            previous = current
    return issues


def source_bar_timestamp_utc(bar: SourceMinuteBar) -> Any | None:
    try:
        timestamp = pd.Timestamp(getattr(bar, "timestamp_utc", None))
    except Exception:
        return None
    if timestamp is pd.NaT or timestamp.tzinfo is None:
        return None
    try:
        return timestamp.tz_convert("UTC")
    except Exception:
        return None


def source_bar_quality_issue(
    bar: SourceMinuteBar,
    *,
    index: int,
    severity: str,
    code: str,
    message: str,
) -> SourceBarQualityIssue:
    timestamp = source_bar_timestamp_utc(bar)
    return SourceBarQualityIssue(
        severity=severity,
        code=code,
        message=message,
        bar_index=index,
        timestamp_utc=timestamp.isoformat() if timestamp is not None else None,
        contract_symbol=str(getattr(bar, "contract_symbol", "") or ""),
        source=str(getattr(bar, "source", "") or ""),
    )


def source_bar_quality_issue_report(issue: SourceBarQualityIssue) -> dict[str, Any]:
    return {
        "severity": issue.severity,
        "code": issue.code,
        "message": issue.message,
        "bar_index": issue.bar_index,
        "timestamp_utc": issue.timestamp_utc,
        "contract_symbol": issue.contract_symbol,
        "source": issue.source,
    }


def load_historical_seed_bars(engine: SignalEngine, *, refresh: bool = False) -> list[SourceMinuteBar]:
    hist_cfg = dict(engine.databento_config.get("historical", {}))
    if not bool(hist_cfg.get("enabled", True)):
        return []
    cache_path = resolve_optional_path(engine.config_dir, hist_cfg.get("cache_path"))
    refresh_requested = bool(refresh or hist_cfg.get("refresh", False))
    if cache_path and cache_path.exists() and not refresh_requested:
        bars = read_bars_file(
            cache_path,
            root_symbol=engine.symbol,
            timezone=engine.timezone,
            source="historical_cache",
            required_source_columns=engine.data_plan.get("source_columns", []),
        )
        validate_historical_cache_metadata(engine, cache_path, bars, hist_cfg)
        print_json({"event": "historical_cache_loaded", "path": str(cache_path), "bars": len(bars)})
        return bars

    seed_bars_path = resolve_optional_path(engine.config_dir, hist_cfg.get("seed_bars_path"))
    if seed_bars_path and not refresh_requested:
        bars = read_bars_file(
            seed_bars_path,
            root_symbol=engine.symbol,
            timezone=engine.timezone,
            source="historical_file",
            required_source_columns=engine.data_plan.get("source_columns", []),
        )
        validate_historical_seed_file_metadata(engine, seed_bars_path, bars, hist_cfg)
        print_json({"event": "historical_seed_file_loaded", "path": str(seed_bars_path), "bars": len(bars)})
        if cache_path:
            write_historical_cache(engine, cache_path, bars, source="historical_file")
        return bars
    if seed_bars_path and refresh_requested:
        print_json(
            {
                "event": "historical_seed_file_bypassed_for_refresh",
                "path": str(seed_bars_path),
                "refresh_requested": True,
                "impact": (
                    "Historical refresh was requested, so the configured seed file was not used. "
                    "The engine will continue to the guarded Databento historical fetch path."
                ),
            }
        )

    bars = fetch_databento_historical_bars(engine, hist_cfg)
    if cache_path and bars:
        write_historical_cache(engine, cache_path, bars, source="databento_historical")
        print_json({"event": "historical_cache_written", "path": str(cache_path), "bars": len(bars)})
    return bars


def write_historical_cache(engine: SignalEngine, cache_path: Path, bars: list[SourceMinuteBar], *, source: str) -> None:
    write_bars_file(cache_path, bars, timezone=engine.timezone)
    hist_cfg = dict(engine.databento_config.get("historical", {}))
    cache_meta_cfg = dict(hist_cfg.get("cache_metadata", {}))
    if not bool(cache_meta_cfg.get("enabled", True)):
        return
    metadata_path = historical_cache_metadata_path(cache_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = build_historical_cache_metadata(engine, bars, source=source)
    metadata_path.write_text(json.dumps(metadata, sort_keys=True, indent=2, default=json_default) + "\n", encoding="utf-8")
    print_json(
        {
            "event": "historical_cache_metadata_written",
            "path": str(metadata_path),
            "cache_path": str(cache_path),
            "bars": len(bars),
        }
    )


def validate_historical_cache_metadata(
    engine: SignalEngine,
    cache_path: Path,
    bars: list[SourceMinuteBar],
    hist_cfg: dict[str, Any],
) -> None:
    validate_historical_bars_metadata(
        engine,
        cache_path,
        bars,
        hist_cfg,
        event_prefix="historical_cache_metadata",
        path_field="cache_path",
        artifact_label="Historical cache",
        refresh_target="cache",
    )


def validate_historical_seed_file_metadata(
    engine: SignalEngine,
    seed_bars_path: Path,
    bars: list[SourceMinuteBar],
    hist_cfg: dict[str, Any],
) -> None:
    validate_historical_bars_metadata(
        engine,
        seed_bars_path,
        bars,
        hist_cfg,
        event_prefix="historical_seed_file_metadata",
        path_field="seed_bars_path",
        artifact_label="Historical seed file",
        refresh_target="seed file",
    )


def validate_historical_bars_metadata(
    engine: SignalEngine,
    bars_path: Path,
    bars: list[SourceMinuteBar],
    hist_cfg: dict[str, Any],
    *,
    event_prefix: str,
    path_field: str,
    artifact_label: str,
    refresh_target: str,
) -> None:
    cache_meta_cfg = dict(hist_cfg.get("cache_metadata", {}))
    if not bool(cache_meta_cfg.get("enabled", True)):
        return
    fail_on_mismatch = bool(cache_meta_cfg.get("fail_on_mismatch", False))
    metadata_path = historical_cache_metadata_path(bars_path)
    if not metadata_path.exists():
        payload = {
            "event": f"{event_prefix}_missing",
            path_field: str(bars_path),
            "metadata_path": str(metadata_path),
            "bars": len(bars),
            "impact": (
                f"{artifact_label} bars were loaded without proof that they match "
                "the current Databento/runtime settings."
            ),
        }
        print_json(payload, prefix="SYSTEM_ALERT")
        if fail_on_mismatch:
            raise RuntimeError(f"{artifact_label} metadata is missing for {bars_path}.")
        return
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:
        payload = {
            "event": f"{event_prefix}_invalid",
            path_field: str(bars_path),
            "metadata_path": str(metadata_path),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "impact": f"{artifact_label} metadata could not be parsed; compatibility is unknown.",
        }
        print_json(payload, prefix="SYSTEM_ALERT")
        if fail_on_mismatch:
            raise RuntimeError(f"{artifact_label} metadata is invalid for {bars_path}: {exc}") from exc
        return
    expected = build_historical_cache_metadata(engine, bars, source=str(metadata.get("source") or "expected"))
    issues = historical_cache_metadata_issues(metadata, expected)
    if not issues:
        print_json(
            {
                "event": f"{event_prefix}_valid",
                path_field: str(bars_path),
                "metadata_path": str(metadata_path),
                "bars": len(bars),
            }
        )
        staleness_issue = historical_cache_staleness_issue(
            bars,
            max_staleness_days=cache_meta_cfg.get("max_staleness_days"),
        )
        if staleness_issue is not None:
            payload = {
                "event": f"{event_prefix}_stale",
                path_field: str(bars_path),
                "metadata_path": str(metadata_path),
                **staleness_issue,
                "impact": (
                    "Historical seed bars are older than the configured freshness threshold. "
                    "Strategies may warm up on stale context before live mode starts."
                ),
            }
            print_json(payload, prefix="SYSTEM_ALERT")
            if fail_on_mismatch:
                raise RuntimeError(f"{artifact_label} is stale for {bars_path}; refresh the {refresh_target}.")
        return
    payload = {
        "event": f"{event_prefix}_mismatch",
        path_field: str(bars_path),
        "metadata_path": str(metadata_path),
        "issue_count": len(issues),
        "issues": issues[:20],
        "issues_truncated": max(0, len(issues) - 20),
        "impact": (
            f"{artifact_label} bars may have been generated with different settings "
            "than the current signal engine config."
        ),
    }
    print_json(payload, prefix="SYSTEM_ALERT")
    if fail_on_mismatch:
        raise RuntimeError(
            f"{artifact_label} metadata mismatch for {bars_path}; refresh the {refresh_target} or update config."
        )


def historical_cache_metadata_path(cache_path: Path) -> Path:
    return cache_path.with_name(f"{cache_path.name}.metadata.json")


def build_historical_cache_metadata(
    engine: SignalEngine,
    bars: list[SourceMinuteBar],
    *,
    source: str,
) -> dict[str, Any]:
    hist_cfg = dict(engine.databento_config.get("historical", {}))
    return {
        "schema_version": "historical_cache_metadata.v1",
        "created_at_utc": utc_now_iso(),
        "source": source,
        "config": historical_cache_metadata_config(engine),
        "bars": historical_cache_bar_summary(bars),
        "historical": {
            "complete_session_end": hist_cfg.get("complete_session_end"),
            "max_seed_bars": hist_cfg.get("max_seed_bars"),
            "allow_contract_symbol_regex_relaxation": bool(
                hist_cfg.get("allow_contract_symbol_regex_relaxation", False)
            ),
        },
    }


def historical_cache_metadata_config(engine: SignalEngine) -> dict[str, Any]:
    config = engine.databento_config
    return {
        "symbol": engine.symbol,
        "timezone": engine.timezone,
        "dataset": str(config.get("dataset", DEFAULT_DATASET)),
        "schema": str(config.get("schema", DEFAULT_SCHEMA)),
        "symbols": config.get("symbols", DEFAULT_DATABENTO_SYMBOLS),
        "stype_in": str(config.get("stype_in", DEFAULT_STYPE_IN)),
        "stype_out": str(config.get("stype_out", DEFAULT_STYPE_OUT)),
        "root_symbol": str(config.get("root_symbol", engine.symbol)),
        "rth_start": str(config.get("rth_start", "09:30:00")),
        "rth_end": str(config.get("rth_end", "16:00:00")),
        "contract_symbol_regex": str(config.get("contract_symbol_regex", r"^ES[HMUZ]\d$")),
        "large_trade_sizes": effective_large_trade_sizes(engine),
        "delta_method": normalize_delta_method(config.get("delta_method", "aggressor_side")),
        "active_contract_mode": validate_active_contract_mode(config.get("active_contract_mode", "highest_session_volume")),
    }


def historical_cache_bar_summary(bars: list[SourceMinuteBar]) -> dict[str, Any]:
    if not bars:
        return {
            "bar_count": 0,
            "first_timestamp_utc": None,
            "last_timestamp_utc": None,
            "contracts": [],
            "content_sha256": historical_cache_bars_fingerprint(bars),
        }
    ordered = sorted(bars, key=lambda bar: (bar.timestamp_utc, bar.contract_symbol))
    return {
        "bar_count": len(bars),
        "first_timestamp_utc": format_timestamp(pd.Timestamp(ordered[0].timestamp_utc).tz_convert("UTC")),
        "last_timestamp_utc": format_timestamp(pd.Timestamp(ordered[-1].timestamp_utc).tz_convert("UTC")),
        "contracts": sorted({bar.contract_symbol for bar in bars})[:20],
        "contracts_truncated": max(0, len({bar.contract_symbol for bar in bars}) - 20),
        "content_sha256": historical_cache_bars_fingerprint(ordered),
    }


def historical_cache_staleness_issue(
    bars: list[SourceMinuteBar],
    *,
    max_staleness_days: Any,
    now_utc: Any | None = None,
) -> dict[str, Any] | None:
    if max_staleness_days is None:
        return None
    max_days = float(max_staleness_days)
    if max_days <= 0 or not bars:
        return None
    latest = max(normalize_utc_timestamp(bar.timestamp_utc) for bar in bars)
    now = normalize_utc_timestamp(now_utc) if now_utc is not None else pd.Timestamp.utcnow()
    age_seconds = max(0.0, (now - latest).total_seconds())
    age_days = age_seconds / 86400.0
    if age_days <= max_days:
        return None
    return {
        "last_timestamp_utc": format_timestamp(latest),
        "now_utc": format_timestamp(now),
        "age_days": round(age_days, 6),
        "age_seconds": round(age_seconds, 3),
        "max_staleness_days": max_days,
        "reason": "Historical cache last bar is older than cache_metadata.max_staleness_days.",
    }


def historical_cache_bars_fingerprint(bars: list[SourceMinuteBar]) -> str:
    digest = hashlib.sha256()
    digest.update(b"historical_cache_bars.v1\n")
    for bar in sorted(bars, key=lambda item: (item.timestamp_utc, item.contract_symbol)):
        payload = {
            "timestamp_utc": format_timestamp(pd.Timestamp(bar.timestamp_utc).tz_convert("UTC")),
            "symbol": str(bar.symbol),
            "contract_symbol": str(bar.contract_symbol),
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": float(bar.volume),
            "signed_volume": float(bar.signed_volume),
            "buy_volume": float(bar.buy_volume),
            "sell_volume": float(bar.sell_volume),
            "trades": int(bar.trades),
            "large": {str(key): float(value) for key, value in sorted((bar.large or {}).items())},
        }
        digest.update(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=json_default).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def historical_cache_metadata_issues(actual: Any, expected: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if not isinstance(actual, dict):
        return [{"field": "", "expected": "mapping", "actual": type(actual).__name__, "reason": "metadata is not a mapping"}]
    if actual.get("schema_version") != expected.get("schema_version"):
        issues.append(
            {
                "field": "schema_version",
                "expected": expected.get("schema_version"),
                "actual": actual.get("schema_version"),
            }
        )
    for section in ("config", "historical", "bars"):
        expected_section = expected.get(section, {})
        actual_section = actual.get(section, {})
        if not isinstance(actual_section, dict):
            issues.append({"field": section, "expected": "mapping", "actual": type(actual_section).__name__})
            continue
        for key, expected_value in expected_section.items():
            if key in {"contracts", "contracts_truncated"}:
                continue
            actual_value = actual_section.get(key)
            if actual_value != expected_value:
                issues.append(
                    {
                        "field": f"{section}.{key}",
                        "expected": expected_value,
                        "actual": actual_value,
                    }
                )
    return issues


def historical_seed_source_report(
    engine: SignalEngine,
    hist_cfg: dict[str, Any],
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    enabled = bool(hist_cfg.get("enabled", True))
    cache_path = resolve_optional_path(engine.config_dir, hist_cfg.get("cache_path"))
    seed_bars_path = resolve_optional_path(engine.config_dir, hist_cfg.get("seed_bars_path"))
    refresh_requested = bool(refresh or hist_cfg.get("refresh", False))
    cache_available = bool(cache_path and cache_path.exists())
    cache_usable = bool(cache_available and not refresh_requested)
    seed_file_configured = seed_bars_path is not None
    seed_file_usable = bool(seed_file_configured and not refresh_requested)
    download_required = bool(enabled and not cache_usable and not seed_file_usable)
    if not enabled:
        source = "disabled"
    elif cache_usable:
        source = "historical_cache"
    elif seed_file_usable:
        source = "historical_file"
    else:
        source = "databento_historical"
    return {
        "enabled": enabled,
        "source": source,
        "download_required": download_required,
        "cache_path": str(cache_path) if cache_path else None,
        "cache_available": cache_available,
        "cache_usable": cache_usable,
        "seed_bars_path": str(seed_bars_path) if seed_bars_path else None,
        "seed_file_configured": seed_file_configured,
        "seed_file_usable": seed_file_usable,
        "refresh_requested": refresh_requested,
    }


def databento_historical_fetch_contract_report(
    engine: SignalEngine,
    hist_cfg: dict[str, Any] | None = None,
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    schema = normalize_schema_name(engine.databento_config.get("schema", DEFAULT_SCHEMA))
    delta_method = normalize_delta_method(engine.databento_config.get("delta_method", "aggressor_side"))
    errors: list[str] = []
    if schema != "trades":
        errors.append(
            f"configured schema {schema!r} is not supported by the historical trade-orderflow fetcher"
        )
    if delta_method != "aggressor_side":
        errors.append(
            f"configured delta_method {delta_method!r} cannot be rebuilt by the historical trade-orderflow fetcher"
        )
    effective_hist_cfg = dict(engine.databento_config.get("historical", {})) if hist_cfg is None else hist_cfg
    source_report = historical_seed_source_report(engine, effective_hist_cfg, refresh=refresh)
    fetch_supported = not errors
    return {
        "ok": bool((not source_report["download_required"]) or fetch_supported),
        "schema": schema,
        "delta_method": delta_method,
        "fetch_supported": fetch_supported,
        "fetch_required": bool(source_report["download_required"]),
        "source": source_report["source"],
        "historical_source": source_report,
        "errors": errors,
        "timeseries_download_attempted": False,
        "guarded_operation": "timeseries.get_range",
    }


def validate_databento_historical_fetch_contract(engine: SignalEngine) -> None:
    hist_cfg = dict(engine.databento_config.get("historical", {}))
    report = databento_historical_fetch_contract_report(engine, hist_cfg, refresh=True)
    errors = [str(error) for error in report.get("errors", [])]
    if not errors:
        return
    print_json(
        {
            "event": "historical_fetch_unsupported_data_contract",
            "schema": report.get("schema"),
            "delta_method": report.get("delta_method"),
            "errors": errors,
            "fetch_required": True,
            "historical_source": report.get("historical_source"),
            "impact": (
                "Refusing to fetch historical Databento data because the built-in historical "
                "aggregator only produces trade-side aggressor bars. Use a prebuilt cache with "
                "matching metadata for other delta methods or schemas."
            ),
            "timeseries_download_attempted": False,
        },
        prefix="SYSTEM_ALERT",
    )
    raise RuntimeError("Historical Databento fetch data contract is unsupported: " + "; ".join(errors))


def fetch_databento_historical_bars(engine: SignalEngine, hist_cfg: dict[str, Any]) -> list[SourceMinuteBar]:
    validate_databento_historical_fetch_contract(engine)
    add_project_src_to_path(engine.project_root)
    from propstack.data.databento_trades import aggregate_trade_orderflow_1m

    import databento as db

    api_key = databento_api_key(engine.databento_config)
    dataset = str(engine.databento_config.get("dataset", DEFAULT_DATASET))
    schema = str(engine.databento_config.get("schema", DEFAULT_SCHEMA))
    symbols = engine.databento_config.get("symbols", DEFAULT_DATABENTO_SYMBOLS)
    stype_in = str(engine.databento_config.get("stype_in", DEFAULT_STYPE_IN))
    stype_out = str(engine.databento_config.get("stype_out", DEFAULT_STYPE_OUT))
    client = db.Historical(api_key)
    available_start, available_end = historical_dataset_available_range(client, dataset, hist_cfg)
    start, end = historical_bounds(hist_cfg, engine.timezone, max_end=available_end)
    enforce_historical_cost_guard(
        client,
        hist_cfg,
        dataset=dataset,
        symbols=symbols,
        schema=schema,
        stype_in=stype_in,
        start=start,
        end=end,
        limit=hist_cfg.get("limit"),
    )
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
            "available_start": str(available_start) if available_start is not None else None,
            "available_end": str(available_end) if available_end is not None else None,
        }
    )
    store, stype_out = historical_get_range(
        client,
        dataset=dataset,
        symbols=symbols,
        schema=schema,
        stype_in=stype_in,
        stype_out=stype_out,
        start=start,
        end=end,
        limit=hist_cfg.get("limit"),
        available_end=available_end,
    )
    trades = ensure_trade_symbol_column(store.to_df().reset_index(), store)
    if trades.empty:
        return []
    contract_symbol_regex = effective_contract_symbol_regex(
        trades,
        str(engine.databento_config.get("contract_symbol_regex", r"^ES[HMUZ]\d$")),
        allow_relaxation=bool(hist_cfg.get("allow_contract_symbol_regex_relaxation", False)),
        context={
            "dataset": dataset,
            "schema": schema,
            "symbols": symbols,
            "stype_in": stype_in,
            "stype_out": stype_out,
        },
    )
    bars = aggregate_trade_orderflow_1m(
        trades,
        timezone=engine.timezone,
        root_symbol=engine.symbol,
        contract_symbol_regex=contract_symbol_regex,
        rth_start=str(engine.databento_config.get("rth_start", "09:30:00")),
        rth_end=str(engine.databento_config.get("rth_end", "16:00:00")),
        complete_session_end=hist_cfg.get("complete_session_end"),
        large_trade_sizes=effective_large_trade_sizes(engine),
    )
    out = bars_from_orderflow_frame(bars, root_symbol=engine.symbol, timezone=engine.timezone, source="historical")
    max_seed_bars = int(hist_cfg.get("max_seed_bars", 0) or 0)
    if max_seed_bars > 0:
        out = out[-max_seed_bars:]
    print_json({"event": "historical_fetch_complete", "trades": len(trades), "bars": len(out)})
    return out


def historical_get_range(
    client: Any,
    *,
    dataset: str,
    symbols: Any,
    schema: str,
    stype_in: str,
    stype_out: str,
    start: Any,
    end: Any,
    limit: int | None = None,
    available_end: Any | None = None,
) -> tuple[Any, str]:
    try:
        store = client.timeseries.get_range(
            dataset=dataset,
            symbols=symbols,
            schema=schema,
            stype_in=stype_in,
            stype_out=stype_out,
            start=start,
            end=end,
            limit=limit,
        )
        return store, stype_out
    except Exception as exc:
        message = str(exc)
        if "data_end_after_available_end" in message:
            retry_end = available_end or historical_dataset_available_end(client, dataset)
            if retry_end is not None and pd.Timestamp(end) > pd.Timestamp(retry_end):
                print_json(
                    {
                        "event": "historical_fetch_retry",
                        "reason": "Requested end is after Databento available end; retrying with available end.",
                        "requested_end": str(end),
                        "retry_end": str(retry_end),
                    }
                )
                return historical_get_range(
                    client,
                    dataset=dataset,
                    symbols=symbols,
                    schema=schema,
                    stype_in=stype_in,
                    stype_out=stype_out,
                    start=start,
                    end=retry_end,
                    limit=limit,
                    available_end=retry_end,
                )
        if (
            stype_in == "parent"
            and stype_out == "raw_symbol"
            and ("symbology_invalid_request" in message or "Unable to process symbology" in message)
        ):
            fallback = "instrument_id"
            print_json(
                {
                    "event": "historical_fetch_retry",
                    "reason": "Databento rejected parent -> raw_symbol symbology; retrying with parent -> instrument_id.",
                    "stype_in": stype_in,
                    "stype_out": fallback,
                }
            )
            return historical_get_range(
                client,
                dataset=dataset,
                symbols=symbols,
                schema=schema,
                stype_in=stype_in,
                stype_out=fallback,
                start=start,
                end=end,
                limit=limit,
                available_end=available_end,
            )
        raise


def ensure_trade_symbol_column(frame: Any, store: Any) -> Any:
    if frame.empty or "contract_symbol" in frame.columns or "symbol" in frame.columns:
        return frame
    if "instrument_id" not in frame.columns:
        return frame
    out = frame.copy()
    mapping = store_symbol_mapping(store)
    if mapping:
        out["symbol"] = out["instrument_id"].map(lambda value: mapping.get(str(value), str(value)))
    else:
        out["symbol"] = out["instrument_id"].astype(str)
    return out


def store_symbol_mapping(store: Any) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for attr in ("mappings", "symbology"):
        value = getattr(store, attr, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                continue
        collect_symbol_mapping(value, mapping)
    return mapping


def collect_symbol_mapping(value: Any, mapping: dict[str, str]) -> None:
    if value is None:
        return
    if isinstance(value, dict):
        instrument_id = value.get("instrument_id") or value.get("instrumentId") or value.get("id")
        symbol = (
            value.get("symbol")
            or value.get("raw_symbol")
            or value.get("rawSymbol")
            or value.get("stype_out_symbol")
            or value.get("s")
        )
        if instrument_id is not None and symbol:
            mapping[str(instrument_id)] = str(symbol)
        for key, item in value.items():
            if isinstance(key, (int, str)):
                found = extract_symbol_value(item)
                if found:
                    key_text = str(key)
                    found_text = str(found)
                    if found_text.isdigit() and is_probable_raw_symbol_key(key_text):
                        mapping.setdefault(found_text, key_text)
                    elif not found_text.isdigit():
                        mapping[key_text] = found_text
            collect_symbol_mapping(item, mapping)
    elif isinstance(value, (list, tuple)):
        for item in value:
            collect_symbol_mapping(item, mapping)


def is_probable_raw_symbol_key(value: str) -> bool:
    text = value.strip()
    if not text or text.isdigit():
        return False
    metadata_keys = {
        "d0",
        "d1",
        "s",
        "symbol",
        "raw_symbol",
        "stype_out_symbol",
        "instrument_id",
        "instrumentId",
        "id",
    }
    return text not in metadata_keys and any(char.isalpha() for char in text)


def effective_contract_symbol_regex(
    trades: Any,
    configured_regex: str,
    *,
    allow_relaxation: bool = False,
    context: dict[str, Any] | None = None,
) -> str:
    column = "contract_symbol" if "contract_symbol" in trades.columns else "symbol" if "symbol" in trades.columns else None
    if column is None:
        return configured_regex
    symbols = trades[column].astype(str)
    try:
        if symbols.str.match(configured_regex, na=False).any():
            return configured_regex
    except Exception:
        return configured_regex
    payload = {
        "event": "historical_symbol_regex_unmatched",
        "reason": "No returned Databento symbols matched databento.contract_symbol_regex.",
        "contract_symbol_regex": configured_regex,
        "symbol_column": column,
        "sample_symbols": sorted(symbols.dropna().unique().tolist())[:10],
        "context": dict(context or {}),
    }
    if not allow_relaxation:
        print_json(
            {
                **payload,
                "impact": (
                    "Historical bars were not aggregated. Refusing to seed strategies from symbols "
                    "that cannot be proven to match the configured contract filter."
                ),
                "fix": (
                    "Verify Databento stype_out/symbology mapping or set "
                    "databento.historical.allow_contract_symbol_regex_relaxation: true only for a "
                    "controlled diagnostic run."
                ),
            },
            prefix="SYSTEM_ALERT",
        )
        raise RuntimeError(
            "No returned Databento symbols matched databento.contract_symbol_regex; "
            "refusing to relax the historical contract filter."
        )
    print_json(
        {
            **payload,
            "event": "historical_symbol_regex_relaxed",
            "allowed_by_config": True,
            "impact": (
                "Historical aggregation will use all returned symbols for this fetch because "
                "databento.historical.allow_contract_symbol_regex_relaxation is true."
            ),
        },
        prefix="SYSTEM_ALERT",
    )
    return r".+"


def historical_dataset_available_range(
    client: Any,
    dataset: str,
    hist_cfg: dict[str, Any],
) -> tuple[Any | None, Any | None]:
    if not bool(hist_cfg.get("clamp_end_to_available", True)):
        return None, None
    try:
        raw = client.metadata.get_dataset_range(dataset)
    except Exception as exc:
        print_json(
            {
                "event": "historical_available_range_unavailable",
                "dataset": dataset,
                "reason": str(exc),
            }
        )
        return None, None
    if not isinstance(raw, dict):
        return None, None
    start = parse_available_range_timestamp(raw.get("start") or raw.get("start_date"))
    end = parse_available_range_timestamp(raw.get("end") or raw.get("end_date"))
    return start, end


def historical_dataset_available_end(client: Any, dataset: str) -> Any | None:
    start, end = historical_dataset_available_range(client, dataset, {"clamp_end_to_available": True})
    return end


def parse_available_range_timestamp(value: Any) -> Any | None:
    if is_missing_or_blank(value):
        return None
    try:
        timestamp = pd.Timestamp(value)
    except Exception:
        return None
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def enforce_historical_cost_guard(
    client: Any,
    hist_cfg: dict[str, Any],
    *,
    dataset: str,
    symbols: Any,
    schema: str,
    stype_in: str,
    start: Any,
    end: Any,
    limit: int | None = None,
) -> dict[str, Any]:
    guard = dict(hist_cfg.get("cost_guard", {}))
    if not bool(guard.get("enabled", True)):
        payload = {
            "event": "historical_fetch_blocked_by_disabled_cost_guard",
            "reason": "Historical Databento cost guard is disabled; refusing to call timeseries.get_range without a cost estimate.",
            "fix": "Set databento.historical.cost_guard.enabled: true with allow_paid_downloads: false and max_cost_usd: 0.0 for zero-cost operation.",
            "metadata_only": True,
            "databento_api_calls_attempted": [],
            "timeseries_get_range_attempted": False,
            "guarded_operation": "timeseries.get_range",
        }
        print_json(
            payload,
            prefix="SYSTEM_ALERT",
        )
        raise RuntimeError("Databento historical cost guard is disabled; refusing unguarded historical fetch.")

    fail_if_unavailable = bool(guard.get("fail_if_estimate_unavailable", True))
    allow_paid = bool(guard.get("allow_paid_downloads", False))
    max_cost = float(guard.get("max_cost_usd", 0.0))
    request = without_none(
        {
            "dataset": dataset,
            "symbols": symbols,
            "schema": schema,
            "stype_in": stype_in,
            "start": start,
            "end": end,
            "limit": limit,
        }
    )
    metadata_api_calls_attempted = ["metadata.get_cost"]
    try:
        cost = float(client.metadata.get_cost(**request))
    except Exception as exc:
        payload = {
            "event": "historical_cost_estimate_unavailable",
            "dataset": dataset,
            "schema": schema,
            "symbols": symbols,
            "error": str(exc),
            "metadata_only": True,
            "databento_api_calls_attempted": metadata_api_calls_attempted,
            "timeseries_get_range_attempted": False,
            "guarded_operation": "timeseries.get_range",
        }
        print_json(payload, prefix="SYSTEM_ALERT")
        if fail_if_unavailable:
            raise RuntimeError(
                "Databento historical cost estimate is unavailable; refusing to fetch historical data."
            ) from exc
        return {**payload, "enabled": True, "allowed": True}

    billable_size = None
    metadata_api_calls_attempted.append("metadata.get_billable_size")
    try:
        billable_size = int(client.metadata.get_billable_size(**request))
    except Exception as exc:
        print_json(
            {
                "event": "historical_billable_size_unavailable",
                "dataset": dataset,
                "schema": schema,
                "symbols": symbols,
                "error": str(exc),
                "metadata_only": True,
                "databento_api_calls_attempted": metadata_api_calls_attempted,
                "timeseries_get_range_attempted": False,
                "guarded_operation": "timeseries.get_range",
            },
            prefix="SYSTEM_ALERT",
        )

    payload = {
        "event": "historical_cost_estimate",
        "dataset": dataset,
        "schema": schema,
        "symbols": symbols,
        "stype_in": stype_in,
        "start": str(start),
        "end": str(end),
        "limit": limit,
        "estimated_cost_usd": cost,
        "billable_size_bytes": billable_size,
        "allow_paid_downloads": allow_paid,
        "max_cost_usd": max_cost,
        "metadata_only": True,
        "databento_api_calls_attempted": metadata_api_calls_attempted,
        "timeseries_get_range_attempted": False,
        "guarded_operation": "timeseries.get_range",
    }
    print_json(payload)
    if cost > max_cost or (cost > 0.0 and not allow_paid):
        print_json(
            {
                **payload,
                "event": "historical_fetch_blocked_by_cost_guard",
                "reason": "Estimated Databento historical request cost is above the configured allowance.",
            },
            prefix="SYSTEM_ALERT",
        )
        raise RuntimeError(
            f"Refusing Databento historical fetch because estimated cost is ${cost:.6f}; "
            f"configured max_cost_usd is ${max_cost:.6f}."
        )
    return {**payload, "enabled": True, "allowed": True}


def live_cost_guard_report(live_cfg: dict[str, Any]) -> dict[str, Any]:
    guard = dict(live_cfg.get("cost_guard", {}))
    enabled = bool(guard.get("enabled", True))
    allow_subscription = bool(guard.get("allow_live_subscription", False))
    acknowledged = bool(guard.get("acknowledge_live_data_may_be_billable", False))
    return {
        "enabled": enabled,
        "allowed": enabled and allow_subscription and acknowledged,
        "allow_live_subscription": allow_subscription,
        "acknowledge_live_data_may_be_billable": acknowledged,
    }


def enforce_live_subscription_cost_guard(
    live_cfg: dict[str, Any],
    *,
    dataset: str,
    symbols: Any,
    schema: str,
    stype_in: str,
) -> dict[str, Any]:
    report = live_cost_guard_report(live_cfg)
    payload = {
        "event": "live_cost_guard",
        "dataset": dataset,
        "schema": schema,
        "symbols": symbols,
        "stype_in": stype_in,
        **report,
    }
    if report["allowed"]:
        print_json(payload)
        return payload
    reason = (
        "Databento live cost guard is disabled; refusing to open a live subscription without "
        "an enabled paid-data guard."
        if not report["enabled"]
        else (
            "Databento live subscriptions may be billable and cannot be cost-estimated "
            "before subscribe(). Explicit live cost acknowledgement is required."
        )
    )
    blocked = {
        **payload,
        "event": "live_subscription_blocked_by_cost_guard",
        "reason": reason,
        "fix": (
            "After confirming the account's Databento live-data billing/entitlements, set "
            "databento.live.cost_guard.enabled: true, "
            "databento.live.cost_guard.allow_live_subscription: true and "
            "databento.live.cost_guard.acknowledge_live_data_may_be_billable: true."
        ),
        "live_subscription_attempted": False,
    }
    print_json(blocked, prefix="SYSTEM_ALERT")
    raise RuntimeError("Refusing Databento live subscription because live cost guard is not explicitly acknowledged.")


def replay_bars(engine: SignalEngine, path: Path, args: argparse.Namespace) -> dict[str, Any]:
    bars = read_bars_file(
        path,
        root_symbol=engine.symbol,
        timezone=engine.timezone,
        source="replay",
        required_source_columns=engine.data_plan.get("source_columns", []),
    )
    if len(bars) < 2:
        raise RuntimeError(f"replay requires at least two bars: {path}")
    seed_count = int(engine.engine_config.get("replay_seed_bars", 1000))
    seed_count = max(0, min(seed_count, len(bars) - 1))
    if seed_count:
        engine.seed([replace_bar_source(bar, "replay_seed") for bar in bars[:seed_count]], source="replay_seed")
    replay_store_count_start = len(engine.store.bars())
    replay_source_filter_drops_start = engine.source_contract_filter_drops
    replay_quality_drops_start = engine.source_bar_quality_drops
    replayed = 0
    starting_alerts = engine.alert_count
    previous = bars[seed_count]
    latest_replay_utc = normalize_utc_timestamp(previous.timestamp_utc)
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
        latest_replay_utc = normalize_utc_timestamp(current.timestamp_utc)
        engine.on_entry_tick(entry_tick)
        replayed += 1
        if args.replay_stop_after_signal and engine.alert_count > starting_alerts:
            break
        previous = current
    entry_alerts = engine.alert_count - starting_alerts
    replay_store_count_end = len(engine.store.bars())
    accepted_replay_source_bars = max(0, replay_store_count_end - replay_store_count_start)
    source_contract_filter_replay_drops = max(
        0,
        engine.source_contract_filter_drops - replay_source_filter_drops_start,
    )
    source_bar_quality_replay_drops = max(0, engine.source_bar_quality_drops - replay_quality_drops_start)
    require_signal = bool(getattr(args, "replay_require_signal", False))
    require_healthy_strategies = bool(getattr(args, "replay_require_healthy_strategies", False))
    strategy_health = engine.strategy_health_report()
    disabled_strategies = [item for item in strategy_health if bool(item.get("disabled", False))]
    runtime_error_strategies = [
        item for item in strategy_health if int(item.get("runtime_error_count", 0) or 0) > 0
    ]
    active_strategies = [item for item in strategy_health if not bool(item.get("disabled", False))]
    unevaluated_active_strategies = [
        item
        for item in active_strategies
        if int(item.get("evaluated_strategy_row_count", 0) or 0) <= 0
    ]
    strategy_health_ok = (
        bool(active_strategies)
        and not disabled_strategies
        and not runtime_error_strategies
        and not unevaluated_active_strategies
    )
    source_contract_filter_starved = (
        replayed > 0
        and accepted_replay_source_bars <= 0
        and source_contract_filter_replay_drops >= replayed
    )
    source_bar_quality_starved = (
        replayed > 0
        and accepted_replay_source_bars <= 0
        and source_bar_quality_replay_drops >= replayed
    )
    source_bar_quality_degraded = source_bar_quality_replay_drops > 0
    replay_health_ok = (
        strategy_health_ok
        and not source_contract_filter_starved
        and not source_bar_quality_degraded
    )
    ok = (entry_alerts > 0 if require_signal else True) and (
        replay_health_ok if require_healthy_strategies else True
    )
    if require_signal and entry_alerts <= 0:
        print_json(
            {
                "event": "replay_required_signal_missing",
                "path": str(path),
                "source_bars": len(bars),
                "seed_bars": seed_count,
                "replayed_bars": replayed,
                "entry_alerts": entry_alerts,
                "reason": "Replay completed without an ENTRY_SIGNAL while --replay-require-signal was enabled.",
            },
            prefix="SYSTEM_ALERT",
        )
    if require_healthy_strategies and not replay_health_ok:
        print_json(
            {
                "event": "replay_strategy_health_failed",
                "path": str(path),
                "source_bars": len(bars),
                "seed_bars": seed_count,
                "replayed_bars": replayed,
                "active_strategy_count": len(active_strategies),
                "disabled_strategy_count": len(disabled_strategies),
                "runtime_error_strategy_count": len(runtime_error_strategies),
                "unevaluated_active_strategy_count": len(unevaluated_active_strategies),
                "accepted_replay_source_bars": accepted_replay_source_bars,
                "source_contract_filter_replay_drops": source_contract_filter_replay_drops,
                "source_contract_filter_starved": source_contract_filter_starved,
                "source_contract_filter": engine.source_contract_filter_report(),
                "source_bar_quality": engine.source_bar_quality_report(),
                "source_bar_quality_replay_drops": source_bar_quality_replay_drops,
                "source_bar_quality_starved": source_bar_quality_starved,
                "source_bar_quality_degraded": source_bar_quality_degraded,
                "last_source_bar_quality_report": engine.last_source_bar_quality_report,
                "disabled_strategy_ids": [item.get("strategy_id") for item in disabled_strategies],
                "runtime_error_strategy_ids": [item.get("strategy_id") for item in runtime_error_strategies],
                "unevaluated_active_strategy_ids": [
                    item.get("strategy_id") for item in unevaluated_active_strategies
                ],
                "reason": (
                    "Replay strategy health failed while --replay-require-healthy-strategies was enabled."
                ),
                "impact": (
                    "A replay that leaves strategies disabled, errored, unevaluated, starved by contract filtering, "
                    "or dropping source bars for data quality is not a safe smoke test for live signal generation."
                ),
            },
            prefix="SYSTEM_ALERT",
        )
    payload = {
        "event": "replay_complete",
        "ok": ok,
        "path": str(path),
        "source_bars": len(bars),
        "seed_bars": seed_count,
        "replayed_bars": replayed,
        "entry_alerts": entry_alerts,
        "require_signal": require_signal,
        "require_healthy_strategies": require_healthy_strategies,
        "strategy_health_ok": strategy_health_ok,
        "replay_health_ok": replay_health_ok,
        "active_strategy_count": len(active_strategies),
        "disabled_strategy_count": len(disabled_strategies),
        "runtime_error_strategy_count": len(runtime_error_strategies),
        "unevaluated_active_strategy_count": len(unevaluated_active_strategies),
        "accepted_replay_source_bars": accepted_replay_source_bars,
        "source_contract_filter_replay_drops": source_contract_filter_replay_drops,
        "source_contract_filter_starved": source_contract_filter_starved,
        "source_bar_quality_replay_drops": source_bar_quality_replay_drops,
        "source_bar_quality_starved": source_bar_quality_starved,
        "source_bar_quality_degraded": source_bar_quality_degraded,
        "last_source_bar_quality_report": engine.last_source_bar_quality_report,
        "dry_run_alerts": bool(engine.dry_run_alerts),
        "trade_setups": engine.setup_notice_count,
        "pending_signals": len(engine.pending),
        "pending_expired_count": engine.pending_expired_count,
        "pending_status": engine.pending_status(now_utc=latest_replay_utc),
        "strategy_health": strategy_health,
        "alert_file": {
            "enabled": engine.alerts_path is not None,
            "path": str(engine.alerts_path) if engine.alerts_path else None,
            "writes_succeeded": engine.alert_sink.writes_succeeded,
            "writes_failed": engine.alert_sink.writes_failed,
            "duplicates_skipped": engine.alert_sink.duplicates_skipped,
            "last_error_type": engine.alert_sink.last_error_type,
            "last_error": engine.alert_sink.last_error,
        },
        "setup_alerts": {
            "enabled": bool(engine.setup_alerts_config.get("enabled", False)),
            "path": str(engine.setup_alerts_path) if engine.setup_alerts_path else None,
            "writes_succeeded": engine.setup_notice_sink.writes_succeeded,
            "writes_failed": engine.setup_notice_sink.writes_failed,
            "duplicates_skipped": engine.setup_notice_sink.duplicates_skipped,
            "last_error_type": engine.setup_notice_sink.last_error_type,
            "last_error": engine.setup_notice_sink.last_error,
        },
        "execution_intents": {
            "enabled": bool(engine.execution_intents_config.get("enabled", False)),
            "path": str(engine.execution_intents_path) if engine.execution_intents_path else None,
            "writes_succeeded": engine.execution_intent_sink.writes_succeeded,
            "writes_failed": engine.execution_intent_sink.writes_failed,
            "duplicates_skipped": engine.execution_intent_sink.duplicates_skipped,
            "freshness_skipped": engine.execution_intent_sink.freshness_skipped,
            "last_freshness_skip_reason": engine.execution_intent_sink.last_freshness_skip_reason,
            "last_error_type": engine.execution_intent_sink.last_error_type,
            "last_error": engine.execution_intent_sink.last_error,
        },
        "source_contract_filter": engine.source_contract_filter_report(),
        "source_bar_quality": engine.source_bar_quality_report(),
    }
    print_json(payload)
    return payload


def run_live(
    engine: SignalEngine,
    *,
    once: bool,
    max_runtime: float,
    live_client_factory: Any | None = None,
    metadata_client: Any | None = None,
) -> int:
    live_cfg = dict(engine.databento_config.get("live", {}))
    dataset = str(engine.databento_config.get("dataset", DEFAULT_DATASET))
    schema = str(engine.databento_config.get("schema", DEFAULT_SCHEMA))
    symbols = engine.databento_config.get("symbols", DEFAULT_DATABENTO_SYMBOLS)
    stype_in = str(engine.databento_config.get("stype_in", DEFAULT_STYPE_IN))
    metadata_client_for_live = metadata_client
    enforce_live_subscription_cost_guard(
        live_cfg,
        dataset=dataset,
        symbols=symbols,
        schema=schema,
        stype_in=stype_in,
    )
    enforce_live_metadata_preflight_guard(engine)
    enforce_output_sink_safety_before_live(engine)
    api_key = databento_api_key(engine.databento_config)
    if bool(live_cfg.get("metadata_preflight", True)):
        if metadata_client_for_live is None:
            import databento as db

            metadata_client_for_live = db.Historical(api_key)
        try:
            report = check_databento_metadata(engine, client=metadata_client_for_live)
        except Exception as exc:
            print_json(
                {
                    "event": "live_metadata_preflight_failed",
                    "dataset": dataset,
                    "schema": schema,
                    "symbols": symbols,
                    "stype_in": stype_in,
                    "timeseries_download_attempted": False,
                    "live_subscription_attempted": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "reason": (
                        "Databento metadata/schema/field/symbology/cost validation failed before live subscribe."
                    ),
                    "impact": "The live subscription was not opened, so no live market data was consumed.",
                },
                prefix="SYSTEM_ALERT",
            )
            engine.play_operator_sound("system")
            raise
        print_json(live_metadata_preflight_payload(report))

    live_instrument_symbol_map: dict[Any, str] = {}
    resolve_symbols = bool(live_cfg.get("resolve_instrument_symbols", True))
    live_symbol_reference_utc: Any | None = None
    if resolve_symbols:
        try:
            if metadata_client_for_live is None:
                import databento as db

                metadata_client_for_live = db.Historical(api_key)
            available_end = historical_dataset_available_end(metadata_client_for_live, dataset)
            live_symbol_reference_utc = available_end
            live_instrument_symbol_map = resolve_live_instrument_symbol_map(
                metadata_client_for_live,
                dataset=dataset,
                symbols=symbols,
                stype_in=stype_in,
                available_end=available_end,
            )
            print_json(
                {
                    "event": "live_instrument_symbol_map_ready",
                    "dataset": dataset,
                    "symbols": symbols,
                    "stype_in": stype_in,
                    "mapping_count": len({str(key) for key in live_instrument_symbol_map}),
                    "sample": sample_symbol_map(live_instrument_symbol_map),
                }
            )
        except Exception as exc:
            payload = {
                "event": "live_instrument_symbol_map_unavailable",
                "dataset": dataset,
                "symbols": symbols,
                "stype_in": stype_in,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "contract_symbol_regex": engine.contract_symbol_regex,
                "impact": (
                    "Live records may only expose instrument_id. Without an instrument-id to raw-contract map, "
                    "contract filtering and contract-matched entries can reject otherwise valid ES ticks."
                ),
            }
            print_json(payload, prefix="SYSTEM_ALERT")
            engine.play_operator_sound("system")
            if bool(live_cfg.get("fail_without_live_symbol_map", True)):
                raise RuntimeError(
                    "Databento live instrument symbol map is unavailable; refusing to start live mode."
                ) from exc
    elif engine.contract_symbol_regex and stype_in != "raw_symbol":
        print_json(
            {
                "event": "live_instrument_symbol_map_disabled",
                "symbols": symbols,
                "stype_in": stype_in,
                "contract_symbol_regex": engine.contract_symbol_regex,
                "impact": (
                    "Live records that only include instrument_id may not match the contract regex, "
                    "so valid ticks can be ignored."
                ),
            },
            prefix="SYSTEM_ALERT",
        )

    if live_client_factory is None:
        import databento as db

        live_client_factory = db.Live

    builder = TradeBarBuilder(
        root_symbol=engine.symbol,
        timezone=engine.timezone,
        large_trade_sizes=effective_large_trade_sizes(engine),
        active_contract_mode=str(engine.databento_config.get("active_contract_mode", "highest_session_volume")),
        delta_method=engine.delta_method,
        contract_symbol_regex=engine.databento_config.get("contract_symbol_regex"),
    )
    try:
        client = live_client_factory(
            key=api_key,
            reconnect_policy=str(live_cfg.get("reconnect_policy", "reconnect")),
            heartbeat_interval_s=live_cfg.get("heartbeat_interval_s"),
        )
    except Exception as exc:
        print_json(
            {
                "event": "live_client_create_failed",
                "dataset": dataset,
                "schema": schema,
                "symbols": symbols,
                "stype_in": stype_in,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "reason": "Databento live client could not be created.",
                "impact": "The live subscription was not opened, so no live market data was consumed.",
            },
            prefix="SYSTEM_ALERT",
        )
        engine.play_operator_sound("system")
        raise RuntimeError("Databento live client creation failed.") from exc
    completed_count = 0
    stop_requested = threading.Event()
    live_errors: list[str] = []
    drop_partial_first_live_bar = bool(live_cfg.get("drop_partial_first_live_bar", True))
    first_live_drop_minute_utc: pd.Timestamp | None = None
    quote_missing_warned = False
    health = LiveHealth(started_monotonic=time.monotonic())
    health.contract_symbol_regex = builder.contract_symbol_regex
    strategy_evaluation_baseline = strategy_evaluation_totals(engine.strategy_health_report())
    flush_completed_bars_on_heartbeat = bool(live_cfg.get("flush_completed_bars_on_heartbeat", True))
    bar_flush_delay_seconds = float(live_cfg.get("bar_flush_delay_seconds", 2.0))
    maintenance_interval = float(live_cfg.get("maintenance_interval_seconds", 1.0))
    startup_grace_seconds = float(live_cfg.get("startup_grace_seconds", 3.0))
    shutdown_grace_seconds = float(live_cfg.get("shutdown_grace_seconds", 3.0))
    state_lock_timeout_seconds = float(live_cfg.get("state_lock_timeout_seconds", 5.0))
    stop_on_state_lock_timeout = bool(live_cfg.get("stop_on_state_lock_timeout", True))
    live_state_lock = threading.RLock()
    stop_reason: str | None = None

    def request_client_stop(reason: str) -> None:
        nonlocal stop_reason
        if stop_reason is None:
            stop_reason = reason
        stop_requested.set()
        try:
            client.stop()
        except Exception:
            pass

    def acquire_live_state_lock(operation: str) -> bool:
        if state_lock_timeout_seconds <= 0:
            live_state_lock.acquire()
            return True
        acquired = live_state_lock.acquire(timeout=state_lock_timeout_seconds)
        if acquired:
            return True
        now = time.monotonic()
        repeat_seconds = float(live_cfg.get("alert_repeat_seconds", 120.0))
        if should_emit_live_health_alert(health, "live_state_lock_timeout", now, repeat_seconds):
            print_json(
                {
                    "event": "live_state_lock_timeout",
                    "operation": operation,
                    "timeout_seconds": state_lock_timeout_seconds,
                    "stop_on_state_lock_timeout": stop_on_state_lock_timeout,
                    "records_received": health.records_received,
                    "trade_ticks_received": health.ticks_received,
                    "completed_source_bars": health.completed_bars,
                    "reason": "The live status loop could not acquire the shared live-state lock quickly enough.",
                    "impact": (
                        "Databento callbacks or strategy processing may be stalled. "
                        "Live status and maintenance snapshots cannot be trusted until the lock is released."
                    ),
                },
                prefix="SYSTEM_ALERT",
            )
            engine.play_operator_sound("system")
        if stop_on_state_lock_timeout:
            request_client_stop("live_state_lock_timeout")
        return False

    def process_completed_bars(completed: list[SourceMinuteBar]) -> None:
        nonlocal completed_count, first_live_drop_minute_utc
        for bar in completed:
            if bar.source == "live_heartbeat":
                health.heartbeat_flushed_bars += 1
            bar_minute_utc = normalize_utc_timestamp(bar.timestamp_utc)
            if drop_partial_first_live_bar and (
                first_live_drop_minute_utc is None or bar_minute_utc == first_live_drop_minute_utc
            ):
                if first_live_drop_minute_utc is None:
                    first_live_drop_minute_utc = bar_minute_utc
                health.dropped_partial_bars += 1
                print_json(
                    {
                        "event": "live_partial_first_bar_dropped",
                        "source_bar_timestamp": format_timestamp(bar_minute_utc),
                        "first_dropped_minute_utc": format_timestamp(first_live_drop_minute_utc),
                        "drop_scope": "first_completed_minute",
                        "contract_symbol": bar.contract_symbol,
                        "volume": bar.volume,
                        "signed_volume": bar.signed_volume,
                        "delta_method": engine.delta_method,
                        "source": bar.source,
                        "reason": "First live minute may be partial because subscription can start after the minute opened.",
                    }
                )
                continue
            engine.on_completed_source_bar(bar)
            completed_count += 1
            health.completed_bars += 1
            health.last_completed_bar_monotonic = time.monotonic()

    def run_live_maintenance(now_utc: Any) -> int:
        if flush_completed_bars_on_heartbeat:
            flushed = builder.flush_completed_bars(
                now_utc=now_utc,
                flush_delay_seconds=bar_flush_delay_seconds,
                source="live_heartbeat",
            )
            process_completed_bars(flushed)
        engine.expire_stale_pending_signals(now_utc=now_utc, source="live_heartbeat")
        return completed_count

    def handle_record(record: Any) -> None:
        nonlocal completed_count, quote_missing_warned
        try:
            now = time.monotonic()
            health.records_received += 1
            health.last_record_monotonic = now
            live_symbol_map = merged_symbol_maps(
                getattr(client, "symbology_map", None),
                live_instrument_symbol_map,
            )
            tick = live_record_to_tick(
                record,
                default_contract_symbol=str(symbols),
                symbology_map=live_symbol_map,
                require_trade_action=normalize_schema_name(schema) == "mbp-1",
            )
            if tick is None:
                return
            health.ticks_received += 1
            health.last_tick_monotonic = now
            update_live_tick_clock_health(health, tick, received_at_utc=pd.Timestamp.utcnow())
            if (
                engine.delta_method == "price_vs_quote"
                and not quote_missing_warned
                and (tick.bid_price is None or tick.ask_price is None)
            ):
                quote_missing_warned = True
                print_json(
                    {
                        "event": "delta_method_unclassified_tick",
                        "delta_method": engine.delta_method,
                        "schema": str(engine.databento_config.get("schema", DEFAULT_SCHEMA)),
                        "reason": "No top-of-book bid/ask was present on this tick; quote-based selected delta will treat this tick as unclassified instead of falling back to another classifier.",
                    }
                )
            ignored_before = builder.late_ticks_ignored
            unmatched_before = builder.unmatched_contract_ticks_ignored
            with live_state_lock:
                completed = builder.update(tick)
                process_completed_bars(completed)
                late_tick_ignored = builder.late_ticks_ignored > ignored_before
                unmatched_tick_ignored = builder.unmatched_contract_ticks_ignored > unmatched_before
                if unmatched_tick_ignored:
                    health.accepted_contract_ticks = dict(builder.accepted_contract_ticks)
                    health.unmatched_contract_ticks_ignored = builder.unmatched_contract_ticks_ignored
                    health.unmatched_contract_ticks = dict(builder.unmatched_contract_ticks)
                    health.last_unmatched_contract_tick = copy.deepcopy(builder.last_unmatched_contract_tick)
                    repeat_seconds = float(live_cfg.get("alert_repeat_seconds", 120.0))
                    if should_emit_live_health_alert(
                        health,
                        "live_unmatched_contract_symbol_ignored",
                        now,
                        repeat_seconds,
                    ):
                        print_json(
                            {
                                "event": "live_unmatched_contract_symbol_ignored",
                                "unmatched_contract_ticks_ignored": health.unmatched_contract_ticks_ignored,
                                "contract_symbol_regex": health.contract_symbol_regex,
                                "last_unmatched_contract_tick": health.last_unmatched_contract_tick,
                                "unmatched_contract_ticks": top_count_items(health.unmatched_contract_ticks),
                                "accepted_contract_ticks": top_count_items(health.accepted_contract_ticks),
                                "reason": "A trade tick was ignored because its contract symbol did not match databento.contract_symbol_regex.",
                                "impact": "The tick was not aggregated into source bars and was not used as an entry trigger.",
                            },
                            prefix="SYSTEM_ALERT",
                        )
                        engine.play_operator_sound("system")
                    if bool(live_cfg.get("stop_on_unmatched_contract_symbol", False)):
                        request_client_stop("unmatched_contract_symbol")
                elif late_tick_ignored:
                    health.accepted_contract_ticks = dict(builder.accepted_contract_ticks)
                    health.late_trade_ticks_ignored = builder.late_ticks_ignored
                    health.last_late_trade_tick = copy.deepcopy(builder.last_late_tick)
                    repeat_seconds = float(live_cfg.get("alert_repeat_seconds", 120.0))
                    if should_emit_live_health_alert(
                        health,
                        "live_late_trade_tick_ignored",
                        now,
                        repeat_seconds,
                    ):
                        print_json(
                            {
                                "event": "live_late_trade_tick_ignored",
                                "late_trade_ticks_ignored": health.late_trade_ticks_ignored,
                                "last_late_trade_tick": health.last_late_trade_tick,
                                "reason": "A trade tick arrived for a minute that has already been finalized; it was ignored to avoid duplicate or revised source bars.",
                            },
                            prefix="SYSTEM_ALERT",
                        )
                        engine.play_operator_sound("system")
                else:
                    health.accepted_contract_ticks = dict(builder.accepted_contract_ticks)
                    engine.on_entry_tick(tick)
                completed_seen = completed_count
            if once and completed_seen > 0:
                request_client_stop("once_completed_source_bar")
        except Exception as exc:  # noqa: BLE001 - callback errors must surface and stop live mode.
            live_errors.append(str(exc))
            print_json(
                {
                    "event": "live_callback_error",
                    "dataset": dataset,
                    "schema": schema,
                    "symbols": symbols,
                    "stype_in": stype_in,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "records_received": health.records_received,
                    "trade_ticks_received": health.ticks_received,
                    "completed_source_bars": health.completed_bars,
                    "reason": "An exception occurred while processing a Databento live record callback.",
                    "impact": "Live mode is stopping because callback state may be inconsistent.",
                },
                prefix="SYSTEM_ALERT",
            )
            engine.play_operator_sound("system")
            request_client_stop("live_callback_error")

    def handle_exception(exc: Exception) -> None:
        live_errors.append(str(exc))
        print_json(
            {
                "event": "live_exception",
                "dataset": dataset,
                "schema": schema,
                "symbols": symbols,
                "stype_in": stype_in,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "records_received": health.records_received,
                "trade_ticks_received": health.ticks_received,
                "completed_source_bars": health.completed_bars,
                "reason": "The Databento live client invoked its exception callback.",
                "impact": "Live mode is stopping because the stream reported an asynchronous exception.",
            },
            prefix="SYSTEM_ALERT",
        )
        engine.play_operator_sound("system")
        request_client_stop("live_exception")

    try:
        client.add_callback(handle_record, handle_exception)
    except Exception as exc:
        stop_report = stop_live_client(client, shutdown_grace_seconds=shutdown_grace_seconds)
        print_json(
            {
                "event": "live_callback_registration_failed",
                "dataset": dataset,
                "schema": schema,
                "symbols": symbols,
                "stype_in": stype_in,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "reason": "Databento live callbacks could not be registered before subscription.",
                "impact": "The live subscription was not opened, so no live market data was consumed.",
                **stop_report,
            },
            prefix="SYSTEM_ALERT",
        )
        engine.play_operator_sound("system")
        raise RuntimeError("Databento live callback registration failed.") from exc
    subscribe_symbols = symbols
    subscribe_stype_in = stype_in
    if (
        bool(live_cfg.get("subscribe_resolved_raw_symbols", True))
        and live_instrument_symbol_map
        and stype_in != "raw_symbol"
    ):
        resolved_symbols = resolved_raw_subscription_symbols(
            live_instrument_symbol_map,
            contract_symbol_regex=engine.contract_symbol_regex,
            reference_utc=live_symbol_reference_utc,
            max_symbols=int(live_cfg.get("max_resolved_raw_symbols", 2) or 0),
        )
        if resolved_symbols:
            subscribe_symbols = resolved_symbols
            subscribe_stype_in = "raw_symbol"
            print_json(
                {
                    "event": "live_resolved_raw_symbol_subscription",
                    "original_symbols": symbols,
                    "original_stype_in": stype_in,
                    "symbols": subscribe_symbols,
                    "symbol_count": len(resolved_symbols),
                    "contract_symbol_regex": engine.contract_symbol_regex,
                    "reason": "Resolved parent symbology to raw outright contracts before subscribing.",
                }
            )
        else:
            print_json(
                {
                    "event": "live_resolved_raw_symbol_subscription_unavailable",
                    "original_symbols": symbols,
                    "original_stype_in": stype_in,
                    "contract_symbol_regex": engine.contract_symbol_regex,
                    "reason": "No resolved raw symbols matched the configured contract filter; using the original subscription.",
                },
                prefix="SYSTEM_ALERT",
            )
    subscribe_args = {
        "dataset": dataset,
        "schema": schema,
        "symbols": subscribe_symbols,
        "stype_in": subscribe_stype_in,
    }
    if live_cfg.get("start"):
        subscribe_args["start"] = live_cfg["start"]
    print_json({"event": "live_subscribe", **subscribe_args, "delta_method": engine.delta_method})
    try:
        client.subscribe(**subscribe_args)
    except Exception as exc:
        stop_report = stop_live_client(client, shutdown_grace_seconds=shutdown_grace_seconds)
        print_json(
            {
                "event": "live_subscribe_failed",
                **subscribe_args,
                "delta_method": engine.delta_method,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "reason": "Databento live subscription failed before the client was started.",
                "impact": "The live stream did not start, so no live market data was consumed.",
                **stop_report,
            },
            prefix="SYSTEM_ALERT",
        )
        engine.play_operator_sound("system")
        raise RuntimeError("Databento live subscribe failed.") from exc
    try:
        client.start()
    except Exception as exc:
        stop_report = stop_live_client(client, shutdown_grace_seconds=shutdown_grace_seconds)
        print_json(
            {
                "event": "live_start_failed",
                **subscribe_args,
                "delta_method": engine.delta_method,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "reason": "Databento live client failed during start().",
                "impact": "The live stream did not become active, so no live market data was consumed.",
                **stop_report,
            },
            prefix="SYSTEM_ALERT",
        )
        engine.play_operator_sound("system")
        raise RuntimeError("Databento live start failed.") from exc
    startup_deadline = time.monotonic() + startup_grace_seconds
    while startup_grace_seconds > 0:
        if bool(client.is_connected() if callable(client.is_connected) else client.is_connected):
            break
        if time.monotonic() >= startup_deadline:
            break
        time.sleep(0.05)
    startup_connected = bool(client.is_connected() if callable(client.is_connected) else client.is_connected)
    if not startup_connected:
        payload = {
            "event": "live_startup_disconnected",
            "dataset": subscribe_args["dataset"],
            "schema": subscribe_args["schema"],
            "symbols": subscribe_args["symbols"],
            "stype_in": subscribe_args["stype_in"],
            "startup_grace_seconds": startup_grace_seconds,
            "reason": "Databento live client was not connected after startup.",
        }
        print_json(payload, prefix="SYSTEM_ALERT")
        engine.play_operator_sound("system")
        try:
            client.stop()
        except Exception:
            pass
        raise RuntimeError("Databento live client was not connected after startup.")
    print_json(
        {
            "event": "live_started",
            "connected": startup_connected,
            "delta_method": engine.delta_method,
            "message": "Databento live stream started; waiting for trade ticks.",
        }
    )

    interrupted = False

    def request_stop(*_: Any) -> None:
        nonlocal interrupted
        interrupted = True
        request_client_stop("signal")

    previous_signal_handlers = install_live_signal_handlers(request_stop)
    try:
        deadline = time.monotonic() + max_runtime if max_runtime > 0 else None
        heartbeat_interval = float(live_cfg.get("status_interval_seconds", 60.0))
        next_heartbeat = time.monotonic() + heartbeat_interval
        next_maintenance = time.monotonic() + maintenance_interval if maintenance_interval > 0 else None
        while not stop_requested.is_set():
            if deadline is not None and time.monotonic() >= deadline:
                request_client_stop("max_runtime")
                break
            now = time.monotonic()
            if next_maintenance is not None and now >= next_maintenance:
                maintenance_utc = pd.Timestamp.utcnow()
                if not acquire_live_state_lock("maintenance"):
                    next_maintenance = time.monotonic() + maintenance_interval
                    if stop_requested.is_set():
                        break
                    continue
                try:
                    completed_seen = run_live_maintenance(maintenance_utc)
                finally:
                    live_state_lock.release()
                if once and completed_seen > 0:
                    request_client_stop("once_completed_source_bar")
                    break
                next_maintenance = now + maintenance_interval
            if heartbeat_interval > 0 and now >= next_heartbeat:
                is_connected = client.is_connected() if callable(client.is_connected) else bool(client.is_connected)
                connected = bool(is_connected)
                heartbeat_utc = pd.Timestamp.utcnow()
                if not acquire_live_state_lock("status"):
                    next_heartbeat = time.monotonic() + heartbeat_interval
                    if stop_requested.is_set():
                        break
                    continue
                try:
                    if next_maintenance is None:
                        completed_count = run_live_maintenance(heartbeat_utc)
                    pending_signals = len(engine.pending)
                    strategy_health = engine.strategy_health_report()
                    strategy_evaluation = live_strategy_evaluation_summary(
                        strategy_health,
                        completed_source_bars=health.completed_bars,
                        data_plan=engine.data_plan,
                        live_cfg=live_cfg,
                        baseline=strategy_evaluation_baseline,
                    )
                    pending_status = engine.pending_status(now_utc=heartbeat_utc)
                    operator_sound = engine.operator_sound_health_report()
                    source_contract_filter = engine.source_contract_filter_report()
                    source_bar_quality = engine.source_bar_quality_report()
                    completed_seen = completed_count
                finally:
                    live_state_lock.release()
                market_session = live_market_session_state(
                    live_cfg,
                    engine.databento_config,
                    now_utc=heartbeat_utc,
                )
                print_json(
                    live_status_payload(
                        health,
                        now=now,
                        connected=connected,
                        entry_alerts=engine.alert_count,
                        pending_signals=pending_signals,
                        alert_sink=engine.alert_sink,
                        setup_notice_sink=engine.setup_notice_sink,
                        execution_intent_sink=engine.execution_intent_sink,
                        strategy_health=strategy_health,
                        strategy_evaluation=strategy_evaluation,
                        market_session=market_session,
                        pending_status=pending_status,
                        operator_sound=operator_sound,
                        source_contract_filter=source_contract_filter,
                        source_bar_quality=source_bar_quality,
                        dry_run_alerts=engine.dry_run_alerts,
                    )
                )
                for alert in live_health_alerts(
                    health,
                    live_cfg,
                    now=now,
                    connected=connected,
                    market_session=market_session,
                    strategy_evaluation=strategy_evaluation,
                ):
                    print_json(alert, prefix="SYSTEM_ALERT")
                    engine.play_operator_sound("system")
                    if live_health_alert_stop_enabled(str(alert["event"]), live_cfg):
                        request_client_stop(str(alert["event"]))
                        break
                if once and completed_seen > 0:
                    request_client_stop("once_completed_source_bar")
                    break
                next_heartbeat = now + heartbeat_interval
            time.sleep(0.5)
    finally:
        restore_live_signal_handlers(previous_signal_handlers)
    stop_report = stop_live_client(client, shutdown_grace_seconds=shutdown_grace_seconds)
    failure_stop_reasons = {
        "live_disconnected",
        "live_no_records_received",
        "live_no_trade_ticks",
        "live_no_completed_bars",
        "live_no_evaluable_strategies",
        "live_partially_unevaluable_strategies",
        "live_trade_tick_stale_timestamp",
        "live_trade_tick_future_timestamp",
        "live_unmatched_contract_symbol_ignored",
        "live_state_lock_timeout",
        "unmatched_contract_symbol",
        "live_callback_error",
        "live_exception",
    }
    exit_code = 1 if live_errors or stop_reason in failure_stop_reasons else 130 if interrupted else 0
    print_json(
        {
            "event": "live_stopped",
            "reason": stop_reason or "loop_exit",
            "exit_code": exit_code,
            "records_received": health.records_received,
            "trade_ticks_received": health.ticks_received,
            "accepted_trade_ticks": sum(int(value) for value in health.accepted_contract_ticks.values()),
            "completed_source_bars": health.completed_bars,
            "dropped_partial_bars": health.dropped_partial_bars,
            "trade_setups": engine.setup_notice_count,
            "entry_alerts": engine.alert_count,
            "dry_run_alerts": engine.dry_run_alerts,
            "pending_signals": len(engine.pending),
            "live_errors": len(live_errors),
            "setup_alerts": {
                "enabled": bool(engine.setup_alerts_config.get("enabled", False)),
                "path": str(engine.setup_alerts_path) if engine.setup_alerts_path else None,
                "writes_succeeded": engine.setup_notice_sink.writes_succeeded,
                "writes_failed": engine.setup_notice_sink.writes_failed,
                "duplicates_skipped": engine.setup_notice_sink.duplicates_skipped,
                "last_error_type": engine.setup_notice_sink.last_error_type,
                "last_error": engine.setup_notice_sink.last_error,
            },
            "execution_intents": {
                "enabled": bool(engine.execution_intents_config.get("enabled", False)),
                "path": str(engine.execution_intents_path) if engine.execution_intents_path else None,
                "writes_succeeded": engine.execution_intent_sink.writes_succeeded,
                "writes_failed": engine.execution_intent_sink.writes_failed,
                "duplicates_skipped": engine.execution_intent_sink.duplicates_skipped,
                "freshness_skipped": engine.execution_intent_sink.freshness_skipped,
                "last_freshness_skip_reason": engine.execution_intent_sink.last_freshness_skip_reason,
                "last_error_type": engine.execution_intent_sink.last_error_type,
                "last_error": engine.execution_intent_sink.last_error,
            },
            "operator_sound": engine.operator_sound_health_report(),
            "contract_symbol_regex": health.contract_symbol_regex,
            "source_contract_filter": engine.source_contract_filter_report(),
            "source_bar_quality": engine.source_bar_quality_report(),
            "accepted_contract_ticks": top_count_items(health.accepted_contract_ticks),
            "unmatched_contract_ticks_ignored": health.unmatched_contract_ticks_ignored,
            "unmatched_contract_ticks": top_count_items(health.unmatched_contract_ticks),
            "last_unmatched_contract_tick": health.last_unmatched_contract_tick,
            **stop_report,
        }
    )
    return exit_code


def stop_live_client(client: Any, *, shutdown_grace_seconds: float) -> dict[str, Any]:
    report: dict[str, Any] = {
        "client_stop_called": False,
        "client_wait_for_close_called": False,
        "client_close_wait_seconds": shutdown_grace_seconds,
        "client_stop_error_type": None,
        "client_stop_error": None,
        "client_wait_error_type": None,
        "client_wait_error": None,
        "client_close_method": None,
    }
    try:
        client.stop()
        report["client_stop_called"] = True
    except Exception as exc:  # noqa: BLE001 - shutdown diagnostics should not hide the original stop reason.
        report["client_stop_error_type"] = type(exc).__name__
        report["client_stop_error"] = str(exc)
    block_for_close = getattr(client, "block_for_close", None)
    wait_for_close = getattr(client, "wait_for_close", None)
    if callable(block_for_close) and shutdown_grace_seconds > 0:
        try:
            block_for_close(timeout=shutdown_grace_seconds)
            report["client_wait_for_close_called"] = True
            report["client_close_method"] = "block_for_close"
        except Exception as exc:  # noqa: BLE001 - report close wait failure and continue shutdown.
            report["client_wait_for_close_called"] = True
            report["client_close_method"] = "block_for_close"
            report["client_wait_error_type"] = type(exc).__name__
            report["client_wait_error"] = str(exc)
    elif callable(wait_for_close) and shutdown_grace_seconds > 0:
        try:
            maybe_awaitable = wait_for_close(timeout=shutdown_grace_seconds)
            if hasattr(maybe_awaitable, "__await__"):
                asyncio.run(maybe_awaitable)
            report["client_wait_for_close_called"] = True
            report["client_close_method"] = "wait_for_close"
        except Exception as exc:  # noqa: BLE001 - report close wait failure and continue shutdown.
            report["client_wait_for_close_called"] = True
            report["client_close_method"] = "wait_for_close"
            report["client_wait_error_type"] = type(exc).__name__
            report["client_wait_error"] = str(exc)
    return report


def install_live_signal_handlers(handler: Any) -> dict[Any, Any]:
    previous: dict[Any, Any] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            previous[sig] = signal.getsignal(sig)
            signal.signal(sig, handler)
        except ValueError as exc:
            print_json(
                {
                    "event": "live_signal_handler_install_skipped",
                    "signal": getattr(sig, "name", str(sig)),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "impact": (
                        "The live engine continues, but this embedding thread cannot install process signal "
                        "handlers. Stop it through the caller or Databento client instead."
                    ),
                },
                prefix="SYSTEM_ALERT",
            )
            previous.pop(sig, None)
        except Exception as exc:
            print_json(
                {
                    "event": "live_signal_handler_install_failed",
                    "signal": getattr(sig, "name", str(sig)),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                prefix="SYSTEM_ALERT",
            )
            previous.pop(sig, None)
    return previous


def restore_live_signal_handlers(previous: dict[Any, Any]) -> None:
    for sig, handler in previous.items():
        try:
            signal.signal(sig, handler)
        except Exception as exc:
            print_json(
                {
                    "event": "live_signal_handler_restore_failed",
                    "signal": getattr(sig, "name", str(sig)),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                prefix="SYSTEM_ALERT",
            )


def live_metadata_preflight_payload(report: dict[str, Any]) -> dict[str, Any]:
    checks = report.get("checks", {}) if isinstance(report.get("checks"), dict) else {}
    dataset_range = checks.get("dataset_range", {}) if isinstance(checks.get("dataset_range"), dict) else {}
    schemas = checks.get("schemas", {}) if isinstance(checks.get("schemas"), dict) else {}
    fields = checks.get("fields", {}) if isinstance(checks.get("fields"), dict) else {}
    symbology = checks.get("symbology", {}) if isinstance(checks.get("symbology"), dict) else {}
    cost_guard = checks.get("historical_cost_guard", {}) if isinstance(checks.get("historical_cost_guard"), dict) else {}
    return {
        "event": "live_metadata_preflight_ok",
        "dataset": report.get("dataset"),
        "schema": report.get("schema"),
        "symbols": report.get("symbols"),
        "stype_in": report.get("stype_in"),
        "dataset_range_ok": dataset_range.get("ok"),
        "dataset_available_end": dataset_range.get("end"),
        "schema_ok": schemas.get("ok"),
        "fields_ok": fields.get("ok"),
        "field_count": fields.get("field_count"),
        "symbology_ok": symbology.get("ok"),
        "symbology_stype_out": symbology.get("stype_out"),
        "symbology_mapping_count": symbology.get("mapping_count"),
        "symbology_not_found": symbology.get("not_found"),
        "historical_cost_guard_ok": cost_guard.get("ok"),
        "estimated_cost_usd": cost_guard.get("estimated_cost_usd"),
        "timeseries_download_attempted": report.get("timeseries_download_attempted"),
        "live_subscription_attempted": report.get("live_subscription_attempted"),
    }


def strategy_evaluation_totals(strategy_health: list[dict[str, Any]] | None) -> dict[str, Any]:
    items = strategy_health or []
    return {
        "processed_strategy_rows": sum(int(item.get("processed_strategy_row_count", 0) or 0) for item in items),
        "evaluated_strategy_rows": sum(int(item.get("evaluated_strategy_row_count", 0) or 0) for item in items),
        "per_strategy_processed_rows": {
            str(item.get("strategy_id")): int(item.get("processed_strategy_row_count", 0) or 0)
            for item in items
        },
        "per_strategy_evaluated_rows": {
            str(item.get("strategy_id")): int(item.get("evaluated_strategy_row_count", 0) or 0)
            for item in items
        },
    }


def live_strategy_evaluation_summary(
    strategy_health: list[dict[str, Any]] | None,
    *,
    completed_source_bars: int,
    data_plan: dict[str, Any],
    live_cfg: dict[str, Any],
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    items = strategy_health or []
    baseline = baseline or {}
    totals = strategy_evaluation_totals(items)
    active = [item for item in items if not item.get("disabled")]
    disabled = [item for item in items if item.get("disabled")]
    unevaluated_active = [
        item
        for item in active
        if int(item.get("evaluated_strategy_row_count", 0) or 0)
        <= int((baseline.get("per_strategy_evaluated_rows") or {}).get(str(item.get("strategy_id")), 0) or 0)
    ]
    per_strategy_processed_rows = totals["per_strategy_processed_rows"]
    per_strategy_evaluated_rows = totals["per_strategy_evaluated_rows"]
    baseline_per_strategy_processed = baseline.get("per_strategy_processed_rows") or {}
    baseline_per_strategy_evaluated = baseline.get("per_strategy_evaluated_rows") or {}
    per_strategy_new_processed_rows = {
        strategy_id: max(0, int(value) - int(baseline_per_strategy_processed.get(strategy_id, 0) or 0))
        for strategy_id, value in per_strategy_processed_rows.items()
    }
    per_strategy_new_evaluated_rows = {
        strategy_id: max(0, int(value) - int(baseline_per_strategy_evaluated.get(strategy_id, 0) or 0))
        for strategy_id, value in per_strategy_evaluated_rows.items()
    }
    warmup = data_plan.get("warmup", {}) if isinstance(data_plan.get("warmup"), dict) else {}
    recommended_source_bars = int(warmup.get("recommended_source_bars", 0) or 0)
    configured_alert_bars = live_cfg.get("no_evaluable_strategy_alert_bars")
    if configured_alert_bars is None:
        alert_after_completed_source_bars = max(1, recommended_source_bars)
        alert_threshold_source = "data_plan.recommended_source_bars"
    else:
        alert_after_completed_source_bars = max(1, int(configured_alert_bars))
        alert_threshold_source = "databento.live.no_evaluable_strategy_alert_bars"
    new_processed_rows = max(0, totals["processed_strategy_rows"] - int(baseline.get("processed_strategy_rows", 0) or 0))
    new_evaluated_rows = max(0, totals["evaluated_strategy_rows"] - int(baseline.get("evaluated_strategy_rows", 0) or 0))
    no_evaluable = (
        bool(active)
        and int(completed_source_bars) >= alert_after_completed_source_bars
        and new_evaluated_rows <= 0
    )
    partially_unevaluable = (
        bool(active)
        and int(completed_source_bars) >= alert_after_completed_source_bars
        and new_evaluated_rows > 0
        and bool(unevaluated_active)
    )
    return {
        "active_strategy_count": len(active),
        "disabled_strategy_count": len(disabled),
        "processed_strategy_rows": totals["processed_strategy_rows"],
        "evaluated_strategy_rows": totals["evaluated_strategy_rows"],
        "per_strategy_new_processed_rows": per_strategy_new_processed_rows,
        "per_strategy_new_evaluated_rows": per_strategy_new_evaluated_rows,
        "new_processed_strategy_rows": new_processed_rows,
        "new_evaluated_strategy_rows": new_evaluated_rows,
        "baseline_processed_strategy_rows": int(baseline.get("processed_strategy_rows", 0) or 0),
        "baseline_evaluated_strategy_rows": int(baseline.get("evaluated_strategy_rows", 0) or 0),
        "feature_quality_skips": sum(int(item.get("feature_quality_skip_count", 0) or 0) for item in items),
        "runtime_errors": sum(int(item.get("runtime_error_count", 0) or 0) for item in items),
        "unevaluated_active_strategy_count": len(unevaluated_active),
        "unevaluated_active_strategy_ids": [str(item.get("strategy_id")) for item in unevaluated_active],
        "completed_source_bars": int(completed_source_bars),
        "recommended_source_bars": recommended_source_bars,
        "alert_after_completed_source_bars": alert_after_completed_source_bars,
        "alert_threshold_source": alert_threshold_source,
        "no_evaluable_strategies": no_evaluable,
        "partially_unevaluable_strategies": partially_unevaluable,
    }


def live_status_payload(
    health: LiveHealth,
    *,
    now: float,
    connected: bool,
    entry_alerts: int,
    pending_signals: int,
    alert_sink: AlertSinkHealth | None = None,
    setup_notice_sink: AlertSinkHealth | None = None,
    execution_intent_sink: AlertSinkHealth | None = None,
    strategy_health: list[dict[str, Any]] | None = None,
    strategy_evaluation: dict[str, Any] | None = None,
    market_session: dict[str, Any] | None = None,
    pending_status: dict[str, Any] | None = None,
    operator_sound: dict[str, Any] | None = None,
    source_contract_filter: dict[str, Any] | None = None,
    source_bar_quality: dict[str, Any] | None = None,
    dry_run_alerts: bool = False,
) -> dict[str, Any]:
    payload = {
        "event": "live_status",
        "connected": connected,
        "uptime_seconds": round(max(0.0, now - health.started_monotonic), 3),
        "records_received": health.records_received,
        "trade_ticks_received": health.ticks_received,
        "completed_source_bars": health.completed_bars,
        "heartbeat_flushed_source_bars": health.heartbeat_flushed_bars,
        "dropped_partial_bars": health.dropped_partial_bars,
        "accepted_trade_ticks": sum(int(value) for value in health.accepted_contract_ticks.values()),
        "late_trade_ticks_ignored": health.late_trade_ticks_ignored,
        "last_late_trade_tick": health.last_late_trade_tick,
        "contract_symbol_regex": health.contract_symbol_regex,
        "accepted_contract_ticks": top_count_items(health.accepted_contract_ticks),
        "unmatched_contract_ticks_ignored": health.unmatched_contract_ticks_ignored,
        "unmatched_contract_ticks": top_count_items(health.unmatched_contract_ticks),
        "last_unmatched_contract_tick": health.last_unmatched_contract_tick,
        "seconds_since_last_record": seconds_since(now, health.last_record_monotonic),
        "seconds_since_last_trade_tick": seconds_since(now, health.last_tick_monotonic),
        "seconds_since_last_completed_bar": seconds_since(now, health.last_completed_bar_monotonic),
        "last_trade_tick_event_timestamp_utc": health.last_tick_event_timestamp_utc,
        "last_trade_tick_clock_lag_seconds": round(health.last_tick_clock_lag_seconds, 3)
        if health.last_tick_clock_lag_seconds is not None
        else None,
        "max_trade_tick_clock_lag_seconds": round(health.max_tick_clock_lag_seconds, 3),
        "max_trade_tick_clock_future_seconds": round(health.max_tick_clock_future_seconds, 3),
        "entry_alerts": entry_alerts,
        "pending_signals": pending_signals,
        "dry_run_alerts": bool(dry_run_alerts),
    }
    if strategy_health is not None:
        payload["active_strategy_count"] = sum(1 for item in strategy_health if not item.get("disabled"))
        payload["disabled_strategy_count"] = sum(1 for item in strategy_health if item.get("disabled"))
        payload["strategy_health"] = strategy_health
    if strategy_evaluation is not None:
        payload["strategy_evaluation"] = strategy_evaluation
    if market_session is not None:
        payload["market_session"] = market_session
    if pending_status is not None:
        payload["pending_status"] = pending_status
    if operator_sound is not None:
        payload["operator_sound"] = operator_sound
    if source_contract_filter is not None:
        payload["source_contract_filter"] = source_contract_filter
    if source_bar_quality is not None:
        payload["source_bar_quality"] = source_bar_quality
    if alert_sink is not None:
        payload.update(
            {
                "alert_file_writes_succeeded": alert_sink.writes_succeeded,
                "alert_file_writes_failed": alert_sink.writes_failed,
                "alert_file_duplicates_skipped": alert_sink.duplicates_skipped,
                "alert_file_last_success_utc": alert_sink.last_success_utc,
                "alert_file_last_duplicate_utc": alert_sink.last_duplicate_utc,
                "alert_file_last_duplicate_alert_id": alert_sink.last_duplicate_alert_id,
                "alert_file_last_duplicate_id_field": alert_sink.last_duplicate_id_field,
                "alert_file_last_error_utc": alert_sink.last_error_utc,
                "alert_file_last_error_type": alert_sink.last_error_type,
                "alert_file_last_error": alert_sink.last_error,
            }
        )
    if setup_notice_sink is not None:
        payload.update(
            {
                "setup_alert_writes_succeeded": setup_notice_sink.writes_succeeded,
                "setup_alert_writes_failed": setup_notice_sink.writes_failed,
                "setup_alert_duplicates_skipped": setup_notice_sink.duplicates_skipped,
                "setup_alert_last_success_utc": setup_notice_sink.last_success_utc,
                "setup_alert_last_duplicate_utc": setup_notice_sink.last_duplicate_utc,
                "setup_alert_last_duplicate_setup_id": setup_notice_sink.last_duplicate_alert_id,
                "setup_alert_last_duplicate_id_field": setup_notice_sink.last_duplicate_id_field,
                "setup_alert_last_error_utc": setup_notice_sink.last_error_utc,
                "setup_alert_last_error_type": setup_notice_sink.last_error_type,
                "setup_alert_last_error": setup_notice_sink.last_error,
            }
        )
    if execution_intent_sink is not None:
        payload.update(
            {
                "execution_intent_writes_succeeded": execution_intent_sink.writes_succeeded,
                "execution_intent_writes_failed": execution_intent_sink.writes_failed,
                "execution_intent_duplicates_skipped": execution_intent_sink.duplicates_skipped,
                "execution_intent_freshness_skipped": execution_intent_sink.freshness_skipped,
                "execution_intent_last_success_utc": execution_intent_sink.last_success_utc,
                "execution_intent_last_duplicate_utc": execution_intent_sink.last_duplicate_utc,
                "execution_intent_last_duplicate_alert_id": execution_intent_sink.last_duplicate_alert_id,
                "execution_intent_last_duplicate_id_field": execution_intent_sink.last_duplicate_id_field,
                "execution_intent_last_freshness_skip_utc": execution_intent_sink.last_freshness_skip_utc,
                "execution_intent_last_freshness_skip_alert_id": (
                    execution_intent_sink.last_freshness_skip_alert_id
                ),
                "execution_intent_last_freshness_skip_reason": (
                    execution_intent_sink.last_freshness_skip_reason
                ),
                "execution_intent_last_error_utc": execution_intent_sink.last_error_utc,
                "execution_intent_last_error_type": execution_intent_sink.last_error_type,
                "execution_intent_last_error": execution_intent_sink.last_error,
            }
        )
    return payload


def live_health_alerts(
    health: LiveHealth,
    live_cfg: dict[str, Any],
    *,
    now: float,
    connected: bool,
    market_session: dict[str, Any] | None = None,
    strategy_evaluation: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    repeat_seconds = float(live_cfg.get("alert_repeat_seconds", 120.0))
    alerts: list[dict[str, Any]] = []
    if not connected and should_emit_live_health_alert(health, "live_disconnected", now, repeat_seconds):
        alerts.append(
            {
                "event": "live_disconnected",
                "connected": False,
                "reason": "Databento live client reports disconnected.",
            }
        )

    if health.unmatched_contract_ticks_ignored > 0 and should_emit_live_health_alert(
        health,
        "live_unmatched_contract_symbol_ignored",
        now,
        repeat_seconds,
    ):
        alerts.append(
            {
                "event": "live_unmatched_contract_symbol_ignored",
                "unmatched_contract_ticks_ignored": health.unmatched_contract_ticks_ignored,
                "contract_symbol_regex": health.contract_symbol_regex,
                "last_unmatched_contract_tick": health.last_unmatched_contract_tick,
                "unmatched_contract_ticks": top_count_items(health.unmatched_contract_ticks),
                "accepted_contract_ticks": top_count_items(health.accepted_contract_ticks),
                "reason": "One or more trade ticks did not match databento.contract_symbol_regex.",
                "impact": "Rejected ticks are not aggregated into source bars and are not used as entry triggers.",
            }
        )

    if (
        strategy_evaluation is not None
        and bool(strategy_evaluation.get("no_evaluable_strategies", False))
        and should_emit_live_health_alert(health, "live_no_evaluable_strategies", now, repeat_seconds)
    ):
        alerts.append(
            {
                "event": "live_no_evaluable_strategies",
                "completed_source_bars": strategy_evaluation.get("completed_source_bars"),
                "alert_after_completed_source_bars": strategy_evaluation.get("alert_after_completed_source_bars"),
                "alert_threshold_source": strategy_evaluation.get("alert_threshold_source"),
                "active_strategy_count": strategy_evaluation.get("active_strategy_count"),
                "new_processed_strategy_rows": strategy_evaluation.get("new_processed_strategy_rows"),
                "new_evaluated_strategy_rows": strategy_evaluation.get("new_evaluated_strategy_rows"),
                "unevaluated_active_strategy_ids": strategy_evaluation.get("unevaluated_active_strategy_ids"),
                "feature_quality_skips": strategy_evaluation.get("feature_quality_skips"),
                "runtime_errors": strategy_evaluation.get("runtime_errors"),
                "reason": (
                    "Live source bars have completed, but no active strategy has evaluated a new complete "
                    "strategy row since live start."
                ),
                "impact": (
                    "The engine may appear connected while being unable to produce valid setup or entry signals. "
                    "Check historical warmup, source columns, feature quality, and strategy filters."
                ),
            }
        )

    if (
        strategy_evaluation is not None
        and bool(strategy_evaluation.get("partially_unevaluable_strategies", False))
        and should_emit_live_health_alert(health, "live_partially_unevaluable_strategies", now, repeat_seconds)
    ):
        alerts.append(
            {
                "event": "live_partially_unevaluable_strategies",
                "completed_source_bars": strategy_evaluation.get("completed_source_bars"),
                "alert_after_completed_source_bars": strategy_evaluation.get("alert_after_completed_source_bars"),
                "alert_threshold_source": strategy_evaluation.get("alert_threshold_source"),
                "active_strategy_count": strategy_evaluation.get("active_strategy_count"),
                "new_processed_strategy_rows": strategy_evaluation.get("new_processed_strategy_rows"),
                "new_evaluated_strategy_rows": strategy_evaluation.get("new_evaluated_strategy_rows"),
                "per_strategy_new_evaluated_rows": strategy_evaluation.get("per_strategy_new_evaluated_rows"),
                "unevaluated_active_strategy_ids": strategy_evaluation.get("unevaluated_active_strategy_ids"),
                "feature_quality_skips": strategy_evaluation.get("feature_quality_skips"),
                "runtime_errors": strategy_evaluation.get("runtime_errors"),
                "reason": (
                    "One or more active strategies have not evaluated any new complete strategy row since live "
                    "start, while at least one other active strategy has evaluated."
                ),
                "impact": (
                    "The live engine is only partially covering the configured strategy set. Check warmup depth, "
                    "required source columns, feature-quality skips, and strategy-specific filters before relying "
                    "on missing strategy signals."
                ),
            }
        )

    max_tick_lag_seconds = float(live_cfg.get("max_trade_tick_lag_seconds", 10.0))
    if (
        max_tick_lag_seconds > 0
        and health.last_tick_clock_lag_seconds is not None
        and health.last_tick_clock_lag_seconds >= max_tick_lag_seconds
        and should_emit_live_health_alert(health, "live_trade_tick_stale_timestamp", now, repeat_seconds)
    ):
        alerts.append(
            {
                "event": "live_trade_tick_stale_timestamp",
                "lag_seconds": round(health.last_tick_clock_lag_seconds, 3),
                "threshold_seconds": max_tick_lag_seconds,
                "trade_tick_event_timestamp_utc": health.last_tick_event_timestamp_utc,
                "reason": "Latest trade tick event timestamp is too old versus local wall-clock UTC.",
            }
        )

    max_tick_future_seconds = float(live_cfg.get("max_trade_tick_future_seconds", 2.0))
    if (
        max_tick_future_seconds > 0
        and health.last_tick_clock_lag_seconds is not None
        and -health.last_tick_clock_lag_seconds >= max_tick_future_seconds
        and should_emit_live_health_alert(health, "live_trade_tick_future_timestamp", now, repeat_seconds)
    ):
        alerts.append(
            {
                "event": "live_trade_tick_future_timestamp",
                "future_seconds": round(-health.last_tick_clock_lag_seconds, 3),
                "threshold_seconds": max_tick_future_seconds,
                "trade_tick_event_timestamp_utc": health.last_tick_event_timestamp_utc,
                "reason": "Latest trade tick event timestamp is ahead of local wall-clock UTC.",
            }
        )

    if market_session is not None and bool(market_session.get("suppress_stale_alerts", False)):
        return alerts

    no_records_seconds = float(live_cfg.get("no_records_alert_seconds", 30.0))
    if no_records_seconds > 0 and health.records_received == 0:
        age = now - health.started_monotonic
        if age >= no_records_seconds and should_emit_live_health_alert(
            health, "live_no_records_received", now, repeat_seconds
        ):
            alerts.append(
                {
                    "event": "live_no_records_received",
                    "age_seconds": round(age, 3),
                    "threshold_seconds": no_records_seconds,
                    "reason": "No Databento records have arrived since live start.",
                }
            )

    no_ticks_seconds = float(live_cfg.get("no_trade_ticks_alert_seconds", 60.0))
    tick_age = now - (health.last_tick_monotonic or health.started_monotonic)
    if no_ticks_seconds > 0 and tick_age >= no_ticks_seconds:
        if should_emit_live_health_alert(health, "live_no_trade_ticks", now, repeat_seconds):
            alerts.append(
                {
                    "event": "live_no_trade_ticks",
                    "age_seconds": round(tick_age, 3),
                    "threshold_seconds": no_ticks_seconds,
                    "records_received": health.records_received,
                    "trade_ticks_received": health.ticks_received,
                    "reason": "No trade ticks have arrived inside the configured threshold.",
                }
            )

    no_bar_seconds = float(live_cfg.get("no_completed_bar_alert_seconds", 180.0))
    if no_bar_seconds > 0 and health.ticks_received > 0:
        bar_age = now - (health.last_completed_bar_monotonic or health.started_monotonic)
        if bar_age >= no_bar_seconds and should_emit_live_health_alert(
            health, "live_no_completed_bars", now, repeat_seconds
        ):
            alerts.append(
                {
                    "event": "live_no_completed_bars",
                    "age_seconds": round(bar_age, 3),
                    "threshold_seconds": no_bar_seconds,
                    "trade_ticks_received": health.ticks_received,
                    "completed_source_bars": health.completed_bars,
                    "reason": "Trade ticks are arriving, but no completed source bars have been emitted recently.",
                }
            )
    return alerts


LIVE_HEALTH_STOP_CONFIG_KEYS = {
    "live_disconnected": "stop_on_disconnect",
    "live_no_records_received": "stop_on_no_records",
    "live_no_trade_ticks": "stop_on_no_trade_ticks",
    "live_no_completed_bars": "stop_on_no_completed_bars",
    "live_no_evaluable_strategies": "stop_on_no_evaluable_strategies",
    "live_partially_unevaluable_strategies": "stop_on_partial_unevaluable_strategies",
    "live_trade_tick_stale_timestamp": "stop_on_stale_trade_tick",
    "live_trade_tick_future_timestamp": "stop_on_future_trade_tick",
    "live_unmatched_contract_symbol_ignored": "stop_on_unmatched_contract_symbol",
}


LIVE_SAFETY_STOP_DEFAULTS = {
    "stop_on_disconnect": False,
    "stop_on_no_records": False,
    "stop_on_no_trade_ticks": False,
    "stop_on_no_completed_bars": False,
    "stop_on_no_evaluable_strategies": False,
    "stop_on_partial_unevaluable_strategies": False,
    "stop_on_stale_trade_tick": False,
    "stop_on_future_trade_tick": False,
    "stop_on_unmatched_contract_symbol": False,
    "stop_on_state_lock_timeout": True,
}


def live_safety_stop_config(live_cfg: Any) -> dict[str, bool]:
    raw = live_cfg if isinstance(live_cfg, dict) else {}
    return {key: bool(raw.get(key, default)) for key, default in LIVE_SAFETY_STOP_DEFAULTS.items()}


def live_health_alert_stop_enabled(event: str, live_cfg: dict[str, Any]) -> bool:
    config_key = LIVE_HEALTH_STOP_CONFIG_KEYS.get(event)
    if config_key is None:
        return False
    return bool(live_cfg.get(config_key, False))


def live_market_session_state(
    live_cfg: dict[str, Any],
    databento_config: dict[str, Any],
    *,
    now_utc: Any,
) -> dict[str, Any]:
    enabled = bool(live_cfg.get("session_aware_stale_alerts", True))
    timezone = str(
        live_cfg.get("stale_alert_session_timezone")
        or databento_config.get("timezone")
        or DEFAULT_TIMEZONE
    )
    start_text = str(
        live_cfg.get("stale_alert_session_start")
        or databento_config.get("rth_start")
        or "09:30:00"
    )
    end_text = str(
        live_cfg.get("stale_alert_session_end")
        or databento_config.get("rth_end")
        or "16:00:00"
    )
    weekdays = live_cfg.get("stale_alert_weekdays")
    weekdays = validate_weekdays(weekdays) if weekdays is not None else [0, 1, 2, 3, 4]
    now_local = pd.Timestamp(now_utc).tz_convert(timezone)
    start_time = parse_time_of_day(start_text, key="stale_alert_session_start")
    end_time = parse_time_of_day(end_text, key="stale_alert_session_end")
    in_weekday = int(now_local.weekday()) in set(weekdays)
    in_time = time_in_session(now_local.time(), start_time, end_time)
    is_open = bool(in_weekday and in_time)
    return {
        "enabled": enabled,
        "timezone": timezone,
        "now_utc": pd.Timestamp(now_utc).tz_convert("UTC").isoformat(),
        "now_local": now_local.isoformat(),
        "session_start": start_text,
        "session_end": end_text,
        "weekdays": weekdays,
        "is_open": True if not enabled else is_open,
        "suppress_stale_alerts": bool(enabled and not is_open),
        "reason": None if not enabled or is_open else "outside_configured_stale_alert_session",
    }


def time_in_session(value: dt.time, start: dt.time, end: dt.time) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= value < end
    return value >= start or value < end


def should_emit_live_health_alert(health: LiveHealth, event: str, now: float, repeat_seconds: float) -> bool:
    last = health.alerts_emitted.get(event)
    if last is not None and repeat_seconds > 0 and now - last < repeat_seconds:
        return False
    health.alerts_emitted[event] = now
    return True


def update_live_tick_clock_health(health: LiveHealth, tick: TradeTick, *, received_at_utc: Any) -> None:
    received = pd.Timestamp(received_at_utc)
    received = received.tz_localize("UTC") if received.tzinfo is None else received.tz_convert("UTC")
    event_timestamp = pd.Timestamp(tick.timestamp_utc)
    event_timestamp = (
        event_timestamp.tz_localize("UTC") if event_timestamp.tzinfo is None else event_timestamp.tz_convert("UTC")
    )
    lag_seconds = float((received - event_timestamp).total_seconds())
    health.last_tick_event_timestamp_utc = event_timestamp.isoformat()
    health.last_tick_clock_lag_seconds = lag_seconds
    if lag_seconds >= 0:
        health.max_tick_clock_lag_seconds = max(health.max_tick_clock_lag_seconds, lag_seconds)
    else:
        health.max_tick_clock_future_seconds = max(health.max_tick_clock_future_seconds, abs(lag_seconds))


def seconds_since(now: float, previous: float | None) -> float | None:
    if previous is None:
        return None
    return round(max(0.0, now - previous), 3)


def top_count_items(counts: dict[str, int] | None, *, limit: int = 20) -> dict[str, int]:
    if not counts:
        return {}
    ordered = sorted(counts.items(), key=lambda item: (-int(item[1]), str(item[0])))
    return {str(key): int(value) for key, value in ordered[: max(0, int(limit))]}


def pending_contract_symbol(pending: PendingSignal) -> str:
    value = None
    row = pending.row
    if hasattr(row, "get"):
        value = row.get("contract_symbol")
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "nat"} else text


def strategy_row_identity_key(row: Any) -> tuple[str, str]:
    timestamp = row_get(row, "timestamp")
    try:
        parsed = pd.Timestamp(timestamp)
        if parsed.tzinfo is not None:
            timestamp_key = parsed.tz_convert("UTC").isoformat()
        else:
            timestamp_key = parsed.isoformat()
    except Exception:
        timestamp_key = str(timestamp)
    contract_symbol = str(row_get(row, "contract_symbol") or "").strip()
    return (timestamp_key, contract_symbol)


def active_contract_source_filter_report(
    frame: Any,
    *,
    mode: str,
    timezone: str,
) -> tuple[Any, dict[str, Any]]:
    mode = validate_active_contract_mode(mode)
    report = {
        "active_contract_mode": mode,
        "input_rows": int(len(frame)) if hasattr(frame, "__len__") else 0,
        "kept_rows": int(len(frame)) if hasattr(frame, "__len__") else 0,
        "dropped_rows": 0,
        "selected_contracts": {},
        "dropped_contracts": {},
        "sample_dropped_rows": [],
        "dropped_row_keys": [],
    }
    if frame.empty or mode == "emit_all" or "contract_symbol" not in frame.columns:
        return frame, report
    time_column = "timestamp_utc" if "timestamp_utc" in frame.columns else "timestamp" if "timestamp" in frame.columns else None
    if time_column is None:
        return frame, report

    work = frame.copy()
    work["_engine_time_key"] = work[time_column].map(active_contract_time_key)
    work["_engine_contract_symbol"] = work["contract_symbol"].map(lambda value: str(value or "").strip())
    work["_engine_volume"] = work["volume"].map(lambda value: finite_float(value) or 0.0) if "volume" in work.columns else 0.0
    work = work.sort_values(["_engine_time_key", "_engine_contract_symbol"]).copy()

    selected_indices: list[Any] = []
    session_volume: dict[tuple[str, str], float] = {}
    for _, group in work.groupby("_engine_time_key", sort=True):
        if mode == "highest_session_volume":
            for _, row in group.iterrows():
                contract = str(row["_engine_contract_symbol"])
                session = local_session_date(active_contract_row_timestamp(row, time_column), timezone)
                key = (session, contract)
                session_volume[key] = session_volume.get(key, 0.0) + float(row["_engine_volume"])
            selected = max(
                group.iterrows(),
                key=lambda item: (
                    session_volume.get(
                        (
                            local_session_date(active_contract_row_timestamp(item[1], time_column), timezone),
                            str(item[1]["_engine_contract_symbol"]),
                        ),
                        0.0,
                    ),
                    float(item[1]["_engine_volume"]),
                    str(item[1]["_engine_contract_symbol"]),
                ),
            )[0]
        else:
            selected = max(
                group.iterrows(),
                key=lambda item: (float(item[1]["_engine_volume"]), str(item[1]["_engine_contract_symbol"])),
            )[0]
        selected_indices.append(selected)

    selected_index_set = set(selected_indices)
    filtered = frame.loc[selected_indices].sort_values([time_column, "contract_symbol"]).reset_index(drop=True)
    dropped = work.loc[[index for index in work.index if index not in selected_index_set]]
    selected_contracts = filtered["contract_symbol"].astype(str).value_counts().to_dict()
    dropped_contracts = dropped["contract_symbol"].astype(str).value_counts().to_dict() if not dropped.empty else {}
    report.update(
        {
            "kept_rows": int(len(filtered)),
            "dropped_rows": int(len(dropped)),
            "selected_contracts": {str(key): int(value) for key, value in selected_contracts.items()},
            "dropped_contracts": {str(key): int(value) for key, value in dropped_contracts.items()},
            "sample_dropped_rows": [
                active_contract_dropped_row_report(row, time_column)
                for _, row in dropped.head(10).iterrows()
            ],
            "dropped_row_keys": [
                [
                    active_contract_timestamp_identity(row, time_column),
                    str(row.get("contract_symbol") or ""),
                ]
                for _, row in dropped.iterrows()
            ],
        }
    )
    return filtered, report


def active_contract_time_key(value: Any) -> str:
    try:
        return normalize_utc_timestamp(value).isoformat()
    except Exception:
        return str(value)


def active_contract_timestamp_identity(row: Any, time_column: str) -> str:
    return active_contract_time_key(row_get(row, time_column))


def active_contract_row_timestamp(row: Any, time_column: str) -> Any:
    value = row_get(row, time_column)
    try:
        return normalize_utc_timestamp(value)
    except Exception:
        timestamp = row_get(row, "timestamp")
        return normalize_utc_timestamp(timestamp)


def active_contract_dropped_row_report(row: Any, time_column: str) -> dict[str, Any]:
    timestamp_utc = None
    try:
        timestamp_utc = format_timestamp(active_contract_row_timestamp(row, time_column))
    except Exception:
        timestamp_utc = str(row_get(row, time_column, ""))
    return {
        "timestamp_utc": timestamp_utc,
        "contract_symbol": str(row_get(row, "contract_symbol") or ""),
        "volume": finite_float(row_get(row, "volume")),
        "signed_volume": finite_float(row_get(row, "signed_volume")),
    }


def row_has_key(row: Any, key: str) -> bool:
    if isinstance(row, dict):
        return key in row
    try:
        return key in row.index
    except Exception:
        try:
            row[key]
        except Exception:
            return False
        return True


def row_get(row: Any, key: str, default: Any = None) -> Any:
    if hasattr(row, "get"):
        try:
            return row.get(key, default)
        except Exception:
            pass
    try:
        return row[key]
    except Exception:
        return default


def feature_value_is_finite(value: Any) -> bool:
    if value is None:
        return False
    try:
        if bool(pd.isna(value)):
            return False
    except Exception:
        pass
    parsed = finite_float(value)
    return parsed is not None and math.isfinite(parsed)


SOURCE_BAR_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "timestamp": ("timestamp", "timestamp_utc"),
    "timestamp_utc": ("timestamp_utc", "timestamp"),
    "symbol": ("symbol", "root_symbol"),
    "contract_symbol": ("contract_symbol", "raw_symbol", "symbol"),
    "open": ("open", "Open"),
    "high": ("high", "High"),
    "low": ("low", "Low"),
    "close": ("close", "last", "Last", "close_price"),
    "volume": ("volume", "Volume"),
    "signed_volume": ("signed_volume", "delta", "Delta"),
    "buy_volume": ("buy_volume", "ask_volume", "AskVolume"),
    "sell_volume": ("sell_volume", "bid_volume", "BidVolume"),
    "trades": ("trades", "count", "NumberOfTrades", "number_of_trades"),
}


def read_bars_file(
    path: Path,
    *,
    root_symbol: str,
    timezone: str,
    source: str,
    required_source_columns: Any = None,
) -> list[SourceMinuteBar]:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
    else:
        frame = pd.read_csv(path)
    if required_source_columns is not None:
        report = source_frame_column_readiness_report(frame, required_source_columns)
        if not bool(report.get("ok", False)):
            payload = {
                "event": "source_bar_file_missing_required_columns",
                "path": str(path),
                "source": source,
                **report,
                "impact": (
                    "The historical/replay file cannot satisfy the selected strategy data plan. "
                    "The engine refuses to synthesize missing orderflow fields because that can "
                    "produce false signals."
                ),
            }
            print_json(payload, prefix="SYSTEM_ALERT")
            labels = ", ".join(str(item.get("label")) for item in report.get("missing_required_column_groups", []))
            raise ValueError(f"bar file is missing required strategy source column groups: {labels}")
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
    base_report = source_frame_column_readiness_report(
        frame,
        ("timestamp", "open", "high", "low", "close", "volume"),
    )
    if not bool(base_report.get("ok", False)):
        labels = ", ".join(str(item.get("label")) for item in base_report.get("missing_required_column_groups", []))
        raise ValueError(f"bar file is missing required columns: {labels}")
    out = frame.copy()
    timestamp_utc_column = resolve_frame_column(out.columns, SOURCE_BAR_COLUMN_ALIASES["timestamp_utc"])
    timestamp_column = resolve_frame_column(out.columns, SOURCE_BAR_COLUMN_ALIASES["timestamp"])
    if timestamp_utc_column is not None:
        timestamps = pd.to_datetime(out[timestamp_utc_column], utc=True)
    else:
        timestamps = pd.to_datetime(out[timestamp_column])
        if getattr(timestamps.dt, "tz", None) is None:
            timestamps = timestamps.dt.tz_localize(timezone)
        timestamps = timestamps.dt.tz_convert("UTC")
    bars: list[SourceMinuteBar] = []
    extra_columns = [col for col in out.columns if is_bar_extra_column(col)]
    for position, (_, row) in enumerate(out.iterrows()):
        large = {column: float(row.get(column, 0.0) or 0.0) for column in extra_columns}
        signed = float(row_alias_value(row, SOURCE_BAR_COLUMN_ALIASES["signed_volume"], 0.0) or 0.0)
        buy_volume = float(
            row_alias_value(row, SOURCE_BAR_COLUMN_ALIASES["buy_volume"], max(signed, 0.0)) or 0.0
        )
        sell_volume = float(
            row_alias_value(row, SOURCE_BAR_COLUMN_ALIASES["sell_volume"], max(-signed, 0.0)) or 0.0
        )
        bars.append(
            SourceMinuteBar(
                timestamp_utc=pd.Timestamp(timestamps.iloc[position]).tz_convert("UTC"),
                symbol=str(row_alias_value(row, SOURCE_BAR_COLUMN_ALIASES["symbol"], root_symbol) or root_symbol),
                contract_symbol=str(
                    row_alias_value(row, SOURCE_BAR_COLUMN_ALIASES["contract_symbol"], root_symbol) or root_symbol
                ),
                open=float(row_alias_value(row, SOURCE_BAR_COLUMN_ALIASES["open"], 0.0)),
                high=float(row_alias_value(row, SOURCE_BAR_COLUMN_ALIASES["high"], 0.0)),
                low=float(row_alias_value(row, SOURCE_BAR_COLUMN_ALIASES["low"], 0.0)),
                close=float(row_alias_value(row, SOURCE_BAR_COLUMN_ALIASES["close"], 0.0)),
                volume=float(row_alias_value(row, SOURCE_BAR_COLUMN_ALIASES["volume"], 0.0)),
                signed_volume=signed,
                buy_volume=buy_volume,
                sell_volume=sell_volume,
                trades=int(row_alias_value(row, SOURCE_BAR_COLUMN_ALIASES["trades"], 0) or 0),
                large=large,
                source=source,
            )
        )
    return sorted(bars, key=lambda bar: (bar.timestamp_utc, bar.contract_symbol))


def source_frame_column_readiness_report(frame: Any, required_source_columns: Any) -> dict[str, Any]:
    required_groups = source_frame_required_column_groups(required_source_columns)
    missing = [
        group for group in required_groups if resolve_frame_column(frame.columns, group["aliases"]) is None
    ]
    columns = [str(column) for column in frame.columns]
    return {
        "ok": not missing,
        "field_count": len(columns),
        "sample_columns": columns[:25],
        "required_column_groups": required_groups,
        "missing_required_column_groups": missing,
    }


def source_frame_required_column_groups(required_source_columns: Any) -> list[dict[str, Any]]:
    raw_columns = [str(column) for column in (required_source_columns or []) if str(column)]
    groups: list[dict[str, Any]] = []
    seen_labels: set[str] = set()
    timestamp_needed = any(column in {"timestamp", "timestamp_utc"} for column in raw_columns)
    identity_needed = any(column in {"symbol", "contract_symbol"} for column in raw_columns)
    if timestamp_needed:
        groups.append({"label": "bar timestamp", "columns": ["timestamp", "timestamp_utc"], "aliases": ["timestamp", "timestamp_utc"]})
        seen_labels.add("bar timestamp")
    if identity_needed:
        groups.append(
            {
                "label": "contract identity",
                "columns": ["symbol", "contract_symbol"],
                "aliases": ["contract_symbol", "raw_symbol", "symbol"],
            }
        )
        seen_labels.add("contract identity")
    for column in raw_columns:
        if column in {"timestamp", "timestamp_utc", "symbol", "contract_symbol"}:
            continue
        label = f"source column {column}"
        if label in seen_labels:
            continue
        aliases = list(SOURCE_BAR_COLUMN_ALIASES.get(column, (column,)))
        groups.append({"label": label, "columns": [column], "aliases": aliases})
        seen_labels.add(label)
    return groups


def resolve_frame_column(columns: Any, aliases: Any) -> str | None:
    aliases_list = [str(alias) for alias in aliases]
    column_names = [str(column) for column in columns]
    exact = {name: name for name in column_names}
    lower = {name.lower(): name for name in column_names}
    for alias in aliases_list:
        if alias in exact:
            return exact[alias]
        match = lower.get(alias.lower())
        if match is not None:
            return match
    return None


def row_alias_value(row: Any, aliases: Any, default: Any = None) -> Any:
    column = resolve_frame_column(row.index, aliases)
    if column is None:
        return default
    value = row.get(column, default)
    try:
        if bool(pd.isna(value)):
            return default
    except Exception:
        pass
    return value


def is_bar_extra_column(column: str) -> bool:
    if column.startswith("large") and column.endswith(("_volume", "_signed_volume")):
        return True
    prefixes = (
        "selected_delta_",
        "databento_",
        "quote_",
        "tick_rule_",
    )
    return column.startswith(prefixes) and column.endswith(("volume", "delta"))


def live_record_to_tick(
    record: Any,
    *,
    default_contract_symbol: str,
    symbology_map: dict[Any, Any] | None = None,
    require_trade_action: bool = False,
) -> TradeTick | None:
    if not hasattr(record, "price") or not hasattr(record, "size") or not hasattr(record, "ts_event"):
        return None
    raw_action = getattr(record, "action", None)
    if require_trade_action and raw_action is None:
        return None
    action = normalize_action("T" if raw_action is None else raw_action)
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
        bid_price=record_book_price(record, "bid"),
        ask_price=record_book_price(record, "ask"),
    )


def record_price(record: Any) -> float | None:
    pretty = getattr(record, "pretty_price", None)
    value = pretty() if callable(pretty) else pretty
    parsed = finite_float(value)
    if parsed is not None:
        return parsed
    return normalize_databento_price(getattr(record, "price", None))


def record_book_price(record: Any, side: str) -> float | None:
    pretty_name = f"pretty_{side}_px_00"
    pretty = getattr(record, pretty_name, None)
    value = pretty() if callable(pretty) else pretty
    parsed = finite_float(value)
    if parsed is not None:
        return parsed

    for attr in (f"{side}_px_00", f"{side}_price", f"{side}_px"):
        parsed = normalize_databento_price(getattr(record, attr, None))
        if parsed is not None:
            return parsed

    levels = getattr(record, "levels", None)
    levels = levels() if callable(levels) else levels
    if levels:
        try:
            level = levels[0]
        except Exception:
            level = None
        if level is not None:
            pretty = getattr(level, f"pretty_{side}_px", None)
            value = pretty() if callable(pretty) else pretty
            parsed = finite_float(value)
            if parsed is not None:
                return parsed
            parsed = normalize_databento_price(getattr(level, f"{side}_px", None))
            if parsed is not None:
                return parsed
    return None


def normalize_databento_price(value: Any) -> float | None:
    raw = finite_float(value)
    if raw is None:
        return None
    if abs(raw) > 1_000_000_000_000_000:
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


def historical_bounds(hist_cfg: dict[str, Any], timezone: str, *, max_end: Any | None = None) -> tuple[Any, Any]:
    end = hist_cfg.get("end")
    if end is None:
        end_ts = pd.Timestamp(max_end) if max_end is not None else pd.Timestamp.now(tz="UTC")
    else:
        end_ts = pd.Timestamp(end)
        end_ts = end_ts.tz_localize(timezone).tz_convert("UTC") if end_ts.tzinfo is None else end_ts.tz_convert("UTC")
        if max_end is not None and end_ts > pd.Timestamp(max_end):
            end_ts = pd.Timestamp(max_end)
    start = hist_cfg.get("start")
    if start is None:
        lookback_days = int(hist_cfg.get("lookback_days", 70))
        start_ts = end_ts - pd.Timedelta(days=lookback_days)
    else:
        start_ts = pd.Timestamp(start)
        start_ts = start_ts.tz_localize(timezone).tz_convert("UTC") if start_ts.tzinfo is None else start_ts.tz_convert("UTC")
    return start_ts, end_ts


def databento_api_key_status(config: dict[str, Any], *, required: bool = True) -> dict[str, Any]:
    env_name = str(config.get("api_key_env", "DATABENTO_API_KEY"))
    direct = config.get("api_key")
    direct_present = not is_missing_or_blank(direct)
    env_value = os.getenv(env_name)
    env_present = not is_missing_or_blank(env_value)
    key_value = str(direct) if direct_present else (str(env_value) if env_present else "")
    ok = direct_present or env_present
    status: dict[str, Any] = {
        "ok": ok or not required,
        "required": bool(required),
        "api_key_env": env_name,
        "source": "databento.api_key" if direct_present else (f"${env_name}" if env_present else None),
        "configured_directly": direct_present,
        "env_present": env_present,
        "key_present": ok,
        "key_length": len(key_value) if ok else 0,
        "value_redacted": True,
    }
    if not ok:
        message = (
            f"Missing Databento API key. Set ${env_name} or databento.api_key. "
            "If the key is defined in a shell profile such as ~/.zprofile, start "
            "the engine from a shell that has sourced that profile."
        )
        status["error"] = message
        status["profile_hint"] = "Run from a shell that sourced ~/.zprofile, or run `source ~/.zprofile` first."
    return status


def databento_api_key(config: dict[str, Any]) -> str:
    direct = config.get("api_key")
    if not is_missing_or_blank(direct):
        return str(direct)
    env_name = str(config.get("api_key_env", "DATABENTO_API_KEY"))
    value = os.getenv(env_name)
    if is_missing_or_blank(value):
        status = databento_api_key_status(config, required=True)
        raise RuntimeError(str(status["error"]))
    return value


def engine_large_trade_sizes(databento_config: dict[str, Any]) -> list[int]:
    values = databento_config.get("large_trade_sizes", [])
    if values is None:
        return []
    return [int(value) for value in values]


def effective_large_trade_sizes(engine: SignalEngine) -> list[int]:
    configured = set(engine_large_trade_sizes(engine.databento_config))
    inferred = {int(value) for value in engine.data_plan.get("large_trade_sizes", []) if int(value) > 0}
    return sorted(configured | inferred)


def normalize_delta_method(value: Any) -> str:
    text = str(value or "aggressor_side").strip().lower().replace("-", "_")
    aliases = {
        "aggressor": "aggressor_side",
        "aggressor_side": "aggressor_side",
        "databento": "aggressor_side",
        "databento_side": "aggressor_side",
        "exchange_aggressor": "aggressor_side",
        "side": "aggressor_side",
        "side_aggressor": "aggressor_side",
        "bid_ask": "price_vs_quote",
        "ask_bid": "price_vs_quote",
        "price_vs_quote": "price_vs_quote",
        "quote": "price_vs_quote",
        "quote_price": "price_vs_quote",
        "top_of_book": "price_vs_quote",
        "trade_at_quote": "price_vs_quote",
        "tick": "tick_rule",
        "tick_rule": "tick_rule",
        "up_down_tick": "tick_rule",
        "price_change": "tick_rule",
    }
    if text not in aliases:
        allowed = ", ".join(sorted(set(aliases.values())))
        raise ValueError(f"databento.delta_method must be one of: {allowed}")
    return aliases[text]


def signed_volume_from_aggressor_side(side: str, size: float) -> float:
    normalized = normalize_side(side)
    if normalized == "B":
        return float(size)
    if normalized == "A":
        return -float(size)
    return 0.0


def signed_volume_from_quote(tick: TradeTick) -> float | None:
    bid = finite_float(tick.bid_price)
    ask = finite_float(tick.ask_price)
    if bid is None or ask is None:
        return None
    epsilon = 1e-9
    if tick.price >= ask - epsilon:
        return float(tick.size)
    if tick.price <= bid + epsilon:
        return -float(tick.size)
    return 0.0


def select_delta_signed_volume(
    delta_method: str,
    *,
    side_signed: float,
    quote_signed: float | None,
    tick_rule_signed: float,
) -> float:
    method = normalize_delta_method(delta_method)
    if method == "aggressor_side":
        return side_signed
    if method == "price_vs_quote":
        return 0.0 if quote_signed is None else quote_signed
    if method == "tick_rule":
        return tick_rule_signed
    raise ValueError(f"Unsupported delta method: {delta_method}")


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


def build_builtin_variant_config(strategy_spec: dict[str, Any], engine_config: dict[str, Any]) -> dict[str, Any]:
    strategy_type = str(strategy_spec.get("type", "builtin_delta_interval")).lower()
    params = copy.deepcopy(strategy_spec.get("params", {}))
    data = copy.deepcopy(strategy_spec.get("data", {}))
    core = copy.deepcopy(strategy_spec.get("core", {}))
    symbol = str(strategy_spec.get("symbol") or engine_config.get("symbol") or DEFAULT_SYMBOL)
    timezone = str(strategy_spec.get("timezone") or engine_config.get("timezone") or DEFAULT_TIMEZONE)
    timeframe = str(strategy_spec.get("timeframe") or params.get("timeframe") or "1m")

    data.setdefault("symbol", symbol)
    data.setdefault("timezone", timezone)
    data.setdefault("exchange_timezone", timezone)
    data.setdefault("source_timeframe", "1m")
    data.setdefault("feature_set", "none")
    data.setdefault("warmup_days", 0)
    data.setdefault("rth_start", "09:30:00")
    data.setdefault("rth_end", "15:59:00")

    tick_size = float(params.get("tick_size", core.get("tick_size", 0.25)))
    core.setdefault("initial_balance", float(engine_config.get("account", {}).get("net_liq", 150000)))
    core.setdefault("tick_size", tick_size)
    core.setdefault("tick_value", float(params.get("tick_value", 12.5)))
    core.setdefault("slippage_ticks", float(params.get("slippage_ticks", 0.0)))
    core.setdefault("contracts", int(params.get("contracts", 1)))
    core.setdefault("position_sizing", {"mode": "fixed_contracts", "contracts": int(core.get("contracts", 1))})

    params.setdefault("interval_bars", 5)
    params.setdefault("delta_window_bars", params["interval_bars"])
    params.setdefault("delta_mode", "window_sum")
    params.setdefault("delta_column", "signed_volume")
    params.setdefault("min_abs_delta", 0.0)
    params.setdefault("stop_mode", "bar_extreme")
    params.setdefault("stop_points", 1.0)
    params.setdefault("target_r_multiple", 1.0)
    params.setdefault("tick_size", tick_size)

    return {
        "variant_id": str(strategy_spec.get("id") or strategy_type),
        "strategy_name": "dummy_delta_interval",
        "symbol": symbol,
        "timeframe": timeframe,
        "data": data,
        "strategy": {
            "entry": {"module": strategy_type, "params": params},
            "sl": {
                "module": "builtin_bar_extreme" if params["stop_mode"] == "bar_extreme" else "builtin_fixed_points",
                "params": {"stop_mode": params["stop_mode"], "stop_points": params["stop_points"]},
            },
            "tp": {"module": "builtin_fixed_r", "params": {"target_r_multiple": params["target_r_multiple"]}},
        },
        "core": core,
    }


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


def resolve_cli_path(base: Path, value: str | os.PathLike[str]) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    cwd_relative = path.resolve()
    if cwd_relative.exists():
        return cwd_relative
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


def contains_trade_orderflow_reference(value: Any) -> bool:
    if isinstance(value, dict):
        return any(contains_trade_orderflow_reference(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_trade_orderflow_reference(item) for item in value)
    if isinstance(value, str):
        text = value.lower()
        return "trade_orderflow" in text or "of_combo" in text
    return False


def collect_feature_column_references(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"feature_column", "rank_column", "column", "flow_column"} and isinstance(item, str):
                found.add(item)
            elif key == "columns" and isinstance(item, list):
                found.update(str(column) for column in item if isinstance(column, str))
            found.update(collect_feature_column_references(item))
    elif isinstance(value, list):
        for item in value:
            found.update(collect_feature_column_references(item))
    return found


def large_trade_sizes_from_feature_columns(columns: Any) -> set[int]:
    sizes: set[int] = set()
    for column in columns or []:
        text = str(column)
        for match in re.finditer(r"(?:^|_)large(\d+)(?:_|$)", text):
            size = int(match.group(1))
            if size > 0:
                sizes.add(size)
    return sizes


def estimate_session_bars(data_config: dict[str, Any], source_timeframe: str) -> int:
    source_minutes = max(1, parse_timeframe_minutes(source_timeframe))
    start = parse_clock(data_config.get("rth_start", "09:30:00"))
    end = parse_clock(data_config.get("rth_end", "15:59:00"))
    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute
    if end_minutes < start_minutes:
        end_minutes += 24 * 60
    duration_minutes = max(source_minutes, end_minutes - start_minutes + source_minutes)
    return max(1, int(math.ceil(duration_minutes / source_minutes)))


def parse_clock(value: Any) -> dt.time:
    text = str(value).strip().strip("'\"")
    try:
        return dt.time.fromisoformat(text)
    except ValueError:
        return dt.datetime.strptime(text, "%H:%M").time()


def count_bar_sessions(bars: list[SourceMinuteBar], timezone: str) -> int:
    return len({local_session_date(bar.timestamp_utc, timezone) for bar in bars})


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


def nearly_equal(left: Any, right: Any, *, tolerance: float = 1e-9) -> bool:
    left_float = finite_float(left)
    right_float = finite_float(right)
    if left_float is None or right_float is None:
        return False
    return abs(left_float - right_float) <= tolerance


def estimated_market_entry(price: float, direction: str, tick_size: float, slippage_ticks: float) -> float:
    slip = tick_size * slippage_ticks
    return price + slip if direction == "long" else price - slip


def round_to_tick(value: float, tick_size: float) -> float:
    if tick_size <= 0:
        return float(value)
    return float(round(round(value / tick_size) * tick_size, 10))


def is_on_tick_grid(value: Any, tick_size: float, *, tolerance: float = 1e-9) -> bool:
    parsed = finite_float(value)
    if parsed is None or tick_size <= 0:
        return False
    return abs(parsed - round_to_tick(parsed, tick_size)) <= tolerance


def tick_adjustment(raw: float, rounded: float, tick_size: float) -> float:
    if tick_size <= 0:
        return 0.0
    return float(round((rounded - raw) / tick_size, 10))


def price_normalization_report(
    *,
    tick_size: float,
    entry_basis_price_raw: float,
    entry_price_raw: float,
    stop_loss_price_raw: float,
    take_profit_price_raw: float,
    entry_basis_price: float,
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float,
) -> dict[str, Any]:
    adjustments = {
        "entry_basis_price_adjustment_ticks": tick_adjustment(entry_basis_price_raw, entry_basis_price, tick_size),
        "entry_price_adjustment_ticks": tick_adjustment(entry_price_raw, entry_price, tick_size),
        "stop_loss_price_adjustment_ticks": tick_adjustment(stop_loss_price_raw, stop_loss_price, tick_size),
        "take_profit_price_adjustment_ticks": tick_adjustment(take_profit_price_raw, take_profit_price, tick_size),
    }
    return {
        "schema_version": "price_normalization.v1",
        "tick_size": tick_size,
        "entry_basis_price_raw": float(entry_basis_price_raw),
        "entry_price_raw": float(entry_price_raw),
        "stop_loss_price_raw": float(stop_loss_price_raw),
        "take_profit_price_raw": float(take_profit_price_raw),
        "entry_basis_price": float(entry_basis_price),
        "entry_price": float(entry_price),
        "stop_loss_price": float(stop_loss_price),
        "take_profit_price": float(take_profit_price),
        **adjustments,
        "normalized": any(abs(value) > 1e-9 for value in adjustments.values()),
    }


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


def config_fingerprint_payload(value: Any, *, kind: str, path: Any) -> dict[str, Any]:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=json_default)
    return {
        "schema_version": CONFIG_FINGERPRINT_VERSION,
        "kind": str(kind),
        "path": str(path),
        "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }


def validate_config_fingerprint_payload(value: Any, *, path: Any | None = None, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    required = {"schema_version", "kind", "path", "sha256"}
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"{label} missing required field(s): {missing}")
    if value["schema_version"] != CONFIG_FINGERPRINT_VERSION:
        raise ValueError(f"unsupported {label} version: {value['schema_version']}")
    for key in ("kind", "path"):
        if not str(value.get(key) or "").strip():
            raise ValueError(f"{label}.{key} must be non-empty")
    expected_path = str(path or "")
    if expected_path and value.get("path") != expected_path:
        raise ValueError(f"{label}.path must match expected path")
    sha256 = str(value.get("sha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError(f"{label}.sha256 must be a lowercase 64-character hex digest")


def validate_setup_notice_contract(notice: dict[str, Any]) -> None:
    required = {
        "event",
        "setup_contract_version",
        "setup_id",
        "pending_signal_key",
        "strategy_id",
        "strategy_name",
        "strategy_config",
        "strategy_config_fingerprint",
        "engine_config",
        "engine_config_fingerprint",
        "symbol",
        "contract_symbol",
        "timeframe",
        "signal_timestamp",
        "due_timestamp_utc",
        "expires_at_utc",
        "entry_window",
        "max_entry_lag_seconds",
        "direction",
        "side",
        "signal",
    }
    missing = sorted(required - set(notice))
    if missing:
        raise ValueError(f"setup notice missing required field(s): {missing}")
    if notice["event"] != "trade_setup":
        raise ValueError("setup notice event must be 'trade_setup'")
    if notice["setup_contract_version"] != SETUP_NOTICE_CONTRACT_VERSION:
        raise ValueError(f"unsupported setup contract version: {notice['setup_contract_version']}")
    for key in (
        "setup_id",
        "pending_signal_key",
        "strategy_id",
        "strategy_config",
        "engine_config",
        "symbol",
        "contract_symbol",
        "timeframe",
    ):
        if not str(notice.get(key) or "").strip():
            raise ValueError(f"setup notice field {key!r} must be non-empty")
    validate_config_fingerprint_payload(
        notice["strategy_config_fingerprint"],
        path=notice.get("strategy_config"),
        label="setup notice strategy_config_fingerprint",
    )
    validate_config_fingerprint_payload(
        notice["engine_config_fingerprint"],
        path=notice.get("engine_config"),
        label="setup notice engine_config_fingerprint",
    )
    direction = str(notice["direction"]).lower()
    side = str(notice["side"]).lower()
    if direction not in {"long", "short"}:
        raise ValueError("setup notice direction must be long or short")
    if side not in {"buy", "sell"}:
        raise ValueError("setup notice side must be buy or sell")
    if (direction == "long" and side != "buy") or (direction == "short" and side != "sell"):
        raise ValueError("setup notice side is inconsistent with direction")
    if config_float(notice, "max_entry_lag_seconds", 120.0, min_value=0.001) <= 0:
        raise ValueError("setup notice max_entry_lag_seconds must be positive")
    try:
        signal_ts = pd.Timestamp(notice["signal_timestamp"])
        due_ts = normalize_utc_timestamp(notice["due_timestamp_utc"])
        expires_at_utc = normalize_utc_timestamp(notice["expires_at_utc"])
    except Exception as exc:
        raise ValueError("setup notice signal_timestamp, due_timestamp_utc, and expires_at_utc must parse as timestamps") from exc
    if signal_ts.tzinfo is None:
        raise ValueError("setup notice signal_timestamp must include a timezone")
    if due_ts.tzinfo is None:
        raise ValueError("setup notice due_timestamp_utc must include a timezone")
    if expires_at_utc <= due_ts:
        raise ValueError("setup notice expires_at_utc must be after due_timestamp_utc")
    expected_expires = due_ts + pd.Timedelta(seconds=float(notice["max_entry_lag_seconds"]))
    if abs((expires_at_utc - expected_expires).total_seconds()) > 1e-6:
        raise ValueError("setup notice expires_at_utc must match max_entry_lag_seconds")
    entry_window = notice.get("entry_window")
    if not isinstance(entry_window, dict):
        raise ValueError("setup notice entry_window must be a mapping")
    if entry_window.get("valid_from_utc") != notice["due_timestamp_utc"]:
        raise ValueError("setup notice entry_window.valid_from_utc must match due_timestamp_utc")
    if entry_window.get("expires_at_utc") != notice["expires_at_utc"]:
        raise ValueError("setup notice entry_window.expires_at_utc must match expires_at_utc")
    if not nearly_equal(entry_window.get("max_entry_lag_seconds"), notice["max_entry_lag_seconds"]):
        raise ValueError("setup notice entry_window.max_entry_lag_seconds must match max_entry_lag_seconds")
    if not isinstance(notice.get("signal"), dict):
        raise ValueError("setup notice signal must be a mapping")
    if "trade_plan_preview" in notice:
        validate_setup_trade_plan_preview(notice["trade_plan_preview"])


def validate_setup_trade_plan_preview(preview: Any) -> None:
    if not isinstance(preview, dict):
        raise ValueError("setup notice trade_plan_preview must be a mapping")
    required = {"schema_version", "status", "executable", "entry_price_basis", "entry_price_type"}
    missing = sorted(required - set(preview))
    if missing:
        raise ValueError(f"setup notice trade_plan_preview missing required field(s): {missing}")
    if preview["schema_version"] != "trade_plan_preview.v1":
        raise ValueError(f"unsupported setup notice trade_plan_preview version: {preview['schema_version']}")
    if preview["executable"] is not False:
        raise ValueError("setup notice trade_plan_preview.executable must be false")
    status = str(preview.get("status") or "")
    if status not in {"estimated", "unavailable"}:
        raise ValueError("setup notice trade_plan_preview.status must be estimated or unavailable")
    if status == "unavailable":
        if not str(preview.get("reason") or "").strip():
            raise ValueError("setup notice trade_plan_preview.reason must explain why preview is unavailable")
        return
    for key in (
        "estimated_entry_basis_price",
        "estimated_entry_price",
        "stop_loss_price",
        "take_profit_price",
        "stop_loss_points",
        "take_profit_points",
        "tick_size",
        "tick_value",
        "risk_dollars",
        "reward_dollars",
    ):
        require_finite(preview.get(key), f"setup notice trade_plan_preview.{key}")
    for key in ("quantity", "suggested_quantity"):
        value = preview.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"setup notice trade_plan_preview.{key} must be a positive integer")


def build_execution_intent(
    alert: dict[str, Any],
    *,
    max_entry_lag_seconds: float,
    intent_ttl_seconds: float | None = None,
) -> dict[str, Any]:
    ttl_seconds = float(max_entry_lag_seconds if intent_ttl_seconds is None else intent_ttl_seconds)
    if ttl_seconds <= 0:
        raise ValueError("execution intent ttl must be positive")
    entry_utc = normalize_utc_timestamp(alert["entry_timestamp_utc"])
    expires_utc = entry_utc + pd.Timedelta(seconds=ttl_seconds)
    return {
        "schema_version": EXECUTION_INTENT_VERSION,
        "intent_id": alert["alert_id"],
        "intent_type": "entry",
        "status": "ready_for_manual_or_future_router",
        "asset_class": "futures",
        "symbol": alert["symbol"],
        "contract_symbol": alert["contract_symbol"],
        "timeframe": alert["timeframe"],
        "direction": alert["direction"],
        "side": alert["side"],
        "quantity": int(alert["quantity"]),
        "order": {
            "order_type": alert["order_type"],
            "entry_price_type": "estimated_market",
            "estimated_entry_price": alert["entry_price"],
            "basis_price": alert["entry_basis_price"],
            "slippage_ticks": alert["entry_slippage_ticks"],
        },
        "bracket": {
            "stop_loss_price": alert["stop_loss_price"],
            "take_profit_price": alert["take_profit_price"],
            "stop_loss_points": alert["stop_loss_points"],
            "take_profit_points": alert["take_profit_points"],
        },
        "risk": {
            "tick_size": alert["tick_size"],
            "tick_value": alert["tick_value"],
            "risk_dollars": alert["risk_dollars"],
            "reward_dollars": alert["reward_dollars"],
        },
        "price_normalization": copy.deepcopy(alert.get("price_normalization")),
        "timing": {
            "signal_timestamp": alert["signal_timestamp"],
            "entry_timestamp": alert["entry_timestamp"],
            "entry_timestamp_utc": alert["entry_timestamp_utc"],
            "valid_from_utc": format_timestamp(entry_utc),
            "expires_at_utc": format_timestamp(expires_utc),
            "intent_ttl_seconds": ttl_seconds,
            "max_entry_lag_seconds": float(max_entry_lag_seconds),
        },
        "source": {
            "setup_id": alert["setup_id"],
            "pending_signal_key": alert["pending_signal_key"],
            "strategy_id": alert["strategy_id"],
            "strategy_name": alert["strategy_name"],
            "strategy_config": alert["strategy_config"],
            "strategy_config_fingerprint": copy.deepcopy(alert.get("strategy_config_fingerprint")),
            "engine_config": alert["engine_config"],
            "engine_config_fingerprint": copy.deepcopy(alert.get("engine_config_fingerprint")),
            "delta_method": alert.get("delta_method"),
            "session_date": alert.get("session_date"),
        },
    }


def build_execution_intent_record(alert: dict[str, Any]) -> dict[str, Any]:
    return {
        "event": "execution_intent_ready",
        "record_schema_version": EXECUTION_INTENT_RECORD_VERSION,
        "created_at_utc": utc_now_iso(),
        "alert_contract_version": alert.get("alert_contract_version"),
        "alert_id": alert.get("alert_id"),
        "setup_id": alert.get("setup_id"),
        "pending_signal_key": alert.get("pending_signal_key"),
        "strategy_id": alert.get("strategy_id"),
        "strategy_config_fingerprint": copy.deepcopy(alert.get("strategy_config_fingerprint")),
        "engine_config": alert.get("engine_config"),
        "engine_config_fingerprint": copy.deepcopy(alert.get("engine_config_fingerprint")),
        "symbol": alert.get("symbol"),
        "contract_symbol": alert.get("contract_symbol"),
        "timeframe": alert.get("timeframe"),
        "entry_timestamp_utc": alert.get("entry_timestamp_utc"),
        "execution_intent": copy.deepcopy(alert.get("execution_intent")),
    }


def validate_entry_alert_contract(alert: dict[str, Any]) -> None:
    required = {
        "event",
        "alert_contract_version",
        "alert_id",
        "setup_id",
        "pending_signal_key",
        "strategy_id",
        "strategy_config",
        "strategy_config_fingerprint",
        "engine_config",
        "engine_config_fingerprint",
        "symbol",
        "contract_symbol",
        "direction",
        "side",
        "quantity",
        "order_type",
        "entry_price",
        "entry_basis_price",
        "entry_slippage_ticks",
        "take_profit_price",
        "stop_loss_price",
        "take_profit_points",
        "stop_loss_points",
        "tick_size",
        "tick_value",
        "risk_dollars",
        "reward_dollars",
        "price_normalization",
        "execution_intent",
    }
    missing = sorted(required - set(alert))
    if missing:
        raise ValueError(f"entry alert missing required field(s): {missing}")
    if alert["event"] != "entry_signal":
        raise ValueError("entry alert event must be 'entry_signal'")
    if alert["alert_contract_version"] != ALERT_CONTRACT_VERSION:
        raise ValueError(f"unsupported alert contract version: {alert['alert_contract_version']}")
    for key in (
        "alert_id",
        "setup_id",
        "pending_signal_key",
        "strategy_id",
        "strategy_config",
        "engine_config",
        "symbol",
        "contract_symbol",
        "timeframe",
    ):
        if not str(alert.get(key) or "").strip():
            raise ValueError(f"entry alert field {key!r} must be non-empty")
    validate_config_fingerprint_payload(
        alert["strategy_config_fingerprint"],
        path=alert.get("strategy_config"),
        label="entry alert strategy_config_fingerprint",
    )
    validate_config_fingerprint_payload(
        alert["engine_config_fingerprint"],
        path=alert.get("engine_config"),
        label="entry alert engine_config_fingerprint",
    )
    direction = str(alert["direction"]).lower()
    side = str(alert["side"]).lower()
    if direction not in {"long", "short"}:
        raise ValueError("entry alert direction must be long or short")
    if side not in {"buy", "sell"}:
        raise ValueError("entry alert side must be buy or sell")
    if (direction == "long" and side != "buy") or (direction == "short" and side != "sell"):
        raise ValueError("entry alert side is inconsistent with direction")
    quantity = int(alert["quantity"])
    if quantity <= 0:
        raise ValueError("entry alert quantity must be positive")
    for key in (
        "entry_price",
        "take_profit_price",
        "stop_loss_price",
        "tick_size",
        "tick_value",
        "risk_dollars",
        "reward_dollars",
    ):
        value = finite_float(alert.get(key))
        if value is None:
            raise ValueError(f"entry alert field {key!r} must be finite")
        if key in {"tick_size", "tick_value", "risk_dollars", "reward_dollars"} and value <= 0:
            raise ValueError(f"entry alert field {key!r} must be positive")
    tick_size = finite_float(alert["tick_size"])
    tick_value = finite_float(alert["tick_value"])
    if tick_size is None or tick_value is None:
        raise ValueError("entry alert tick_size and tick_value must be finite")
    for key in ("entry_price", "entry_basis_price", "take_profit_price", "stop_loss_price"):
        if not is_on_tick_grid(alert.get(key), tick_size):
            raise ValueError(f"entry alert field {key!r} must be on the configured tick grid")
    if direction == "long" and not (alert["stop_loss_price"] < alert["entry_price"] < alert["take_profit_price"]):
        raise ValueError("long entry alert stop/entry/target ordering is invalid")
    if direction == "short" and not (alert["take_profit_price"] < alert["entry_price"] < alert["stop_loss_price"]):
        raise ValueError("short entry alert stop/entry/target ordering is invalid")
    stop_points = abs(float(alert["entry_price"]) - float(alert["stop_loss_price"]))
    target_points = abs(float(alert["take_profit_price"]) - float(alert["entry_price"]))
    if not nearly_equal(finite_float(alert.get("stop_loss_points")), stop_points):
        raise ValueError("entry alert stop_loss_points must match executable entry/stop prices")
    if not nearly_equal(finite_float(alert.get("take_profit_points")), target_points):
        raise ValueError("entry alert take_profit_points must match executable entry/target prices")
    quantity = int(alert["quantity"])
    expected_risk = stop_points / tick_size * tick_value * quantity
    expected_reward = target_points / tick_size * tick_value * quantity
    if not nearly_equal(finite_float(alert.get("risk_dollars")), expected_risk):
        raise ValueError("entry alert risk_dollars must match executable stop distance")
    if not nearly_equal(finite_float(alert.get("reward_dollars")), expected_reward):
        raise ValueError("entry alert reward_dollars must match executable target distance")
    validate_price_normalization_contract(alert["price_normalization"], alert)
    validate_execution_intent_contract(alert["execution_intent"], alert)


def validate_execution_intent_contract(intent: Any, alert: dict[str, Any]) -> None:
    if not isinstance(intent, dict):
        raise ValueError("execution_intent must be a mapping")
    validate_execution_intent_payload_contract(intent)
    required = {"schema_version", "intent_id", "intent_type", "symbol", "contract_symbol", "side", "quantity", "order", "bracket", "risk", "timing", "source"}
    missing = sorted(required - set(intent))
    if missing:
        raise ValueError(f"execution_intent missing required field(s): {missing}")
    if intent["schema_version"] != EXECUTION_INTENT_VERSION:
        raise ValueError(f"unsupported execution intent version: {intent['schema_version']}")
    if intent["intent_id"] != alert["alert_id"]:
        raise ValueError("execution_intent.intent_id must match alert_id")
    if intent["intent_type"] != "entry":
        raise ValueError("execution_intent.intent_type must be entry")
    for key in ("symbol", "contract_symbol", "side", "quantity", "direction"):
        if intent.get(key) != alert.get(key):
            raise ValueError(f"execution_intent.{key} must match alert field {key}")
    order = intent["order"]
    bracket = intent["bracket"]
    risk = intent["risk"]
    timing = intent["timing"]
    if not isinstance(timing, dict):
        raise ValueError("execution_intent.timing must be a mapping")
    timing_required = {
        "signal_timestamp",
        "entry_timestamp",
        "entry_timestamp_utc",
        "valid_from_utc",
        "expires_at_utc",
        "intent_ttl_seconds",
        "max_entry_lag_seconds",
    }
    timing_missing = sorted(timing_required - set(timing))
    if timing_missing:
        raise ValueError(f"execution_intent.timing missing required field(s): {timing_missing}")
    if order.get("order_type") != alert["order_type"]:
        raise ValueError("execution_intent.order.order_type must match alert order_type")
    if finite_float(order.get("estimated_entry_price")) != finite_float(alert["entry_price"]):
        raise ValueError("execution_intent.order.estimated_entry_price must match alert entry_price")
    if finite_float(bracket.get("stop_loss_price")) != finite_float(alert["stop_loss_price"]):
        raise ValueError("execution_intent.bracket.stop_loss_price must match alert stop_loss_price")
    if finite_float(bracket.get("take_profit_price")) != finite_float(alert["take_profit_price"]):
        raise ValueError("execution_intent.bracket.take_profit_price must match alert take_profit_price")
    if finite_float(risk.get("risk_dollars")) != finite_float(alert["risk_dollars"]):
        raise ValueError("execution_intent.risk.risk_dollars must match alert risk_dollars")
    if intent.get("price_normalization") != alert.get("price_normalization"):
        raise ValueError("execution_intent.price_normalization must match alert price_normalization")
    source = intent.get("source")
    if not isinstance(source, dict):
        raise ValueError("execution_intent.source must be a mapping")
    if source.get("setup_id") != alert.get("setup_id"):
        raise ValueError("execution_intent.source.setup_id must match alert")
    if source.get("pending_signal_key") != alert.get("pending_signal_key"):
        raise ValueError("execution_intent.source.pending_signal_key must match alert")
    if source.get("strategy_config") != alert.get("strategy_config"):
        raise ValueError("execution_intent.source.strategy_config must match alert strategy_config")
    if source.get("strategy_config_fingerprint") != alert.get("strategy_config_fingerprint"):
        raise ValueError("execution_intent.source.strategy_config_fingerprint must match alert")
    validate_config_fingerprint_payload(
        source.get("strategy_config_fingerprint"),
        path=source.get("strategy_config"),
        label="execution_intent.source.strategy_config_fingerprint",
    )
    if source.get("engine_config") != alert.get("engine_config"):
        raise ValueError("execution_intent.source.engine_config must match alert engine_config")
    if source.get("engine_config_fingerprint") != alert.get("engine_config_fingerprint"):
        raise ValueError("execution_intent.source.engine_config_fingerprint must match alert")
    validate_config_fingerprint_payload(
        source.get("engine_config_fingerprint"),
        path=source.get("engine_config"),
        label="execution_intent.source.engine_config_fingerprint",
    )
    try:
        entry_utc = normalize_utc_timestamp(alert["entry_timestamp_utc"])
        valid_from_utc = normalize_utc_timestamp(timing["valid_from_utc"])
        expires_at_utc = normalize_utc_timestamp(timing["expires_at_utc"])
    except Exception as exc:
        raise ValueError("execution_intent timing timestamps must parse as UTC timestamps") from exc
    if valid_from_utc != entry_utc:
        raise ValueError("execution_intent.timing.valid_from_utc must match alert entry_timestamp_utc")
    ttl_seconds = finite_float(timing.get("intent_ttl_seconds"))
    if ttl_seconds is None or ttl_seconds <= 0:
        raise ValueError("execution_intent.timing.intent_ttl_seconds must be positive")
    if expires_at_utc <= valid_from_utc:
        raise ValueError("execution_intent.timing.expires_at_utc must be after valid_from_utc")
    expected_expires = valid_from_utc + pd.Timedelta(seconds=float(ttl_seconds))
    if abs((expires_at_utc - expected_expires).total_seconds()) > 1e-6:
        raise ValueError("execution_intent.timing.expires_at_utc must match intent_ttl_seconds")


def execution_intent_freshness_report(
    intent: Any,
    *,
    now_utc: Any | None = None,
    grace_seconds: float = 0.0,
) -> dict[str, Any]:
    now = normalize_utc_timestamp(pd.Timestamp.utcnow() if now_utc is None else now_utc)
    grace = max(0.0, float(grace_seconds))
    report: dict[str, Any] = {
        "actionable": False,
        "state": "invalid",
        "now_utc": format_timestamp(now),
        "freshness_grace_seconds": grace,
        "valid_from_utc": None,
        "expires_at_utc": None,
        "seconds_until_valid": None,
        "seconds_until_expiry": None,
    }
    if not isinstance(intent, dict):
        report["reason"] = "execution_intent is not a mapping"
        return report
    timing = intent.get("timing")
    if not isinstance(timing, dict):
        report["reason"] = "execution_intent.timing is not a mapping"
        return report
    try:
        valid_from_utc = normalize_utc_timestamp(timing["valid_from_utc"])
        expires_at_utc = normalize_utc_timestamp(timing["expires_at_utc"])
    except Exception as exc:
        report["reason"] = "execution_intent timing timestamps could not be parsed"
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)
        return report
    seconds_until_valid = (valid_from_utc - now).total_seconds()
    seconds_until_expiry = (expires_at_utc - now).total_seconds()
    report.update(
        {
            "valid_from_utc": format_timestamp(valid_from_utc),
            "expires_at_utc": format_timestamp(expires_at_utc),
            "seconds_until_valid": round(seconds_until_valid, 6),
            "seconds_until_expiry": round(seconds_until_expiry, 6),
        }
    )
    if now < valid_from_utc - pd.Timedelta(seconds=grace):
        report["state"] = "not_yet_valid"
        report["reason"] = "execution_intent.valid_from_utc is still in the future"
        return report
    if now > expires_at_utc + pd.Timedelta(seconds=grace):
        report["state"] = "expired"
        report["reason"] = "execution_intent.expires_at_utc is in the past"
        return report
    report["actionable"] = True
    report["state"] = "fresh"
    report["reason"] = "execution intent is within its valid time window"
    return report


def validate_price_normalization_contract(value: Any, alert: dict[str, Any]) -> None:
    if not isinstance(value, dict):
        raise ValueError("price_normalization must be a mapping")
    required = {
        "schema_version",
        "tick_size",
        "entry_basis_price_raw",
        "entry_price_raw",
        "stop_loss_price_raw",
        "take_profit_price_raw",
        "entry_basis_price",
        "entry_price",
        "stop_loss_price",
        "take_profit_price",
        "entry_basis_price_adjustment_ticks",
        "entry_price_adjustment_ticks",
        "stop_loss_price_adjustment_ticks",
        "take_profit_price_adjustment_ticks",
        "normalized",
    }
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"price_normalization missing required field(s): {missing}")
    if value["schema_version"] != "price_normalization.v1":
        raise ValueError(f"unsupported price_normalization version: {value['schema_version']}")
    if finite_float(value.get("tick_size")) != finite_float(alert.get("tick_size")):
        raise ValueError("price_normalization.tick_size must match alert tick_size")
    for key in ("entry_basis_price", "entry_price", "stop_loss_price", "take_profit_price"):
        if finite_float(value.get(key)) != finite_float(alert.get(key)):
            raise ValueError(f"price_normalization.{key} must match alert {key}")
    normalized = value.get("normalized")
    if not isinstance(normalized, bool):
        raise ValueError("price_normalization.normalized must be a boolean")


def validate_execution_intent_record(record: Any, alert: dict[str, Any]) -> None:
    if not isinstance(record, dict):
        raise ValueError("execution intent record must be a mapping")
    required = {
        "event",
        "record_schema_version",
        "created_at_utc",
        "alert_contract_version",
        "alert_id",
        "setup_id",
        "pending_signal_key",
        "strategy_id",
        "strategy_config_fingerprint",
        "engine_config",
        "engine_config_fingerprint",
        "symbol",
        "contract_symbol",
        "timeframe",
        "entry_timestamp_utc",
        "execution_intent",
    }
    missing = sorted(required - set(record))
    if missing:
        raise ValueError(f"execution intent record missing required field(s): {missing}")
    if record["event"] != "execution_intent_ready":
        raise ValueError("execution intent record event must be execution_intent_ready")
    if record["record_schema_version"] != EXECUTION_INTENT_RECORD_VERSION:
        raise ValueError(f"unsupported execution intent record version: {record['record_schema_version']}")
    for key in (
        "alert_contract_version",
        "alert_id",
        "setup_id",
        "pending_signal_key",
        "strategy_id",
        "strategy_config_fingerprint",
        "engine_config",
        "engine_config_fingerprint",
        "symbol",
        "contract_symbol",
        "timeframe",
        "entry_timestamp_utc",
    ):
        if record.get(key) != alert.get(key):
            raise ValueError(f"execution intent record {key} must match alert")
    validate_execution_intent_contract(record["execution_intent"], alert)


def validate_execution_intent_ready_record(record: Any) -> None:
    if not isinstance(record, dict):
        raise ValueError("execution intent ready record must be a mapping")
    required = {
        "event",
        "record_schema_version",
        "created_at_utc",
        "alert_contract_version",
        "alert_id",
        "setup_id",
        "pending_signal_key",
        "strategy_id",
        "strategy_config_fingerprint",
        "engine_config",
        "engine_config_fingerprint",
        "symbol",
        "contract_symbol",
        "timeframe",
        "entry_timestamp_utc",
        "execution_intent",
    }
    missing = sorted(required - set(record))
    if missing:
        raise ValueError(f"execution intent ready record missing required field(s): {missing}")
    if record["event"] != "execution_intent_ready":
        raise ValueError("execution intent ready record event must be execution_intent_ready")
    if record["record_schema_version"] != EXECUTION_INTENT_RECORD_VERSION:
        raise ValueError(f"unsupported execution intent record version: {record['record_schema_version']}")
    if record["alert_contract_version"] != ALERT_CONTRACT_VERSION:
        raise ValueError(f"unsupported alert contract version: {record['alert_contract_version']}")
    created_at_utc = normalize_utc_timestamp(record["created_at_utc"])
    entry_timestamp_utc = normalize_utc_timestamp(record["entry_timestamp_utc"])
    if created_at_utc.tzinfo is None or entry_timestamp_utc.tzinfo is None:
        raise ValueError("execution intent ready record timestamps must include timezone")
    intent = record["execution_intent"]
    validate_execution_intent_payload_contract(intent)
    top_level_pairs = {
        "alert_id": ("intent_id",),
        "setup_id": ("source", "setup_id"),
        "pending_signal_key": ("source", "pending_signal_key"),
        "engine_config": ("source", "engine_config"),
        "symbol": ("symbol",),
        "contract_symbol": ("contract_symbol",),
        "timeframe": ("timeframe",),
    }
    for record_key, intent_path in top_level_pairs.items():
        if record.get(record_key) != nested_get(intent, *intent_path):
            raise ValueError(f"execution intent ready record {record_key} must match execution_intent")
    if record.get("strategy_id") != nested_get(intent, "source", "strategy_id"):
        raise ValueError("execution intent ready record strategy_id must match execution_intent.source.strategy_id")
    if record.get("strategy_config_fingerprint") != nested_get(intent, "source", "strategy_config_fingerprint"):
        raise ValueError(
            "execution intent ready record strategy_config_fingerprint must match execution_intent.source"
        )
    if record.get("engine_config_fingerprint") != nested_get(intent, "source", "engine_config_fingerprint"):
        raise ValueError("execution intent ready record engine_config_fingerprint must match execution_intent.source")
    if format_timestamp(entry_timestamp_utc) != format_timestamp(
        normalize_utc_timestamp(nested_get(intent, "timing", "entry_timestamp_utc"))
    ):
        raise ValueError("execution intent ready record entry_timestamp_utc must match execution_intent timing")


def validate_execution_intent_payload_contract(intent: Any) -> None:
    if not isinstance(intent, dict):
        raise ValueError("execution_intent must be a mapping")
    required = {
        "schema_version",
        "intent_id",
        "intent_type",
        "status",
        "asset_class",
        "symbol",
        "contract_symbol",
        "timeframe",
        "direction",
        "side",
        "quantity",
        "order",
        "bracket",
        "risk",
        "price_normalization",
        "timing",
        "source",
    }
    missing = sorted(required - set(intent))
    if missing:
        raise ValueError(f"execution_intent missing required field(s): {missing}")
    if intent["schema_version"] != EXECUTION_INTENT_VERSION:
        raise ValueError(f"unsupported execution intent version: {intent['schema_version']}")
    if intent["intent_type"] != "entry":
        raise ValueError("execution_intent.intent_type must be entry")
    if intent["status"] != "ready_for_manual_or_future_router":
        raise ValueError("execution_intent.status must be ready_for_manual_or_future_router")
    if intent["asset_class"] != "futures":
        raise ValueError("execution_intent.asset_class must be futures")
    for key in ("intent_id", "symbol", "contract_symbol", "timeframe"):
        if not str(intent.get(key) or "").strip():
            raise ValueError(f"execution_intent.{key} must be non-empty")
    direction = str(intent["direction"]).lower()
    side = str(intent["side"]).lower()
    if direction not in {"long", "short"}:
        raise ValueError("execution_intent.direction must be long or short")
    if side not in {"buy", "sell"}:
        raise ValueError("execution_intent.side must be buy or sell")
    if (direction == "long" and side != "buy") or (direction == "short" and side != "sell"):
        raise ValueError("execution_intent.side is inconsistent with direction")
    quantity = int(intent["quantity"])
    if quantity <= 0:
        raise ValueError("execution_intent.quantity must be positive")
    order = require_mapping(intent.get("order"), "execution_intent.order")
    bracket = require_mapping(intent.get("bracket"), "execution_intent.bracket")
    risk = require_mapping(intent.get("risk"), "execution_intent.risk")
    timing = require_mapping(intent.get("timing"), "execution_intent.timing")
    source = require_mapping(intent.get("source"), "execution_intent.source")
    price_normalization = require_mapping(intent.get("price_normalization"), "execution_intent.price_normalization")
    for key in ("setup_id", "pending_signal_key", "strategy_id", "strategy_name", "strategy_config", "engine_config"):
        if not str(source.get(key) or "").strip():
            raise ValueError(f"execution_intent.source.{key} must be non-empty")
    validate_config_fingerprint_payload(
        source.get("strategy_config_fingerprint"),
        path=source.get("strategy_config"),
        label="execution_intent.source.strategy_config_fingerprint",
    )
    validate_config_fingerprint_payload(
        source.get("engine_config_fingerprint"),
        path=source.get("engine_config"),
        label="execution_intent.source.engine_config_fingerprint",
    )
    if order.get("order_type") != "market":
        raise ValueError("execution_intent.order.order_type must be market")
    if order.get("entry_price_type") != "estimated_market":
        raise ValueError("execution_intent.order.entry_price_type must be estimated_market")
    entry_price = require_finite(order.get("estimated_entry_price"), "execution_intent.order.estimated_entry_price")
    basis_price = require_finite(order.get("basis_price"), "execution_intent.order.basis_price")
    require_finite(order.get("slippage_ticks"), "execution_intent.order.slippage_ticks")
    stop_loss_price = require_finite(bracket.get("stop_loss_price"), "execution_intent.bracket.stop_loss_price")
    take_profit_price = require_finite(bracket.get("take_profit_price"), "execution_intent.bracket.take_profit_price")
    stop_loss_points = require_finite(bracket.get("stop_loss_points"), "execution_intent.bracket.stop_loss_points")
    take_profit_points = require_finite(bracket.get("take_profit_points"), "execution_intent.bracket.take_profit_points")
    tick_size = require_finite(risk.get("tick_size"), "execution_intent.risk.tick_size", positive=True)
    tick_value = require_finite(risk.get("tick_value"), "execution_intent.risk.tick_value", positive=True)
    risk_dollars = require_finite(risk.get("risk_dollars"), "execution_intent.risk.risk_dollars", positive=True)
    reward_dollars = require_finite(risk.get("reward_dollars"), "execution_intent.risk.reward_dollars", positive=True)
    for key, value in (
        ("estimated_entry_price", entry_price),
        ("basis_price", basis_price),
        ("stop_loss_price", stop_loss_price),
        ("take_profit_price", take_profit_price),
    ):
        if not is_on_tick_grid(value, tick_size):
            raise ValueError(f"execution_intent price {key!r} must be on the configured tick grid")
    if direction == "long" and not (stop_loss_price < entry_price < take_profit_price):
        raise ValueError("long execution_intent stop/entry/target ordering is invalid")
    if direction == "short" and not (take_profit_price < entry_price < stop_loss_price):
        raise ValueError("short execution_intent stop/entry/target ordering is invalid")
    if not nearly_equal(stop_loss_points, abs(entry_price - stop_loss_price)):
        raise ValueError("execution_intent.bracket.stop_loss_points must match executable entry/stop prices")
    if not nearly_equal(take_profit_points, abs(take_profit_price - entry_price)):
        raise ValueError("execution_intent.bracket.take_profit_points must match executable entry/target prices")
    if not nearly_equal(risk_dollars, stop_loss_points / tick_size * tick_value * quantity):
        raise ValueError("execution_intent.risk.risk_dollars must match executable stop distance")
    if not nearly_equal(reward_dollars, take_profit_points / tick_size * tick_value * quantity):
        raise ValueError("execution_intent.risk.reward_dollars must match executable target distance")
    validate_price_normalization_payload_contract(
        price_normalization,
        tick_size=tick_size,
        entry_basis_price=basis_price,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
    )
    validate_execution_intent_timing_payload(timing)


def validate_price_normalization_payload_contract(
    value: dict[str, Any],
    *,
    tick_size: float,
    entry_basis_price: float,
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float,
) -> None:
    required = {
        "schema_version",
        "tick_size",
        "entry_basis_price",
        "entry_price",
        "stop_loss_price",
        "take_profit_price",
        "normalized",
    }
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"execution_intent.price_normalization missing required field(s): {missing}")
    if value["schema_version"] != "price_normalization.v1":
        raise ValueError(f"unsupported execution_intent price_normalization version: {value['schema_version']}")
    if not nearly_equal(value.get("tick_size"), tick_size):
        raise ValueError("execution_intent.price_normalization.tick_size must match risk.tick_size")
    for key, expected in (
        ("entry_basis_price", entry_basis_price),
        ("entry_price", entry_price),
        ("stop_loss_price", stop_loss_price),
        ("take_profit_price", take_profit_price),
    ):
        if not nearly_equal(value.get(key), expected):
            raise ValueError(f"execution_intent.price_normalization.{key} must match execution intent price")
    if not isinstance(value.get("normalized"), bool):
        raise ValueError("execution_intent.price_normalization.normalized must be a boolean")


def validate_execution_intent_timing_payload(timing: dict[str, Any]) -> None:
    required = {
        "signal_timestamp",
        "entry_timestamp",
        "entry_timestamp_utc",
        "valid_from_utc",
        "expires_at_utc",
        "intent_ttl_seconds",
        "max_entry_lag_seconds",
    }
    missing = sorted(required - set(timing))
    if missing:
        raise ValueError(f"execution_intent.timing missing required field(s): {missing}")
    try:
        signal_timestamp = pd.Timestamp(timing["signal_timestamp"])
        entry_timestamp = pd.Timestamp(timing["entry_timestamp"])
        entry_utc = normalize_utc_timestamp(timing["entry_timestamp_utc"])
        valid_from_utc = normalize_utc_timestamp(timing["valid_from_utc"])
        expires_at_utc = normalize_utc_timestamp(timing["expires_at_utc"])
    except Exception as exc:
        raise ValueError("execution_intent timing timestamps must parse as timestamps") from exc
    if signal_timestamp.tzinfo is None or entry_timestamp.tzinfo is None:
        raise ValueError("execution_intent timing signal and entry timestamps must include timezone")
    if valid_from_utc != entry_utc:
        raise ValueError("execution_intent.timing.valid_from_utc must match entry_timestamp_utc")
    ttl_seconds = require_finite(
        timing.get("intent_ttl_seconds"),
        "execution_intent.timing.intent_ttl_seconds",
        positive=True,
    )
    require_finite(
        timing.get("max_entry_lag_seconds"),
        "execution_intent.timing.max_entry_lag_seconds",
        positive=True,
    )
    if expires_at_utc <= valid_from_utc:
        raise ValueError("execution_intent.timing.expires_at_utc must be after valid_from_utc")
    expected_expires = valid_from_utc + pd.Timedelta(seconds=float(ttl_seconds))
    if abs((expires_at_utc - expected_expires).total_seconds()) > 1e-6:
        raise ValueError("execution_intent.timing.expires_at_utc must match intent_ttl_seconds")


def execution_intent_record_actionability_report(
    record: Any,
    *,
    now_utc: Any | None = None,
    grace_seconds: float = 0.0,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "actionable": False,
        "state": "invalid_contract",
        "alert_id": record.get("alert_id") if isinstance(record, dict) else None,
        "record_schema_version": record.get("record_schema_version") if isinstance(record, dict) else None,
        "alert_contract_version": record.get("alert_contract_version") if isinstance(record, dict) else None,
        "freshness": None,
        "error_type": None,
        "error": None,
    }
    try:
        validate_execution_intent_ready_record(record)
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)
        return report
    freshness = execution_intent_freshness_report(
        record["execution_intent"],
        now_utc=now_utc,
        grace_seconds=grace_seconds,
    )
    report["freshness"] = freshness
    if not bool(freshness.get("actionable", False)):
        report["state"] = str(freshness.get("state") or "non_actionable")
        report["error"] = str(freshness.get("reason") or "execution intent is not actionable")
        return report
    report["actionable"] = True
    report["state"] = "ready"
    return report


def load_actionable_execution_intents(
    path: Path | str,
    *,
    now_utc: Any | None = None,
    grace_seconds: float = 0.0,
    include_rejected: bool = True,
    fail_on_error: bool = False,
    dedupe_alert_ids: bool = True,
    dedupe_setup_ids: bool = True,
) -> dict[str, Any]:
    outbox_path = Path(path)
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_actionable_alert_ids: dict[str, int] = {}
    seen_actionable_setup_ids: dict[str, int] = {}
    duplicate_alert_id_count = 0
    duplicate_setup_id_count = 0
    records_read = 0
    malformed = 0
    if not outbox_path.exists():
        return {
            "event": "execution_intent_outbox_read",
            "path": str(outbox_path),
            "records_read": 0,
            "actionable_count": 0,
            "rejected_count": 0,
            "malformed_count": 0,
            "duplicate_alert_id_count": 0,
            "duplicate_setup_id_count": 0,
            "records": records,
            "rejected": rejected,
        }
    with outbox_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            records_read += 1
            try:
                payload = json.loads(text)
            except Exception as exc:
                malformed += 1
                rejection = {
                    "line_number": line_number,
                    "actionable": False,
                    "state": "malformed_json",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                if include_rejected:
                    rejected.append(rejection)
                if fail_on_error:
                    raise RuntimeError(f"Malformed execution-intent JSONL at {outbox_path}:{line_number}: {exc}") from exc
                continue
            report = execution_intent_record_actionability_report(
                payload,
                now_utc=now_utc,
                grace_seconds=grace_seconds,
            )
            report["line_number"] = line_number
            if bool(report.get("actionable", False)):
                alert_id = str(payload.get("alert_id") or "")
                setup_id = str(payload.get("setup_id") or "")
                if dedupe_alert_ids and alert_id and alert_id in seen_actionable_alert_ids:
                    duplicate_alert_id_count += 1
                    duplicate = {
                        "line_number": line_number,
                        "first_line_number": seen_actionable_alert_ids[alert_id],
                        "actionable": False,
                        "state": "duplicate_alert_id",
                        "alert_id": alert_id,
                        "record_schema_version": payload.get("record_schema_version"),
                        "alert_contract_version": payload.get("alert_contract_version"),
                        "error": "Duplicate actionable execution-intent alert_id in outbox.",
                    }
                    if include_rejected:
                        rejected.append(duplicate)
                    if fail_on_error:
                        raise RuntimeError(
                            f"Duplicate actionable execution-intent alert_id at "
                            f"{outbox_path}:{line_number}: {alert_id}"
                        )
                    continue
                if dedupe_setup_ids and setup_id and setup_id in seen_actionable_setup_ids:
                    duplicate_setup_id_count += 1
                    duplicate = {
                        "line_number": line_number,
                        "first_line_number": seen_actionable_setup_ids[setup_id],
                        "actionable": False,
                        "state": "duplicate_setup_id",
                        "setup_id": setup_id,
                        "record_schema_version": payload.get("record_schema_version"),
                        "alert_contract_version": payload.get("alert_contract_version"),
                        "error": "Duplicate actionable execution-intent setup_id in outbox.",
                    }
                    if include_rejected:
                        rejected.append(duplicate)
                    if fail_on_error:
                        raise RuntimeError(
                            f"Duplicate actionable execution-intent setup_id at "
                            f"{outbox_path}:{line_number}: {setup_id}"
                        )
                    continue
                if alert_id:
                    seen_actionable_alert_ids[alert_id] = line_number
                if setup_id:
                    seen_actionable_setup_ids[setup_id] = line_number
                records.append(payload)
                continue
            if include_rejected:
                rejected.append(report)
            if fail_on_error:
                raise RuntimeError(
                    f"Non-actionable execution-intent record at {outbox_path}:{line_number}: "
                    f"{report.get('state')} {report.get('error') or ''}".strip()
                )
    return {
        "event": "execution_intent_outbox_read",
        "path": str(outbox_path),
        "records_read": records_read,
        "actionable_count": len(records),
        "rejected_count": len(rejected) if include_rejected else 0,
        "malformed_count": malformed,
        "duplicate_alert_id_count": duplicate_alert_id_count,
        "duplicate_setup_id_count": duplicate_setup_id_count,
        "records": records,
        "rejected": rejected,
    }


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def require_finite(value: Any, label: str, *, positive: bool = False) -> float:
    parsed = finite_float(value)
    if parsed is None:
        raise ValueError(f"{label} must be finite")
    if positive and parsed <= 0:
        raise ValueError(f"{label} must be positive")
    return parsed


def format_setup_readout(notice: dict[str, Any]) -> str:
    signal = notice.get("signal", {}) if isinstance(notice.get("signal"), dict) else {}
    metadata = signal.get("metadata", {}) if isinstance(signal.get("metadata"), dict) else {}
    entry_window = notice.get("entry_window", {}) if isinstance(notice.get("entry_window"), dict) else {}
    entry_trigger = str(entry_window.get("entry_trigger") or "").replace("_", " ").strip()
    entry_window_seconds = finite_float(entry_window.get("max_entry_lag_seconds", notice.get("max_entry_lag_seconds")))
    lines = [
        "",
        "=" * 72,
        "TRADE SETUP",
        "-" * 72,
        "Status   : PREP ONLY - WAIT FOR ENTRY TRIGGER",
        f"Strategy : {notice.get('strategy_id', '')}",
        f"Symbol   : {notice.get('contract_symbol') or notice.get('symbol', '')} {notice.get('timeframe', '')}",
        f"Direction: {str(notice.get('direction', '')).upper()} ({notice.get('side', '')})",
        f"Signal   : {notice.get('signal_timestamp', '')}",
        f"Due UTC  : {notice.get('due_timestamp_utc', '')}",
        f"Expires  : {notice.get('expires_at_utc', '')}",
    ]
    if entry_trigger:
        lines.append(f"Entry    : {entry_trigger}")
    if entry_window_seconds is not None:
        lines.append(f"Window   : {format_number(entry_window_seconds)}s after due time")
    stop_preview = finite_float(notice.get("stop_loss_price_preview"))
    if stop_preview is not None:
        lines.append(f"Stop ref : {format_number(stop_preview)}")
    preview = notice.get("trade_plan_preview")
    if isinstance(preview, dict):
        if preview.get("status") == "estimated":
            lines.append("Plan     : ESTIMATE ONLY - final entry waits for trigger")
            entry_price = finite_float(preview.get("estimated_entry_price"))
            stop_price = finite_float(preview.get("stop_loss_price"))
            target_price = finite_float(preview.get("take_profit_price"))
            quantity = preview.get("quantity")
            risk_dollars = finite_float(preview.get("risk_dollars"))
            reward_dollars = finite_float(preview.get("reward_dollars"))
            if entry_price is not None:
                lines.append(f"Est entry: {format_number(entry_price)}")
            if stop_price is not None:
                lines.append(f"Est stop : {format_number(stop_price)}")
            if target_price is not None:
                lines.append(f"Est tgt  : {format_number(target_price)}")
            if isinstance(quantity, int) and quantity > 0:
                lines.append(f"Est qty  : {quantity} contract(s)")
            if risk_dollars is not None or reward_dollars is not None:
                lines.append(
                    "Est R/R  : "
                    f"${format_number(risk_dollars) if risk_dollars is not None else '?'} / "
                    f"${format_number(reward_dollars) if reward_dollars is not None else '?'}"
                )
        elif preview.get("status") == "unavailable" and preview.get("reason"):
            lines.append(f"Plan     : unavailable - {preview.get('reason')}")
    delta = finite_float(metadata.get("delta"))
    current_delta = finite_float(metadata.get("current_bar_delta"))
    if delta is not None:
        lines.append(f"Delta    : {format_number(delta)}")
    if current_delta is not None and current_delta != delta:
        lines.append(f"Bar delta: {format_number(current_delta)}")
    lines.extend(
        [
            "=" * 72,
            "",
        ]
    )
    return "\n".join(lines)


def format_entry_alert_readout(alert: dict[str, Any]) -> str:
    signal = alert.get("signal", {}) if isinstance(alert.get("signal"), dict) else {}
    metadata = signal.get("metadata", {}) if isinstance(signal.get("metadata"), dict) else {}
    intent = alert.get("execution_intent", {}) if isinstance(alert.get("execution_intent"), dict) else {}
    order = intent.get("order", {}) if isinstance(intent.get("order"), dict) else {}
    timing = intent.get("timing", {}) if isinstance(intent.get("timing"), dict) else {}
    order_type = str(order.get("order_type") or alert.get("order_type") or "").upper()
    entry_price_type = str(order.get("entry_price_type") or "").replace("_", " ").strip()
    expiry = timing.get("expires_at_utc")
    ttl_seconds = finite_float(timing.get("intent_ttl_seconds"))
    risk_dollars = finite_float(alert.get("risk_dollars"))
    reward_dollars = finite_float(alert.get("reward_dollars"))
    lines = [
        "",
        "=" * 72,
        "ENTRY SIGNAL - TAKE TRADE NOW",
        "-" * 72,
        f"Strategy : {alert.get('strategy_id', '')}",
        f"Symbol   : {alert.get('contract_symbol') or alert.get('symbol', '')} {alert.get('timeframe', '')}",
        f"Action   : {str(alert.get('direction', '')).upper()} / {str(alert.get('side', '')).upper()}",
        f"Quantity : {alert.get('quantity', '')} contract(s)",
        f"Order    : {order_type}{f' ({entry_price_type})' if entry_price_type else ''}",
        f"Entry    : {format_number(alert.get('entry_price'))}  basis {format_number(alert.get('entry_basis_price'))}",
        f"Stop     : {format_number(alert.get('stop_loss_price'))}  ({format_number(alert.get('stop_loss_points'))} pts)",
        f"Target   : {format_number(alert.get('take_profit_price'))}  ({format_number(alert.get('take_profit_points'))} pts)",
        f"Risk     : ${format_number(alert.get('risk_dollars'))}",
        f"Reward   : ${format_number(alert.get('reward_dollars'))}",
        f"Signal   : {alert.get('signal_timestamp', '')}",
        f"Entry TS : {alert.get('entry_timestamp_utc', alert.get('entry_timestamp', ''))}",
    ]
    if expiry:
        expires_text = str(expiry)
        if ttl_seconds is not None:
            expires_text = f"{expires_text} ({format_number(ttl_seconds)}s TTL)"
        lines.append(f"Expires  : {expires_text}")
    if risk_dollars is not None and risk_dollars > 0 and reward_dollars is not None:
        lines.append(f"R/R      : {format_number(reward_dollars / risk_dollars)}R")
    delta = finite_float(metadata.get("delta"))
    bar_volume = finite_float(metadata.get("latest_completed_bar_volume"))
    if delta is not None:
        lines.append(f"Delta    : {format_number(delta)}")
    if bar_volume is not None:
        lines.append(f"Bar vol  : {format_number(bar_volume)}")
    lines.extend(
        [
            f"Setup ID : {alert.get('setup_id', '')}",
            f"Alert ID : {alert.get('alert_id', '')}",
            "=" * 72,
            "",
        ]
    )
    return "\n".join(lines)


def format_rejection_readout(payload: dict[str, Any]) -> str:
    signal = payload.get("signal", {}) if isinstance(payload.get("signal"), dict) else {}
    metadata = signal.get("metadata", {}) if isinstance(signal.get("metadata"), dict) else {}
    lines = [
        "",
        "=" * 72,
        "SIGNAL REJECTED",
        "-" * 72,
        f"Strategy : {payload.get('strategy_id', '')}",
        f"Signal   : {payload.get('timestamp', '')}",
        f"Session  : {payload.get('session_date', '')}",
        f"Reason   : {payload.get('reason', '')}",
    ]
    direction = signal.get("direction")
    if direction:
        lines.append(f"Direction: {str(direction).upper()}")
    due_timestamp = payload.get("due_timestamp_utc")
    if due_timestamp:
        lines.append(f"Due UTC  : {due_timestamp}")
    checked_timestamp = payload.get("checked_timestamp_utc")
    if checked_timestamp:
        lines.append(f"Checked  : {checked_timestamp}")
    delta = finite_float(metadata.get("delta"))
    current_delta = finite_float(metadata.get("current_bar_delta"))
    if delta is not None:
        lines.append(f"Delta    : {format_number(delta)}")
    if current_delta is not None and current_delta != delta:
        lines.append(f"Bar delta: {format_number(current_delta)}")
    lines.extend(
        [
            "=" * 72,
            "",
        ]
    )
    return "\n".join(lines)


def format_number(value: Any) -> str:
    parsed = finite_float(value)
    if parsed is None:
        return "n/a"
    if abs(parsed) >= 1000:
        return f"{parsed:,.2f}".rstrip("0").rstrip(".")
    return f"{parsed:.4f}".rstrip("0").rstrip(".")


def alert_hash(*parts: str) -> str:
    data = "|".join(parts).encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:20]


def format_timestamp(value: Any) -> str:
    timestamp = pd.Timestamp(value)
    return timestamp.isoformat()


def normalize_utc_timestamp(value: Any) -> Any:
    timestamp = pd.Timestamp(value)
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")


def utc_now_iso() -> str:
    return pd.Timestamp.utcnow().isoformat()


def load_existing_jsonl_alert_ids(
    path: Path | None,
    *,
    sink: AlertSinkHealth,
    sink_label: str,
    fail_on_error: bool,
    id_fields: tuple[str, ...] = ("alert_id",),
    expected_version_field: str | None = None,
    expected_version_value: str | None = None,
    expected_record_schema_version: str | None = None,
) -> set[str]:
    if expected_record_schema_version is not None:
        expected_version_field = "record_schema_version"
        expected_version_value = expected_record_schema_version
    if path is None or not path.exists():
        return set()
    ids: set[str] = set()
    malformed_lines: list[int] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except Exception:
                    malformed_lines.append(line_number)
                    continue
                if not isinstance(payload, dict):
                    malformed_lines.append(line_number)
                    continue
                if expected_version_field is not None and payload.get(expected_version_field) != expected_version_value:
                    continue
                for id_field in id_fields:
                    alert_id = payload.get(id_field)
                    if alert_id is not None and str(alert_id):
                        ids.add(str(alert_id))
    except Exception as exc:
        sink.last_error_utc = utc_now_iso()
        sink.last_error_type = type(exc).__name__
        sink.last_error = str(exc)
        payload = {
            "event": f"{sink_label}_duplicate_index_failed",
            "path": str(path),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "impact": "Duplicate JSONL id suppression could not index existing records.",
        }
        print_json(payload, prefix="SYSTEM_ALERT")
        if fail_on_error:
            raise RuntimeError(f"Failed to index existing JSONL alert ids for {path}: {exc}") from exc
        return set()
    if malformed_lines:
        sink.last_error_utc = utc_now_iso()
        sink.last_error_type = "MalformedJSONL"
        sink.last_error = f"{len(malformed_lines)} malformed line(s) while indexing duplicate JSONL ids"
        payload = {
            "event": f"{sink_label}_duplicate_index_malformed_lines",
            "path": str(path),
            "malformed_line_count": len(malformed_lines),
            "first_malformed_lines": malformed_lines[:10],
            "loaded_alert_ids": len(ids),
            "impact": "Duplicate alert-id suppression may miss records from malformed JSONL lines.",
        }
        print_json(payload, prefix="SYSTEM_ALERT")
        if fail_on_error:
            raise RuntimeError(f"Malformed JSONL while indexing existing alert ids for {path}.")
    return ids


def read_process_lock_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8").strip() or "{}")
    except Exception as exc:
        return {"read_error_type": type(exc).__name__, "read_error": str(exc)}
    return payload if isinstance(payload, dict) else {"read_error_type": "InvalidLock", "read_error": "lock file is not a JSON object"}


def is_process_lock_stale(path: Path, payload: dict[str, Any], *, stale_after_seconds: float) -> bool:
    pid = payload.get("pid")
    if isinstance(pid, int) and pid > 0:
        if is_process_alive(pid):
            return False
        return True
    try:
        age_seconds = max(0.0, time.time() - path.stat().st_mtime)
    except OSError:
        return True
    return age_seconds > stale_after_seconds


def is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


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


def without_none(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in mapping.items() if value is not None}


def required_spec_value(spec: dict[str, Any], key: str) -> Any:
    if key not in spec or is_missing_or_blank(spec[key]):
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
        print_json(
            {
                "event": "fatal",
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
            prefix="FATAL",
        )
        raise SystemExit(1)
