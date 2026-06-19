from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


FLOW_COLUMNS = {
    "signed_volume": ("signed_volume", "volume"),
    "signed": ("signed_volume", "volume"),
    "large10": ("large10_signed_volume", "large10_volume"),
    "large10_imbalance": ("large10_signed_volume", "large10_volume"),
    "large20": ("large20_signed_volume", "large20_volume"),
    "large20_imbalance": ("large20_signed_volume", "large20_volume"),
}


class PriorSessionBenchmarkOrderflowReactionEntry:
    name = "prior_session_benchmark_orderflow_reaction"

    def __init__(self, params: dict):
        self.params = params
        self.level_set = str(params.get("level_set", "previous_close")).lower()
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        self.start_time = parse_time(params.get("start_time", "09:35:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:45:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_probe_ticks = float(params.get("min_probe_ticks", 1))
        self.reclaim_buffer_ticks = float(params.get("reclaim_buffer_ticks", 0))
        self.reclaim_window_bars = int(params.get("reclaim_window_bars", 2))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.02))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        t = timestamp.time()
        if t < self.start_time or t > self.end_time:
            return None

        session_date = bar.get("session_date", timestamp.date())
        state = self._state(session_date)
        state["bar_index"] += 1

        levels = self._levels(bar)
        for level in levels:
            signal = self._process_level(bar, state, level)
            if signal is not None:
                return signal
        return None

    def _process_level(self, bar: pd.Series, state: dict, level: dict) -> Signal | None:
        bar_index = state["bar_index"]
        threshold = self.min_probe_ticks * self.tick_size
        buffer = self.reclaim_buffer_ticks * self.tick_size
        price = level["price"]

        candidates = []
        if self.allow_long:
            candidates.append(("long", f"{level['level_type']}:long"))
        if self.allow_short:
            candidates.append(("short", f"{level['level_type']}:short"))

        for direction, key in candidates:
            if key in state["traded_keys"]:
                continue
            sweep = state["sweeps"].get(key)
            if sweep is not None:
                sweep["sweep_low"] = min(sweep["sweep_low"], float(bar["low"]))
                sweep["sweep_high"] = max(sweep["sweep_high"], float(bar["high"]))

            if sweep is None:
                if direction == "long" and float(bar["low"]) <= price - threshold:
                    sweep = self._new_sweep(bar, level, direction, bar_index)
                    state["sweeps"][key] = sweep
                elif direction == "short" and float(bar["high"]) >= price + threshold:
                    sweep = self._new_sweep(bar, level, direction, bar_index)
                    state["sweeps"][key] = sweep

            if sweep is None:
                continue
            if bar_index - sweep["bar_index"] > self.reclaim_window_bars:
                state["sweeps"].pop(key, None)
                continue
            if not self._reclaimed(bar, direction, price, buffer):
                continue
            flow = self._flow(bar)
            if flow is None:
                continue
            imbalance = flow["imbalance"]
            if direction == "long" and imbalance < self.min_orderflow_imbalance:
                continue
            if direction == "short" and imbalance > -self.min_orderflow_imbalance:
                continue

            state["sweeps"].pop(key, None)
            state["traded_keys"].add(key)
            return self._signal(bar, sweep, flow)
        return None

    def _new_sweep(self, bar: pd.Series, level: dict, direction: str, bar_index: int) -> dict:
        return {
            **level,
            "direction": direction,
            "bar_index": bar_index,
            "sweep_timestamp": pd.Timestamp(bar["timestamp"]),
            "sweep_low": float(bar["low"]),
            "sweep_high": float(bar["high"]),
        }

    def _reclaimed(self, bar: pd.Series, direction: str, price: float, buffer: float) -> bool:
        close = float(bar["close"])
        if direction == "long":
            return close >= price + buffer
        return close <= price - buffer

    def _levels(self, bar: pd.Series) -> list[dict]:
        candidates = []
        if self.level_set in {"previous_close", "prev_close", "close", "both", "open_close"}:
            value = _finite_float(bar.get("prev_rth_close"))
            if value is not None:
                candidates.append({"level_type": "previous_rth_close", "price": value})
        if self.level_set in {"previous_open", "prev_open", "open", "both", "open_close"}:
            value = _finite_float(bar.get("prev_rth_open"))
            if value is not None:
                candidates.append({"level_type": "previous_rth_open", "price": value})
        return candidates

    def _flow(self, bar: pd.Series) -> dict | None:
        columns = FLOW_COLUMNS.get(self.flow_mode)
        if columns is None:
            return None
        signed_col, total_col = columns
        signed = _finite_float(bar.get(signed_col))
        total = _finite_float(bar.get(total_col))
        if signed is None or total is None or total <= 0:
            return None
        return {
            "signed_volume": signed,
            "total_volume": total,
            "imbalance": signed / total,
            "signed_column": signed_col,
            "total_column": total_col,
        }

    def _signal(self, bar: pd.Series, sweep: dict, flow: dict) -> Signal:
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        flatten_label = self.flatten_time.strftime("%H:%M:%S")
        report_fields = {
            "setup_mode": "prior_session_benchmark_orderflow_reaction",
            "feature_method": "previous_rth_open_close_completed_bar_counterflow",
            "benchmark_level_type": sweep["level_type"],
            "benchmark_level": sweep["price"],
            "sweep_timestamp": sweep["sweep_timestamp"],
            "sweep_high": sweep["sweep_high"],
            "sweep_low": sweep["sweep_low"],
            "reclaim_timestamp": signal_timestamp,
            "confirmation_close": float(bar["close"]),
            "flow_mode": self.flow_mode,
            "flow_signed_column": flow["signed_column"],
            "flow_total_column": flow["total_column"],
            "confirmation_signed_volume": flow["signed_volume"],
            "confirmation_total_volume": flow["total_volume"],
            "confirmation_orderflow_imbalance": flow["imbalance"],
            "min_probe_ticks": self.min_probe_ticks,
            "reclaim_buffer_ticks": self.reclaim_buffer_ticks,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "signal_flatten_time": flatten_label,
        }
        return Signal(
            direction=sweep["direction"],
            level_type=sweep["level_type"],
            swept_level=sweep["price"],
            sweep_timestamp=sweep["sweep_timestamp"],
            sweep_high=sweep["sweep_high"],
            sweep_low=sweep["sweep_low"],
            reclaim_timestamp=signal_timestamp,
            metadata={
                "flow_mode": self.flow_mode,
                "orderflow_imbalance": flow["imbalance"],
                "min_probe_ticks": self.min_probe_ticks,
                "reclaim_buffer_ticks": self.reclaim_buffer_ticks,
                "min_orderflow_imbalance": self.min_orderflow_imbalance,
                "flatten_time": flatten_label,
            },
            report_fields=report_fields,
        )

    def _state(self, session_date) -> dict:
        return self.state_by_day.setdefault(
            session_date,
            {
                "bar_index": -1,
                "sweeps": {},
                "traded_keys": set(),
            },
        )

    def _validate(self) -> None:
        if self.level_set not in {
            "previous_close",
            "prev_close",
            "close",
            "previous_open",
            "prev_open",
            "open",
            "both",
            "open_close",
        }:
            raise ValueError("level_set must be previous_close, previous_open, or both.")
        if self.flow_mode not in FLOW_COLUMNS:
            raise ValueError(f"flow_mode must be one of: {sorted(FLOW_COLUMNS)}.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.min_probe_ticks < 0 or self.reclaim_buffer_ticks < 0:
            raise ValueError("probe and reclaim buffers must be non-negative.")
        if self.reclaim_window_bars < 0:
            raise ValueError("reclaim_window_bars must be non-negative.")
        if self.min_orderflow_imbalance < 0:
            raise ValueError("min_orderflow_imbalance must be non-negative.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
