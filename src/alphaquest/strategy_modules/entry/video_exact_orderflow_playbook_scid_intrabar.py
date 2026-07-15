from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.profile_aoi_footprint_trap import _finite_float
from alphaquest.strategy_modules.entry.video_exact_orderflow_playbook import VideoExactOrderflowPlaybookEntry


class VideoExactOrderflowPlaybookScidIntrabarEntry(VideoExactOrderflowPlaybookEntry):
    name = "video_exact_orderflow_playbook_scid_intrabar"

    _SUPPORTED_MODES = {
        "model1_range_value_edge_two_sided",
        "model1_range_value_edge_long",
        "model1_range_value_edge_short",
        "model2_trend_lvn_two_sided",
        "model2_trend_lvn_long",
        "model2_trend_lvn_short",
    }

    def __init__(self, params: dict):
        super().__init__(params)
        self._last_intrabar_appended_timestamp: pd.Timestamp | None = None

    def on_bar_intrabar(
        self,
        bar: pd.Series,
        detail_rows: pd.DataFrame,
        trades_today: int = 0,
    ) -> Signal | None:
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

        candidates = self._candidate_setups(bar, profile, _finite_float(context_bar.get("close")) or 0.0)
        if not candidates:
            return None

        state = _IntrabarState()
        for _, tick in detail_rows.iterrows():
            tick_state = state.update(tick)
            if tick_state is None:
                continue
            tick_timestamp = pd.Timestamp(tick["timestamp"])
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
                if model == "range":
                    confirms = self._intrabar_range_trap_confirms(direction, level, tick_state)
                else:
                    confirms = self._intrabar_trend_pullback_confirms(direction, level, tick_state)
                if not confirms:
                    continue
                signal = self._intrabar_video_signal(
                    direction=direction,
                    model=model,
                    level_type=level_type,
                    level=level,
                    profile=profile,
                    confluence=confluence,
                    tick_state=tick_state,
                    tick=tick,
                )
                self.signals_by_session[session_date] = self.signals_by_session.get(session_date, 0) + 1
                self.signaled_sessions.add(session_date)
                self.current_session_bars.append(bar.copy())
                self._last_intrabar_appended_timestamp = pd.Timestamp(bar["timestamp"])
                return signal
        return None

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        self._roll_session(bar)
        timestamp = pd.Timestamp(bar["timestamp"])
        if self._last_intrabar_appended_timestamp is None or timestamp != self._last_intrabar_appended_timestamp:
            self.current_session_bars.append(bar.copy())
        return None

    def _intrabar_aoi_confluence(
        self,
        bar: pd.Series,
        profile: dict,
        direction: str,
        model: str,
        level: float,
        state: dict,
    ) -> dict:
        criteria = ["volume_profile"]
        details = {
            "aoi_volume_profile_level": float(level),
            "aoi_volume_profile_source": self.profile_source,
            "intrabar_profile_context": "prior_completed_3m_bar",
        }
        market = self._nearest_market_level(bar, level)
        if market is not None:
            criteria.append("market_level")
            details.update(market)
        large_record = self._intrabar_large_record_state(state)
        if large_record is not None and self._flow_side_confirms(direction, model, large_record["signed_volume"]):
            criteria.append("big_trades")
            details.update(
                {
                    "large200_record_max_volume": large_record["max_volume"],
                    "large200_record_volume": large_record["total_volume"],
                    "large200_record_signed_volume": large_record["signed_volume"],
                    "large200_record_count": large_record["record_count"],
                    "large200_record_dominant_side": large_record["dominant_side"],
                }
            )
        delta = state["signed_volume"] / state["volume"] if state["volume"] > 0 else None
        if delta is not None and math.isfinite(delta) and abs(delta) >= self.min_delta_activity_imbalance:
            if self._flow_side_confirms(direction, model, delta):
                criteria.append("delta_activity")
                details["aoi_delta_imbalance"] = delta
        return {"criteria": criteria, "details": details}

    def _intrabar_large_record_state(self, state: dict) -> dict | None:
        if (
            state["large_record_max_volume"] < self.min_large200_record_volume
            or state["large_record_volume"] <= 0
            or state["large_record_signed_volume"] == 0
        ):
            return None
        signed = state["large_record_signed_volume"]
        return {
            "max_volume": state["large_record_max_volume"],
            "total_volume": state["large_record_volume"],
            "signed_volume": signed,
            "record_count": state["large_record_count"],
            "dominant_side": "buy" if signed > 0 else "sell",
        }

    def _intrabar_range_trap_confirms(self, direction: str, level: float, state: dict) -> bool:
        if not self._bar_reaches_aoi(state["high"], state["low"], level):
            return False
        probe = self.min_probe_ticks * self.tick_size
        confirm = self.confirmation_ticks * self.tick_size
        price = state["price"]
        if direction == "long":
            absorption_price = state["highest_sell_absorption_price"]
            return (
                state["max_sell_imbalance_volume"] >= self.min_absorption_volume
                and absorption_price is not None
                and absorption_price < price
                and state["low"] <= level - probe
                and price >= level + confirm
                and price > state["open"]
            )
        absorption_price = state["lowest_buy_absorption_price"]
        return (
            state["max_buy_imbalance_volume"] >= self.min_absorption_volume
            and absorption_price is not None
            and absorption_price > price
            and state["high"] >= level + probe
            and price <= level - confirm
            and price < state["open"]
        )

    def _intrabar_trend_pullback_confirms(self, direction: str, level: float, state: dict) -> bool:
        if not self._bar_reaches_aoi(state["high"], state["low"], level):
            return False
        confirm = self.confirmation_ticks * self.tick_size
        price = state["price"]
        if direction == "long":
            absorption_price = state["highest_sell_absorption_price"]
            return (
                state["max_sell_imbalance_volume"] >= self.min_absorption_volume
                and absorption_price is not None
                and absorption_price < price
                and self._intrabar_directional_delta_imbalance("long", state)
                and price >= level + confirm
                and price > state["open"]
            )
        absorption_price = state["lowest_buy_absorption_price"]
        return (
            state["max_buy_imbalance_volume"] >= self.min_absorption_volume
            and absorption_price is not None
            and absorption_price > price
            and self._intrabar_directional_delta_imbalance("short", state)
            and price <= level - confirm
            and price < state["open"]
        )

    def _intrabar_directional_delta_imbalance(self, direction: str, state: dict) -> bool:
        if self.min_directional_delta_imbalance <= 0:
            return True
        volume = state["volume"]
        if volume <= 0:
            return False
        delta = state["signed_volume"] / volume
        if direction == "long":
            return delta >= self.min_directional_delta_imbalance
        return delta <= -self.min_directional_delta_imbalance

    def _intrabar_video_signal(
        self,
        *,
        direction: str,
        model: str,
        level_type: str,
        level: float,
        profile: dict,
        confluence: dict,
        tick_state: dict,
        tick: pd.Series,
    ) -> Signal:
        tick_timestamp = pd.Timestamp(tick["timestamp"])
        fields = {
            "setup_mode": self.setup_mode,
            "entry_mode": "intrabar",
            "entry_reference_price": float(tick_state["price"]),
            "intrabar_entry_price": float(tick_state["price"]),
            "video_model": "model1_range_scid_intrabar" if model == "range" else "model2_trend_scid_intrabar",
            "profile_level_type": level_type,
            "profile_level_price": float(level),
            "profile_source": self.profile_source,
            "profile_session": profile.get("session_date"),
            "profile_total_volume": profile.get("total_volume"),
            "profile_bars": profile.get("bar_count"),
            "aoi_min_confluences": self.min_aoi_confluences,
            "aoi_confluence_count": len(confluence["criteria"]),
            "aoi_confluence_criteria": ",".join(confluence["criteria"]),
            "aoi_reach_tolerance_ticks": self.aoi_reach_tolerance_ticks,
            "market_aoi_max_distance_ticks": self.market_aoi_max_distance_ticks,
            "min_large200_record_volume": self.min_large200_record_volume,
            "min_delta_activity_imbalance": self.min_delta_activity_imbalance,
            "min_absorption_volume": self.min_absorption_volume,
            "signed_volume": tick_state["signed_volume"],
            "delta_imbalance": tick_state["signed_volume"] / tick_state["volume"] if tick_state["volume"] else 0.0,
            "confirmation_high": float(tick_state["high"]),
            "confirmation_low": float(tick_state["low"]),
            "signal_timestamp": tick_timestamp,
            "intended_entry_timestamp": tick_timestamp,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "intrabar_source": "sierra_scid_record_replay",
            "intrabar_source_quality_label": (
                "Sierra SCID record close-only replay; raw high/low are not treated as traded-price extrema; "
                "not exchange MBO sequencing."
            ),
            "video_mechanics_not_simulated": "partials_dynamic_trailing_and_tick_built_vap_footprint",
        }
        fields.update(confluence["details"])
        target = self._target_price(direction, model, profile)
        if target is not None:
            fields["signal_target_price"] = target
            fields["signal_target_reference"] = self.target_reference
        return Signal(
            direction=direction,
            level_type=f"{model}_{level_type}_{direction}_video_exact_scid_intrabar",
            swept_level=float(level),
            sweep_timestamp=tick_timestamp,
            sweep_high=float(tick_state["high"]),
            sweep_low=float(tick_state["low"]),
            reclaim_timestamp=tick_timestamp,
            breakout_level=float(level),
            metadata=fields.copy(),
            report_fields=fields,
        )


class _IntrabarState:
    def __init__(self) -> None:
        self.open: float | None = None
        self.high = -math.inf
        self.low = math.inf
        self.volume = 0.0
        self.signed_volume = 0.0
        self.max_sell_imbalance_volume = 0.0
        self.max_buy_imbalance_volume = 0.0
        self.highest_sell_absorption_price: float | None = None
        self.lowest_buy_absorption_price: float | None = None
        self.large_record_volume = 0.0
        self.large_record_signed_volume = 0.0
        self.large_record_count = 0.0
        self.large_record_max_volume = 0.0

    def update(self, tick: pd.Series) -> dict | None:
        price = _finite_float(tick.get("close"))
        volume = _finite_float(tick.get("volume"))
        if price is None or volume is None or volume <= 0:
            return None
        high = _finite_float(tick.get("high")) or price
        low = _finite_float(tick.get("low")) or price
        bid = _finite_float(tick.get("sell_volume"))
        if bid is None:
            bid = _finite_float(tick.get("bid_volume")) or 0.0
        ask = _finite_float(tick.get("buy_volume"))
        if ask is None:
            ask = _finite_float(tick.get("ask_volume")) or 0.0
        trades = _finite_float(tick.get("num_trades"))
        if trades is None:
            trades = _finite_float(tick.get("trades")) or 1.0
        if self.open is None:
            self.open = price
        self.high = max(self.high, high)
        self.low = min(self.low, low)
        self.volume += volume
        signed = ask - bid
        self.signed_volume += signed
        self.max_sell_imbalance_volume = max(self.max_sell_imbalance_volume, bid)
        self.max_buy_imbalance_volume = max(self.max_buy_imbalance_volume, ask)
        if bid > 0:
            self.highest_sell_absorption_price = (
                price
                if self.highest_sell_absorption_price is None
                else max(self.highest_sell_absorption_price, price)
            )
        if ask > 0:
            self.lowest_buy_absorption_price = (
                price if self.lowest_buy_absorption_price is None else min(self.lowest_buy_absorption_price, price)
            )
        if volume >= 200 and trades == 1 and math.isclose(bid + ask, volume):
            self.large_record_volume += volume
            self.large_record_signed_volume += signed
            self.large_record_count += 1.0
            self.large_record_max_volume = max(self.large_record_max_volume, volume)
        return {
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "price": price,
            "volume": self.volume,
            "signed_volume": self.signed_volume,
            "max_sell_imbalance_volume": self.max_sell_imbalance_volume,
            "max_buy_imbalance_volume": self.max_buy_imbalance_volume,
            "highest_sell_absorption_price": self.highest_sell_absorption_price,
            "lowest_buy_absorption_price": self.lowest_buy_absorption_price,
            "large_record_volume": self.large_record_volume,
            "large_record_signed_volume": self.large_record_signed_volume,
            "large_record_count": self.large_record_count,
            "large_record_max_volume": self.large_record_max_volume,
        }
