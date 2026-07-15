from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class TradeFragmentationLiquidityReversionEntry:
    name = "trade_fragmentation_liquidity_reversion"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", self.name))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.window_minutes = int(params.get("window_minutes", 30))
        self.rank_window = int(params.get("rank_window", 42))
        self.trade_count_rank_threshold = float(params.get("trade_count_rank_threshold", 0.65))
        self.avg_trade_size_rank_threshold = float(params.get("avg_trade_size_rank_threshold", 0.50))
        self.min_return_ticks = float(params.get("min_return_ticks", 1.0))
        self.return_mode = str(params.get("return_mode", "both")).lower()
        self.direction = str(params.get("direction", "auto")).lower()
        self.max_trades_per_day = int(params.get("max_trades_per_day", 2))
        self.stop_pct = float(params.get("stop_pct", 0.003))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.0))
        self.default_flatten_time = parse_time(params.get("flatten_time", "15:00:00"))
        self.slots = [_slot_config(params, slot, index) for index, slot in enumerate(params.get("slots") or [{}], start=1)]
        self.slots.sort(key=lambda item: item["entry_time"])
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        for slot in self.slots:
            signal_timestamp = timestamp.replace(
                hour=slot["entry_time"].hour,
                minute=slot["entry_time"].minute,
                second=slot["entry_time"].second,
                microsecond=0,
            )
            if bar_close != signal_timestamp:
                continue
            signal = self._signal_for_slot(bar, timestamp, signal_timestamp, slot)
            if signal is not None:
                return signal
        return None

    def _signal_for_slot(
        self,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        signal_timestamp: pd.Timestamp,
        slot: dict,
    ) -> Signal | None:
        values = self._feature_values(bar, slot)
        if values is None:
            return None
        if values["trade_count_rank"] < self.trade_count_rank_threshold:
            return None
        if values["avg_trade_size_rank"] > self.avg_trade_size_rank_threshold:
            return None

        direction = self._direction_from_return(values["return_ticks"])
        if direction is None:
            return None
        if self.direction in {"long", "short"} and direction != self.direction:
            return None

        current_close = float(bar["close"])
        flatten_time = slot["flatten_time"]
        report_fields = {
            "setup_mode": self.setup_mode,
            "slot_id": slot["slot_id"],
            "feature_method": "completed_bar_trade_fragmentation_liquidity_reversion",
            "window_minutes": self.window_minutes,
            "rank_window": self.rank_window,
            "return_mode": self.return_mode,
            "configured_direction": self.direction,
            "trade_count_column": slot["trade_count_column"],
            "trade_count_value": values["trade_count"],
            "trade_count_rank_column": slot["trade_count_rank_column"],
            "trade_count_rank": values["trade_count_rank"],
            "trade_count_rank_threshold": self.trade_count_rank_threshold,
            "avg_trade_size_column": slot["avg_trade_size_column"],
            "avg_trade_size_value": values["avg_trade_size"],
            "avg_trade_size_rank_column": slot["avg_trade_size_rank_column"],
            "avg_trade_size_rank": values["avg_trade_size_rank"],
            "avg_trade_size_rank_threshold": self.avg_trade_size_rank_threshold,
            "return_column": slot["return_column"],
            "return_ticks": values["return_ticks"],
            "min_return_ticks": self.min_return_ticks,
            "orderflow_signal_timestamp": signal_timestamp,
            "orderflow_intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": flatten_time.strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        return Signal(
            direction=direction,
            level_type=f"trade_fragmentation_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "slot_id": slot["slot_id"],
                "window_minutes": self.window_minutes,
                "rank_window": self.rank_window,
                "trade_count_rank_threshold": self.trade_count_rank_threshold,
                "avg_trade_size_rank_threshold": self.avg_trade_size_rank_threshold,
                "min_return_ticks": self.min_return_ticks,
                "return_mode": self.return_mode,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _feature_values(self, bar: pd.Series, slot: dict) -> dict[str, float] | None:
        values = {
            "trade_count": _finite_float(bar.get(slot["trade_count_column"])),
            "trade_count_rank": _finite_float(bar.get(slot["trade_count_rank_column"])),
            "avg_trade_size": _finite_float(bar.get(slot["avg_trade_size_column"])),
            "avg_trade_size_rank": _finite_float(bar.get(slot["avg_trade_size_rank_column"])),
            "return_ticks": _finite_float(bar.get(slot["return_column"])),
        }
        if any(value is None for value in values.values()):
            return None
        return values

    def _direction_from_return(self, return_ticks: float) -> str | None:
        if self.return_mode in {"up", "both"} and return_ticks >= self.min_return_ticks:
            return "short"
        if self.return_mode in {"down", "both"} and return_ticks <= -self.min_return_ticks:
            return "long"
        return None

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.window_minutes <= 0:
            raise ValueError("window_minutes must be greater than 0.")
        if self.rank_window <= 0:
            raise ValueError("rank_window must be greater than 0.")
        if not (0 <= self.trade_count_rank_threshold <= 1):
            raise ValueError("trade_count_rank_threshold must be in [0, 1].")
        if not (0 <= self.avg_trade_size_rank_threshold <= 1):
            raise ValueError("avg_trade_size_rank_threshold must be in [0, 1].")
        if self.min_return_ticks < 0:
            raise ValueError("min_return_ticks must be non-negative.")
        if self.return_mode not in {"up", "down", "both"}:
            raise ValueError("return_mode must be one of: up, down, both.")
        if self.direction not in {"auto", "long", "short"}:
            raise ValueError("direction must be auto, long, or short.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if not self.slots:
            raise ValueError("trade_fragmentation_liquidity_reversion requires at least one slot.")


def _slot_config(params: dict, slot: dict, index: int) -> dict:
    merged = {**params, **dict(slot or {})}
    window = int(merged.get("window_minutes", params.get("window_minutes", 30)))
    rank_window = int(merged.get("rank_window", params.get("rank_window", 42)))
    suffix = str(window)
    return {
        "slot_id": str(merged.get("slot_id", f"slot_{index}")),
        "entry_time": parse_time(merged.get("entry_time", "10:00:00")),
        "flatten_time": parse_time(merged.get("flatten_time", params.get("flatten_time", "15:00:00"))),
        "trade_count_column": str(merged.get("trade_count_column", f"trade_orderflow_trades_{suffix}")),
        "trade_count_rank_column": str(
            merged.get("trade_count_rank_column", f"trade_orderflow_trades_{suffix}_rank{rank_window}")
        ),
        "avg_trade_size_column": str(merged.get("avg_trade_size_column", f"trade_orderflow_avg_trade_size_{suffix}")),
        "avg_trade_size_rank_column": str(
            merged.get(
                "avg_trade_size_rank_column",
                f"trade_orderflow_avg_trade_size_{suffix}_rank{rank_window}",
            )
        ),
        "return_column": str(merged.get("return_column", f"trade_orderflow_return_ticks_{suffix}")),
    }


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
