from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class ProfileAoiFootprintTrapEntry:
    name = "profile_aoi_footprint_trap"

    _MODES = {
        "prior_low_profile_seller_trap_long",
        "prior_high_profile_buyer_trap_short",
        "prior_profile_two_sided_trap",
        "opening_low_profile_seller_trap_long",
        "opening_high_profile_buyer_trap_short",
        "opening_profile_two_sided_trap",
        "overnight_low_profile_seller_trap_long",
        "overnight_high_profile_buyer_trap_short",
        "overnight_profile_two_sided_trap",
        "market_profile_two_sided_trap",
    }

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "opening_profile_two_sided_trap")).lower()
        self.start_time = parse_time(params.get("start_time", "10:00:00"))
        self.end_time = parse_time(params.get("end_time", "15:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.opening_range_minutes = int(params.get("opening_range_minutes", 30))
        self.value_area_fraction = float(params.get("value_area_fraction", 0.70))
        self.lvn_quantile = float(params.get("lvn_quantile", 0.20))
        self.profile_source = str(params.get("profile_source", "computed_prior_ohlcv")).lower()
        self.cached_profile_prefix = str(params.get("cached_profile_prefix", "prior_vap"))
        self.min_prior_profile_bars = int(params.get("min_prior_profile_bars", 200))
        self.min_developing_profile_bars = int(
            params.get("min_developing_profile_bars", self.min_prior_profile_bars)
        )
        self.max_profile_distance_ticks = int(params.get("max_profile_distance_ticks", 12))
        self.min_probe_ticks = float(params.get("min_probe_ticks", 1))
        self.confirmation_ticks = float(params.get("confirmation_ticks", 0))
        self.min_absorption_volume = float(params.get("min_absorption_volume", 20))
        self.min_adverse_delta_imbalance = float(params.get("min_adverse_delta_imbalance", 0.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.max_signals_per_session = int(params.get("max_signals_per_session", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.current_session = None
        self.current_session_bars: list[pd.Series] = []
        self.current_session_volume_by_tick: dict[int, float] = {}
        self.current_session_profile_bar_count = 0
        self.current_session_profile_last_timestamp: pd.Timestamp | None = None
        self.prior_profile: dict | None = None
        self.signaled_sessions: set = set()
        self.signals_by_session: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        if not bool(bar.get("is_rth", False)):
            return None
        if self.profile_source == "developing_session_ohlcv":
            self._add_bar_to_developing_profile(bar)
        session_date = bar.get("session_date")
        signal = None
        if (
            self._profile_available(bar)
            and self.signals_by_session.get(session_date, 0) < self.max_signals_per_session
            and trades_today < self.max_trades_per_day
        ):
            signal = self._signal_from_completed_bar(bar)
            if signal is not None:
                self.signals_by_session[session_date] = self.signals_by_session.get(session_date, 0) + 1
                self.signaled_sessions.add(session_date)
        self.current_session_bars.append(bar.copy())
        return signal

    def _roll_session(self, bar: pd.Series) -> None:
        session_date = bar.get("session_date")
        if self.current_session is None:
            self.current_session = session_date
            return
        if session_date == self.current_session:
            return
        self.prior_profile = self._build_profile(self.current_session, self.current_session_bars)
        self.current_session = session_date
        self.current_session_bars = []
        self.current_session_volume_by_tick = {}
        self.current_session_profile_bar_count = 0
        self.current_session_profile_last_timestamp = None

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

        for direction, aoi_type, aoi_level in self._candidate_aois(bar):
            if direction == "long" and not self.allow_long:
                continue
            if direction == "short" and not self.allow_short:
                continue
            profile_match = self._nearest_profile_level(aoi_level, bar)
            if profile_match is None:
                continue
            if direction == "long":
                if self._long_trap_confirms(bar, aoi_level, open_price, low, close):
                    return self._signal(direction, aoi_type, aoi_level, profile_match, bar, signal_timestamp)
            else:
                if self._short_trap_confirms(bar, aoi_level, open_price, high, close):
                    return self._signal(direction, aoi_type, aoi_level, profile_match, bar, signal_timestamp)
        return None

    def _candidate_aois(self, bar: pd.Series) -> list[tuple[str, str, float]]:
        candidates: list[tuple[str, str, float]] = []
        if self.setup_mode == "prior_low_profile_seller_trap_long":
            level = _finite_float(bar.get("prev_rth_low"))
            if level is not None:
                candidates.append(("long", "prior_rth_low", level))
        elif self.setup_mode == "prior_high_profile_buyer_trap_short":
            level = _finite_float(bar.get("prev_rth_high"))
            if level is not None:
                candidates.append(("short", "prior_rth_high", level))
        elif self.setup_mode == "prior_profile_two_sided_trap":
            low = _finite_float(bar.get("prev_rth_low"))
            high = _finite_float(bar.get("prev_rth_high"))
            if low is not None:
                candidates.append(("long", "prior_rth_low", low))
            if high is not None:
                candidates.append(("short", "prior_rth_high", high))
        elif self.setup_mode == "opening_low_profile_seller_trap_long":
            opening = self._opening_range()
            if opening is not None:
                candidates.append(("long", "opening_range_low", opening["low"]))
        elif self.setup_mode == "opening_high_profile_buyer_trap_short":
            opening = self._opening_range()
            if opening is not None:
                candidates.append(("short", "opening_range_high", opening["high"]))
        elif self.setup_mode == "opening_profile_two_sided_trap":
            opening = self._opening_range()
            if opening is not None:
                candidates.extend(
                    [
                        ("long", "opening_range_low", opening["low"]),
                        ("short", "opening_range_high", opening["high"]),
                    ]
                )
        elif self.setup_mode == "overnight_low_profile_seller_trap_long":
            level = _finite_float(bar.get("overnight_low"))
            if level is not None:
                candidates.append(("long", "overnight_low", level))
        elif self.setup_mode == "overnight_high_profile_buyer_trap_short":
            level = _finite_float(bar.get("overnight_high"))
            if level is not None:
                candidates.append(("short", "overnight_high", level))
        elif self.setup_mode == "overnight_profile_two_sided_trap":
            low = _finite_float(bar.get("overnight_low"))
            high = _finite_float(bar.get("overnight_high"))
            if low is not None:
                candidates.append(("long", "overnight_low", low))
            if high is not None:
                candidates.append(("short", "overnight_high", high))
        elif self.setup_mode == "market_profile_two_sided_trap":
            low = _finite_float(bar.get("prev_rth_low"))
            high = _finite_float(bar.get("prev_rth_high"))
            if low is not None:
                candidates.append(("long", "prior_rth_low", low))
            if high is not None:
                candidates.append(("short", "prior_rth_high", high))
            opening = self._opening_range()
            if opening is not None:
                candidates.extend(
                    [
                        ("long", "opening_range_low", opening["low"]),
                        ("short", "opening_range_high", opening["high"]),
                    ]
                )
        return candidates

    def _opening_range(self) -> dict | None:
        expected_bars = int(math.ceil(self.opening_range_minutes / self.bar_interval_minutes))
        if len(self.current_session_bars) < expected_bars:
            return None
        first = self.current_session_bars[0]
        session_start = pd.Timestamp(first["timestamp"])
        opening_end = session_start + pd.Timedelta(minutes=self.opening_range_minutes)
        opening_bars = [
            bar
            for bar in self.current_session_bars
            if pd.Timestamp(bar["timestamp"]) < opening_end
        ]
        if len(opening_bars) < expected_bars:
            return None
        return {
            "high": max(float(bar["high"]) for bar in opening_bars),
            "low": min(float(bar["low"]) for bar in opening_bars),
            "start_timestamp": session_start,
            "end_timestamp": opening_end,
        }

    def _profile_available(self, bar: pd.Series) -> bool:
        return self._active_profile(bar) is not None

    def _nearest_profile_level(self, aoi_level: float, bar: pd.Series | None = None) -> dict | None:
        profile = self._active_profile(bar)
        profile = profile or {}
        levels = profile.get("levels") or []
        if not levels:
            return None
        max_distance = self.max_profile_distance_ticks * self.tick_size
        best = min(levels, key=lambda item: abs(float(item["price"]) - aoi_level))
        distance = abs(float(best["price"]) - aoi_level)
        if distance > max_distance:
            return None
        return {
            "profile_level_type": best["type"],
            "profile_level_price": float(best["price"]),
            "profile_distance_ticks": distance / self.tick_size,
            "profile_source": self.profile_source,
            "profile_session": profile.get("session_date"),
            "profile_total_volume": profile.get("total_volume"),
            "profile_bars": profile.get("bar_count"),
            "prior_profile_session": profile.get("session_date"),
            "prior_profile_total_volume": profile.get("total_volume"),
            "prior_profile_bars": profile.get("bar_count"),
        }

    def _active_profile(self, bar: pd.Series | None = None) -> dict | None:
        if self.profile_source in {"cached_prior_vap", "cached_developing_vap", "cached_vap"}:
            return self._profile_from_cached_columns(bar)
        if self.profile_source == "developing_session_ohlcv":
            if bar is None:
                return self._profile_from_volume_by_tick(
                    self.current_session,
                    self.current_session_volume_by_tick,
                    self.current_session_profile_bar_count,
                    self.min_developing_profile_bars,
                )
            timestamp = _bar_timestamp(bar)
            if timestamp is not None and timestamp == self.current_session_profile_last_timestamp:
                return self._profile_from_volume_by_tick(
                    bar.get("session_date"),
                    self.current_session_volume_by_tick,
                    self.current_session_profile_bar_count,
                    self.min_developing_profile_bars,
                )
            volume_by_tick = dict(self.current_session_volume_by_tick)
            bar_count = self.current_session_profile_bar_count
            if self._accumulate_profile_bar(volume_by_tick, bar):
                bar_count += 1
            return self._profile_from_volume_by_tick(
                bar.get("session_date"),
                volume_by_tick,
                bar_count,
                self.min_developing_profile_bars,
            )
        return self.prior_profile

    def _profile_from_cached_columns(self, bar: pd.Series | None) -> dict | None:
        if bar is None:
            return None
        prefix = self.cached_profile_prefix
        level_specs = [
            ("poc", f"{prefix}_poc"),
            ("vah", f"{prefix}_vah"),
            ("val", f"{prefix}_val"),
            ("lvn", f"{prefix}_lvn_near_close"),
            ("lvn_near_high", f"{prefix}_lvn_near_high"),
            ("lvn_near_low", f"{prefix}_lvn_near_low"),
        ]
        levels = []
        seen: set[tuple[str, float]] = set()
        for level_type, column in level_specs:
            price = _finite_float(bar.get(column))
            if price is None or price <= 0:
                continue
            key = (level_type, round(price / self.tick_size) * self.tick_size)
            if key in seen:
                continue
            seen.add(key)
            levels.append({"type": level_type, "price": price})
        if not levels:
            return None
        return {
            "session_date": _finite_float(bar.get(f"{prefix}_session_yyyymmdd")),
            "levels": levels,
            "poc": _finite_float(bar.get(f"{prefix}_poc")),
            "vah": _finite_float(bar.get(f"{prefix}_vah")),
            "val": _finite_float(bar.get(f"{prefix}_val")),
            "lvn_count": _finite_float(bar.get(f"{prefix}_lvn_count")),
            "total_volume": _finite_float(bar.get(f"{prefix}_total_volume")),
            "bar_count": _finite_float(bar.get(f"{prefix}_bars"))
            or _finite_float(bar.get(f"{prefix}_price_levels")),
            "price_levels": _finite_float(bar.get(f"{prefix}_price_levels")),
        }

    def _long_trap_confirms(
        self,
        bar: pd.Series,
        level: float,
        open_price: float,
        low: float,
        close: float,
    ) -> bool:
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        absorption = _finite_float(bar.get("footprint_absorption_long")) or 0.0
        absorption_volume = _finite_float(bar.get("footprint_max_sell_imbalance_volume")) or 0.0
        absorption_price = _finite_float(bar.get("footprint_highest_sell_imbalance_price"))
        return (
            absorption > 0
            and absorption_volume >= self.min_absorption_volume
            and absorption_price is not None
            and absorption_price < close
            and self._adverse_delta_imbalance(bar, "long")
            and low <= level - probe
            and close >= level + confirm
            and close > open_price
        )

    def _short_trap_confirms(
        self,
        bar: pd.Series,
        level: float,
        open_price: float,
        high: float,
        close: float,
    ) -> bool:
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        absorption = _finite_float(bar.get("footprint_absorption_short")) or 0.0
        absorption_volume = _finite_float(bar.get("footprint_max_buy_imbalance_volume")) or 0.0
        absorption_price = _finite_float(bar.get("footprint_lowest_buy_imbalance_price"))
        return (
            absorption > 0
            and absorption_volume >= self.min_absorption_volume
            and absorption_price is not None
            and absorption_price > close
            and self._adverse_delta_imbalance(bar, "short")
            and high >= level + probe
            and close <= level - confirm
            and close < open_price
        )

    def _adverse_delta_imbalance(self, bar: pd.Series, direction: str) -> bool:
        if self.min_adverse_delta_imbalance <= 0:
            return True
        signed = _finite_float(bar.get("signed_volume"))
        volume = _finite_float(bar.get("volume"))
        if signed is None or volume is None or volume <= 0:
            return False
        imbalance = signed / volume
        if not math.isfinite(imbalance):
            return False
        if direction == "long":
            return imbalance <= -self.min_adverse_delta_imbalance
        return imbalance >= self.min_adverse_delta_imbalance

    def _signal(
        self,
        direction: str,
        aoi_type: str,
        aoi_level: float,
        profile_match: dict,
        bar: pd.Series,
        signal_timestamp: pd.Timestamp,
    ) -> Signal:
        volume_col = (
            "footprint_max_sell_imbalance_volume"
            if direction == "long"
            else "footprint_max_buy_imbalance_volume"
        )
        price_col = (
            "footprint_highest_sell_imbalance_price"
            if direction == "long"
            else "footprint_lowest_buy_imbalance_price"
        )
        signed = _finite_float(bar.get("signed_volume")) or 0.0
        volume = _finite_float(bar.get("volume")) or 0.0
        delta_imbalance = signed / volume if volume > 0 else 0.0
        fields = {
            "setup_mode": self.setup_mode,
            "aoi_type": aoi_type,
            "aoi_level": aoi_level,
            **profile_match,
            "min_probe_ticks": self.min_probe_ticks,
            "confirmation_ticks": self.confirmation_ticks,
            "min_absorption_volume": self.min_absorption_volume,
            "footprint_absorption_volume": _finite_float(bar.get(volume_col)) or 0.0,
            "footprint_absorption_price": _finite_float(bar.get(price_col)) or 0.0,
            "signed_volume": signed,
            "delta_imbalance": delta_imbalance,
            "min_adverse_delta_imbalance": self.min_adverse_delta_imbalance,
            "signal_timestamp": signal_timestamp,
            "intended_entry_timestamp": signal_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction=direction,
            level_type=f"{aoi_type}_{profile_match['profile_level_type']}_footprint_trap",
            swept_level=aoi_level,
            sweep_timestamp=bar["timestamp"],
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=signal_timestamp,
            breakout_level=aoi_level,
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _build_profile(
        self,
        session_date,
        bars: list[pd.Series],
        min_bars: int | None = None,
    ) -> dict | None:
        min_bars = self.min_prior_profile_bars if min_bars is None else int(min_bars)
        if len(bars) < min_bars:
            return None
        volume_by_tick: dict[int, float] = {}
        bar_count = 0
        for bar in bars:
            if self._accumulate_profile_bar(volume_by_tick, bar):
                bar_count += 1
        return self._profile_from_volume_by_tick(session_date, volume_by_tick, bar_count, min_bars)

    def _add_bar_to_developing_profile(self, bar: pd.Series) -> None:
        timestamp = _bar_timestamp(bar)
        if timestamp is not None and timestamp == self.current_session_profile_last_timestamp:
            return
        if self._accumulate_profile_bar(self.current_session_volume_by_tick, bar):
            self.current_session_profile_bar_count += 1
            self.current_session_profile_last_timestamp = timestamp

    def _accumulate_profile_bar(self, volume_by_tick: dict[int, float], bar: pd.Series) -> bool:
        if not bool(bar.get("is_rth", True)):
            return False
        volume = _finite_float(bar.get("volume"))
        low = _finite_float(bar.get("low"))
        high = _finite_float(bar.get("high"))
        if volume is None or volume <= 0 or low is None or high is None:
            return False
        low_tick = math.floor(low / self.tick_size)
        high_tick = math.ceil(high / self.tick_size)
        if high_tick < low_tick:
            return False
        ticks = list(range(low_tick, high_tick + 1))
        if not ticks:
            return False
        per_tick = volume / len(ticks)
        for tick in ticks:
            volume_by_tick[tick] = volume_by_tick.get(tick, 0.0) + per_tick
        return True

    def _profile_from_volume_by_tick(
        self,
        session_date,
        volume_by_tick: dict[int, float],
        bar_count: int,
        min_bars: int,
    ) -> dict | None:
        if bar_count < min_bars or not volume_by_tick:
            return None

        ticks = sorted(volume_by_tick)
        total_volume = sum(volume_by_tick.values())
        if total_volume <= 0:
            return None
        poc_tick = max(ticks, key=lambda tick: (volume_by_tick[tick], -abs(tick - (ticks[0] + ticks[-1]) / 2)))
        vah_tick, val_tick = self._value_area_bounds(ticks, volume_by_tick, poc_tick, total_volume)
        lvn_threshold = _quantile(list(volume_by_tick.values()), self.lvn_quantile)
        levels = [
            {"type": "poc", "price": poc_tick * self.tick_size},
            {"type": "vah", "price": vah_tick * self.tick_size},
            {"type": "val", "price": val_tick * self.tick_size},
        ]
        levels.extend(
            {"type": "lvn", "price": tick * self.tick_size}
            for tick in ticks
            if volume_by_tick[tick] <= lvn_threshold
        )
        return {
            "session_date": session_date,
            "levels": levels,
            "poc": poc_tick * self.tick_size,
            "vah": vah_tick * self.tick_size,
            "val": val_tick * self.tick_size,
            "lvn_count": sum(1 for item in levels if item["type"] == "lvn"),
            "total_volume": total_volume,
            "bar_count": bar_count,
        }

    def _value_area_bounds(
        self,
        ticks: list[int],
        volume_by_tick: dict[int, float],
        poc_tick: int,
        total_volume: float,
    ) -> tuple[int, int]:
        poc_index = ticks.index(poc_tick)
        left = right = poc_index
        included = volume_by_tick[poc_tick]
        target_volume = self.value_area_fraction * total_volume
        while included < target_volume and (left > 0 or right < len(ticks) - 1):
            left_volume = volume_by_tick[ticks[left - 1]] if left > 0 else -1.0
            right_volume = volume_by_tick[ticks[right + 1]] if right < len(ticks) - 1 else -1.0
            if left_volume > right_volume:
                left -= 1
                included += left_volume
            elif right_volume > left_volume:
                right += 1
                included += right_volume
            else:
                if left > 0:
                    left -= 1
                    included += left_volume
                if right < len(ticks) - 1 and included < target_volume:
                    right += 1
                    included += right_volume
        return ticks[right], ticks[left]

    def _validate(self) -> None:
        if self.setup_mode not in self._MODES:
            raise ValueError(f"entry.params.setup_mode must be one of {sorted(self._MODES)}.")
        if self.end_time <= self.start_time:
            raise ValueError("entry.params.end_time must be after start_time.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("entry.params.bar_interval_minutes must be positive.")
        if self.tick_size <= 0:
            raise ValueError("entry.params.tick_size must be positive.")
        if self.opening_range_minutes < 1:
            raise ValueError("entry.params.opening_range_minutes must be at least one.")
        if not 0 < self.value_area_fraction <= 1:
            raise ValueError("entry.params.value_area_fraction must be in (0, 1].")
        if not 0 < self.lvn_quantile < 1:
            raise ValueError("entry.params.lvn_quantile must be in (0, 1).")
        if self.profile_source not in {
            "computed_prior_ohlcv",
            "cached_prior_vap",
            "cached_developing_vap",
            "cached_vap",
            "developing_session_ohlcv",
        }:
            raise ValueError(
                "entry.params.profile_source must be computed_prior_ohlcv, cached_prior_vap, "
                "cached_developing_vap, cached_vap, or developing_session_ohlcv."
            )
        if self.min_prior_profile_bars < 1:
            raise ValueError("entry.params.min_prior_profile_bars must be positive.")
        if self.min_developing_profile_bars < 1:
            raise ValueError("entry.params.min_developing_profile_bars must be positive.")
        if self.max_profile_distance_ticks < 0:
            raise ValueError("entry.params.max_profile_distance_ticks must be non-negative.")
        if self.min_probe_ticks < 0 or self.confirmation_ticks < 0:
            raise ValueError("entry.params probe and confirmation ticks must be non-negative.")
        if self.min_absorption_volume <= 0:
            raise ValueError("entry.params.min_absorption_volume must be positive.")
        if self.min_adverse_delta_imbalance < 0:
            raise ValueError("entry.params.min_adverse_delta_imbalance must be non-negative.")
        if self.max_trades_per_day < 1:
            raise ValueError("entry.params.max_trades_per_day must be at least one.")
        if self.max_signals_per_session < 1:
            raise ValueError("entry.params.max_signals_per_session must be at least one.")


def _quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    index = int(math.floor((len(ordered) - 1) * fraction))
    return ordered[max(0, min(index, len(ordered) - 1))]


def _bar_timestamp(bar: pd.Series) -> pd.Timestamp | None:
    value = bar.get("timestamp")
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value)


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
