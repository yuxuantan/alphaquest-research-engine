from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class EsMesLeadLagEntry:
    name = "es_mes_lead_lag"

    _FLOW_PREFIX = {
        "signed": "mes_trade_orderflow_imbalance",
        "large10": "mes_trade_orderflow_large10_imbalance",
        "large20": "mes_trade_orderflow_large20_imbalance",
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_mes_lead_es_lag_follow"))
        self.signal_time = parse_time(params.get("signal_time", "10:30:00")) if params.get("signal_time") else None
        self.signal_start = parse_time(params.get("signal_start")) if params.get("signal_start") else None
        self.signal_end = parse_time(params.get("signal_end")) if params.get("signal_end") else None
        self.flatten_time = parse_time(params.get("flatten_time", "12:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.lookback_minutes = int(params.get("lookback_minutes", 15))
        self.flow_window_minutes = int(params.get("flow_window_minutes", self.lookback_minutes))
        self.min_mes_return_ticks = float(params.get("min_mes_return_ticks", 4.0))
        self.min_lag_gap_ticks = float(params.get("min_lag_gap_ticks", 2.0))
        self.min_mes_flow_imbalance = float(params.get("min_mes_flow_imbalance", 0.02))
        self.mes_flow_mode = str(params.get("mes_flow_mode", "signed")).lower()
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        close_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if not self._is_signal_time(close_timestamp):
            return None

        es_return = _finite_float(bar.get(self._es_return_column))
        mes_return = _finite_float(bar.get(self._mes_return_column))
        mes_flow = _finite_float(bar.get(self._flow_column))
        signal_close = _finite_float(bar.get("close"))
        signal_high = _finite_float(bar.get("high"))
        signal_low = _finite_float(bar.get("low"))
        if None in {es_return, mes_return, mes_flow, signal_close, signal_high, signal_low}:
            return None

        direction = self._direction(mes_return, es_return, mes_flow)
        if direction is None:
            return None

        directional_gap = mes_return - es_return if direction == "long" else es_return - mes_return
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "completed_bar_mes_price_flow_lead_es_lag",
            "leader_symbol": "MES",
            "traded_symbol": "ES",
            "signal_bar_timestamp": timestamp,
            "signal_close_timestamp": close_timestamp,
            "intended_entry_timestamp": close_timestamp,
            "signal_time": self.signal_time.isoformat() if self.signal_time else None,
            "signal_start": self.signal_start.isoformat() if self.signal_start else None,
            "signal_end": self.signal_end.isoformat() if self.signal_end else None,
            "direction": direction,
            "lookback_minutes": self.lookback_minutes,
            "flow_window_minutes": self.flow_window_minutes,
            "mes_flow_mode": self.mes_flow_mode,
            "min_mes_return_ticks": self.min_mes_return_ticks,
            "min_lag_gap_ticks": self.min_lag_gap_ticks,
            "min_mes_flow_imbalance": self.min_mes_flow_imbalance,
            "mes_return_ticks": mes_return,
            "es_return_ticks": es_return,
            "directional_lag_gap_ticks": directional_gap,
            "mes_flow_imbalance": mes_flow,
            "signal_close": signal_close,
            "signal_high": signal_high,
            "signal_low": signal_low,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"{direction}_{self.setup_mode}_{self.mes_flow_mode}_{self.lookback_minutes}m",
            swept_level=signal_close,
            sweep_timestamp=timestamp,
            sweep_high=signal_high,
            sweep_low=signal_low,
            reclaim_timestamp=close_timestamp,
            breakout_level=signal_close,
            metadata=report_fields,
            report_fields=report_fields,
        )

    def _direction(self, mes_return: float, es_return: float, mes_flow: float) -> str | None:
        mode = self.setup_mode.lower()
        long_ok = (
            self.allow_long
            and mes_return >= self.min_mes_return_ticks
            and mes_return - es_return >= self.min_lag_gap_ticks
            and mes_flow >= self.min_mes_flow_imbalance
        )
        short_ok = (
            self.allow_short
            and mes_return <= -self.min_mes_return_ticks
            and es_return - mes_return >= self.min_lag_gap_ticks
            and mes_flow <= -self.min_mes_flow_imbalance
        )
        if mode == "mes_up_es_lag_long":
            return "long" if long_ok else None
        if mode == "mes_down_es_lag_short":
            return "short" if short_ok else None
        if mode == "two_sided_mes_lead_es_lag_follow":
            if long_ok:
                return "long"
            if short_ok:
                return "short"
            return None
        raise ValueError(
            "Unsupported setup_mode for es_mes_lead_lag. Expected one of "
            "mes_up_es_lag_long, mes_down_es_lag_short, two_sided_mes_lead_es_lag_follow."
        )

    @property
    def _es_return_column(self) -> str:
        return f"es_trade_orderflow_return_ticks_{self.lookback_minutes}"

    @property
    def _mes_return_column(self) -> str:
        return f"mes_trade_orderflow_return_ticks_{self.lookback_minutes}"

    @property
    def _flow_column(self) -> str:
        return f"{self._FLOW_PREFIX[self.mes_flow_mode]}_{self.flow_window_minutes}"

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        if self.lookback_minutes <= 0 or self.flow_window_minutes <= 0:
            raise ValueError("entry.params lookback and flow windows must be positive.")
        if self.min_mes_return_ticks < 0 or self.min_lag_gap_ticks < 0:
            raise ValueError("entry.params return and lag thresholds must be non-negative.")
        if self.min_mes_flow_imbalance < 0:
            raise ValueError("entry.params.min_mes_flow_imbalance must be non-negative.")
        if self.mes_flow_mode not in self._FLOW_PREFIX:
            raise ValueError(f"entry.params.mes_flow_mode must be one of {sorted(self._FLOW_PREFIX)}.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least 1.")
        if self.signal_time is None and (self.signal_start is None or self.signal_end is None):
            raise ValueError("entry.params must provide signal_time or both signal_start and signal_end.")
        if self.signal_start and self.signal_end and self.signal_end < self.signal_start:
            raise ValueError("entry.params.signal_end must be >= signal_start.")

    def _is_signal_time(self, close_timestamp: pd.Timestamp) -> bool:
        close_time = close_timestamp.time()
        if self.signal_time is not None:
            return close_time == self.signal_time
        return self.signal_start <= close_time <= self.signal_end


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
