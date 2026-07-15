from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.yush_range_1 import YushRange1Entry


class YushRange4Entry(YushRange1Entry):
    name = "yush_range_4"

    def on_bar_intrabar(
        self,
        bar: pd.Series,
        detail_rows: pd.DataFrame,
        trades_today: int = 0,
    ):
        self._roll_session(bar)
        if detail_rows is None or detail_rows.empty:
            return None

        previous_bar = self.current_session_bars[-1] if self.current_session_bars else None
        atr = self._atr()
        session_key = self.session_key
        can_emit = (
            bool(bar.get("is_rth", False))
            and trades_today < self.max_trades_per_day
            and self.signals_by_session.get(session_key, 0) < self.max_trades_per_day
            and atr is not None
        )
        if not can_emit or not self._detail_window_can_absorb(detail_rows):
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

            for direction in ("long", "short"):
                if direction == "long" and not self.allow_long:
                    continue
                if direction == "short" and not self.allow_short:
                    continue
                sweep = self._value_area_edge_sweep(direction, profile)
                if sweep is None:
                    continue
                confirmation = self.state.confirmed_orderflow(direction, self.confirmation_modes)
                if confirmation is None:
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
                if not self._within_atr_of_value_edge(direction, tick_state["price"], profile, atr):
                    continue
                signal = self._signal(direction, bar, tick_state, profile, sweep, confirmation, atr)
                self.signals_by_session[session_key] = self.signals_by_session.get(session_key, 0) + 1
                return signal
        return None

    def _value_area_edge_sweep(self, direction: str, profile: dict) -> dict | None:
        current_high = self.state.current_bar_high
        current_low = self.state.current_bar_low
        if current_high is None or current_low is None:
            return None
        if direction == "long":
            edge = float(profile["val"])
            swept = current_low < edge <= current_high
            edge_type = "VAL"
        else:
            edge = float(profile["vah"])
            swept = current_low <= edge < current_high
            edge_type = "VAH"
        if not swept:
            return None
        return {
            "market_level_type": edge_type,
            "market_level_price": edge,
            "market_sweep_window": "current_developing_3m",
            "market_sweep_source": "current_developing_value_area_edge",
        }
