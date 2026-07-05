from __future__ import annotations

import math
from collections import deque

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class LiquidityInversionFvgEntry:
    name = "liquidity_inversion_fvg"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "prior_two_sided")).lower()
        self.setup_start_time = parse_time(params.get("setup_start_time", "09:30:00"))
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "14:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.sweep_buffer_ticks = int(params.get("sweep_buffer_ticks", 0))
        self.min_gap_ticks = int(params.get("min_gap_ticks", 2))
        self.inversion_buffer_ticks = int(params.get("inversion_buffer_ticks", 0))
        self.max_inversion_bars = int(params.get("max_inversion_bars", 6))
        self._bars: deque[dict] = deque(maxlen=3)
        self._session_date = None
        self._session_bar_index = 0
        self._current_high: float | None = None
        self._current_low: float | None = None
        self._previous_session_high: float | None = None
        self._previous_session_low: float | None = None
        self._state = self._new_state()
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _session_date(bar, timestamp)
        if session_date != self._session_date:
            self._roll_session(session_date)

        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        pre_session_high = self._current_high
        pre_session_low = self._current_low
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)

        self._record_sweep(bar, bar_close, pre_session_high, pre_session_low)
        self._record_gap(bar, timestamp)
        signal = self._maybe_signal(bar, bar_close, trades_today)
        self._finish_bar(high, low, close, timestamp)
        return signal

    def _roll_session(self, session_date) -> None:
        if self._session_date is not None and self._current_high is not None and self._current_low is not None:
            self._previous_session_high = self._current_high
            self._previous_session_low = self._current_low
        self._session_date = session_date
        self._session_bar_index = 0
        self._current_high = None
        self._current_low = None
        self._bars.clear()
        self._state = self._new_state()

    def _record_sweep(
        self,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        pre_session_high: float | None,
        pre_session_low: float | None,
    ) -> None:
        if bar_close.time() < self.setup_start_time or bar_close.time() > self.end_time:
            return
        high = float(bar["high"])
        low = float(bar["low"])
        timestamp = pd.Timestamp(bar["timestamp"])
        buffer = self.sweep_buffer_ticks * self.tick_size

        if self._allows_short():
            ref_high, ref_type = self._high_reference(pre_session_high)
            if _finite(ref_high) and high >= float(ref_high) + buffer:
                short = self._state["short"]
                if not short["swept"]:
                    short["swept"] = True
                    short["reference_level"] = float(ref_high)
                    short["reference_type"] = ref_type
                    short["sweep_timestamp"] = timestamp
                short["protected_extreme"] = max(float(short.get("protected_extreme", high)), high)

        if self._allows_long():
            ref_low, ref_type = self._low_reference(pre_session_low)
            if _finite(ref_low) and low <= float(ref_low) - buffer:
                long = self._state["long"]
                if not long["swept"]:
                    long["swept"] = True
                    long["reference_level"] = float(ref_low)
                    long["reference_type"] = ref_type
                    long["sweep_timestamp"] = timestamp
                long["protected_extreme"] = min(float(long.get("protected_extreme", low)), low)

    def _record_gap(self, bar: pd.Series, timestamp: pd.Timestamp) -> None:
        if len(self._bars) < 2:
            return
        two_back = self._bars[-2]
        high = float(bar["high"])
        low = float(bar["low"])
        min_gap = self.min_gap_ticks * self.tick_size

        bullish_gap = low - float(two_back["high"])
        if bullish_gap >= min_gap and self._state["short"]["swept"]:
            self._state["short"]["gap"] = {
                "gap_type": "bullish_fvg",
                "bottom": float(two_back["high"]),
                "top": low,
                "created_index": self._session_bar_index,
                "created_timestamp": timestamp,
            }

        bearish_gap = float(two_back["low"]) - high
        if bearish_gap >= min_gap and self._state["long"]["swept"]:
            self._state["long"]["gap"] = {
                "gap_type": "bearish_fvg",
                "bottom": high,
                "top": float(two_back["low"]),
                "created_index": self._session_bar_index,
                "created_timestamp": timestamp,
            }

    def _maybe_signal(self, bar: pd.Series, bar_close: pd.Timestamp, trades_today: int) -> Signal | None:
        if trades_today >= self.max_trades_per_day or self._state["signaled"]:
            return None
        if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
            return None

        close = float(bar["close"])
        inversion = self.inversion_buffer_ticks * self.tick_size
        short_gap = self._active_gap("short")
        if short_gap is not None and close <= float(short_gap["bottom"]) - inversion:
            self._state["signaled"] = True
            return self._signal("short", bar, bar_close, short_gap)

        long_gap = self._active_gap("long")
        if long_gap is not None and close >= float(long_gap["top"]) + inversion:
            self._state["signaled"] = True
            return self._signal("long", bar, bar_close, long_gap)
        return None

    def _active_gap(self, direction: str) -> dict | None:
        gap = self._state[direction].get("gap")
        if not gap:
            return None
        age = self._session_bar_index - int(gap["created_index"])
        if age <= 0:
            return None
        if age > self.max_inversion_bars:
            self._state[direction]["gap"] = None
            return None
        return gap

    def _signal(self, direction: str, bar: pd.Series, signal_timestamp: pd.Timestamp, gap: dict) -> Signal:
        timestamp = pd.Timestamp(bar["timestamp"])
        side = self._state[direction]
        protected = float(side["protected_extreme"])
        reference_level = float(side["reference_level"])
        report_fields = {
            "academic_source_key": "chartfanatics_liquidity_inversion_fvg_lo_mamaysky_wang_osler_barriers",
            "setup_mode": self.setup_mode,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "liquidity_reference_type": side["reference_type"],
            "liquidity_reference_level": reference_level,
            "liquidity_sweep_timestamp": side["sweep_timestamp"],
            "protected_extreme": protected,
            "fvg_type": gap["gap_type"],
            "fvg_bottom": float(gap["bottom"]),
            "fvg_top": float(gap["top"]),
            "fvg_created_timestamp": gap["created_timestamp"],
            "fvg_age_bars": self._session_bar_index - int(gap["created_index"]),
            "sweep_buffer_ticks": self.sweep_buffer_ticks,
            "min_gap_ticks": self.min_gap_ticks,
            "inversion_buffer_ticks": self.inversion_buffer_ticks,
            "max_inversion_bars": self.max_inversion_bars,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"liquidity_inversion_fvg_{direction}",
            swept_level=reference_level,
            sweep_timestamp=side["sweep_timestamp"],
            sweep_high=protected if direction == "short" else float(bar["high"]),
            sweep_low=protected if direction == "long" else float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            breakout_level=float(gap["bottom"] if direction == "short" else gap["top"]),
            metadata={
                "setup_mode": self.setup_mode,
                "liquidity_reference_type": side["reference_type"],
                "liquidity_reference_level": reference_level,
                "protected_extreme": protected,
                "fvg_type": gap["gap_type"],
                "fvg_bottom": float(gap["bottom"]),
                "fvg_top": float(gap["top"]),
                "sweep_buffer_ticks": self.sweep_buffer_ticks,
                "min_gap_ticks": self.min_gap_ticks,
                "inversion_buffer_ticks": self.inversion_buffer_ticks,
                "max_inversion_bars": self.max_inversion_bars,
            },
            report_fields=report_fields,
        )

    def _finish_bar(self, high: float, low: float, close: float, timestamp: pd.Timestamp) -> None:
        self._current_high = high if self._current_high is None else max(self._current_high, high)
        self._current_low = low if self._current_low is None else min(self._current_low, low)
        self._bars.append({"timestamp": timestamp, "high": high, "low": low, "close": close})
        self._session_bar_index += 1

    def _high_reference(self, pre_session_high: float | None) -> tuple[float | None, str]:
        if self.setup_mode in {"prior_high_short", "prior_two_sided"}:
            return self._previous_session_high, "previous_session_high"
        return pre_session_high, "current_session_high"

    def _low_reference(self, pre_session_low: float | None) -> tuple[float | None, str]:
        if self.setup_mode in {"prior_low_long", "prior_two_sided"}:
            return self._previous_session_low, "previous_session_low"
        return pre_session_low, "current_session_low"

    def _allows_short(self) -> bool:
        return self.setup_mode in {"prior_high_short", "prior_two_sided", "session_high_short", "session_two_sided"}

    def _allows_long(self) -> bool:
        return self.setup_mode in {"prior_low_long", "prior_two_sided", "session_low_long", "session_two_sided"}

    def _validate(self) -> None:
        allowed = {
            "prior_high_short",
            "prior_low_long",
            "prior_two_sided",
            "session_high_short",
            "session_low_long",
            "session_two_sided",
        }
        if self.setup_mode not in allowed:
            raise ValueError(f"setup_mode must be one of {sorted(allowed)}.")
        if self.tick_size <= 0 or self.bar_interval_minutes <= 0:
            raise ValueError("tick_size and bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if min(self.sweep_buffer_ticks, self.min_gap_ticks, self.inversion_buffer_ticks, self.max_inversion_bars) < 0:
            raise ValueError("tick and bar thresholds must be non-negative.")

    @staticmethod
    def _new_state() -> dict:
        return {
            "signaled": False,
            "short": {"swept": False, "gap": None},
            "long": {"swept": False, "gap": None},
        }


def _session_date(bar: pd.Series, timestamp: pd.Timestamp):
    value = bar.get("session_date")
    if value is None or pd.isna(value):
        return timestamp.date()
    return pd.Timestamp(value).date()


def _finite(value) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return math.isfinite(number)
