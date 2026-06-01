from __future__ import annotations


def fixed_r_target(entry_price: float, stop_price: float, direction: str, r_multiple: float) -> float:
    risk = abs(entry_price - stop_price)
    if direction == "long":
        return entry_price + risk * r_multiple
    return entry_price - risk * r_multiple


class FixedRTarget:
    name = "fixed_r"

    def __init__(self, params: dict):
        self.params = params

    def price(self, entry_price: float, stop_price: float, direction: str) -> float:
        return fixed_r_target(
            entry_price,
            stop_price,
            direction,
            float(self.params.get("target_r_multiple", 1.5)),
        )


def build_tp_module(config: dict):
    name = config.get("module", "fixed_r")
    params = config.get("params", {})
    if name == "fixed_r":
        return FixedRTarget(params)
    raise ValueError(f"Unknown TP module: {name}")
