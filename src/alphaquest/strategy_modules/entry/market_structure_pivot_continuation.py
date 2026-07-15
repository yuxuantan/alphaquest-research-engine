from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.market_structure_pivots import MultiTimeframePivotStructure
from alphaquest.utils.time import parse_time


class MarketStructurePivotContinuationEntry:
    name = "market_structure_pivot_continuation"

    def __init__(self, params: dict):
        self.params = params
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.signal_mode = str(params.get("signal_mode", "fixed_time")).lower()
        self.start_time = parse_time(params.get("start_time", "09:30:00"))
        self.end_time = parse_time(params.get("end_time", params.get("signal_time", "15:55:00")))
        self.signal_time = parse_time(params.get("signal_time", "11:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.setup_mode = str(params.get("setup_mode", "market_structure_pivot_continuation"))
        timeframes = _int_list(params.get("timeframes_minutes", [15, 30]))
        self.structure = MultiTimeframePivotStructure(
            timeframes_minutes=timeframes,
            bar_interval_minutes=self.bar_interval_minutes,
            rth_start=self.rth_start,
            tick_size=self.tick_size,
            pivot_left_bars=int(params.get("pivot_left_bars", 1)),
            pivot_right_bars=int(params.get("pivot_right_bars", 1)),
            min_pivot_move_ticks=float(params.get("min_pivot_move_ticks", 0.0)),
            min_aligned_timeframes=int(params.get("min_aligned_timeframes", len(timeframes))),
            carry_pivots_across_sessions=bool(params.get("carry_pivots_across_sessions", False)),
        )
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        self.structure.update(bar)
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        state = self.state_by_day.setdefault(session_date, {"signaled": False})
        if state["signaled"]:
            return None

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if self.signal_mode == "fixed_time":
            signal_timestamp = timestamp.replace(
                hour=self.signal_time.hour,
                minute=self.signal_time.minute,
                second=self.signal_time.second,
                microsecond=0,
            )
            if bar_close != signal_timestamp:
                return None
        elif self.signal_mode == "first_bias_in_window":
            if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
                return None
            signal_timestamp = bar_close
        else:
            raise ValueError("signal_mode must be fixed_time or first_bias_in_window.")

        bias = self.structure.bias()
        direction = bias["direction"]
        if direction == "long" and not self.allow_long:
            return None
        if direction == "short" and not self.allow_short:
            return None
        if direction not in {"long", "short"}:
            return None

        state["signaled"] = True
        close = float(bar["close"])
        report_fields = {
            "setup_mode": self.setup_mode,
            "feature_method": "completed_multitimeframe_swing_pivot_sequence",
            "signal_mode": self.signal_mode,
            "signal_window_start": self.start_time.strftime("%H:%M:%S"),
            "signal_window_end": self.end_time.strftime("%H:%M:%S"),
            "signal_close_timestamp": bar_close,
            "intended_entry_timestamp": bar_close,
            "signal_time": self.signal_time.strftime("%H:%M:%S"),
            "signal_close": close,
            "signal_high": float(bar["high"]),
            "signal_low": float(bar["low"]),
            "trend_direction": direction,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            **self.structure.report_fields(),
        }
        return Signal(
            direction=direction,
            level_type=f"market_structure_pivot_{direction}_continuation",
            swept_level=close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar_close,
            breakout_level=close,
            metadata={
                "setup_mode": self.setup_mode,
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
                **self.structure.report_fields(),
            },
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.signal_mode not in {"fixed_time", "first_bias_in_window"}:
            raise ValueError("signal_mode must be fixed_time or first_bias_in_window.")


def _int_list(value) -> list[int]:
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",") if item.strip()]
    return [int(item) for item in value]
