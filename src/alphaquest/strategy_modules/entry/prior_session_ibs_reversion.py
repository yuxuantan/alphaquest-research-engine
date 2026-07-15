from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class PriorSessionIbsReversionEntry:
    name = "prior_session_ibs_reversion"

    _MODES = {"low_ibs_long", "high_ibs_short", "two_sided_reversion"}

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "low_ibs_long")).lower()
        if self.setup_mode not in self._MODES:
            raise ValueError(f"entry.params.setup_mode must be one of {sorted(self._MODES)}.")
        self.signal_time = parse_time(params.get("signal_time", "09:35:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.low_ibs_threshold = float(params.get("low_ibs_threshold", 0.2))
        self.high_ibs_threshold = float(params.get("high_ibs_threshold", 0.8))
        self.min_prior_range_points = float(params.get("min_prior_range_points", 0.0))
        self.max_prior_range_points = params.get("max_prior_range_points")
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.state_by_day: dict = {}

    def _state(self, session_date):
        return self.state_by_day.setdefault(session_date, {"signaled": False})

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() != self.signal_time:
            return None
        state = self._state(bar["session_date"])
        if state["signaled"]:
            return None

        prev_high = _finite_float(bar.get("prev_rth_high"))
        prev_low = _finite_float(bar.get("prev_rth_low"))
        prev_close = _finite_float(bar.get("prev_rth_close"))
        if prev_high is None or prev_low is None or prev_close is None:
            return None

        prior_range = prev_high - prev_low
        if not math.isfinite(prior_range) or prior_range <= 0:
            return None
        if prior_range < self.min_prior_range_points:
            return None
        if self.max_prior_range_points is not None and prior_range > float(self.max_prior_range_points):
            return None

        ibs = (prev_close - prev_low) / prior_range
        direction = self._direction(ibs)
        if direction is None:
            return None

        state["signaled"] = True
        signal_close = float(bar["close"])
        return Signal(
            direction=direction,
            level_type=f"prior_session_ibs_{self.setup_mode}",
            swept_level=prev_close,
            sweep_timestamp=bar_close,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar_close,
            metadata={
                "stop_pct": float(self.params.get("stop_pct", 0.0035)),
                "target_r_multiple": float(self.params.get("target_r_multiple", 1.5)),
                "flatten_time": self.params.get("flatten_time", "15:59:00"),
                "prior_session_ibs": ibs,
            },
            report_fields={
                "academic_source_key": "pagonidis_internal_bar_strength_equity_etf_mean_reversion",
                "setup_mode": self.setup_mode,
                "signal_timestamp": bar_close,
                "signal_close": signal_close,
                "prev_rth_high": prev_high,
                "prev_rth_low": prev_low,
                "prev_rth_close": prev_close,
                "prior_rth_range": prior_range,
                "prior_session_ibs": ibs,
                "low_ibs_threshold": self.low_ibs_threshold,
                "high_ibs_threshold": self.high_ibs_threshold,
            },
        )

    def _direction(self, ibs: float) -> str | None:
        if self.setup_mode in {"low_ibs_long", "two_sided_reversion"}:
            if self.allow_long and ibs <= self.low_ibs_threshold:
                return "long"
        if self.setup_mode in {"high_ibs_short", "two_sided_reversion"}:
            if self.allow_short and ibs >= self.high_ibs_threshold:
                return "short"
        return None


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
