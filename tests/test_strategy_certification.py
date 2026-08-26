from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from alphaquest.strategy_certification import (
    REQUIRED_TEST_CATEGORIES,
    StrategyCertificationError,
    StrategyPackageAccess,
    StrategyPackageLifecycle,
    apply_certified_execution_contract,
    audit_strategy_certification,
    compute_implementation_sha256,
    get_strategy_certification,
    load_strategy_certifications,
    load_strategy_package_availability,
    normalize_certified_event_params,
    require_certified_execution_contract,
    strategy_package_access_for_config,
    strategy_identity_for_config,
    validate_certified_event_parameter_grid,
)
from alphaquest.strategy_modules.event import build_event_strategy
from alphaquest.strategy_modules.event.yush_adaptive_orderflow_range_v4 import (
    AdaptiveOrderflowRangeV4EventStrategy,
    ENTRY_MODULE,
    STOP_MODULE,
    TARGET_MODULE,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_STRATEGY_IDS = frozenset({"yush_adaptive_orderflow_range_v4"})
RETIRED_STRATEGY_IDS = frozenset(
    {
        "yush_failed_auction_reclaim",
        "yush_adaptive_orderflow_range",
        "yush_orderflow_range",
    }
)
DEPRECATED_STRATEGY_IDS = frozenset({"yush_adaptive_orderflow_range_v3"})
HISTORICAL_STRATEGY_IDS = RETIRED_STRATEGY_IDS | DEPRECATED_STRATEGY_IDS


def _event_config() -> dict:
    return {
        "engine_lane": "canonical_event_replay",
        "strategy_name": "yush_adaptive_orderflow_range_v4",
        "strategy": {
            "event": {"module": "yush_adaptive_orderflow_range_v4", "params": {}},
            "entry": {"module": "yush_adaptive_orderflow_range_v4", "params": {}},
            "sl": {"module": "event_fill_time_sweep_to_entry_extreme_stop", "params": {}},
            "tp": {
                "module": "event_frozen_midpoint_two_ticks_outside_opposite_value_area_scale_out",
                "params": {},
            },
        },
    }


def test_yush_v04_certification_is_current_and_declares_required_coverage():
    certification = get_strategy_certification(
        "yush_adaptive_orderflow_range_v4", PROJECT_ROOT, require_current=True
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


def test_certified_execution_contract_applies_risk_percent_sizing_and_rejects_drift():
    certification = get_strategy_certification(
        "yush_adaptive_orderflow_range_v4",
        PROJECT_ROOT,
        require_current=False,
    )
    config = {
        "variant_id": "v04",
        "timeframe": "3m",
        "strategy": {},
        "core": {
            "data_subset": {"start_date": "2011-08-15"},
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
        },
        "core_grid": {"data_subset": {"start_date": "2011-08-15"}},
        "monkey": {"data_subset": {"start_date": "2011-08-15"}},
        "wfa": {"data_subset": {"start_date": "2011-08-15"}},
        "monte_carlo": {
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1}
        },
        "apex_rules": {},
        "prop_rules": {},
    }

    changes = apply_certified_execution_contract(config, certification)

    assert config["core"]["position_sizing"] == {
        "mode": "risk_percent_net_liq",
        "risk_pct": 0.004,
        "cost_allowance_per_contract": 2.27,
        "rounding": "floor",
        "min_contracts": 1,
    }
    assert config["monte_carlo"]["position_sizing"] == config["core"][
        "position_sizing"
    ]
    assert config["certified_execution_contract"]["manifest_sha256"] == (
        certification.manifest_sha256
    )
    assert any(change["field"] == "position_sizing" for change in changes)
    require_certified_execution_contract(config, certification)

    config.update(
        {
            "engine_lane": "canonical_event_replay",
            "strategy_name": certification.strategy_id,
            "strategy_certification": {
                "strategy_id": certification.strategy_id,
                "implementation_version": certification.implementation_version,
                "implementation_sha256": certification.implementation_sha256,
                "manifest_sha256": certification.manifest_sha256,
            },
            "research_metadata": {
                "authoring_contract": "alphaquest.campaign-draft/v1"
            },
        }
    )
    config["strategy"]["event"] = {
        "module": certification.strategy_id,
        "params": {},
    }
    assert strategy_identity_for_config(config, PROJECT_ROOT) == certification

    config["core"]["position_sizing"] = {
        "mode": "fixed_contracts",
        "contracts": 1,
    }
    with pytest.raises(
        StrategyCertificationError,
        match="core.position_sizing",
    ):
        require_certified_execution_contract(config, certification)
    with pytest.raises(
        StrategyCertificationError,
        match="core.position_sizing",
    ):
        strategy_identity_for_config(config, PROJECT_ROOT)


def test_strategy_package_availability_has_exactly_one_active_yush_package():
    policy = load_strategy_package_availability(PROJECT_ROOT)

    assert policy.active_strategy_ids == ACTIVE_STRATEGY_IDS
    assert policy.deprecated_strategy_ids == DEPRECATED_STRATEGY_IDS
    assert policy.retired_strategy_ids == RETIRED_STRATEGY_IDS
    assert policy.development_strategy_ids == frozenset()
    assert policy.quarantined_strategy_ids == frozenset()
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
    assert set(historical_certifications) == ACTIVE_STRATEGY_IDS | HISTORICAL_STRATEGY_IDS

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

    with pytest.raises(
        StrategyCertificationError,
        match="is deprecated and unavailable for new work",
    ):
        get_strategy_certification(
            "yush_adaptive_orderflow_range_v3",
            PROJECT_ROOT,
            require_current=False,
        )
    deprecated = get_strategy_certification(
        "yush_adaptive_orderflow_range_v3",
        PROJECT_ROOT,
        require_current=False,
        access=StrategyPackageAccess.HISTORICAL_REPLAY,
    )
    assert deprecated.strategy_id == "yush_adaptive_orderflow_range_v3"

    with pytest.raises(StrategyCertificationError, match="is retired"):
        get_strategy_certification(
            "yush_orderflow_range",
            PROJECT_ROOT,
            require_current=False,
            access=StrategyPackageAccess.HISTORICAL_REPLAY,
        )


def test_all_lifecycle_states_have_distinct_fail_closed_access(tmp_path):
    config_root = tmp_path / "config"
    config_root.mkdir()
    (config_root / "strategy_packages.yaml").write_text(
        """\
schema: alphaquest.strategy-package-availability/v2
policy_version: test.1
strategy_packages:
  dev:
    lifecycle: development
    lifecycle_changed_at: "2026-08-24"
    reason: Engineering only.
  live:
    lifecycle: active
    lifecycle_changed_at: "2026-08-24"
    reason: New governed work.
  old:
    lifecycle: deprecated
    lifecycle_changed_at: "2026-08-24"
    reason: Exact historical replay only.
  archive:
    lifecycle: retired
    lifecycle_changed_at: "2026-08-24"
    reason: Inspection only.
  suspect:
    lifecycle: quarantined
    lifecycle_changed_at: "2026-08-24"
    reason: Integrity review required.
historical_evidence_policy: preserve_read_only
""",
        encoding="utf-8",
    )

    policy = load_strategy_package_availability(tmp_path)

    assert policy.ids_allowed_for("new_work") == frozenset({"live"})
    assert policy.ids_allowed_for("engineering") == frozenset({"dev", "live", "old"})
    assert policy.ids_allowed_for("historical_replay") == frozenset({"live", "old"})
    assert policy.ids_allowed_for("inspection") == frozenset(
        {"dev", "live", "old", "archive", "suspect"}
    )
    assert policy.lifecycle_for("suspect") is StrategyPackageLifecycle.QUARANTINED


def test_legacy_active_retired_policy_remains_readable(tmp_path):
    config_root = tmp_path / "config"
    config_root.mkdir()
    (config_root / "strategy_packages.yaml").write_text(
        """\
schema: alphaquest.strategy-package-availability/v1
policy_version: legacy.1
active_strategy_ids: [live]
retired_strategy_ids:
  old:
    retired_at: "2026-08-01"
    reason: Historical inspection only.
historical_evidence_policy: preserve_read_only
""",
        encoding="utf-8",
    )

    policy = load_strategy_package_availability(tmp_path)

    assert policy.active_strategy_ids == frozenset({"live"})
    assert policy.retired_strategy_ids == frozenset({"old"})


def test_only_authored_exact_replication_selects_historical_replay_access():
    assert strategy_package_access_for_config(
        {"attempt_kind": "replication", "attempt_provenance": "authored"}
    ) is StrategyPackageAccess.HISTORICAL_REPLAY
    assert strategy_package_access_for_config(
        {"attempt_kind": "replication", "attempt_provenance": "developer"}
    ) is StrategyPackageAccess.NEW_WORK
    assert strategy_package_access_for_config(
        {"attempt_kind": "methodology_rerun", "attempt_provenance": "authored"}
    ) is StrategyPackageAccess.NEW_WORK


def test_deprecated_package_identity_is_available_only_to_authored_replication(
    monkeypatch: pytest.MonkeyPatch,
):
    deprecated = get_strategy_certification(
        "yush_adaptive_orderflow_range_v3",
        PROJECT_ROOT,
        require_current=False,
        access=StrategyPackageAccess.INSPECTION,
    )
    config = {
        "engine_lane": "canonical_event_replay",
        "attempt_kind": "replication",
        "attempt_provenance": "authored",
        "strategy": {"event": {"module": deprecated.strategy_id}},
        "strategy_certification": deprecated.public_record(),
    }
    monkeypatch.setattr(
        "alphaquest.strategy_certification.require_current_certification",
        lambda certification, _root: certification,
    )

    assert strategy_identity_for_config(config, PROJECT_ROOT) == deprecated
    config["attempt_kind"] = "methodology_rerun"
    with pytest.raises(StrategyCertificationError, match="is deprecated"):
        strategy_identity_for_config(config, PROJECT_ROOT)


def test_generic_event_registry_resolves_the_certified_v04_factory():
    assert isinstance(
        build_event_strategy(_event_config()),
        AdaptiveOrderflowRangeV4EventStrategy,
    )


def test_certified_event_grid_uses_semantic_budgets_and_requires_reviewed_defaults():
    certification = get_strategy_certification(
        "yush_adaptive_orderflow_range_v4", PROJECT_ROOT, require_current=False
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
        "yush_adaptive_orderflow_range_v4", PROJECT_ROOT, require_current=False
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
        "yush_adaptive_orderflow_range_v4", PROJECT_ROOT, require_current=False
    )
    local = replace(
        certification,
        source_files=("strategy.py",),
        implementation_sha256=compute_implementation_sha256(tmp_path, ["strategy.py"]),
    )
    assert audit_strategy_certification(local, tmp_path) == []
    source.write_text("VALUE = 2\n", encoding="utf-8")
    assert any("implementation hash has drifted" in item for item in audit_strategy_certification(local, tmp_path))
