from __future__ import annotations

import copy
from dataclasses import dataclass
import json
import math
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from propstack.backtest.contracts import ExecutionAssumptions, validate_market_data_contract
from propstack.backtest.fills import entry_price, exit_price, stop_target_hit
from propstack.backtest.metrics import calculate_metrics, daily_results
from propstack.backtest.risk import DailyRisk
from propstack.backtest.sizing import size_position
from propstack.strategy import ModularStrategy
from propstack.strategy_modules.entry import entry_module_metadata
from propstack.utils.config import config_timeframe_minutes
from propstack.utils.hashing import object_sha256
from propstack.utils.progress import progress_bar
from propstack.utils.target_rr import require_minimum_target_rr
from propstack.utils.time import parse_time
from propstack.validation.exporter import build_bar_window_rows, build_tick_window_rows
from propstack.validation.exit_path import enrich_exit_audits
from propstack.validation.schema import CONDITION_SNAPSHOT_COLUMNS, EXIT_AUDIT_COLUMNS, normalize_columns
from propstack.version import ENGINE_CONTRACT_VERSION


@dataclass(frozen=True)
class ApexRules:
    enabled: bool = False
    timezone: str = "America/New_York"
    latest_flat_time: object = parse_time("16:59:59")
    cancel_pending_orders_before_flatten: bool = True
    no_overnight_positions: bool = True
    reject_if_position_after_flatten_deadline: bool = True
    reject_if_pending_order_after_flatten_deadline: bool = True
    reject_if_entry_after_latest_entry_time: bool = True
    force_flatten_enabled: bool = True
    force_flatten_time: object = parse_time("16:58:30")
    latest_entry_time: object = parse_time("16:45:00")

    @classmethod
    def from_config(cls, config: dict) -> "ApexRules":
        raw = dict(config.get("apex_rules") or {})
        return cls(
            enabled=bool(raw.get("enabled", False)),
            timezone=str(raw.get("timezone", "America/New_York")),
            latest_flat_time=parse_time(raw.get("latest_flat_time", "16:59:59")),
            cancel_pending_orders_before_flatten=bool(raw.get("cancel_pending_orders_before_flatten", True)),
            no_overnight_positions=bool(raw.get("no_overnight_positions", True)),
            reject_if_position_after_flatten_deadline=bool(
                raw.get("reject_if_position_after_flatten_deadline", True)
            ),
            reject_if_pending_order_after_flatten_deadline=bool(
                raw.get("reject_if_pending_order_after_flatten_deadline", True)
            ),
            reject_if_entry_after_latest_entry_time=bool(raw.get("reject_if_entry_after_latest_entry_time", True)),
            force_flatten_enabled=bool(raw.get("force_flatten_enabled", True)),
            force_flatten_time=parse_time(raw.get("force_flatten_time", "16:58:30")),
            latest_entry_time=parse_time(raw.get("latest_entry_time", "16:45:00")),
        )


@dataclass(frozen=True)
class NoTradeWindow:
    name: str
    dates: frozenset[str]
    start_time: object
    end_time: object
    timezone: str
    block_entries: bool = True
    cancel_pending_orders: bool = True
    flatten_positions: bool = True
    exit_reason: str = "event_no_trade_flatten"


@dataclass(frozen=True)
class EventFilters:
    enabled: bool = False
    timezone: str = "America/New_York"
    no_trade_windows: tuple[NoTradeWindow, ...] = ()

    @classmethod
    def from_config(cls, config: dict) -> "EventFilters":
        raw = dict(config.get("event_filters") or {})
        enabled = bool(raw.get("enabled", False))
        timezone = str(raw.get("timezone", "America/New_York"))
        windows = []
        for item in raw.get("no_trade_windows") or []:
            window = dict(item or {})
            window_timezone = str(window.get("timezone", timezone))
            dates = _no_trade_window_dates(window)
            windows.append(
                NoTradeWindow(
                    name=str(window.get("name", "event_no_trade_window")),
                    dates=frozenset(dates),
                    start_time=parse_time(window.get("start_time", "00:00:00")),
                    end_time=parse_time(window.get("end_time", "23:59:59")),
                    timezone=window_timezone,
                    block_entries=bool(window.get("block_entries", True)),
                    cancel_pending_orders=bool(window.get("cancel_pending_orders", True)),
                    flatten_positions=bool(window.get("flatten_positions", True)),
                    exit_reason=str(window.get("exit_reason", "event_no_trade_flatten")),
                )
            )
        return cls(enabled=enabled, timezone=timezone, no_trade_windows=tuple(windows))


@dataclass(frozen=True)
class ValidationExportConfig:
    enabled: bool = False
    window_bars_before: int = 5
    window_bars_after: int = 5
    max_trades: int | None = None

    @classmethod
    def from_config(cls, config: dict) -> "ValidationExportConfig":
        raw = dict(config.get("validation_export") or {})
        raw.update(dict((config.get("core") or {}).get("validation_export") or {}))
        max_trades = raw.get("max_trades")
        return cls(
            enabled=bool(raw.get("enabled", False) or raw.get("export", False)),
            window_bars_before=max(0, int(raw.get("window_bars_before", 5) or 0)),
            window_bars_after=max(0, int(raw.get("window_bars_after", 5) or 0)),
            max_trades=None if max_trades in (None, "") else max(0, int(max_trades)),
        )


class BacktestEngine:
    def __init__(self, config: dict, show_progress: bool = False):
        require_minimum_target_rr(config.get("strategy", {}), context="strategy")
        self.config = config
        self.strategy_config = copy.deepcopy(config.get("strategy", {}))
        if "strategy_name" not in self.strategy_config and config.get("strategy_name"):
            self.strategy_config["strategy_name"] = config["strategy_name"]
        self.core_config = config.get("core", {})
        self.execution_assumptions = ExecutionAssumptions.from_core_config(self.core_config)
        self.apex_rules = ApexRules.from_config(config)
        self.apex_timezone = ZoneInfo(self.apex_rules.timezone)
        self.event_filters = EventFilters.from_config(config)
        self.validation_export = ValidationExportConfig.from_config(config)
        self.show_progress = show_progress
        self.timeframe_minutes = self._configured_bar_interval_minutes()
        self._apply_timeframe_to_strategy()

    def run(self, data: pd.DataFrame, detail_data: pd.DataFrame | None = None) -> dict:
        data_contract = validate_market_data_contract(
            data,
            label="Backtest data",
            require_session_date=True,
        )
        detail_contract = None
        if detail_data is not None:
            detail_contract = validate_market_data_contract(
                detail_data,
                label="Backtest detail_data",
                require_session_date=False,
                allow_duplicate_timestamps=True,
            )
        df = data.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
        detail_df = None
        detail_attrs = getattr(detail_data, "attrs", {}) if detail_data is not None else {}
        if detail_data is not None and not detail_data.empty:
            detail_df = detail_data.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
            detail_df.attrs.update(detail_attrs)
        diagnostics = self._preflight(df, detail_df, data_contract, detail_contract)
        strategy = ModularStrategy(self.strategy_config)
        entry_params = self.strategy_config.get("entry", {}).get("params", {})
        risk = DailyRisk({**self.core_config, **self.strategy_config, **entry_params})
        tick_size = self.execution_assumptions.tick_size
        tick_value = self.execution_assumptions.tick_value
        commission = self.execution_assumptions.commission_per_contract
        slippage_ticks = self.execution_assumptions.slippage_ticks
        flatten_time = parse_time(self.strategy_config.get("flatten_time", self.core_config.get("flatten_time", "14:55:00")))
        bar_interval_minutes = self.timeframe_minutes
        net_liq = float(self.core_config.get("initial_balance", 0.0))
        bar_delta = pd.Timedelta(minutes=bar_interval_minutes)
        timestamps = [pd.Timestamp(timestamp) for timestamp in df["timestamp"]] if len(df) else []
        bar_close_timestamps = [timestamp + bar_delta for timestamp in timestamps]
        next_entry_timestamps = timestamps[1:] + [None] if timestamps else []
        next_bar_close_timestamps = bar_close_timestamps[1:] + [None] if bar_close_timestamps else []
        detail_timestamps = (
            pd.to_datetime(detail_df["timestamp"]).reset_index(drop=True) if detail_df is not None else None
        )

        pending_signal = None
        pending_validation_context = None
        position = None
        trades = []
        validation_condition_rows = []
        validation_exit_rows = []
        validation_trade_contexts = {}
        trade_id = 1
        progress = progress_bar(len(df), "bars", enabled=self.show_progress)

        def open_position_from_signal(sig, bar, reference_price, entry_timestamp, entry_bar_index, signal_context=None):
            nonlocal trade_id

            direction = sig.direction
            ep = entry_price(float(reference_price), direction, tick_size, slippage_ticks)
            stop = strategy.stop_price(sig, direction, tick_size, entry_price=ep)
            if stop is None:
                diagnostics["rejects"]["missing_stop"] += 1
                return None
            target = strategy.target_price(ep, stop, direction, signal=sig)
            if _target_already_reached(direction, ep, target, sig):
                diagnostics["rejects"]["target_already_reached"] += 1
                return None
            risk_points = abs(ep - stop)
            sizing = size_position(self.core_config, risk_points, tick_size, tick_value, net_liq=net_liq)
            if sizing.contracts < 1:
                diagnostics["rejects"]["position_sizing"] += 1
                return None
            opened = {
                "trade_id": trade_id,
                "strategy_name": strategy.name,
                "session_date": bar["session_date"],
                "direction": direction,
                "level_type": sig.level_type,
            }
            if sig.report_fields:
                opened.update(sig.report_fields)
            else:
                opened.update(
                    {
                        "swept_level": sig.swept_level,
                        "sweep_timestamp": sig.sweep_timestamp,
                        "sweep_high": sig.sweep_high,
                        "sweep_low": sig.sweep_low,
                        "reclaim_timestamp": sig.reclaim_timestamp,
                    }
                )
            opened.update(
                {
                    "entry_timestamp": entry_timestamp,
                    "entry_reference_price_raw": float(reference_price),
                    "entry_price": ep,
                    "stop_price": stop,
                    "target_price": target,
                    "risk_points": risk_points,
                    "signal_flatten_time": _format_time(_signal_metadata_time(sig, "flatten_time", flatten_time)),
                    "contracts": sizing.contracts,
                    "max_favorable_excursion": 0.0,
                    "max_adverse_excursion": 0.0,
                }
            )
            opened.update(sizing.report_fields())
            risk.record_entry(bar["session_date"])
            diagnostics["entries_opened"] += 1
            if self.validation_export.enabled:
                context = dict(signal_context or {})
                context.update(
                    {
                        "entry_bar_index": int(entry_bar_index),
                        "entry_execution_time": entry_timestamp,
                        "entry_reference_price": reference_price,
                        "no_trade_window_filter_pass": self._event_entry_allowed(entry_timestamp),
                        "max_trades_filter_pass": True,
                    }
                )
                validation_trade_contexts[trade_id] = context
                validation_condition_rows.append(
                    self._validation_condition_snapshot(
                        trade_id,
                        sig,
                        bar,
                        context,
                        ep,
                        stop,
                        target,
                        risk_points,
                        strategy,
                        tick_size,
                        df,
                        detail_df,
                    )
                )
            trade_id += 1
            return opened

        def maybe_close_position(opened, bar, index, detail_start_timestamp=None):
            nonlocal net_liq

            direction = opened["direction"]
            segment_start = (
                pd.Timestamp(detail_start_timestamp)
                if detail_start_timestamp is not None
                else pd.Timestamp(bar["timestamp"])
            )
            bar_close_timestamp = bar_close_timestamps[index]
            next_bar_close_timestamp = next_bar_close_timestamps[index]
            opened_this_bar = pd.Timestamp(opened["entry_timestamp"]) >= pd.Timestamp(bar["timestamp"])
            event_window = None
            exit_audit = {} if self.validation_export.enabled else None
            self._maybe_update_dynamic_stop(
                opened,
                bar,
                direction,
                detail_df,
                segment_start,
                bar_close_timestamp,
                diagnostics,
            )
            reason, raw_exit, exit_timestamp = self._resolve_stop_target_exit(
                bar,
                direction,
                opened["stop_price"],
                opened["target_price"],
                bar_close_timestamp,
                detail_df,
                diagnostics,
                start_timestamp=detail_start_timestamp,
                suppress_first_detail_target=detail_start_timestamp is not None,
                allow_open_gap_fill=not opened_this_bar,
                audit=exit_audit,
            )
            position_flatten_time = parse_time(opened.get("signal_flatten_time", flatten_time))
            if reason is None and bar_close_timestamp.time() >= position_flatten_time:
                reason, raw_exit = "eod_flatten", float(bar["close"])
                exit_timestamp = bar_close_timestamp
            if reason is None:
                event_window = self._event_window_to_flatten_before(
                    bar_close_timestamp,
                    next_bar_close_timestamp,
                )
                if event_window is not None:
                    reason, raw_exit = event_window.exit_reason, float(bar["close"])
                    exit_timestamp = bar_close_timestamp
            if reason is None and self._apex_should_force_flatten(
                bar_close_timestamp,
                next_bar_close_timestamp,
            ):
                reason, raw_exit = "forced_apex_flatten", float(bar["close"])
                exit_timestamp = bar_close_timestamp
            if reason is None:
                _update_trade_excursions(
                    opened,
                    bar,
                    detail_df,
                    detail_timestamps,
                    segment_start,
                    bar_close_timestamp,
                    exit_reason=None,
                    raw_exit=None,
                )
                return opened, False

            _update_trade_excursions(
                opened,
                bar,
                detail_df,
                detail_timestamps,
                segment_start,
                exit_timestamp,
                exit_reason=reason,
                raw_exit=raw_exit,
            )
            xp = exit_price(float(raw_exit), direction, tick_size, slippage_ticks)
            point_pnl = xp - opened["entry_price"] if direction == "long" else opened["entry_price"] - xp
            reference_point_pnl = (
                float(raw_exit) - opened["entry_reference_price_raw"]
                if direction == "long"
                else opened["entry_reference_price_raw"] - float(raw_exit)
            )
            contracts = int(opened["contracts"])
            gross = point_pnl / tick_size * tick_value * contracts
            gross_before_slippage = reference_point_pnl / tick_size * tick_value * contracts
            total_commission = commission * contracts * 2
            slippage_cost = slippage_ticks * tick_value * contracts * 2
            net = gross - total_commission
            r_mult = point_pnl / opened["risk_points"] if opened["risk_points"] else 0.0
            trade = {
                **opened,
                "exit_timestamp": exit_timestamp,
                "exit_reference_price_raw": float(raw_exit),
                "exit_price": xp,
                "exit_reason": reason,
                "gross_pnl_before_slippage": gross_before_slippage,
                "gross_pnl": gross,
                "net_pnl": net,
                "r_multiple": r_mult,
                "commission": total_commission,
                "slippage_cost": slippage_cost,
                "total_transaction_cost": total_commission + slippage_cost,
                "cost_accounting_error": gross_before_slippage - slippage_cost - gross,
            }
            trade.update(self._apex_trade_fields(trade))
            trades.append(trade)
            diagnostics["exits"][reason] = diagnostics["exits"].get(reason, 0) + 1
            self._record_trade_apex_diagnostics(trade, diagnostics)
            if event_window is not None and reason == event_window.exit_reason:
                self._record_event_flatten(diagnostics, event_window)
            risk.record_exit(opened["session_date"], net)
            net_liq += net
            if self.validation_export.enabled:
                context = validation_trade_contexts.setdefault(opened["trade_id"], {})
                context["exit_bar_index"] = int(index)
                validation_exit_rows.append(
                    self._validation_exit_audit(
                        trade,
                        bar,
                        raw_exit,
                        exit_audit or {},
                        tick_size,
                    )
                )
            return None, True

        def detail_rows_between(start_timestamp, end_timestamp):
            if detail_df is None or detail_timestamps is None:
                return None
            left = int(detail_timestamps.searchsorted(pd.Timestamp(start_timestamp), side="left"))
            right = int(detail_timestamps.searchsorted(pd.Timestamp(end_timestamp), side="left"))
            if right <= left:
                return detail_df.iloc[0:0]
            return detail_df.iloc[left:right]

        def open_intrabar_signal(signal, bar, index, bar_close_timestamp, signal_context=None):
            entry_timestamp = _signal_metadata_timestamp(signal, "intended_entry_timestamp")
            reference_price = _signal_metadata_float(signal, "entry_reference_price")
            if entry_timestamp is None:
                entry_timestamp = _signal_metadata_timestamp(signal, "intrabar_entry_timestamp")
            if reference_price is None:
                reference_price = _signal_metadata_float(signal, "intrabar_entry_price")
            if entry_timestamp is None:
                entry_timestamp = bar_close_timestamp
            if reference_price is None:
                diagnostics["rejects"]["missing_intrabar_entry_price"] += 1
                return None, False
            if self._apex_entry_allowed(entry_timestamp) and self._event_entry_allowed(entry_timestamp):
                diagnostics["intrabar_entries_requested"] += 1
                opened = open_position_from_signal(
                    signal,
                    bar,
                    reference_price,
                    entry_timestamp,
                    index,
                    signal_context=signal_context,
                )
                if opened is None:
                    return None, False
                return maybe_close_position(opened, bar, index, detail_start_timestamp=entry_timestamp)
            if not self._apex_entry_allowed(entry_timestamp):
                diagnostics["rejects"]["apex_latest_entry_time"] += 1
                self._record_apex_pending_cancel(diagnostics, entry_timestamp)
            else:
                diagnostics["rejects"]["event_no_trade_window"] += 1
                self._record_event_pending_cancel(diagnostics, entry_timestamp)
            return None, False

        for i, bar in df.iterrows():
            progress.update(i + 1)
            if pending_signal is not None and position is None and not self._apex_entry_allowed(bar["timestamp"]):
                diagnostics["rejects"]["apex_latest_entry_time"] += 1
                self._record_apex_pending_cancel(diagnostics, bar["timestamp"])
                pending_signal = None
                pending_validation_context = None
            if pending_signal is not None and position is None and not self._event_entry_allowed(bar["timestamp"]):
                diagnostics["rejects"]["event_no_trade_window"] += 1
                self._record_event_pending_cancel(diagnostics, bar["timestamp"])
                pending_signal = None
                pending_validation_context = None

            if pending_signal is not None and position is None and risk.allow_new_trade(bar["session_date"]):
                sig = pending_signal
                position = open_position_from_signal(
                    sig,
                    bar,
                    bar["open"],
                    bar["timestamp"],
                    i,
                    signal_context=pending_validation_context,
                )
            elif pending_signal is not None and position is None:
                diagnostics["rejects"]["daily_risk_lockout"] += 1
            pending_signal = None
            pending_validation_context = None

            if position is not None:
                position, closed = maybe_close_position(position, bar, i)
                if closed:
                    continue

            if position is None and risk.allow_new_trade(bar["session_date"]):
                bar_close_timestamp = bar_close_timestamps[i]
                detail_rows = detail_rows_between(bar["timestamp"], bar_close_timestamp)
                if detail_rows is not None and not detail_rows.empty:
                    signal = strategy.on_bar_intrabar(bar, detail_rows, risk.trades_today(bar["session_date"]))
                    if signal is not None:
                        diagnostics["signals_generated"] += 1
                        diagnostics["intrabar_signals_generated"] += 1
                        signal_context = self._validation_signal_context(
                            signal,
                            bar,
                            i,
                            "intrabar",
                            bar_close_timestamp,
                            detail_rows=detail_rows,
                            trades_today=risk.trades_today(bar["session_date"]),
                        )
                        position, closed = open_intrabar_signal(
                            signal,
                            bar,
                            i,
                            bar_close_timestamp,
                            signal_context=signal_context,
                        )
                        if closed:
                            continue
                        if position is not None:
                            continue
                signal = strategy.on_bar_close(bar, risk.trades_today(bar["session_date"]))
                if signal is not None:
                    diagnostics["signals_generated"] += 1
                    entry_mode = _signal_entry_mode(signal)
                    if entry_mode == "intrabar":
                        signal_context = self._validation_signal_context(
                            signal,
                            bar,
                            i,
                            "bar_close_intrabar",
                            bar_close_timestamp,
                            trades_today=risk.trades_today(bar["session_date"]),
                        )
                        position, closed = open_intrabar_signal(
                            signal,
                            bar,
                            i,
                            bar_close_timestamp,
                            signal_context=signal_context,
                        )
                        if closed:
                            continue
                    else:
                        next_entry_timestamp = next_entry_timestamps[i]
                        if (
                            next_entry_timestamp is not None
                            and self._apex_entry_allowed(next_entry_timestamp)
                            and self._event_entry_allowed(next_entry_timestamp)
                        ):
                            pending_signal = signal
                            pending_validation_context = self._validation_signal_context(
                                signal,
                                bar,
                                i,
                                "bar_close",
                                bar_close_timestamp,
                                entry_execution_time=next_entry_timestamp,
                                trades_today=risk.trades_today(bar["session_date"]),
                            )
                        else:
                            if next_entry_timestamp is None or not self._apex_entry_allowed(next_entry_timestamp):
                                diagnostics["rejects"]["apex_latest_entry_time"] += 1
                                self._record_apex_pending_cancel(diagnostics, bar_close_timestamp)
                            elif not self._event_entry_allowed(next_entry_timestamp):
                                diagnostics["rejects"]["event_no_trade_window"] += 1
                                self._record_event_pending_cancel(diagnostics, next_entry_timestamp)

        if pending_signal is not None and self.apex_rules.enabled:
            last_timestamp = timestamps[-1] if timestamps else pd.Timestamp.now(tz=self.apex_timezone)
            self._record_apex_pending_cancel(diagnostics, last_timestamp)
            pending_signal = None
            pending_validation_context = None
        if position is not None and self.apex_rules.enabled:
            self._record_apex_violation(diagnostics, "position_after_flatten_deadline")

        trades_df = pd.DataFrame(trades)
        diagnostics["trades_closed"] = int(len(trades_df))
        metrics = calculate_metrics(
            trades_df,
            initial_balance=float(self.core_config.get("initial_balance", 0)),
        )
        if self.event_filters.enabled:
            metrics["event_no_trade_flatten_trades"] = int(diagnostics["event_filters"]["flatten_trades"])
            metrics["event_no_trade_entry_rejections"] = int(diagnostics["event_filters"]["entry_rejections"])
        if self.apex_rules.enabled:
            metrics["apex_rule_violations"] = max(
                int(metrics.get("apex_rule_violations", 0)),
                int(diagnostics["apex"]["rule_violations"]),
            )
            metrics["apex_forced_flatten_trades"] = int(diagnostics["apex"]["forced_flatten_trades"])
        output = {
            "trades": trades_df,
            "daily": daily_results(trades_df),
            "metrics": metrics,
            "diagnostics": diagnostics,
            "reproducibility": {
                "engine_contract_version": ENGINE_CONTRACT_VERSION,
                "config_hash": object_sha256(self.config),
                "data_contract": data_contract,
                "detail_data_contract": detail_contract,
                "execution_assumptions": self.execution_assumptions.as_dict(),
            },
        }
        if self.validation_export.enabled:
            output["validation"] = self._validation_frames(
                df,
                detail_df,
                trades_df,
                validation_condition_rows,
                validation_exit_rows,
                validation_trade_contexts,
                bar_delta,
            )
        return output

    def _validation_signal_context(
        self,
        signal,
        bar: pd.Series,
        index: int,
        source: str,
        bar_close_timestamp: pd.Timestamp,
        *,
        entry_execution_time=None,
        detail_rows: pd.DataFrame | None = None,
        trades_today: int | None = None,
    ) -> dict | None:
        if not self.validation_export.enabled:
            return None
        context = {
            "signal_source": source,
            "decision_bar_index": int(index),
            "decision_bar_time": bar_close_timestamp,
            "bar_timestamp": bar["timestamp"],
            "bar_close_timestamp": bar_close_timestamp,
            "entry_execution_time": entry_execution_time,
            "trades_today_before_signal": trades_today,
            "entry_mode": _signal_entry_mode(signal),
        }
        if detail_rows is not None:
            context.update(
                {
                    "detail_rows_seen": int(len(detail_rows)),
                    "detail_start_timestamp": detail_rows["timestamp"].iloc[0] if len(detail_rows) else None,
                    "detail_end_timestamp": detail_rows["timestamp"].iloc[-1] if len(detail_rows) else None,
                    "detail_granularity": _detail_granularity(detail_rows),
                }
            )
        return context

    def _validation_condition_snapshot(
        self,
        trade_id: int,
        signal,
        bar: pd.Series,
        context: dict,
        entry: float,
        stop: float,
        target: float,
        risk_points: float,
        strategy: ModularStrategy,
        tick_size: float,
        data: pd.DataFrame,
        detail_data: pd.DataFrame | None,
    ) -> dict:
        metadata = dict(getattr(signal, "metadata", {}) or {})
        report_fields = dict(getattr(signal, "report_fields", {}) or {})
        sweep_time = _first_present(
            report_fields.get("sweep_time"),
            report_fields.get("sweep_timestamp"),
            getattr(signal, "sweep_timestamp", None),
            metadata.get("sweep_timestamp"),
        )
        reclaim_time = _first_present(
            report_fields.get("reclaim_time"),
            report_fields.get("reclaim_timestamp"),
            getattr(signal, "reclaim_timestamp", None),
            metadata.get("reclaim_timestamp"),
        )
        sweep_source_row = _validation_source_row_for_timestamp(sweep_time, data, detail_data)
        reclaim_source_row = _validation_source_row_for_timestamp(reclaim_time, data, detail_data)
        trigger_values = {
            "direction": getattr(signal, "direction", None),
            "level_type": getattr(signal, "level_type", None),
            "swept_level": getattr(signal, "swept_level", None),
            "sweep_timestamp": sweep_time,
            "reclaim_timestamp": reclaim_time,
            "entry_reference_price": context.get("entry_reference_price"),
            "entry_price": entry,
            "risk_points": risk_points,
            "sweep_source_row": sweep_source_row,
            "reclaim_source_row": reclaim_source_row,
        }
        signal_time = _first_present(
            report_fields.get("signal_time"),
            report_fields.get("signal_timestamp"),
            metadata.get("signal_timestamp"),
            reclaim_time,
            context.get("decision_bar_time"),
        )
        decision_bar_time = _first_present(
            context.get("decision_bar_time"),
            report_fields.get("decision_bar_time"),
            metadata.get("decision_bar_time"),
        )
        return {
            "trade_id": trade_id,
            "signal_time": signal_time,
            "decision_bar_time": decision_bar_time,
            "entry_execution_time": context.get("entry_execution_time"),
            "entry_mode": context.get("entry_mode"),
            "swept_level_name": _first_present(
                report_fields.get("swept_level_name"),
                report_fields.get("market_level_type"),
                getattr(signal, "level_type", None),
            ),
            "swept_level_price": _float_or_none(
                _first_present(
                    report_fields.get("swept_level_price"),
                    report_fields.get("market_level_price"),
                    getattr(signal, "swept_level", None),
                )
            ),
            "sweep_time": sweep_time,
            "reclaim_time": reclaim_time,
            "reclaim_window_bars": _int_or_none(
                _first_present(report_fields.get("reclaim_window_bars"), metadata.get("reclaim_window_bars"))
            ),
            "sweep_bar_open": _float_or_none(_first_present(report_fields.get("sweep_bar_open"), sweep_source_row.get("open"))),
            "sweep_bar_high": _float_or_none(
                _first_present(report_fields.get("sweep_bar_high"), getattr(signal, "sweep_high", None), sweep_source_row.get("high"))
            ),
            "sweep_bar_low": _float_or_none(
                _first_present(report_fields.get("sweep_bar_low"), getattr(signal, "sweep_low", None), sweep_source_row.get("low"))
            ),
            "sweep_bar_close": _float_or_none(_first_present(report_fields.get("sweep_bar_close"), sweep_source_row.get("close"))),
            "sweep_bar_volume": _float_or_none(
                _first_present(report_fields.get("sweep_bar_volume"), sweep_source_row.get("volume"))
            ),
            "avg_volume_reference": _float_or_none(
                _first_present(
                    report_fields.get("avg_volume_reference"),
                    report_fields.get("rolling_volume"),
                    metadata.get("avg_volume_reference"),
                    metadata.get("rolling_volume"),
                )
            ),
            "volume_filter_pass": _bool_or_none(_first_present(report_fields.get("volume_filter_pass"), metadata.get("volume_filter_pass"))),
            "delta_value": _float_or_none(
                _first_present(
                    report_fields.get("delta_value"),
                    report_fields.get("signed_volume"),
                    report_fields.get("absorption_bucket_delta"),
                    metadata.get("delta_value"),
                    metadata.get("signed_volume"),
                    _series_value(bar, "signed_volume"),
                )
            ),
            "delta_pct": _float_or_none(
                _first_present(
                    report_fields.get("delta_pct"),
                    report_fields.get("delta_imbalance"),
                    metadata.get("delta_pct"),
                    metadata.get("delta_imbalance"),
                )
            ),
            "delta_filter_pass": _bool_or_none(_first_present(report_fields.get("delta_filter_pass"), metadata.get("delta_filter_pass"))),
            "bid_volume": _float_or_none(_first_present(report_fields.get("bid_volume"), report_fields.get("sell_volume"), _series_value(bar, "sell_volume"))),
            "ask_volume": _float_or_none(_first_present(report_fields.get("ask_volume"), report_fields.get("buy_volume"), _series_value(bar, "buy_volume"))),
            "total_volume": _float_or_none(_first_present(report_fields.get("total_volume"), report_fields.get("volume"), _series_value(bar, "volume"))),
            "cumulative_delta": _float_or_none(_first_present(report_fields.get("cumulative_delta"), _series_value(bar, "cumulative_delta"))),
            "imbalance_count": _float_or_none(
                _first_present(
                    report_fields.get("imbalance_count"),
                    report_fields.get("footprint_buy_imbalance_count"),
                    report_fields.get("footprint_sell_imbalance_count"),
                    _series_value(bar, "footprint_buy_imbalance_count"),
                    _series_value(bar, "footprint_sell_imbalance_count"),
                )
            ),
            "stacked_imbalance_pass": _bool_or_none(
                _first_present(report_fields.get("stacked_imbalance_pass"), metadata.get("stacked_imbalance_pass"))
            ),
            "close_location_metric": _float_or_none(
                _first_present(report_fields.get("close_location_metric"), metadata.get("close_location_metric"))
            ),
            "rth_filter_pass": _bool_or_none(_first_present(report_fields.get("rth_filter_pass"), _series_value(bar, "is_rth"))),
            "no_trade_window_filter_pass": _bool_or_none(context.get("no_trade_window_filter_pass")),
            "max_trades_filter_pass": _bool_or_none(context.get("max_trades_filter_pass")),
            "final_entry_pass": True,
            "reason_if_rejected": None,
            "entry_trigger_values": _json_text(trigger_values),
            "filter_pass_values": _json_text(_validation_filter_values(report_fields, metadata, bar)),
            "raw_orderflow_values": _json_text(_validation_orderflow_values(report_fields, metadata, bar)),
            "signal_metadata": _json_text(metadata),
            "signal_report_fields": _json_text(report_fields),
            "decision_context": _json_text(context),
            "stop_anchor_calculation": _json_text(
                {
                    "module": strategy.sl.name,
                    "params": getattr(strategy.sl, "params", {}),
                    "entry_price": entry,
                    "computed_stop_price": stop,
                    "risk_points": risk_points,
                    "tick_size": tick_size,
                    "signal_stop_price": metadata.get("signal_stop_price"),
                    "sweep_high": getattr(signal, "sweep_high", None),
                    "sweep_low": getattr(signal, "sweep_low", None),
                }
            ),
            "target_calculation": _json_text(
                {
                    "module": strategy.tp.name,
                    "params": getattr(strategy.tp, "params", {}),
                    "entry_price": entry,
                    "stop_price": stop,
                    "computed_target_price": target,
                    "risk_points": risk_points,
                    "tick_size": tick_size,
                    "signal_target_price": metadata.get("signal_target_price"),
                }
            ),
        }

    def _validation_exit_audit(
        self,
        trade: dict,
        bar: pd.Series,
        raw_exit: float | None,
        audit: dict,
        tick_size: float,
    ) -> dict:
        reason = str(trade.get("exit_reason"))
        forced_reason = reason if reason in {"forced_apex_flatten", "eod_flatten"} or reason.endswith("_flatten") else None
        return {
            "trade_id": trade.get("trade_id"),
            "entry_time": trade.get("entry_timestamp"),
            "entry_price": _float_or_none(trade.get("entry_price")),
            "stop_price": _float_or_none(trade.get("stop_price")),
            "target_price": _float_or_none(trade.get("target_price")),
            "exit_time": trade.get("exit_timestamp"),
            "exit_price": _float_or_none(trade.get("exit_price")),
            "exit_reason": reason,
            "first_touch_tp_time": audit.get("first_touch_tp_time"),
            "first_touch_sl_time": audit.get("first_touch_sl_time"),
            "first_touch_tp_price": audit.get("first_touch_tp_price"),
            "first_touch_sl_price": audit.get("first_touch_sl_price"),
            "first_touch_decision": audit.get("first_touch_decision"),
            "first_touch_exit_decision": audit.get("first_touch_exit_decision") or reason,
            "same_bar_ambiguous": audit.get("same_bar_ambiguous"),
            "ambiguity_resolution": audit.get("ambiguity_resolution"),
            "forced_flatten_reason": forced_reason,
            "exit_bar_timestamp": bar["timestamp"],
            "exit_bar_open": _float_or_none(_series_value(bar, "open")),
            "exit_bar_high": _float_or_none(_series_value(bar, "high")),
            "exit_bar_low": _float_or_none(_series_value(bar, "low")),
            "exit_bar_close": _float_or_none(_series_value(bar, "close")),
            "raw_exit_price": _float_or_none(raw_exit),
            "tp_hit_on_exit_bar": audit.get("tp_hit_on_exit_bar"),
            "sl_hit_on_exit_bar": audit.get("sl_hit_on_exit_bar"),
            "max_favorable_excursion_ticks": _points_to_ticks(trade.get("max_favorable_excursion"), tick_size),
            "max_adverse_excursion_ticks": _points_to_ticks(trade.get("max_adverse_excursion"), tick_size),
            "mfe_ticks": _points_to_ticks(trade.get("max_favorable_excursion"), tick_size),
            "mae_ticks": _points_to_ticks(trade.get("max_adverse_excursion"), tick_size),
            "highest_price_before_exit": audit.get("highest_price_before_exit"),
            "lowest_price_before_exit": audit.get("lowest_price_before_exit"),
            "max_price_before_exit": audit.get("highest_price_before_exit"),
            "min_price_before_exit": audit.get("lowest_price_before_exit"),
            "tick_count_checked": audit.get("tick_count_checked"),
            "path_source": audit.get("path_source"),
            "engine_exit_decision": audit.get("engine_exit_decision"),
            "engine_exit_matches_path": audit.get("engine_exit_matches_path"),
            "warning_flags": audit.get("warning_flags"),
        }

    def _validation_frames(
        self,
        data: pd.DataFrame,
        detail_data: pd.DataFrame | None,
        trades: pd.DataFrame,
        condition_rows: list[dict],
        exit_rows: list[dict],
        trade_contexts: dict[int, dict],
        bar_delta: pd.Timedelta,
    ) -> dict[str, pd.DataFrame]:
        selected_trade_ids = _validation_selected_trade_ids(trades, self.validation_export.max_trades)
        bar_windows = self._validation_bar_windows(data, trades, trade_contexts, selected_trade_ids)
        tick_windows = self._validation_tick_windows(
            data,
            detail_data,
            trades,
            trade_contexts,
            selected_trade_ids,
            bar_delta,
        )
        exit_audits = enrich_exit_audits(
            trades,
            normalize_columns(pd.DataFrame(exit_rows), EXIT_AUDIT_COLUMNS),
            tick_windows,
            tick_size=float(self.core_config.get("tick_size", 0.25)),
        )
        return {
            "condition_snapshots": normalize_columns(pd.DataFrame(condition_rows), CONDITION_SNAPSHOT_COLUMNS),
            "exit_audits": exit_audits,
            "bar_windows": bar_windows,
            "tick_windows": tick_windows,
        }

    def _validation_bar_windows(
        self,
        data: pd.DataFrame,
        trades: pd.DataFrame,
        trade_contexts: dict[int, dict],
        selected_trade_ids: set,
    ) -> pd.DataFrame:
        frames = []
        for _, trade in trades.iterrows():
            trade_id = trade["trade_id"]
            if trade_id not in selected_trade_ids:
                continue
            context = trade_contexts.get(int(trade_id), {})
            start_index, end_index = _validation_window_indices(
                context,
                len(data),
                self.validation_export.window_bars_before,
                self.validation_export.window_bars_after,
            )
            if start_index is None:
                continue
            frames.append(build_bar_window_rows(data.iloc[start_index : end_index + 1], trade_id=trade_id))
        if not frames:
            return build_bar_window_rows(pd.DataFrame(), trade_id=None)
        return pd.concat(frames, ignore_index=True)

    def _validation_tick_windows(
        self,
        data: pd.DataFrame,
        detail_data: pd.DataFrame | None,
        trades: pd.DataFrame,
        trade_contexts: dict[int, dict],
        selected_trade_ids: set,
        bar_delta: pd.Timedelta,
    ) -> pd.DataFrame:
        if detail_data is None or detail_data.empty:
            return build_tick_window_rows(pd.DataFrame(), trade_id=None)
        frames = []
        detail_timestamps = pd.to_datetime(detail_data["timestamp"]).reset_index(drop=True)
        for _, trade in trades.iterrows():
            trade_id = trade["trade_id"]
            if trade_id not in selected_trade_ids:
                continue
            context = trade_contexts.get(int(trade_id), {})
            start_index, end_index = _validation_window_indices(
                context,
                len(data),
                self.validation_export.window_bars_before,
                self.validation_export.window_bars_after,
            )
            if start_index is None:
                continue
            start_ts = pd.Timestamp(data.iloc[start_index]["timestamp"])
            end_ts = pd.Timestamp(data.iloc[end_index]["timestamp"]) + bar_delta
            left = int(detail_timestamps.searchsorted(start_ts, side="left"))
            right = int(detail_timestamps.searchsorted(end_ts, side="left"))
            frames.append(build_tick_window_rows(detail_data.iloc[left:right], trade_id=trade_id))
        if not frames:
            return build_tick_window_rows(pd.DataFrame(), trade_id=None)
        return pd.concat(frames, ignore_index=True)

    def _preflight(
        self,
        data: pd.DataFrame,
        detail_data: pd.DataFrame | None,
        data_contract: dict[str, Any],
        detail_contract: dict[str, Any] | None,
    ) -> dict:
        required = {"timestamp", "session_date", "open", "high", "low", "close"}
        missing = required - set(data.columns)
        if missing:
            raise ValueError(f"Backtest data is missing required column(s): {sorted(missing)}.")

        diagnostics = {
            "preflight": {
                "rows": int(len(data)),
                "timeframe_minutes": float(self.timeframe_minutes),
                "warnings": [],
                "required_columns": sorted(required),
                "engine_contract_version": ENGINE_CONTRACT_VERSION,
                "data_contract": data_contract,
                "detail_data_contract": detail_contract,
                "execution_assumptions": self.execution_assumptions.as_dict(),
            },
            "signals_generated": 0,
            "entries_opened": 0,
            "trades_closed": 0,
            "rejects": {
                "missing_stop": 0,
                "missing_intrabar_entry_price": 0,
                "target_already_reached": 0,
                "position_sizing": 0,
                "daily_risk_lockout": 0,
                "apex_latest_entry_time": 0,
                "event_no_trade_window": 0,
            },
            "exits": {},
            "intrabar_entries_requested": 0,
            "intrabar_signals_generated": 0,
            "stop_target_conflicts": 0,
            "detail_conflicts_resolved": 0,
            "detail_conflicts_unresolved": 0,
            "intrabar_first_detail_targets_suppressed": 0,
            "dynamic_stop_updates": 0,
            "gap_stop_fills": 0,
            "apex": self._apex_diagnostics(),
            "event_filters": self._event_filter_diagnostics(),
        }
        self._validate_strategy_feature_columns(data, diagnostics)
        self._validate_timeframe_column(data, diagnostics)
        self._validate_detail_data_coverage(data, detail_data, diagnostics)
        return diagnostics

    def _validate_strategy_feature_columns(self, data: pd.DataFrame, diagnostics: dict) -> None:
        module = str(self.strategy_config.get("entry", {}).get("module", ""))
        try:
            metadata_required = set(entry_module_metadata(module).required_columns)
        except ValueError:
            metadata_required = set()
        if metadata_required:
            missing = metadata_required - set(data.columns)
            if missing:
                raise ValueError(
                    f"Strategy entry module {module!r} requires missing feature column(s): {sorted(missing)}."
                )
        required_by_module = {
            "amihud_illiquidity_state": {"is_rth"},
            "bls_macro_release_day_drift": {"is_rth"},
            "calendar_session_bias": {"is_rth"},
            "cftc_tff_hedging_pressure": {"is_rth"},
            "cftc_tff_tiered_hedging_pressure": {"is_rth"},
            "connors_rsi2_mean_reversion": {"is_rth"},
            "daily_bollinger_environment": {"is_rth"},
            "fifty_two_week_anchor_momentum": {"is_rth"},
            "weekly_stage_analysis": {"is_rth"},
            "daily_time_series_momentum": {"is_rth"},
            "daily_short_term_reversal": {"is_rth"},
            "turnaround_tuesday_reversal": {"is_rth"},
            "nq_nikkei225_close_spillover": {"is_rth"},
            "daily_reversal_orderflow_confirmation": {
                "is_rth",
                "trade_orderflow_imbalance_12",
                "trade_orderflow_imbalance_18",
                "trade_orderflow_imbalance_24",
                "trade_orderflow_imbalance_30",
                "trade_orderflow_volume_12",
                "trade_orderflow_volume_18",
                "trade_orderflow_volume_24",
                "trade_orderflow_volume_30",
            },
            "es_term_structure_lead_lag": {"is_rth"},
            "fomc_pre_announcement_drift": {"is_rth"},
            "macro_event_amd_distribution": {"is_rth"},
            "session_liquidity_fvg_reversal": {"is_rth"},
            "pdh_pdl_sweep_reclaim": {"is_rth", "prev_rth_low", "prev_rth_high"},
            "pdh_pdl_vap_absorption_sweep": {
                "is_rth",
                "prev_rth_low",
                "prev_rth_high",
                "intrabar_short_release_price",
                "intrabar_short_release_offset_seconds",
                "intrabar_short_delta",
                "intrabar_short_session_open",
                "intrabar_short_session_high",
                "intrabar_short_session_low",
                "intrabar_short_session_range_pct",
                "intrabar_short_vap_poc",
                "intrabar_short_vap_vah",
                "intrabar_short_vap_val",
                "intrabar_short_vap_no_lvn_between_value_area",
                "intrabar_long_release_price",
                "intrabar_long_release_offset_seconds",
                "intrabar_long_delta",
                "intrabar_long_session_open",
                "intrabar_long_session_high",
                "intrabar_long_session_low",
                "intrabar_long_session_range_pct",
                "intrabar_long_vap_poc",
                "intrabar_long_vap_vah",
                "intrabar_long_vap_val",
                "intrabar_long_vap_no_lvn_between_value_area",
            },
            "trend_orderflow_pdh_pdl_sweep_reclaim": {
                "is_rth",
                "prev_rth_low",
                "prev_rth_high",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "rolling_stat_envelope_orderflow_reversion": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "opening_range_breakout": {"is_rth"},
            "opening_drive_inventory_combo": {
                "is_rth",
                "signed_volume",
                "trade_orderflow_return_ticks_30",
                "trade_orderflow_return_ticks_60",
                "trade_orderflow_imbalance_30",
                "trade_orderflow_imbalance_60",
                "trade_orderflow_volume_30",
                "trade_orderflow_volume_60",
            },
            "opening_gap_orderflow_fade": {
                "is_rth",
                "prev_rth_close",
                "signed_volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "opening_gap_orderflow_continuation": {
                "is_rth",
                "prev_rth_close",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "opening_range_filtered_breakout": {"is_rth", "vwap", "volume_ratio"},
            "opening_range_failed_breakout_orderflow": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "opening_range_inverse_breakout": {"is_rth"},
            "opening_range_orderflow_breakout": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "opening_range_trend_orderflow_breakout": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "opening_range_nq_orderflow_breakout": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
                "es_return_bps_5",
                "nq_return_bps_5",
                "es_return_bps_15",
                "nq_return_bps_15",
                "es_return_bps_30",
                "nq_return_bps_30",
                "es_return_bps_60",
                "nq_return_bps_60",
            },
            "opening_range_retest_orderflow": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "orderflow_recent_pocket_combo": {
                "is_rth",
                "of_combo_signal_sc_short_1130_loose",
                "of_combo_signal_multi_short_1130",
                "of_combo_signal_late_vwap_short_1330",
                "of_combo_signal_late_flow_long_1500",
            },
            "intraday_capitulation_mr": {"is_rth", "vwap"},
            "intraday_momentum_priority": {"is_rth"},
            "intraday_range_orderflow_breakout": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "intraday_invariance_dislocation_reversion": {
                "is_rth",
                "signed_volume",
                "volume",
                "trades",
            },
            "pdh_pdl_orderflow_breakout_continuation": {
                "is_rth",
                "prev_rth_high",
                "prev_rth_low",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "pdh_pdl_trend_orderflow_breakout_continuation": {
                "is_rth",
                "prev_rth_high",
                "prev_rth_low",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "rolling_range_orderflow_sweep_reversal": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "session_extreme_delta_divergence": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "session_open_orderflow_reclaim": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "sector_rotation_risk_appetite": {"is_rth"},
            "sector_rotation_orderflow_pullback": {
                "is_rth",
                "vwap",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "gao_last_half_hour_orderflow": {"is_rth", "signed_volume", "large20_signed_volume", "large20_volume"},
            "impulse_pause_orderflow_continuation": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "import_export_price_pressure": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "halloween_seasonal_premium": {"is_rth"},
            "late_day_intraday_momentum": {"is_rth", "prev_rth_close", "volume_ratio"},
            "leveraged_etf_rebalance_pressure": {"is_rth", "prev_rth_close"},
            "liquidity_risk_capacity_priority": {"is_rth"},
            "market_plumbing_priority": {"is_rth"},
            "market_structure_pivot_continuation": {"is_rth"},
            "measured_move_pullback_continuation": {"is_rth"},
            "market_structure_filtered_entry": {
                "is_rth",
                "vwap",
                "volume",
                "signed_volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
                "mes_participation_share_30_rank252",
                "mes_participation_share_60_rank252",
                "mes_trade_share_60_rank252",
                "es_return_ticks_30",
                "es_return_ticks_60",
            },
            "mes_participation_crowding": {
                "is_rth",
                "mes_participation_share_30_rank252",
                "mes_participation_share_60_rank252",
                "mes_trade_share_60_rank252",
                "es_return_ticks_30",
                "es_return_ticks_60",
                "nq_return_ticks_30",
                "nq_return_ticks_60",
            },
            "volatility_filtered_trend_mes_participation_crowding": {
                "is_rth",
                "mes_participation_share_15_rank252",
                "mes_participation_share_30_rank252",
                "mes_participation_share_60_rank252",
                "mes_trade_share_15_rank252",
                "mes_trade_share_30_rank252",
                "mes_trade_share_60_rank252",
                "es_return_ticks_15",
                "es_return_ticks_30",
                "es_return_ticks_60",
            },
            "semivariance_filtered_trend_mes_participation_crowding": {
                "is_rth",
                "mes_participation_share_15_rank252",
                "mes_participation_share_30_rank252",
                "mes_participation_share_60_rank252",
                "mes_trade_share_15_rank252",
                "mes_trade_share_30_rank252",
                "mes_trade_share_60_rank252",
                "es_return_ticks_15",
                "es_return_ticks_30",
                "es_return_ticks_60",
                "nq_return_ticks_15",
                "nq_return_ticks_30",
                "nq_return_ticks_60",
            },
            "mes_footprint_liquidity_sweep_reversion": {
                "is_rth",
                "footprint_absorption_long",
                "footprint_absorption_short",
                "footprint_max_sell_imbalance_volume",
                "footprint_max_buy_imbalance_volume",
                "footprint_highest_sell_imbalance_price",
                "footprint_lowest_buy_imbalance_price",
                "mes_participation_share_15_rank252",
                "mes_participation_share_30_rank252",
                "mes_trade_share_15_rank252",
                "mes_trade_share_30_rank252",
                "mes_trade_orderflow_imbalance_15",
                "mes_trade_orderflow_imbalance_30",
                "mes_trade_orderflow_large10_imbalance_15",
                "mes_trade_orderflow_large10_imbalance_30",
            },
            "opening_drive_mes_crowding_reversal": {
                "is_rth",
                "mes_participation_share_15",
                "mes_participation_share_15_rank252",
                "mes_participation_share_30",
                "mes_participation_share_30_rank252",
                "mes_participation_share_60",
                "mes_participation_share_60_rank252",
                "mes_trade_share_15",
                "mes_trade_share_15_rank252",
                "mes_trade_share_30",
                "mes_trade_share_30_rank252",
                "mes_trade_share_60",
                "mes_trade_share_60_rank252",
            },
            "ema_pullback_orderflow_continuation": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "es_nq_relative_value_orderflow_absorption_reversion": {
                "is_rth",
                "es_return_bps_15",
                "nq_return_bps_15",
                "nq_minus_es_return_bps_15",
                "es_signed_imbalance_15",
                "es_return_bps_30",
                "nq_return_bps_30",
                "nq_minus_es_return_bps_30",
                "es_signed_imbalance_30",
                "es_return_bps_60",
                "nq_return_bps_60",
                "nq_minus_es_return_bps_60",
                "es_signed_imbalance_60",
            },
            "nq_es_lead_lag": {
                "is_rth",
                "es_return_bps_5",
                "nq_return_bps_5",
                "es_return_bps_15",
                "nq_return_bps_15",
                "es_return_bps_30",
                "nq_return_bps_30",
                "es_return_bps_60",
                "nq_return_bps_60",
            },
            "es_mes_aligned_flow_continuation": {
                "is_rth",
                "es_trade_orderflow_return_ticks_15",
                "es_trade_orderflow_return_ticks_30",
                "es_trade_orderflow_return_ticks_60",
                "mes_trade_orderflow_imbalance_15",
                "mes_trade_orderflow_imbalance_30",
                "mes_trade_orderflow_imbalance_60",
                "mes_trade_orderflow_large10_imbalance_15",
                "mes_trade_orderflow_large10_imbalance_30",
                "mes_trade_orderflow_large10_imbalance_60",
                "mes_trade_orderflow_large20_imbalance_15",
                "mes_trade_orderflow_large20_imbalance_30",
                "mes_trade_orderflow_large20_imbalance_60",
            },
            "footprint_absorption_initiation": {
                "is_rth",
                "prev_rth_high",
                "prev_rth_low",
                "footprint_absorption_long",
                "footprint_absorption_short",
                "footprint_max_sell_imbalance_volume",
                "footprint_max_buy_imbalance_volume",
                "footprint_highest_sell_imbalance_price",
                "footprint_lowest_buy_imbalance_price",
            },
            "monthly_opex_pressure": {"is_rth"},
            "morning_intraday_momentum": {"is_rth", "volume_ratio"},
            "morning_orderflow_momentum": {"is_rth", "signed_volume", "large20_signed_volume", "large20_volume"},
            "nq_tech_relative_strength": {"is_rth"},
            "nq_small_cap_relative_rotation": {"is_rth"},
            "nq_europe_equity_close_spillover": {"is_rth"},
            "nq_btc_crypto_risk_sentiment": {"is_rth"},
            "nq_copper_growth_risk_sentiment": {"is_rth"},
            "nq_semiconductor_leadership": {"is_rth"},
            "nq_taiwan_semiconductor_spillover": {"is_rth"},
            "nq_china_tech_risk_sentiment": {"is_rth"},
            "nq_industrial_production_state": {"is_rth"},
            "nq_retail_inventory_demand": {"is_rth"},
            "nq_manufacturing_orders_state": {"is_rth"},
            "nq_jobless_claims_state": {"is_rth"},
            "nq_housing_construction_state": {"is_rth"},
            "nq_inflation_pressure_state": {"is_rth"},
            "nq_labor_market_slack_state": {"is_rth"},
            "nq_productivity_unit_labor_cost_state": {"is_rth"},
            "nq_consumer_credit_state": {"is_rth"},
            "nq_corporate_profitability_state": {"is_rth"},
            "nq_credit_quality_stress_state": {"is_rth"},
            "nq_bank_credit_supply_state": {"is_rth"},
            "nq_sloos_bank_lending_survey_state": {"is_rth"},
            "nq_trade_balance_quantity_state": {"is_rth"},
            "nq_fiscal_deficit_treasury_supply_state": {"is_rth"},
            "morning_trend_lunch_reversal_orderflow": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "overnight_intraday_reversal": {"is_rth", "prev_rth_close"},
            "overnight_drift": {"is_eth", "session_label", "prev_rth_open", "prev_rth_close"},
            "overnight_return_late_day_momentum": {"is_rth", "prev_rth_close"},
            "overnight_inventory_reversion": {"is_rth", "overnight_high", "overnight_low", "vwap"},
            "overnight_range_orderflow_breakout": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "pdh_pdl_breakout_continuation": {"is_rth", "prev_rth_high", "prev_rth_low", "volume_ratio"},
            "positive_delta_dislocation": {
                "is_rth",
                "prev_rth_high",
                "trade_orderflow_return_points_60",
                "trade_orderflow_signed_volume_60",
                "trade_orderflow_volume_60",
            },
            "preholiday_effect": {"is_rth"},
            "prior_session_ibs_reversion": {"is_rth", "prev_rth_high", "prev_rth_low", "prev_rth_close"},
            "prior_session_benchmark_orderflow_reaction": {
                "is_rth",
                "prev_rth_open",
                "prev_rth_close",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "prior_value_area_orderflow_acceptance": {
                "is_rth",
                "volume",
                "signed_volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "trend_filtered_prior_value_area_acceptance": {
                "is_rth",
                "volume",
                "signed_volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "prior_value_area_orderflow_rejection": {
                "is_rth",
                "volume",
                "signed_volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "prior_poc_orderflow_magnet": {
                "is_rth",
                "volume",
                "signed_volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "prior_lvn_orderflow_rejection": {
                "is_rth",
                "volume",
                "signed_volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "price_ending_barrier": {"is_rth"},
            "quarterly_expiration_pressure": {"is_rth"},
            "range_compression_breakout": {"is_rth"},
            "range_compression_orderflow_breakout": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "gold_platinum_ratio_state": {"is_rth"},
            "realized_semivariance_asymmetry": {"is_rth"},
            "realized_semivariance_orderflow_confirmation": {
                "is_rth",
                "trade_orderflow_imbalance_6",
                "trade_orderflow_imbalance_12",
                "trade_orderflow_imbalance_18",
                "trade_orderflow_large10_imbalance_6",
                "trade_orderflow_large10_imbalance_12",
                "trade_orderflow_large10_imbalance_18",
            },
            "realized_skewness_reversal": {"is_rth"},
            "max_daily_return_lottery_reversal": {"is_rth"},
            "real_yield_breakeven_state": {"is_rth"},
            "move_treasury_vol_state": {"is_rth"},
            "realized_vol_of_vol_state": {"is_rth"},
            "round_number_barrier": {"is_rth"},
            "round_number_orderflow_barrier": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "rth_gap_fade": {"is_rth", "prev_rth_close", "vwap"},
            "turn_of_month_bias": {"is_rth"},
            "trade_orderflow_multi_pressure": {"is_rth"},
            "trade_orderflow_pressure": {"is_rth"},
            "trend_aligned_orderflow_continuation": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "trade_fragmentation_liquidity_reversion": {"is_rth"},
            "trade_size_segment_orderflow": {"is_rth"},
            "turn_of_year_effect": {"is_rth"},
            "variance_risk_premium_intraday": {"is_rth"},
            "variance_ratio_orderflow_regime": {
                "is_rth",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "vix_expiration_pressure": {"is_rth"},
            "volatility_managed_intraday_premium": {"is_rth"},
            "volume_conditioned_liquidity_reversal": {"is_rth", "volume_ratio"},
            "wide_range_orderflow_continuation": {
                "is_rth",
                "volume_ratio",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "vpin_toxicity_continuation": {
                "is_rth",
                "vpin_prior_rank21_at_1330",
                "vpin_prior_drawdown_rank63_at_1330",
                "vpin_session_ret",
            },
            "vwap_orderflow_pullback_continuation": {
                "is_rth",
                "vwap",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "vwap_deviation_orderflow_reversion": {
                "is_rth",
                "vwap",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "vix_term_structure_orderflow_pullback": {
                "is_rth",
                "vwap",
                "signed_volume",
                "volume",
                "large10_signed_volume",
                "large10_volume",
                "large20_signed_volume",
                "large20_volume",
            },
            "vwap_pullback_continuation": {"is_rth", "vwap"},
            "yush_range_1": {
                "is_rth",
                "prev_rth_high",
                "prev_rth_low",
                "prev_rth_close",
                "overnight_high",
                "overnight_low",
            },
        }
        required = set(required_by_module.get(module, set()))
        if module == "connors_rsi2_mean_reversion":
            params = self.strategy_config.get("entry", {}).get("params", {})
            trend_filter = str(params.get("trend_filter", "ma")).lower()
            min_vwap_extension_ticks = float(params.get("min_vwap_extension_ticks", 0.0) or 0.0)
            if trend_filter in {"vwap", "ma_and_vwap"} or min_vwap_extension_ticks > 0:
                required.add("vwap")
        missing = sorted(required - set(data.columns))
        if missing:
            diagnostics["preflight"]["warnings"].append(
                f"Entry module {module} is missing optional/strategy feature column(s): {missing}."
            )

    def _validate_timeframe_column(self, data: pd.DataFrame, diagnostics: dict) -> None:
        if "timeframe_minutes" not in data.columns or data.empty:
            return
        actual = pd.to_numeric(data["timeframe_minutes"], errors="coerce").dropna().unique()
        expected = float(self.timeframe_minutes)
        if len(actual) and any(not math.isclose(float(value), expected) for value in actual):
            diagnostics["preflight"]["warnings"].append(
                f"Data timeframe_minutes values {sorted(float(value) for value in actual)} do not match config {expected:g}."
            )

    def _validate_detail_data_coverage(
        self,
        data: pd.DataFrame,
        detail_data: pd.DataFrame | None,
        diagnostics: dict,
    ) -> None:
        if self.timeframe_minutes <= 1:
            return
        if detail_data is None or detail_data.empty:
            diagnostics["preflight"]["warnings"].append(
                "Higher-timeframe run has no detail_data; same-bar stop/target conflicts will use stop-first fallback."
            )
            return
        required = {"timestamp", "open", "high", "low", "close"}
        missing = required - set(detail_data.columns)
        if missing:
            raise ValueError(f"Backtest detail_data is missing required column(s): {sorted(missing)}.")
        if data.empty:
            return
        first = pd.Timestamp(data["timestamp"].min())
        last = pd.Timestamp(data["timestamp"].max()) + pd.Timedelta(minutes=self.timeframe_minutes)
        detail_first = pd.Timestamp(detail_data["timestamp"].min())
        detail_last = pd.Timestamp(detail_data["timestamp"].max())
        detail_granularity = _detail_granularity(detail_data)
        coverage_buffer = pd.Timedelta(minutes=1) if detail_granularity == "minute_bar" else pd.Timedelta(0)
        if detail_first > first or detail_last < last - coverage_buffer:
            diagnostics["preflight"]["warnings"].append(
                "detail_data does not fully cover the higher-timeframe backtest span."
            )

    def _configured_bar_interval_minutes(self) -> float:
        timeframe_minutes = config_timeframe_minutes(self.config, required=False)
        if timeframe_minutes is not None:
            return float(timeframe_minutes)
        entry_params = (self.config.get("strategy", {}).get("entry", {}) or {}).get("params", {})
        return float(entry_params.get("bar_interval_minutes", 1))

    def _apply_timeframe_to_strategy(self) -> None:
        entry = self.strategy_config.setdefault("entry", {})
        params = entry.setdefault("params", {})
        self._validate_or_set_timeframe_param(params, "bar_interval_minutes")
        if "timeframe_minutes" in params:
            self._validate_or_set_timeframe_param(params, "timeframe_minutes")

    def _validate_or_set_timeframe_param(self, params: dict, key: str) -> None:
        if key not in params:
            params[key] = self.timeframe_minutes
            return
        configured = float(params[key])
        if not math.isclose(configured, self.timeframe_minutes):
            raise ValueError(
                f"strategy.entry.params.{key} ({configured:g}) must match variant timeframe "
                f"({self.timeframe_minutes:g} minutes)."
            )

    def _resolve_stop_target_exit(
        self,
        bar: pd.Series,
        direction: str,
        stop_price: float,
        target_price: float,
        bar_close_timestamp: pd.Timestamp,
        detail_data: pd.DataFrame | None,
        diagnostics: dict,
        start_timestamp: pd.Timestamp | None = None,
        suppress_first_detail_target: bool = False,
        allow_open_gap_fill: bool = False,
        audit: dict | None = None,
    ) -> tuple[str | None, float | None, pd.Timestamp]:
        exit_timestamp = bar["timestamp"]
        start = pd.Timestamp(start_timestamp) if start_timestamp is not None else pd.Timestamp(bar["timestamp"])
        bar_start = pd.Timestamp(bar["timestamp"])
        stop_hit, target_hit = _stop_target_hits(bar, direction, stop_price, target_price)
        if audit is not None:
            audit.update(
                _validation_stop_target_audit(
                    bar,
                    detail_data,
                    direction,
                    stop_price,
                    target_price,
                    start,
                    bar_close_timestamp,
                    suppress_first_detail_target=suppress_first_detail_target,
                )
            )
        if start > bar_start:
            if stop_hit and target_hit:
                diagnostics["stop_target_conflicts"] += 1
            if detail_data is not None and not detail_data.empty:
                detail_exit = _resolve_detail_stop_target(
                    detail_data,
                    start,
                    bar_close_timestamp,
                    direction,
                    stop_price,
                    target_price,
                    suppress_first_detail_target=suppress_first_detail_target,
                    allow_open_gap_fill=allow_open_gap_fill,
                    diagnostics=diagnostics,
                )
                if detail_exit is not None:
                    if stop_hit and target_hit:
                        diagnostics["detail_conflicts_resolved"] += 1
                    if audit is not None:
                        audit["first_touch_exit_decision"] = detail_exit[0]
                        audit["ambiguity_resolution"] = "detail_data" if stop_hit and target_hit else None
                    return detail_exit
                if stop_hit and target_hit:
                    diagnostics["detail_conflicts_unresolved"] += 1
                    if audit is not None:
                        audit["ambiguity_resolution"] = "detail_data_unresolved"
                return None, None, exit_timestamp
            if stop_hit:
                if stop_hit and target_hit:
                    diagnostics["detail_conflicts_unresolved"] += 1
                    if audit is not None:
                        audit["ambiguity_resolution"] = "post_entry_no_detail_stop_first"
                if audit is not None:
                    audit["first_touch_exit_decision"] = "stop"
                return "stop", stop_price, start
            if target_hit:
                diagnostics["intrabar_first_detail_targets_suppressed"] += 1
            return None, None, exit_timestamp
        if (stop_hit or target_hit) and detail_data is not None and not detail_data.empty:
            detail_exit = _resolve_detail_stop_target(
                detail_data,
                start,
                bar_close_timestamp,
                direction,
                stop_price,
                target_price,
                suppress_first_detail_target=suppress_first_detail_target,
                allow_open_gap_fill=allow_open_gap_fill,
                diagnostics=diagnostics,
            )
            if detail_exit is not None:
                if stop_hit and target_hit:
                    diagnostics["stop_target_conflicts"] += 1
                    diagnostics["detail_conflicts_resolved"] += 1
                if audit is not None:
                    audit["first_touch_exit_decision"] = detail_exit[0]
                    audit["ambiguity_resolution"] = "detail_data" if stop_hit and target_hit else None
                return detail_exit
            if _detail_data_is_authoritative_execution_path(detail_data):
                if stop_hit and target_hit:
                    diagnostics["stop_target_conflicts"] += 1
                diagnostics["detail_conflicts_unresolved"] += 1
                if audit is not None and stop_hit and target_hit:
                    audit["ambiguity_resolution"] = "detail_data_unresolved"
                return None, None, exit_timestamp
        if stop_hit and target_hit:
            diagnostics["stop_target_conflicts"] += 1
            detail_exit = _resolve_detail_stop_target(
                detail_data,
                start,
                bar_close_timestamp,
                direction,
                stop_price,
                target_price,
                suppress_first_detail_target=suppress_first_detail_target,
                allow_open_gap_fill=allow_open_gap_fill,
                diagnostics=diagnostics,
            )
            if detail_exit is not None:
                diagnostics["detail_conflicts_resolved"] += 1
                if audit is not None:
                    audit["first_touch_exit_decision"] = detail_exit[0]
                    audit["ambiguity_resolution"] = "detail_data"
                return detail_exit
            diagnostics["detail_conflicts_unresolved"] += 1
            if audit is not None:
                audit["ambiguity_resolution"] = "pessimistic_stop_first"
        reason, raw_exit = stop_target_hit(
            bar,
            direction,
            stop_price,
            target_price,
            allow_open_gap_fill=allow_open_gap_fill,
        )
        if reason == "stop" and raw_exit != stop_price:
            diagnostics["gap_stop_fills"] = diagnostics.get("gap_stop_fills", 0) + 1
        if audit is not None and reason is not None:
            audit["first_touch_exit_decision"] = reason
            if stop_hit and target_hit and not audit.get("ambiguity_resolution"):
                audit["ambiguity_resolution"] = "pessimistic_stop_first"
        return reason, raw_exit, exit_timestamp

    def _maybe_update_dynamic_stop(
        self,
        opened: dict,
        bar: pd.Series,
        direction: str,
        detail_data: pd.DataFrame | None,
        start_timestamp: pd.Timestamp,
        end_timestamp: pd.Timestamp,
        diagnostics: dict,
    ) -> None:
        if bool(opened.get("dynamic_stop_activated", False)):
            return
        trigger = _float_or_none(opened.get("dynamic_stop_trigger_price"))
        new_stop = _float_or_none(opened.get("dynamic_stop_price"))
        if trigger is None or new_stop is None:
            return
        current_stop = _float_or_none(opened.get("stop_price"))
        target = _float_or_none(opened.get("target_price"))
        if current_stop is None or target is None:
            return
        if direction == "long":
            if new_stop <= current_stop:
                return
        elif new_stop >= current_stop:
            return

        if detail_data is not None and not detail_data.empty:
            mask = (detail_data["timestamp"] >= start_timestamp) & (detail_data["timestamp"] < end_timestamp)
            for _, detail_bar in detail_data.loc[mask].iterrows():
                stop_hit, target_hit = _stop_target_hits(detail_bar, direction, current_stop, target)
                trigger_hit = _dynamic_stop_trigger_hit(detail_bar, direction, trigger)
                if stop_hit:
                    return
                if trigger_hit:
                    opened["stop_price"] = new_stop
                    opened["dynamic_stop_activated"] = True
                    opened["dynamic_stop_activated_at"] = pd.Timestamp(detail_bar["timestamp"])
                    diagnostics["dynamic_stop_updates"] = diagnostics.get("dynamic_stop_updates", 0) + 1
                    return
                if target_hit:
                    return
            return

        stop_hit, target_hit = _stop_target_hits(bar, direction, current_stop, target)
        if stop_hit or target_hit:
            return
        if _dynamic_stop_trigger_hit(bar, direction, trigger):
            opened["stop_price"] = new_stop
            opened["dynamic_stop_activated"] = True
            opened["dynamic_stop_activated_at"] = end_timestamp
            diagnostics["dynamic_stop_updates"] = diagnostics.get("dynamic_stop_updates", 0) + 1

    def _apex_diagnostics(self) -> dict:
        rules = self.apex_rules
        return {
            "enabled": bool(rules.enabled),
            "timezone": rules.timezone,
            "latest_flat_time": _format_time(rules.latest_flat_time),
            "force_flatten_time": _format_time(rules.force_flatten_time),
            "latest_entry_time": _format_time(rules.latest_entry_time),
            "pending_orders_cancelled": 0,
            "pending_order_after_flatten_deadline": 0,
            "entry_after_latest_entry_time": 0,
            "exit_after_flatten_deadline": 0,
            "position_after_flatten_deadline": 0,
            "overnight_position_violations": 0,
            "forced_flatten_trades": 0,
            "rule_violations": 0,
        }

    def _apex_entry_allowed(self, timestamp) -> bool:
        rules = self.apex_rules
        if not rules.enabled:
            return True
        ts = self._apex_timestamp(timestamp)
        if rules.reject_if_entry_after_latest_entry_time and ts.time() > rules.latest_entry_time:
            return False
        if ts.time() > rules.latest_flat_time:
            return False
        return True

    def _record_apex_pending_cancel(self, diagnostics: dict, timestamp) -> None:
        if not self.apex_rules.enabled:
            return
        diagnostics["apex"]["pending_orders_cancelled"] += 1
        if not self.apex_rules.reject_if_pending_order_after_flatten_deadline:
            return
        ts = self._apex_timestamp(timestamp)
        if ts.time() > self.apex_rules.latest_flat_time:
            self._record_apex_violation(diagnostics, "pending_order_after_flatten_deadline")

    def _next_bar_close_timestamp(
        self,
        data: pd.DataFrame,
        current_index: int,
        bar_interval_minutes: float,
    ) -> pd.Timestamp | None:
        next_index = current_index + 1
        if next_index >= len(data):
            return None
        return pd.Timestamp(data.iloc[next_index]["timestamp"]) + pd.Timedelta(minutes=bar_interval_minutes)

    def _next_bar_entry_timestamp(self, data: pd.DataFrame, current_index: int) -> pd.Timestamp | None:
        next_index = current_index + 1
        if next_index >= len(data):
            return None
        return pd.Timestamp(data.iloc[next_index]["timestamp"])

    def _apex_should_force_flatten(self, bar_close_timestamp, next_bar_close_timestamp=None) -> bool:
        rules = self.apex_rules
        if not rules.enabled or not rules.force_flatten_enabled:
            return False
        close_ts = self._apex_timestamp(bar_close_timestamp)
        if close_ts.time() > rules.force_flatten_time:
            return False
        if next_bar_close_timestamp is None:
            return True
        next_close = self._apex_timestamp(next_bar_close_timestamp)
        return next_close.date() != close_ts.date() or next_close.time() > rules.force_flatten_time

    def _apex_trade_fields(self, trade: dict) -> dict:
        rules = self.apex_rules
        enabled = bool(rules.enabled)
        entry_ts = self._apex_timestamp(trade["entry_timestamp"])
        exit_ts = self._apex_timestamp(trade["exit_timestamp"])
        entry_before_latest = (not enabled) or (not rules.reject_if_entry_after_latest_entry_time) or (
            entry_ts.time() <= rules.latest_entry_time
        )
        exit_before_flatten = (not enabled) or (not rules.reject_if_position_after_flatten_deadline) or (
            exit_ts.time() <= rules.latest_flat_time
        )
        no_overnight_ok = (not enabled) or (not rules.no_overnight_positions) or (entry_ts.date() == exit_ts.date())
        position_flat_before_deadline = exit_before_flatten and no_overnight_ok
        violation = enabled and not (
            entry_before_latest
            and exit_before_flatten
            and no_overnight_ok
        )
        return {
            "apex_rules_enabled": enabled,
            "latest_flat_time": _format_time(rules.latest_flat_time),
            "force_flatten_time": _format_time(rules.force_flatten_time),
            "latest_entry_time": _format_time(rules.latest_entry_time),
            "was_forced_flatten": trade["exit_reason"] == "forced_apex_flatten",
            "position_flat_before_deadline": position_flat_before_deadline,
            "pending_orders_cancelled_before_deadline": True,
            "entry_before_latest_entry_time": entry_before_latest,
            "exit_before_flatten_deadline": exit_before_flatten,
            "apex_rule_violation": violation,
        }

    def _record_trade_apex_diagnostics(self, trade: dict, diagnostics: dict) -> None:
        if not self.apex_rules.enabled:
            return
        if trade.get("was_forced_flatten"):
            diagnostics["apex"]["forced_flatten_trades"] += 1
        if trade.get("entry_before_latest_entry_time") is False:
            self._record_apex_violation(diagnostics, "entry_after_latest_entry_time")
        if trade.get("exit_before_flatten_deadline") is False:
            self._record_apex_violation(diagnostics, "exit_after_flatten_deadline")
        if trade.get("position_flat_before_deadline") is False and trade.get("exit_before_flatten_deadline") is not False:
            self._record_apex_violation(diagnostics, "overnight_position_violations")

    def _record_apex_violation(self, diagnostics: dict, key: str) -> None:
        diagnostics["apex"][key] = diagnostics["apex"].get(key, 0) + 1
        diagnostics["apex"]["rule_violations"] += 1

    def _apex_timestamp(self, timestamp) -> pd.Timestamp:
        ts = pd.Timestamp(timestamp)
        if ts.tzinfo is None:
            return ts.tz_localize(self.apex_timezone)
        return ts.tz_convert(self.apex_timezone)

    def _event_filter_diagnostics(self) -> dict:
        filters = self.event_filters
        return {
            "enabled": bool(filters.enabled),
            "timezone": filters.timezone,
            "windows_configured": len(filters.no_trade_windows),
            "entry_rejections": 0,
            "pending_orders_cancelled": 0,
            "flatten_trades": 0,
            "flatten_trades_by_window": {},
        }

    def _event_entry_allowed(self, timestamp) -> bool:
        if not self.event_filters.enabled:
            return True
        window = self._event_window_at(timestamp)
        return window is None or not window.block_entries

    def _record_event_pending_cancel(self, diagnostics: dict, timestamp) -> None:
        if not self.event_filters.enabled:
            return
        diagnostics["event_filters"]["entry_rejections"] += 1
        window = self._event_window_at(timestamp)
        if window is not None and window.cancel_pending_orders:
            diagnostics["event_filters"]["pending_orders_cancelled"] += 1

    def _record_event_flatten(self, diagnostics: dict, window: NoTradeWindow) -> None:
        diagnostics["event_filters"]["flatten_trades"] += 1
        by_window = diagnostics["event_filters"]["flatten_trades_by_window"]
        by_window[window.name] = by_window.get(window.name, 0) + 1

    def _event_window_to_flatten_before(
        self,
        bar_close_timestamp,
        next_bar_close_timestamp=None,
    ) -> NoTradeWindow | None:
        if not self.event_filters.enabled:
            return None
        for window in self.event_filters.no_trade_windows:
            if not window.flatten_positions:
                continue
            close_ts = self._event_timestamp(bar_close_timestamp, window)
            if close_ts.date().isoformat() not in window.dates:
                continue
            if close_ts.time() > window.start_time:
                continue
            if close_ts.time() == window.start_time:
                return window
            if next_bar_close_timestamp is None:
                return window
            next_close = self._event_timestamp(next_bar_close_timestamp, window)
            if next_close.date() != close_ts.date():
                return window
            if next_close.time() > window.start_time:
                return window
        return None

    def _event_window_at(self, timestamp) -> NoTradeWindow | None:
        if not self.event_filters.enabled:
            return None
        for window in self.event_filters.no_trade_windows:
            ts = self._event_timestamp(timestamp, window)
            if ts.date().isoformat() in window.dates and _time_in_window(ts.time(), window.start_time, window.end_time):
                return window
        return None

    def _event_timestamp(self, timestamp, window: NoTradeWindow) -> pd.Timestamp:
        ts = pd.Timestamp(timestamp)
        timezone = ZoneInfo(window.timezone)
        if ts.tzinfo is None:
            return ts.tz_localize(timezone)
        return ts.tz_convert(timezone)


def _format_time(value) -> str:
    return parse_time(value).strftime("%H:%M:%S")


def _no_trade_window_dates(config: dict) -> list[str]:
    dates = {pd.Timestamp(value).date().isoformat() for value in config.get("dates") or []}
    source_csv = config.get("source_csv")
    if source_csv:
        frame = pd.read_csv(source_csv)
        event_column = config.get("event_column")
        event_values = config.get("event_values")
        if event_column and event_values is not None:
            allowed = {str(value) for value in event_values}
            frame = frame[frame[event_column].astype(str).isin(allowed)]
        date_column = str(config.get("date_column", "date"))
        if date_column not in frame.columns:
            raise ValueError(f"No-trade window source_csv {source_csv} is missing date column {date_column!r}.")
        dates.update(pd.to_datetime(frame[date_column]).dt.date.astype(str))
    return sorted(dates)


def _time_in_window(value, start, end) -> bool:
    if start <= end:
        return start <= value < end
    return value >= start or value < end


def _target_already_reached(direction: str, entry: float, target: float, signal) -> bool:
    if not math.isfinite(entry) or not math.isfinite(target):
        return True
    if direction == "long":
        if entry >= target:
            return True
        confirmation_high = _signal_metadata_float(signal, "confirmation_high")
        return confirmation_high is not None and confirmation_high >= target
    if direction == "short":
        if entry <= target:
            return True
        confirmation_low = _signal_metadata_float(signal, "confirmation_low")
        return confirmation_low is not None and confirmation_low <= target
    return False


def _signal_metadata_float(signal, key: str) -> float | None:
    try:
        value = signal.metadata.get(key)
    except AttributeError:
        return None
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _signal_metadata_time(signal, key: str, default):
    try:
        value = signal.metadata.get(key)
    except AttributeError:
        value = None
    return parse_time(default if value is None else value)


def _signal_metadata_timestamp(signal, key: str) -> pd.Timestamp | None:
    try:
        value = signal.metadata.get(key)
    except AttributeError:
        return None
    if value is None or pd.isna(value):
        return None
    try:
        return pd.Timestamp(value)
    except (TypeError, ValueError):
        return None


def _signal_entry_mode(signal) -> str:
    try:
        value = signal.metadata.get("entry_mode")
    except AttributeError:
        value = None
    return str(value or "next_bar_open").strip().lower()


def _stop_target_hits(
    bar: pd.Series,
    direction: str,
    stop_price: float,
    target_price: float,
) -> tuple[bool, bool]:
    if direction == "long":
        return bool(bar["low"] <= stop_price), bool(bar["high"] >= target_price)
    return bool(bar["high"] >= stop_price), bool(bar["low"] <= target_price)


def _dynamic_stop_trigger_hit(bar: pd.Series, direction: str, trigger_price: float) -> bool:
    if direction == "long":
        return bool(bar["high"] >= trigger_price)
    return bool(bar["low"] <= trigger_price)


def _resolve_detail_stop_target(
    detail_data: pd.DataFrame | None,
    start: pd.Timestamp,
    end: pd.Timestamp,
    direction: str,
    stop_price: float,
    target_price: float,
    *,
    suppress_first_detail_target: bool = False,
    allow_open_gap_fill: bool = False,
    diagnostics: dict | None = None,
) -> tuple[str, float, pd.Timestamp] | None:
    if detail_data is None or detail_data.empty:
        return None
    detail_granularity = _detail_granularity(detail_data)
    first_detail_start = (
        start.floor("min") if suppress_first_detail_target and detail_granularity == "minute_bar" else start
    )
    mask = (detail_data["timestamp"] >= first_detail_start) & (detail_data["timestamp"] < end)
    for _, detail_bar in detail_data.loc[mask].iterrows():
        detail_timestamp = pd.Timestamp(detail_bar["timestamp"])
        if suppress_first_detail_target and _detail_row_contains_start(detail_timestamp, start, detail_granularity):
            stop_hit, target_hit = _stop_target_hits(detail_bar, direction, stop_price, target_price)
            if stop_hit:
                reason, raw_exit = stop_target_hit(
                    detail_bar,
                    direction,
                    stop_price,
                    target_price,
                    allow_open_gap_fill=(allow_open_gap_fill or detail_granularity == "scid_record"),
                )
                if diagnostics is not None and raw_exit != stop_price:
                    diagnostics["gap_stop_fills"] = diagnostics.get("gap_stop_fills", 0) + 1
                return reason, raw_exit, detail_timestamp
            if target_hit:
                if diagnostics is not None:
                    diagnostics["intrabar_first_detail_targets_suppressed"] += 1
                continue
        reason, raw_exit = stop_target_hit(
            detail_bar,
            direction,
            stop_price,
            target_price,
            allow_open_gap_fill=(allow_open_gap_fill or detail_timestamp > start),
        )
        if reason is not None:
            if diagnostics is not None and reason == "stop" and raw_exit != stop_price:
                diagnostics["gap_stop_fills"] = diagnostics.get("gap_stop_fills", 0) + 1
            return reason, raw_exit, detail_timestamp
    return None


def _update_trade_excursions(
    opened: dict,
    bar: pd.Series,
    detail_data: pd.DataFrame | None,
    detail_timestamps,
    start_timestamp,
    end_timestamp,
    *,
    exit_reason: str | None,
    raw_exit: float | None,
) -> None:
    high, low = _held_segment_price_bounds(
        bar,
        detail_data,
        detail_timestamps,
        start_timestamp,
        end_timestamp,
        include_end=exit_reason is not None,
    )
    raw_exit_price = _float_or_none(raw_exit)
    if raw_exit_price is not None:
        if high is None or low is None:
            high = low = raw_exit_price
        else:
            high = max(high, raw_exit_price)
            low = min(low, raw_exit_price)
    if high is None or low is None:
        return
    high, low = _clamp_exit_segment_bounds(
        str(opened.get("direction")),
        exit_reason,
        raw_exit_price,
        high,
        low,
    )
    mfe, mae = _excursions_from_bounds(
        str(opened.get("direction")),
        float(opened["entry_price"]),
        high,
        low,
    )
    opened["max_favorable_excursion"] = max(float(opened.get("max_favorable_excursion", 0.0)), mfe)
    opened["max_adverse_excursion"] = max(float(opened.get("max_adverse_excursion", 0.0)), mae)


def _held_segment_price_bounds(
    bar: pd.Series,
    detail_data: pd.DataFrame | None,
    detail_timestamps,
    start_timestamp,
    end_timestamp,
    *,
    include_end: bool,
) -> tuple[float | None, float | None]:
    if detail_data is not None and detail_timestamps is not None:
        start = pd.Timestamp(start_timestamp)
        end = pd.Timestamp(end_timestamp)
        if end < start:
            end = start
        left = int(detail_timestamps.searchsorted(start, side="left"))
        right = int(detail_timestamps.searchsorted(end, side="right" if include_end else "left"))
        if right <= left:
            return None, None
        return _detail_rows_price_bounds(detail_data.iloc[left:right])
    return _float_or_none(_series_value(bar, "high")), _float_or_none(_series_value(bar, "low"))


def _detail_rows_price_bounds(rows: pd.DataFrame) -> tuple[float | None, float | None]:
    high = _series_extreme(rows.get("high"), "max")
    low = _series_extreme(rows.get("low"), "min")
    if high is None:
        high = _series_extreme(rows.get("close"), "max")
    if low is None:
        low = _series_extreme(rows.get("close"), "min")
    return high, low


def _series_extreme(series, method: str) -> float | None:
    if series is None:
        return None
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    value = numeric.max() if method == "max" else numeric.min()
    return _float_or_none(value)


def _clamp_exit_segment_bounds(
    direction: str,
    exit_reason: str | None,
    raw_exit: float | None,
    high: float,
    low: float,
) -> tuple[float, float]:
    if raw_exit is None:
        return high, low
    reason = str(exit_reason or "")
    if direction == "long":
        if reason == "stop":
            low = max(low, raw_exit)
        elif reason == "target":
            high = min(high, raw_exit)
    elif direction == "short":
        if reason == "stop":
            high = min(high, raw_exit)
        elif reason == "target":
            low = max(low, raw_exit)
    return high, low


def _excursions_from_bounds(direction: str, entry_price: float, high: float, low: float) -> tuple[float, float]:
    if direction == "long":
        return max(0.0, high - entry_price), max(0.0, entry_price - low)
    return max(0.0, entry_price - low), max(0.0, high - entry_price)


def _detail_granularity(detail_data: pd.DataFrame | None) -> str:
    if detail_data is None:
        return "minute_bar"
    attr_value = getattr(detail_data, "attrs", {}).get("detail_granularity")
    if attr_value:
        return str(attr_value)
    if "execution_granularity" in detail_data.columns and len(detail_data):
        value = detail_data["execution_granularity"].iloc[0]
        if pd.notna(value):
            return str(value)
    return "minute_bar"


def _detail_data_is_authoritative_execution_path(detail_data: pd.DataFrame | None) -> bool:
    return _detail_granularity(detail_data) in {"scid_record"}


def _detail_row_contains_start(detail_timestamp: pd.Timestamp, start: pd.Timestamp, granularity: str) -> bool:
    if granularity == "minute_bar":
        return detail_timestamp <= start < detail_timestamp + pd.Timedelta(minutes=1)
    return detail_timestamp <= start


def _validation_stop_target_audit(
    bar: pd.Series,
    detail_data: pd.DataFrame | None,
    direction: str,
    stop_price: float,
    target_price: float,
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    suppress_first_detail_target: bool = False,
) -> dict:
    stop_hit, target_hit = _stop_target_hits(bar, direction, stop_price, target_price)
    audit = {
        "exit_bar_timestamp": _series_value(bar, "timestamp"),
        "exit_bar_open": _float_or_none(_series_value(bar, "open")),
        "exit_bar_high": _float_or_none(_series_value(bar, "high")),
        "exit_bar_low": _float_or_none(_series_value(bar, "low")),
        "exit_bar_close": _float_or_none(_series_value(bar, "close")),
        "sl_hit_on_exit_bar": stop_hit,
        "tp_hit_on_exit_bar": target_hit,
        "same_bar_ambiguous": stop_hit and target_hit,
        "highest_price_before_exit": _float_or_none(_series_value(bar, "high")),
        "lowest_price_before_exit": _float_or_none(_series_value(bar, "low")),
    }
    if detail_data is not None and not detail_data.empty:
        audit.update(
            _validation_detail_first_touches(
                detail_data,
                start,
                end,
                direction,
                stop_price,
                target_price,
                suppress_first_detail_target=suppress_first_detail_target,
            )
        )
        return audit
    bar_timestamp = _series_value(bar, "timestamp")
    if stop_hit:
        audit["first_touch_sl_time"] = bar_timestamp
        audit["first_touch_sl_price"] = stop_price
    if target_hit:
        audit["first_touch_tp_time"] = bar_timestamp
        audit["first_touch_tp_price"] = target_price
    return audit


def _validation_detail_first_touches(
    detail_data: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    direction: str,
    stop_price: float,
    target_price: float,
    *,
    suppress_first_detail_target: bool = False,
) -> dict:
    detail_granularity = _detail_granularity(detail_data)
    first_detail_start = (
        start.floor("min") if suppress_first_detail_target and detail_granularity == "minute_bar" else start
    )
    mask = (detail_data["timestamp"] >= first_detail_start) & (detail_data["timestamp"] < end)
    first_sl = None
    first_tp = None
    first_sl_price = None
    first_tp_price = None
    highest = None
    lowest = None
    for _, detail_bar in detail_data.loc[mask].iterrows():
        detail_timestamp = pd.Timestamp(detail_bar["timestamp"])
        high = _float_or_none(_series_value(detail_bar, "high"))
        low = _float_or_none(_series_value(detail_bar, "low"))
        if high is not None:
            highest = high if highest is None else max(highest, high)
        if low is not None:
            lowest = low if lowest is None else min(lowest, low)
        stop_hit, target_hit = _stop_target_hits(detail_bar, direction, stop_price, target_price)
        suppress_target = suppress_first_detail_target and _detail_row_contains_start(
            detail_timestamp,
            start,
            detail_granularity,
        )
        if stop_hit and first_sl is None:
            first_sl = detail_timestamp
            first_sl_price = stop_price
        if target_hit and not suppress_target and first_tp is None:
            first_tp = detail_timestamp
            first_tp_price = target_price
        if first_sl is not None and first_tp is not None:
            break
    return {
        "first_touch_sl_time": first_sl,
        "first_touch_tp_time": first_tp,
        "first_touch_sl_price": first_sl_price,
        "first_touch_tp_price": first_tp_price,
        "highest_price_before_exit": highest,
        "lowest_price_before_exit": lowest,
    }


def _validation_selected_trade_ids(trades: pd.DataFrame, max_trades: int | None) -> set:
    if trades.empty or "trade_id" not in trades.columns:
        return set()
    ids = list(trades["trade_id"])
    if max_trades is not None:
        ids = ids[:max_trades]
    return set(ids)


def _validation_window_indices(
    context: dict,
    row_count: int,
    before: int,
    after: int,
) -> tuple[int | None, int | None]:
    indices = [
        _int_or_none(context.get("decision_bar_index")),
        _int_or_none(context.get("entry_bar_index")),
        _int_or_none(context.get("exit_bar_index")),
    ]
    indices = [value for value in indices if value is not None]
    if not indices or row_count <= 0:
        return None, None
    start = max(0, min(indices) - before)
    end = min(row_count - 1, max(indices) + after)
    return start, end


def _validation_source_row_for_timestamp(
    timestamp,
    data: pd.DataFrame,
    detail_data: pd.DataFrame | None,
) -> dict:
    if _is_missing(timestamp):
        return {}
    ts = pd.Timestamp(timestamp)
    detail_row = _first_matching_timestamp_row(detail_data, ts) if detail_data is not None else {}
    if detail_row:
        detail_row["source"] = "detail"
        return detail_row
    bar_row = _first_matching_timestamp_row(data, ts)
    if bar_row:
        bar_row["source"] = "bar"
    return bar_row


def _first_matching_timestamp_row(frame: pd.DataFrame | None, timestamp: pd.Timestamp) -> dict:
    if frame is None or frame.empty or "timestamp" not in frame.columns:
        return {}
    timestamps = pd.to_datetime(frame["timestamp"])
    exact = frame.loc[timestamps == timestamp]
    if exact.empty:
        return {}
    return _row_to_jsonable_dict(exact.iloc[0])


def _validation_filter_values(report_fields: dict, metadata: dict, bar: pd.Series) -> dict:
    out: dict[str, Any] = {}
    for source_name, source in (
        ("report", report_fields),
        ("metadata", metadata),
        ("bar", _row_to_jsonable_dict(bar)),
    ):
        for key, value in source.items():
            lowered = str(key).lower()
            if (
                isinstance(value, bool)
                or "filter" in lowered
                or "pass" in lowered
                or "reject" in lowered
                or "eligible" in lowered
                or lowered.startswith("is_")
                or lowered.startswith("allow_")
                or "max_trades" in lowered
                or "no_trade" in lowered
            ):
                out[f"{source_name}.{key}"] = value
    return out


def _validation_orderflow_values(report_fields: dict, metadata: dict, bar: pd.Series) -> dict:
    terms = (
        "volume",
        "delta",
        "signed",
        "imbalance",
        "bid",
        "ask",
        "buy",
        "sell",
        "large",
        "trade_orderflow",
        "footprint",
        "vpin",
        "vap",
        "vwap",
        "poc",
        "vah",
        "val",
        "lvn",
        "aoi",
        "absorption",
    )
    out: dict[str, Any] = {}
    for source_name, source in (
        ("report", report_fields),
        ("metadata", metadata),
        ("bar", _row_to_jsonable_dict(bar)),
    ):
        for key, value in source.items():
            lowered = str(key).lower()
            if any(term in lowered for term in terms):
                out[f"{source_name}.{key}"] = value
    return out


def _row_to_jsonable_dict(row) -> dict:
    if row is None:
        return {}
    if isinstance(row, pd.Series):
        items = row.to_dict()
    elif isinstance(row, dict):
        items = dict(row)
    else:
        return {}
    return {str(key): _json_safe(value) for key, value in items.items() if not _is_missing(value)}


def _json_text(value) -> str | None:
    if value is None:
        return None
    safe = _json_safe(value)
    if safe in ({}, []):
        return None
    return json.dumps(safe, sort_keys=True, default=str, allow_nan=False)


def _json_safe(value):
    if _is_missing(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items() if not _is_missing(item)}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value if not _is_missing(item)]
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass
    if hasattr(value, "item"):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass
    return value


def _first_present(*values):
    for value in values:
        if not _is_missing(value):
            return value
    return None


def _series_value(row, column: str):
    if row is None:
        return None
    try:
        if column not in row.index:
            return None
        value = row[column]
    except AttributeError:
        try:
            value = row[column]
        except (KeyError, TypeError):
            return None
    return None if _is_missing(value) else value


def _is_missing(value) -> bool:
    if value is None:
        return True
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(result, bool):
        return result
    return False


def _float_or_none(value) -> float | None:
    if _is_missing(value):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _int_or_none(value) -> int | None:
    if _is_missing(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value) -> bool | None:
    if _is_missing(value):
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return bool(value)


def _points_to_ticks(value, tick_size: float) -> float | None:
    points = _float_or_none(value)
    if points is None or tick_size <= 0:
        return points
    return points / tick_size
