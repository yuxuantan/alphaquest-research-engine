from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.yush_range_1 import YushRange1Entry
from alphaquest.strategy_modules.entry.yush_range_27 import (
    _level_type_filter_with_opening_range,
    _raw_level_list,
)
from alphaquest.utils.time import parse_time


class YushTrend74Entry(YushRange1Entry):
    name = "yush_trend_74"

    def __init__(self, params: dict):
        raw_allowed = params.get("allowed_market_level_types")
        super_params = dict(params)
        if raw_allowed not in (None, ""):
            super_params["allowed_market_level_types"] = [
                item for item in _raw_level_list(raw_allowed) if item not in {"ORH", "ORL"}
            ]
        super().__init__(super_params)
        self.allowed_market_level_types = _level_type_filter_with_opening_range(raw_allowed)
        self.opening_range_start_time = parse_time(params.get("opening_range_start_time", "09:30:00"))
        self.opening_range_seconds = float(params.get("opening_range_seconds", 32.0))
        self.breakout_hold_seconds = float(params.get("breakout_hold_seconds", 1.0))
        self.breakout_hold_ticks = int(params.get("breakout_hold_ticks", 0))
        self.probe_ticks = int(params.get("probe_ticks", 2))
        self.max_signal_risk_points = float(params.get("max_signal_risk_points", 6.0))
        self._opening_range_high: float | None = None
        self._opening_range_low: float | None = None
        self._pending_breakouts: dict[tuple[str, str, float], dict] = {}
        self._validate_trend74_params()

    def _roll_session(self, bar: pd.Series) -> None:
        previous = self.session_key
        super()._roll_session(bar)
        if self.session_key != previous:
            self._opening_range_high = None
            self._opening_range_low = None
            self._pending_breakouts = {}

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

        for tick_state in self._iter_tick_states(detail_rows, bar_timestamp):
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
                    pending = self._update_breakout_state(direction, level, tick_state)
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

    def _market_levels(self, bar: pd.Series) -> list[dict]:
        levels = super()._market_levels(bar)
        if self._level_allowed("ORH") and self._opening_range_high is not None:
            levels.append({"type": "ORH", "price": self._opening_range_high})
        if self._level_allowed("ORL") and self._opening_range_low is not None:
            levels.append({"type": "ORL", "price": self._opening_range_low})
        return levels

    def _level_allowed(self, label: str) -> bool:
        return self.allowed_market_level_types is None or label in self.allowed_market_level_types

    def _update_opening_range(self, detail_rows: pd.DataFrame) -> None:
        if "timestamp" not in detail_rows:
            return
        timestamps = pd.to_datetime(detail_rows["timestamp"])
        if timestamps.empty:
            return
        first_timestamp = pd.Timestamp(timestamps.iloc[0])
        start = first_timestamp.replace(
            hour=self.opening_range_start_time.hour,
            minute=self.opening_range_start_time.minute,
            second=self.opening_range_start_time.second,
            microsecond=0,
        )
        end = start + pd.Timedelta(seconds=self.opening_range_seconds)
        if pd.Timestamp(timestamps.iloc[-1]) < start or first_timestamp >= end:
            return
        mask = (timestamps >= start) & (timestamps < end)
        if not bool(mask.any()):
            return
        high_source = detail_rows.loc[mask, "high"] if "high" in detail_rows else detail_rows.loc[mask, "close"]
        low_source = detail_rows.loc[mask, "low"] if "low" in detail_rows else detail_rows.loc[mask, "close"]
        high = pd.to_numeric(high_source, errors="coerce").max()
        low = pd.to_numeric(low_source, errors="coerce").min()
        if pd.notna(high):
            high = float(high)
            self._opening_range_high = high if self._opening_range_high is None else max(self._opening_range_high, high)
        if pd.notna(low):
            low = float(low)
            self._opening_range_low = low if self._opening_range_low is None else min(self._opening_range_low, low)

    def _update_breakout_state(self, direction: str, level: dict, tick_state: dict) -> dict | None:
        level_price = float(level["price"])
        high = self.state.current_bar_high
        low = self.state.current_bar_low
        price = float(tick_state["price"])
        if high is None or low is None:
            return None
        probe = self.probe_ticks * self.tick_size
        hold = self.breakout_hold_ticks * self.tick_size
        key = (direction, str(level["type"]), level_price)
        pending = self._pending_breakouts.get(key)
        if pending is None:
            broke = high >= level_price + probe if direction == "long" else low <= level_price - probe
            if not broke:
                return None
            pending = {
                "direction": direction,
                "market_level_type": str(level["type"]),
                "market_level_price": level_price,
                "breakout_timestamp": tick_state["timestamp"],
                "breakout_high": float(high),
                "breakout_low": float(low),
                "hold_start": None,
                "confirmed": False,
                "confirmed_at": None,
            }
            self._pending_breakouts[key] = pending

        pending["breakout_high"] = max(float(pending["breakout_high"]), float(high))
        pending["breakout_low"] = min(float(pending["breakout_low"]), float(low))
        accepted = price >= level_price + hold if direction == "long" else price <= level_price - hold
        if not accepted:
            pending["hold_start"] = None
            pending["confirmed"] = False
            pending["confirmed_at"] = None
            return pending
        if pending["hold_start"] is None:
            pending["hold_start"] = tick_state["timestamp"]
        if (tick_state["timestamp"] - pending["hold_start"]).total_seconds() >= self.breakout_hold_seconds:
            pending["confirmed"] = True
            pending["confirmed_at"] = tick_state["timestamp"]
        return pending

    def _signal_stop_price(self, direction: str, pending: dict) -> float:
        offset = self.stop_offset_ticks * self.tick_size
        level = float(pending["market_level_price"])
        return level - offset if direction == "long" else level + offset

    def _signal_risk_points(self, direction: str, pending: dict, tick_state: dict) -> float | None:
        entry = float(tick_state["price"])
        stop = self._signal_stop_price(direction, pending)
        risk = entry - stop if direction == "long" else stop - entry
        return risk if math.isfinite(risk) and risk > 0 else None

    def _signal_for_breakout(
        self,
        *,
        direction: str,
        bar: pd.Series,
        tick_state: dict,
        pending: dict,
        confirmation: dict,
        risk_points: float,
    ) -> Signal:
        del bar
        entry_price = float(tick_state["price"])
        stop_price = self._signal_stop_price(direction, pending)
        fields = {
            "setup_mode": self.name,
            "entry_mode": "intrabar",
            "entry_reference_price": entry_price,
            "intrabar_entry_price": entry_price,
            "signal_timestamp": tick_state["timestamp"],
            "intended_entry_timestamp": tick_state["timestamp"],
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "market_level_type": pending["market_level_type"],
            "market_level_price": pending["market_level_price"],
            "market_sweep_window": "current_developing_3m",
            "market_sweep_source": "current_developing_scid_path",
            "breakout_timestamp": pending["breakout_timestamp"],
            "breakout_hold_start": pending["hold_start"],
            "breakout_confirmed_at": pending["confirmed_at"],
            "breakout_hold_seconds": self.breakout_hold_seconds,
            "breakout_hold_ticks": self.breakout_hold_ticks,
            "probe_ticks": self.probe_ticks,
            "max_signal_risk_points": self.max_signal_risk_points,
            "signal_risk_points": risk_points,
            "signal_stop_price": stop_price,
            "delta_bucket_points": self.delta_bucket_points,
            "orderflow_confirmation_type": confirmation["confirmation_type"],
            "orderflow_bucket_bottom": confirmation["bucket_bottom"],
            "orderflow_bucket_top": confirmation["bucket_top"],
            "orderflow_bucket_delta": confirmation["delta"],
            "orderflow_hold_start": confirmation["hold_start"],
            "orderflow_confirmed_at": confirmation["confirmed_at"],
            "confirmation_modes": ",".join(self.confirmation_modes),
            "absorption_delta_threshold": self.absorption_delta_threshold,
            "absorption_hold_seconds": self.absorption_hold_seconds,
            "intrabar_source": "sierra_scid_record_replay",
            "intrabar_source_quality_label": (
                "Sierra SCID record close-only replay; raw high/low are not treated as traded-price extrema; "
                "not exchange MBO sequencing."
            ),
            "confirmation_high": entry_price,
            "confirmation_low": entry_price,
        }
        return Signal(
            direction=direction,
            level_type=f"{self.name}_{direction}_{pending['market_level_type']}",
            swept_level=float(pending["market_level_price"]),
            sweep_timestamp=pending["breakout_timestamp"],
            sweep_high=float(pending["breakout_high"]),
            sweep_low=float(pending["breakout_low"]),
            reclaim_timestamp=tick_state["timestamp"],
            breakout_level=float(pending["market_level_price"]),
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _validate_trend74_params(self) -> None:
        if self.opening_range_seconds <= 0:
            raise ValueError("entry.params.opening_range_seconds must be greater than 0.")
        if self.breakout_hold_seconds < 0:
            raise ValueError("entry.params.breakout_hold_seconds must be non-negative.")
        if self.breakout_hold_ticks < 0 or self.probe_ticks < 0:
            raise ValueError("entry.params breakout/probe tick settings must be non-negative.")
        if not math.isfinite(self.max_signal_risk_points) or self.max_signal_risk_points <= 0:
            raise ValueError("entry.params.max_signal_risk_points must be positive and finite.")
