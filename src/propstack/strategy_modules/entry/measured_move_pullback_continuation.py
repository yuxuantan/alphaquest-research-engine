from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.market_structure_pivots import MultiTimeframePivotStructure, StructureState
from propstack.utils.time import parse_time


class MeasuredMovePullbackContinuationEntry:
    name = "measured_move_pullback_continuation"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_continuation")).lower()
        self.start_time = parse_time(params.get("start_time", "09:45:00"))
        self.end_time = parse_time(params.get("end_time", "14:30:00"))
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.breakout_buffer_ticks = int(params.get("breakout_buffer_ticks", 1))
        self.min_measured_move_ticks = float(params.get("min_measured_move_ticks", 12.0))
        self.target_projection_multiple = float(params.get("target_projection_multiple", 1.0))
        timeframes = _int_list(params.get("timeframes_minutes", [5, 15]))
        self.structure = MultiTimeframePivotStructure(
            timeframes_minutes=timeframes,
            bar_interval_minutes=self.bar_interval_minutes,
            rth_start=self.rth_start,
            tick_size=self.tick_size,
            pivot_left_bars=int(params.get("pivot_left_bars", 1)),
            pivot_right_bars=int(params.get("pivot_right_bars", 1)),
            min_pivot_move_ticks=float(params.get("min_pivot_move_ticks", 0.0)),
            min_aligned_timeframes=int(params.get("min_aligned_timeframes", 1)),
            carry_pivots_across_sessions=bool(params.get("carry_pivots_across_sessions", False)),
        )
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        self.structure.update(bar)

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        state = self.state_by_day.setdefault(
            session_date,
            {"signaled": False, "previous_close": None, "last_trigger": None},
        )
        previous_close = state["previous_close"]
        state["previous_close"] = float(bar["close"])

        if trades_today >= self.max_trades_per_day or state["signaled"]:
            return None
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
            return None

        bias = self.structure.bias()
        direction = bias["direction"]
        if direction not in {"long", "short"}:
            return None
        if direction == "long" and self.setup_mode not in {"long_continuation", "two_sided_continuation"}:
            return None
        if direction == "short" and self.setup_mode not in {"short_continuation", "two_sided_continuation"}:
            return None

        structure_state = self._selected_structure_state(direction, bias["states"])
        if structure_state is None:
            return None
        setup = self._setup_levels(direction, structure_state)
        if setup is None:
            return None
        trigger, stop_level, measured_distance = setup
        if measured_distance < self.min_measured_move_ticks * self.tick_size:
            return None
        if state["last_trigger"] == (direction, trigger, stop_level):
            return None
        if not self._breakout_confirmed(direction, previous_close, float(bar["close"]), trigger):
            return None

        state["signaled"] = True
        state["last_trigger"] = (direction, trigger, stop_level)
        return self._signal(direction, bar, bar_close, trigger, stop_level, measured_distance, structure_state)

    def _selected_structure_state(
        self,
        direction: str,
        states: list[StructureState],
    ) -> StructureState | None:
        matches = [state for state in states if state.direction == direction and len(state.pivots) >= 4]
        return matches[-1] if matches else None

    def _setup_levels(self, direction: str, state: StructureState) -> tuple[float, float, float] | None:
        highs = [pivot for pivot in state.pivots if pivot["type"] == "high"]
        lows = [pivot for pivot in state.pivots if pivot["type"] == "low"]
        if not highs or not lows:
            return None
        if direction == "long":
            trigger = float(highs[-1]["price"])
            stop_level = float(lows[-1]["price"])
            measured_distance = trigger - stop_level
        else:
            trigger = float(lows[-1]["price"])
            stop_level = float(highs[-1]["price"])
            measured_distance = stop_level - trigger
        if measured_distance <= 0 or not math.isfinite(measured_distance):
            return None
        return trigger, stop_level, measured_distance

    def _breakout_confirmed(
        self,
        direction: str,
        previous_close: float | None,
        close: float,
        trigger: float,
    ) -> bool:
        if previous_close is None or not math.isfinite(previous_close):
            return False
        buffer = self.breakout_buffer_ticks * self.tick_size
        if direction == "long":
            return previous_close <= trigger + buffer and close >= trigger + buffer
        return previous_close >= trigger - buffer and close <= trigger - buffer

    def _signal(
        self,
        direction: str,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
        trigger: float,
        stop_level: float,
        measured_distance: float,
        state: StructureState,
    ) -> Signal:
        timestamp = pd.Timestamp(bar["timestamp"])
        projection = measured_distance * self.target_projection_multiple
        target = trigger + projection if direction == "long" else trigger - projection
        report_fields = {
            "academic_source_key": "chartfanatics_measured_move_little_rzy_lo_mamaysky_wang_patterns",
            "setup_mode": self.setup_mode,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_close": float(bar["close"]),
            "measured_move_direction": direction,
            "measured_move_timeframe_minutes": state.timeframe_minutes,
            "measured_move_pattern": state.pattern,
            "measured_move_trigger": trigger,
            "measured_move_stop_level": stop_level,
            "measured_move_distance": measured_distance,
            "signal_target_price": target,
            "breakout_buffer_ticks": self.breakout_buffer_ticks,
            "min_measured_move_ticks": self.min_measured_move_ticks,
            "target_projection_multiple": self.target_projection_multiple,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            **self.structure.report_fields("measured_move_structure"),
        }
        return Signal(
            direction=direction,
            level_type=f"measured_move_pullback_{direction}_continuation",
            swept_level=trigger,
            sweep_timestamp=timestamp,
            sweep_high=stop_level if direction == "short" else float(bar["high"]),
            sweep_low=stop_level if direction == "long" else float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            breakout_level=trigger,
            metadata={
                "setup_mode": self.setup_mode,
                "signal_target_price": target,
                "measured_move_trigger": trigger,
                "measured_move_stop_level": stop_level,
                "measured_move_distance": measured_distance,
                "target_projection_multiple": self.target_projection_multiple,
            },
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.setup_mode not in {"long_continuation", "short_continuation", "two_sided_continuation"}:
            raise ValueError("setup_mode must be long_continuation, short_continuation, or two_sided_continuation.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.breakout_buffer_ticks < 0 or self.min_measured_move_ticks < 0:
            raise ValueError("breakout_buffer_ticks and min_measured_move_ticks must be non-negative.")
        if self.target_projection_multiple <= 0:
            raise ValueError("target_projection_multiple must be greater than 0.")


def _int_list(value) -> list[int]:
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",") if item.strip()]
    return [int(item) for item in value]
