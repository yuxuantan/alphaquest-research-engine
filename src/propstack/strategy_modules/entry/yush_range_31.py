from __future__ import annotations

from collections import deque
import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class YushRange31Entry:
    name = "yush_range_31"

    _MODES = {
        "developing_value_large_record_trap_two_sided",
        "developing_lvn_large_record_trap_two_sided",
        "developing_value_large_record_acceptance_two_sided",
        "developing_lvn_large_record_acceptance_two_sided",
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "developing_value_large_record_trap_two_sided")).lower()
        self.start_time = parse_time(params.get("start_time", "09:33:00"))
        self.end_time = parse_time(params.get("end_time", "11:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:53:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 3))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_probe_ticks = float(params.get("min_probe_ticks", 1))
        self.confirmation_ticks = float(params.get("confirmation_ticks", 0))
        self.stop_offset_ticks = float(params.get("stop_offset_ticks", 2))
        self.max_signal_risk_points = float(params.get("max_signal_risk_points", 6.0))
        self.target_extension_fraction = float(params.get("target_extension_fraction", 1.0))
        self.min_target_points = float(params.get("min_target_points", 2.0))
        self.range_snapshot_minutes = float(params.get("range_snapshot_minutes", 30.0))
        self.max_range_change_pct = float(params.get("max_range_change_pct", 0.20))
        self.value_area_fraction = float(params.get("value_area_fraction", 0.70))
        self.max_lvn_count = int(params.get("max_lvn_count", 6))
        self.min_profile_total_volume = float(params.get("min_profile_total_volume", 100.0))
        self.min_profile_price_levels = float(params.get("min_profile_price_levels", 3.0))
        self.min_large200_record_volume = float(params.get("min_large200_record_volume", 200.0))
        self.min_large200_signed_share = float(params.get("min_large200_signed_share", 0.35))
        self.min_bar_signed_imbalance = float(params.get("min_bar_signed_imbalance", 0.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 3))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.profile_prefix = str(params.get("profile_prefix", "developing_vap"))
        self._session_key = None
        self._session_high: float | None = None
        self._session_low: float | None = None
        self._range_snapshots: deque[tuple[pd.Timestamp, float]] = deque()
        self._signals_by_session: dict[object, int] = {}
        self._latest_range_change_pct: float | None = None
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        self._update_session_range(bar, signal_timestamp)
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        if self._signals_by_session.get(self._session_key, 0) >= self.max_trades_per_day:
            return None
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        profile = self._developing_profile(bar)
        if profile is None or not self._profile_is_balanced(profile):
            return None
        if not self._range_is_stable(signal_timestamp):
            return None

        large_record = self._large_record_state(bar)
        if large_record is None:
            return None
        bar_imbalance = self._bar_signed_imbalance(bar)
        if bar_imbalance is None or abs(bar_imbalance) < self.min_bar_signed_imbalance:
            return None

        open_price = _finite_float(bar.get("open"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        if None in {open_price, high, low, close}:
            return None

        for direction, boundary_type, boundary, reaction_type in self._candidates(profile):
            if direction == "long" and not self.allow_long:
                continue
            if direction == "short" and not self.allow_short:
                continue
            if not self._large_record_side_confirms(direction, reaction_type, large_record):
                continue
            if not self._bar_imbalance_side_confirms(direction, reaction_type, bar_imbalance):
                continue
            if reaction_type == "trap" and not self._trap_confirms(
                direction, boundary, open_price, high, low, close
            ):
                continue
            if reaction_type == "acceptance" and not self._acceptance_confirms(
                direction, boundary, open_price, high, low, close
            ):
                continue
            signal = self._signal(
                direction=direction,
                boundary_type=boundary_type,
                boundary=boundary,
                reaction_type=reaction_type,
                profile=profile,
                bar=bar,
                signal_timestamp=signal_timestamp,
                large_record=large_record,
                bar_imbalance=bar_imbalance,
            )
            if signal is None:
                continue
            self._signals_by_session[self._session_key] = self._signals_by_session.get(self._session_key, 0) + 1
            return signal
        return None

    def _roll_session(self, bar: pd.Series) -> None:
        key = bar.get("session_date")
        if key == self._session_key:
            return
        self._session_key = key
        self._session_high = None
        self._session_low = None
        self._range_snapshots = deque()
        self._latest_range_change_pct = None

    def _update_session_range(self, bar: pd.Series, timestamp: pd.Timestamp) -> None:
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        if high is None or low is None:
            return
        self._session_high = high if self._session_high is None else max(self._session_high, high)
        self._session_low = low if self._session_low is None else min(self._session_low, low)
        current_range = self._session_range
        if current_range is None:
            return
        self._range_snapshots.append((timestamp, current_range))
        cutoff = timestamp - pd.Timedelta(minutes=max(self.range_snapshot_minutes * 2.0, self.range_snapshot_minutes + 10.0))
        while self._range_snapshots and self._range_snapshots[0][0] < cutoff:
            self._range_snapshots.popleft()

    @property
    def _session_range(self) -> float | None:
        if self._session_high is None or self._session_low is None:
            return None
        return self._session_high - self._session_low

    def _range_is_stable(self, timestamp: pd.Timestamp) -> bool:
        current_range = self._session_range
        past_range = self._range_at(timestamp - pd.Timedelta(minutes=self.range_snapshot_minutes))
        if current_range is None or past_range is None or past_range <= 0:
            self._latest_range_change_pct = None
            return False
        change = abs(current_range - past_range) / past_range
        self._latest_range_change_pct = change
        return change < self.max_range_change_pct

    def _range_at(self, target_timestamp: pd.Timestamp) -> float | None:
        for timestamp, value in reversed(self._range_snapshots):
            if timestamp <= target_timestamp:
                return value
        return None

    def _developing_profile(self, bar: pd.Series) -> dict | None:
        prefix = self.profile_prefix
        poc = _finite_float(bar.get(f"{prefix}_poc"))
        vah = _finite_float(bar.get(f"{prefix}_vah"))
        val = _finite_float(bar.get(f"{prefix}_val"))
        lvn_high = _finite_float(bar.get(f"{prefix}_lvn_near_high"))
        lvn_low = _finite_float(bar.get(f"{prefix}_lvn_near_low"))
        total_volume = _finite_float(bar.get(f"{prefix}_total_volume"))
        price_levels = _finite_float(bar.get(f"{prefix}_price_levels"))
        lvn_count = _finite_float(bar.get(f"{prefix}_lvn_count")) or 0.0
        if None in {poc, vah, val}:
            return None
        if vah <= val:
            return None
        if total_volume is not None and total_volume < self.min_profile_total_volume:
            return None
        if price_levels is not None and price_levels < self.min_profile_price_levels:
            return None
        if lvn_count > self.max_lvn_count:
            return None
        return {
            "prefix": prefix,
            "session": _finite_float(bar.get(f"{prefix}_session_yyyymmdd")),
            "poc": poc,
            "vah": vah,
            "val": val,
            "lvn_near_high": lvn_high,
            "lvn_near_low": lvn_low,
            "lvn_count": lvn_count,
            "total_volume": total_volume,
            "price_levels": price_levels,
        }

    def _profile_is_balanced(self, profile: dict) -> bool:
        val = float(profile["val"])
        vah = float(profile["vah"])
        poc = float(profile["poc"])
        width = vah - val
        if width <= 0:
            return False
        lower = val + width / 3.0
        upper = vah - width / 3.0
        return lower <= poc <= upper

    def _candidates(self, profile: dict) -> list[tuple[str, str, float, str]]:
        if self.setup_mode == "developing_value_large_record_trap_two_sided":
            return [
                ("long", "val", profile["val"], "trap"),
                ("short", "vah", profile["vah"], "trap"),
            ]
        if self.setup_mode == "developing_lvn_large_record_trap_two_sided":
            return [
                ("long", "lvn_near_low", profile["lvn_near_low"], "trap"),
                ("short", "lvn_near_high", profile["lvn_near_high"], "trap"),
            ]
        if self.setup_mode == "developing_lvn_large_record_acceptance_two_sided":
            return [
                ("long", "lvn_near_high", profile["lvn_near_high"], "acceptance"),
                ("short", "lvn_near_low", profile["lvn_near_low"], "acceptance"),
            ]
        return [
            ("long", "vah", profile["vah"], "acceptance"),
            ("short", "val", profile["val"], "acceptance"),
        ]

    def _large_record_state(self, bar: pd.Series) -> dict | None:
        max_volume = _finite_float(bar.get("large200_record_max_volume"))
        total_volume = _finite_float(bar.get("large200_record_volume"))
        signed_volume = _finite_float(bar.get("large200_record_signed_volume"))
        record_count = _finite_float(bar.get("large200_record_count")) or 0.0
        if (
            max_volume is None
            or total_volume is None
            or signed_volume is None
            or max_volume < self.min_large200_record_volume
            or total_volume <= 0
            or signed_volume == 0
        ):
            return None
        signed_share = abs(signed_volume) / total_volume
        if not math.isfinite(signed_share) or signed_share < self.min_large200_signed_share:
            return None
        return {
            "max_volume": max_volume,
            "total_volume": total_volume,
            "signed_volume": signed_volume,
            "signed_share": signed_share,
            "record_count": record_count,
            "dominant_side": "buy" if signed_volume > 0 else "sell",
        }

    def _bar_signed_imbalance(self, bar: pd.Series) -> float | None:
        signed = _finite_float(bar.get("signed_volume"))
        volume = _finite_float(bar.get("volume"))
        if signed is None or volume is None or volume <= 0:
            return None
        imbalance = signed / volume
        return imbalance if math.isfinite(imbalance) else None

    def _large_record_side_confirms(self, direction: str, reaction_type: str, large_record: dict) -> bool:
        signed = float(large_record["signed_volume"])
        if reaction_type == "trap":
            return signed < 0 if direction == "long" else signed > 0
        return signed > 0 if direction == "long" else signed < 0

    def _bar_imbalance_side_confirms(self, direction: str, reaction_type: str, imbalance: float) -> bool:
        if self.min_bar_signed_imbalance <= 0:
            return True
        if reaction_type == "trap":
            return imbalance < 0 if direction == "long" else imbalance > 0
        return imbalance > 0 if direction == "long" else imbalance < 0

    def _trap_confirms(
        self,
        direction: str,
        boundary: float | None,
        open_price: float,
        high: float,
        low: float,
        close: float,
    ) -> bool:
        if boundary is None:
            return False
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        if direction == "long":
            return low <= boundary - probe and close >= boundary + confirm and close > open_price
        return high >= boundary + probe and close <= boundary - confirm and close < open_price

    def _acceptance_confirms(
        self,
        direction: str,
        boundary: float | None,
        open_price: float,
        high: float,
        low: float,
        close: float,
    ) -> bool:
        if boundary is None:
            return False
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        if direction == "long":
            return high >= boundary + probe and close >= boundary + confirm and close > open_price
        return low <= boundary - probe and close <= boundary - confirm and close < open_price

    def _signal(
        self,
        *,
        direction: str,
        boundary_type: str,
        boundary: float,
        reaction_type: str,
        profile: dict,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
        large_record: dict,
        bar_imbalance: float,
    ) -> Signal | None:
        open_price = float(bar["open"])
        high = float(bar["high"])
        low = float(bar["low"])
        close = float(bar["close"])
        stop_offset = self.stop_offset_ticks * self.tick_size
        if direction == "long":
            stop = low - stop_offset
            target = self._target_price("long", reaction_type, close, profile)
        else:
            stop = high + stop_offset
            target = self._target_price("short", reaction_type, close, profile)
        risk = abs(close - stop)
        if risk <= 0 or risk > self.max_signal_risk_points:
            return None
        fields = {
            "setup_mode": self.setup_mode,
            "reaction_type": reaction_type,
            "entry_mode": "bar_close",
            "decision_bar_timestamp": bar["timestamp"],
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "entry_reference_price": close,
            "signal_stop_price": stop,
            "signal_target_price": target,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "boundary_type": boundary_type,
            "boundary_level": boundary,
            "min_probe_ticks": self.min_probe_ticks,
            "confirmation_ticks": self.confirmation_ticks,
            "stop_offset_ticks": self.stop_offset_ticks,
            "signal_risk_points_from_bar_close": risk,
            "max_signal_risk_points": self.max_signal_risk_points,
            "developing_vap_prefix": profile["prefix"],
            "developing_vap_session": profile["session"],
            "developing_vap_poc": profile["poc"],
            "developing_vap_vah": profile["vah"],
            "developing_vap_val": profile["val"],
            "developing_vap_lvn_near_high": profile["lvn_near_high"],
            "developing_vap_lvn_near_low": profile["lvn_near_low"],
            "developing_vap_lvn_count": profile["lvn_count"],
            "developing_vap_total_volume": profile["total_volume"],
            "developing_vap_price_levels": profile["price_levels"],
            "value_area_fraction": self.value_area_fraction,
            "profile_poc_middle_third": True,
            "session_range": self._session_range,
            "range_snapshot_minutes": self.range_snapshot_minutes,
            "range_change_pct": self._latest_range_change_pct,
            "max_range_change_pct": self.max_range_change_pct,
            "large200_record_max_volume": large_record["max_volume"],
            "large200_record_volume": large_record["total_volume"],
            "large200_record_signed_volume": large_record["signed_volume"],
            "large200_record_signed_share": large_record["signed_share"],
            "large200_record_count": large_record["record_count"],
            "large200_record_dominant_side": large_record["dominant_side"],
            "bar_signed_imbalance": bar_imbalance,
            "min_large200_record_volume": self.min_large200_record_volume,
            "min_large200_signed_share": self.min_large200_signed_share,
            "min_bar_signed_imbalance": self.min_bar_signed_imbalance,
            "source_quality_label": "Completed 3-minute Sierra large200/VAP cache; large records are SCID aggregate proxy, not MBO prints.",
            "target_reference": "opposite_value_area_edge" if reaction_type == "trap" else "value_area_width_extension",
            "stop_reference": "completed_bar_extreme_plus_offset",
        }
        return Signal(
            direction=direction,
            level_type=f"{self.name}_{boundary_type}_{reaction_type}",
            swept_level=float(boundary),
            sweep_timestamp=bar["timestamp"],
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=signal_timestamp,
            breakout_level=float(boundary),
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _target_price(self, direction: str, reaction_type: str, close: float, profile: dict) -> float:
        width = max(float(profile["vah"]) - float(profile["val"]), self.min_target_points)
        if reaction_type == "trap":
            return float(profile["vah"] if direction == "long" else profile["val"])
        extension = max(width * self.target_extension_fraction, self.min_target_points)
        return close + extension if direction == "long" else close - extension

    def _validate(self) -> None:
        if self.setup_mode not in self._MODES:
            raise ValueError(f"entry.params.setup_mode must be one of {sorted(self._MODES)}.")
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0 or self.tick_size <= 0:
            raise ValueError("entry.params bar_interval_minutes and tick_size must be positive.")
        for name, value in {
            "min_probe_ticks": self.min_probe_ticks,
            "confirmation_ticks": self.confirmation_ticks,
            "stop_offset_ticks": self.stop_offset_ticks,
            "max_signal_risk_points": self.max_signal_risk_points,
            "target_extension_fraction": self.target_extension_fraction,
            "min_target_points": self.min_target_points,
            "range_snapshot_minutes": self.range_snapshot_minutes,
            "max_range_change_pct": self.max_range_change_pct,
            "min_profile_total_volume": self.min_profile_total_volume,
            "min_profile_price_levels": self.min_profile_price_levels,
            "min_large200_record_volume": self.min_large200_record_volume,
            "min_large200_signed_share": self.min_large200_signed_share,
            "min_bar_signed_imbalance": self.min_bar_signed_imbalance,
        }.items():
            if not math.isfinite(float(value)):
                raise ValueError(f"entry.params.{name} must be finite.")
        if self.min_probe_ticks < 0 or self.confirmation_ticks < 0 or self.stop_offset_ticks < 0:
            raise ValueError("entry.params probe/confirmation/stop offsets must be non-negative.")
        if self.max_signal_risk_points <= 0:
            raise ValueError("entry.params.max_signal_risk_points must be positive.")
        if self.range_snapshot_minutes <= 0 or self.max_range_change_pct < 0:
            raise ValueError("entry.params range stability settings must be positive.")
        if not 0 < self.value_area_fraction <= 1:
            raise ValueError("entry.params.value_area_fraction must be between 0 and 1.")
        if self.max_lvn_count < 0:
            raise ValueError("entry.params.max_lvn_count must be non-negative.")
        if self.min_large200_record_volume < 200:
            raise ValueError("entry.params.min_large200_record_volume must be at least 200.")
        if not 0 <= self.min_large200_signed_share <= 1:
            raise ValueError("entry.params.min_large200_signed_share must be between 0 and 1.")
        if self.min_bar_signed_imbalance < 0:
            raise ValueError("entry.params.min_bar_signed_imbalance must be non-negative.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least one.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
