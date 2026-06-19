from __future__ import annotations

import copy
from dataclasses import dataclass
import math
from zoneinfo import ZoneInfo

import pandas as pd

from propstack.backtest.fills import entry_price, exit_price, stop_target_hit
from propstack.backtest.metrics import calculate_metrics, daily_results
from propstack.backtest.risk import DailyRisk
from propstack.backtest.sizing import size_position, tick_value_from_core
from propstack.strategy import ModularStrategy
from propstack.utils.config import config_timeframe_minutes
from propstack.utils.progress import progress_bar
from propstack.utils.time import parse_time


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


class BacktestEngine:
    def __init__(self, config: dict, show_progress: bool = False):
        self.config = config
        self.strategy_config = copy.deepcopy(config.get("strategy", {}))
        if "strategy_name" not in self.strategy_config and config.get("strategy_name"):
            self.strategy_config["strategy_name"] = config["strategy_name"]
        self.core_config = config.get("core", {})
        self.apex_rules = ApexRules.from_config(config)
        self.apex_timezone = ZoneInfo(self.apex_rules.timezone)
        self.event_filters = EventFilters.from_config(config)
        self.show_progress = show_progress
        self.timeframe_minutes = self._configured_bar_interval_minutes()
        self._apply_timeframe_to_strategy()

    def run(self, data: pd.DataFrame, detail_data: pd.DataFrame | None = None) -> dict:
        df = data.sort_values("timestamp").reset_index(drop=True)
        detail_df = (
            detail_data.sort_values("timestamp").reset_index(drop=True)
            if detail_data is not None and not detail_data.empty
            else None
        )
        diagnostics = self._preflight(df, detail_df)
        strategy = ModularStrategy(self.strategy_config)
        entry_params = self.strategy_config.get("entry", {}).get("params", {})
        risk = DailyRisk({**self.core_config, **self.strategy_config, **entry_params})
        tick_size = float(self.core_config.get("tick_size", 0.25))
        tick_value = tick_value_from_core(self.core_config, tick_size)
        commission = float(self.core_config.get("commission_per_contract", 2.5))
        slippage_ticks = float(self.core_config.get("slippage_ticks", 1))
        flatten_time = parse_time(self.strategy_config.get("flatten_time", self.core_config.get("flatten_time", "14:55:00")))
        bar_interval_minutes = self.timeframe_minutes
        net_liq = float(self.core_config.get("initial_balance", 0.0))
        bar_delta = pd.Timedelta(minutes=bar_interval_minutes)
        timestamps = [pd.Timestamp(timestamp) for timestamp in df["timestamp"]] if len(df) else []
        bar_close_timestamps = [timestamp + bar_delta for timestamp in timestamps]
        next_entry_timestamps = timestamps[1:] + [None] if timestamps else []
        next_bar_close_timestamps = bar_close_timestamps[1:] + [None] if bar_close_timestamps else []

        pending_signal = None
        position = None
        trades = []
        trade_id = 1
        progress = progress_bar(len(df), "bars", enabled=self.show_progress)

        for i, bar in df.iterrows():
            progress.update(i + 1)
            if pending_signal is not None and position is None and not self._apex_entry_allowed(bar["timestamp"]):
                diagnostics["rejects"]["apex_latest_entry_time"] += 1
                self._record_apex_pending_cancel(diagnostics, bar["timestamp"])
                pending_signal = None
            if pending_signal is not None and position is None and not self._event_entry_allowed(bar["timestamp"]):
                diagnostics["rejects"]["event_no_trade_window"] += 1
                self._record_event_pending_cancel(diagnostics, bar["timestamp"])
                pending_signal = None

            if pending_signal is not None and position is None and risk.allow_new_trade(bar["session_date"]):
                sig = pending_signal
                direction = sig.direction
                ep = entry_price(float(bar["open"]), direction, tick_size, slippage_ticks)
                stop = strategy.stop_price(sig, direction, tick_size, entry_price=ep)
                if stop is None:
                    diagnostics["rejects"]["missing_stop"] += 1
                    pending_signal = None
                    continue
                target = strategy.target_price(ep, stop, direction, signal=sig)
                if _target_already_reached(direction, ep, target, sig):
                    diagnostics["rejects"]["target_already_reached"] += 1
                    pending_signal = None
                    continue
                risk_points = abs(ep - stop)
                sizing = size_position(self.core_config, risk_points, tick_size, tick_value, net_liq=net_liq)
                if sizing.contracts < 1:
                    diagnostics["rejects"]["position_sizing"] += 1
                    pending_signal = None
                    continue
                position = {
                    "trade_id": trade_id,
                    "strategy_name": strategy.name,
                    "session_date": bar["session_date"],
                    "direction": direction,
                    "level_type": sig.level_type,
                }
                if sig.report_fields:
                    position.update(sig.report_fields)
                else:
                    position.update(
                        {
                            "swept_level": sig.swept_level,
                            "sweep_timestamp": sig.sweep_timestamp,
                            "sweep_high": sig.sweep_high,
                            "sweep_low": sig.sweep_low,
                            "reclaim_timestamp": sig.reclaim_timestamp,
                        }
                    )
                position.update(
                    {
                        "entry_timestamp": bar["timestamp"],
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
                position.update(sizing.report_fields())
                risk.record_entry(bar["session_date"])
                diagnostics["entries_opened"] += 1
                trade_id += 1
            elif pending_signal is not None and position is None:
                diagnostics["rejects"]["daily_risk_lockout"] += 1
            pending_signal = None

            if position is not None:
                direction = position["direction"]
                if direction == "long":
                    mfe = max(0.0, float(bar["high"]) - position["entry_price"])
                    mae = max(0.0, position["entry_price"] - float(bar["low"]))
                else:
                    mfe = max(0.0, position["entry_price"] - float(bar["low"]))
                    mae = max(0.0, float(bar["high"]) - position["entry_price"])
                position["max_favorable_excursion"] = max(position["max_favorable_excursion"], mfe)
                position["max_adverse_excursion"] = max(position["max_adverse_excursion"], mae)

                bar_close_timestamp = bar_close_timestamps[i]
                next_bar_close_timestamp = next_bar_close_timestamps[i]
                event_window = None
                reason, raw_exit, exit_timestamp = self._resolve_stop_target_exit(
                    bar,
                    direction,
                    position["stop_price"],
                    position["target_price"],
                    bar_close_timestamp,
                    detail_df,
                    diagnostics,
                )
                position_flatten_time = parse_time(position.get("signal_flatten_time", flatten_time))
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
                if reason is not None:
                    xp = exit_price(float(raw_exit), direction, tick_size, slippage_ticks)
                    point_pnl = xp - position["entry_price"] if direction == "long" else position["entry_price"] - xp
                    contracts = int(position["contracts"])
                    gross = point_pnl / tick_size * tick_value * contracts
                    total_commission = commission * contracts * 2
                    slippage_cost = slippage_ticks * tick_value * contracts * 2
                    net = gross - total_commission
                    r_mult = point_pnl / position["risk_points"] if position["risk_points"] else 0.0
                    trade = {
                        **position,
                        "exit_timestamp": exit_timestamp,
                        "exit_price": xp,
                        "exit_reason": reason,
                        "gross_pnl": gross,
                        "net_pnl": net,
                        "r_multiple": r_mult,
                        "commission": total_commission,
                        "slippage_cost": slippage_cost,
                    }
                    trade.update(self._apex_trade_fields(trade))
                    trades.append(trade)
                    diagnostics["exits"][reason] = diagnostics["exits"].get(reason, 0) + 1
                    self._record_trade_apex_diagnostics(trade, diagnostics)
                    if event_window is not None and reason == event_window.exit_reason:
                        self._record_event_flatten(diagnostics, event_window)
                    risk.record_exit(position["session_date"], net)
                    net_liq += net
                    position = None
                    continue

            if position is None and risk.allow_new_trade(bar["session_date"]):
                bar_close_timestamp = bar_close_timestamps[i]
                signal = strategy.on_bar_close(bar, risk.trades_today(bar["session_date"]))
                if signal is not None:
                    diagnostics["signals_generated"] += 1
                    next_entry_timestamp = next_entry_timestamps[i]
                    if (
                        next_entry_timestamp is not None
                        and self._apex_entry_allowed(next_entry_timestamp)
                        and self._event_entry_allowed(next_entry_timestamp)
                    ):
                        pending_signal = signal
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
        return {
            "trades": trades_df,
            "daily": daily_results(trades_df),
            "metrics": metrics,
            "diagnostics": diagnostics,
        }

    def _preflight(self, data: pd.DataFrame, detail_data: pd.DataFrame | None) -> dict:
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
            },
            "signals_generated": 0,
            "entries_opened": 0,
            "trades_closed": 0,
            "rejects": {
                "missing_stop": 0,
                "target_already_reached": 0,
                "position_sizing": 0,
                "daily_risk_lockout": 0,
                "apex_latest_entry_time": 0,
                "event_no_trade_window": 0,
            },
            "exits": {},
            "stop_target_conflicts": 0,
            "detail_conflicts_resolved": 0,
            "detail_conflicts_unresolved": 0,
            "apex": self._apex_diagnostics(),
            "event_filters": self._event_filter_diagnostics(),
        }
        self._validate_strategy_feature_columns(data, diagnostics)
        self._validate_timeframe_column(data, diagnostics)
        self._validate_detail_data_coverage(data, detail_data, diagnostics)
        return diagnostics

    def _validate_strategy_feature_columns(self, data: pd.DataFrame, diagnostics: dict) -> None:
        module = str(self.strategy_config.get("entry", {}).get("module", ""))
        required_by_module = {
            "amihud_illiquidity_state": {"is_rth"},
            "bls_macro_release_day_drift": {"is_rth"},
            "calendar_session_bias": {"is_rth"},
            "cftc_tff_hedging_pressure": {"is_rth"},
            "cftc_tff_tiered_hedging_pressure": {"is_rth"},
            "connors_rsi2_mean_reversion": {"is_rth"},
            "daily_time_series_momentum": {"is_rth"},
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
            "pdh_pdl_sweep_reclaim": {"is_rth", "prev_rth_low", "prev_rth_high"},
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
            "gao_last_half_hour_orderflow": {"is_rth", "signed_volume", "large20_signed_volume", "large20_volume"},
            "halloween_seasonal_premium": {"is_rth"},
            "late_day_intraday_momentum": {"is_rth", "prev_rth_close", "volume_ratio"},
            "leveraged_etf_rebalance_pressure": {"is_rth", "prev_rth_close"},
            "liquidity_risk_capacity_priority": {"is_rth"},
            "mes_participation_crowding": {
                "is_rth",
                "mes_participation_share_30_rank252",
                "mes_participation_share_60_rank252",
                "mes_trade_share_60_rank252",
                "es_return_ticks_30",
                "es_return_ticks_60",
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
                "Higher-timeframe run has no 1-minute detail_data; same-bar stop/target conflicts will use stop-first fallback."
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
        if detail_first > first or detail_last < last - pd.Timedelta(minutes=1):
            diagnostics["preflight"]["warnings"].append(
                "1-minute detail_data does not fully cover the higher-timeframe backtest span."
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
    ) -> tuple[str | None, float | None, pd.Timestamp]:
        exit_timestamp = bar["timestamp"]
        stop_hit, target_hit = _stop_target_hits(bar, direction, stop_price, target_price)
        if stop_hit and target_hit:
            diagnostics["stop_target_conflicts"] += 1
            detail_exit = _resolve_detail_stop_target(
                detail_data,
                pd.Timestamp(bar["timestamp"]),
                bar_close_timestamp,
                direction,
                stop_price,
                target_price,
            )
            if detail_exit is not None:
                diagnostics["detail_conflicts_resolved"] += 1
                return detail_exit
            diagnostics["detail_conflicts_unresolved"] += 1
        reason, raw_exit = stop_target_hit(bar, direction, stop_price, target_price)
        return reason, raw_exit, exit_timestamp

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


def _stop_target_hits(
    bar: pd.Series,
    direction: str,
    stop_price: float,
    target_price: float,
) -> tuple[bool, bool]:
    if direction == "long":
        return bool(bar["low"] <= stop_price), bool(bar["high"] >= target_price)
    return bool(bar["high"] >= stop_price), bool(bar["low"] <= target_price)


def _resolve_detail_stop_target(
    detail_data: pd.DataFrame | None,
    start: pd.Timestamp,
    end: pd.Timestamp,
    direction: str,
    stop_price: float,
    target_price: float,
) -> tuple[str, float, pd.Timestamp] | None:
    if detail_data is None or detail_data.empty:
        return None
    mask = (detail_data["timestamp"] >= start) & (detail_data["timestamp"] < end)
    for _, detail_bar in detail_data.loc[mask].iterrows():
        reason, raw_exit = stop_target_hit(detail_bar, direction, stop_price, target_price)
        if reason is not None:
            return reason, raw_exit, detail_bar["timestamp"]
    return None
