#!/usr/bin/env python3
"""
Bridge IBKR market data, propstack strategy configs, Apex guardrails, and Tradovate.

The bridge:
  1. Loads a campaign variant YAML from the main propstack project.
  2. Pulls recent 1-minute historical bars for the selected futures symbol from IBKR.
  3. Subscribes to live IBKR 5-second bars and aggregates completed 1-minute bars.
  4. Rebuilds the same session/timeframe/features used by the backtest engine.
  5. Runs the modular strategy on newly completed strategy bars.
  6. Computes entry estimate, stop, target, and guardrail-constrained size.
  7. Optionally sends the guarded market OSO bracket order to Tradovate.

It is dry-run by default. Use --execute to allow the Tradovate POST.
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import json
import math
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

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

try:
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.wrapper import EWrapper
except ImportError as exc:  # pragma: no cover - runtime dependency guard.
    EClient = object  # type: ignore[assignment,misc]
    EWrapper = object  # type: ignore[assignment,misc]
    Contract = None
    IBAPI_IMPORT_ERROR: ImportError | None = exc
else:
    IBAPI_IMPORT_ERROR = None

import apex_eod_guardrails as guardrails
import tradovate_client as tradovate
from ibkr_decimal_volume_patch import patch_ibapi_realtime_bar_decimal_volume
from ibkr_es_historical_1m_fetch import next_quarterly_expiry


HISTORICAL_REQ_ID = 12001
REALTIME_BARS_REQ_ID = 12002
INFO_CODES = {2103, 2104, 2106, 2107, 2108, 2158}
DEFAULT_CONFIG = "strategy_execution_bridge.example.json"
@dataclass(frozen=True)
class OneMinuteBar:
    timestamp_epoch: int
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: Decimal
    count: int | None = None
    source: str = ""


@dataclass
class LiveMinuteBuilder:
    current: OneMinuteBar | None = None

    def update(
        self,
        *,
        timestamp_epoch: int,
        symbol: str,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: Any,
        count: int,
    ) -> OneMinuteBar | None:
        minute_start = int(timestamp_epoch) - (int(timestamp_epoch) % 60)
        completed = None
        if self.current is None:
            self.current = OneMinuteBar(
                minute_start,
                symbol,
                open_price,
                high,
                low,
                close,
                to_decimal(volume),
                int(count),
                "live",
            )
            return None

        if self.current.timestamp_epoch == minute_start:
            self.current = OneMinuteBar(
                self.current.timestamp_epoch,
                symbol,
                self.current.open,
                max(self.current.high, high),
                min(self.current.low, low),
                close,
                self.current.volume + to_decimal(volume),
                (self.current.count or 0) + int(count),
                "live",
            )
            return None

        completed = self.current
        self.current = OneMinuteBar(
            minute_start,
            symbol,
            open_price,
            high,
            low,
            close,
            to_decimal(volume),
            int(count),
            "live",
        )
        return completed


class BarStore:
    def __init__(self, max_bars: int) -> None:
        self.max_bars = max_bars
        self._bars: dict[int, OneMinuteBar] = {}

    def add(self, bar: OneMinuteBar) -> bool:
        existing = self._bars.get(bar.timestamp_epoch)
        self._bars[bar.timestamp_epoch] = bar
        if len(self._bars) > self.max_bars:
            for key in sorted(self._bars)[: len(self._bars) - self.max_bars]:
                del self._bars[key]
        return existing != bar

    def add_many(self, bars: list[OneMinuteBar]) -> int:
        changed = 0
        for bar in bars:
            if self.add(bar):
                changed += 1
        return changed

    def bars(self) -> list[OneMinuteBar]:
        return [self._bars[key] for key in sorted(self._bars)]


class IbkrBridgeApp(EWrapper, EClient):
    def __init__(
        self,
        *,
        ibkr_config: dict[str, Any],
        contract: Any,
        display_symbol: str,
        on_seed: Callable[[list[OneMinuteBar]], None],
        on_completed_minute: Callable[[OneMinuteBar], None],
    ) -> None:
        EClient.__init__(self, self)
        self.ibkr_config = ibkr_config
        self.contract = contract
        self.display_symbol = display_symbol
        self.on_seed = on_seed
        self.on_completed_minute = on_completed_minute
        self.started = threading.Event()
        self.seeded = threading.Event()
        self.done = threading.Event()
        self.failed = False
        self.errors: list[str] = []
        self._started_requests = False
        self._historical_bars: list[OneMinuteBar] = []
        self._live_builder = LiveMinuteBuilder()

    def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IBAPI callback name.
        if self._started_requests:
            return
        self._started_requests = True
        self.started.set()
        print(f"Connected to IBKR nextValidId={orderId}; seeding {self.display_symbol}", file=sys.stderr)
        self.reqMarketDataType(int(self.ibkr_config.get("market_data_type", 1)))
        self.reqHistoricalData(
            HISTORICAL_REQ_ID,
            self.contract,
            "",
            str(self.ibkr_config.get("historical_duration", "3 D")),
            "1 min",
            str(self.ibkr_config.get("what_to_show", "TRADES")),
            int(self.ibkr_config.get("use_rth", 0)),
            2,
            False,
            [],
        )

    def historicalData(self, reqId: int, bar: Any) -> None:  # noqa: N802 - IBAPI callback name.
        if reqId != HISTORICAL_REQ_ID:
            return
        parsed = ib_bar_to_minute(bar, self.display_symbol, "historical")
        if parsed is not None:
            self._historical_bars.append(parsed)

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:  # noqa: N802 - IBAPI callback name.
        if reqId != HISTORICAL_REQ_ID:
            return
        print(
            f"Historical seed complete start={start} end={end} bars={len(self._historical_bars)}",
            file=sys.stderr,
        )
        self.on_seed(self._historical_bars)
        self.seeded.set()
        self.reqRealTimeBars(
            REALTIME_BARS_REQ_ID,
            self.contract,
            5,
            str(self.ibkr_config.get("what_to_show", "TRADES")),
            int(self.ibkr_config.get("use_rth", 0)),
            [],
        )
        print("Subscribed to IBKR 5-second real-time bars.", file=sys.stderr)

    def realtimeBar(  # noqa: N802 - IBAPI callback name.
        self,
        reqId: int,
        time_: int,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: Any,
        wap: Any,
        count: int,
    ) -> None:
        if reqId != REALTIME_BARS_REQ_ID:
            return
        completed = self._live_builder.update(
            timestamp_epoch=int(time_),
            symbol=self.display_symbol,
            open_price=float(open_),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=volume,
            count=int(count),
        )
        if completed is not None:
            self.on_completed_minute(completed)

    def error(  # noqa: A003,N802 - IBAPI callback name.
        self,
        reqId: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        severity = "info" if errorCode in INFO_CODES else "error"
        prefix = f"IBKR reqId={reqId}" if reqId >= 0 else "IBKR"
        message = f"{prefix} {severity} {errorCode}: {errorString}"
        print(message, file=sys.stderr)
        if severity == "error":
            self.errors.append(message)
        if reqId == HISTORICAL_REQ_ID and severity == "error":
            self.failed = True
            self.done.set()

    def connectionClosed(self) -> None:  # noqa: N802 - IBAPI callback name.
        self.done.set()

    def shutdown(self) -> None:
        if not self.isConnected():
            self.done.set()
            return
        try:
            self.cancelHistoricalData(HISTORICAL_REQ_ID)
        except Exception:
            pass
        try:
            self.cancelRealTimeBars(REALTIME_BARS_REQ_ID)
        except Exception:
            pass
        self.disconnect()
        self.done.set()


class StrategyExecutionRuntime:
    def __init__(self, config: dict[str, Any], config_path: Path) -> None:
        if pd is None:
            raise RuntimeError("Missing dependency: python3 -m pip install pandas")
        self.config = config
        self.config_path = config_path
        self.project_root = Path(config.get("project_root", config_path.parent.parent)).expanduser().resolve()
        self.strategy_config_path = resolve_strategy_path(self.project_root, config_path.parent, config["strategy_config"])
        self.guardrails_path = resolve_path(config_path.parent, config.get("guardrails_config", "apex_50k_eod_guardrails.example.json"))
        self.execution_config = config.get("execution", {})
        self.tradovate_config = config.get("tradovate", {})
        self.ibkr_config = config.get("ibkr", {})
        self.guardrails_config = guardrails.load_config(str(self.guardrails_path))
        self.variant_config = load_yaml(self.strategy_config_path)
        self.preflight_warnings = validate_strategy_variant(
            self.variant_config,
            self.strategy_config_path,
            self.project_root,
        )
        self.data_config = dict(self.variant_config.get("data", {}))
        self.timeframe = self.variant_config.get("timeframe") or self.data_config.get("timeframe")
        self.timeframe_minutes = parse_timeframe_minutes(self.timeframe)
        self._apply_strategy_defaults_to_execution_config()
        self.preflight_warnings.extend(self._history_window_warnings())
        self.strategy = self._build_strategy()
        self.bar_store = BarStore(int(self.execution_config.get("max_source_bars", 10000)))
        self.trades_by_session: dict[Any, int] = {}
        self.last_processed_strategy_timestamp: Any = None
        self.last_live_strategy_timestamp: Any = None
        self.sent_signal_keys: set[tuple[Any, str, str]] = set()

    def _apply_strategy_defaults_to_execution_config(self) -> None:
        symbol = str(self.variant_config.get("symbol") or self.data_config.get("symbol") or "").strip()
        if not symbol:
            return
        if not self.ibkr_config.get("symbol"):
            self.ibkr_config["symbol"] = symbol
        if not self.execution_config.get("guardrail_symbol"):
            self.execution_config["guardrail_symbol"] = symbol
        if not self.tradovate_config.get("symbol") and self.ibkr_config.get("expiry"):
            self.tradovate_config["symbol"] = tradovate.tradovate_contract_symbol(symbol, self.ibkr_config.get("expiry"))
        if not self.ibkr_config.get("multiplier"):
            self.ibkr_config["multiplier"] = default_futures_multiplier(str(self.ibkr_config.get("symbol", symbol)))

    def _history_window_warnings(self) -> list[str]:
        warnings: list[str] = []
        warmup_days = int(self.data_config.get("warmup_days") or 0)
        history_days = historical_duration_days(str(self.ibkr_config.get("historical_duration", "")))
        if warmup_days and history_days is not None and history_days < warmup_days + 1:
            warnings.append(
                f"IBKR historical_duration={self.ibkr_config.get('historical_duration')} is shorter than "
                f"data.warmup_days+1 ({warmup_days + 1} D); strategy features may be under-warmed."
            )
        return warnings

    def preflight_report(self) -> dict[str, Any]:
        strategy = self.variant_config["strategy"]
        return {
            "strategy_config": str(self.strategy_config_path),
            "strategy_name": self.variant_config.get("strategy_name"),
            "symbol": self.variant_config.get("symbol") or self.data_config.get("symbol"),
            "timeframe": self.timeframe,
            "timeframe_minutes": self.timeframe_minutes,
            "modules": {
                "entry": strategy["entry"]["module"],
                "sl": strategy["sl"]["module"],
                "tp": strategy["tp"]["module"],
            },
            "ibkr": {
                "host": self.ibkr_config.get("host"),
                "port": self.ibkr_config.get("port"),
                "client_id": self.ibkr_config.get("client_id"),
                "symbol": self.ibkr_config.get("symbol"),
                "expiry": self.ibkr_config.get("expiry"),
                "local_symbol": self.ibkr_config.get("local_symbol"),
                "historical_duration": self.ibkr_config.get("historical_duration"),
                "market_data_type": self.ibkr_config.get("market_data_type"),
            },
            "guardrails_config": str(self.guardrails_path),
            "tradovate": {
                "environment": self.tradovate_config.get("environment", "demo"),
                "account_id": self.tradovate_config.get("account_id"),
                "account_spec": self.tradovate_config.get("account_spec"),
                "symbol": self.tradovate_symbol(),
                "auth_mode": self.tradovate_config.get("auth_mode", "auto"),
            },
            "dry_run": not bool(self.execution_config.get("execute", False)),
            "warnings": self.preflight_warnings,
        }

    def _build_strategy(self):
        add_project_src_to_path(self.project_root)
        from propstack.strategy import ModularStrategy

        strategy_config = copy.deepcopy(self.variant_config.get("strategy", {}))
        if "strategy_name" not in strategy_config and self.variant_config.get("strategy_name"):
            strategy_config["strategy_name"] = self.variant_config["strategy_name"]
        entry = strategy_config.setdefault("entry", {})
        params = entry.setdefault("params", {})
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
                f"strategy.entry.params.{key} ({configured:g}) must match variant timeframe "
                f"({self.timeframe_minutes:g} minutes)."
            )

    def seed(self, bars: list[OneMinuteBar]) -> None:
        changed = self.bar_store.add_many(bars)
        print(f"Seeded {len(bars)} historical bars ({changed} new/updated).", file=sys.stderr)
        features = self.completed_features()
        for _, row in features.iterrows():
            self._process_strategy_bar(row, live=False)
        print(
            f"Hydrated strategy state through {self.last_processed_strategy_timestamp}.",
            file=sys.stderr,
        )

    def on_completed_minute(self, bar: OneMinuteBar) -> None:
        self.bar_store.add(bar)
        print(
            f"Live minute complete {epoch_to_utc_iso(bar.timestamp_epoch)} "
            f"O={bar.open} H={bar.high} L={bar.low} C={bar.close} V={bar.volume}",
            file=sys.stderr,
        )
        features = self.completed_features()
        new_rows = features
        if self.last_processed_strategy_timestamp is not None:
            new_rows = features[features["timestamp"] > self.last_processed_strategy_timestamp]
        for _, row in new_rows.iterrows():
            self._process_strategy_bar(row, live=True)

    def completed_features(self):
        features = self.current_features()
        if features.empty:
            return features
        bars = self.bar_store.bars()
        if not bars:
            return features.iloc[0:0].copy()
        latest_source_end = pd.Timestamp(
            max(bar.timestamp_epoch for bar in bars), unit="s", tz="UTC"
        ).tz_convert(str(self.data_config.get("timezone", "America/New_York"))) + pd.Timedelta(minutes=1)
        completed = features[
            features["timestamp"] + pd.Timedelta(minutes=self.timeframe_minutes) <= latest_source_end
        ]
        return completed.reset_index(drop=True)

    def current_features(self):
        add_project_src_to_path(self.project_root)
        from propstack.data.features import build_features
        from propstack.data.sessions import assign_sessions, filter_trading_sessions
        from propstack.data.timeframe import aggregate_timeframe

        df = bars_to_dataframe(
            self.bar_store.bars(),
            market_timezone=str(self.data_config.get("timezone", "America/New_York")),
            symbol=str(self.variant_config.get("symbol", "ES")),
        )
        if df.empty:
            return df
        sessionized = assign_sessions(df, self.data_config)
        sessionized = filter_trading_sessions(sessionized)
        strategy_bars = aggregate_timeframe(sessionized, self.data_config, self.timeframe)
        features = build_features(strategy_bars, self.data_config)
        return features.sort_values("timestamp").reset_index(drop=True)

    def _process_strategy_bar(self, row: Any, *, live: bool) -> None:
        timestamp = row["timestamp"]
        session_date = row["session_date"]
        trades_today = self.trades_by_session.get(session_date, 0)
        signal_obj = self.strategy.on_bar_close(row, trades_today=trades_today)
        self.last_processed_strategy_timestamp = timestamp
        if not live:
            if signal_obj is not None:
                self.trades_by_session[session_date] = trades_today + 1
            return
        self.last_live_strategy_timestamp = timestamp
        if signal_obj is None:
            print(f"No signal on completed strategy bar {timestamp}.", file=sys.stderr)
            return
        decision = self.plan_trade(row, signal_obj)
        print_report(decision)
        if decision["action"] != "send_order":
            return
        self.trades_by_session[session_date] = trades_today + 1
        if not bool(self.execution_config.get("send_to_tradovate", True)):
            print("send_to_tradovate=false; guardrail-approved order was not posted.", file=sys.stderr)
            return
        if not bool(self.execution_config.get("execute", False)):
            print("Dry run only. Use --execute or execution.execute=true to POST to Tradovate.", file=sys.stderr)
            return
        self.post_to_tradovate(decision["tradovate_payload"])

    def plan_trade(self, row: Any, signal_obj: Any) -> dict[str, Any]:
        direction = str(signal_obj.direction)
        side = "buy" if direction == "long" else "sell"
        tick_size = float(self.variant_config.get("core", {}).get("tick_size", self.data_config.get("tick_size", 0.25)))
        tick_value = float(self.variant_config.get("core", {}).get("tick_value", 12.5))
        slippage_ticks = float(self.variant_config.get("core", {}).get("slippage_ticks", 1))
        entry_estimate = estimated_market_entry(float(row["close"]), direction, tick_size, slippage_ticks)
        stop_price = self.strategy.stop_price(signal_obj, direction, tick_size, entry_price=entry_estimate)
        if stop_price is None:
            return self.reject(row, signal_obj, "strategy did not produce a stop price")
        target_price = self.strategy.target_price(entry_estimate, stop_price, direction, signal=signal_obj)
        if target_already_reached(direction, entry_estimate, target_price, signal_obj):
            return self.reject(row, signal_obj, "target already reached or invalid at entry estimate")

        stop_points = abs(entry_estimate - float(stop_price))
        target_points = abs(float(target_price) - entry_estimate)
        if stop_points <= 0 or target_points <= 0:
            return self.reject(row, signal_obj, "non-positive stop/target distance")

        suggested_qty = self.strategy_suggested_quantity(stop_points, tick_size, tick_value)
        max_qty = int(self.execution_config.get("max_quantity", suggested_qty))
        min_qty = int(self.execution_config.get("min_quantity", 1))
        final = self.guardrail_constrained_quantity(
            side=side,
            symbol=str(self.execution_config.get("guardrail_symbol", self.variant_config.get("symbol", "ES"))),
            suggested_qty=min(suggested_qty, max_qty),
            min_qty=min_qty,
            stop_points=Decimal(str(stop_points)),
            target_points=Decimal(str(target_points)),
        )
        if final is None:
            return self.reject(row, signal_obj, "no quantity passed guardrails", extra={"suggested_quantity": suggested_qty})

        signal_key = (row["timestamp"], direction, str(signal_obj.level_type))
        if signal_key in self.sent_signal_keys:
            return self.reject(row, signal_obj, "signal was already handled")
        self.sent_signal_keys.add(signal_key)

        guardrail_report = final["guardrail_report"]
        tradovate_payload = self.build_tradovate_payload(
            guardrail_report,
            stop_price=float(stop_price),
            target_price=float(target_price),
        )
        return {
            "action": "send_order",
            "timestamp": str(row["timestamp"]),
            "session_date": str(row["session_date"]),
            "strategy_name": getattr(self.strategy, "name", self.variant_config.get("strategy_name")),
            "signal": signal_report(signal_obj),
            "side": side,
            "direction": direction,
            "entry_estimate": entry_estimate,
            "stop_price": float(stop_price),
            "target_price": float(target_price),
            "stop_points": stop_points,
            "target_points": target_points,
            "suggested_quantity": suggested_qty,
            "quantity": final["quantity"],
            "guardrail_report": guardrail_report,
            "tradovate_payload": tradovate_payload,
        }

    def reject(self, row: Any, signal_obj: Any, reason: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "action": "reject_signal",
            "timestamp": str(row["timestamp"]),
            "session_date": str(row["session_date"]),
            "strategy_name": getattr(self.strategy, "name", self.variant_config.get("strategy_name")),
            "signal": signal_report(signal_obj),
            "reason": reason,
        }
        if extra:
            payload.update(extra)
        return payload

    def strategy_suggested_quantity(self, stop_points: float, tick_size: float, tick_value: float) -> int:
        add_project_src_to_path(self.project_root)
        from propstack.backtest.sizing import size_position

        core = copy.deepcopy(self.variant_config.get("core", {}))
        if "position_sizing" not in core:
            core["position_sizing"] = {"mode": "fixed_contracts", "contracts": 1}
        account_equity = min_guardrail_equity(self.guardrails_config)
        sizing = size_position(core, stop_points, tick_size, tick_value, net_liq=account_equity)
        return max(0, int(sizing.contracts))

    def guardrail_constrained_quantity(
        self,
        *,
        side: str,
        symbol: str,
        suggested_qty: int,
        min_qty: int,
        stop_points: Decimal,
        target_points: Decimal,
    ) -> dict[str, Any] | None:
        if suggested_qty < min_qty:
            return None
        for quantity in range(suggested_qty, min_qty - 1, -1):
            args = argparse.Namespace(
                side=side,
                quantity=quantity,
                symbol=symbol,
                accounts=self.execution_config.get("accounts"),
                now=None,
                tp_ticks=None,
                sl_ticks=None,
                tp_points=target_points,
                sl_points=stop_points,
            )
            report = guardrails.check_order(self.guardrails_config, args)
            if report["allowed"]:
                return {"quantity": quantity, "guardrail_report": report}
        return None

    def tradovate_symbol(self) -> str:
        configured = self.tradovate_config.get("symbol") or self.execution_config.get("tradovate_symbol")
        if configured:
            return str(configured)
        root = str(self.execution_config.get("guardrail_symbol") or self.variant_config.get("symbol") or "ES")
        expiry = self.ibkr_config.get("expiry")
        return tradovate.tradovate_contract_symbol(root, expiry) if expiry else root

    def build_tradovate_payload(
        self,
        guardrail_report: dict[str, Any],
        *,
        stop_price: float,
        target_price: float,
        account: tradovate.TradovateAccount | None = None,
    ) -> dict[str, Any]:
        account_spec = account.account_spec if account else self.tradovate_config.get("account_spec")
        account_id = account.account_id if account else self.tradovate_config.get("account_id")
        return tradovate.build_market_oso_payload(
            account_spec=str(account_spec) if account_spec else None,
            account_id=int(account_id) if account_id else None,
            action=guardrail_report["order"]["side"],
            symbol=self.tradovate_symbol(),
            order_qty=int(guardrail_report["order"]["quantity"]),
            target_price=target_price,
            stop_price=stop_price,
            time_in_force=str(self.tradovate_config.get("time_in_force", "Day")),
            cl_ord_id=self.tradovate_config.get("cl_ord_id"),
            custom_tag=self.tradovate_config.get("custom_tag"),
            text=self.tradovate_config.get("text", "strategy-execution-bridge"),
        )

    def post_to_tradovate(self, payload: dict[str, Any]) -> None:
        client, _token_response = tradovate.client_from_config(self.tradovate_config)
        payload = dict(payload)
        if not payload.get("accountSpec") or not payload.get("accountId"):
            account = tradovate.resolve_account(client, self.tradovate_config)
            payload["accountSpec"] = account.account_spec
            payload["accountId"] = account.account_id
        response = client.place_oso(payload)
        print_report({"endpoint": f"{client.base_url}/order/placeoso", "request": payload, "response": response})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live strategy decisions from IBKR through Apex guardrails.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Bridge JSON config inside execution_system.")
    parser.add_argument(
        "--strategy-config",
        help="Campaign variant YAML under configs/campaigns. Overrides config.strategy_config.",
    )
    parser.add_argument("--project-root", help="Project root containing src/ and configs/. Overrides config.project_root.")
    parser.add_argument("--guardrails-config", help="Apex guardrails JSON. Overrides config.guardrails_config.")
    parser.add_argument("--preflight-only", action="store_true", help="Validate strategy/config and exit without opening IBKR.")
    parser.add_argument("--execute", action="store_true", help="Allow Tradovate POSTs after guardrails pass.")
    parser.add_argument("--once", action="store_true", help="Exit after the first completed live minute is evaluated.")
    parser.add_argument("--max-runtime", type=float, default=0.0, help="Optional runtime limit in seconds.")
    parser.add_argument("--ib-host", "--host", dest="ib_host", help="Override IBKR host.")
    parser.add_argument("--ib-port", "--port", dest="ib_port", type=int, help="Override IBKR port.")
    parser.add_argument("--client-id", type=int, help="Override IBKR client id.")
    parser.add_argument("--ib-symbol", "--symbol", dest="ib_symbol", help="Override IBKR futures root symbol.")
    parser.add_argument("--expiry", help="Override IBKR contract expiry, e.g. 202606.")
    parser.add_argument("--local-symbol", help="Override IBKR local symbol, e.g. ESM6.")
    parser.add_argument("--market-data-type", type=int, choices=(1, 2, 3, 4), help="IBKR market data type.")
    parser.add_argument("--historical-duration", help="IBKR historical seed duration, e.g. '14 D'.")
    parser.add_argument("--tradovate-symbol", help="Override Tradovate contract symbol, e.g. ESM6.")
    parser.add_argument("--tradovate-account-id", type=int, help="Override Tradovate account id.")
    parser.add_argument("--tradovate-account-spec", help="Override Tradovate account spec/name.")
    parser.add_argument("--tradovate-environment", choices=("demo", "live"), help="Override Tradovate environment.")
    parser.add_argument("--tradovate-access-token", help="Override Tradovate bearer token.")
    parser.add_argument("--max-quantity", type=int, help="Max order quantity before guardrail clamp.")
    return parser.parse_args()


def apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    config = copy.deepcopy(config)
    if args.project_root:
        config["project_root"] = args.project_root
    if args.strategy_config:
        config["strategy_config"] = args.strategy_config
    if args.guardrails_config:
        config["guardrails_config"] = args.guardrails_config

    ibkr = config.setdefault("ibkr", {})
    for arg_name, key in {
        "ib_host": "host",
        "ib_port": "port",
        "client_id": "client_id",
        "ib_symbol": "symbol",
        "expiry": "expiry",
        "local_symbol": "local_symbol",
        "market_data_type": "market_data_type",
        "historical_duration": "historical_duration",
    }.items():
        value = getattr(args, arg_name)
        if value is not None:
            ibkr[key] = value

    execution = config.setdefault("execution", {})
    tv_config = config.setdefault("tradovate", {})
    if args.tradovate_symbol:
        tv_config["symbol"] = args.tradovate_symbol
    if args.tradovate_account_id is not None:
        tv_config["account_id"] = args.tradovate_account_id
    if args.tradovate_account_spec:
        tv_config["account_spec"] = args.tradovate_account_spec
    if args.tradovate_environment:
        tv_config["environment"] = args.tradovate_environment
    if args.tradovate_access_token:
        tv_config["access_token"] = args.tradovate_access_token
    if args.max_quantity is not None:
        execution["max_quantity"] = args.max_quantity
    if args.execute:
        execution["execute"] = True
        execution["send_to_tradovate"] = True
    return config


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"config is not valid JSON: {path}: {exc}") from exc


def load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise RuntimeError("Missing dependency: python3 -m pip install pyyaml")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"strategy config not found: {path}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"strategy config must be a YAML mapping: {path}")
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
        errors.append("variant YAML must define top-level timeframe")
    if not config.get("symbol"):
        errors.append("variant YAML must define top-level symbol")

    strategy = config.get("strategy")
    if not isinstance(strategy, dict):
        errors.append("variant YAML must define strategy mapping")
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

    data_config = config.get("data")
    if not isinstance(data_config, dict):
        warnings.append("variant YAML has no data mapping; execution will use default session settings")
    elif not data_config.get("timezone"):
        warnings.append("data.timezone is missing; execution will default to America/New_York")

    if errors:
        joined = "\n  - ".join(errors)
        raise ValueError(f"Strategy variant preflight failed for {path}:\n  - {joined}")
    return warnings


def build_contract(ibkr: dict[str, Any]) -> Any:
    if Contract is None:
        raise RuntimeError("Missing dependency: python3 -m pip install ibapi")
    contract = Contract()
    contract.symbol = str(ibkr.get("symbol", "ES"))
    contract.secType = "FUT"
    contract.exchange = str(ibkr.get("exchange", "CME"))
    contract.currency = str(ibkr.get("currency", "USD"))
    multiplier = ibkr.get("multiplier") or default_futures_multiplier(contract.symbol)
    if multiplier:
        contract.multiplier = str(multiplier)
    local_symbol = ibkr.get("local_symbol")
    if local_symbol:
        contract.localSymbol = str(local_symbol)
    else:
        contract.lastTradeDateOrContractMonth = str(ibkr.get("expiry") or next_quarterly_expiry())
    return contract


def display_symbol(contract: Any) -> str:
    contract_id = getattr(contract, "localSymbol", "") or getattr(contract, "lastTradeDateOrContractMonth", "")
    return f"{contract.symbol} {contract_id} {contract.exchange}".strip()


def default_futures_multiplier(symbol: str) -> str:
    return {
        "ES": "50",
        "MES": "5",
        "NQ": "20",
        "MNQ": "2",
        "YM": "5",
        "MYM": "0.5",
        "RTY": "50",
        "M2K": "5",
    }.get(str(symbol).upper(), "")


def ib_bar_to_minute(bar: Any, symbol: str, source: str) -> OneMinuteBar | None:
    epoch = parse_epoch(getattr(bar, "date", None))
    if epoch is None:
        return None
    return OneMinuteBar(
        timestamp_epoch=epoch,
        symbol=symbol,
        open=float(bar.open),
        high=float(bar.high),
        low=float(bar.low),
        close=float(bar.close),
        volume=to_decimal(bar.volume),
        count=int(getattr(bar, "barCount", 0) or 0),
        source=source,
    )


def bars_to_dataframe(bars: list[OneMinuteBar], *, market_timezone: str, symbol: str):
    if pd is None:
        raise RuntimeError("Missing dependency: python3 -m pip install pandas")
    rows = []
    for bar in bars:
        timestamp_utc = pd.Timestamp(bar.timestamp_epoch, unit="s", tz="UTC")
        rows.append(
            {
                "timestamp": timestamp_utc.tz_convert(market_timezone),
                "timestamp_utc": timestamp_utc,
                "symbol": symbol,
                "contract_symbol": bar.symbol,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
                "source": bar.source,
            }
        )
    if not rows:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "timestamp_utc",
                "symbol",
                "contract_symbol",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "source",
            ]
        )
    return pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)


def parse_epoch(value: Any) -> int | None:
    try:
        epoch = int(str(value))
    except (TypeError, ValueError):
        return None
    return epoch if epoch > 0 else None


def epoch_to_utc_iso(epoch: int) -> str:
    return dt.datetime.fromtimestamp(epoch, tz=dt.timezone.utc).isoformat().replace("+00:00", "Z")


def to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def estimated_market_entry(close_price: float, direction: str, tick_size: float, slippage_ticks: float) -> float:
    slip = tick_size * slippage_ticks
    return close_price + slip if direction == "long" else close_price - slip


def target_already_reached(direction: str, entry: float, target: float, signal_obj: Any) -> bool:
    if not math.isfinite(entry) or not math.isfinite(target):
        return True
    if direction == "long":
        if entry >= target:
            return True
        confirmation_high = signal_metadata_float(signal_obj, "confirmation_high")
        return confirmation_high is not None and confirmation_high >= target
    if direction == "short":
        if entry <= target:
            return True
        confirmation_low = signal_metadata_float(signal_obj, "confirmation_low")
        return confirmation_low is not None and confirmation_low <= target
    return True


def signal_metadata_float(signal_obj: Any, key: str) -> float | None:
    try:
        value = signal_obj.metadata.get(key)
    except AttributeError:
        return None
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def signal_report(signal_obj: Any) -> dict[str, Any]:
    return {
        "direction": str(getattr(signal_obj, "direction", "")),
        "level_type": str(getattr(signal_obj, "level_type", "")),
        "swept_level": getattr(signal_obj, "swept_level", None),
        "metadata": getattr(signal_obj, "metadata", {}),
        "report_fields": getattr(signal_obj, "report_fields", {}),
    }


def min_guardrail_equity(config: dict[str, Any]) -> float:
    accounts = guardrails.selected_accounts(config, None)
    values = []
    for account in accounts:
        current_balance = guardrails.money(account.get("current_balance", account.get("starting_balance", 50000)))
        current_equity = guardrails.money(account.get("current_equity", current_balance))
        values.append(float(current_equity))
    return min(values) if values else 0.0


def add_project_src_to_path(project_root: Path) -> None:
    src = str(project_root / "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def resolve_path(base: Path, value: str | os.PathLike[str]) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base / path).resolve()


def resolve_strategy_path(project_root: Path, config_dir: Path, value: str | os.PathLike[str]) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    config_relative = (config_dir / path).resolve()
    if config_relative.exists():
        return config_relative
    return (project_root / path).resolve()


def parse_timeframe_minutes(value: Any) -> int:
    if value is None:
        raise ValueError("timeframe is required")
    text = str(value).strip().lower()
    if text.endswith("mins"):
        text = text[:-4]
    elif text.endswith("min"):
        text = text[:-3]
    elif text.endswith("m"):
        text = text[:-1]
    elif text.endswith("hours"):
        text = str(float(text[:-5].strip()) * 60)
    elif text.endswith("hour"):
        text = str(float(text[:-4].strip()) * 60)
    elif text.endswith("h"):
        text = str(float(text[:-1].strip()) * 60)
    minutes = int(float(text))
    if minutes <= 0:
        raise ValueError("timeframe must be positive")
    return minutes


def historical_duration_days(value: str) -> int | None:
    parts = str(value).strip().split()
    if len(parts) != 2:
        return None
    try:
        amount = float(parts[0])
    except ValueError:
        return None
    unit = parts[1].upper()
    if unit.startswith("D"):
        return int(amount)
    if unit.startswith("W"):
        return int(amount * 7)
    if unit.startswith("M"):
        return int(amount * 30)
    if unit.startswith("Y"):
        return int(amount * 365)
    if unit.startswith("H"):
        return 0
    return None


def print_report(report: dict[str, Any]) -> None:
    print(json.dumps(report, indent=2, sort_keys=True, default=guardrails.json_default))


def run() -> int:
    args = parse_args()
    if PANDAS_IMPORT_ERROR is not None:
        print("Missing dependency: python3 -m pip install pandas", file=sys.stderr)
        return 2
    if YAML_IMPORT_ERROR is not None:
        print("Missing dependency: python3 -m pip install pyyaml", file=sys.stderr)
        return 2
    config_path = Path(args.config).expanduser().resolve()
    config = apply_cli_overrides(load_json(config_path), args)

    runtime = StrategyExecutionRuntime(config, config_path)
    print_report(runtime.preflight_report())
    if args.preflight_only:
        return 0

    if IBAPI_IMPORT_ERROR is not None:
        print("Missing dependency: python3 -m pip install ibapi", file=sys.stderr)
        return 2

    patch_ibapi_realtime_bar_decimal_volume()

    contract = build_contract(runtime.ibkr_config)
    display = display_symbol(contract)
    stop_after_first_live_bar = threading.Event()

    def on_completed(bar: OneMinuteBar) -> None:
        runtime.on_completed_minute(bar)
        if args.once:
            stop_after_first_live_bar.set()

    app = IbkrBridgeApp(
        ibkr_config=runtime.ibkr_config,
        contract=contract,
        display_symbol=display,
        on_seed=runtime.seed,
        on_completed_minute=on_completed,
    )

    host = str(runtime.ibkr_config.get("host", "127.0.0.1"))
    port = int(runtime.ibkr_config.get("port", 4002))
    client_id = int(runtime.ibkr_config.get("client_id", 82))
    print(f"Connecting to IBKR {host}:{port} client_id={client_id} contract={display}", file=sys.stderr)
    app.connect(host, port, client_id)
    thread = threading.Thread(target=app.run, name="ibkr-strategy-execution", daemon=True)
    thread.start()

    if not app.started.wait(float(runtime.ibkr_config.get("connect_timeout", 15))):
        print("Timed out waiting for IBKR nextValidId.", file=sys.stderr)
        app.shutdown()
        thread.join(timeout=2)
        return 1
    if not app.seeded.wait(float(runtime.ibkr_config.get("historical_timeout", 90))):
        print("Timed out waiting for IBKR historical seed.", file=sys.stderr)
        app.shutdown()
        thread.join(timeout=2)
        return 1

    stop_requested = False

    def handle_signal(*_: Any) -> None:
        nonlocal stop_requested
        stop_requested = True
        app.shutdown()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    deadline = time.monotonic() + args.max_runtime if args.max_runtime > 0 else None
    while not app.done.is_set():
        if stop_after_first_live_bar.is_set():
            app.shutdown()
            break
        if deadline and time.monotonic() >= deadline:
            app.shutdown()
            break
        time.sleep(0.2)

    app.shutdown()
    thread.join(timeout=2)
    if app.failed:
        return 1
    return 130 if stop_requested else 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001 - keep CLI failure readable.
        print(f"fatal: {exc}", file=sys.stderr)
        raise SystemExit(1)
