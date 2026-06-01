from __future__ import annotations

from copy import deepcopy


def apply_dotted_params(config: dict, params: dict, base_path: str = "strategy") -> dict:
    out = deepcopy(config)
    for key, value in params.items():
        if "." in key:
            path = key.split(".")
        else:
            path = [key]
        target = out.setdefault(base_path, {})
        for part in path[:-1]:
            target = target.setdefault(part, {})
        target[path[-1]] = value
    return out
