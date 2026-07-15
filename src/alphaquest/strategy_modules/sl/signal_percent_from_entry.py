from __future__ import annotations

from alphaquest.strategy_modules.sl.percent_from_entry import percent_from_entry_stop


class SignalPercentFromEntryStop:
    name = "signal_percent_from_entry"

    def __init__(self, params: dict):
        self.params = params
        self.metadata_key = str(params.get("metadata_key", "stop_pct"))

    def price(self, signal, direction: str, tick_size: float, entry_price: float | None = None) -> float | None:
        if entry_price is None:
            return None
        stop_pct = self.params.get("default_stop_pct", self.params.get("stop_pct", 0.003))
        if signal is not None:
            stop_pct = getattr(signal, "metadata", {}).get(self.metadata_key, stop_pct)
        return percent_from_entry_stop(
            direction,
            float(entry_price),
            float(stop_pct),
            tick_size,
            bool(self.params.get("round_to_tick", True)),
        )
