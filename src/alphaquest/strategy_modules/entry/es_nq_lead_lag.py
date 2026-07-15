from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class EsNqLeadLagEntry:
    name = "es_nq_lead_lag"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_es_lag_follow")).lower()
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.lookback_minutes = int(params.get("lookback_minutes", 30))
        self.min_nq_return_bps = float(params.get("min_nq_return_bps", 8.0))
        self.min_lead_gap_bps = float(params.get("min_lead_gap_bps", 2.0))
        self.stop_pct = float(params.get("stop_pct", 0.003))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.state_by_day: dict = {}

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._validate()
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        state = self._state(bar["session_date"])
        if state["signaled"]:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = self._session_timestamp(timestamp, self.entry_time)
        if bar_close != signal_timestamp:
            return None

        nq_return = _finite_float(bar.get(f"nq_return_bps_{self.lookback_minutes}"))
        es_return = _finite_float(bar.get(f"es_return_bps_{self.lookback_minutes}"))
        if nq_return is None or es_return is None:
            return None

        direction = self._direction(nq_return, es_return)
        if direction is None:
            return None
        if direction == "long":
            lead_gap = nq_return - es_return
        else:
            lead_gap = es_return - nq_return

        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "high_frequency_cross_asset_lead_lag",
            "setup_mode": self.setup_mode,
            "leader_symbol": "NQ",
            "traded_symbol": "ES",
            "lookback_minutes": self.lookback_minutes,
            "nq_return_bps": nq_return,
            "es_return_bps": es_return,
            "directional_lead_gap_bps": lead_gap,
            "min_nq_return_bps": self.min_nq_return_bps,
            "min_lead_gap_bps": self.min_lead_gap_bps,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": signal_timestamp,
        }
        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"es_nq_lead_lag_{self.setup_mode}_{self.lookback_minutes}m",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "leader_symbol": "NQ",
                "lookback_minutes": self.lookback_minutes,
                "nq_return_bps": nq_return,
                "es_return_bps": es_return,
                "directional_lead_gap_bps": lead_gap,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(self, nq_return: float, es_return: float) -> str | None:
        mode = self.setup_mode
        if mode == "nq_up_es_lag_long":
            return "long" if self._long_condition(nq_return, es_return, require_confirmed=False) else None
        if mode == "nq_down_es_lag_short":
            return "short" if self._short_condition(nq_return, es_return, require_confirmed=False) else None
        if mode == "two_sided_es_lag_follow":
            if self._long_condition(nq_return, es_return, require_confirmed=False):
                return "long"
            if self._short_condition(nq_return, es_return, require_confirmed=False):
                return "short"
            return None
        if mode == "two_sided_confirmed_follow":
            if self._long_condition(nq_return, es_return, require_confirmed=True):
                return "long"
            if self._short_condition(nq_return, es_return, require_confirmed=True):
                return "short"
            return None
        raise ValueError(
            "Unsupported setup_mode for es_nq_lead_lag. Expected one of "
            "nq_up_es_lag_long, nq_down_es_lag_short, two_sided_es_lag_follow, "
            "two_sided_confirmed_follow."
        )

    def _long_condition(self, nq_return: float, es_return: float, *, require_confirmed: bool) -> bool:
        if not self.allow_long:
            return False
        if nq_return < self.min_nq_return_bps:
            return False
        if nq_return - es_return < self.min_lead_gap_bps:
            return False
        if require_confirmed and es_return <= 0:
            return False
        return True

    def _short_condition(self, nq_return: float, es_return: float, *, require_confirmed: bool) -> bool:
        if not self.allow_short:
            return False
        if nq_return > -self.min_nq_return_bps:
            return False
        if es_return - nq_return < self.min_lead_gap_bps:
            return False
        if require_confirmed and es_return >= 0:
            return False
        return True

    def _state(self, session_date):
        return self.state_by_day.setdefault(session_date, {"signaled": False})

    def _session_timestamp(self, timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
        return timestamp.replace(
            hour=session_time.hour,
            minute=session_time.minute,
            second=session_time.second,
            microsecond=0,
        )

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.lookback_minutes <= 0:
            raise ValueError("lookback_minutes must be greater than 0.")
        if self.min_nq_return_bps < 0 or self.min_lead_gap_bps < 0:
            raise ValueError("min_nq_return_bps and min_lead_gap_bps must be non-negative.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
