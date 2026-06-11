from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.utils.time import parse_time


class OrderflowRecentPocketComboEntry:
    name = "orderflow_recent_pocket_combo"

    def __init__(self, params: dict):
        self.params = params
        self.setup_mode = str(params.get("setup_mode", "orderflow_recent_pocket_combo"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.stop_pct = float(params.get("stop_pct", 0.004))
        self.target_r_multiple = float(params.get("target_r_multiple", 2.0))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 3))
        slots = params.get("slots") or _default_slots()
        if not slots:
            raise ValueError("orderflow_recent_pocket_combo requires at least one slot.")
        self.slots = [_parse_slot(slot) for slot in slots]
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None
        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        for slot in self.slots:
            signal_timestamp = _session_timestamp(timestamp, slot["entry_time"])
            if bar_close != signal_timestamp:
                continue
            if not bool(bar.get(slot["signal_column"], False)):
                continue
            current_close = float(bar["close"])
            flatten_label = slot["flatten_time"].strftime("%H:%M:%S")
            report_fields = {
                "setup_mode": self.setup_mode,
                "slot_id": slot["slot_id"],
                "feature_method": "recent_pocket_aggregate_orderflow_combo",
                "orderflow_signal_column": slot["signal_column"],
                "orderflow_signal_timestamp": signal_timestamp,
                "orderflow_intended_entry_timestamp": signal_timestamp,
                "signal_stop_pct": self.stop_pct,
                "signal_target_r_multiple": self.target_r_multiple,
                "signal_flatten_time": flatten_label,
                "swept_level": current_close,
                "sweep_timestamp": timestamp,
                "sweep_high": float(bar["high"]),
                "sweep_low": float(bar["low"]),
                "reclaim_timestamp": signal_timestamp,
            }
            return Signal(
                direction=slot["direction"],
                level_type=f"orderflow_recent_pocket_{slot['slot_id']}",
                swept_level=current_close,
                sweep_timestamp=timestamp,
                sweep_high=float(bar["high"]),
                sweep_low=float(bar["low"]),
                reclaim_timestamp=signal_timestamp,
                metadata={
                    "setup_mode": self.setup_mode,
                    "slot_id": slot["slot_id"],
                    "signal_column": slot["signal_column"],
                    "stop_pct": self.stop_pct,
                    "target_r_multiple": self.target_r_multiple,
                    "flatten_time": flatten_label,
                },
                report_fields=report_fields,
            )
        return None

    def _validate(self) -> None:
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        if self.stop_pct <= 0 or self.target_r_multiple <= 0:
            raise ValueError("stop_pct and target_r_multiple must be greater than 0.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        for slot in self.slots:
            if slot["direction"] not in {"long", "short"}:
                raise ValueError(f"Invalid direction for slot {slot['slot_id']}: {slot['direction']}.")
            if not slot["signal_column"]:
                raise ValueError(f"Slot {slot['slot_id']} must define signal_column.")


def _parse_slot(slot: dict) -> dict:
    item = dict(slot or {})
    slot_id = str(item.get("slot_id", item.get("signal_column", "slot")))
    return {
        "slot_id": slot_id,
        "signal_column": str(item.get("signal_column", "")),
        "entry_time": parse_time(item.get("entry_time", "11:30:00")),
        "flatten_time": parse_time(item.get("flatten_time", "13:30:00")),
        "direction": str(item.get("direction", "long")).lower(),
    }


def _default_slots() -> list[dict]:
    return [
        {
            "slot_id": "same_clock_short_1130",
            "signal_column": "of_combo_signal_sc_short_1130_loose",
            "entry_time": "11:30:00",
            "flatten_time": "13:30:00",
            "direction": "short",
        },
        {
            "slot_id": "multi_day_short_1130",
            "signal_column": "of_combo_signal_multi_short_1130",
            "entry_time": "11:30:00",
            "flatten_time": "13:30:00",
            "direction": "short",
        },
        {
            "slot_id": "late_vwap_short_1330",
            "signal_column": "of_combo_signal_late_vwap_short_1330",
            "entry_time": "13:30:00",
            "flatten_time": "14:00:00",
            "direction": "short",
        },
        {
            "slot_id": "late_flow_long_1500",
            "signal_column": "of_combo_signal_late_flow_long_1500",
            "entry_time": "15:00:00",
            "flatten_time": "15:45:00",
            "direction": "long",
        },
    ]


def _session_timestamp(timestamp: pd.Timestamp, session_time) -> pd.Timestamp:
    return timestamp.replace(
        hour=session_time.hour,
        minute=session_time.minute,
        second=session_time.second,
        microsecond=0,
    )
