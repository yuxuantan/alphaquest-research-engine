from __future__ import annotations

from datetime import date
import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class OvernightDriftEntry:
    name = "overnight_drift"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "eu_open_long_0200_0300"))
        self.signal_time = parse_time(params.get("signal_time", "02:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "03:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.require_eth = bool(params.get("require_eth", True))
        self.direction = str(params.get("direction", "long")).lower()
        self.min_prior_rth_down_ticks = _optional_float(params.get("min_prior_rth_down_ticks"))
        self.max_pre_signal_return_ticks = _optional_float(params.get("max_pre_signal_return_ticks"))
        self.stop_pct = float(params.get("stop_pct", 0.0015))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.0))
        self.state_by_session: dict[date, dict] = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._validate()
        if trades_today >= self.max_trades_per_day:
            return None
        if self.require_eth and not bool(bar.get("is_eth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar["session_date"])
        state = self.state_by_session.setdefault(session_date, {"signaled": False, "eth_open": None})
        if state["eth_open"] is None and bool(bar.get("is_eth", False)):
            state["eth_open"] = float(bar["open"])
        if state["signaled"]:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = timestamp.replace(
            hour=self.signal_time.hour,
            minute=self.signal_time.minute,
            second=self.signal_time.second,
            microsecond=0,
        )
        if bar_close != signal_timestamp:
            return None
        if self.direction != "long":
            return None

        prior_rth_return_ticks = self._prior_rth_return_ticks(bar)
        if self.min_prior_rth_down_ticks is not None:
            if prior_rth_return_ticks is None:
                return None
            if prior_rth_return_ticks > -self.min_prior_rth_down_ticks:
                return None

        pre_signal_return_ticks = self._pre_signal_return_ticks(bar, state)
        if self.max_pre_signal_return_ticks is not None:
            if pre_signal_return_ticks is None:
                return None
            if pre_signal_return_ticks > self.max_pre_signal_return_ticks:
                return None

        close = float(bar["close"])
        report_fields = {
            "academic_source_key": "boyarchenko_larsen_whelan_2020_overnight_drift",
            "setup_mode": self.setup_mode,
            "feature_method": "fixed_eth_european_open_overnight_drift_window",
            "session_label": bar.get("session_label"),
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_time": self.signal_time.strftime("%H:%M:%S"),
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "prior_rth_open": _finite_float(bar.get("prev_rth_open")),
            "prior_rth_close": _finite_float(bar.get("prev_rth_close")),
            "prior_rth_return_ticks": prior_rth_return_ticks,
            "min_prior_rth_down_ticks": self.min_prior_rth_down_ticks,
            "eth_open": state["eth_open"],
            "pre_signal_return_ticks": pre_signal_return_ticks,
            "max_pre_signal_return_ticks": self.max_pre_signal_return_ticks,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "overnight_drift_same_calendar_exit": True,
        }
        state["signaled"] = True
        return Signal(
            direction="long",
            level_type=f"overnight_drift_{self.setup_mode}",
            swept_level=close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _prior_rth_return_ticks(self, bar: pd.Series) -> float | None:
        prior_open = _finite_float(bar.get("prev_rth_open"))
        prior_close = _finite_float(bar.get("prev_rth_close"))
        if prior_open is None or prior_close is None:
            return None
        return (prior_close - prior_open) / self.tick_size

    def _pre_signal_return_ticks(self, bar: pd.Series, state: dict) -> float | None:
        eth_open = state.get("eth_open")
        if eth_open is None or not math.isfinite(float(eth_open)):
            return None
        return (float(bar["close"]) - float(eth_open)) / self.tick_size

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1.")
        if self.direction != "long":
            raise ValueError("overnight_drift currently supports only long direction.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if self.min_prior_rth_down_ticks is not None and self.min_prior_rth_down_ticks < 0:
            raise ValueError("min_prior_rth_down_ticks must be non-negative when supplied.")


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
