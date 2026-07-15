from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class OvernightInventoryReversionEntry:
    name = "overnight_inventory_reversion"

    def __init__(self, params: dict):
        self.params = params
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "long_sweep": None,
                "short_sweep": None,
                "opening_bar": None,
            },
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= int(self.params.get("max_trades_per_day", 1)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        if timestamp.time() < parse_time(self.params.get("start_time", "09:30:00")):
            return None
        if timestamp.time() > parse_time(self.params.get("end_time", "11:30:00")):
            return None

        overnight_high = _finite_float(bar.get("overnight_high"))
        overnight_low = _finite_float(bar.get("overnight_low"))
        if overnight_high is None or overnight_low is None or overnight_high <= overnight_low:
            return None

        overnight_range = overnight_high - overnight_low
        if overnight_range < float(self.params.get("min_overnight_range_points", 4.0)):
            return None
        max_range = self.params.get("max_overnight_range_points")
        if max_range is not None and overnight_range > float(max_range):
            return None

        state = self._state(bar["session_date"])
        if state["opening_bar"] is None:
            state["opening_bar"] = {
                "timestamp": timestamp,
                "open": float(bar["open"]),
                "close": float(bar["close"]),
            }

        signal = self._existing_sweep_signal(bar, state, overnight_high, overnight_low)
        if signal is not None:
            return signal

        self._record_new_sweeps(bar, state, overnight_high, overnight_low)
        return self._existing_sweep_signal(bar, state, overnight_high, overnight_low)

    def _existing_sweep_signal(
        self,
        bar: pd.Series,
        state: dict,
        overnight_high: float,
        overnight_low: float,
    ) -> Signal | None:
        idx = int(bar.name) if bar.name is not None else 0
        window = int(self.params.get("reclaim_window_bars", 5))

        long_sweep = state.get("long_sweep")
        if long_sweep:
            long_sweep["sweep_low"] = min(long_sweep["sweep_low"], float(bar["low"]))
            long_sweep["sweep_high"] = max(long_sweep["sweep_high"], float(bar["high"]))
            if self._expired(idx, long_sweep, window):
                state["long_sweep"] = None
            elif self.params.get("allow_long", True) and self._long_reclaimed(bar, long_sweep, overnight_high, overnight_low):
                state["long_sweep"] = None
                return self._signal("long", bar, long_sweep, overnight_high, overnight_low)

        short_sweep = state.get("short_sweep")
        if short_sweep:
            short_sweep["sweep_low"] = min(short_sweep["sweep_low"], float(bar["low"]))
            short_sweep["sweep_high"] = max(short_sweep["sweep_high"], float(bar["high"]))
            if self._expired(idx, short_sweep, window):
                state["short_sweep"] = None
            elif self.params.get("allow_short", True) and self._short_reclaimed(bar, short_sweep, overnight_high, overnight_low):
                state["short_sweep"] = None
                return self._signal("short", bar, short_sweep, overnight_high, overnight_low)
        return None

    def _record_new_sweeps(
        self,
        bar: pd.Series,
        state: dict,
        overnight_high: float,
        overnight_low: float,
    ) -> None:
        idx = int(bar.name) if bar.name is not None else 0
        min_extension = float(self.params.get("min_extension_points", 0.25))

        if self.params.get("allow_long", True) and state.get("long_sweep") is None:
            if float(bar["low"]) <= overnight_low - min_extension and self._opening_context_allows("long", state, overnight_high, overnight_low):
                state["long_sweep"] = {
                    "idx": idx,
                    "timestamp": bar["timestamp"],
                    "sweep_low": float(bar["low"]),
                    "sweep_high": float(bar["high"]),
                    "level": overnight_low,
                }

        if self.params.get("allow_short", True) and state.get("short_sweep") is None:
            if float(bar["high"]) >= overnight_high + min_extension and self._opening_context_allows("short", state, overnight_high, overnight_low):
                state["short_sweep"] = {
                    "idx": idx,
                    "timestamp": bar["timestamp"],
                    "sweep_low": float(bar["low"]),
                    "sweep_high": float(bar["high"]),
                    "level": overnight_high,
                }

    def _opening_context_allows(self, direction: str, state: dict, overnight_high: float, overnight_low: float) -> bool:
        if not bool(self.params.get("require_open_outside_range", False)):
            return True
        opening = state.get("opening_bar")
        if opening is None:
            return False
        open_price = float(opening["open"])
        if direction == "long":
            return open_price <= overnight_low
        return open_price >= overnight_high

    def _long_reclaimed(self, bar: pd.Series, sweep: dict, overnight_high: float, overnight_low: float) -> bool:
        close = float(bar["close"])
        tick_size = float(self.params.get("tick_size", 0.25))
        buffer = tick_size * int(self.params.get("reclaim_buffer_ticks", 0))
        if close < self._confirmation_level("long", overnight_high, overnight_low) + buffer:
            return False
        return self._vwap_allows("long", bar)

    def _short_reclaimed(self, bar: pd.Series, sweep: dict, overnight_high: float, overnight_low: float) -> bool:
        close = float(bar["close"])
        tick_size = float(self.params.get("tick_size", 0.25))
        buffer = tick_size * int(self.params.get("reclaim_buffer_ticks", 0))
        if close > self._confirmation_level("short", overnight_high, overnight_low) - buffer:
            return False
        return self._vwap_allows("short", bar)

    def _confirmation_level(self, direction: str, overnight_high: float, overnight_low: float) -> float:
        mode = str(self.params.get("confirmation_mode", "extreme_reclaim")).lower()
        if mode == "midpoint_reclaim":
            return (overnight_high + overnight_low) / 2.0
        if direction == "long":
            return overnight_low
        return overnight_high

    def _vwap_allows(self, direction: str, bar: pd.Series) -> bool:
        mode = str(self.params.get("vwap_filter", "none")).lower()
        if mode in {"", "none", "false"}:
            return True
        vwap = _finite_float(bar.get("vwap"))
        if vwap is None:
            return False
        close = float(bar["close"])
        if mode == "same_side":
            return close <= vwap if direction == "long" else close >= vwap
        if mode == "reclaimed":
            return close >= vwap if direction == "long" else close <= vwap
        raise ValueError(f"Unsupported overnight_inventory_reversion vwap_filter: {mode}")

    def _expired(self, idx: int, sweep: dict, window: int) -> bool:
        bars_between = max(0, idx - int(sweep["idx"]) - 1)
        return bars_between > window

    def _signal(
        self,
        direction: str,
        bar: pd.Series,
        sweep: dict,
        overnight_high: float,
        overnight_low: float,
    ) -> Signal:
        overnight_midpoint = (overnight_high + overnight_low) / 2.0
        confirmation_level = self._confirmation_level(direction, overnight_high, overnight_low)
        confirmation_end = pd.Timestamp(bar["timestamp"]) + pd.Timedelta(
            minutes=float(self.params.get("bar_interval_minutes", 1))
        )
        vwap = _finite_float(bar.get("vwap"))
        opening = self._state(bar["session_date"]).get("opening_bar") or {}
        report_fields = {
            "overnight_high": overnight_high,
            "overnight_low": overnight_low,
            "overnight_midpoint": overnight_midpoint,
            "overnight_range_points": overnight_high - overnight_low,
            "overnight_sweep_timestamp": sweep["timestamp"],
            "overnight_sweep_level": sweep["level"],
            "overnight_sweep_high": sweep["sweep_high"],
            "overnight_sweep_low": sweep["sweep_low"],
            "overnight_reclaim_timestamp": bar["timestamp"],
            "overnight_confirmation_level": confirmation_level,
            "overnight_confirmation_close": float(bar["close"]),
            "overnight_confirmation_high": float(bar["high"]),
            "overnight_confirmation_low": float(bar["low"]),
            "overnight_confirmation_end_timestamp": confirmation_end,
            "opening_bar_timestamp": opening.get("timestamp"),
            "opening_bar_open": opening.get("open"),
            "opening_bar_close": opening.get("close"),
            "session_vwap_at_signal": vwap,
        }
        return Signal(
            direction=direction,
            level_type="overnight_low_reclaim" if direction == "long" else "overnight_high_reclaim",
            swept_level=sweep["level"],
            sweep_timestamp=sweep["timestamp"],
            sweep_high=sweep["sweep_high"],
            sweep_low=sweep["sweep_low"],
            reclaim_timestamp=bar["timestamp"],
            metadata={
                "confirmation_close": float(bar["close"]),
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_end_timestamp": confirmation_end,
                "overnight_high": overnight_high,
                "overnight_low": overnight_low,
                "overnight_midpoint": overnight_midpoint,
                "overnight_confirmation_level": confirmation_level,
                "session_vwap_at_signal": vwap,
            },
            report_fields=report_fields,
        )


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
