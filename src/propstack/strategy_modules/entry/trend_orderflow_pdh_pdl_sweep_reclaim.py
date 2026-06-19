from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class TrendOrderflowPdhPdlSweepReclaimEntry:
    name = "trend_orderflow_pdh_pdl_sweep_reclaim"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "trend_orderflow_sweep_reclaim")).lower()
        self.start_time = parse_time(params.get("start_time", "09:45:00"))
        self.end_time = parse_time(params.get("end_time", "14:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.min_sweep_ticks = float(params.get("min_sweep_ticks", 1.0))
        self.reclaim_buffer_ticks = float(params.get("reclaim_buffer_ticks", 0.0))
        self.reclaim_window_bars = int(params.get("reclaim_window_bars", 3))
        self.require_fresh_level = bool(params.get("require_fresh_level", False))
        self.min_volume_ratio = float(params.get("min_volume_ratio", 0.0))
        self.orderflow_mode = str(params.get("orderflow_mode", "signed")).lower()
        self.flow_confirmation = str(params.get("flow_confirmation", "absorbed")).lower()
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.05))
        self.short_trend_bars = int(params.get("short_trend_bars", 2))
        self.long_trend_bars = int(params.get("long_trend_bars", 4))
        self.min_trend_move_ticks = float(params.get("min_trend_move_ticks", 0.0))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        state = self._state(session_date)
        state["bar_index"] += 1
        try:
            if state["completed"] or trades_today >= self.max_trades_per_day:
                return None
            bar_time = timestamp.time()
            if bar_time < self.start_time or bar_time > self.end_time:
                return None
            if float(bar.get("volume_ratio", 0.0)) < self.min_volume_ratio:
                return None

            prev_high = _finite_float(bar.get("prev_rth_high"))
            prev_low = _finite_float(bar.get("prev_rth_low"))
            if prev_high is None or prev_low is None:
                return None

            signal = self._process_side(bar, state, "long", prev_low, "prev_rth_low_fresh")
            if signal is None:
                signal = self._process_side(bar, state, "short", prev_high, "prev_rth_high_fresh")
            if signal is not None:
                state["completed"] = True
            return signal
        finally:
            self._record_trend_bar(state, bar)

    def _process_side(
        self,
        bar: pd.Series,
        state: dict,
        direction: str,
        level: float,
        fresh_column: str,
    ) -> Signal | None:
        if direction == "long" and not self.allow_long:
            return None
        if direction == "short" and not self.allow_short:
            return None
        key = f"{direction}_sweep"
        sweep = state.get(key)
        bar_index = int(state["bar_index"])
        threshold = self.min_sweep_ticks * self.tick_size

        if sweep is None and self._fresh_level(bar, fresh_column):
            if direction == "long" and float(bar["low"]) <= level - threshold:
                sweep = self._new_sweep(bar, state, bar_index, direction, level)
                state[key] = sweep
            elif direction == "short" and float(bar["high"]) >= level + threshold:
                sweep = self._new_sweep(bar, state, bar_index, direction, level)
                state[key] = sweep

        if sweep is None:
            return None

        sweep["sweep_low"] = min(sweep["sweep_low"], float(bar["low"]))
        sweep["sweep_high"] = max(sweep["sweep_high"], float(bar["high"]))
        if bar_index - int(sweep["bar_index"]) > self.reclaim_window_bars:
            state[key] = None
            return None
        if not self._reclaimed(bar, sweep):
            return None
        state[key] = None

        imbalance = self._orderflow_imbalance(bar)
        if imbalance is None or not self._flow_confirms(direction, imbalance):
            return None
        trend = self._trend_filter(direction, sweep)
        if trend is None:
            return None
        return self._signal(bar, sweep, imbalance, trend)

    def _new_sweep(self, bar: pd.Series, state: dict, bar_index: int, direction: str, level: float) -> dict:
        return {
            "bar_index": bar_index,
            "timestamp": pd.Timestamp(bar["timestamp"]),
            "direction": direction,
            "level": float(level),
            "sweep_low": float(bar["low"]),
            "sweep_high": float(bar["high"]),
            "trend_bars": list(state["trend_bars"]),
        }

    def _reclaimed(self, bar: pd.Series, sweep: dict) -> bool:
        buffer = self.reclaim_buffer_ticks * self.tick_size
        close = float(bar["close"])
        if sweep["direction"] == "long":
            return close >= float(sweep["level"]) + buffer
        return close <= float(sweep["level"]) - buffer

    def _orderflow_imbalance(self, bar: pd.Series) -> float | None:
        signed_col, volume_col = {
            "signed": ("signed_volume", "volume"),
            "large10": ("large10_signed_volume", "large10_volume"),
            "large20": ("large20_signed_volume", "large20_volume"),
        }[self.orderflow_mode]
        signed = _finite_float(bar.get(signed_col))
        volume = _finite_float(bar.get(volume_col))
        if signed is None or volume is None or volume <= 0:
            return None
        return signed / volume

    def _flow_confirms(self, direction: str, imbalance: float) -> bool:
        threshold = self.min_orderflow_imbalance
        if self.flow_confirmation == "absorbed":
            if direction == "long":
                return imbalance <= -threshold
            return imbalance >= threshold
        if direction == "long":
            return imbalance >= threshold
        return imbalance <= -threshold

    def _trend_filter(self, direction: str, sweep: dict) -> dict | None:
        bars = list(sweep.get("trend_bars") or [])
        required = 2 * max(self.short_trend_bars, self.long_trend_bars)
        if len(bars) < required:
            return None
        short = self._window_trend(bars, self.short_trend_bars, "short")
        long = self._window_trend(bars, self.long_trend_bars, "long")
        if direction == "long":
            if not (short["long_ok"] and long["long_ok"]):
                return None
        elif direction == "short":
            if not (short["short_ok"] and long["short_ok"]):
                return None
        else:
            return None
        return {**short["report_fields"], **long["report_fields"]}

    def _window_trend(self, bars: list[dict], window_bars: int, label: str) -> dict:
        previous = bars[-(2 * window_bars) : -window_bars]
        current = bars[-window_bars:]
        prev_high = max(_required_float(bar.get("high"), "high") for bar in previous)
        prev_low = min(_required_float(bar.get("low"), "low") for bar in previous)
        current_high = max(_required_float(bar.get("high"), "high") for bar in current)
        current_low = min(_required_float(bar.get("low"), "low") for bar in current)
        min_move = self.min_trend_move_ticks * self.tick_size
        long_ok = current_high >= prev_high + min_move and current_low >= prev_low + min_move
        short_ok = current_high <= prev_high - min_move and current_low <= prev_low - min_move
        return {
            "long_ok": long_ok,
            "short_ok": short_ok,
            "report_fields": {
                f"{label}_trend_previous_high": prev_high,
                f"{label}_trend_previous_low": prev_low,
                f"{label}_trend_current_high": current_high,
                f"{label}_trend_current_low": current_low,
            },
        }

    def _signal(self, bar: pd.Series, sweep: dict, imbalance: float, trend: dict) -> Signal:
        direction = sweep["direction"]
        level_type = "previous_rth_low_trend_flow_reclaim" if direction == "long" else "previous_rth_high_trend_flow_reject"
        timestamp = pd.Timestamp(bar["timestamp"])
        flatten_label = self.flatten_time.strftime("%H:%M:%S")
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "pdh_pdl_sweep_reclaim_trend_absorbed_orderflow",
            "trend_filter": "completed_bar_higher_highs_lows",
            "flow_confirmation": self.flow_confirmation,
            "orderflow_mode": self.orderflow_mode,
            "orderflow_imbalance": imbalance,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "min_sweep_ticks": self.min_sweep_ticks,
            "reclaim_buffer_ticks": self.reclaim_buffer_ticks,
            "reclaim_window_bars": self.reclaim_window_bars,
            "swept_level": sweep["level"],
            "sweep_timestamp": sweep["timestamp"],
            "sweep_high": sweep["sweep_high"],
            "sweep_low": sweep["sweep_low"],
            "reclaim_timestamp": timestamp,
            "signal_flatten_time": flatten_label,
            "short_trend_bars": self.short_trend_bars,
            "long_trend_bars": self.long_trend_bars,
            "min_trend_move_ticks": self.min_trend_move_ticks,
            **trend,
        }
        return Signal(
            direction=direction,
            level_type=level_type,
            swept_level=sweep["level"],
            sweep_timestamp=sweep["timestamp"],
            sweep_high=sweep["sweep_high"],
            sweep_low=sweep["sweep_low"],
            reclaim_timestamp=timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "orderflow_mode": self.orderflow_mode,
                "flow_confirmation": self.flow_confirmation,
                "orderflow_imbalance": imbalance,
                "flatten_time": flatten_label,
            },
            report_fields=report_fields,
        )

    def _fresh_level(self, bar: pd.Series, column: str) -> bool:
        if not self.require_fresh_level:
            return True
        if column not in bar:
            return True
        value = bar.get(column)
        if pd.isna(value):
            return False
        return bool(value)

    def _state(self, session_date) -> dict:
        return self.state_by_day.setdefault(
            session_date,
            {
                "bar_index": -1,
                "long_sweep": None,
                "short_sweep": None,
                "completed": False,
                "trend_bars": [],
            },
        )

    def _trend_bar_snapshot(self, bar: pd.Series) -> dict:
        return {
            "timestamp": bar["timestamp"],
            "high": _required_float(bar.get("high"), "high"),
            "low": _required_float(bar.get("low"), "low"),
        }

    def _record_trend_bar(self, state: dict, bar: pd.Series) -> None:
        state["trend_bars"].append(self._trend_bar_snapshot(bar))
        max_trend_bars = 2 * max(self.short_trend_bars, self.long_trend_bars)
        state["trend_bars"][:] = state["trend_bars"][-max_trend_bars:]

    def _validate(self) -> None:
        if self.tick_size <= 0 or self.bar_interval_minutes <= 0:
            raise ValueError("tick_size and bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.min_sweep_ticks < 0 or self.reclaim_buffer_ticks < 0:
            raise ValueError("min_sweep_ticks and reclaim_buffer_ticks must be non-negative.")
        if self.reclaim_window_bars < 0:
            raise ValueError("reclaim_window_bars must be non-negative.")
        if self.orderflow_mode not in {"signed", "large10", "large20"}:
            raise ValueError("orderflow_mode must be signed, large10, or large20.")
        if self.flow_confirmation not in {"absorbed", "aligned"}:
            raise ValueError("flow_confirmation must be absorbed or aligned.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("min_orderflow_imbalance must be non-negative.")
        if self.short_trend_bars <= 0 or self.long_trend_bars <= 0:
            raise ValueError("short_trend_bars and long_trend_bars must be positive.")
        if self.min_trend_move_ticks < 0:
            raise ValueError("min_trend_move_ticks must be non-negative.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _required_float(value, name: str) -> float:
    out = _finite_float(value)
    if out is None:
        raise ValueError(f"entry bar is missing finite {name}.")
    return out
