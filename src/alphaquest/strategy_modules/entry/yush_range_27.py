from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.yush_range_1 import (
    YushRange1Entry,
    _bucket_start,
    _finite_float,
)
from alphaquest.utils.time import parse_time


class YushRange27Entry(YushRange1Entry):
    name = "yush_range_27"

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
        self.max_aoi_width_points = float(params.get("max_aoi_width_points", 3.0))
        self.entry_offset_ticks = int(params.get("entry_offset_ticks", 2))
        self.max_stop_points = float(params.get("max_stop_points", 5.0))
        self.bubble_delta_threshold = float(params.get("bubble_delta_threshold", 300.0))
        self.big_trade_threshold = float(params.get("big_trade_threshold", 200.0))
        self.big_trade_agg_ms = float(params.get("big_trade_agg_ms", 100.0))
        self.breakeven_offset_points = float(params.get("breakeven_offset_points", 1.25))
        self.breakout_lookback_bars = int(params.get("breakout_lookback_bars", 20))
        self.min_failed_breakouts = int(params.get("min_failed_breakouts", 1))
        self.reversal_lookback_bars = int(params.get("reversal_lookback_bars", 20))
        self.min_reversal_touches = int(params.get("min_reversal_touches", 2))
        self.range_edge_tolerance_ticks = int(params.get("range_edge_tolerance_ticks", 8))
        self._opening_range_high: float | None = None
        self._opening_range_low: float | None = None
        self._traded_aoi_keys: set[tuple] = set()
        self._pending_aoi: dict[tuple, dict] = {}
        self._big_trade_anchor: dict | None = None
        self._big_trade_snapshots: list[dict] = []
        self._delta_qualified_at: dict[float, pd.Timestamp] = {}
        self._delta_bar_timestamp: pd.Timestamp | None = None
        self._validate_range27_params()

    def _roll_session(self, bar: pd.Series) -> None:
        previous = self.session_key
        super()._roll_session(bar)
        if self.session_key != previous:
            self._opening_range_high = None
            self._opening_range_low = None
            self._traded_aoi_keys = set()
            self._pending_aoi = {}
            self._big_trade_anchor = None
            self._big_trade_snapshots = []
            self._delta_qualified_at = {}
            self._delta_bar_timestamp = None

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
        if bar_timestamp.time() >= self.end_time:
            return None
        self._update_opening_range(detail_rows)

        previous_bar = self.current_session_bars[-1] if self.current_session_bars else None
        session_key = self.session_key
        can_emit = (
            bool(bar.get("is_rth", False))
            and trades_today < self.max_trades_per_day
            and self.signals_by_session.get(session_key, 0) < self.max_trades_per_day
        )

        profile_cache = None
        profile_cache_timestamp = None
        candidates_cache = None
        candidates_cache_timestamp = None
        range_cache = None
        range_cache_timestamp = None
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
            if tick_state is None:
                continue
            self._update_event_triggers(tick_state, bar_timestamp)
            if not can_emit:
                continue
            timestamp = tick_state["timestamp"]
            tick_time = timestamp.time()
            if tick_time < self.start_time or tick_time > self.end_time:
                continue
            if (
                profile_cache is None
                or profile_cache_timestamp is None
                or (timestamp - profile_cache_timestamp).total_seconds() >= self.profile_recheck_seconds
            ):
                profile_cache = self.state.profile(
                    value_area_fraction=self.value_area_fraction,
                    lvn_poc_fraction=self.lvn_poc_fraction,
                    bucket_points=self.profile_bucket_points,
                    min_profile_volume=self.min_profile_volume,
                    min_profile_buckets=self.min_profile_buckets,
                )
                profile_cache_timestamp = timestamp
            profile = profile_cache
            if profile is None:
                continue
            if candidates_cache is None or candidates_cache_timestamp != profile_cache_timestamp:
                levels = self._market_levels(bar)
                candidates_cache = self._aoi_candidates(profile, levels)
                candidates_cache_timestamp = profile_cache_timestamp
            candidates = candidates_cache or []
            current_candidate_keys = {candidate["aoi_key"] for candidate in candidates}
            for stale_key in set(self._pending_aoi) - current_candidate_keys:
                self._pending_aoi.pop(stale_key, None)
            for candidate in candidates:
                key = candidate["aoi_key"]
                if key in self._traded_aoi_keys:
                    continue
                direction = candidate["direction"]
                if direction == "long" and not self.allow_long:
                    continue
                if direction == "short" and not self.allow_short:
                    continue
                existing = self._pending_aoi.get(key)
                if not self._aoi_tapped_or_exceeded(direction, candidate, tick_state) and existing is None:
                    continue
                tap_timestamp = existing["tap_timestamp"] if existing is not None else timestamp
                tap_price = existing["tap_price"] if existing is not None else tick_state["price"]
                bubble = self._bubble_in_or_past_aoi(
                    direction,
                    candidate,
                    after_timestamp=tap_timestamp,
                )
                if bubble is None:
                    continue
                self._pending_aoi[key] = {
                    **candidate,
                    "bubble": bubble,
                    "tap_timestamp": tap_timestamp,
                    "tap_price": tap_price,
                }
            if (
                range_cache is None
                or range_cache_timestamp is None
                or (timestamp - range_cache_timestamp).total_seconds() >= self.range_recheck_seconds
            ):
                range_cache = self._range_conditions_pass(profile, timestamp)
                range_cache_timestamp = timestamp
            if not range_cache:
                continue
            if not candidates:
                continue
            for candidate in candidates:
                key = candidate["aoi_key"]
                if key in self._traded_aoi_keys:
                    continue
                direction = candidate["direction"]
                if direction == "long" and not self.allow_long:
                    continue
                if direction == "short" and not self.allow_short:
                    continue
                pending = self._pending_aoi.get(key)
                if pending is None:
                    continue
                if not self._entry_triggered(direction, pending, tick_state):
                    continue
                entry_bubble = self._entry_tick_bubble(direction, pending)
                if entry_bubble is None:
                    self._pending_aoi.pop(key, None)
                    continue
                pending = {**pending, "bubble": entry_bubble}
                signal = self._aoi_signal(direction, bar, tick_state, profile, pending, previous_bar)
                if signal is None:
                    continue
                self._traded_aoi_keys.add(key)
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

    def _range_conditions_pass(self, profile: dict, timestamp: pd.Timestamp) -> bool:
        return (
            self._range_is_stable(timestamp)
            and self._profile_is_balanced(profile)
            and self._breakouts_lack_followthrough(profile)
            and self._frequent_reversals(profile)
        )

    def _has_past_range_snapshot(self, timestamp: pd.Timestamp) -> bool:
        return self._range_reference(timestamp) is not None

    def _range_is_stable(self, timestamp: pd.Timestamp) -> bool:
        current_range = self.state.session_range
        reference = self._range_reference(timestamp)
        if current_range is None or reference is None or reference <= 0:
            self.state.latest_range_change_pct = None
            return False
        change = (current_range - reference) / reference
        self.state.latest_range_change_pct = change
        return change <= self.max_range_change_pct

    def _range_reference(self, timestamp: pd.Timestamp) -> float | None:
        open_timestamp = pd.Timestamp(timestamp).replace(
            hour=self.opening_range_start_time.hour,
            minute=self.opening_range_start_time.minute,
            second=self.opening_range_start_time.second,
            microsecond=0,
        )
        elapsed = pd.Timestamp(timestamp) - open_timestamp
        if elapsed < pd.Timedelta(0):
            return None
        comparison_timestamp = open_timestamp + elapsed * (2.0 / 3.0)
        return self.state.range_at(comparison_timestamp)

    def _profile_is_balanced(self, profile: dict) -> bool:
        session_low = self.state.session_low
        session_high = self.state.session_high
        if session_low is None or session_high is None or session_high <= session_low:
            return False
        width = session_high - session_low
        return session_low + width / 3.0 <= profile["poc"] <= session_low + 2.0 * width / 3.0

    def _breakouts_lack_followthrough(self, profile: dict) -> bool:
        if self.min_failed_breakouts <= 0:
            return True
        recent = self.current_session_bars[-self.breakout_lookback_bars :]
        if not recent:
            return False
        tolerance = self.range_edge_tolerance_ticks * self.tick_size
        failed = 0
        for bar in recent:
            high = _finite_float(bar.get("high"))
            low = _finite_float(bar.get("low"))
            close = _finite_float(bar.get("close"))
            if high is None or low is None or close is None:
                continue
            if high >= profile["vah"] + tolerance and close <= profile["vah"]:
                failed += 1
            if low <= profile["val"] - tolerance and close >= profile["val"]:
                failed += 1
        return failed >= self.min_failed_breakouts

    def _frequent_reversals(self, profile: dict) -> bool:
        if self.min_reversal_touches <= 0:
            return True
        recent = self.current_session_bars[-self.reversal_lookback_bars :]
        if not recent:
            return False
        tolerance = self.range_edge_tolerance_ticks * self.tick_size
        touches = 0
        for bar in recent:
            high = _finite_float(bar.get("high"))
            low = _finite_float(bar.get("low"))
            open_ = _finite_float(bar.get("open"))
            close = _finite_float(bar.get("close"))
            if high is None or low is None or open_ is None or close is None:
                continue
            if high >= profile["vah"] - tolerance and close < open_:
                touches += 1
            if low <= profile["val"] + tolerance and close > open_:
                touches += 1
        return touches >= self.min_reversal_touches

    def _aoi_candidates(self, profile: dict, market_levels: list[dict]) -> list[dict]:
        profile_levels = self._profile_levels(profile)
        out = []
        for market in market_levels:
            market_price = float(market["price"])
            for profile_level in profile_levels:
                profile_price = float(profile_level["price"])
                low = min(market_price, profile_price)
                high = max(market_price, profile_price)
                width = high - low
                if width > self.max_aoi_width_points:
                    continue
                direction = self._aoi_direction(profile, profile_level)
                out.append(
                    {
                        "direction": direction,
                        "box_low": low,
                        "box_high": high,
                        "box_width": width,
                        "market_level_type": market["type"],
                        "market_level_price": market_price,
                        "profile_level_type": profile_level["type"],
                        "profile_level_price": profile_price,
                        "aoi_key": (
                            direction,
                            market["type"],
                            round(market_price / self.tick_size),
                            profile_level["type"],
                            round(profile_price / self.tick_size),
                        ),
                    }
                )
        return sorted(out, key=lambda item: (item["box_width"], item["market_level_type"], item["profile_level_type"]))

    def _profile_levels(self, profile: dict) -> list[dict]:
        return [
            {"type": "VAL", "price": float(profile["val"])},
            {"type": "VAH", "price": float(profile["vah"])},
        ]

    def _aoi_direction(self, profile: dict, profile_level: dict) -> str:
        if profile_level["type"] == "VAL":
            return "long"
        if profile_level["type"] == "VAH":
            return "short"
        return "long" if float(profile_level["price"]) < float(profile["poc"]) else "short"

    def _aoi_tapped_or_exceeded(self, direction: str, candidate: dict, tick_state: dict) -> bool:
        if direction == "long":
            return float(tick_state["price"]) <= candidate["box_high"]
        return float(tick_state["price"]) >= candidate["box_low"]

    def _entry_triggered(self, direction: str, candidate: dict, tick_state: dict) -> bool:
        trigger = self._entry_trigger_price(direction, candidate)
        price = float(tick_state["price"])
        return price >= trigger if direction == "long" else price <= trigger

    def _entry_trigger_price(self, direction: str, candidate: dict) -> float:
        offset = self.entry_offset_ticks * self.tick_size
        return candidate["box_high"] + offset if direction == "long" else candidate["box_low"] - offset

    def _stop_price(self, direction: str, candidate: dict) -> float:
        offset = self.stop_offset_ticks * self.tick_size
        return candidate["box_low"] - offset if direction == "long" else candidate["box_high"] + offset

    def _bubble_in_or_past_aoi(
        self,
        direction: str,
        candidate: dict,
        *,
        after_timestamp: pd.Timestamp,
    ) -> dict | None:
        delta = self._delta_bubble_in_or_past_aoi(direction, candidate, after_timestamp)
        big_trade = self._big_trade_bubble_in_or_past_aoi(direction, candidate, after_timestamp)
        if delta is not None:
            return delta
        return big_trade

    def _delta_bubble_in_or_past_aoi(
        self,
        direction: str,
        candidate: dict,
        after_timestamp: pd.Timestamp,
    ) -> dict | None:
        for bucket, delta in self.state.delta_by_bucket.items():
            if abs(delta) <= self.bubble_delta_threshold:
                continue
            qualified_at = self._delta_qualified_at.get(float(bucket))
            if qualified_at is None or qualified_at < after_timestamp:
                continue
            if not self._bucket_in_or_past_aoi(direction, float(bucket), candidate):
                continue
            return {
                "bubble_type": "delta_profile",
                "bubble_bucket": float(bucket),
                "bubble_delta": float(delta),
                "bubble_bucket_points": self.delta_bucket_points,
                "bubble_qualified_at": qualified_at,
            }
        return None

    def _big_trade_bubble_in_or_past_aoi(
        self,
        direction: str,
        candidate: dict,
        after_timestamp: pd.Timestamp,
    ) -> dict | None:
        for record in reversed(self._big_trade_snapshots):
            if record["qualified_at"] < after_timestamp:
                continue
            if not self._price_in_or_past_aoi(direction, record["price"], candidate):
                continue
            return {
                "bubble_type": "big_trade_100ms",
                "bubble_volume": record["volume"],
                "bubble_signed_volume": record["signed_volume"],
                "bubble_price": record["price"],
                "bubble_side": record["side"],
                "bubble_agg_ms": self.big_trade_agg_ms,
                "bubble_qualified_at": record["qualified_at"],
                "bubble_persistence": "session_snapshot",
            }
        return None

    def _entry_tick_bubble(self, direction: str, candidate: dict) -> dict | None:
        bubble = candidate.get("bubble") or {}
        if bubble.get("bubble_type") == "big_trade_100ms":
            return {**bubble, "bubble_timing": "qualified_after_aoi_tap"}
        bucket = _finite_float(bubble.get("bubble_bucket"))
        if bucket is None:
            return None
        delta = self.state.delta_by_bucket.get(float(bucket))
        if delta is None or abs(delta) <= self.bubble_delta_threshold:
            return None
        if not self._bucket_in_or_past_aoi(direction, float(bucket), candidate):
            return None
        return {
            "bubble_type": "delta_profile",
            "bubble_bucket": float(bucket),
            "bubble_delta": float(delta),
            "bubble_bucket_points": self.delta_bucket_points,
            "bubble_delta_timing": "entry_tick",
        }

    def _bucket_in_or_past_aoi(self, direction: str, bucket: float, candidate: dict) -> bool:
        bucket_top = bucket + self.delta_bucket_points
        return (
            bucket <= candidate["box_high"]
            if direction == "long"
            else bucket_top >= candidate["box_low"]
        )

    def _price_in_or_past_aoi(self, direction: str, price: float, candidate: dict) -> bool:
        return price <= candidate["box_high"] if direction == "long" else price >= candidate["box_low"]

    def _update_event_triggers(self, tick_state: dict, bar_timestamp: pd.Timestamp) -> None:
        timestamp = pd.Timestamp(tick_state["timestamp"])
        price = float(tick_state["price"])
        volume = float(tick_state["volume"])
        signed_volume = float(tick_state["signed_volume"])
        side = "B" if signed_volume > 0 else "A" if signed_volume < 0 else "N"
        anchor = self._big_trade_anchor
        matches = bool(
            anchor is not None
            and timestamp - anchor["timestamp"] <= pd.Timedelta(milliseconds=self.big_trade_agg_ms)
            and price == anchor["price"]
            and side == anchor["side"]
        )
        if not matches:
            anchor = {
                "timestamp": timestamp,
                "price": price,
                "side": side,
                "volume": volume,
                "signed_volume": signed_volume,
                "qualified": False,
            }
            self._big_trade_anchor = anchor
        else:
            anchor["volume"] += volume
            anchor["signed_volume"] += signed_volume
        if side != "N" and not anchor["qualified"] and anchor["volume"] > self.big_trade_threshold:
            anchor["qualified"] = True
            self._big_trade_snapshots.append(
                {
                    **anchor,
                    "qualified_at": timestamp,
                }
            )

        if self._delta_bar_timestamp != bar_timestamp:
            self._delta_bar_timestamp = bar_timestamp
            self._delta_qualified_at = {}
        for bucket, delta in self.state.delta_by_bucket.items():
            if abs(delta) > self.bubble_delta_threshold and float(bucket) not in self._delta_qualified_at:
                self._delta_qualified_at[float(bucket)] = timestamp

    def _entry_tick_delta_bubble(self, direction: str, candidate: dict) -> dict | None:
        """Backward-compatible test helper; production uses the OR-trigger method."""
        return self._entry_tick_bubble(direction, candidate)

    def _aoi_signal(
        self,
        direction: str,
        bar: pd.Series,
        tick_state: dict,
        profile: dict,
        candidate: dict,
        previous_bar: pd.Series | None,
    ) -> Signal | None:
        reference_price = self._entry_trigger_price(direction, candidate)
        stop = self._stop_price(direction, candidate)
        risk = abs(reference_price - stop)
        if risk <= 0 or risk > self.max_stop_points:
            return None
        target = float(profile["vah"] if direction == "long" else profile["val"])
        if direction == "long" and target <= reference_price:
            return None
        if direction == "short" and target >= reference_price:
            return None
        value_mid = (float(profile["vah"]) + float(profile["val"])) / 2.0
        dynamic_stop = (
            reference_price + self.breakeven_offset_points
            if direction == "long"
            else reference_price - self.breakeven_offset_points
        )
        fields = {
            "setup_mode": self.name,
            "entry_mode": "intrabar",
            "entry_reference_price": float(reference_price),
            "intrabar_entry_price": float(reference_price),
            "signal_stop_price": float(stop),
            "signal_target_price": float(target),
            "signal_timestamp": tick_state["timestamp"],
            "intended_entry_timestamp": tick_state["timestamp"],
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "aoi_box_low": candidate["box_low"],
            "aoi_box_high": candidate["box_high"],
            "aoi_box_width": candidate["box_width"],
            "aoi_entry_offset_ticks": self.entry_offset_ticks,
            "aoi_stop_offset_ticks": self.stop_offset_ticks,
            "aoi_market_level_type": candidate["market_level_type"],
            "aoi_market_level_price": candidate["market_level_price"],
            "aoi_profile_level_type": candidate["profile_level_type"],
            "aoi_profile_level_price": candidate["profile_level_price"],
            "aoi_confluence_count": 2,
            "aoi_confluence_criteria": "market_level,volume_profile",
            "range_condition_stable_area": True,
            "range_condition_middle_volume": True,
            "range_condition_breakouts_lack_followthrough": True,
            "range_condition_reversals_similar_levels": True,
            "profile_poc": profile["poc"],
            "profile_vah": profile["vah"],
            "profile_val": profile["val"],
            "profile_mid": value_mid,
            "profile_bucket_points": self.profile_bucket_points,
            "profile_value_area_fraction": self.value_area_fraction,
            "profile_total_volume": profile["total_volume"],
            "lvn_between_value_area_count": profile["lvn_between_value_area_count"],
            "session_range": self.state.session_range,
            "range_change_pct": self.state.latest_range_change_pct,
            "dynamic_stop_trigger_price": value_mid,
            "dynamic_stop_price": dynamic_stop,
            "dynamic_stop_policy": "move_to_entry_plus_offset_after_mid_value_area",
            "breakeven_offset_points": self.breakeven_offset_points,
            "target_reference": "opposite_value_area_edge",
            "post_trade_aoi_lockout": True,
            "max_trades_per_day": self.max_trades_per_day,
            "opening_range_seconds": self.opening_range_seconds,
            "opening_range_high": self._opening_range_high,
            "opening_range_low": self._opening_range_low,
            "previous_bar_timestamp": previous_bar.get("timestamp") if previous_bar is not None else None,
            "intrabar_source": "sierra_scid_record_replay",
        }
        fields.update(candidate["bubble"])
        return Signal(
            direction=direction,
            level_type=f"{self.name}_{direction}_{candidate['market_level_type']}_{candidate['profile_level_type']}",
            swept_level=float(candidate["profile_level_price"]),
            sweep_timestamp=tick_state["timestamp"],
            sweep_high=float(self.state.current_bar_high or tick_state["price"]),
            sweep_low=float(self.state.current_bar_low or tick_state["price"]),
            reclaim_timestamp=tick_state["timestamp"],
            breakout_level=float(reference_price),
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _validate_range27_params(self) -> None:
        if self.opening_range_seconds <= 0:
            raise ValueError("entry.params.opening_range_seconds must be greater than 0.")
        if self.max_aoi_width_points <= 0:
            raise ValueError("entry.params.max_aoi_width_points must be greater than 0.")
        if self.max_stop_points <= 0:
            raise ValueError("entry.params.max_stop_points must be greater than 0.")
        if self.entry_offset_ticks < 0 or self.stop_offset_ticks < 0:
            raise ValueError("entry/stop offset ticks must be non-negative.")
        if self.bubble_delta_threshold <= 0 or self.big_trade_threshold <= 0 or self.big_trade_agg_ms <= 0:
            raise ValueError("bubble thresholds must be positive.")
        if self.breakeven_offset_points < 0:
            raise ValueError("entry.params.breakeven_offset_points must be non-negative.")


def _raw_level_list(value) -> list[str]:
    raw_values = [value] if isinstance(value, str) else list(value)
    return [str(item).strip().upper() for item in raw_values if str(item).strip()]


def _level_type_filter_with_opening_range(value) -> set[str] | None:
    if value is None or value == "":
        return None
    allowed = {"PDH", "PDL", "PDC", "ONH", "ONL", "ORH", "ORL"}
    out = set(_raw_level_list(value))
    unknown = sorted(out - allowed)
    if unknown:
        raise ValueError(f"Unsupported entry.params.allowed_market_level_types: {', '.join(unknown)}")
    return out or None
