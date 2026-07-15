from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class VwapDeviationOrderflowReversionEntry:
    name = "vwap_deviation_orderflow_reversion"

    _FLOW_COLUMNS = {
        "signed_volume": ("signed_volume", "volume"),
        "large10": ("large10_signed_volume", "large10_volume"),
        "large20": ("large20_signed_volume", "large20_volume"),
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "counterflow_vwap_deviation")).lower()
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_vwap_deviation_ticks = float(params.get("min_vwap_deviation_ticks", 12))
        self.min_counterflow_imbalance = float(params.get("min_counterflow_imbalance", 0.02))
        self.min_flow_volume = float(params.get("min_flow_volume", 0.0))
        self.min_close_location_long = float(params.get("min_close_location_long", 0.35))
        self.max_close_location_short = float(params.get("max_close_location_short", 0.65))
        self.flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
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
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
            return None

        close = _finite_float(bar.get("close"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        vwap = _finite_float(bar.get("vwap"))
        if None in {close, high, low, vwap}:
            return None

        flow = self._counterflow(bar)
        if flow is None:
            return None
        signed_volume, total_volume, imbalance = flow
        if total_volume < self.min_flow_volume:
            return None

        deviation_ticks = (close - vwap) / self.tick_size
        close_location = _close_location(close, high, low)
        direction = None
        if (
            self.allow_long
            and deviation_ticks <= -self.min_vwap_deviation_ticks
            and imbalance >= self.min_counterflow_imbalance
            and close_location >= self.min_close_location_long
        ):
            direction = "long"
        elif (
            self.allow_short
            and deviation_ticks >= self.min_vwap_deviation_ticks
            and imbalance <= -self.min_counterflow_imbalance
            and close_location <= self.max_close_location_short
        ):
            direction = "short"
        if direction is None:
            return None

        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "completed_vwap_deviation_counter_orderflow",
            "vwap_deviation_signal_timestamp": bar_close,
            "vwap_deviation_intended_entry_timestamp": bar_close,
            "vwap_at_signal": vwap,
            "signal_close": close,
            "signal_high": high,
            "signal_low": low,
            "vwap_deviation_points": close - vwap,
            "vwap_deviation_ticks": deviation_ticks,
            "min_vwap_deviation_ticks": self.min_vwap_deviation_ticks,
            "flow_mode": self.flow_mode,
            "counterflow_signed_volume": signed_volume,
            "counterflow_volume": total_volume,
            "counterflow_imbalance": imbalance,
            "min_counterflow_imbalance": self.min_counterflow_imbalance,
            "signal_close_location": close_location,
            "min_close_location_long": self.min_close_location_long,
            "max_close_location_short": self.max_close_location_short,
            "swept_level": vwap,
            "sweep_timestamp": bar_close,
            "sweep_high": high,
            "sweep_low": low,
            "reclaim_timestamp": bar_close,
        }
        return Signal(
            direction=direction,
            level_type=f"vwap_deviation_orderflow_reversion_{self.setup_mode}",
            swept_level=vwap,
            sweep_timestamp=bar_close,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=bar_close,
            metadata={
                "setup_mode": self.setup_mode,
                "vwap_at_signal": vwap,
                "vwap_deviation_ticks": deviation_ticks,
                "flow_mode": self.flow_mode,
                "counterflow_imbalance": imbalance,
            },
            report_fields=report_fields,
        )

    def _counterflow(self, bar: pd.Series) -> tuple[float, float, float] | None:
        signed_col, total_col = self._FLOW_COLUMNS[self.flow_mode]
        signed_volume = _finite_float(bar.get(signed_col))
        total_volume = _finite_float(bar.get(total_col))
        if signed_volume is None or total_volume is None or total_volume <= 0:
            return None
        imbalance = signed_volume / total_volume
        if not math.isfinite(imbalance):
            return None
        return signed_volume, total_volume, imbalance

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")
        if self.min_vwap_deviation_ticks < 0:
            raise ValueError("entry.params.min_vwap_deviation_ticks must be non-negative.")
        if self.min_counterflow_imbalance < 0:
            raise ValueError("entry.params.min_counterflow_imbalance must be non-negative.")
        if self.min_flow_volume < 0:
            raise ValueError("entry.params.min_flow_volume must be non-negative.")
        if self.flow_mode not in self._FLOW_COLUMNS:
            raise ValueError(f"entry.params.flow_mode must be one of {sorted(self._FLOW_COLUMNS)}.")
        if not (0.0 <= self.min_close_location_long <= 1.0):
            raise ValueError("entry.params.min_close_location_long must be in [0, 1].")
        if not (0.0 <= self.max_close_location_short <= 1.0):
            raise ValueError("entry.params.max_close_location_short must be in [0, 1].")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least 1.")


def _close_location(close: float, high: float, low: float) -> float:
    span = high - low
    if span <= 0:
        return 0.5
    return max(0.0, min(1.0, (close - low) / span))


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
