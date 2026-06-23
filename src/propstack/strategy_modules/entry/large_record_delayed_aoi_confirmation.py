from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class LargeRecordDelayedAoiConfirmationEntry:
    name = "large_record_delayed_aoi_confirmation"

    _MODES = {
        "all_aoi_delayed_trap",
        "market_aoi_delayed_trap",
        "opening_aoi_delayed_trap",
        "overnight_aoi_delayed_trap",
        "value_area_delayed_trap",
        "all_aoi_delayed_continuation",
        "market_aoi_delayed_continuation",
        "value_area_delayed_continuation",
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "all_aoi_delayed_trap")).lower()
        self.profile_context_mode = str(params.get("profile_context_mode", "beyond_poc")).lower()
        self.cached_profile_prefix = str(params.get("cached_profile_prefix", "prior_vap"))
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.opening_range_minutes = int(params.get("opening_range_minutes", 30))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_probe_ticks = float(params.get("min_probe_ticks", 1))
        self.confirmation_ticks = float(params.get("confirmation_ticks", 0))
        self.min_large200_record_volume = float(params.get("min_large200_record_volume", 200))
        self.min_confirm_delta_imbalance = float(params.get("min_confirm_delta_imbalance", 0.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.current_session = None
        self.current_session_bars: list[pd.Series] = []
        self.signaled_sessions: set = set()
        self.pending_events: dict[object, dict] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        if not bool(bar.get("is_rth", False)):
            return None

        session_date = bar.get("session_date")
        signal = None
        if session_date not in self.signaled_sessions and trades_today < self.max_trades_per_day:
            signal = self._confirm_pending_event(bar)
            if signal is not None:
                self.signaled_sessions.add(session_date)
                self.pending_events.pop(session_date, None)
            else:
                event = self._event_from_completed_bar(bar)
                if event is not None:
                    self.pending_events[session_date] = event
        self.current_session_bars.append(bar.copy())
        return signal

    def _roll_session(self, bar: pd.Series) -> None:
        session_date = bar.get("session_date")
        if self.current_session is None:
            self.current_session = session_date
            return
        if session_date == self.current_session:
            return
        self.current_session = session_date
        self.current_session_bars = []
        self.pending_events.clear()

    def _event_from_completed_bar(self, bar: pd.Series) -> dict | None:
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() < self.start_time or signal_timestamp.time() > self.end_time:
            return None
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        open_price = _finite_float(bar.get("open"))
        close = _finite_float(bar.get("close"))
        if None in {high, low, open_price, close}:
            return None
        large_record = self._large_record_state(bar)
        if large_record is None:
            return None
        for direction, reaction, aoi_type, level, profile_match in self._candidate_setups(bar):
            if direction == "long" and not self.allow_long:
                continue
            if direction == "short" and not self.allow_short:
                continue
            if reaction == "trap":
                ok = self._trap_event_confirms(direction, large_record, level, high, low)
            else:
                ok = self._continuation_event_confirms(direction, large_record, level, high, low)
            if ok:
                return {
                    "direction": direction,
                    "reaction": reaction,
                    "aoi_type": aoi_type,
                    "level": float(level),
                    "profile_match": profile_match,
                    "large_record": large_record,
                    "event_timestamp": timestamp,
                    "event_high": high,
                    "event_low": low,
                    "event_open": open_price,
                    "event_close": close,
                }
        return None

    def _confirm_pending_event(self, bar: pd.Series) -> Signal | None:
        session_date = bar.get("session_date")
        event = self.pending_events.get(session_date)
        if event is None:
            return None
        timestamp = pd.Timestamp(bar["timestamp"])
        expected_timestamp = event["event_timestamp"] + pd.Timedelta(minutes=self.bar_interval_minutes)
        if timestamp != expected_timestamp:
            self.pending_events.pop(session_date, None)
            return None
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if signal_timestamp.time() > self.end_time:
            self.pending_events.pop(session_date, None)
            return None
        open_price = _finite_float(bar.get("open"))
        close = _finite_float(bar.get("close"))
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        if None in {open_price, close, high, low}:
            return None
        direction = event["direction"]
        reaction = event["reaction"]
        level = event["level"]
        if reaction == "trap":
            ok = self._trap_confirmation(direction, bar, level, open_price, close)
        else:
            ok = self._continuation_confirmation(direction, bar, level, open_price, close)
        if not ok:
            self.pending_events.pop(session_date, None)
            return None
        return self._signal(event, bar, signal_timestamp)

    def _candidate_setups(self, bar: pd.Series) -> list[tuple[str, str, str, float, dict]]:
        candidates: list[tuple[str, str, str, float, dict]] = []
        mode = self.setup_mode
        if mode in {"all_aoi_delayed_trap", "market_aoi_delayed_trap"}:
            candidates.extend(self._market_aoi_candidates(bar, "trap"))
        if mode in {"all_aoi_delayed_continuation", "market_aoi_delayed_continuation"}:
            candidates.extend(self._market_aoi_candidates(bar, "continuation"))
        if mode in {"all_aoi_delayed_trap", "overnight_aoi_delayed_trap"}:
            candidates.extend(self._overnight_aoi_candidates(bar, "trap"))
        if mode == "all_aoi_delayed_continuation":
            candidates.extend(self._overnight_aoi_candidates(bar, "continuation"))
        if mode == "opening_aoi_delayed_trap":
            candidates.extend(self._opening_aoi_candidates(bar, "trap"))
        if mode == "value_area_delayed_trap":
            candidates.extend(self._value_area_candidates("trap", bar))
        if mode == "value_area_delayed_continuation":
            candidates.extend(self._value_area_candidates("continuation", bar))
        return candidates

    def _market_aoi_candidates(self, bar: pd.Series, reaction: str) -> list[tuple[str, str, str, float, dict]]:
        raw: list[tuple[str, str, float | None]] = []
        if reaction == "trap":
            raw.extend(
                [
                    ("long", "prior_rth_low", _finite_float(bar.get("prev_rth_low"))),
                    ("short", "prior_rth_high", _finite_float(bar.get("prev_rth_high"))),
                ]
            )
        else:
            raw.extend(
                [
                    ("long", "prior_rth_high", _finite_float(bar.get("prev_rth_high"))),
                    ("short", "prior_rth_low", _finite_float(bar.get("prev_rth_low"))),
                ]
            )
        raw.extend((direction, aoi, level) for direction, aoi, level in self._opening_raw_candidates(reaction))
        return self._profile_context_candidates(raw, reaction, bar)

    def _opening_aoi_candidates(self, bar: pd.Series, reaction: str) -> list[tuple[str, str, str, float, dict]]:
        return self._profile_context_candidates(self._opening_raw_candidates(reaction), reaction, bar)

    def _opening_raw_candidates(self, reaction: str) -> list[tuple[str, str, float | None]]:
        opening = self._opening_range()
        if opening is None:
            return []
        if reaction == "trap":
            return [("long", "opening_range_low", opening["low"]), ("short", "opening_range_high", opening["high"])]
        return [("long", "opening_range_high", opening["high"]), ("short", "opening_range_low", opening["low"])]

    def _overnight_aoi_candidates(self, bar: pd.Series, reaction: str) -> list[tuple[str, str, str, float, dict]]:
        if reaction == "trap":
            raw = [
                ("long", "overnight_low", _finite_float(bar.get("overnight_low"))),
                ("short", "overnight_high", _finite_float(bar.get("overnight_high"))),
            ]
        else:
            raw = [
                ("long", "overnight_high", _finite_float(bar.get("overnight_high"))),
                ("short", "overnight_low", _finite_float(bar.get("overnight_low"))),
            ]
        return self._profile_context_candidates(raw, reaction, bar)

    def _value_area_candidates(self, reaction: str, bar: pd.Series) -> list[tuple[str, str, str, float, dict]]:
        prefix = self.cached_profile_prefix
        if reaction == "trap":
            raw = [
                ("long", "prior_value_area_low", _finite_float(bar.get(f"{prefix}_val"))),
                ("short", "prior_value_area_high", _finite_float(bar.get(f"{prefix}_vah"))),
            ]
        else:
            raw = [
                ("long", "prior_value_area_high", _finite_float(bar.get(f"{prefix}_vah"))),
                ("short", "prior_value_area_low", _finite_float(bar.get(f"{prefix}_val"))),
            ]
        out = []
        for direction, aoi_type, level in raw:
            if level is None:
                continue
            out.append((direction, reaction, aoi_type, level, self._direct_profile_match(aoi_type, level, bar)))
        return out

    def _profile_context_candidates(
        self,
        raw: list[tuple[str, str, float | None]],
        reaction: str,
        bar: pd.Series,
    ) -> list[tuple[str, str, str, float, dict]]:
        out = []
        for direction, aoi_type, level in raw:
            if level is None:
                continue
            match = self._profile_context(direction, level, bar)
            if match is not None:
                out.append((direction, reaction, aoi_type, level, match))
        return out

    def _opening_range(self) -> dict | None:
        if len(self.current_session_bars) < self.opening_range_minutes:
            return None
        first = self.current_session_bars[0]
        session_start = pd.Timestamp(first["timestamp"])
        opening_end = session_start + pd.Timedelta(minutes=self.opening_range_minutes)
        bars = [bar for bar in self.current_session_bars if pd.Timestamp(bar["timestamp"]) < opening_end]
        if len(bars) < self.opening_range_minutes:
            return None
        return {"high": max(float(bar["high"]) for bar in bars), "low": min(float(bar["low"]) for bar in bars)}

    def _profile_context(self, direction: str, level: float, bar: pd.Series) -> dict | None:
        prefix = self.cached_profile_prefix
        poc = _finite_float(bar.get(f"{prefix}_poc"))
        vah = _finite_float(bar.get(f"{prefix}_vah"))
        val = _finite_float(bar.get(f"{prefix}_val"))
        if poc is None or vah is None or val is None:
            return None
        if direction == "long":
            if self.profile_context_mode == "beyond_poc" and level > poc:
                return None
            ref = val
        else:
            if self.profile_context_mode == "beyond_poc" and level < poc:
                return None
            ref = vah
        return {
            "profile_level_type": self.profile_context_mode,
            "profile_level_price": ref,
            "profile_distance_ticks": abs(level - ref) / self.tick_size,
            "prior_profile_session": _finite_float(bar.get(f"{prefix}_session_yyyymmdd")),
            "prior_profile_total_volume": _finite_float(bar.get(f"{prefix}_total_volume")),
            "prior_profile_bars": _finite_float(bar.get(f"{prefix}_price_levels")),
        }

    def _direct_profile_match(self, aoi_type: str, level: float, bar: pd.Series) -> dict:
        prefix = self.cached_profile_prefix
        return {
            "profile_level_type": "val" if "low" in aoi_type else "vah",
            "profile_level_price": float(level),
            "profile_distance_ticks": 0.0,
            "prior_profile_session": _finite_float(bar.get(f"{prefix}_session_yyyymmdd")),
            "prior_profile_total_volume": _finite_float(bar.get(f"{prefix}_total_volume")),
            "prior_profile_bars": _finite_float(bar.get(f"{prefix}_price_levels")),
        }

    def _large_record_state(self, bar: pd.Series) -> dict | None:
        max_volume = _finite_float(bar.get("large200_record_max_volume"))
        total_volume = _finite_float(bar.get("large200_record_volume"))
        signed_volume = _finite_float(bar.get("large200_record_signed_volume"))
        count = _finite_float(bar.get("large200_record_count")) or 0.0
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
            "record_count": count,
            "dominant_side": "buy" if signed_volume > 0 else "sell",
        }

    def _trap_event_confirms(self, direction: str, large_record: dict, level: float, high: float, low: float) -> bool:
        probe = self.min_probe_ticks * self.tick_size
        if direction == "long":
            return large_record["signed_volume"] < 0 and low <= level - probe
        return large_record["signed_volume"] > 0 and high >= level + probe

    def _continuation_event_confirms(self, direction: str, large_record: dict, level: float, high: float, low: float) -> bool:
        probe = self.min_probe_ticks * self.tick_size
        if direction == "long":
            return large_record["signed_volume"] > 0 and high >= level + probe
        return large_record["signed_volume"] < 0 and low <= level - probe

    def _trap_confirmation(self, direction: str, bar: pd.Series, level: float, open_price: float, close: float) -> bool:
        confirm = self.confirmation_ticks * self.tick_size
        if not self._confirm_delta(bar, direction):
            return False
        if direction == "long":
            return close >= level + confirm and close > open_price
        return close <= level - confirm and close < open_price

    def _continuation_confirmation(self, direction: str, bar: pd.Series, level: float, open_price: float, close: float) -> bool:
        confirm = max(self.confirmation_ticks * self.tick_size, self.min_probe_ticks * self.tick_size)
        if not self._confirm_delta(bar, direction):
            return False
        if direction == "long":
            return close >= level + confirm and close > open_price
        return close <= level - confirm and close < open_price

    def _confirm_delta(self, bar: pd.Series, direction: str) -> bool:
        if self.min_confirm_delta_imbalance <= 0:
            return True
        signed = _finite_float(bar.get("signed_volume"))
        volume = _finite_float(bar.get("volume"))
        if signed is None or volume is None or volume <= 0:
            return False
        imbalance = signed / volume
        if direction == "long":
            return imbalance >= self.min_confirm_delta_imbalance
        return imbalance <= -self.min_confirm_delta_imbalance

    def _signal(self, event: dict, bar: pd.Series, signal_timestamp: pd.Timestamp) -> Signal:
        signed = _finite_float(bar.get("signed_volume")) or 0.0
        volume = _finite_float(bar.get("volume")) or 0.0
        delta_imbalance = signed / volume if volume > 0 else 0.0
        fields = {
            "setup_mode": self.setup_mode,
            "reaction_model": event["reaction"],
            "aoi_type": event["aoi_type"],
            "aoi_level": event["level"],
            **event["profile_match"],
            "min_probe_ticks": self.min_probe_ticks,
            "confirmation_ticks": self.confirmation_ticks,
            "min_large200_record_volume": self.min_large200_record_volume,
            "large200_record_max_volume": event["large_record"]["max_volume"],
            "large200_record_volume": event["large_record"]["total_volume"],
            "large200_record_signed_volume": event["large_record"]["signed_volume"],
            "large200_record_count": event["large_record"]["record_count"],
            "confirm_signed_volume": signed,
            "confirm_delta_imbalance": delta_imbalance,
            "min_confirm_delta_imbalance": self.min_confirm_delta_imbalance,
            "event_timestamp": event["event_timestamp"],
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "source_quality_label": "Sierra SCID large-record proxy; not vendor-equivalent print data",
        }
        return Signal(
            direction=event["direction"],
            level_type=f"{event['aoi_type']}_{event['profile_match']['profile_level_type']}_{event['reaction']}_delayed_large200_record",
            swept_level=event["level"],
            sweep_timestamp=event["event_timestamp"],
            sweep_high=event["event_high"],
            sweep_low=event["event_low"],
            reclaim_timestamp=signal_timestamp,
            breakout_level=event["level"],
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _validate(self) -> None:
        if self.setup_mode not in self._MODES:
            raise ValueError(f"entry.params.setup_mode must be one of {sorted(self._MODES)}.")
        if self.profile_context_mode not in {"beyond_poc"}:
            raise ValueError("entry.params.profile_context_mode must be beyond_poc.")
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0 or self.tick_size <= 0:
            raise ValueError("entry.params bar_interval_minutes and tick_size must be positive.")
        if self.opening_range_minutes < 1:
            raise ValueError("entry.params.opening_range_minutes must be positive.")
        if self.min_probe_ticks < 0 or self.confirmation_ticks < 0:
            raise ValueError("entry.params probe and confirmation ticks must be non-negative.")
        if self.min_large200_record_volume < 200:
            raise ValueError("entry.params.min_large200_record_volume must be at least 200.")
        if self.min_confirm_delta_imbalance < 0:
            raise ValueError("entry.params.min_confirm_delta_imbalance must be non-negative.")
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
