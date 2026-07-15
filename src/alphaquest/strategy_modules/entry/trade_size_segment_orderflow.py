from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class TradeSizeSegmentOrderflowEntry:
    name = "trade_size_segment_orderflow"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "trade_size_segment_orderflow"))
        self.entry_time = parse_time(params.get("entry_time", "10:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "10:45:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.window_minutes = int(params.get("window_minutes", 15))
        self.large_trade_size = int(params.get("large_trade_size", 20))
        self.direction = str(params.get("direction", "both")).lower()
        self.residual_mode = str(params.get("residual_mode", "loose")).lower()
        self.min_large_imbalance = float(params.get("min_large_imbalance", 0.02))
        self.min_disagreement = float(params.get("min_disagreement", 0.04))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.stop_pct = float(params.get("stop_pct", 0.004))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        self._validate()

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        signal_timestamp = timestamp.replace(
            hour=self.entry_time.hour,
            minute=self.entry_time.minute,
            second=self.entry_time.second,
            microsecond=0,
        )
        if bar_close != signal_timestamp:
            return None

        metrics = self._segment_metrics(bar)
        if metrics is None:
            return None

        direction = self._direction_from_metrics(metrics)
        if direction is None:
            return None

        current_close = float(bar["close"])
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "completed_bar_trade_size_segment_orderflow",
            "window_minutes": self.window_minutes,
            "large_trade_size": self.large_trade_size,
            "residual_mode": self.residual_mode,
            "configured_direction": self.direction,
            "large_imbalance": metrics["large_imbalance"],
            "residual_imbalance": metrics["residual_imbalance"],
            "total_imbalance": metrics["total_imbalance"],
            "long_disagreement": metrics["long_disagreement"],
            "short_disagreement": metrics["short_disagreement"],
            "min_large_imbalance": self.min_large_imbalance,
            "min_disagreement": self.min_disagreement,
            "large_signed_volume": metrics["large_signed_volume"],
            "large_volume": metrics["large_volume"],
            "residual_signed_volume": metrics["residual_signed_volume"],
            "residual_volume": metrics["residual_volume"],
            "total_signed_volume": metrics["total_signed_volume"],
            "total_volume": metrics["total_volume"],
            "orderflow_signal_timestamp": signal_timestamp,
            "orderflow_intended_entry_timestamp": signal_timestamp,
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
            level_type=f"trade_size_segment_{self.setup_mode}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            metadata={
                "setup_mode": self.setup_mode,
                "window_minutes": self.window_minutes,
                "large_trade_size": self.large_trade_size,
                "residual_mode": self.residual_mode,
                "min_large_imbalance": self.min_large_imbalance,
                "min_disagreement": self.min_disagreement,
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.window_minutes <= 0:
            raise ValueError("window_minutes must be greater than 0.")
        if self.large_trade_size <= 0:
            raise ValueError("large_trade_size must be greater than 0.")
        if self.direction not in {"long", "short", "both"}:
            raise ValueError("direction must be long, short, or both.")
        if self.residual_mode not in {"loose", "not_aligned", "opposite"}:
            raise ValueError("residual_mode must be loose, not_aligned, or opposite.")
        if self.min_large_imbalance < 0:
            raise ValueError("min_large_imbalance must be non-negative.")
        if self.min_disagreement < 0:
            raise ValueError("min_disagreement must be non-negative.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")

    def _segment_metrics(self, bar: pd.Series) -> dict[str, float] | None:
        suffix = str(self.window_minutes)
        total_signed = _finite_float(bar.get(f"trade_orderflow_signed_volume_{suffix}"))
        total_volume = _finite_float(bar.get(f"trade_orderflow_volume_{suffix}"))
        large_signed = _finite_float(
            bar.get(f"trade_orderflow_large{self.large_trade_size}_signed_volume_{suffix}")
        )
        large_volume = _finite_float(
            bar.get(f"trade_orderflow_large{self.large_trade_size}_volume_{suffix}")
        )
        if None in {total_signed, total_volume, large_signed, large_volume}:
            return None
        if total_volume <= 0 or large_volume <= 0:
            return None
        residual_volume = total_volume - large_volume
        residual_signed = total_signed - large_signed
        if residual_volume <= 0:
            return None
        total_imbalance = total_signed / total_volume
        large_imbalance = large_signed / large_volume
        residual_imbalance = residual_signed / residual_volume
        values = {
            "total_signed_volume": total_signed,
            "total_volume": total_volume,
            "large_signed_volume": large_signed,
            "large_volume": large_volume,
            "residual_signed_volume": residual_signed,
            "residual_volume": residual_volume,
            "total_imbalance": total_imbalance,
            "large_imbalance": large_imbalance,
            "residual_imbalance": residual_imbalance,
            "long_disagreement": large_imbalance - residual_imbalance,
            "short_disagreement": residual_imbalance - large_imbalance,
        }
        return values if all(math.isfinite(value) for value in values.values()) else None

    def _direction_from_metrics(self, metrics: dict[str, float]) -> str | None:
        large_imbalance = metrics["large_imbalance"]
        residual_imbalance = metrics["residual_imbalance"]
        long_ok = (
            large_imbalance >= self.min_large_imbalance
            and metrics["long_disagreement"] >= self.min_disagreement
        )
        short_ok = (
            large_imbalance <= -self.min_large_imbalance
            and metrics["short_disagreement"] >= self.min_disagreement
        )
        if self.residual_mode == "opposite":
            long_ok = long_ok and residual_imbalance <= 0
            short_ok = short_ok and residual_imbalance >= 0
        elif self.residual_mode == "not_aligned":
            long_ok = long_ok and residual_imbalance < self.min_large_imbalance / 2
            short_ok = short_ok and residual_imbalance > -self.min_large_imbalance / 2

        if self.direction == "long":
            return "long" if long_ok else None
        if self.direction == "short":
            return "short" if short_ok else None
        if long_ok:
            return "long"
        if short_ok:
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
