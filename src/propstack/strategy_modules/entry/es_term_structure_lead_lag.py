from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class EsTermStructureLeadLagEntry:
    name = "es_term_structure_lead_lag"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_spread_feedback")).lower()
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.lookback_minutes = int(params.get("lookback_minutes", 30))
        self.min_front_return_bps = float(params.get("min_front_return_bps", 6.0))
        self.min_spread_gap_bps = float(params.get("min_spread_gap_bps", 2.0))
        self.stop_pct = float(params.get("stop_pct", 0.0025))
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

        suffix = str(self.lookback_minutes)
        front_return = _finite_float(bar.get(f"front_return_bps_{suffix}"))
        deferred_return = _finite_float(bar.get(f"deferred_return_bps_{suffix}"))
        front_minus_deferred = _finite_float(bar.get(f"front_minus_deferred_return_bps_{suffix}"))
        deferred_minus_front = _finite_float(bar.get(f"deferred_minus_front_return_bps_{suffix}"))
        spread_change = _finite_float(bar.get(f"calendar_spread_change_points_{suffix}"))
        if (
            front_return is None
            or deferred_return is None
            or front_minus_deferred is None
            or deferred_minus_front is None
        ):
            return None

        direction = self._direction(front_return, deferred_return, front_minus_deferred, deferred_minus_front)
        if direction is None:
            return None

        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "futures_term_structure_lead_lag_spread_feedback",
            "setup_mode": self.setup_mode,
            "leader_symbol": "ES_front_or_calendar_spread",
            "traded_symbol": "ES_front",
            "lookback_minutes": self.lookback_minutes,
            "front_return_bps": front_return,
            "deferred_return_bps": deferred_return,
            "front_minus_deferred_return_bps": front_minus_deferred,
            "deferred_minus_front_return_bps": deferred_minus_front,
            "calendar_spread_change_points": spread_change,
            "min_front_return_bps": self.min_front_return_bps,
            "min_spread_gap_bps": self.min_spread_gap_bps,
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
        if "contract_symbol" in bar:
            report_fields["front_contract_symbol"] = bar.get("contract_symbol")
        if "deferred_contract_symbol" in bar:
            report_fields["deferred_contract_symbol"] = bar.get("deferred_contract_symbol")

        state["signaled"] = True
        return Signal(
            direction=direction,
            level_type=f"es_term_structure_{self.setup_mode}_{self.lookback_minutes}m",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "lookback_minutes": self.lookback_minutes,
                "front_return_bps": front_return,
                "deferred_return_bps": deferred_return,
                "front_minus_deferred_return_bps": front_minus_deferred,
                "deferred_minus_front_return_bps": deferred_minus_front,
                "calendar_spread_change_points": spread_change,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(
        self,
        front_return: float,
        deferred_return: float,
        front_minus_deferred: float,
        deferred_minus_front: float,
    ) -> str | None:
        mode = self.setup_mode
        if mode == "front_premium_reversion_short":
            return "short" if self._short_condition(front_return, deferred_return, front_minus_deferred, False) else None
        if mode == "front_discount_reversion_long":
            return "long" if self._long_condition(front_return, deferred_return, deferred_minus_front, False) else None
        if mode == "two_sided_spread_feedback":
            if self._long_condition(front_return, deferred_return, deferred_minus_front, False):
                return "long"
            if self._short_condition(front_return, deferred_return, front_minus_deferred, False):
                return "short"
            return None
        if mode == "two_sided_confirmed_feedback":
            if self._long_condition(front_return, deferred_return, deferred_minus_front, True):
                return "long"
            if self._short_condition(front_return, deferred_return, front_minus_deferred, True):
                return "short"
            return None
        raise ValueError(
            "Unsupported setup_mode for es_term_structure_lead_lag. Expected one of "
            "front_premium_reversion_short, front_discount_reversion_long, "
            "two_sided_spread_feedback, two_sided_confirmed_feedback."
        )

    def _long_condition(
        self,
        front_return: float,
        deferred_return: float,
        deferred_minus_front: float,
        require_confirmed: bool,
    ) -> bool:
        if not self.allow_long:
            return False
        if front_return > -self.min_front_return_bps:
            return False
        if deferred_minus_front < self.min_spread_gap_bps:
            return False
        if require_confirmed and deferred_return >= 0:
            return False
        return True

    def _short_condition(
        self,
        front_return: float,
        deferred_return: float,
        front_minus_deferred: float,
        require_confirmed: bool,
    ) -> bool:
        if not self.allow_short:
            return False
        if front_return < self.min_front_return_bps:
            return False
        if front_minus_deferred < self.min_spread_gap_bps:
            return False
        if require_confirmed and deferred_return <= 0:
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
        if self.min_front_return_bps < 0 or self.min_spread_gap_bps < 0:
            raise ValueError("min_front_return_bps and min_spread_gap_bps must be non-negative.")
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
