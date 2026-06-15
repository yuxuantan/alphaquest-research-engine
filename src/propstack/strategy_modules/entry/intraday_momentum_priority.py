from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class IntradayMomentumPriorityEntry:
    name = "intraday_momentum_priority"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "intraday_momentum_priority"))
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        raw_slots = params.get("slots") or []
        if not raw_slots:
            raise ValueError("intraday_momentum_priority requires at least one slot.")
        self.slots = [_parse_slot(slot, self.rth_start, self.tick_size) for slot in raw_slots]
        _apply_flat_overrides(self.slots, params)
        self.state_by_day: dict = {}
        self._validate()

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "signaled": False,
                "source_windows": {slot["slot_id"]: None for slot in self.slots},
            },
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        if self.tick_size <= 0 or self.bar_interval_minutes <= 0:
            raise ValueError("tick_size and bar_interval_minutes must be greater than 0.")

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        state = self._state(bar["session_date"])

        for slot in self.slots:
            source_start = self._session_timestamp(timestamp, slot["source_start"])
            signal_timestamp = self._session_timestamp(timestamp, slot["signal_time"])
            if timestamp >= source_start and bar_close <= signal_timestamp:
                current = state["source_windows"].get(slot["slot_id"])
                state["source_windows"][slot["slot_id"]] = self._aggregate_bar(
                    current,
                    bar,
                    source_start,
                    signal_timestamp,
                )

        if state["signaled"]:
            return None

        for slot in self.slots:
            signal_timestamp = self._session_timestamp(timestamp, slot["signal_time"])
            if bar_close != signal_timestamp:
                continue
            signal = self._signal_for_slot(slot, state["source_windows"].get(slot["slot_id"]), signal_timestamp)
            if signal is not None:
                state["signaled"] = True
                return signal
        return None

    def _signal_for_slot(self, slot: dict, source: dict | None, signal_timestamp: pd.Timestamp) -> Signal | None:
        if not source or not self._window_complete(source):
            return None

        source_open = float(source["open"])
        source_high = float(source["high"])
        source_low = float(source["low"])
        source_close = float(source["close"])
        direction = slot["direction"]
        source_return_points = source_close - source_open
        source_return_ticks = source_return_points / self.tick_size
        source_return_bps = (source_close / source_open - 1.0) * 10000.0
        source_range_points = source_high - source_low
        source_range_bps = (source_range_points / source_open) * 10000.0 if source_open else 0.0
        source_efficiency = abs(source_return_points) / source_range_points if source_range_points > 0 else 0.0
        if direction == "long":
            close_location = (source_close - source_low) / source_range_points if source_range_points > 0 else 0.0
        else:
            close_location = (source_high - source_close) / source_range_points if source_range_points > 0 else 0.0

        if direction == "long" and source_return_bps < slot["min_signal_return_bps"]:
            return None
        if direction == "short" and source_return_bps > -slot["min_signal_return_bps"]:
            return None
        if abs(source_return_ticks) < slot["min_signal_return_ticks"]:
            return None
        if source_efficiency < slot["min_source_efficiency"]:
            return None
        if close_location < slot["min_close_location"]:
            return None
        if source_range_bps < slot["min_source_range_bps"]:
            return None
        if slot["max_source_range_bps"] is not None and source_range_bps > slot["max_source_range_bps"]:
            return None

        flatten_label = slot["flatten_time"].strftime("%H:%M:%S")
        report_fields = {
            "setup_mode": self.setup_mode,
            "slot_id": slot["slot_id"],
            "source_return_reference": "slot_source_open_to_signal_close",
            "source_window_start_timestamp": source["start_timestamp"],
            "source_window_end_timestamp": source["end_timestamp"],
            "source_window_open": source_open,
            "source_window_high": source_high,
            "source_window_low": source_low,
            "source_window_close": source_close,
            "source_window_return_points": source_return_points,
            "source_window_return_ticks": source_return_ticks,
            "source_window_return_bps": source_return_bps,
            "source_window_range_bps": source_range_bps,
            "source_window_efficiency": source_efficiency,
            "source_window_directional_close_location": close_location,
            "momentum_priority_signal_timestamp": signal_timestamp,
            "momentum_priority_entry_window_start": signal_timestamp,
            "momentum_priority_entry_window_end": signal_timestamp
            + pd.Timedelta(minutes=self.bar_interval_minutes),
            "min_signal_return_bps": slot["min_signal_return_bps"],
            "min_signal_return_ticks": slot["min_signal_return_ticks"],
            "min_source_efficiency": slot["min_source_efficiency"],
            "min_close_location": slot["min_close_location"],
            "min_source_range_bps": slot["min_source_range_bps"],
            "max_source_range_bps": slot["max_source_range_bps"],
            "signal_stop_pct": slot["stop_pct"],
            "signal_target_r_multiple": slot["target_r_multiple"],
            "signal_flatten_time": flatten_label,
        }
        return Signal(
            direction=direction,
            level_type=f"intraday_momentum_priority_{slot['slot_id']}",
            swept_level=source_open,
            sweep_timestamp=source["start_timestamp"],
            sweep_high=float(source["high"]),
            sweep_low=float(source["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "slot_id": slot["slot_id"],
                "source_window_return_bps": source_return_bps,
                "source_window_range_bps": source_range_bps,
                "source_window_efficiency": source_efficiency,
                "source_window_directional_close_location": close_location,
                "stop_pct": slot["stop_pct"],
                "target_r_multiple": slot["target_r_multiple"],
                "flatten_time": flatten_label,
            },
            report_fields=report_fields,
        )

    def _aggregate_bar(self, aggregate: dict | None, bar: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict:
        if aggregate is None or aggregate.get("start_timestamp") != start or aggregate.get("end_timestamp") != end:
            return {
                "start_timestamp": start,
                "end_timestamp": end,
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": float(bar["close"]),
                "bar_count": 1,
            }

        aggregate["high"] = max(float(aggregate["high"]), float(bar["high"]))
        aggregate["low"] = min(float(aggregate["low"]), float(bar["low"]))
        aggregate["close"] = float(bar["close"])
        aggregate["bar_count"] += 1
        return aggregate

    def _window_complete(self, window: dict) -> bool:
        start = pd.Timestamp(window["start_timestamp"])
        end = pd.Timestamp(window["end_timestamp"])
        minutes = (end - start).total_seconds() / 60
        expected = max(1, int(math.ceil(minutes / self.bar_interval_minutes)))
        return int(window.get("bar_count", 0)) >= expected

    def _session_timestamp(self, timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
        return timestamp.replace(
            hour=session_time.hour,
            minute=session_time.minute,
            second=session_time.second,
            microsecond=0,
        )

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        for slot in self.slots:
            if slot["direction"] not in {"long", "short"}:
                raise ValueError(f"Invalid direction for slot {slot['slot_id']}: {slot['direction']}.")
            if slot["min_signal_return_bps"] < 0 or slot["min_signal_return_ticks"] < 0:
                raise ValueError(f"Slot {slot['slot_id']} signal thresholds must be non-negative.")
            if slot["min_source_efficiency"] < 0 or slot["min_source_efficiency"] > 1:
                raise ValueError(f"Slot {slot['slot_id']} min_source_efficiency must be in [0, 1].")
            if slot["min_close_location"] < 0 or slot["min_close_location"] > 1:
                raise ValueError(f"Slot {slot['slot_id']} min_close_location must be in [0, 1].")
            if slot["min_source_range_bps"] < 0:
                raise ValueError(f"Slot {slot['slot_id']} min_source_range_bps must be non-negative.")
            if slot["max_source_range_bps"] is not None and slot["max_source_range_bps"] <= 0:
                raise ValueError(f"Slot {slot['slot_id']} max_source_range_bps must be greater than 0.")
            if slot["stop_pct"] <= 0 or slot["target_r_multiple"] <= 0:
                raise ValueError(f"Slot {slot['slot_id']} stop_pct and target_r_multiple must be greater than 0.")


def _parse_slot(slot: dict, default_source_start, default_tick_size: float) -> dict:
    item = dict(slot or {})
    slot_id = str(item.get("slot_id", item.get("direction", "slot"))).strip()
    if not slot_id:
        raise ValueError("Each intraday momentum priority slot requires a slot_id.")
    return {
        "slot_id": slot_id,
        "param_prefix": str(item.get("param_prefix", slot_id)).strip(),
        "direction": str(item.get("direction", "long")).lower(),
        "source_start": parse_time(item.get("source_start", default_source_start)),
        "signal_time": parse_time(item.get("signal_time", item.get("entry_time", "10:30:00"))),
        "flatten_time": parse_time(item.get("flatten_time", "15:59:00")),
        "min_signal_return_bps": float(item.get("min_signal_return_bps", 0.0)),
        "min_signal_return_ticks": float(item.get("min_signal_return_ticks", 0.0)),
        "min_source_efficiency": float(item.get("min_source_efficiency", 0.0)),
        "min_close_location": float(item.get("min_close_location", 0.0)),
        "min_source_range_bps": float(item.get("min_source_range_bps", 0.0)),
        "max_source_range_bps": (
            None if item.get("max_source_range_bps") is None else float(item.get("max_source_range_bps"))
        ),
        "stop_pct": float(item.get("stop_pct", 0.0035)),
        "target_r_multiple": float(item.get("target_r_multiple", 3.0)),
        "tick_size": float(item.get("tick_size", default_tick_size)),
    }


def _apply_flat_overrides(slots: list[dict], params: dict) -> None:
    for slot in slots:
        prefix = slot["param_prefix"]
        overrides = {
            "min_signal_return_bps": f"{prefix}_min_signal_return_bps",
            "min_signal_return_ticks": f"{prefix}_min_signal_return_ticks",
            "min_source_efficiency": f"{prefix}_min_source_efficiency",
            "min_close_location": f"{prefix}_min_close_location",
            "min_source_range_bps": f"{prefix}_min_source_range_bps",
            "max_source_range_bps": f"{prefix}_max_source_range_bps",
            "stop_pct": f"{prefix}_stop_pct",
            "target_r_multiple": f"{prefix}_target_r_multiple",
        }
        for field, param_key in overrides.items():
            if param_key in params:
                slot[field] = float(params[param_key])
        if f"{prefix}_source_start" in params:
            slot["source_start"] = parse_time(params[f"{prefix}_source_start"])
        if f"{prefix}_signal_time" in params:
            slot["signal_time"] = parse_time(params[f"{prefix}_signal_time"])
        if f"{prefix}_flatten_time" in params:
            slot["flatten_time"] = parse_time(params[f"{prefix}_flatten_time"])
