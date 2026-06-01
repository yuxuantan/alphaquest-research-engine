from __future__ import annotations

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.pdh_pdl_sweep_reclaim import PdhPdlSweepReclaimEntry


ENTRY_MODULES = {
    PdhPdlSweepReclaimEntry.name: PdhPdlSweepReclaimEntry,
}


def build_entry_module(config: dict):
    name = config.get("module", PdhPdlSweepReclaimEntry.name)
    params = config.get("params", {})
    try:
        return ENTRY_MODULES[name](params)
    except KeyError as exc:
        raise ValueError(f"Unknown entry module: {name}") from exc


__all__ = ["Signal", "PdhPdlSweepReclaimEntry", "build_entry_module"]
