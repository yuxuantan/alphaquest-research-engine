from __future__ import annotations

from propstack.strategy_modules.tp.fixed_r import FixedRTarget, fixed_r_target


TP_MODULES = {
    FixedRTarget.name: FixedRTarget,
}


def build_tp_module(config: dict):
    name = config.get("module", FixedRTarget.name)
    params = config.get("params", {})
    try:
        return TP_MODULES[name](params)
    except KeyError as exc:
        raise ValueError(f"Unknown TP module: {name}") from exc


__all__ = ["FixedRTarget", "fixed_r_target", "build_tp_module"]
