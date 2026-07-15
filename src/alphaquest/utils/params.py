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
            if isinstance(target, list) and part.isdigit():
                target = target[int(part)]
            else:
                target = target.setdefault(part, {})
        final = path[-1]
        if isinstance(target, list) and final.isdigit():
            target[int(final)] = value
        else:
            target[final] = value
    return out
