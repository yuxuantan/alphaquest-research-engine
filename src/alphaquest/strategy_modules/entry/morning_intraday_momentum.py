from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class MorningIntradayMomentumEntry:
    name = "morning_intraday_momentum"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "long_only_strength")).lower()
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.signal_time = parse_time(params.get("signal_time", "10:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_signal_return_ticks = float(params.get("min_signal_return_ticks", 0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(session_date, {"source_window": None, "signaled": False})

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        if self.tick_size <= 0 or self.bar_interval_minutes <= 0:
            raise ValueError("tick_size and bar_interval_minutes must be greater than 0.")

        timestamp = pd.Timestamp(bar["timestamp"])
        state = self._state(bar["session_date"])
        if state["signaled"]:
            return None

        source_start = self._session_timestamp(timestamp, self.rth_start)
        signal_timestamp = self._session_timestamp(timestamp, self.signal_time)
        bar_close = self._bar_close_timestamp(timestamp)
        if timestamp >= source_start and bar_close <= signal_timestamp:
            state["source_window"] = self._aggregate_bar(
                state["source_window"],
                bar,
                source_start,
                signal_timestamp,
            )

        if bar_close != signal_timestamp:
            return None

        signal = self._signal(bar, state, signal_timestamp)
        if signal is not None:
            state["signaled"] = True
        return signal

    def _signal(self, bar: pd.Series, state: dict, signal_timestamp: pd.Timestamp) -> Signal | None:
        source = state.get("source_window")
        if not source or not self._window_complete(source):
            return None

        source_open = float(source["open"])
        source_close = float(source["close"])
        source_return_points = source_close - source_open
        source_return_ticks = source_return_points / self.tick_size
        if abs(source_return_ticks) < self.min_signal_return_ticks:
            return None

        direction = self._direction(source_return_points)
        if direction is None:
            return None
        if direction == "long" and not self.allow_long:
            return None
        if direction == "short" and not self.allow_short:
            return None

        source_range = float(source["high"]) - float(source["low"])
        source_volume_ratio = _finite_float(source.get("avg_volume_ratio"))
        if self.setup_mode in {"volume_volatility_conditioned", "high_volume_morning_strength"}:
            min_volume_ratio = float(self.params.get("min_source_window_volume_ratio", 1.0))
            min_range = float(self.params.get("min_source_window_range_points", 0.0))
            if source_volume_ratio is None or source_volume_ratio < min_volume_ratio:
                return None
            if source_range < min_range:
                return None

        report_fields = {
            "academic_source_key": "gao_han_li_zhou_2018_market_intraday_momentum",
            "setup_mode": self.setup_mode,
            "source_return_reference": "rth_open_to_signal_close",
            "source_window_start_timestamp": source["start_timestamp"],
            "source_window_end_timestamp": source["end_timestamp"],
            "source_window_open": source_open,
            "source_window_high": float(source["high"]),
            "source_window_low": float(source["low"]),
            "source_window_close": source_close,
            "source_window_return_points": source_return_points,
            "source_window_return_ticks": source_return_ticks,
            "source_window_range_points": source_range,
            "source_window_volume": float(source["volume"]),
            "source_window_avg_volume_ratio": source_volume_ratio,
            "morning_momentum_signal_timestamp": signal_timestamp,
            "morning_momentum_entry_window_start": signal_timestamp,
            "morning_momentum_entry_window_end": signal_timestamp + pd.Timedelta(minutes=self.bar_interval_minutes),
            "min_signal_return_ticks": self.min_signal_return_ticks,
            "min_source_window_volume_ratio": self.params.get("min_source_window_volume_ratio"),
            "min_source_window_range_points": self.params.get("min_source_window_range_points"),
        }
        return Signal(
            direction=direction,
            level_type=f"morning_intraday_momentum_{self.setup_mode}",
            swept_level=source_open,
            sweep_timestamp=source["start_timestamp"],
            sweep_high=float(source["high"]),
            sweep_low=float(source["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_close": float(bar["close"]),
                "source_window_return_ticks": source_return_ticks,
                "setup_mode": self.setup_mode,
            },
            report_fields=report_fields,
        )

    def _direction(self, source_return_points: float) -> str | None:
        if source_return_points == 0:
            return None
        if self.setup_mode in {"long_only_strength", "high_volume_morning_strength"}:
            return "long" if source_return_points > 0 else None
        if self.setup_mode in {"short_only_weakness"}:
            return "short" if source_return_points < 0 else None
        if self.setup_mode in {"two_sided_continuation", "volume_volatility_conditioned"}:
            return "long" if source_return_points > 0 else "short"
        raise ValueError(f"Unknown morning intraday momentum setup_mode: {self.setup_mode}")

    def _aggregate_bar(self, aggregate: dict | None, bar: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> dict:
        volume_ratio = _finite_float(bar.get("volume_ratio"))
        if aggregate is None or aggregate.get("start_timestamp") != start or aggregate.get("end_timestamp") != end:
            return {
                "start_timestamp": start,
                "end_timestamp": end,
                "open": float(bar["open"]),
                "high": float(bar["high"]),
                "low": float(bar["low"]),
                "close": float(bar["close"]),
                "volume": float(bar.get("volume", 0.0)),
                "volume_ratio_sum": volume_ratio or 0.0,
                "volume_ratio_count": 1 if volume_ratio is not None else 0,
                "avg_volume_ratio": volume_ratio,
                "bar_count": 1,
            }

        aggregate["high"] = max(float(aggregate["high"]), float(bar["high"]))
        aggregate["low"] = min(float(aggregate["low"]), float(bar["low"]))
        aggregate["close"] = float(bar["close"])
        aggregate["volume"] = float(aggregate["volume"]) + float(bar.get("volume", 0.0))
        aggregate["bar_count"] += 1
        if volume_ratio is not None:
            aggregate["volume_ratio_sum"] = float(aggregate["volume_ratio_sum"]) + volume_ratio
            aggregate["volume_ratio_count"] = int(aggregate["volume_ratio_count"]) + 1
            aggregate["avg_volume_ratio"] = float(aggregate["volume_ratio_sum"]) / int(aggregate["volume_ratio_count"])
        return aggregate

    def _window_complete(self, window: dict) -> bool:
        start = pd.Timestamp(window["start_timestamp"])
        end = pd.Timestamp(window["end_timestamp"])
        minutes = (end - start).total_seconds() / 60
        expected = max(1, int(math.ceil(minutes / self.bar_interval_minutes)))
        return int(window.get("bar_count", 0)) >= expected

    def _bar_close_timestamp(self, timestamp: pd.Timestamp) -> pd.Timestamp:
        return timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)

    def _session_timestamp(self, timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
        return timestamp.replace(
            hour=session_time.hour,
            minute=session_time.minute,
            second=session_time.second,
            microsecond=0,
        )


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
