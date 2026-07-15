from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class OvernightIntradayReversalEntry:
    name = "overnight_intraday_reversal"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "first_window_confirmed_reversal")).lower()
        self.direction_mode = str(params.get("direction_mode", "two_sided")).lower()
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "14:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.confirm_window_minutes = float(params.get("confirm_window_minutes", 5))
        self.min_abs_overnight_bps = float(params.get("min_abs_overnight_bps", 25))
        self.confirm_mode = str(params.get("confirm_mode", "confirm_reversal")).lower()
        self.confirm_threshold_bps = float(params.get("confirm_threshold_bps", 10))
        self.stop_pct = float(params.get("stop_pct", 0.0035))
        self.target_r_multiple = float(params.get("target_r_multiple", 3.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        state = self._state(bar["session_date"])
        if state["signaled"]:
            return None

        session_start = _session_timestamp(timestamp, self.rth_start)
        confirm_end = session_start + pd.Timedelta(minutes=self.confirm_window_minutes)
        signal_timestamp = _session_timestamp(timestamp, self.entry_time)

        if state["opening"] is None and timestamp >= session_start:
            prev_close = _finite_float(bar.get("prev_rth_close"))
            if prev_close is not None:
                state["opening"] = {
                    "timestamp": timestamp,
                    "open": float(bar["open"]),
                    "prev_rth_close": prev_close,
                }

        if timestamp >= session_start and bar_close <= confirm_end:
            state["confirm_window"] = self._aggregate_bar(
                state["confirm_window"],
                bar,
                session_start,
                confirm_end,
            )

        if bar_close != signal_timestamp:
            return None

        signal = self._signal(state, signal_timestamp)
        if signal is not None:
            state["signaled"] = True
        return signal

    def _state(self, session_date):
        return self.state_by_day.setdefault(
            session_date,
            {
                "opening": None,
                "confirm_window": None,
                "signaled": False,
            },
        )

    def _signal(self, state: dict, signal_timestamp: pd.Timestamp) -> Signal | None:
        opening = state.get("opening")
        confirm = state.get("confirm_window")
        if not opening or not confirm or not self._window_complete(confirm):
            return None

        prev_close = float(opening["prev_rth_close"])
        rth_open = float(opening["open"])
        if prev_close <= 0 or rth_open <= 0:
            return None

        overnight_points = rth_open - prev_close
        overnight_bps = (rth_open / prev_close - 1.0) * 10000.0
        if abs(overnight_bps) < self.min_abs_overnight_bps:
            return None

        direction = "long" if overnight_bps < 0 else "short"
        if self.direction_mode == "long_only" and direction != "long":
            return None
        if self.direction_mode == "short_only" and direction != "short":
            return None
        if self.direction_mode not in {"two_sided", "long_only", "short_only"}:
            raise ValueError("overnight_intraday_reversal direction_mode must be two_sided, long_only, or short_only.")

        confirm_open = float(confirm["open"])
        confirm_close = float(confirm["close"])
        confirm_return_points = confirm_close - confirm_open
        confirm_return_bps = (confirm_close / confirm_open - 1.0) * 10000.0 if confirm_open > 0 else math.nan
        if not math.isfinite(confirm_return_bps):
            return None
        if not self._confirmation_passes(direction, confirm_return_bps):
            return None

        flatten_label = self.flatten_time.strftime("%H:%M:%S")
        report_fields = {
            "academic_source_key": "liu_liu_wang_zhou_zhu_overnight_intraday_reversal",
            "setup_mode": self.setup_mode,
            "feature_method": "overnight_intraday_reversal",
            "direction_mode": self.direction_mode,
            "confirm_mode": self.confirm_mode,
            "prev_rth_close": prev_close,
            "rth_open": rth_open,
            "overnight_return_points": overnight_points,
            "overnight_return_bps": overnight_bps,
            "confirm_window_start_timestamp": confirm["start_timestamp"],
            "confirm_window_end_timestamp": confirm["end_timestamp"],
            "confirm_window_open": confirm_open,
            "confirm_window_high": float(confirm["high"]),
            "confirm_window_low": float(confirm["low"]),
            "confirm_window_close": confirm_close,
            "confirm_window_return_points": confirm_return_points,
            "confirm_window_return_bps": confirm_return_bps,
            "min_abs_overnight_bps": self.min_abs_overnight_bps,
            "confirm_threshold_bps": self.confirm_threshold_bps,
            "overnight_intraday_reversal_signal_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": flatten_label,
            "swept_level": prev_close,
            "sweep_timestamp": opening["timestamp"],
            "sweep_high": float(confirm["high"]),
            "sweep_low": float(confirm["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        return Signal(
            direction=direction,
            level_type=f"overnight_intraday_reversal_{self.setup_mode}",
            swept_level=prev_close,
            sweep_timestamp=opening["timestamp"],
            sweep_high=float(confirm["high"]),
            sweep_low=float(confirm["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "overnight_return_bps": overnight_bps,
                "confirm_window_return_bps": confirm_return_bps,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": flatten_label,
            },
            report_fields=report_fields,
        )

    def _confirmation_passes(self, direction: str, confirm_return_bps: float) -> bool:
        threshold = self.confirm_threshold_bps
        if self.confirm_mode in {"none", "overnight_only"}:
            return True
        if self.confirm_mode == "confirm_reversal":
            return confirm_return_bps >= threshold if direction == "long" else confirm_return_bps <= -threshold
        if self.confirm_mode == "confirm_noncontinuation":
            return confirm_return_bps >= -threshold if direction == "long" else confirm_return_bps <= threshold
        raise ValueError(
            "overnight_intraday_reversal confirm_mode must be one of: "
            "confirm_reversal, confirm_noncontinuation, none."
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
        expected = max(1, int(math.ceil(self.confirm_window_minutes / self.bar_interval_minutes)))
        return int(window.get("bar_count", 0)) >= expected

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0 or self.confirm_window_minutes <= 0:
            raise ValueError("bar_interval_minutes and confirm_window_minutes must be greater than 0.")
        if self.min_abs_overnight_bps < 0 or self.confirm_threshold_bps < 0:
            raise ValueError("overnight and confirmation thresholds must be non-negative.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")


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
