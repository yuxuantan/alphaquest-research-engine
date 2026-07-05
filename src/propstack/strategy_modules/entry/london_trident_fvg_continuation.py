from __future__ import annotations

import math
from collections import deque

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class LondonTridentFvgContinuationEntry:
    name = "london_trident_fvg_continuation"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided")).lower()
        self.fvg_start_time = parse_time(params.get("fvg_start_time", "02:30:00"))
        self.fvg_end_time = parse_time(params.get("fvg_end_time", "04:00:00"))
        self.start_time = parse_time(params.get("start_time", "03:00:00"))
        self.end_time = parse_time(params.get("end_time", "06:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "06:55:00"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 30))
        self.min_gap_ticks = int(params.get("min_gap_ticks", 2))
        self.max_doji_body_ratio = float(params.get("max_doji_body_ratio", 0.35))
        self.mid_ema_period = int(params.get("mid_ema_period", 13))
        self.confirmation_buffer_ticks = int(params.get("confirmation_buffer_ticks", 0))
        self.require_200_ema_bias = bool(params.get("require_200_ema_bias", True))
        self.require_eth = bool(params.get("require_eth", True))
        self._bars: deque[dict] = deque(maxlen=5)
        self._session_date = None
        self._signaled_sessions: set = set()
        self._ema_periods = sorted({5, 9, self.mid_ema_period, 21, 200})
        self._ema_values: dict[int, float | None] = {period: None for period in self._ema_periods}
        self._ema_counts: dict[int, int] = {period: 0 for period in self._ema_periods}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        if session_date != self._session_date:
            self._session_date = session_date
            self._bars.clear()
        self._update_emas(float(bar["close"]))
        self._bars.append(_bar_record(bar, timestamp))

        if trades_today >= self.max_trades_per_day or session_date in self._signaled_sessions:
            return None
        if self.require_eth and not bool(bar.get("is_eth", False)):
            return None
        if len(self._bars) < 5:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
            return None

        first = self._bars[-5]
        third = self._bars[-3]
        doji = self._bars[-2]
        confirm = self._bars[-1]
        if not all(record["session_date"] == session_date for record in [first, third, doji, confirm]):
            return None
        if third["timestamp"].time() < self.fvg_start_time or third["timestamp"].time() > self.fvg_end_time:
            return None
        if not self._small_body(doji):
            return None

        signal = self._maybe_long(first, third, doji, confirm, bar_close)
        if signal is None:
            signal = self._maybe_short(first, third, doji, confirm, bar_close)
        if signal is not None:
            self._signaled_sessions.add(session_date)
        return signal

    def _maybe_long(
        self,
        first: dict,
        third: dict,
        doji: dict,
        confirm: dict,
        signal_timestamp: pd.Timestamp,
    ) -> Signal | None:
        if self.setup_mode not in {"long", "two_sided"}:
            return None
        gap = third["low"] - first["high"]
        if gap < self.min_gap_ticks * self.tick_size or not self._ema_stack_ok("long", confirm["close"]):
            return None
        gap_bottom = first["high"]
        gap_top = third["low"]
        midpoint = (gap_bottom + gap_top) / 2.0
        body_low = min(doji["open"], doji["close"])
        if doji["low"] > midpoint or body_low < midpoint:
            return None
        if confirm["close"] < doji["high"] + self.confirmation_buffer_ticks * self.tick_size:
            return None
        return self._signal("long", first, third, doji, confirm, signal_timestamp, gap_bottom, gap_top, midpoint)

    def _maybe_short(
        self,
        first: dict,
        third: dict,
        doji: dict,
        confirm: dict,
        signal_timestamp: pd.Timestamp,
    ) -> Signal | None:
        if self.setup_mode not in {"short", "two_sided"}:
            return None
        gap = first["low"] - third["high"]
        if gap < self.min_gap_ticks * self.tick_size or not self._ema_stack_ok("short", confirm["close"]):
            return None
        gap_bottom = third["high"]
        gap_top = first["low"]
        midpoint = (gap_bottom + gap_top) / 2.0
        body_high = max(doji["open"], doji["close"])
        if doji["high"] < midpoint or body_high > midpoint:
            return None
        if confirm["close"] > doji["low"] - self.confirmation_buffer_ticks * self.tick_size:
            return None
        return self._signal("short", first, third, doji, confirm, signal_timestamp, gap_bottom, gap_top, midpoint)

    def _signal(
        self,
        direction: str,
        first: dict,
        third: dict,
        doji: dict,
        confirm: dict,
        signal_timestamp: pd.Timestamp,
        gap_bottom: float,
        gap_top: float,
        midpoint: float,
    ) -> Signal:
        report_fields = {
            "academic_source_key": "chartfanatics_unique_high_rr_london_trident_fvg",
            "setup_mode": self.setup_mode,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_direction": direction,
            "fvg_first_timestamp": first["timestamp"],
            "fvg_third_timestamp": third["timestamp"],
            "doji_timestamp": doji["timestamp"],
            "confirmation_timestamp": confirm["timestamp"],
            "fvg_bottom": gap_bottom,
            "fvg_top": gap_top,
            "fvg_midpoint": midpoint,
            "doji_high": doji["high"],
            "doji_low": doji["low"],
            "confirmation_close": confirm["close"],
            "min_gap_ticks": self.min_gap_ticks,
            "max_doji_body_ratio": self.max_doji_body_ratio,
            "mid_ema_period": self.mid_ema_period,
            "confirmation_buffer_ticks": self.confirmation_buffer_ticks,
            "require_200_ema_bias": self.require_200_ema_bias,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        stop_low = min(third["low"], doji["low"])
        stop_high = max(third["high"], doji["high"])
        return Signal(
            direction=direction,
            level_type=f"london_trident_fvg_{direction}_continuation",
            swept_level=midpoint,
            sweep_timestamp=third["timestamp"],
            sweep_high=stop_high if direction == "short" else confirm["high"],
            sweep_low=stop_low if direction == "long" else confirm["low"],
            reclaim_timestamp=signal_timestamp,
            breakout_level=doji["high"] if direction == "long" else doji["low"],
            metadata={
                "setup_mode": self.setup_mode,
                "fvg_bottom": gap_bottom,
                "fvg_top": gap_top,
                "fvg_midpoint": midpoint,
                "doji_high": doji["high"],
                "doji_low": doji["low"],
                "min_gap_ticks": self.min_gap_ticks,
                "max_doji_body_ratio": self.max_doji_body_ratio,
                "mid_ema_period": self.mid_ema_period,
                "confirmation_buffer_ticks": self.confirmation_buffer_ticks,
            },
            report_fields=report_fields,
        )

    def _small_body(self, record: dict) -> bool:
        candle_range = record["high"] - record["low"]
        if candle_range <= 0:
            return False
        body = abs(record["close"] - record["open"])
        return body / candle_range <= self.max_doji_body_ratio

    def _update_emas(self, close: float) -> None:
        for period in self._ema_periods:
            prior = self._ema_values[period]
            alpha = 2.0 / (period + 1.0)
            self._ema_values[period] = close if prior is None else alpha * close + (1.0 - alpha) * prior
            self._ema_counts[period] += 1

    def _ema_stack_ok(self, direction: str, close: float) -> bool:
        for period in [5, 9, self.mid_ema_period, 21]:
            if self._ema_counts[period] < period or not _finite(self._ema_values[period]):
                return False
        ema5 = float(self._ema_values[5])
        ema9 = float(self._ema_values[9])
        ema_mid = float(self._ema_values[self.mid_ema_period])
        ema21 = float(self._ema_values[21])
        if self.require_200_ema_bias:
            if self._ema_counts[200] < 200 or not _finite(self._ema_values[200]):
                return False
            ema200 = float(self._ema_values[200])
        else:
            ema200 = None
        if direction == "long":
            stacked = ema5 > ema9 > ema_mid > ema21
            return stacked and (ema200 is None or close > ema200)
        stacked = ema5 < ema9 < ema_mid < ema21
        return stacked and (ema200 is None or close < ema200)

    def _validate(self) -> None:
        if self.setup_mode not in {"long", "short", "two_sided"}:
            raise ValueError("setup_mode must be long, short, or two_sided.")
        if self.tick_size <= 0 or self.bar_interval_minutes <= 0:
            raise ValueError("tick_size and bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.min_gap_ticks < 0 or self.confirmation_buffer_ticks < 0:
            raise ValueError("min_gap_ticks and confirmation_buffer_ticks must be non-negative.")
        if not 0 < self.max_doji_body_ratio <= 1:
            raise ValueError("max_doji_body_ratio must be in (0, 1].")
        if self.mid_ema_period not in {13, 15}:
            raise ValueError("mid_ema_period must be 13 or 15.")


def _bar_record(bar: pd.Series, timestamp: pd.Timestamp) -> dict:
    return {
        "timestamp": timestamp,
        "session_date": bar.get("session_date", timestamp.date()),
        "open": float(bar["open"]),
        "high": float(bar["high"]),
        "low": float(bar["low"]),
        "close": float(bar["close"]),
    }


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
