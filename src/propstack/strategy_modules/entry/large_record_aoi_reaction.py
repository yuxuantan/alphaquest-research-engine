from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.profile_aoi_footprint_trap import (
    ProfileAoiFootprintTrapEntry,
    _finite_float,
)


class LargeRecordAoiReactionEntry(ProfileAoiFootprintTrapEntry):
    name = "large_record_aoi_reaction"

    _MODES = {
        "market_aoi_large_record_two_sided_trap",
        "market_aoi_large_record_two_sided_continuation",
        "profile_value_large_record_two_sided_trap",
        "profile_value_large_record_two_sided_continuation",
        "combined_aoi_profile_large_record_reaction",
    }

    def __init__(self, params: dict):
        super().__init__(params)
        self.min_large200_record_volume = float(params.get("min_large200_record_volume", 200))
        self.large_record_max_volume_col = str(
            params.get("large_record_max_volume_col", "large200_record_max_volume")
        )
        self.large_record_total_volume_col = str(
            params.get("large_record_total_volume_col", "large200_record_volume")
        )
        self.large_record_signed_volume_col = str(
            params.get("large_record_signed_volume_col", "large200_record_signed_volume")
        )
        self.large_record_count_col = str(params.get("large_record_count_col", "large200_record_count"))
        self.session_signal_counts: dict[object, int] = {}
        self._validate_large_record_params()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        if not bool(bar.get("is_rth", False)):
            return None
        session_date = bar.get("session_date")
        signal = None
        signals_today = self.session_signal_counts.get(session_date, 0)
        if (
            self.prior_profile is not None
            and signals_today < self.max_trades_per_day
            and trades_today < self.max_trades_per_day
        ):
            signal = self._signal_from_completed_bar(bar)
            if signal is not None:
                self.session_signal_counts[session_date] = signals_today + 1
        self.current_session_bars.append(bar.copy())
        return signal

    def _signal_from_completed_bar(self, bar: pd.Series) -> Signal | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None

        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        open_price = _finite_float(bar.get("open"))
        close = _finite_float(bar.get("close"))
        volume = _finite_float(bar.get("volume"))
        if None in {high, low, open_price, close} or volume is None or volume <= 0:
            return None

        large_record = self._large_record_state(bar)
        if large_record is None:
            return None

        for candidate in self._candidate_setups(bar):
            direction, reaction, aoi_type, level, profile_match = candidate
            if direction == "long" and not self.allow_long:
                continue
            if direction == "short" and not self.allow_short:
                continue
            if reaction == "trap":
                confirms = (
                    self._long_trap_confirms_large_record(large_record, level, open_price, low, close)
                    if direction == "long"
                    else self._short_trap_confirms_large_record(large_record, level, open_price, high, close)
                )
            else:
                confirms = (
                    self._long_continuation_confirms_large_record(
                        large_record, level, open_price, high, close
                    )
                    if direction == "long"
                    else self._short_continuation_confirms_large_record(
                        large_record, level, open_price, low, close
                    )
                )
            if confirms:
                return self._large_record_signal(
                    direction,
                    reaction,
                    aoi_type,
                    level,
                    profile_match,
                    large_record,
                    bar,
                    signal_timestamp,
                )
        return None

    def _candidate_setups(self, bar: pd.Series) -> list[tuple[str, str, str, float, dict]]:
        candidates: list[tuple[str, str, str, float, dict]] = []
        mode = self.setup_mode
        if mode in {
            "market_aoi_large_record_two_sided_trap",
            "combined_aoi_profile_large_record_reaction",
        }:
            candidates.extend(self._market_aoi_candidates(bar, "trap"))
        if mode in {
            "market_aoi_large_record_two_sided_continuation",
            "combined_aoi_profile_large_record_reaction",
        }:
            candidates.extend(self._market_aoi_candidates(bar, "continuation"))
        if mode in {
            "profile_value_large_record_two_sided_trap",
            "combined_aoi_profile_large_record_reaction",
        }:
            candidates.extend(self._profile_value_candidates("trap"))
        if mode in {
            "profile_value_large_record_two_sided_continuation",
            "combined_aoi_profile_large_record_reaction",
        }:
            candidates.extend(self._profile_value_candidates("continuation"))
        return candidates

    def _market_aoi_candidates(self, bar: pd.Series, reaction: str) -> list[tuple[str, str, str, float, dict]]:
        raw_candidates: list[tuple[str, str, float | None]] = []
        if reaction == "trap":
            raw_candidates.append(("long", "prior_rth_low", _finite_float(bar.get("prev_rth_low"))))
            raw_candidates.append(("short", "prior_rth_high", _finite_float(bar.get("prev_rth_high"))))
            opening = self._opening_range()
            if opening is not None:
                raw_candidates.append(("long", "opening_range_low", opening["low"]))
                raw_candidates.append(("short", "opening_range_high", opening["high"]))
        else:
            raw_candidates.append(("long", "prior_rth_high", _finite_float(bar.get("prev_rth_high"))))
            raw_candidates.append(("short", "prior_rth_low", _finite_float(bar.get("prev_rth_low"))))
            opening = self._opening_range()
            if opening is not None:
                raw_candidates.append(("long", "opening_range_high", opening["high"]))
                raw_candidates.append(("short", "opening_range_low", opening["low"]))

        candidates: list[tuple[str, str, str, float, dict]] = []
        for direction, aoi_type, level in raw_candidates:
            if level is None:
                continue
            profile_match = self._nearest_profile_level(level)
            if profile_match is None:
                continue
            candidates.append((direction, reaction, aoi_type, level, profile_match))
        return candidates

    def _profile_value_candidates(self, reaction: str) -> list[tuple[str, str, str, float, dict]]:
        profile = self.prior_profile or {}
        candidates: list[tuple[str, str, str, float, dict]] = []
        if reaction == "trap":
            val = _finite_float(profile.get("val"))
            vah = _finite_float(profile.get("vah"))
            if val is not None:
                candidates.append(
                    ("long", reaction, "prior_value_area_low", val, self._direct_profile_match("val", val))
                )
            if vah is not None:
                candidates.append(
                    ("short", reaction, "prior_value_area_high", vah, self._direct_profile_match("vah", vah))
                )
        else:
            vah = _finite_float(profile.get("vah"))
            val = _finite_float(profile.get("val"))
            if vah is not None:
                candidates.append(
                    ("long", reaction, "prior_value_area_high", vah, self._direct_profile_match("vah", vah))
                )
            if val is not None:
                candidates.append(
                    ("short", reaction, "prior_value_area_low", val, self._direct_profile_match("val", val))
                )
        return candidates

    def _direct_profile_match(self, profile_type: str, price: float) -> dict:
        profile = self.prior_profile or {}
        return {
            "profile_level_type": profile_type,
            "profile_level_price": float(price),
            "profile_distance_ticks": 0.0,
            "prior_profile_session": profile.get("session_date"),
            "prior_profile_total_volume": profile.get("total_volume"),
            "prior_profile_bars": profile.get("bar_count"),
        }

    def _large_record_state(self, bar: pd.Series) -> dict | None:
        max_volume = _finite_float(bar.get(self.large_record_max_volume_col))
        total_volume = _finite_float(bar.get(self.large_record_total_volume_col))
        signed_volume = _finite_float(bar.get(self.large_record_signed_volume_col))
        record_count = _finite_float(bar.get(self.large_record_count_col)) or 0.0
        if (
            max_volume is None
            or total_volume is None
            or signed_volume is None
            or max_volume < self.min_large200_record_volume
            or total_volume <= 0
            or signed_volume == 0
        ):
            return None
        return {
            "max_volume": max_volume,
            "total_volume": total_volume,
            "signed_volume": signed_volume,
            "record_count": record_count,
            "dominant_side": "buy" if signed_volume > 0 else "sell",
        }

    def _long_trap_confirms_large_record(
        self,
        large_record: dict,
        level: float,
        open_price: float,
        low: float,
        close: float,
    ) -> bool:
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        return (
            large_record["signed_volume"] < 0
            and low <= level - probe
            and close >= level + confirm
            and close > open_price
        )

    def _short_trap_confirms_large_record(
        self,
        large_record: dict,
        level: float,
        open_price: float,
        high: float,
        close: float,
    ) -> bool:
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        return (
            large_record["signed_volume"] > 0
            and high >= level + probe
            and close <= level - confirm
            and close < open_price
        )

    def _long_continuation_confirms_large_record(
        self,
        large_record: dict,
        level: float,
        open_price: float,
        high: float,
        close: float,
    ) -> bool:
        confirm = self.confirmation_ticks * self.tick_size
        return (
            large_record["signed_volume"] > 0
            and open_price <= level
            and high >= level + confirm
            and close >= level + confirm
            and close > open_price
        )

    def _short_continuation_confirms_large_record(
        self,
        large_record: dict,
        level: float,
        open_price: float,
        low: float,
        close: float,
    ) -> bool:
        confirm = self.confirmation_ticks * self.tick_size
        return (
            large_record["signed_volume"] < 0
            and open_price >= level
            and low <= level - confirm
            and close <= level - confirm
            and close < open_price
        )

    def _large_record_signal(
        self,
        direction: str,
        reaction: str,
        aoi_type: str,
        level: float,
        profile_match: dict,
        large_record: dict,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
    ) -> Signal:
        signed = _finite_float(bar.get("signed_volume")) or 0.0
        volume = _finite_float(bar.get("volume")) or 0.0
        delta_imbalance = signed / volume if volume > 0 else 0.0
        fields = {
            "setup_mode": self.setup_mode,
            "reaction_model": reaction,
            "aoi_type": aoi_type,
            "aoi_level": float(level),
            **profile_match,
            "min_probe_ticks": self.min_probe_ticks,
            "confirmation_ticks": self.confirmation_ticks,
            "max_profile_distance_ticks": self.max_profile_distance_ticks,
            "min_large200_record_volume": self.min_large200_record_volume,
            "large200_record_max_volume": large_record["max_volume"],
            "large200_record_volume": large_record["total_volume"],
            "large200_record_signed_volume": large_record["signed_volume"],
            "large200_record_count": large_record["record_count"],
            "large200_record_dominant_side": large_record["dominant_side"],
            "signed_volume": signed,
            "delta_imbalance": delta_imbalance,
            "source_quality_label": "Sierra SCID large-record proxy; not vendor-equivalent print data",
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"{aoi_type}_{profile_match['profile_level_type']}_{reaction}_large200_record",
            swept_level=float(level),
            sweep_timestamp=bar["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            breakout_level=float(level),
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _validate_large_record_params(self) -> None:
        if not math.isfinite(self.min_large200_record_volume) or self.min_large200_record_volume < 200:
            raise ValueError("entry.params.min_large200_record_volume must be at least 200.")
