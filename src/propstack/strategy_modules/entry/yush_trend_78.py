from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.yush_trend_77 import YushTrend77Entry


class YushTrend78Entry(YushTrend77Entry):
    name = "yush_trend_78"

    def __init__(self, params: dict):
        super().__init__(params)
        self.retest_tolerance_ticks = int(params.get("retest_tolerance_ticks", 2))
        self.retest_hold_seconds = float(params.get("retest_hold_seconds", 1.0))
        self.retest_invalidation_ticks = int(params.get("retest_invalidation_ticks", 2))
        self._pending_retests: dict[tuple[str, str, float], dict] = {}
        self._validate_trend78_params()

    def _roll_session(self, bar: pd.Series) -> None:
        previous = self.session_key
        super()._roll_session(bar)
        if self.session_key != previous:
            self._pending_retests = {}

    def on_bar_intrabar(
        self,
        bar: pd.Series,
        detail_rows: pd.DataFrame,
        trades_today: int = 0,
    ) -> Signal | None:
        self._roll_session(bar)
        if detail_rows is None or detail_rows.empty:
            return None
        bar_timestamp = pd.Timestamp(bar["timestamp"])
        self._update_opening_range(detail_rows)

        levels = self._market_levels(bar)
        session_key = self.session_key
        can_emit = (
            bool(bar.get("is_rth", False))
            and trades_today < self.max_trades_per_day
            and self.signals_by_session.get(session_key, 0) < self.max_trades_per_day
            and bool(levels)
        )

        for tick in detail_rows.itertuples(index=False):
            tick_state = self.state.update_tick(
                tick,
                bar_timestamp=bar_timestamp,
                profile_bucket_points=self.profile_bucket_points,
                delta_bucket_points=self.delta_bucket_points,
                absorption_delta_threshold=self.absorption_delta_threshold,
                hold_seconds=self.absorption_hold_seconds,
                range_snapshot_minutes=self.range_snapshot_minutes,
            )
            if tick_state is None or not can_emit:
                continue
            tick_time = tick_state["timestamp"].time()
            if tick_time < self.start_time or tick_time > self.end_time:
                continue
            for direction in ("long", "short"):
                if direction == "long" and not self.allow_long:
                    continue
                if direction == "short" and not self.allow_short:
                    continue
                confirmation = self.state.confirmed_orderflow(direction, self.confirmation_modes)
                for level in levels:
                    pending = self._update_retest_state(direction, level, tick_state)
                    if pending is None or not pending.get("confirmed") or confirmation is None:
                        continue
                    risk_points = self._signal_risk_points(direction, pending, tick_state)
                    if risk_points is None or risk_points > self.max_signal_risk_points:
                        continue
                    signal = self._signal_for_breakout(
                        direction=direction,
                        bar=bar,
                        tick_state=tick_state,
                        pending=pending,
                        confirmation=confirmation,
                        risk_points=risk_points,
                    )
                    self.signals_by_session[session_key] = self.signals_by_session.get(session_key, 0) + 1
                    return signal
        return None

    def _update_retest_state(self, direction: str, level: dict, tick_state: dict) -> dict | None:
        level_type = str(level["type"])
        if not self._level_direction_allowed(direction, level_type):
            return None
        level_price = float(level["price"])
        high = self.state.current_bar_high
        low = self.state.current_bar_low
        price = float(tick_state["price"])
        if high is None or low is None:
            return None

        probe = self.probe_ticks * self.tick_size
        tolerance = self.retest_tolerance_ticks * self.tick_size
        invalidation = self.retest_invalidation_ticks * self.tick_size
        key = (direction, level_type, level_price)
        pending = self._pending_retests.get(key)
        if pending is None:
            broke = high >= level_price + probe if direction == "long" else low <= level_price - probe
            if not broke:
                return None
            pending = {
                "direction": direction,
                "market_level_type": level_type,
                "market_level_price": level_price,
                "breakout_timestamp": tick_state["timestamp"],
                "breakout_high": float(high),
                "breakout_low": float(low),
                "retested": False,
                "retest_timestamp": None,
                "hold_start": None,
                "confirmed": False,
                "confirmed_at": None,
            }
            self._pending_retests[key] = pending

        pending["breakout_high"] = max(float(pending["breakout_high"]), float(high))
        pending["breakout_low"] = min(float(pending["breakout_low"]), float(low))

        invalidated = price < level_price - invalidation if direction == "long" else price > level_price + invalidation
        if invalidated:
            self._pending_retests.pop(key, None)
            return None

        if not pending["retested"]:
            retested = (
                level_price <= price <= level_price + tolerance
                if direction == "long"
                else level_price - tolerance <= price <= level_price
            )
            if not retested:
                return pending
            pending["retested"] = True
            pending["retest_timestamp"] = tick_state["timestamp"]
            pending["hold_start"] = tick_state["timestamp"]

        accepted = price >= level_price if direction == "long" else price <= level_price
        if not accepted:
            pending["retested"] = False
            pending["retest_timestamp"] = None
            pending["hold_start"] = None
            pending["confirmed"] = False
            pending["confirmed_at"] = None
            return pending

        if pending["hold_start"] is None:
            pending["hold_start"] = tick_state["timestamp"]
        if (tick_state["timestamp"] - pending["hold_start"]).total_seconds() >= self.retest_hold_seconds:
            pending["confirmed"] = True
            pending["confirmed_at"] = tick_state["timestamp"]
        return pending

    def _signal_for_breakout(
        self,
        *,
        direction: str,
        bar,
        tick_state: dict,
        pending: dict,
        confirmation: dict,
        risk_points: float,
    ) -> Signal:
        signal = super()._signal_for_breakout(
            direction=direction,
            bar=bar,
            tick_state=tick_state,
            pending=pending,
            confirmation=confirmation,
            risk_points=risk_points,
        )
        fields = {
            "entry_pattern": "breakout_retest_continuation",
            "retest_tolerance_ticks": self.retest_tolerance_ticks,
            "retest_hold_seconds": self.retest_hold_seconds,
            "retest_invalidation_ticks": self.retest_invalidation_ticks,
            "retest_timestamp": pending["retest_timestamp"],
            "retest_confirmed_at": pending["confirmed_at"],
            "stop_reference": "broken_public_edge_retest_boundary",
        }
        signal.metadata.update(fields)
        signal.report_fields.update(fields)
        return signal

    def _validate_trend78_params(self) -> None:
        if self.retest_tolerance_ticks < 0 or self.retest_invalidation_ticks < 0:
            raise ValueError("entry.params retest tick settings must be non-negative.")
        if not math.isfinite(self.retest_hold_seconds) or self.retest_hold_seconds < 0:
            raise ValueError("entry.params.retest_hold_seconds must be non-negative and finite.")
