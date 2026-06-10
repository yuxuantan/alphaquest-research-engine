from propstack.utils.params import apply_dotted_params


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
