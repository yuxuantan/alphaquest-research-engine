from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.profile_aoi_footprint_trap import _finite_float
from propstack.strategy_modules.entry.video_exact_orderflow_playbook_scid_intrabar import _IntrabarState
from propstack.strategy_modules.entry.yush_trend_47 import YushTrend47Entry


class YushTrend67Entry(YushTrend47Entry):
    name = "yush_trend_67"

    def __init__(self, params: dict):
        super().__init__(params)
        self.entry_hold_seconds = float(params.get("entry_hold_seconds", 3.0))
        if not math.isfinite(self.entry_hold_seconds) or self.entry_hold_seconds < 0:
            raise ValueError("entry.params.entry_hold_seconds must be non-negative.")

    def on_bar_intrabar(
        self,
        bar: pd.Series,
        detail_rows: pd.DataFrame,
        trades_today: int = 0,
    ):
        self._roll_session(bar)
        if self.setup_mode not in self._SUPPORTED_MODES:
            return None
        if not bool(bar.get("is_rth", False)):
            return None
        session_date = bar.get("session_date")
        if (
            self.signals_by_session.get(session_date, 0) >= self.max_signals_per_session
            or trades_today >= self.max_trades_per_day
            or detail_rows is None
            or detail_rows.empty
            or "timestamp" not in detail_rows
            or not self.current_session_bars
        ):
            return None

        context_bar = self.current_session_bars[-1]
        profile = self._active_profile(context_bar) or {}
        if not profile:
            return None

        context_close = _finite_float(context_bar.get("close")) or 0.0
        candidates = self._candidate_setups(bar, profile, context_close)
        if not candidates:
            return None

        state = _IntrabarState()
        pending: dict[tuple[str, str, str, float], dict] = {}
        hold_delta = pd.Timedelta(seconds=self.entry_hold_seconds)
        for _, tick in detail_rows.iterrows():
            tick_state = state.update(tick)
            if tick_state is None:
                continue
            tick_timestamp = pd.Timestamp(tick["timestamp"])
            if tick_timestamp.time() < self.start_time or tick_timestamp.time() > self.end_time:
                continue
            if hasattr(self, "_timestamp_is_blocked") and self._timestamp_is_blocked(tick_timestamp):
                continue

            for direction, model, level_type, level in candidates:
                if direction == "long" and not self.allow_long:
                    continue
                if direction == "short" and not self.allow_short:
                    continue
                key = (direction, model, level_type, float(level))
                if not self._hold_side_is_intact(direction, float(level), tick_state):
                    pending.pop(key, None)
                    continue

                active = pending.get(key)
                if active is None:
                    confluence = self._intrabar_aoi_confluence(bar, profile, direction, model, level, tick_state)
                    if len(confluence["criteria"]) < self.min_aoi_confluences:
                        continue
                    confirms = (
                        self._intrabar_range_trap_confirms(direction, level, tick_state)
                        if model == "range"
                        else self._intrabar_trend_pullback_confirms(direction, level, tick_state)
                    )
                    if not confirms:
                        continue
                    active = {"start": tick_timestamp, "confluence": confluence}
                    pending[key] = active

                if tick_timestamp - active["start"] < hold_delta:
                    continue
                if not self._known_risk_within_cap(direction, tick_state):
                    continue

                signal = self._intrabar_video_signal(
                    direction=direction,
                    model=model,
                    level_type=level_type,
                    level=level,
                    profile=profile,
                    confluence=active["confluence"],
                    tick_state=tick_state,
                    tick=tick,
                )
                signal.metadata["entry_hold_seconds"] = self.entry_hold_seconds
                signal.metadata["entry_hold_start"] = active["start"]
                signal.metadata["entry_hold_confirmed_at"] = tick_timestamp
                signal.metadata["entry_hold_policy"] = "price_only_after_initial_orderflow"
                signal.report_fields["entry_hold_seconds"] = self.entry_hold_seconds
                signal.report_fields["entry_hold_start"] = active["start"]
                signal.report_fields["entry_hold_confirmed_at"] = tick_timestamp
                signal.report_fields["entry_hold_policy"] = "price_only_after_initial_orderflow"
                self.signals_by_session[session_date] = self.signals_by_session.get(session_date, 0) + 1
                self.signaled_sessions.add(session_date)
                self.current_session_bars.append(bar.copy())
                self._last_intrabar_appended_timestamp = pd.Timestamp(bar["timestamp"])
                return signal
        return None

    def _hold_side_is_intact(self, direction: str, level: float, state: dict) -> bool:
        price = float(state["price"])
        if direction == "long":
            return price >= level
        return price <= level

    def _known_risk_within_cap(self, direction: str, state: dict) -> bool:
        stop_offset = self.stop_offset_ticks * self.tick_size
        if direction == "long":
            risk_points = float(state["price"]) - (float(state["low"]) - stop_offset)
        else:
            risk_points = (float(state["high"]) + stop_offset) - float(state["price"])
        return 0 < risk_points <= self.max_signal_risk_points
