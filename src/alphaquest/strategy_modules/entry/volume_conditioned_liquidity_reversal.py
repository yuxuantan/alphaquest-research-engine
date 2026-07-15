from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class VolumeConditionedLiquidityReversalEntry:
    name = "volume_conditioned_liquidity_reversal"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "symmetric_volume_shock_reversion")).lower()
        self.start_time = parse_time(params.get("start_time", "09:35:00"))
        self.end_time = parse_time(params.get("end_time", "15:30:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_move_ticks = float(params.get("min_move_ticks", 8))
        self.min_volume_ratio = float(params.get("min_volume_ratio", 1.25))
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
        if self.tick_size <= 0 or self.bar_interval_minutes <= 0:
            raise ValueError("tick_size and bar_interval_minutes must be greater than 0.")

        state = self._state(bar["session_date"])
        if state["signaled"]:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
            return None

        open_price = _finite_float(bar.get("open"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        volume_ratio = _finite_float(bar.get("volume_ratio"))
        if any(value is None for value in [open_price, high, low, close, volume_ratio]):
            return None
        if volume_ratio < self.min_volume_ratio:
            return None

        return_ticks = (close - open_price) / self.tick_size
        direction = self._direction(return_ticks)
        if direction is None:
            return None
        if direction == "long" and not self.allow_long:
            return None
        if direction == "short" and not self.allow_short:
            return None

        state["signaled"] = True
        report_fields = {
            "academic_source_key": "campbell_grossman_wang_1993_volume_serial_correlation",
            "setup_mode": self.setup_mode,
            "volume_reversal_signal_timestamp": bar_close,
            "shock_bar_open": open_price,
            "shock_bar_high": high,
            "shock_bar_low": low,
            "shock_bar_close": close,
            "shock_return_points": close - open_price,
            "shock_return_ticks": return_ticks,
            "shock_volume_ratio": volume_ratio,
            "min_move_ticks": self.min_move_ticks,
            "min_volume_ratio": self.min_volume_ratio,
        }
        return Signal(
            direction=direction,
            level_type=f"volume_conditioned_liquidity_reversal_{self.setup_mode}",
            swept_level=close,
            sweep_timestamp=bar_close,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=bar_close,
            metadata={
                "confirmation_high": high,
                "confirmation_low": low,
                "confirmation_close": close,
                "shock_return_ticks": return_ticks,
                "shock_volume_ratio": volume_ratio,
                "setup_mode": self.setup_mode,
            },
            report_fields=report_fields,
        )

    def _direction(self, return_ticks: float) -> str | None:
        if self.setup_mode == "high_volume_down_reversal":
            return "long" if return_ticks <= -self.min_move_ticks else None
        if self.setup_mode == "high_volume_up_reversal":
            return "short" if return_ticks >= self.min_move_ticks else None
        if self.setup_mode == "symmetric_volume_shock_reversion":
            if return_ticks <= -self.min_move_ticks:
                return "long"
            if return_ticks >= self.min_move_ticks:
                return "short"
            return None
        raise ValueError(f"Unknown volume-conditioned reversal setup_mode: {self.setup_mode}")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
