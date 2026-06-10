from __future__ import annotations

from propstack.strategy_modules.tp.fixed_r import fixed_r_target


class SignalFixedRTarget:
    name = "signal_fixed_r"

    def __init__(self, params: dict):
        self.params = params
        self.metadata_key = str(params.get("metadata_key", "target_r_multiple"))

    def price(self, entry_price: float, stop_price: float, direction: str, signal=None) -> float:
        target_r = self.params.get("default_target_r_multiple", self.params.get("target_r_multiple", 1.5))
        if signal is not None:
            target_r = getattr(signal, "metadata", {}).get(self.metadata_key, target_r)
        return fixed_r_target(entry_price, stop_price, direction, float(target_r))
