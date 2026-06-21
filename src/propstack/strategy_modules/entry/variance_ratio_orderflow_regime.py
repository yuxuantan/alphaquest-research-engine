from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class VarianceRatioOrderflowRegimeEntry:
    name = "variance_ratio_orderflow_regime"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "variance_ratio_orderflow_regime"))
        self.regime_mode = str(params.get("regime_mode", "continuation")).lower()
        self.start_time = parse_time(params.get("start_time", "09:45:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.lookback_bars = int(params.get("lookback_bars", 24))
        self.horizon_bars = int(params.get("horizon_bars", 3))
        self.signal_return_bars = int(params.get("signal_return_bars", 3))
        self.flow_window_bars = int(params.get("flow_window_bars", self.signal_return_bars))
        self.vr_threshold = float(params.get("vr_threshold", 1.15))
        self.min_orderflow_imbalance = float(params.get("min_orderflow_imbalance", 0.08))
        self.min_signal_return_ticks = float(params.get("min_signal_return_ticks", 4.0))
        self.min_close_location = float(params.get("min_close_location", 0.55))
        self.max_reversion_close_location = float(params.get("max_reversion_close_location", 0.45))
        self.flow_mode = str(params.get("flow_mode", "signed")).lower()
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 2))
        self.stop_pct = float(params.get("stop_pct", 0.0025))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        state = self._state(bar, timestamp)
        self._append_bar(state, bar_close, bar)

        if trades_today >= self.max_trades_per_day:
            return None
        if timestamp.time() < self.start_time or timestamp.time() > self.end_time:
            return None

        metrics = self._metrics(state)
        if metrics is None:
            return None

        direction = self._direction(metrics)
        if direction is None:
            return None

        return self._signal(bar, bar_close, direction, metrics)

    def _state(self, bar: pd.Series, timestamp: pd.Timestamp) -> dict:
        session_date = bar.get("session_date", timestamp.date())
        state = self.state_by_day.get(session_date)
        if state is None:
            state = {"bars": []}
            self.state_by_day[session_date] = state
        return state

    def _append_bar(self, state: dict, bar_close: pd.Timestamp, bar: pd.Series) -> None:
        item = {
            "timestamp": bar_close,
            "open": _finite_float(bar.get("open")),
            "high": _finite_float(bar.get("high")),
            "low": _finite_float(bar.get("low")),
            "close": _finite_float(bar.get("close")),
            "volume": _finite_float(bar.get("volume")),
            "signed_volume": _finite_float(bar.get("signed_volume")),
            "large10_signed_volume": _finite_float(bar.get("large10_signed_volume")),
            "large10_volume": _finite_float(bar.get("large10_volume")),
            "large20_signed_volume": _finite_float(bar.get("large20_signed_volume")),
            "large20_volume": _finite_float(bar.get("large20_volume")),
        }
        if None in {item["open"], item["high"], item["low"], item["close"]}:
            return
        state["bars"].append(item)
        max_bars = max(self.lookback_bars + self.horizon_bars + 2, self.signal_return_bars + 2)
        state["bars"] = state["bars"][-max_bars:]

    def _metrics(self, state: dict) -> dict[str, float] | None:
        bars = state["bars"]
        min_bars = max(self.lookback_bars + self.horizon_bars + 1, self.signal_return_bars + 1)
        if len(bars) < min_bars:
            return None

        closes = [bar["close"] for bar in bars[-(self.lookback_bars + self.horizon_bars + 1) :]]
        variance_ratio = _variance_ratio(closes, self.lookback_bars, self.horizon_bars)
        if variance_ratio is None:
            return None

        current = bars[-1]
        signal_start = bars[-(self.signal_return_bars + 1)]["close"]
        signal_return_ticks = (current["close"] - signal_start) / self.tick_size
        if not math.isfinite(signal_return_ticks):
            return None
        if abs(signal_return_ticks) < self.min_signal_return_ticks:
            return None

        flow_imbalance = self._flow_imbalance(bars[-self.flow_window_bars :])
        if flow_imbalance is None or abs(flow_imbalance) < self.min_orderflow_imbalance:
            return None

        bar_range = current["high"] - current["low"]
        if bar_range <= 0:
            return None
        close_location = (current["close"] - current["low"]) / bar_range
        if not math.isfinite(close_location):
            return None

        return {
            "variance_ratio": variance_ratio,
            "signal_return_ticks": signal_return_ticks,
            "flow_imbalance": flow_imbalance,
            "close_location": close_location,
            "current_close": current["close"],
        }

    def _flow_imbalance(self, bars: list[dict]) -> float | None:
        signed_col, volume_col = {
            "signed": ("signed_volume", "volume"),
            "signed_volume": ("signed_volume", "volume"),
            "large10": ("large10_signed_volume", "large10_volume"),
            "large20": ("large20_signed_volume", "large20_volume"),
        }[self.flow_mode]
        signed = 0.0
        volume = 0.0
        for bar in bars:
            signed_value = _finite_float(bar.get(signed_col))
            volume_value = _finite_float(bar.get(volume_col))
            if signed_value is None or volume_value is None:
                return None
            signed += signed_value
            volume += abs(volume_value)
        if volume <= 0:
            return None
        out = signed / volume
        return out if math.isfinite(out) else None

    def _direction(self, metrics: dict[str, float]) -> str | None:
        return_sign = _sign(metrics["signal_return_ticks"])
        flow_sign = _sign(metrics["flow_imbalance"])
        if return_sign == 0 or flow_sign == 0 or return_sign != flow_sign:
            return None

        if self.regime_mode == "continuation":
            if metrics["variance_ratio"] < self.vr_threshold:
                return None
            if return_sign > 0 and self.allow_long and metrics["close_location"] >= self.min_close_location:
                return "long"
            if return_sign < 0 and self.allow_short and metrics["close_location"] <= 1.0 - self.min_close_location:
                return "short"
            return None

        if self.regime_mode == "reversion":
            if metrics["variance_ratio"] > self.vr_threshold:
                return None
            if (
                return_sign < 0
                and self.allow_long
                and metrics["close_location"] >= self.max_reversion_close_location
            ):
                return "long"
            if (
                return_sign > 0
                and self.allow_short
                and metrics["close_location"] <= 1.0 - self.max_reversion_close_location
            ):
                return "short"
            return None

        raise ValueError(f"Unsupported regime_mode: {self.regime_mode}")

    def _signal(self, bar: pd.Series, bar_close: pd.Timestamp, direction: str, metrics: dict[str, float]) -> Signal:
        timestamp = pd.Timestamp(bar["timestamp"])
        current_close = float(bar["close"])
        flatten_label = self.flatten_time.strftime("%H:%M:%S")
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "completed_bar_variance_ratio_orderflow_regime",
            "regime_mode": self.regime_mode,
            "lookback_bars": self.lookback_bars,
            "horizon_bars": self.horizon_bars,
            "signal_return_bars": self.signal_return_bars,
            "flow_window_bars": self.flow_window_bars,
            "flow_mode": self.flow_mode,
            "variance_ratio": metrics["variance_ratio"],
            "vr_threshold": self.vr_threshold,
            "signal_return_ticks": metrics["signal_return_ticks"],
            "flow_imbalance": metrics["flow_imbalance"],
            "min_orderflow_imbalance": self.min_orderflow_imbalance,
            "close_location": metrics["close_location"],
            "signal_close_timestamp": bar_close,
            "intended_entry_timestamp": bar_close,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": flatten_label,
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": bar_close,
        }
        return Signal(
            direction=direction,
            level_type=f"variance_ratio_orderflow_{self.regime_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar_close,
            metadata={
                "setup_mode": self.setup_mode,
                "regime_mode": self.regime_mode,
                "variance_ratio": metrics["variance_ratio"],
                "signal_return_ticks": metrics["signal_return_ticks"],
                "flow_imbalance": metrics["flow_imbalance"],
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": flatten_label,
            },
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.regime_mode not in {"continuation", "reversion"}:
            raise ValueError("regime_mode must be continuation or reversion.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.lookback_bars < 4:
            raise ValueError("lookback_bars must be at least 4.")
        if self.horizon_bars < 2 or self.horizon_bars >= self.lookback_bars:
            raise ValueError("horizon_bars must be at least 2 and less than lookback_bars.")
        if self.signal_return_bars <= 0 or self.flow_window_bars <= 0:
            raise ValueError("signal_return_bars and flow_window_bars must be positive.")
        if self.vr_threshold <= 0:
            raise ValueError("vr_threshold must be greater than 0.")
        if self.min_orderflow_imbalance < 0 or self.min_signal_return_ticks < 0:
            raise ValueError("minimum thresholds must be non-negative.")
        if not 0 <= self.min_close_location <= 1 or not 0 <= self.max_reversion_close_location <= 1:
            raise ValueError("close-location thresholds must be between 0 and 1.")
        if self.flow_mode not in {"signed", "signed_volume", "large10", "large20"}:
            raise ValueError("flow_mode must be signed, signed_volume, large10, or large20.")
        if not self.allow_long and not self.allow_short:
            raise ValueError("At least one side must be allowed.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")


def _variance_ratio(closes: list[float], lookback_bars: int, horizon_bars: int) -> float | None:
    if len(closes) < lookback_bars + horizon_bars + 1:
        return None
    values = pd.Series(closes, dtype="float64")
    one_returns = values.diff().iloc[-lookback_bars:]
    horizon_returns = values.diff(horizon_bars).iloc[-lookback_bars:]
    var_one = float(one_returns.var(ddof=1))
    var_horizon = float(horizon_returns.var(ddof=1))
    if not math.isfinite(var_one) or not math.isfinite(var_horizon) or var_one <= 0:
        return None
    ratio = var_horizon / (horizon_bars * var_one)
    return ratio if math.isfinite(ratio) else None


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0
