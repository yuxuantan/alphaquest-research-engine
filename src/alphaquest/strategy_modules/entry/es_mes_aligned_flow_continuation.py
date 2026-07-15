from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class EsMesAlignedFlowContinuationEntry:
    name = "es_mes_aligned_flow_continuation"

    _FLOW_PREFIX = {
        "signed": "mes_trade_orderflow_imbalance",
        "large10": "mes_trade_orderflow_large10_imbalance",
        "large20": "mes_trade_orderflow_large20_imbalance",
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "es_mes_aligned_flow_continuation"))
        self.primary_prefix = str(params.get("primary_prefix", "es")).lower()
        if self.primary_prefix not in {"es", "nq"}:
            raise ValueError("entry.params.primary_prefix must be one of ['es', 'nq'].")
        self.signal_time = parse_time(params.get("signal_time", "10:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")

        self.return_window_minutes = int(params.get("return_window_minutes", 30))
        self.flow_window_minutes = int(params.get("flow_window_minutes", self.return_window_minutes))
        if self.return_window_minutes <= 0 or self.flow_window_minutes <= 0:
            raise ValueError("entry.params return and flow windows must be positive.")

        self.min_es_return_ticks = float(params.get("min_primary_return_ticks", params.get("min_es_return_ticks", 4.0)))
        self.min_mes_flow_imbalance = float(params.get("min_mes_flow_imbalance", 0.02))
        if self.min_es_return_ticks < 0:
            raise ValueError("entry.params.min_es_return_ticks must be non-negative.")
        if self.min_mes_flow_imbalance < 0:
            raise ValueError("entry.params.min_mes_flow_imbalance must be non-negative.")

        self.mes_flow_mode = str(params.get("mes_flow_mode", "signed")).lower()
        if self.mes_flow_mode not in self._FLOW_PREFIX:
            raise ValueError(f"entry.params.mes_flow_mode must be one of {sorted(self._FLOW_PREFIX)}.")

        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        close_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if close_timestamp.time() != self.signal_time:
            return None

        es_return = _finite_float(bar.get(self._return_column))
        mes_imbalance = _finite_float(bar.get(self._flow_column))
        signal_close = _finite_float(bar.get("close"))
        signal_high = _finite_float(bar.get("high"))
        signal_low = _finite_float(bar.get("low"))
        if None in {es_return, mes_imbalance, signal_close, signal_high, signal_low}:
            return None

        long_ok = (
            self.allow_long
            and es_return >= self.min_es_return_ticks
            and mes_imbalance >= self.min_mes_flow_imbalance
        )
        short_ok = (
            self.allow_short
            and es_return <= -self.min_es_return_ticks
            and mes_imbalance <= -self.min_mes_flow_imbalance
        )
        if not long_ok and not short_ok:
            return None

        direction = "long" if long_ok else "short"
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": f"completed_bar_{self.primary_prefix}_trend_mes_aligned_flow",
            "signal_bar_timestamp": timestamp,
            "signal_close_timestamp": close_timestamp,
            "intended_entry_timestamp": close_timestamp,
            "signal_time": self.signal_time.isoformat(),
            "direction": direction,
            "return_window_minutes": self.return_window_minutes,
            "flow_window_minutes": self.flow_window_minutes,
            "primary_prefix": self.primary_prefix,
            "mes_flow_mode": self.mes_flow_mode,
            "min_primary_return_ticks": self.min_es_return_ticks,
            "min_es_return_ticks": self.min_es_return_ticks,
            "min_mes_flow_imbalance": self.min_mes_flow_imbalance,
            "primary_return_ticks": es_return,
            "es_return_ticks": es_return,
            "mes_flow_imbalance": mes_imbalance,
            "signal_close": signal_close,
            "signal_high": signal_high,
            "signal_low": signal_low,
        }
        return Signal(
            direction=direction,
            level_type=f"{direction}_es_mes_aligned_{self.mes_flow_mode}_flow_continuation",
            swept_level=signal_close,
            sweep_timestamp=timestamp,
            sweep_high=signal_high,
            sweep_low=signal_low,
            reclaim_timestamp=close_timestamp,
            breakout_level=signal_close,
            metadata={**report_fields, "flatten_time": self.params.get("flatten_time")},
            report_fields=report_fields,
        )

    @property
    def _return_column(self) -> str:
        return f"{self.primary_prefix}_trade_orderflow_return_ticks_{self.return_window_minutes}"

    @property
    def _flow_column(self) -> str:
        return f"{self._FLOW_PREFIX[self.mes_flow_mode]}_{self.flow_window_minutes}"


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
