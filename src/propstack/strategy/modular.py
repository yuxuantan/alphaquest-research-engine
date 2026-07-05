from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry import Signal, build_entry_module
from propstack.strategy_modules.sl import build_sl_module
from propstack.strategy_modules.tp import build_tp_module


class ModularStrategy:
    def __init__(self, config: dict):
        self.config = _validate_strategy_config(config)
        self.name = self.config.get("strategy_name", "modular_strategy")
        self.entry = build_entry_module(self.config["entry"])
        self.tp = build_tp_module(self.config["tp"])
        self.sl = build_sl_module(self.config["sl"])

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        return self.entry.on_bar_close(bar, trades_today=trades_today)

    def on_bar_intrabar(
        self,
        bar: pd.Series,
        detail_rows: pd.DataFrame,
        trades_today: int = 0,
    ) -> Signal | None:
        handler = getattr(self.entry, "on_bar_intrabar", None)
        if handler is None:
            return None
        return handler(bar, detail_rows, trades_today=trades_today)

    def stop_price(
        self,
        signal: Signal,
        direction: str,
        tick_size: float,
        entry_price: float | None = None,
    ) -> float | None:
        return self.sl.price(signal, direction, tick_size, entry_price=entry_price)

    def target_price(
        self,
        entry_price: float,
        stop_price: float,
        direction: str,
        signal: Signal | None = None,
    ) -> float:
        return self.tp.price(entry_price, stop_price, direction, signal=signal)


def _validate_strategy_config(config: dict) -> dict:
    required = ["entry", "tp", "sl"]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(
            "Strategy config must use the modular format with entry, tp, and sl sections. "
            f"Missing: {', '.join(missing)}"
        )
    for section in required:
        if "module" not in config[section]:
            raise ValueError(f"Strategy {section} section must define a module.")
        if "params" not in config[section]:
            raise ValueError(f"Strategy {section} section must define params.")
    return config
