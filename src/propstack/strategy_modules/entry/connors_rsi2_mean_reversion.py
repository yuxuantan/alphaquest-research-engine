from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class ConnorsRsi2MeanReversionEntry:
    name = "connors_rsi2_mean_reversion"

    _MODES = {"long_pullback_uptrend", "short_bounce_downtrend", "two_sided_trend_reversion"}
    _TREND_FILTERS = {"none", "ma", "vwap", "ma_and_vwap"}

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_trend_reversion")).lower()
        if self.setup_mode not in self._MODES:
            raise ValueError(f"entry.params.setup_mode must be one of {sorted(self._MODES)}.")

        self.trend_filter = str(params.get("trend_filter", "ma")).lower()
        if self.trend_filter not in self._TREND_FILTERS:
            raise ValueError(f"entry.params.trend_filter must be one of {sorted(self._TREND_FILTERS)}.")

        self.rsi_period = int(params.get("rsi_period", 2))
        self.moving_average_period = int(params.get("moving_average_period", 200))
        if self.rsi_period <= 0:
            raise ValueError("entry.params.rsi_period must be greater than 0.")
        if self.moving_average_period <= 0:
            raise ValueError("entry.params.moving_average_period must be greater than 0.")

        self.tick_size = float(params.get("tick_size", 0.25))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        if self.tick_size <= 0 or self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.tick_size and bar_interval_minutes must be greater than 0.")

        self.oversold_rsi = float(params.get("oversold_rsi", 10.0))
        self.overbought_rsi = float(params.get("overbought_rsi", 90.0))
        self.min_vwap_extension_ticks = float(params.get("min_vwap_extension_ticks", 0.0))
        self.earliest_entry_time = parse_time(params.get("earliest_entry_time", "09:35:00"))
        self.latest_entry_time = parse_time(params.get("latest_entry_time", "15:30:00"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.history: list[dict] = []
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(session_date, {"signaled": False})

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        close = _finite_float(bar.get("close"))
        if close is None:
            return None

        self.history.append({"close": close})
        max_history = max(self.moving_average_period + 5, self.rsi_period + 5)
        if len(self.history) > max_history:
            self.history = self.history[-max_history:]

        if trades_today >= self.max_trades_per_day:
            return None
        state = self._state(bar["session_date"])
        if state["signaled"]:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() < self.earliest_entry_time or bar_close.time() > self.latest_entry_time:
            return None

        rsi = _rsi([item["close"] for item in self.history], self.rsi_period)
        ma = _sma([item["close"] for item in self.history], self.moving_average_period)
        if rsi is None or ma is None:
            return None

        direction = self._direction(close, rsi, ma, bar)
        if direction is None:
            return None

        state["signaled"] = True
        vwap = _finite_float(bar.get("vwap"))
        signal = Signal(
            direction=direction,
            level_type=f"connors_rsi2_{self.setup_mode}",
            swept_level=close,
            sweep_timestamp=bar_close,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar_close,
            metadata={
                "stop_pct": float(self.params.get("stop_pct", 0.003)),
                "target_r_multiple": float(self.params.get("target_r_multiple", 1.5)),
                "flatten_time": self.params.get("flatten_time", "15:59:00"),
                "rsi2": rsi,
                "moving_average": ma,
                "trend_filter": self.trend_filter,
            },
            report_fields={
                "academic_source_key": "connors_alvarez_rsi2_short_term_mean_reversion",
                "setup_mode": self.setup_mode,
                "rsi_period": self.rsi_period,
                "rsi_value": rsi,
                "oversold_rsi": self.oversold_rsi,
                "overbought_rsi": self.overbought_rsi,
                "moving_average_period": self.moving_average_period,
                "moving_average": ma,
                "trend_filter": self.trend_filter,
                "vwap": vwap,
                "min_vwap_extension_ticks": self.min_vwap_extension_ticks,
                "signal_timestamp": bar_close,
                "signal_close": close,
            },
        )
        return signal

    def _direction(self, close: float, rsi: float, ma: float, bar: pd.Series) -> str | None:
        if self.setup_mode in {"long_pullback_uptrend", "two_sided_trend_reversion"}:
            if self.allow_long and rsi <= self.oversold_rsi and self._passes_trend("long", close, ma, bar):
                return "long"
        if self.setup_mode in {"short_bounce_downtrend", "two_sided_trend_reversion"}:
            if self.allow_short and rsi >= self.overbought_rsi and self._passes_trend("short", close, ma, bar):
                return "short"
        return None

    def _passes_trend(self, direction: str, close: float, ma: float, bar: pd.Series) -> bool:
        if self.trend_filter in {"ma", "ma_and_vwap"}:
            if direction == "long" and close < ma:
                return False
            if direction == "short" and close > ma:
                return False

        if self.trend_filter in {"vwap", "ma_and_vwap"} or self.min_vwap_extension_ticks > 0:
            vwap = _finite_float(bar.get("vwap"))
            if vwap is None:
                return False
            extension = self.min_vwap_extension_ticks * self.tick_size
            if direction == "long" and close > vwap - extension:
                return False
            if direction == "short" and close < vwap + extension:
                return False
        return True


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _sma(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


def _rsi(values: list[float], period: int) -> float | None:
    if len(values) <= period:
        return None

    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period

    if avg_loss == 0 and avg_gain == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
