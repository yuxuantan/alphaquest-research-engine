from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class EsNqRelativeValueReversionEntry:
    name = "es_nq_relative_value_reversion"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_divergence_fade")).lower()
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.lookback_minutes = int(params.get("lookback_minutes", 30))
        self.min_spread_bps = float(params.get("min_spread_bps", 6.0))
        self.min_abs_es_return_bps = float(params.get("min_abs_es_return_bps", 0.0))
        self.stop_pct = float(params.get("stop_pct", 0.003))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        state = self._state(bar["session_date"])
        if state["signaled"]:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = _session_timestamp(timestamp, self.entry_time)
        if bar_close != signal_timestamp:
            return None

        es_return = _finite_float(bar.get(f"es_return_bps_{self.lookback_minutes}"))
        nq_return = _finite_float(bar.get(f"nq_return_bps_{self.lookback_minutes}"))
        spread = _finite_float(bar.get(f"nq_minus_es_return_bps_{self.lookback_minutes}"))
        if es_return is None or nq_return is None or spread is None:
            return None

        direction = self._direction(es_return, spread)
        if direction is None:
            return None

        state["signaled"] = True
        current_close = float(bar["close"])
        report_fields = {
            "academic_source_key": "cross_index_relative_value_reversion",
            "setup_mode": self.setup_mode,
            "leader_symbol": "NQ",
            "traded_symbol": "ES",
            "lookback_minutes": self.lookback_minutes,
            "es_return_bps": es_return,
            "nq_return_bps": nq_return,
            "nq_minus_es_return_bps": spread,
            "min_spread_bps": self.min_spread_bps,
            "min_abs_es_return_bps": self.min_abs_es_return_bps,
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
        return Signal(
            direction=direction,
            level_type=f"es_nq_relative_value_reversion_{self.setup_mode}_{self.lookback_minutes}m",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "leader_symbol": "NQ",
                "lookback_minutes": self.lookback_minutes,
                "es_return_bps": es_return,
                "nq_return_bps": nq_return,
                "nq_minus_es_return_bps": spread,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _direction(self, es_return: float, spread: float) -> str | None:
        if self.setup_mode == "es_underperform_long":
            return "long" if self._long_condition(es_return, spread) else None
        if self.setup_mode == "es_outperform_short":
            return "short" if self._short_condition(es_return, spread) else None
        if self.setup_mode == "two_sided_divergence_fade":
            if self._long_condition(es_return, spread):
                return "long"
            if self._short_condition(es_return, spread):
                return "short"
            return None
        raise ValueError(
            "Unsupported setup_mode for es_nq_relative_value_reversion. Expected one of "
            "es_underperform_long, es_outperform_short, two_sided_divergence_fade."
        )

    def _long_condition(self, es_return: float, spread: float) -> bool:
        if not self.allow_long:
            return False
        if spread < self.min_spread_bps:
            return False
        return es_return <= -self.min_abs_es_return_bps

    def _short_condition(self, es_return: float, spread: float) -> bool:
        if not self.allow_short:
            return False
        if spread > -self.min_spread_bps:
            return False
        return es_return >= self.min_abs_es_return_bps

    def _state(self, session_date):
        return self.state_by_day.setdefault(session_date, {"signaled": False})

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.lookback_minutes <= 0:
            raise ValueError("lookback_minutes must be greater than 0.")
        if self.min_spread_bps < 0 or self.min_abs_es_return_bps < 0:
            raise ValueError("min_spread_bps and min_abs_es_return_bps must be non-negative.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")


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
