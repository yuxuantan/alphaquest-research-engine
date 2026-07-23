from alphaquest.utils.params import apply_dotted_params
from alphaquest.strategy_certification import get_strategy_certification


def test_apply_dotted_params_updates_nested_dicts_and_slot_lists():
    cfg = {
        "strategy": {
            "entry": {
                "params": {
                    "threshold": 1,
                    "slots": [
                        {"stop_pct": 0.004, "target_r_multiple": 1.0},
                        {"stop_pct": 0.006, "target_r_multiple": 2.0},
                    ],
                }
            }
        }
    }

    out = apply_dotted_params(
        cfg,
        {
            "entry.params.threshold": 2,
            "entry.params.slots.0.stop_pct": 0.008,
            "entry.params.slots.1.target_r_multiple": 3.0,
        },
    )

    assert out["strategy"]["entry"]["params"]["threshold"] == 2
    assert out["strategy"]["entry"]["params"]["slots"][0]["stop_pct"] == 0.008
    assert out["strategy"]["entry"]["params"]["slots"][1]["target_r_multiple"] == 3.0
    assert cfg["strategy"]["entry"]["params"]["slots"][0]["stop_pct"] == 0.004


def test_apply_dotted_params_changes_the_canonical_certified_event_runtime_parameter():
    certification = get_strategy_certification("yush_orderflow_range", require_current=True)
    defaults = {name: parameter.default for name, parameter in certification.parameters.items()}
    cfg = {
        "engine_lane": "canonical_event_replay",
        "strategy_name": certification.strategy_id,
        "strategy_certification": {
            "strategy_id": certification.strategy_id,
            "implementation_version": certification.implementation_version,
            "implementation_sha256": certification.implementation_sha256,
            "manifest_sha256": certification.manifest_sha256,
        },
        "strategy": {
            "event": {"module": certification.strategy_id, "params": defaults},
        },
    }

    out = apply_dotted_params(cfg, {"event.params.max_aoi_width_points": 4.0})

    assert out["strategy"]["event"]["params"]["max_aoi_width_points"] == 4.0
    assert cfg["strategy"]["event"]["params"]["max_aoi_width_points"] == 3.0
    with __import__("pytest").raises(ValueError, match="must target strategy.event.params"):
        apply_dotted_params(cfg, {"entry.params.mechanics.max_aoi_width_points": 4.0})
