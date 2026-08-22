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
    load_strategy_certifications,
    load_strategy_package_availability,
    normalize_certified_event_params,
    strategy_identity_for_config,
    validate_certified_event_parameter_grid,
)
from alphaquest.strategy_modules.event import build_event_strategy
from alphaquest.strategy_modules.event.yush_adaptive_orderflow_range_v3 import (
    AdaptiveOrderflowRangeV3EventStrategy,
    ENTRY_MODULE,
    STOP_MODULE,
    TARGET_MODULE,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_STRATEGY_IDS = frozenset({"yush_adaptive_orderflow_range_v3"})
RETIRED_STRATEGY_IDS = frozenset(
    {
        "yush_failed_auction_reclaim",
        "yush_adaptive_orderflow_range",
        "yush_orderflow_range",
    }
)


def _event_config() -> dict:
    return {
        "engine_lane": "canonical_event_replay",
        "strategy_name": "yush_adaptive_orderflow_range_v3",
        "strategy": {
            "event": {"module": "yush_adaptive_orderflow_range_v3", "params": {}},
            "entry": {"module": "yush_adaptive_orderflow_range_v3", "params": {}},
            "sl": {"module": "event_fill_time_sweep_to_entry_extreme_stop", "params": {}},
            "tp": {"module": "event_frozen_midpoint_opposite_edge_scale_out", "params": {}},
        },
    }


def test_yush_v03_certification_is_current_and_declares_required_coverage():
    certification = get_strategy_certification(
        "yush_adaptive_orderflow_range_v3", PROJECT_ROOT, require_current=True
    )
    assert certification.certification_status == "certified"
    assert set(certification.required_test_categories) >= REQUIRED_TEST_CATEGORIES
    assert {
        name for name, parameter in certification.parameters.items() if parameter.tunable
    } == {"sweep_atr_fraction", "maximum_stop_atr_multiple"}
    assert (certification.entry_module, certification.stop_module, certification.target_module) == (
        ENTRY_MODULE,
        STOP_MODULE,
        TARGET_MODULE,
    )

    actual_sha256 = compute_implementation_sha256(PROJECT_ROOT, certification.source_files)
    assert certification.implementation_sha256 == actual_sha256
    assert audit_strategy_certification(certification, PROJECT_ROOT) == []


def test_strategy_package_availability_has_exactly_one_active_yush_package():
    policy = load_strategy_package_availability(PROJECT_ROOT)

    assert policy.active_strategy_ids == ACTIVE_STRATEGY_IDS
    assert policy.retired_strategy_ids == RETIRED_STRATEGY_IDS
    assert policy.historical_evidence_policy == "preserve_read_only"


def test_retired_certifications_require_explicit_historical_inspection_opt_in():
    default_certifications = load_strategy_certifications(
        PROJECT_ROOT,
        require_current=False,
    )
    assert set(default_certifications) == ACTIVE_STRATEGY_IDS

    historical_certifications = load_strategy_certifications(
        PROJECT_ROOT,
        require_current=False,
        include_retired=True,
    )
    assert set(historical_certifications) == ACTIVE_STRATEGY_IDS | RETIRED_STRATEGY_IDS

    for strategy_id in sorted(RETIRED_STRATEGY_IDS):
        with pytest.raises(
            StrategyCertificationError,
            match="is retired and available only for historical inspection",
        ):
            get_strategy_certification(
                strategy_id,
                PROJECT_ROOT,
                require_current=False,
            )

        historical = get_strategy_certification(
            strategy_id,
            PROJECT_ROOT,
            require_current=False,
            include_retired=True,
        )
        assert historical.strategy_id == strategy_id


def test_generic_event_registry_resolves_the_certified_v03_factory():
    assert isinstance(
        build_event_strategy(_event_config()),
        AdaptiveOrderflowRangeV3EventStrategy,
    )


def test_certified_event_grid_uses_semantic_budgets_and_requires_reviewed_defaults():
    certification = get_strategy_certification(
        "yush_adaptive_orderflow_range_v3", PROJECT_ROOT, require_current=False
    )
    params = normalize_certified_event_params(certification, {})

    grid = validate_certified_event_parameter_grid(
        certification,
        params,
        {
            "sweep_atr_fraction": [0.1, 0.15, 0.2, 0.25, 0.3],
            "maximum_stop_atr_multiple": [1.25, 1.5, 1.75],
        },
    )

    assert grid == {
        "event.params.sweep_atr_fraction": [0.1, 0.15, 0.2, 0.25, 0.3],
        "event.params.maximum_stop_atr_multiple": [1.25, 1.5, 1.75],
    }
    with pytest.raises(StrategyCertificationError, match="reviewed default"):
        validate_certified_event_parameter_grid(
            certification,
            params,
            {
                "sweep_atr_fraction": [0.1, 0.15, 0.25, 0.3],
            },
        )
    with pytest.raises(StrategyCertificationError, match="fixed and cannot be tuned"):
        validate_certified_event_parameter_grid(
            certification,
            params,
            {
                "big_trade_lookback_sessions": [10, 15, 20, 25, 30, 35, 40, 45],
            },
        )


def test_config_cannot_claim_a_different_certified_implementation(
    monkeypatch: pytest.MonkeyPatch,
):
    config = _event_config()
    certification = get_strategy_certification(
        "yush_adaptive_orderflow_range_v3", PROJECT_ROOT, require_current=False
    )
    current_certification = replace(
        certification,
        implementation_sha256=compute_implementation_sha256(
            PROJECT_ROOT, certification.source_files
        ),
    )
    monkeypatch.setattr(
        "alphaquest.strategy_certification.get_strategy_certification",
        lambda *args, **kwargs: current_certification,
    )
    config["strategy_certification"] = {
        "strategy_id": current_certification.strategy_id,
        "implementation_version": current_certification.implementation_version,
        "implementation_sha256": "0" * 64,
        "manifest_sha256": current_certification.manifest_sha256,
    }
    with pytest.raises(StrategyCertificationError, match="stale or mismatched"):
        strategy_identity_for_config(config, PROJECT_ROOT)


def test_source_drift_fails_closed(tmp_path: Path):
    source = tmp_path / "strategy.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    certification = get_strategy_certification(
        "yush_adaptive_orderflow_range_v3", PROJECT_ROOT, require_current=False
    )
    local = replace(
        certification,
        source_files=("strategy.py",),
        implementation_sha256=compute_implementation_sha256(tmp_path, ["strategy.py"]),
    )
    assert audit_strategy_certification(local, tmp_path) == []
    source.write_text("VALUE = 2\n", encoding="utf-8")
    assert any("implementation hash has drifted" in item for item in audit_strategy_certification(local, tmp_path))
