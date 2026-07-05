from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class YushRange1Entry:
    name = "yush_range_1"

    def __init__(self, params: dict):
        self.params = params
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.bar_interval_minutes = int(params.get("bar_interval_minutes", 3))
        self.profile_bucket_points = float(params.get("profile_bucket_points", 1.0))
        self.delta_bucket_points = float(params.get("delta_bucket_points", 1.0))
        self.value_area_fraction = float(params.get("value_area_fraction", 0.70))
        self.lvn_poc_fraction = float(params.get("lvn_poc_fraction", 0.20))
        self.max_lvn_between_value_area = int(params.get("max_lvn_between_value_area", 1))
        self.range_snapshot_minutes = float(params.get("range_snapshot_minutes", 30.0))
        self.max_range_change_pct = float(params.get("max_range_change_pct", 0.20))
        self.atr_period = int(params.get("atr_period", 14))
        self.atr_multiple = float(params.get("atr_multiple", 2.0))
        self.absorption_delta_threshold = float(params.get("absorption_delta_threshold", 300.0))
        self.absorption_hold_seconds = float(params.get("absorption_hold_seconds", 3.0))
        self.stop_offset_ticks = int(params.get("stop_offset_ticks", 2))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.min_profile_volume = float(params.get("min_profile_volume", 1.0))
        self.min_profile_buckets = int(params.get("min_profile_buckets", 3))
        self.profile_recheck_seconds = float(params.get("profile_recheck_seconds", 1.0))
        self.range_recheck_seconds = float(params.get("range_recheck_seconds", 1.0))
        self.signals_by_session: dict[object, int] = {}
        self.current_session_bars: list[pd.Series] = []
        self.completed_bars: list[pd.Series] = []
        self.session_key = None
        self.state = _SessionTickState()
        self._validate_params()

    def on_bar_intrabar(
        self,
        bar: pd.Series,
        detail_rows: pd.DataFrame,
        trades_today: int = 0,
    ) -> Signal | None:
        self._roll_session(bar)
        if detail_rows is None or detail_rows.empty:
            return None

        levels = self._market_levels(bar)
        previous_bar = self.current_session_bars[-1] if self.current_session_bars else None
        atr = self._atr()
        session_key = self.session_key
        can_emit = (
            bool(bar.get("is_rth", False))
            and trades_today < self.max_trades_per_day
            and self.signals_by_session.get(session_key, 0) < self.max_trades_per_day
            and atr is not None
            and levels
        )
        if (
            not can_emit
            or not self._detail_window_can_sweep(levels, previous_bar, detail_rows)
            or not self._detail_window_can_absorb(detail_rows)
        ):
            self.state.update_bar_aggregate(
                detail_rows,
                bar_timestamp=pd.Timestamp(bar["timestamp"]),
                profile_bucket_points=self.profile_bucket_points,
                range_snapshot_minutes=self.range_snapshot_minutes,
            )
            return None

        profile_cache = None
        profile_cache_timestamp = None
        range_cache = None
        range_cache_timestamp = None
        for tick in detail_rows.itertuples(index=False):
            tick_state = self.state.update_tick(
                tick,
                bar_timestamp=pd.Timestamp(bar["timestamp"]),
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
                sweep = self._market_sweep(direction, levels, previous_bar)
                if sweep is None:
                    continue
                absorption = self.state.confirmed_absorption(direction)
                if absorption is None:
                    continue
                if (
                    range_cache is None
                    or range_cache_timestamp is None
                    or (tick_state["timestamp"] - range_cache_timestamp).total_seconds()
                    >= self.range_recheck_seconds
                ):
                    range_cache = self._range_is_stable(tick_state["timestamp"])
                    range_cache_timestamp = tick_state["timestamp"]
                if not range_cache:
                    continue
                if (
                    profile_cache is None
                    or profile_cache_timestamp is None
                    or (tick_state["timestamp"] - profile_cache_timestamp).total_seconds()
                    >= self.profile_recheck_seconds
                ):
                    profile_cache = self.state.profile(
                        value_area_fraction=self.value_area_fraction,
                        lvn_poc_fraction=self.lvn_poc_fraction,
                        bucket_points=self.profile_bucket_points,
                        min_profile_volume=self.min_profile_volume,
                        min_profile_buckets=self.min_profile_buckets,
                    )
                    profile_cache_timestamp = tick_state["timestamp"]
                profile = profile_cache
                if profile is None or not self._profile_is_balanced(profile):
                    continue
                if not self._within_atr_of_value_edge(direction, tick_state["price"], profile, atr):
                    continue
                signal = self._signal(direction, bar, tick_state, profile, sweep, absorption, atr)
                self.signals_by_session[session_key] = self.signals_by_session.get(session_key, 0) + 1
                return signal
        return None

    def _detail_window_can_sweep(
        self,
        levels: list[dict],
        previous_bar: pd.Series | None,
        detail_rows: pd.DataFrame,
    ) -> bool:
        if detail_rows is None or detail_rows.empty:
            return previous_bar is not None and bool(levels)
        high = _finite_float(detail_rows["high"].max()) if "high" in detail_rows else None
        low = _finite_float(detail_rows["low"].min()) if "low" in detail_rows else None
        previous_high = _finite_float(previous_bar.get("high")) if previous_bar is not None else None
        previous_low = _finite_float(previous_bar.get("low")) if previous_bar is not None else None
        for level in levels:
            price = level["price"]
            crossed_now = high is not None and low is not None and high >= price and low < price
            crossed_previous = (
                previous_high is not None and previous_low is not None and previous_high >= price and previous_low < price
            )
            if crossed_now or crossed_previous:
                return True
        return False

    def _detail_window_can_absorb(self, detail_rows: pd.DataFrame) -> bool:
        if detail_rows is None or detail_rows.empty or "close" not in detail_rows:
            return False
        close = pd.to_numeric(detail_rows["close"], errors="coerce")
        if "buy_volume" in detail_rows:
            buy_source = detail_rows["buy_volume"]
        elif "ask_volume" in detail_rows:
            buy_source = detail_rows["ask_volume"]
        else:
            buy_source = pd.Series(0.0, index=detail_rows.index)
        if "sell_volume" in detail_rows:
            sell_source = detail_rows["sell_volume"]
        elif "bid_volume" in detail_rows:
            sell_source = detail_rows["bid_volume"]
        else:
            sell_source = pd.Series(0.0, index=detail_rows.index)
        buy = pd.to_numeric(buy_source, errors="coerce").fillna(0.0)
        sell = pd.to_numeric(sell_source, errors="coerce").fillna(0.0)
        valid = close.notna() & (close > 0)
        if not bool(valid.any()):
            return False
        buckets = close.loc[valid].map(lambda price: _bucket_start(float(price), self.delta_bucket_points))
        signed = (buy.loc[valid] - sell.loc[valid]).astype(float)
        cumulative = signed.groupby(buckets, sort=False).cumsum()
        return bool(
            (cumulative <= -self.absorption_delta_threshold).any()
            or (cumulative >= self.absorption_delta_threshold).any()
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        timestamp = pd.Timestamp(bar["timestamp"])
        if not self.current_session_bars or pd.Timestamp(self.current_session_bars[-1]["timestamp"]) != timestamp:
            self.current_session_bars.append(bar.copy())
        if not self.completed_bars or pd.Timestamp(self.completed_bars[-1]["timestamp"]) != timestamp:
            self.completed_bars.append(bar.copy())
            max_bars = max(self.atr_period + 10, 100)
            if len(self.completed_bars) > max_bars:
                self.completed_bars = self.completed_bars[-max_bars:]
        return None

    def _roll_session(self, bar: pd.Series) -> None:
        session_key = bar.get("session_date")
        if pd.isna(session_key):
            session_key = pd.Timestamp(bar["timestamp"]).date()
        if session_key == self.session_key:
            return
        self.session_key = session_key
        self.current_session_bars = []
        self.state = _SessionTickState()

    def _market_levels(self, bar: pd.Series) -> list[dict]:
        candidates = [
            ("PDH", "prev_rth_high"),
            ("PDL", "prev_rth_low"),
            ("PDC", "prev_rth_close"),
            ("ONH", "overnight_high"),
            ("ONL", "overnight_low"),
        ]
        levels = []
        for label, column in candidates:
            value = _finite_float(bar.get(column))
            if value is not None:
                levels.append({"type": label, "price": value})
        return levels

    def _market_sweep(self, direction: str, levels: list[dict], previous_bar: pd.Series | None) -> dict | None:
        current_high = self.state.current_bar_high
        current_low = self.state.current_bar_low
        for level in levels:
            price = level["price"]
            previous_swept = False
            if previous_bar is not None:
                previous_high = _finite_float(previous_bar.get("high"))
                previous_low = _finite_float(previous_bar.get("low"))
                previous_swept = (
                    previous_high is not None and previous_low is not None and previous_high >= price and previous_low < price
                    if direction == "long"
                    else previous_high is not None and previous_low is not None and previous_low <= price and previous_high > price
                )
            current_swept = (
                current_high is not None and current_low is not None and current_high >= price and current_low < price
                if direction == "long"
                else current_high is not None and current_low is not None and current_low <= price and current_high > price
            )
            if previous_swept or current_swept:
                return {
                    "market_level_type": level["type"],
                    "market_level_price": price,
                    "market_sweep_window": "previous_or_current_3m",
                    "market_sweep_source": "previous_3m_bar" if previous_swept else "current_developing_3m_bar",
                }
        return None

    def _range_is_stable(self, timestamp: pd.Timestamp) -> bool:
        current_range = self.state.session_range
        past_range = self.state.range_at(timestamp - pd.Timedelta(minutes=self.range_snapshot_minutes))
        if current_range is None or past_range is None or past_range <= 0:
            self.state.latest_range_change_pct = None
            return False
        change = abs(current_range - past_range) / past_range
        self.state.latest_range_change_pct = change
        return change < self.max_range_change_pct

    def _profile_is_balanced(self, profile: dict) -> bool:
        if profile["lvn_between_value_area_count"] > self.max_lvn_between_value_area:
            return False
        val = profile["val"]
        vah = profile["vah"]
        poc = profile["poc"]
        width = vah - val
        if width <= 0:
            return False
        return val + width / 3.0 <= poc <= val + (2.0 * width / 3.0)

    def _within_atr_of_value_edge(self, direction: str, price: float, profile: dict, atr: float) -> bool:
        if atr <= 0:
            return False
        reference = profile["val"] if direction == "long" else profile["vah"]
        return abs(price - reference) <= self.atr_multiple * atr

    def _atr(self) -> float | None:
        if len(self.completed_bars) < self.atr_period + 1:
            return None
        bars = self.completed_bars[-(self.atr_period + 1) :]
        ranges = []
        for previous, current in zip(bars[:-1], bars[1:], strict=False):
            prev_close = _finite_float(previous.get("close"))
            high = _finite_float(current.get("high"))
            low = _finite_float(current.get("low"))
            if prev_close is None or high is None or low is None:
                return None
            ranges.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
        if len(ranges) != self.atr_period:
            return None
        return sum(ranges) / len(ranges)

    def _signal(
        self,
        direction: str,
        bar: pd.Series,
        tick_state: dict,
        profile: dict,
        sweep: dict,
        absorption: dict,
        atr: float,
    ) -> Signal:
        entry_price = float(tick_state["price"])
        if direction == "long":
            stop_price = absorption["bucket_bottom"] - self.stop_offset_ticks * self.tick_size
        else:
            stop_price = absorption["bucket_top"] + self.stop_offset_ticks * self.tick_size
        fields = {
            "setup_mode": self.name,
            "entry_mode": "intrabar",
            "entry_reference_price": entry_price,
            "intrabar_entry_price": entry_price,
            "signal_stop_price": float(stop_price),
            "signal_target_r_multiple": 2.0,
            "signal_timestamp": tick_state["timestamp"],
            "intended_entry_timestamp": tick_state["timestamp"],
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "market_level_type": sweep["market_level_type"],
            "market_level_price": sweep["market_level_price"],
            "market_sweep_window": sweep["market_sweep_window"],
            "market_sweep_source": sweep["market_sweep_source"],
            "developing_profile_source": "sierra_scid_record_replay",
            "profile_bucket_points": self.profile_bucket_points,
            "profile_value_area_fraction": self.value_area_fraction,
            "profile_poc": profile["poc"],
            "profile_poc_volume": profile["poc_volume"],
            "profile_vah": profile["vah"],
            "profile_val": profile["val"],
            "profile_total_volume": profile["total_volume"],
            "profile_bucket_count": profile["bucket_count"],
            "lvn_between_value_area_count": profile["lvn_between_value_area_count"],
            "lvn_poc_fraction": self.lvn_poc_fraction,
            "session_range": self.state.session_range,
            "range_snapshot_minutes": self.range_snapshot_minutes,
            "range_change_pct": self.state.latest_range_change_pct,
            "atr_period": self.atr_period,
            "atr": atr,
            "atr_multiple": self.atr_multiple,
            "delta_bucket_points": self.delta_bucket_points,
            "absorption_bucket_bottom": absorption["bucket_bottom"],
            "absorption_bucket_top": absorption["bucket_top"],
            "absorption_bucket_delta": absorption["delta"],
            "absorption_hold_start": absorption["hold_start"],
            "absorption_confirmed_at": absorption["confirmed_at"],
            "absorption_hold_seconds": self.absorption_hold_seconds,
            "absorption_delta_threshold": self.absorption_delta_threshold,
            "intrabar_source": "sierra_scid_record_replay",
            "intrabar_source_quality_label": "Sierra SCID records; not exchange MBO sequencing.",
            "confirmation_high": entry_price,
            "confirmation_low": entry_price,
        }
        return Signal(
            direction=direction,
            level_type=f"{self.name}_{direction}_{sweep['market_level_type']}",
            swept_level=float(sweep["market_level_price"]),
            sweep_timestamp=tick_state["timestamp"],
            sweep_high=float(self.state.current_bar_high or tick_state["price"]),
            sweep_low=float(self.state.current_bar_low or tick_state["price"]),
            reclaim_timestamp=tick_state["timestamp"],
            breakout_level=float(absorption["bucket_top"] if direction == "long" else absorption["bucket_bottom"]),
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _validate_params(self) -> None:
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be greater than 0.")
        if self.profile_bucket_points <= 0 or self.delta_bucket_points <= 0:
            raise ValueError("profile and delta bucket sizes must be greater than 0.")
        if not 0 < self.value_area_fraction <= 1:
            raise ValueError("entry.params.value_area_fraction must be in (0, 1].")
        if self.lvn_poc_fraction < 0:
            raise ValueError("entry.params.lvn_poc_fraction must be non-negative.")
        if self.range_snapshot_minutes <= 0 or self.max_range_change_pct < 0:
            raise ValueError("range snapshot settings must be positive.")
        if self.atr_period <= 0 or self.atr_multiple <= 0:
            raise ValueError("ATR settings must be positive.")
        if self.absorption_delta_threshold <= 0 or self.absorption_hold_seconds < 0:
            raise ValueError("absorption settings must be positive.")
        if self.profile_recheck_seconds < 0:
            raise ValueError("entry.params.profile_recheck_seconds must be non-negative.")
        if self.range_recheck_seconds < 0:
            raise ValueError("entry.params.range_recheck_seconds must be non-negative.")


@dataclass
class _AbsorptionCandidate:
    bucket_bottom: float
    bucket_top: float
    delta: float
    hold_start: pd.Timestamp | None = None
    confirmed_at: pd.Timestamp | None = None
    confirmed: bool = False


class _SessionTickState:
    def __init__(self) -> None:
        self.profile_volume: dict[float, float] = {}
        self.delta_by_bucket: dict[float, float] = {}
        self.active_long_candidate: _AbsorptionCandidate | None = None
        self.active_short_candidate: _AbsorptionCandidate | None = None
        self.session_high: float | None = None
        self.session_low: float | None = None
        self.current_bar_timestamp: pd.Timestamp | None = None
        self.current_bar_high: float | None = None
        self.current_bar_low: float | None = None
        self.current_price: float | None = None
        self.range_snapshots: deque[tuple[pd.Timestamp, float]] = deque()
        self.latest_range_change_pct: float | None = None

    @property
    def session_range(self) -> float | None:
        if self.session_high is None or self.session_low is None:
            return None
        return self.session_high - self.session_low

    def update_tick(
        self,
        tick,
        *,
        bar_timestamp: pd.Timestamp,
        profile_bucket_points: float,
        delta_bucket_points: float,
        absorption_delta_threshold: float,
        hold_seconds: float,
        range_snapshot_minutes: float,
    ) -> dict | None:
        timestamp = pd.Timestamp(_row_value(tick, "timestamp"))
        price = _finite_float(_row_value(tick, "close"))
        volume = _finite_float(_row_value(tick, "volume"))
        if price is None or volume is None or volume <= 0:
            return None
        high = _finite_float(_row_value(tick, "high")) or price
        low = _finite_float(_row_value(tick, "low")) or price
        buy = _finite_float(_row_value(tick, "buy_volume"))
        if buy is None:
            buy = _finite_float(_row_value(tick, "ask_volume")) or 0.0
        sell = _finite_float(_row_value(tick, "sell_volume"))
        if sell is None:
            sell = _finite_float(_row_value(tick, "bid_volume")) or 0.0
        signed = buy - sell

        if self.current_bar_timestamp != bar_timestamp:
            self.current_bar_timestamp = bar_timestamp
            self.current_bar_high = None
            self.current_bar_low = None
            self.delta_by_bucket = {}
            self.active_long_candidate = None
            self.active_short_candidate = None
        self.current_bar_high = high if self.current_bar_high is None else max(self.current_bar_high, high)
        self.current_bar_low = low if self.current_bar_low is None else min(self.current_bar_low, low)
        self.session_high = high if self.session_high is None else max(self.session_high, high)
        self.session_low = low if self.session_low is None else min(self.session_low, low)
        self.current_price = price

        profile_bucket = _bucket_start(price, profile_bucket_points)
        self.profile_volume[profile_bucket] = self.profile_volume.get(profile_bucket, 0.0) + volume
        delta_bucket = _bucket_start(price, delta_bucket_points)
        self.delta_by_bucket[delta_bucket] = self.delta_by_bucket.get(delta_bucket, 0.0) + signed
        self._update_absorption_candidates(
            timestamp,
            price,
            delta_bucket,
            delta_bucket_points,
            absorption_delta_threshold,
            hold_seconds,
        )
        self._record_range_snapshot(timestamp, range_snapshot_minutes)
        return {
            "timestamp": timestamp,
            "price": price,
            "high": high,
            "low": low,
            "signed_volume": signed,
            "volume": volume,
        }

    def update_bar_aggregate(
        self,
        detail_rows: pd.DataFrame,
        *,
        bar_timestamp: pd.Timestamp,
        profile_bucket_points: float,
        range_snapshot_minutes: float,
    ) -> None:
        if detail_rows is None or detail_rows.empty:
            return
        timestamps = pd.to_datetime(detail_rows["timestamp"])
        close = pd.to_numeric(detail_rows["close"], errors="coerce")
        volume = pd.to_numeric(detail_rows["volume"], errors="coerce")
        valid = close.notna() & volume.notna() & (close > 0) & (volume > 0)
        if not bool(valid.any()):
            return

        if self.current_bar_timestamp != bar_timestamp:
            self.current_bar_timestamp = bar_timestamp
            self.delta_by_bucket = {}
            self.active_long_candidate = None
            self.active_short_candidate = None
        high = pd.to_numeric(detail_rows.loc[valid, "high"], errors="coerce").max()
        low = pd.to_numeric(detail_rows.loc[valid, "low"], errors="coerce").min()
        last_price = float(close.loc[valid].iloc[-1])
        last_timestamp = pd.Timestamp(timestamps.loc[valid].iloc[-1])
        if pd.notna(high):
            high = float(high)
            self.current_bar_high = high
            self.session_high = high if self.session_high is None else max(self.session_high, high)
        if pd.notna(low):
            low = float(low)
            self.current_bar_low = low
            self.session_low = low if self.session_low is None else min(self.session_low, low)
        self.current_price = last_price

        buckets = (close.loc[valid].map(lambda price: _bucket_start(float(price), profile_bucket_points))).to_numpy()
        bucket_frame = pd.DataFrame({"bucket": buckets, "volume": volume.loc[valid].to_numpy(dtype=float)})
        grouped = bucket_frame.groupby("bucket", sort=False)["volume"].sum()
        for bucket, bucket_volume in grouped.items():
            self.profile_volume[float(bucket)] = self.profile_volume.get(float(bucket), 0.0) + float(bucket_volume)
        self._record_range_snapshot(last_timestamp, range_snapshot_minutes)

    def _update_absorption_candidates(
        self,
        timestamp: pd.Timestamp,
        price: float,
        bucket: float,
        bucket_points: float,
        threshold: float,
        hold_seconds: float,
    ) -> None:
        delta = self.delta_by_bucket[bucket]
        if delta <= -threshold:
            if self.active_long_candidate is None or self.active_long_candidate.bucket_bottom != bucket:
                self.active_long_candidate = _AbsorptionCandidate(bucket, bucket + bucket_points, delta)
            else:
                self.active_long_candidate.delta = delta
        if delta >= threshold:
            if self.active_short_candidate is None or self.active_short_candidate.bucket_bottom != bucket:
                self.active_short_candidate = _AbsorptionCandidate(bucket, bucket + bucket_points, delta)
            else:
                self.active_short_candidate.delta = delta
        self._advance_long_candidates(timestamp, price, threshold, hold_seconds)
        self._advance_short_candidates(timestamp, price, threshold, hold_seconds)

    def _advance_long_candidates(
        self,
        timestamp: pd.Timestamp,
        price: float,
        threshold: float,
        hold_seconds: float,
    ) -> None:
        candidate = self.active_long_candidate
        if candidate is None:
            return
        if candidate.delta > -threshold or price <= candidate.bucket_top:
            candidate.hold_start = None
            candidate.confirmed = False
            candidate.confirmed_at = None
            return
        if candidate.hold_start is None:
            candidate.hold_start = timestamp
        if (timestamp - candidate.hold_start).total_seconds() >= hold_seconds:
            candidate.confirmed = True
            candidate.confirmed_at = timestamp

    def _advance_short_candidates(
        self,
        timestamp: pd.Timestamp,
        price: float,
        threshold: float,
        hold_seconds: float,
    ) -> None:
        candidate = self.active_short_candidate
        if candidate is None:
            return
        if candidate.delta < threshold or price >= candidate.bucket_bottom:
            candidate.hold_start = None
            candidate.confirmed = False
            candidate.confirmed_at = None
            return
        if candidate.hold_start is None:
            candidate.hold_start = timestamp
        if (timestamp - candidate.hold_start).total_seconds() >= hold_seconds:
            candidate.confirmed = True
            candidate.confirmed_at = timestamp

    def _record_range_snapshot(self, timestamp: pd.Timestamp, range_snapshot_minutes: float) -> None:
        current_range = self.session_range
        if current_range is None:
            return
        self.range_snapshots.append((timestamp, current_range))
        cutoff = timestamp - pd.Timedelta(minutes=max(range_snapshot_minutes * 2.0, range_snapshot_minutes + 10.0))
        while self.range_snapshots and self.range_snapshots[0][0] < cutoff:
            self.range_snapshots.popleft()

    def range_at(self, target_timestamp: pd.Timestamp) -> float | None:
        for timestamp, value in reversed(self.range_snapshots):
            if timestamp <= target_timestamp:
                return value
        return None

    def confirmed_absorption(self, direction: str) -> dict | None:
        selected = self.active_long_candidate if direction == "long" else self.active_short_candidate
        if selected is None or not selected.confirmed:
            return None
        return {
            "bucket_bottom": selected.bucket_bottom,
            "bucket_top": selected.bucket_top,
            "delta": selected.delta,
            "hold_start": selected.hold_start,
            "confirmed_at": selected.confirmed_at,
        }

    def profile(
        self,
        *,
        value_area_fraction: float,
        lvn_poc_fraction: float,
        bucket_points: float,
        min_profile_volume: float,
        min_profile_buckets: int,
    ) -> dict | None:
        if len(self.profile_volume) < min_profile_buckets:
            return None
        total_volume = sum(self.profile_volume.values())
        if total_volume < min_profile_volume:
            return None
        buckets = sorted(self.profile_volume)
        poc_bucket = max(buckets, key=lambda bucket: (self.profile_volume[bucket], -abs(bucket)))
        poc_idx = buckets.index(poc_bucket)
        poc_volume = self.profile_volume[poc_bucket]
        if poc_volume <= 0:
            return None
        target_volume = total_volume * value_area_fraction
        low_idx = high_idx = poc_idx
        value_volume = poc_volume
        while value_volume < target_volume and (low_idx > 0 or high_idx < len(buckets) - 1):
            lower_volume = self.profile_volume[buckets[low_idx - 1]] if low_idx > 0 else -1.0
            upper_volume = self.profile_volume[buckets[high_idx + 1]] if high_idx < len(buckets) - 1 else -1.0
            if lower_volume > upper_volume:
                low_idx -= 1
                value_volume += lower_volume
            elif upper_volume > lower_volume:
                high_idx += 1
                value_volume += upper_volume
            else:
                if low_idx > 0:
                    low_idx -= 1
                    value_volume += lower_volume
                if value_volume >= target_volume:
                    break
                if high_idx < len(buckets) - 1:
                    high_idx += 1
                    value_volume += upper_volume
        val = buckets[low_idx]
        vah = buckets[high_idx] + bucket_points
        lvn_threshold = poc_volume * lvn_poc_fraction
        lvn_count = sum(
            1
            for bucket in buckets[low_idx : high_idx + 1]
            if self.profile_volume[bucket] < lvn_threshold
        )
        return {
            "poc": poc_bucket + bucket_points / 2.0,
            "poc_bucket": poc_bucket,
            "poc_volume": poc_volume,
            "vah": vah,
            "val": val,
            "total_volume": total_volume,
            "value_area_volume": value_volume,
            "bucket_count": len(buckets),
            "value_area_bucket_count": high_idx - low_idx + 1,
            "lvn_between_value_area_count": lvn_count,
        }


def _bucket_start(price: float, bucket_points: float) -> float:
    return math.floor(price / bucket_points) * bucket_points


def _row_value(row, key: str):
    if isinstance(row, pd.Series):
        return row.get(key)
    return getattr(row, key, None)


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
