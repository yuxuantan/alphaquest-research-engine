from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class TpoValueEdgeAuctionRejectionEntry:
    """Completed-bar, price-only proxy for the range/value-edge auction thesis.

    The developing TPO profile is built only from completed one-minute OHLC bars.
    The current bar is deliberately excluded from the profile and AOI used to test
    that bar, so a rejection is always judged against levels known before it began.
    """

    name = "tpo_value_edge_auction_rejection"

    _SETUP_MODES = {
        "two_sided_rejection",
        "strong_close_rejection",
        "two_bar_confirmation",
        "val_long_rejection",
        "vah_short_rejection",
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "two_sided_rejection")).lower()
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "10:59:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "11:00:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.value_area_fraction = float(params.get("value_area_fraction", 0.70))
        self.opening_range_minutes = int(params.get("opening_range_minutes", 30))
        self.min_profile_bars = int(params.get("min_profile_bars", 30))
        self.min_probe_ticks = float(params.get("min_probe_ticks", 1))
        self.max_aoi_width_points = float(params.get("max_aoi_width_points", 3.0))
        self.max_range_expansion_ratio = float(params.get("max_range_expansion_ratio", 1.20))
        self.poc_middle_fraction = float(params.get("poc_middle_fraction", 1 / 3))
        self.min_close_location = float(params.get("min_close_location", 0.50))
        self.strong_close_location = float(params.get("strong_close_location", 0.70))
        self.midpoint_be_offset_points = float(params.get("midpoint_be_offset_points", 1.25))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 3))
        self.max_signals_per_session = int(params.get("max_signals_per_session", 3))
        self.cooldown_bars = int(params.get("cooldown_bars", 2))
        self.alternate_after_full_stop = bool(params.get("alternate_after_full_stop", True))

        self.current_session = None
        self.current_session_bars: list[pd.Series] = []
        self.tpo_by_tick: dict[int, int] = {}
        self.signals_by_session: dict[object, int] = {}
        self.last_signal_bar_by_session: dict[object, int] = {}
        self.required_direction_by_session: dict[object, str] = {}
        self.pending_rejection: dict[object, dict] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        if not bool(bar.get("is_rth", False)):
            return None

        session_date = bar.get("session_date")
        signal = None
        if (
            self.signals_by_session.get(session_date, 0) < self.max_signals_per_session
            and trades_today < self.max_trades_per_day
        ):
            signal = self._signal_from_completed_bar(bar)
            if signal is not None:
                self.signals_by_session[session_date] = self.signals_by_session.get(session_date, 0) + 1
                self.last_signal_bar_by_session[session_date] = len(self.current_session_bars)

        self.current_session_bars.append(bar.copy())
        self._accumulate_tpo_bar(bar)
        return signal

    def on_trade_closed(self, trade: dict) -> None:
        """Require the opposite edge only after an actual full stop exit."""
        session_date = trade.get("session_date")
        if session_date is None or not self.alternate_after_full_stop:
            return
        if str(trade.get("exit_reason", "")).lower() == "stop":
            direction = str(trade.get("direction", "")).lower()
            if direction in {"long", "short"}:
                self.required_direction_by_session[session_date] = (
                    "short" if direction == "long" else "long"
                )
        else:
            self.required_direction_by_session.pop(session_date, None)

    def _roll_session(self, bar: pd.Series) -> None:
        session_date = bar.get("session_date")
        if session_date == self.current_session:
            return
        self.current_session = session_date
        self.current_session_bars = []
        self.tpo_by_tick = {}

    def _signal_from_completed_bar(self, bar: pd.Series) -> Signal | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        decision_time = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if decision_time.time() < self.start_time or decision_time.time() > self.end_time:
            return None
        if len(self.current_session_bars) < self.min_profile_bars:
            return None

        session_date = bar.get("session_date")
        last_index = self.last_signal_bar_by_session.get(session_date)
        if last_index is not None and len(self.current_session_bars) - last_index <= self.cooldown_bars:
            return None

        if self.setup_mode == "two_bar_confirmation":
            confirmed = self._confirm_pending_rejection(bar, decision_time)
            if confirmed is not None:
                return confirmed
        profile = self._developing_profile()
        opening_range = self._opening_range()
        if profile is None or opening_range is None or not self._balanced_range(profile):
            self.pending_rejection.pop(session_date, None)
            return None

        if self.setup_mode == "two_bar_confirmation":
            rejection = self._find_rejection(bar, profile, opening_range)
            if rejection is not None:
                self.pending_rejection[session_date] = {
                    **rejection,
                    "rejection_bar": bar.copy(),
                    "profile": profile,
                    "opening_range": opening_range,
                }
            else:
                self.pending_rejection.pop(session_date, None)
            return None

        rejection = self._find_rejection(bar, profile, opening_range)
        if rejection is None:
            return None
        return self._build_signal(rejection, bar, profile, opening_range, decision_time)

    def _find_rejection(self, bar: pd.Series, profile: dict, opening_range: dict) -> dict | None:
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        if None in {high, low, close} or high < low:
            return None
        bar_range = high - low
        if bar_range <= 0:
            return None

        required_direction = self.required_direction_by_session.get(bar.get("session_date"))
        min_location = (
            self.strong_close_location
            if self.setup_mode == "strong_close_rejection"
            else self.min_close_location
        )
        candidates = []
        if self.setup_mode != "vah_short_rejection":
            candidates.append(("long", profile["val"], opening_range["low"]))
        if self.setup_mode != "val_long_rejection":
            candidates.append(("short", profile["vah"], opening_range["high"]))

        for direction, value_edge, market_level in candidates:
            if required_direction is not None and direction != required_direction:
                continue
            aoi_low = min(value_edge, market_level)
            aoi_high = max(value_edge, market_level)
            aoi_width = aoi_high - aoi_low
            if aoi_width > self.max_aoi_width_points + 1e-12:
                continue
            probe = self.min_probe_ticks * self.tick_size
            close_location = (close - low) / bar_range
            if direction == "long":
                passed = low <= aoi_low - probe and close >= aoi_low and close_location >= min_location
            else:
                passed = high >= aoi_high + probe and close <= aoi_high and close_location <= 1.0 - min_location
            if passed:
                return {
                    "direction": direction,
                    "value_edge": value_edge,
                    "market_level": market_level,
                    "aoi_low": aoi_low,
                    "aoi_high": aoi_high,
                    "aoi_width": aoi_width,
                    "close_location": close_location,
                }
        return None

    def _confirm_pending_rejection(
        self,
        bar: pd.Series,
        decision_time: pd.Timestamp,
    ) -> Signal | None:
        session_date = bar.get("session_date")
        pending = self.pending_rejection.pop(session_date, None)
        if pending is None:
            return None
        close = _finite_float(bar.get("close"))
        prior_close = _finite_float(pending["rejection_bar"].get("close"))
        if close is None or prior_close is None:
            return None
        direction = pending["direction"]
        confirms = close > prior_close if direction == "long" else close < prior_close
        if not confirms:
            return None
        # Freeze the AOI and target from the rejection bar; the confirmation bar
        # cannot retroactively reprice the setup.
        return self._build_signal(
            pending,
            pending["rejection_bar"],
            pending["profile"],
            pending["opening_range"],
            decision_time,
            confirmation_bar=bar,
        )

    def _build_signal(
        self,
        rejection: dict,
        rejection_bar: pd.Series,
        profile: dict,
        opening_range: dict,
        decision_time: pd.Timestamp,
        confirmation_bar: pd.Series | None = None,
    ) -> Signal:
        direction = rejection["direction"]
        breakout_level = rejection["aoi_low"] if direction == "long" else rejection["aoi_high"]
        target = profile["vah"] if direction == "long" else profile["val"]
        midpoint = (profile["vah"] + profile["val"]) / 2.0
        fields = {
            "setup_mode": self.setup_mode,
            "profile_source": "developing_completed_bar_tpo",
            "tpo_profile_bars": len(self.current_session_bars),
            "tpo_poc": profile["poc"],
            "tpo_vah": profile["vah"],
            "tpo_val": profile["val"],
            "tpo_midpoint": midpoint,
            "opening_range_high": opening_range["high"],
            "opening_range_low": opening_range["low"],
            "aoi_anchor": "VAL" if direction == "long" else "VAH",
            "aoi_market_confluence": "ORL" if direction == "long" else "ORH",
            "aoi_low": rejection["aoi_low"],
            "aoi_high": rejection["aoi_high"],
            "aoi_width_points": rejection["aoi_width"],
            "min_probe_ticks": self.min_probe_ticks,
            "close_location_metric": rejection["close_location"],
            "range_expansion_ratio": profile["range_expansion_ratio"],
            "poc_range_location": profile["poc_range_location"],
            "signal_target_price": target,
            "dynamic_stop_trigger_price": midpoint,
            "dynamic_stop_offset_points": self.midpoint_be_offset_points,
            "signal_timestamp": decision_time,
            "intended_entry_timestamp": decision_time,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "rejection_bar_timestamp": rejection_bar["timestamp"],
            "confirmation_bar_timestamp": (
                confirmation_bar["timestamp"] if confirmation_bar is not None else None
            ),
        }
        return Signal(
            direction=direction,
            level_type=f"tpo_{fields['aoi_anchor'].lower()}_or_rejection",
            swept_level=float(rejection["value_edge"]),
            sweep_timestamp=rejection_bar["timestamp"],
            sweep_high=float(rejection_bar["high"]),
            sweep_low=float(rejection_bar["low"]),
            reclaim_timestamp=decision_time,
            opening_range_high=float(opening_range["high"]),
            opening_range_low=float(opening_range["low"]),
            opening_range_width=float(opening_range["high"] - opening_range["low"]),
            breakout_level=float(breakout_level),
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _opening_range(self) -> dict | None:
        expected = int(math.ceil(self.opening_range_minutes / self.bar_interval_minutes))
        if len(self.current_session_bars) < expected:
            return None
        bars = self.current_session_bars[:expected]
        return {
            "high": max(float(bar["high"]) for bar in bars),
            "low": min(float(bar["low"]) for bar in bars),
        }

    def _balanced_range(self, profile: dict) -> bool:
        return (
            profile["range_expansion_ratio"] <= self.max_range_expansion_ratio + 1e-12
            and profile["poc_range_location"] >= (1.0 - self.poc_middle_fraction) / 2.0
            and profile["poc_range_location"] <= (1.0 + self.poc_middle_fraction) / 2.0
        )

    def _developing_profile(self) -> dict | None:
        if len(self.current_session_bars) < self.min_profile_bars or not self.tpo_by_tick:
            return None
        ticks = sorted(self.tpo_by_tick)
        total = sum(self.tpo_by_tick.values())
        if total <= 0:
            return None
        midpoint_tick = (ticks[0] + ticks[-1]) / 2.0
        poc_tick = max(ticks, key=lambda tick: (self.tpo_by_tick[tick], -abs(tick - midpoint_tick)))
        val_tick, vah_tick = self._value_area_bounds(ticks, poc_tick, total)
        session_low = min(float(bar["low"]) for bar in self.current_session_bars)
        session_high = max(float(bar["high"]) for bar in self.current_session_bars)
        current_range = session_high - session_low
        if current_range <= 0:
            return None
        comparison_count = max(1, int(math.floor(len(self.current_session_bars) * 2.0 / 3.0)))
        comparison_bars = self.current_session_bars[:comparison_count]
        comparison_range = max(float(bar["high"]) for bar in comparison_bars) - min(
            float(bar["low"]) for bar in comparison_bars
        )
        expansion_ratio = math.inf if comparison_range <= 0 else current_range / comparison_range
        poc = poc_tick * self.tick_size
        return {
            "poc": poc,
            "vah": vah_tick * self.tick_size,
            "val": val_tick * self.tick_size,
            "range_expansion_ratio": expansion_ratio,
            "poc_range_location": (poc - session_low) / current_range,
        }

    def _value_area_bounds(self, ticks: list[int], poc_tick: int, total: int) -> tuple[int, int]:
        left = right = ticks.index(poc_tick)
        included = self.tpo_by_tick[poc_tick]
        target = self.value_area_fraction * total
        while included < target and (left > 0 or right < len(ticks) - 1):
            left_count = self.tpo_by_tick[ticks[left - 1]] if left > 0 else -1
            right_count = self.tpo_by_tick[ticks[right + 1]] if right < len(ticks) - 1 else -1
            if left_count > right_count:
                left -= 1
                included += left_count
            else:
                right += 1
                included += right_count
        return ticks[left], ticks[right]

    def _accumulate_tpo_bar(self, bar: pd.Series) -> None:
        low = _finite_float(bar.get("low"))
        high = _finite_float(bar.get("high"))
        if low is None or high is None or high < low:
            return
        low_tick = math.floor(low / self.tick_size + 1e-12)
        high_tick = math.ceil(high / self.tick_size - 1e-12)
        for tick in range(low_tick, high_tick + 1):
            self.tpo_by_tick[tick] = self.tpo_by_tick.get(tick, 0) + 1

    def _validate(self) -> None:
        if self.setup_mode not in self._SETUP_MODES:
            raise ValueError(f"Unsupported setup_mode: {self.setup_mode}")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be positive")
        if not 0 < self.value_area_fraction <= 1:
            raise ValueError("value_area_fraction must be in (0, 1]")
        if self.min_profile_bars < self.opening_range_minutes:
            raise ValueError("min_profile_bars cannot be shorter than opening_range_minutes")
        if self.max_aoi_width_points <= 0:
            raise ValueError("max_aoi_width_points must be positive")
        if not 0 < self.poc_middle_fraction <= 1:
            raise ValueError("poc_middle_fraction must be in (0, 1]")
        if not 0.5 <= self.min_close_location <= 1:
            raise ValueError("min_close_location must be in [0.5, 1]")
        if not self.min_close_location <= self.strong_close_location <= 1:
            raise ValueError("strong_close_location must be in [min_close_location, 1]")


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
