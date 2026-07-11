from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.yush_range_28 import YushRange28Entry


class YushRange29Entry(YushRange28Entry):
    name = "yush_range_29"

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
        self._update_opening_range(detail_rows)

        levels = self._market_levels(bar)
        atr = self._atr()
        session_key = self.session_key
        can_emit = (
            bool(bar.get("is_rth", False))
            and trades_today < self.max_trades_per_day
            and self.signals_by_session.get(session_key, 0) < self.max_trades_per_day
            and atr is not None
            and bool(levels)
        )

        profile_cache = None
        profile_cache_timestamp = None
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
                for level in levels:
                    pending = self._update_reclaim_state(direction, level, tick_state)
                    if pending is None or not pending.get("confirmed"):
                        continue
                    confirmation = self.state.confirmed_orderflow(direction, self.confirmation_modes)
                    if confirmation is None or not self._entry_close_enough(direction, pending, tick_state):
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
                    target = float(profile["vah"] if direction == "long" else profile["val"])
                    entry_price = float(tick_state["price"])
                    if direction == "long" and target <= entry_price:
                        continue
                    if direction == "short" and target >= entry_price:
                        continue
                    signal = self._signal_for_reclaim(
                        direction=direction,
                        bar=bar,
                        tick_state=tick_state,
                        pending=pending,
                        confirmation=confirmation,
                    )
                    fields = {
                        "signal_target_price": target,
                        "target_reference": "opposite_developing_value_area_edge",
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
                    }
                    signal.metadata.update(fields)
                    signal.report_fields.update(fields)
                    self.signals_by_session[session_key] = self.signals_by_session.get(session_key, 0) + 1
                    return signal
        return None
