from __future__ import annotations

from copy import deepcopy


def apply_dotted_params(config: dict, params: dict, base_path: str = "strategy") -> dict:
    if str(config.get("engine_lane") or "") == "canonical_event_replay" and params:
        invalid = sorted(key for key in params if not str(key).startswith("event.params."))
        if invalid:
            raise ValueError(
                "certified event parameter selections must target strategy.event.params: "
                + ", ".join(invalid)
            )
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
    if str(out.get("engine_lane") or "") == "canonical_event_replay":
        from alphaquest.strategy_certification import (
            normalize_certified_event_params,
            strategy_identity_for_config,
        )

        certification = strategy_identity_for_config(out, require_declared_match=True)
        if certification is None:
            raise ValueError("certified event strategy identity is missing")
        strategy = out.get("strategy") if isinstance(out.get("strategy"), dict) else {}
        event = strategy.get("event") if isinstance(strategy.get("event"), dict) else {}
        event_params = event.get("params") if isinstance(event.get("params"), dict) else {}
        normalized = normalize_certified_event_params(certification, event_params)
        if normalized != event_params:
            raise ValueError("strategy.event.params must explicitly contain every certified default")
    return out
