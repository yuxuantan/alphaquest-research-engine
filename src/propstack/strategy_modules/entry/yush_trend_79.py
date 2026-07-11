from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.yush_range_1 import YushRange1Entry


class YushTrend79Entry(YushRange1Entry):
    name = "yush_trend_79"

    def __init__(self, params: dict):
        super().__init__(params)
        self.acceptance_hold_seconds = float(params.get("acceptance_hold_seconds", 1.0))
        self.acceptance_hold_ticks = int(params.get("acceptance_hold_ticks", 0))
        self.probe_ticks = int(params.get("probe_ticks", 2))
        self.max_signal_risk_points = float(params.get("max_signal_risk_points", 6.0))
        self._pending_acceptance: dict[tuple[str, int], dict] = {}
        self._validate_trend79_params()

    def _roll_session(self, bar: pd.Series) -> None:
        previous = self.session_key
        super()._roll_session(bar)
        if self.session_key != previous:
            self._pending_acceptance = {}

    def on_bar_intrabar(
        self,
        bar: pd.Series,
        detail_rows: pd.DataFrame,
        trades_today: int = 0,
    ) -> Signal | None:
        self._roll_session(bar)
        if detail_rows is None or detail_rows.empty:
            return None

        session_key = self.session_key
        can_emit = (
            bool(bar.get("is_rth", False))
            and trades_today < self.max_trades_per_day
            and self.signals_by_session.get(session_key, 0) < self.max_trades_per_day
        )
        bar_timestamp = pd.Timestamp(bar["timestamp"])
        if not can_emit:
            self.state.update_bar_aggregate(
                detail_rows,
                bar_timestamp=bar_timestamp,
                profile_bucket_points=self.profile_bucket_points,
                range_snapshot_minutes=self.range_snapshot_minutes,
            )
            return None
        profile_cache = None
        profile_cache_timestamp = None
        range_cache = None
        range_cache_timestamp = None

        for tick_state in self._iter_tick_states(detail_rows, bar_timestamp):
            if tick_state is None or not can_emit:
                continue
            tick_time = tick_state["timestamp"].time()
            if tick_time < self.start_time or tick_time > self.end_time:
                continue
            if (
                range_cache is None
                or range_cache_timestamp is None
                or (tick_state["timestamp"] - range_cache_timestamp).total_seconds() >= self.range_recheck_seconds
            ):
                range_cache = self._range_is_stable(tick_state["timestamp"])
                range_cache_timestamp = tick_state["timestamp"]
            if not range_cache:
                continue
            if (
                profile_cache is None
                or profile_cache_timestamp is None
                or (tick_state["timestamp"] - profile_cache_timestamp).total_seconds() >= self.profile_recheck_seconds
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

            for direction in ("long", "short"):
                if direction == "long" and not self.allow_long:
                    continue
                if direction == "short" and not self.allow_short:
                    continue
                pending = self._update_acceptance_state(direction, profile, tick_state)
                if pending is None or not pending.get("confirmed"):
                    continue
                confirmation = self.state.confirmed_orderflow(direction, self.confirmation_modes)
                if confirmation is None:
                    continue
                risk_points = self._signal_risk_points(direction, pending, tick_state)
                if risk_points is None or risk_points > self.max_signal_risk_points:
                    continue
                signal = self._signal_for_acceptance(
                    direction=direction,
                    bar=bar,
                    tick_state=tick_state,
                    profile=profile,
                    pending=pending,
                    confirmation=confirmation,
                    risk_points=risk_points,
                )
                self.signals_by_session[session_key] = self.signals_by_session.get(session_key, 0) + 1
                return signal
        return None

    def _iter_tick_states(self, detail_rows: pd.DataFrame, bar_timestamp: pd.Timestamp):
        timestamps = pd.to_datetime(detail_rows["timestamp"])
        close = pd.to_numeric(detail_rows["close"], errors="coerce").to_numpy()
        volume = pd.to_numeric(detail_rows["volume"], errors="coerce").to_numpy()
        high_source = detail_rows["high"] if "high" in detail_rows else detail_rows["close"]
        low_source = detail_rows["low"] if "low" in detail_rows else detail_rows["close"]
        high = pd.to_numeric(high_source, errors="coerce").to_numpy()
        low = pd.to_numeric(low_source, errors="coerce").to_numpy()
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
        buy = pd.to_numeric(buy_source, errors="coerce").fillna(0.0).to_numpy()
        sell = pd.to_numeric(sell_source, errors="coerce").fillna(0.0).to_numpy()
        for idx, timestamp in enumerate(timestamps):
            yield self.state.update_tick_values(
                timestamp=timestamp,
                price=close[idx],
                volume=volume[idx],
                high=high[idx],
                low=low[idx],
                buy=buy[idx],
                sell=sell[idx],
                bar_timestamp=bar_timestamp,
                profile_bucket_points=self.profile_bucket_points,
                delta_bucket_points=self.delta_bucket_points,
                absorption_delta_threshold=self.absorption_delta_threshold,
                hold_seconds=self.absorption_hold_seconds,
                range_snapshot_minutes=self.range_snapshot_minutes,
            )

    def _update_acceptance_state(self, direction: str, profile: dict, tick_state: dict) -> dict | None:
        level_type = "VAH" if direction == "long" else "VAL"
        level_price = float(profile["vah"] if direction == "long" else profile["val"])
        high = self.state.current_bar_high
        low = self.state.current_bar_low
        price = float(tick_state["price"])
        if high is None or low is None or not math.isfinite(level_price):
            return None

        probe = self.probe_ticks * self.tick_size
        hold = self.acceptance_hold_ticks * self.tick_size
        key = (direction, round(level_price / self.tick_size))
        pending = self._pending_acceptance.get(key)
        if pending is None:
            broke = high >= level_price + probe if direction == "long" else low <= level_price - probe
            if not broke:
                return None
            pending = {
                "direction": direction,
                "profile_level_type": level_type,
                "profile_level_price": level_price,
                "breakout_timestamp": tick_state["timestamp"],
                "breakout_high": float(high),
                "breakout_low": float(low),
                "hold_start": None,
                "confirmed": False,
                "confirmed_at": None,
                "profile_snapshot_at_breakout": dict(profile),
            }
            self._pending_acceptance[key] = pending

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
        if (tick_state["timestamp"] - pending["hold_start"]).total_seconds() >= self.acceptance_hold_seconds:
            pending["confirmed"] = True
            pending["confirmed_at"] = tick_state["timestamp"]
        return pending

    def _signal_stop_price(self, direction: str, pending: dict) -> float:
        offset = self.stop_offset_ticks * self.tick_size
        level = float(pending["profile_level_price"])
        return level - offset if direction == "long" else level + offset

    def _signal_risk_points(self, direction: str, pending: dict, tick_state: dict) -> float | None:
        entry = float(tick_state["price"])
        stop = self._signal_stop_price(direction, pending)
        risk = entry - stop if direction == "long" else stop - entry
        return risk if math.isfinite(risk) and risk > 0 else None

    def _signal_for_acceptance(
        self,
        *,
        direction: str,
        bar: pd.Series,
        tick_state: dict,
        profile: dict,
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
            "profile_level_type": pending["profile_level_type"],
            "profile_level_price": pending["profile_level_price"],
            "breakout_timestamp": pending["breakout_timestamp"],
            "breakout_hold_start": pending["hold_start"],
            "breakout_confirmed_at": pending["confirmed_at"],
            "acceptance_hold_seconds": self.acceptance_hold_seconds,
            "acceptance_hold_ticks": self.acceptance_hold_ticks,
            "probe_ticks": self.probe_ticks,
            "max_signal_risk_points": self.max_signal_risk_points,
            "signal_risk_points": risk_points,
            "signal_stop_price": stop_price,
            "stop_reference": "inside_developing_value_area_edge",
            "target_reference": "fixed_r_after_developing_value_area_acceptance",
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
            level_type=f"{self.name}_{direction}_{pending['profile_level_type']}",
            swept_level=float(pending["profile_level_price"]),
            sweep_timestamp=pending["breakout_timestamp"],
            sweep_high=float(pending["breakout_high"]),
            sweep_low=float(pending["breakout_low"]),
            reclaim_timestamp=tick_state["timestamp"],
            breakout_level=float(pending["profile_level_price"]),
            metadata=fields.copy(),
            report_fields=fields,
        )

    def _validate_trend79_params(self) -> None:
        if self.acceptance_hold_seconds < 0:
            raise ValueError("entry.params.acceptance_hold_seconds must be non-negative.")
        if self.acceptance_hold_ticks < 0 or self.probe_ticks < 0:
            raise ValueError("entry.params acceptance/probe tick settings must be non-negative.")
        if not math.isfinite(self.max_signal_risk_points) or self.max_signal_risk_points <= 0:
            raise ValueError("entry.params.max_signal_risk_points must be positive and finite.")
