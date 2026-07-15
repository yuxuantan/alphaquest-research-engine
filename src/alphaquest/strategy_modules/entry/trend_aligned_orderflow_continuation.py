from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class TrendAlignedOrderflowContinuationEntry:
    name = "trend_aligned_orderflow_continuation"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.state_by_day: dict = {}
        self.signal_time = parse_time(params.get("signal_time", "11:30:00"))
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")

        self.short_trend_bars = int(params.get("short_trend_bars", 3))
        self.long_trend_bars = int(params.get("long_trend_bars", 6))
        if self.short_trend_bars <= 0 or self.long_trend_bars <= 0:
            raise ValueError("entry.params.short_trend_bars and long_trend_bars must be positive.")

        self.tick_size = float(params.get("tick_size", 0.25))
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")

        self.min_trend_move_ticks = float(params.get("min_trend_move_ticks", 0.0))
        if self.min_trend_move_ticks < 0:
            raise ValueError("entry.params.min_trend_move_ticks must be non-negative.")
        self.min_trend_move = self.min_trend_move_ticks * self.tick_size

        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.0))
        if self.min_orderflow_imbalance < 0:
            raise ValueError("entry.params.min_orderflow_imbalance must be non-negative.")

        self.min_flow_volume = float(params.get("min_flow_volume", 0.0))
        if self.min_flow_volume < 0:
            raise ValueError("entry.params.min_flow_volume must be non-negative.")

        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError(f"entry.params.flow_mode must be one of {sorted(self._FLOW_COLUMNS)}.")

    def _state(self, session_date) -> dict:
        return self.state_by_day.setdefault(session_date, {"bars": [], "evaluated": False})

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        if timestamp.time() < self.rth_start:
            return None

        session_date = bar.get("session_date", timestamp.date())
        state = self._state(session_date)
        state["bars"].append(bar)
        state["bars"] = state["bars"][-(2 * max(self.short_trend_bars, self.long_trend_bars)) :]

        close_timestamp = self._bar_close_timestamp(timestamp)
        if close_timestamp.time() != self.signal_time:
            return None
        if state["evaluated"]:
            return None
        state["evaluated"] = True

        if trades_today >= int(self.params.get("max_trades_per_day", 1)):
            return None

        if len(state["bars"]) < 2 * max(self.short_trend_bars, self.long_trend_bars):
            return None

        flow = self._bar_flow(bar)
        if flow is None:
            return None
        signed_volume, total_volume, imbalance = flow
        if total_volume < self.min_flow_volume:
            return None

        trend = self._trend_state(state["bars"])
        long_ok = (
            bool(self.params.get("allow_long", True))
            and trend["short_long_ok"]
            and trend["long_long_ok"]
            and imbalance >= self.min_orderflow_imbalance
        )
        short_ok = (
            bool(self.params.get("allow_short", True))
            and trend["short_short_ok"]
            and trend["long_short_ok"]
            and imbalance <= -self.min_orderflow_imbalance
        )
        if not long_ok and not short_ok:
            return None

        direction = "long" if long_ok else "short"
        close = _finite_float(bar.get("close"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        if close is None or high is None or low is None:
            return None

        level_type = f"{direction}_trend_aligned_{self.flow_mode}_orderflow_continuation"
        report_fields = {
            "signal_bar_timestamp": timestamp,
            "signal_close_timestamp": close_timestamp,
            "intended_entry_timestamp": close_timestamp,
            "signal_time": self.signal_time.isoformat(),
            "trend_direction": direction,
            "flow_mode": self.flow_mode,
            "short_trend_bars": self.short_trend_bars,
            "long_trend_bars": self.long_trend_bars,
            "min_trend_move_ticks": self.min_trend_move_ticks,
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "signal_close": close,
            "signal_high": high,
            "signal_low": low,
            "signal_signed_volume": signed_volume,
            "signal_flow_volume": total_volume,
            "signal_orderflow_imbalance": imbalance,
            **trend["report_fields"],
        }
        return Signal(
            direction=direction,
            level_type=level_type,
            swept_level=close,
            sweep_timestamp=timestamp,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=close_timestamp,
            breakout_level=close,
            metadata={**report_fields, "flatten_time": self.params.get("flatten_time")},
            report_fields=report_fields,
        )

    def _trend_state(self, bars: list[pd.Series]) -> dict:
        short = self._window_trend(bars, self.short_trend_bars, "short")
        long = self._window_trend(bars, self.long_trend_bars, "long")
        return {
            "short_long_ok": short["long_ok"],
            "short_short_ok": short["short_ok"],
            "long_long_ok": long["long_ok"],
            "long_short_ok": long["short_ok"],
            "report_fields": {**short["report_fields"], **long["report_fields"]},
        }

    def _window_trend(self, bars: list[pd.Series], window_bars: int, label: str) -> dict:
        previous = bars[-(2 * window_bars) : -window_bars]
        current = bars[-window_bars:]
        prev_high = max(_required_float(bar.get("high"), "high") for bar in previous)
        prev_low = min(_required_float(bar.get("low"), "low") for bar in previous)
        current_high = max(_required_float(bar.get("high"), "high") for bar in current)
        current_low = min(_required_float(bar.get("low"), "low") for bar in current)
        long_ok = current_high >= prev_high + self.min_trend_move and current_low >= prev_low + self.min_trend_move
        short_ok = current_high <= prev_high - self.min_trend_move and current_low <= prev_low - self.min_trend_move
        return {
            "long_ok": long_ok,
            "short_ok": short_ok,
            "report_fields": {
                f"{label}_previous_high": prev_high,
                f"{label}_previous_low": prev_low,
                f"{label}_current_high": current_high,
                f"{label}_current_low": current_low,
            },
        }

    def _bar_flow(self, bar: pd.Series) -> tuple[float, float, float] | None:
        signed_col, total_col = self._FLOW_COLUMNS[self.flow_mode]
        signed = _finite_float(bar.get(signed_col))
        total = _finite_float(bar.get(total_col))
        if signed is None or total is None or total <= 0:
            return None
        imbalance = signed / total
        if not math.isfinite(imbalance):
            return None
        return signed, total, imbalance

    def _bar_close_timestamp(self, timestamp) -> pd.Timestamp:
        return pd.Timestamp(timestamp) + pd.Timedelta(minutes=self.bar_interval_minutes)


def _finite_float(value) -> float | None:
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
