from __future__ import annotations

from collections import defaultdict, deque
import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class OpeningDriveInventoryComboEntry:
    name = "opening_drive_inventory_combo"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "opening_drive_inventory_combo"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.opening_rank_window = int(params.get("opening_rank_window", 42))
        self.opening_rank_min_periods = int(
            params.get("opening_rank_min_periods", max(1, self.opening_rank_window // 3))
        )
        self.stop_pct = float(params.get("stop_pct", 0.004))
        self.target_r_multiple = float(params.get("target_r_multiple", 3.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 6))
        slots = params.get("slots") or _default_slots()
        if not slots:
            raise ValueError("opening_drive_inventory_combo requires at least one slot.")
        self.slots = [_parse_slot(slot) for slot in slots]
        self.slots.sort(key=lambda slot: (slot["entry_time"], slot["slot_id"]))
        self._validate()

        self._rank_history = defaultdict(lambda: deque(maxlen=self.opening_rank_window))
        self._session_date = None
        self._session_open = math.nan
        self._session_cum_pv = 0.0
        self._session_cum_volume = 0.0
        self._session_cum_delta = 0.0
        self._opening_context: dict[int, dict[str, float]] = {}
        self._rank_updates_this_session: set[tuple[str, int]] = set()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = bar.get("session_date", timestamp.date())
        self._reset_session_if_needed(session_date, bar)
        self._update_session_state(bar)

        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        self._capture_opening_context(bar, bar_close)

        due_slots = [
            slot for slot in self.slots if bar_close == _session_timestamp(timestamp, slot["entry_time"])
        ]
        if not due_slots:
            return None

        signal = None
        rank_updates: dict[tuple[str, int], float] = {}
        for slot in due_slots:
            opening = self._opening_context.get(slot["opening_window"])
            if opening is None or not _finite(opening.get("volume")):
                continue

            rank_key = (_time_label(slot["entry_time"]), slot["opening_window"])
            open_volume_rank = self._opening_volume_rank(rank_key, opening["volume"])
            rank_updates[rank_key] = opening["volume"]

            if signal is not None or trades_today >= self.max_trades_per_day:
                continue
            observed = self._observed_values(bar, slot, opening, open_volume_rank)
            if not self._matches(slot, observed):
                continue
            signal = self._build_signal(bar, timestamp, bar_close, slot, observed)

        for rank_key, opening_volume in rank_updates.items():
            self._append_rank_history_once(rank_key, opening_volume)
        return signal

    def _reset_session_if_needed(self, session_date, bar: pd.Series) -> None:
        if self._session_date == session_date:
            return
        self._session_date = session_date
        self._session_open = _float_value(bar.get("open"))
        self._session_cum_pv = 0.0
        self._session_cum_volume = 0.0
        self._session_cum_delta = 0.0
        self._opening_context = {}
        self._rank_updates_this_session = set()

    def _update_session_state(self, bar: pd.Series) -> None:
        close = _float_value(bar.get("close"))
        volume = max(_float_value(bar.get("volume"), 0.0), 0.0)
        signed_volume = _float_value(bar.get("signed_volume"), 0.0)
        if _finite(close) and _finite(volume):
            self._session_cum_pv += close * volume
            self._session_cum_volume += volume
        if _finite(signed_volume):
            self._session_cum_delta += signed_volume

    def _capture_opening_context(self, bar: pd.Series, bar_close: pd.Timestamp) -> None:
        close_time = bar_close.time()
        for window, capture_time in ((30, parse_time("10:00:00")), (60, parse_time("10:30:00"))):
            if close_time != capture_time or window in self._opening_context:
                continue
            self._opening_context[window] = {
                "return_ticks": _float_value(bar.get(f"trade_orderflow_return_ticks_{window}")),
                "imbalance": _float_value(bar.get(f"trade_orderflow_imbalance_{window}")),
                "volume": _float_value(bar.get(f"trade_orderflow_volume_{window}")),
            }

    def _opening_volume_rank(self, rank_key: tuple[str, int], opening_volume: float) -> float:
        history = [value for value in self._rank_history[rank_key] if _finite(value)]
        if len(history) < self.opening_rank_min_periods:
            return math.nan
        return float(sum(value <= opening_volume for value in history) / len(history))

    def _append_rank_history_once(self, rank_key: tuple[str, int], opening_volume: float) -> None:
        if rank_key in self._rank_updates_this_session:
            return
        self._rank_history[rank_key].append(float(opening_volume))
        self._rank_updates_this_session.add(rank_key)

    def _observed_values(self, bar: pd.Series, slot: dict, opening: dict[str, float], rank: float) -> dict:
        sign = 1.0 if slot["pressure_direction"] == "long" else -1.0
        close = _float_value(bar.get("close"))
        session_return_ticks = (
            (close - self._session_open) / self.tick_size
            if self.tick_size > 0 and _finite(close) and _finite(self._session_open)
            else math.nan
        )
        session_vwap = (
            self._session_cum_pv / self._session_cum_volume
            if self._session_cum_volume > 0
            else math.nan
        )
        price_vs_vwap_ticks = (
            (close - session_vwap) / self.tick_size
            if self.tick_size > 0 and _finite(close) and _finite(session_vwap)
            else math.nan
        )
        session_delta_ratio = (
            self._session_cum_delta / self._session_cum_volume
            if self._session_cum_volume > 0
            else math.nan
        )
        open_ret = sign * opening["return_ticks"]
        open_imb = sign * opening["imbalance"]
        signed_current_ret = sign * session_return_ticks
        signed_vwap = sign * price_vs_vwap_ticks
        signed_session_delta = sign * session_delta_ratio
        retrace_frac = (
            signed_current_ret / abs(open_ret) if _finite(open_ret) and abs(open_ret) > 0 else math.nan
        )
        return {
            "opening_return_ticks": opening["return_ticks"],
            "opening_imbalance": opening["imbalance"],
            "opening_volume": opening["volume"],
            "opening_volume_rank": rank,
            "signed_opening_return_ticks": open_ret,
            "signed_opening_imbalance": open_imb,
            "session_return_from_open_ticks": session_return_ticks,
            "signed_session_return_from_open_ticks": signed_current_ret,
            "price_vs_vwap_ticks": price_vs_vwap_ticks,
            "signed_price_vs_vwap_ticks": signed_vwap,
            "session_cum_delta_ratio": session_delta_ratio,
            "signed_session_cum_delta_ratio": signed_session_delta,
            "current_retrace_frac": retrace_frac,
        }

    def _matches(self, slot: dict, observed: dict) -> bool:
        open_ret = observed["signed_opening_return_ticks"]
        open_imb = observed["signed_opening_imbalance"]
        open_vol_rank = observed["opening_volume_rank"]
        current_ret = observed["signed_session_return_from_open_ticks"]
        vwap = observed["signed_price_vs_vwap_ticks"]
        session_delta = observed["signed_session_cum_delta_ratio"]
        retrace_frac = observed["current_retrace_frac"]
        base = (
            _finite(open_ret)
            and _finite(open_imb)
            and _finite(open_vol_rank)
            and open_vol_rank >= slot["min_open_volume_rank"]
            and open_ret >= slot["min_open_return_ticks"]
            and open_ret <= slot["max_open_return_ticks"]
            and open_imb >= slot["min_open_imbalance"]
            and open_imb <= slot["max_open_imbalance"]
        )
        if not base:
            return False
        if slot["family"] == "opening_drive_flow_continuation":
            return (
                _finite(retrace_frac)
                and _finite(session_delta)
                and retrace_frac <= slot["max_current_retrace_frac"]
                and session_delta >= slot["min_session_delta_ratio"]
            )
        if slot["family"] == "opening_drive_exhaustion_fade":
            return (
                _finite(vwap)
                and _finite(retrace_frac)
                and _finite(session_delta)
                and vwap >= slot["min_vwap_extension_ticks"]
                and retrace_frac <= slot["max_current_retrace_frac"]
                and session_delta >= slot["min_session_delta_ratio"]
            )
        if slot["family"] == "absorbed_opening_pressure_fade":
            return _finite(current_ret) and current_ret <= slot["max_current_retrace_frac"] * max(abs(open_ret), 1.0)
        if slot["family"] == "price_flow_divergence_fade":
            return _finite(session_delta) and session_delta >= slot["min_session_delta_ratio"]
        raise ValueError(f"Unknown opening-drive family: {slot['family']}.")

    def _build_signal(
        self,
        bar: pd.Series,
        timestamp: pd.Timestamp,
        bar_close: pd.Timestamp,
        slot: dict,
        observed: dict,
    ) -> Signal:
        current_close = float(bar["close"])
        flatten_label = _time_label(slot["flatten_time"])
        report_fields = {
            "setup_mode": self.setup_mode,
            "slot_id": slot["slot_id"],
            "feature_method": "opening_drive_inventory_aggregate_orderflow_combo",
            "opening_family": slot["family"],
            "opening_window": slot["opening_window"],
            "opening_pressure_direction": slot["pressure_direction"],
            "orderflow_signal_timestamp": bar_close,
            "orderflow_intended_entry_timestamp": bar_close,
            "signal_stop_pct": self.stop_pct,
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": flatten_label,
            "swept_level": current_close,
            "sweep_timestamp": timestamp,
            "sweep_high": float(bar["high"]),
            "sweep_low": float(bar["low"]),
            "reclaim_timestamp": bar_close,
            **observed,
        }
        return Signal(
            direction=slot["direction"],
            level_type=f"opening_drive_inventory_{slot['slot_id']}",
            swept_level=current_close,
            sweep_timestamp=timestamp,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar_close,
            metadata={
                "setup_mode": self.setup_mode,
                "slot_id": slot["slot_id"],
                "stop_pct": self.stop_pct,
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": flatten_label,
            },
            report_fields=report_fields,
        )

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.opening_rank_window <= 0 or self.opening_rank_min_periods <= 0:
            raise ValueError("opening rank window and min_periods must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        valid_families = {
            "opening_drive_flow_continuation",
            "opening_drive_exhaustion_fade",
            "absorbed_opening_pressure_fade",
            "price_flow_divergence_fade",
        }
        for slot in self.slots:
            if slot["family"] not in valid_families:
                raise ValueError(f"Invalid opening-drive family for slot {slot['slot_id']}: {slot['family']}.")
            if slot["pressure_direction"] not in {"long", "short"}:
                raise ValueError(f"Invalid pressure_direction for slot {slot['slot_id']}.")
            if slot["direction"] not in {"long", "short"}:
                raise ValueError(f"Invalid direction for slot {slot['slot_id']}: {slot['direction']}.")
            if slot["opening_window"] not in {30, 60}:
                raise ValueError(f"Invalid opening_window for slot {slot['slot_id']}: {slot['opening_window']}.")


def _parse_slot(slot: dict) -> dict:
    item = dict(slot or {})
    slot_id = str(item.get("slot_id", item.get("family", "slot")))
    entry_time = parse_time(item.get("entry_time", "10:15:00"))
    flatten_time = item.get("flatten_time")
    if flatten_time is None and "hold_minutes" in item:
        flatten_time = _add_minutes(entry_time, int(item["hold_minutes"]))
    return {
        "slot_id": slot_id,
        "family": str(item.get("family", "opening_drive_flow_continuation")),
        "opening_window": int(item.get("opening_window", 30)),
        "pressure_direction": str(item.get("pressure_direction", "long")).lower(),
        "direction": str(item.get("direction", "long")).lower(),
        "min_open_return_ticks": _float_param(item.get("min_open_return_ticks", 8.0)),
        "max_open_return_ticks": _float_param(item.get("max_open_return_ticks", math.inf)),
        "min_open_imbalance": _float_param(item.get("min_open_imbalance", 0.05)),
        "max_open_imbalance": _float_param(item.get("max_open_imbalance", math.inf)),
        "min_open_volume_rank": _float_param(item.get("min_open_volume_rank", 0.0)),
        "min_vwap_extension_ticks": _float_param(item.get("min_vwap_extension_ticks", 0.0)),
        "max_current_retrace_frac": _float_param(item.get("max_current_retrace_frac", 1.25)),
        "min_session_delta_ratio": _float_param(item.get("min_session_delta_ratio", -0.10)),
        "entry_time": entry_time,
        "flatten_time": parse_time(flatten_time or "10:46:00"),
    }


def _default_slots() -> list[dict]:
    return [
        {
            "slot_id": "divergence_fade_short_pressure_long_1015",
            "family": "price_flow_divergence_fade",
            "opening_window": 30,
            "pressure_direction": "short",
            "direction": "long",
            "min_open_return_ticks": 8.0,
            "max_open_return_ticks": math.inf,
            "min_open_imbalance": -math.inf,
            "max_open_imbalance": 0.02,
            "min_open_volume_rank": 0.70,
            "entry_time": "10:15:00",
            "hold_minutes": 31,
        },
        {
            "slot_id": "flow_continuation_short_1315",
            "family": "opening_drive_flow_continuation",
            "opening_window": 60,
            "pressure_direction": "short",
            "direction": "short",
            "min_open_return_ticks": 16.0,
            "min_open_imbalance": 0.05,
            "min_session_delta_ratio": -0.10,
            "entry_time": "13:15:00",
            "hold_minutes": 31,
        },
        {
            "slot_id": "flow_continuation_long_1430",
            "family": "opening_drive_flow_continuation",
            "opening_window": 60,
            "pressure_direction": "long",
            "direction": "long",
            "min_open_return_ticks": 8.0,
            "min_open_imbalance": 0.05,
            "min_session_delta_ratio": 0.0,
            "entry_time": "14:30:00",
            "hold_minutes": 61,
        },
        {
            "slot_id": "flow_continuation_long_1145",
            "family": "opening_drive_flow_continuation",
            "opening_window": 30,
            "pressure_direction": "long",
            "direction": "long",
            "min_open_return_ticks": 8.0,
            "min_open_imbalance": 0.05,
            "min_session_delta_ratio": -0.10,
            "entry_time": "11:45:00",
            "hold_minutes": 31,
        },
        {
            "slot_id": "divergence_fade_long_pressure_short_1400",
            "family": "price_flow_divergence_fade",
            "opening_window": 30,
            "pressure_direction": "long",
            "direction": "short",
            "min_open_return_ticks": 8.0,
            "max_open_imbalance": 0.02,
            "min_open_imbalance": -math.inf,
            "min_open_volume_rank": 0.50,
            "entry_time": "14:00:00",
            "hold_minutes": 16,
        },
        {
            "slot_id": "flow_continuation_short_1230",
            "family": "opening_drive_flow_continuation",
            "opening_window": 30,
            "pressure_direction": "short",
            "direction": "short",
            "min_open_return_ticks": 16.0,
            "min_open_imbalance": 0.05,
            "min_session_delta_ratio": 0.0,
            "entry_time": "12:30:00",
            "hold_minutes": 16,
        },
    ]


def _session_timestamp(timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
    return timestamp.replace(
        hour=session_time.hour,
        minute=session_time.minute,
        second=session_time.second,
        microsecond=0,
    )


def _add_minutes(session_time, minutes: int) -> str:
    ts = pd.Timestamp("2000-01-01").replace(
        hour=session_time.hour,
        minute=session_time.minute,
        second=session_time.second,
        microsecond=0,
    )
    return (ts + pd.Timedelta(minutes=minutes)).strftime("%H:%M:%S")


def _time_label(value) -> str:
    return value.strftime("%H:%M:%S")


def _float_param(value) -> float:
    if isinstance(value, str):
        value = value.strip().lower()
        if value in {"inf", "+inf", ".inf", "+.inf"}:
            return math.inf
        if value in {"-inf", "-.inf"}:
            return -math.inf
    return float(value)


def _float_value(value, default: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if _finite(out) else default


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
