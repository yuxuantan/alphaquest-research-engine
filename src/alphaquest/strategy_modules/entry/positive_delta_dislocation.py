from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class PositiveDeltaDislocationEntry:
    name = "positive_delta_dislocation"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "pdh_negative_hour_positive_delta_long")).lower()
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.signal_start = parse_time(params.get("signal_start", "10:30:00"))
        self.signal_end = parse_time(params.get("signal_end", "15:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "16:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.hour_window_minutes = int(params.get("hour_window_minutes", 60))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_close_above_prev_high_ticks = float(params.get("min_close_above_prev_high_ticks", 1))
        self.max_close_above_prev_high_ticks = _optional_float(params.get("max_close_above_prev_high_ticks"))
        self.min_negative_hour_ticks = float(params.get("min_negative_hour_ticks", 1))
        self.min_hour_delta = float(params.get("min_hour_delta", 500.0))
        self.max_hour_delta = _optional_float(params.get("max_hour_delta"))
        self.min_hour_delta_ratio = _optional_float(params.get("min_hour_delta_ratio"))
        self.max_hour_delta_ratio = _optional_float(params.get("max_hour_delta_ratio"))
        self.allowed_signal_times = _parse_time_set(params.get("allowed_signal_times"))
        self.reference_side = str(params.get("reference_side", "pdh")).lower()
        self.direction = str(params.get("direction", "long")).lower()
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.require_fresh_prev_high = bool(params.get("require_fresh_prev_high", False))
        self.require_fresh_prev_low = bool(params.get("require_fresh_prev_low", False))
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if not self._is_hour_window_close(timestamp, bar_close):
            return None
        if bar_close.time() < self.signal_start or bar_close.time() > self.signal_end:
            return None
        if self.allowed_signal_times and bar_close.time() not in self.allowed_signal_times:
            return None

        current_close = _finite_float(bar.get("close"))
        hour_return = _finite_float(bar.get(f"trade_orderflow_return_points_{self.hour_window_minutes}"))
        hour_delta = _finite_float(bar.get(f"trade_orderflow_signed_volume_{self.hour_window_minutes}"))
        hour_volume = _finite_float(bar.get(f"trade_orderflow_volume_{self.hour_window_minutes}"))
        if None in {current_close, hour_return, hour_delta}:
            return None

        candidate = self._signal_candidate(bar, current_close, hour_return, hour_delta, hour_volume)
        if candidate is None:
            return None

        hour_delta_ratio = hour_delta / hour_volume if hour_volume and hour_volume > 0 else None
        hour_open = current_close - hour_return
        window_start = bar_close - pd.Timedelta(minutes=self.hour_window_minutes)
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "sierra_rolling_60m_trade_delta_at_previous_rth_high",
            "price_reference": "current_signal_bar_close",
            "level_reference": candidate["level_reference"],
            "reference_side": candidate["reference_side"],
            "reference_level": candidate["reference_level"],
            "prev_rth_high": _finite_float(bar.get("prev_rth_high")),
            "prev_rth_low": _finite_float(bar.get("prev_rth_low")),
            "current_close": current_close,
            "close_above_prev_rth_high_points": current_close - _finite_float(bar.get("prev_rth_high"))
            if _finite_float(bar.get("prev_rth_high")) is not None
            else None,
            "close_below_prev_rth_low_points": _finite_float(bar.get("prev_rth_low")) - current_close
            if _finite_float(bar.get("prev_rth_low")) is not None
            else None,
            "reference_distance_points": candidate["reference_distance_points"],
            "min_close_above_prev_high_ticks": self.min_close_above_prev_high_ticks,
            "max_close_above_prev_high_ticks": self.max_close_above_prev_high_ticks,
            "hour_window_minutes": self.hour_window_minutes,
            "hour_window_start_timestamp": window_start,
            "hour_window_end_timestamp": bar_close,
            "hour_open": hour_open,
            "hour_close": current_close,
            "hour_return_points": hour_return,
            "hour_return_ticks": hour_return / self.tick_size,
            "hour_signed_volume_delta": hour_delta,
            "hour_volume": hour_volume,
            "hour_delta_ratio": hour_delta_ratio,
            "min_negative_hour_ticks": self.min_negative_hour_ticks,
            "min_hour_delta": self.min_hour_delta,
            "max_hour_delta": self.max_hour_delta,
            "min_hour_delta_ratio": self.min_hour_delta_ratio,
            "max_hour_delta_ratio": self.max_hour_delta_ratio,
            "direction": candidate["direction"],
            "positive_delta_dislocation_signal_timestamp": bar_close,
            "positive_delta_dislocation_intended_entry_timestamp": bar_close,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": candidate["reference_level"],
            "sweep_timestamp": window_start,
            "sweep_high": float(bar.get("high", current_close)),
            "sweep_low": float(bar.get("low", current_close)),
            "reclaim_timestamp": bar_close,
        }
        return Signal(
            direction=candidate["direction"],
            level_type=candidate["level_type"],
            swept_level=candidate["reference_level"],
            sweep_timestamp=window_start,
            sweep_high=float(bar.get("high", current_close)),
            sweep_low=float(bar.get("low", current_close)),
            reclaim_timestamp=bar_close,
            metadata={
                "setup_mode": self.setup_mode,
                "reference_side": candidate["reference_side"],
                "reference_level": candidate["reference_level"],
                "hour_return_points": hour_return,
                "hour_signed_volume_delta": hour_delta,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _signal_candidate(
        self,
        bar: pd.Series,
        current_close: float,
        hour_return: float,
        hour_delta: float,
        hour_volume: float | None,
    ) -> dict | None:
        min_distance = self.min_close_above_prev_high_ticks * self.tick_size
        max_distance = (
            self.max_close_above_prev_high_ticks * self.tick_size
            if self.max_close_above_prev_high_ticks is not None
            else None
        )
        min_counter_move = self.min_negative_hour_ticks * self.tick_size

        if self.reference_side in {"pdh", "both"}:
            prev_high = _finite_float(bar.get("prev_rth_high"))
            if prev_high is not None and (not self.require_fresh_prev_high or _truthy(bar.get("prev_rth_high_fresh"))):
                distance = current_close - prev_high
                if (
                    distance >= min_distance
                    and (max_distance is None or distance <= max_distance)
                    and hour_return <= -min_counter_move
                    and hour_delta >= self.min_hour_delta
                    and self._delta_filters_pass(hour_delta, hour_volume)
                ):
                    direction = self._direction_for_side("pdh")
                    return {
                        "reference_side": "pdh",
                        "level_reference": "previous_rth_high",
                        "reference_level": prev_high,
                        "reference_distance_points": distance,
                        "direction": direction,
                        "level_type": self._level_type("pdh", direction),
                    }

        if self.reference_side in {"pdl", "both"}:
            prev_low = _finite_float(bar.get("prev_rth_low"))
            if prev_low is not None and (not self.require_fresh_prev_low or _truthy(bar.get("prev_rth_low_fresh"))):
                distance = prev_low - current_close
                if (
                    distance >= min_distance
                    and (max_distance is None or distance <= max_distance)
                    and hour_return >= min_counter_move
                    and hour_delta <= -self.min_hour_delta
                    and self._delta_filters_pass(hour_delta, hour_volume)
                ):
                    direction = self._direction_for_side("pdl")
                    return {
                        "reference_side": "pdl",
                        "level_reference": "previous_rth_low",
                        "reference_level": prev_low,
                        "reference_distance_points": distance,
                        "direction": direction,
                        "level_type": self._level_type("pdl", direction),
                    }
        return None

    def _delta_filters_pass(self, hour_delta: float, hour_volume: float | None) -> bool:
        hour_delta_abs = abs(hour_delta)
        if self.max_hour_delta is not None and hour_delta_abs > self.max_hour_delta:
            return False
        hour_delta_ratio = hour_delta / hour_volume if hour_volume and hour_volume > 0 else None
        hour_delta_ratio_abs = abs(hour_delta_ratio) if hour_delta_ratio is not None else None
        if self.min_hour_delta_ratio is not None:
            if hour_delta_ratio_abs is None or hour_delta_ratio_abs < self.min_hour_delta_ratio:
                return False
        if self.max_hour_delta_ratio is not None:
            if hour_delta_ratio_abs is None or hour_delta_ratio_abs > self.max_hour_delta_ratio:
                return False
        return True

    def _direction_for_side(self, reference_side: str) -> str:
        if self.direction != "auto":
            return self.direction
        return "short" if reference_side == "pdh" else "long"

    def _level_type(self, reference_side: str, direction: str) -> str:
        if self.reference_side == "pdh" and self.direction != "auto":
            return f"positive_delta_dislocation_{self.setup_mode}"
        return f"positive_delta_dislocation_{self.setup_mode}_{reference_side}_{direction}"

    def _is_hour_window_close(self, timestamp: pd.Timestamp, bar_close: pd.Timestamp) -> bool:
        anchor = _session_timestamp(timestamp, self.rth_start)
        elapsed_seconds = (bar_close - anchor).total_seconds()
        if elapsed_seconds <= 0:
            return False
        window_seconds = self.hour_window_minutes * 60
        return math.isclose(elapsed_seconds % window_seconds, 0.0, abs_tol=1e-9)

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.hour_window_minutes <= 0:
            raise ValueError("hour_window_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.min_close_above_prev_high_ticks < 0:
            raise ValueError("min_close_above_prev_high_ticks must be non-negative.")
        if self.max_close_above_prev_high_ticks is not None and self.max_close_above_prev_high_ticks < 0:
            raise ValueError("max_close_above_prev_high_ticks must be non-negative.")
        if (
            self.max_close_above_prev_high_ticks is not None
            and self.max_close_above_prev_high_ticks < self.min_close_above_prev_high_ticks
        ):
            raise ValueError("max_close_above_prev_high_ticks must be >= min_close_above_prev_high_ticks.")
        if self.min_negative_hour_ticks < 0:
            raise ValueError("min_negative_hour_ticks must be non-negative.")
        if self.min_hour_delta < 0:
            raise ValueError("min_hour_delta must be non-negative.")
        if self.max_hour_delta is not None and self.max_hour_delta < self.min_hour_delta:
            raise ValueError("max_hour_delta must be >= min_hour_delta.")
        if self.min_hour_delta_ratio is not None and self.min_hour_delta_ratio < 0:
            raise ValueError("min_hour_delta_ratio must be non-negative.")
        if self.max_hour_delta_ratio is not None and self.max_hour_delta_ratio < 0:
            raise ValueError("max_hour_delta_ratio must be non-negative.")
        if (
            self.max_hour_delta_ratio is not None
            and self.min_hour_delta_ratio is not None
            and self.max_hour_delta_ratio < self.min_hour_delta_ratio
        ):
            raise ValueError("max_hour_delta_ratio must be >= min_hour_delta_ratio.")
        if self.reference_side not in {"pdh", "pdl", "both"}:
            raise ValueError("reference_side must be pdh, pdl, or both.")
        if self.direction not in {"long", "short", "auto"}:
            raise ValueError("direction must be long, short, or auto.")
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1.")


def _session_timestamp(timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
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


def _optional_float(value) -> float | None:
    if value is None:
        return None
    return _finite_float(value)


def _parse_time_set(value) -> set | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        values = [value]
    else:
        values = list(value)
    return {parse_time(item) for item in values}


def _truthy(value) -> bool:
    if value is None or pd.isna(value):
        return False
    return bool(value)
