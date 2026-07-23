from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from alphaquest.strategy_certification import (
    REQUIRED_TEST_CATEGORIES,
    StrategyCertificationError,
    audit_strategy_certification,
    compute_implementation_sha256,
    get_strategy_certification,
    normalize_certified_event_params,
    strategy_identity_for_config,
    validate_certified_event_parameter_grid,
)
from alphaquest.strategy_modules.event import build_event_strategy
from alphaquest.strategy_modules.event.yush_orderflow_range import YushOrderflowRangeEventStrategy


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _event_config() -> dict:
    return {
        "engine_lane": "canonical_event_replay",
        "strategy_name": "yush_orderflow_range",
        "strategy": {
            "event": {"module": "yush_orderflow_range", "params": {}},
            "entry": {"module": "yush_orderflow_range", "params": {}},
            "sl": {"module": "event_aoi_structural_stop", "params": {}},
            "tp": {"module": "event_value_area_management", "params": {}},
        },
    }


def test_yush_certification_is_current_and_covers_required_categories():
    certification = get_strategy_certification(
        "yush_orderflow_range", PROJECT_ROOT, require_current=True
    )
    assert certification.certification_status == "certified"
    assert set(certification.required_test_categories) >= REQUIRED_TEST_CATEGORIES
    assert certification.implementation_sha256 == compute_implementation_sha256(
        PROJECT_ROOT, certification.source_files
    )
    assert audit_strategy_certification(certification, PROJECT_ROOT) == []
    assert {
        name for name, parameter in certification.parameters.items() if parameter.tunable
    } == {"max_aoi_width_points", "entry_offset_ticks", "stop_offset_ticks"}


def test_generic_event_registry_resolves_the_certified_factory():
    assert isinstance(build_event_strategy(_event_config()), YushOrderflowRangeEventStrategy)


def test_certified_event_grid_uses_semantic_budgets_and_requires_reviewed_defaults():
    certification = get_strategy_certification("yush_orderflow_range", PROJECT_ROOT)
    params = normalize_certified_event_params(certification, {})

    grid = validate_certified_event_parameter_grid(
        certification,
        params,
        {
            "max_aoi_width_points": [3, 4, 5, 6],
            "entry_offset_ticks": [0, 1, 2, 3, 4],
            "stop_offset_ticks": [0, 1, 2, 3, 4],
        },
    )

    assert grid == {
        "event.params.max_aoi_width_points": [3, 4, 5, 6],
        "event.params.entry_offset_ticks": [0, 1, 2, 3, 4],
        "event.params.stop_offset_ticks": [0, 1, 2, 3, 4],
    }
    with pytest.raises(StrategyCertificationError, match="reviewed default"):
        validate_certified_event_parameter_grid(
            certification,
            params,
            {
                "max_aoi_width_points": [2.0, 4.0, 6.0],
            },
        )
    with pytest.raises(StrategyCertificationError, match="fixed and cannot be tuned"):
        validate_certified_event_parameter_grid(
            certification,
            params,
            {
                "big_trade_window_ms": [50, 100, 150, 200, 250, 300, 350, 400],
            },
        )


def test_config_cannot_claim_a_different_certified_implementation():
    config = _event_config()
    certification = get_strategy_certification("yush_orderflow_range", PROJECT_ROOT)
    config["strategy_certification"] = {
        "strategy_id": certification.strategy_id,
        "implementation_version": certification.implementation_version,
        "implementation_sha256": "0" * 64,
        "manifest_sha256": certification.manifest_sha256,
    }
    with pytest.raises(StrategyCertificationError, match="stale or mismatched"):
        strategy_identity_for_config(config, PROJECT_ROOT)


def test_source_drift_fails_closed(tmp_path: Path):
    source = tmp_path / "strategy.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    certification = get_strategy_certification(
        "yush_orderflow_range", PROJECT_ROOT, require_current=False
    )
    local = replace(
        certification,
        source_files=("strategy.py",),
        implementation_sha256=compute_implementation_sha256(tmp_path, ["strategy.py"]),
    )
    assert audit_strategy_certification(local, tmp_path) == []
    source.write_text("VALUE = 2\n", encoding="utf-8")
    assert any("implementation hash has drifted" in item for item in audit_strategy_certification(local, tmp_path))
