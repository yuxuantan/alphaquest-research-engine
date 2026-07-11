from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from propstack.strategy_modules.entry.profile_aoi_footprint_trap import _finite_float
from propstack.strategy_modules.entry.video_exact_orderflow_playbook_scid_intrabar import (
    VideoExactOrderflowPlaybookScidIntrabarEntry,
)


class YushTrend16Entry(VideoExactOrderflowPlaybookScidIntrabarEntry):
    name = "yush_trend_16"

    def __init__(self, params: dict):
        super().__init__(params)
        self.delta_bucket_points = float(params.get("delta_bucket_points", 1.0))
        self.initiation_delta_threshold = float(
            params.get("initiation_delta_threshold", params.get("absorption_delta_threshold", 300.0))
        )
        self.initiation_hold_seconds = float(
            params.get("initiation_hold_seconds", params.get("absorption_hold_seconds", 3.0))
        )
        self.max_signal_risk_points = float(params.get("max_signal_risk_points", 6.0))
        self.stop_offset_ticks = int(params.get("stop_offset_ticks", 2))
        if self.delta_bucket_points <= 0:
            raise ValueError("entry.params.delta_bucket_points must be greater than 0.")
        if self.initiation_delta_threshold <= 0 or self.initiation_hold_seconds < 0:
            raise ValueError("entry.params initiation threshold/hold settings are invalid.")
        if not math.isfinite(self.max_signal_risk_points) or self.max_signal_risk_points <= 0:
            raise ValueError("entry.params.max_signal_risk_points must be greater than 0.")

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
            or not self.current_session_bars
        ):
            return None

        context_bar = self.current_session_bars[-1]
        profile = self._active_profile(context_bar) or {}
        if not profile:
            return None

        close = _finite_float(context_bar.get("close")) or 0.0
        candidates = [
            candidate for candidate in self._candidate_setups(bar, profile, close) if candidate[1] == "trend"
        ]
        if not candidates:
            return None

        state = _TrendInitiationIntrabarState()
        for tick in detail_rows.itertuples(index=False):
            tick_state = state.update(
                tick,
                bar_timestamp=pd.Timestamp(bar["timestamp"]),
                delta_bucket_points=self.delta_bucket_points,
                initiation_delta_threshold=self.initiation_delta_threshold,
                initiation_hold_seconds=self.initiation_hold_seconds,
            )
            if tick_state is None:
                continue
            tick_timestamp = pd.Timestamp(tick_state["timestamp"])
            if tick_timestamp.time() < self.start_time or tick_timestamp.time() > self.end_time:
                continue
            for direction, model, level_type, level in candidates:
                if direction == "long" and not self.allow_long:
                    continue
                if direction == "short" and not self.allow_short:
                    continue
                confluence = self._intrabar_aoi_confluence(bar, profile, direction, model, level, tick_state)
                if len(confluence["criteria"]) < self.min_aoi_confluences:
                    continue
                if not self._intrabar_trend_initiation_confirms(direction, level, tick_state):
                    continue
                risk_points = self._known_signal_risk_points(direction, tick_state)
                if risk_points is None or risk_points > self.max_signal_risk_points:
                    continue
                signal = self._intrabar_video_signal(
                    direction=direction,
                    model=model,
                    level_type=level_type,
                    level=level,
                    profile=profile,
                    confluence=confluence,
                    tick_state=tick_state,
                    tick=pd.Series(tick._asdict()),
                )
                fields = {
                    "entry_trigger": "delta_bucket_initiation",
                    "delta_bucket_points": self.delta_bucket_points,
                    "initiation_delta_threshold": self.initiation_delta_threshold,
                    "initiation_hold_seconds": self.initiation_hold_seconds,
                    "orderflow_bucket_bottom": tick_state["initiation_bucket_bottom"],
                    "orderflow_bucket_top": tick_state["initiation_bucket_top"],
                    "orderflow_bucket_delta": tick_state["initiation_delta"],
                    "orderflow_hold_start": tick_state["initiation_hold_start"],
                    "orderflow_confirmed_at": tick_state["initiation_confirmed_at"],
                    "max_signal_risk_points": self.max_signal_risk_points,
                    "signal_risk_points": risk_points,
                }
                signal.metadata.update(fields)
                signal.report_fields.update(fields)
                self.signals_by_session[session_date] = self.signals_by_session.get(session_date, 0) + 1
                self.current_session_bars.append(bar.copy())
                self._last_intrabar_appended_timestamp = pd.Timestamp(bar["timestamp"])
                return signal
        return None

    def _intrabar_trend_initiation_confirms(self, direction: str, level: float, state: dict) -> bool:
        if not self._bar_reaches_aoi(state["high"], state["low"], level):
            return False
        confirm = self.confirmation_ticks * self.tick_size
        price = state["price"]
        if direction == "long":
            return (
                state.get("confirmed_long_initiation") is not None
                and self._intrabar_directional_delta_imbalance("long", state)
                and price >= level + confirm
                and price > state["open"]
            )
        return (
            state.get("confirmed_short_initiation") is not None
            and self._intrabar_directional_delta_imbalance("short", state)
            and price <= level - confirm
            and price < state["open"]
        )

    def _known_signal_risk_points(self, direction: str, state: dict) -> float | None:
        stop_offset = self.stop_offset_ticks * self.tick_size
        if direction == "long":
            risk = float(state["price"]) - (float(state["low"]) - stop_offset)
        else:
            risk = (float(state["high"]) + stop_offset) - float(state["price"])
        return risk if math.isfinite(risk) and risk > 0 else None


@dataclass
class _InitiationCandidate:
    bucket_bottom: float
    bucket_top: float
    delta: float
    hold_start: pd.Timestamp | None = None
    confirmed_at: pd.Timestamp | None = None
    confirmed: bool = False


class _TrendInitiationIntrabarState:
    def __init__(self) -> None:
        self.current_bar_timestamp: pd.Timestamp | None = None
        self.open: float | None = None
        self.high = -math.inf
        self.low = math.inf
        self.volume = 0.0
        self.signed_volume = 0.0
        self.delta_by_bucket: dict[float, float] = {}
        self.active_long_initiation: _InitiationCandidate | None = None
        self.active_short_initiation: _InitiationCandidate | None = None
        self.large_record_volume = 0.0
        self.large_record_signed_volume = 0.0
        self.large_record_count = 0.0
        self.large_record_max_volume = 0.0

    def update(
        self,
        tick,
        *,
        bar_timestamp: pd.Timestamp,
        delta_bucket_points: float,
        initiation_delta_threshold: float,
        initiation_hold_seconds: float,
    ) -> dict | None:
        if self.current_bar_timestamp != bar_timestamp:
            self.current_bar_timestamp = bar_timestamp
            self.open = None
            self.high = -math.inf
            self.low = math.inf
            self.volume = 0.0
            self.signed_volume = 0.0
            self.delta_by_bucket = {}
            self.active_long_initiation = None
            self.active_short_initiation = None
            self.large_record_volume = 0.0
            self.large_record_signed_volume = 0.0
            self.large_record_count = 0.0
            self.large_record_max_volume = 0.0

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
        trades = _finite_float(_row_value(tick, "num_trades"))
        if trades is None:
            trades = _finite_float(_row_value(tick, "trades")) or 1.0
        signed = buy - sell

        if self.open is None:
            self.open = price
        self.high = max(self.high, high)
        self.low = min(self.low, low)
        self.volume += volume
        self.signed_volume += signed
        if volume >= 200 and trades == 1 and math.isclose(buy + sell, volume):
            self.large_record_volume += volume
            self.large_record_signed_volume += signed
            self.large_record_count += 1.0
            self.large_record_max_volume = max(self.large_record_max_volume, volume)

        bucket = _bucket_start(price, delta_bucket_points)
        self.delta_by_bucket[bucket] = self.delta_by_bucket.get(bucket, 0.0) + signed
        self._update_initiation_candidates(
            timestamp,
            price,
            bucket,
            delta_bucket_points,
            initiation_delta_threshold,
            initiation_hold_seconds,
        )
        long_initiation = self._confirmed(self.active_long_initiation)
        short_initiation = self._confirmed(self.active_short_initiation)
        confirmed = long_initiation or short_initiation
        return {
            "timestamp": timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "price": price,
            "volume": self.volume,
            "signed_volume": self.signed_volume,
            "large_record_volume": self.large_record_volume,
            "large_record_signed_volume": self.large_record_signed_volume,
            "large_record_count": self.large_record_count,
            "large_record_max_volume": self.large_record_max_volume,
            "max_sell_imbalance_volume": 0.0,
            "max_buy_imbalance_volume": 0.0,
            "highest_sell_absorption_price": None,
            "lowest_buy_absorption_price": None,
            "confirmed_long_initiation": long_initiation,
            "confirmed_short_initiation": short_initiation,
            "initiation_bucket_bottom": confirmed["bucket_bottom"] if confirmed else None,
            "initiation_bucket_top": confirmed["bucket_top"] if confirmed else None,
            "initiation_delta": confirmed["delta"] if confirmed else None,
            "initiation_hold_start": confirmed["hold_start"] if confirmed else None,
            "initiation_confirmed_at": confirmed["confirmed_at"] if confirmed else None,
        }

    def _update_initiation_candidates(
        self,
        timestamp: pd.Timestamp,
        price: float,
        bucket: float,
        bucket_points: float,
        threshold: float,
        hold_seconds: float,
    ) -> None:
        delta = self.delta_by_bucket[bucket]
        if delta >= threshold:
            if self.active_long_initiation is None or self.active_long_initiation.bucket_bottom != bucket:
                self.active_long_initiation = _InitiationCandidate(bucket, bucket + bucket_points, delta)
            else:
                self.active_long_initiation.delta = delta
        if delta <= -threshold:
            if self.active_short_initiation is None or self.active_short_initiation.bucket_bottom != bucket:
                self.active_short_initiation = _InitiationCandidate(bucket, bucket + bucket_points, delta)
            else:
                self.active_short_initiation.delta = delta
        self._advance_long_initiation(timestamp, price, threshold, hold_seconds)
        self._advance_short_initiation(timestamp, price, threshold, hold_seconds)

    def _advance_long_initiation(
        self,
        timestamp: pd.Timestamp,
        price: float,
        threshold: float,
        hold_seconds: float,
    ) -> None:
        candidate = self.active_long_initiation
        if candidate is None:
            return
        candidate.delta = self.delta_by_bucket.get(candidate.bucket_bottom, 0.0)
        if candidate.delta < threshold or price <= candidate.bucket_top:
            candidate.hold_start = None
            candidate.confirmed = False
            candidate.confirmed_at = None
            return
        if candidate.hold_start is None:
            candidate.hold_start = timestamp
        if (timestamp - candidate.hold_start).total_seconds() >= hold_seconds:
            candidate.confirmed = True
            candidate.confirmed_at = timestamp

    def _advance_short_initiation(
        self,
        timestamp: pd.Timestamp,
        price: float,
        threshold: float,
        hold_seconds: float,
    ) -> None:
        candidate = self.active_short_initiation
        if candidate is None:
            return
        candidate.delta = self.delta_by_bucket.get(candidate.bucket_bottom, 0.0)
        if candidate.delta > -threshold or price >= candidate.bucket_bottom:
            candidate.hold_start = None
            candidate.confirmed = False
            candidate.confirmed_at = None
            return
        if candidate.hold_start is None:
            candidate.hold_start = timestamp
        if (timestamp - candidate.hold_start).total_seconds() >= hold_seconds:
            candidate.confirmed = True
            candidate.confirmed_at = timestamp

    def _confirmed(self, candidate: _InitiationCandidate | None) -> dict | None:
        if candidate is None or not candidate.confirmed:
            return None
        return {
            "bucket_bottom": candidate.bucket_bottom,
            "bucket_top": candidate.bucket_top,
            "delta": candidate.delta,
            "hold_start": candidate.hold_start,
            "confirmed_at": candidate.confirmed_at,
        }


def _bucket_start(price: float, bucket_points: float) -> float:
    return math.floor(price / bucket_points) * bucket_points


def _row_value(row, key: str):
    if isinstance(row, pd.Series):
        return row.get(key)
    return getattr(row, key, None)
