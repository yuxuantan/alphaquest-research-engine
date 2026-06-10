from __future__ import annotations

from propstack.strategy_modules.entry.trade_orderflow_pressure import TradeOrderflowPressureEntry


class TradeOrderflowMultiPressureEntry:
    name = "trade_orderflow_multi_pressure"

    def __init__(self, params: dict):
        self.params = params
        slots = params.get("slots") or []
        if not slots:
            raise ValueError("trade_orderflow_multi_pressure requires at least one slot.")
        self.max_trades_per_day = int(params.get("max_trades_per_day", len(slots)))
        self.slots = []
        for index, slot in enumerate(slots, start=1):
            slot_params = {**params, **dict(slot or {})}
            slot_params.pop("slots", None)
            slot_params["max_trades_per_day"] = self.max_trades_per_day
            slot_params.setdefault("setup_mode", f"slot_{index}")
            slot_params["slot_id"] = str(slot.get("slot_id", slot_params["setup_mode"]))
            entry = TradeOrderflowPressureEntry(slot_params)
            self.slots.append((entry.entry_time, entry, slot_params["slot_id"]))
        self.slots.sort(key=lambda item: item[0])

    def on_bar_close(self, bar, trades_today: int = 0):
        if trades_today >= self.max_trades_per_day:
            return None
        for _, entry, slot_id in self.slots:
            signal = entry.on_bar_close(bar, trades_today=trades_today)
            if signal is None:
                continue
            signal.metadata["slot_id"] = slot_id
            signal.report_fields["slot_id"] = slot_id
            signal.report_fields["multi_slot_count"] = len(self.slots)
            return signal
        return None
