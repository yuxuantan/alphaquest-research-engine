from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from alphaquest.research.campaign_stages import (
    DEFAULT_STAGE_ORDER,
    canonicalize_campaign_config,
)
from alphaquest.research.factory_policy import research_factory_binding
from alphaquest.research.experiment_registry import (
    AttemptReservation,
    AttemptResolution,
    AttemptStatusTransition,
    ExperimentRegistry,
)
from alphaquest.studio.followups import (
    DestinationBenchmarkSelectionV1,
    FollowUpAttemptRequestV1,
    FollowUpAttemptService,
    ExecutionTimelinePatchV1,
    MechanicParameterPatchV1,
    _apply_certification_refresh,
    _apply_dataset_refresh,
    _apply_execution_timeline,
    _apply_parameter_declaration,
    _attempt_test_data_windows,
    _config_mechanic_signature,
    _is_legacy_unreserved_preflight_only_job,
    _is_proven_pre_performance_incomplete_run,
    _performance_hash_locks,
    _rebase_relocated_project_paths,
    _require_queueable_performance_job,
    _resolve_project_owned_path,
)
from alphaquest.accounts.catalog import AccountProfileCatalog
from alphaquest.accounts.models import AccountAssessmentCostsV1
from alphaquest.authoring.models import (
    DatasetManifestV1,
    EventExecutionSourceV1,
    ResearchObjectivesV1,
)
from alphaquest.strategy_certification import (
    compute_implementation_sha256,
    get_strategy_certification,
)
from alphaquest.studio.jobs import OperationalState, SQLiteJobQueue


VARIANTS = tuple(f"v{index:02d}" for index in range(1, 6))
FIXED_NOW = datetime(2026, 7, 15, 12, 30, tzinfo=UTC)


def test_performance_hash_locks_require_core_identity_and_allow_certified_recipe(tmp_path):
    approval = tmp_path / "approval.json"
    approval.write_text("{}\n", encoding="utf-8")
    locks = _performance_hash_locks(
        {
            "approval_path": str(approval),
            "config_hash": "a" * 64,
            "input_data_hash": "b" * 64,
        }
    )

    assert locks == {
        "config_hash": "a" * 64,
        "input_data_hash": "b" * 64,
        "mechanics_approval_sha256": _sha(approval),
    }
    with pytest.raises(ValueError, match="mandatory hash locks"):
        _performance_hash_locks({"approval_path": str(approval)})


def _synthetic_current_yush_certification(
    monkeypatch: pytest.MonkeyPatch,
    project_root: Path,
):
    certification = get_strategy_certification(
        "yush_orderflow_range",
        project_root,
        require_current=False,
        include_retired=True,
    )
    current = replace(
        certification,
        implementation_sha256=compute_implementation_sha256(
            project_root,
            certification.source_files,
        ),
    )
    monkeypatch.setattr(
        "alphaquest.studio.followups.get_strategy_certification",
        lambda *args, **kwargs: current,
    )
    return current


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _object_sha(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dataset(root: Path, dataset_id: str, *, quality: str = "PASS", start: str = "2020-01-01") -> dict:
    dataset_root = root / "research/datasets" / dataset_id
    dataset_root.mkdir(parents=True)
    bars = dataset_root / "bars.csv"
    review_dates = (
        "2025-12-18",
        "2025-12-19",
        "2025-12-22",
        "2025-12-23",
        "2025-12-24",
        "2025-12-25",
        "2025-12-26",
        "2025-12-29",
        "2025-12-30",
        "2025-12-31",
    )
    bars.write_text(
        "timestamp,open,high,low,close,volume\n"
        + "".join(
            f"{session}T14:30:00+00:00,5000,5001,4999,5000.5,10\n"
            for session in review_dates
        ),
        encoding="utf-8",
    )
    document = {
        "schema": "alphaquest.dataset-manifest/v1",
        "dataset_id": dataset_id,
        "source": "csv",
        "path": str(bars.relative_to(root)),
        "symbol": "ES",
        "timeframe": "1m",
        "timezone": "America/New_York",
        "exchange_timezone": "America/New_York",
        "timestamp_semantics": "bar_open",
        "source_timestamp_semantics": "bar_open",
        "source_sha256": _sha(bars),
        "canonical_sha256": _sha(bars),
        "coverage_start": f"{start}T09:30:00-04:00",
        "coverage_end": "2025-12-31T16:00:00-05:00",
        "roll_policy": "single_contract",
        "continuous_contract": "none",
        "contract_column": None,
        "source_contract_column": None,
        "contract_count": 1,
        "roll_calendar": None,
        "roll_calendar_sha256": None,
        "transformations": [],
        "row_count": 10,
        "dropped_row_count": 0,
        "gap_count": 0,
        "duplicate_count": 0,
        "out_of_order_count": 0,
        "invalid_ohlc_count": 0,
        "cadence_violation_count": 0,
        "certified_features": [],
        "quality_verdict": quality,
        "quality_notes": [],
    }
    (dataset_root / "dataset_manifest.json").write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
    )
    return document


def _workspace(root: Path, *, rescue_allowed: bool = False) -> Path:
    _dataset(root, "bars_v1")
    campaign_root = root / "research/campaigns/active/demo"
    campaign_root.mkdir(parents=True)
    campaign = {
        "campaign_id": "demo",
        "title": "Governed demo",
        "governance_contract_version": 2,
        "variants": list(VARIANTS),
        "rescue_policy": {
            "allowed": rescue_allowed,
            "max_rescues_per_failed_variant": 1,
        },
    }
    (campaign_root / "campaign.yaml").write_text(yaml.safe_dump(campaign), encoding="utf-8")
    for variant in VARIANTS:
        stop_module, stop_params, target_module, target_params = {
            "v01": (
                "points_from_entry",
                {"stop_points": 2.0, "round_to_tick": True},
                "fixed_r",
                {"target_r_multiple": 1.5},
            ),
            "v02": (
                "percent_from_entry",
                {"stop_pct": 0.002, "round_to_tick": True},
                "fixed_r",
                {"target_r_multiple": 1.5},
            ),
            "v03": (
                "fixed_dollar_per_contract",
                {"dollars_per_contract": 250.0, "tick_value": 12.5, "round_to_tick": True},
                "cost_adjusted_fixed_r",
                {
                    "target_r_multiple": 1.5,
                    "tick_size": 0.25,
                    "tick_value": 12.5,
                    "commission_per_contract": 2.5,
                    "slippage_ticks": 1,
                    "round_to_tick": True,
                },
            ),
            "v04": (
                "points_from_entry",
                {"stop_points": 2.0, "round_to_tick": True},
                "cost_adjusted_fixed_r",
                {
                    "target_r_multiple": 1.5,
                    "tick_size": 0.25,
                    "tick_value": 12.5,
                    "commission_per_contract": 2.5,
                    "slippage_ticks": 1,
                    "round_to_tick": True,
                },
            ),
            "v05": (
                "fixed_dollar_per_contract",
                {"dollars_per_contract": 250.0, "tick_value": 12.5, "round_to_tick": True},
                "fixed_r",
                {"target_r_multiple": 1.5},
            ),
        }[variant]
        config = {
            "campaign_id": "demo",
            "variant_id": variant,
            "attempt_id": "original",
            "attempt_kind": "original",
            "attempt_provenance": "authored",
            "strategy_name": variant,
            "symbol": "ES",
            "dataset_id": "bars_v1",
            "timeframe": "1m",
            "research_metadata": {
                "validation_gate": {
                    "required": True,
                    "lane": "bar",
                    "data_subset": {"start_date": "2020-01-01", "end_date": "2020-01-08"},
                    "evidence_dir": str(root / f"old-validation/{variant}"),
                    "approval_path": str(root / f"old-approvals/{variant}.json"),
                }
            },
            "data": {
                "dataset_id": "bars_v1",
                "source": "csv",
                "raw_csv": "research/datasets/bars_v1/bars.csv",
                "symbol": "ES",
                "timezone": "America/New_York",
                "exchange_timezone": "America/New_York",
            },
            "strategy": {
                "entry": {
                    "module": "calendar_session_bias",
                    "params": {
                        "signal_time": "09:35:00",
                        "bar_interval_minutes": 1.0,
                        "max_trades_per_day": 1,
                        "weekday_directions": {"0": "long"},
                        "setup_mode": f"weekday_bias_{variant}",
                    },
                },
                "sl": {
                    "module": stop_module,
                    "params": stop_params,
                },
                "tp": {"module": target_module, "params": target_params},
                "flatten_time": "15:55:00",
            },
            "core": {
                "tick_size": 0.25,
                "point_value": 50.0,
                "tick_value": 12.5,
                "commission_per_contract": 2.5,
                "slippage_ticks": 1,
                "data_subset": {
                    "start_date": "2020-01-01",
                    "end_date": "2025-12-31",
                    "session_labels": ["RTH"],
                },
            },
            "core_grid": {"parameters": {}, "data_subset": {}},
            "monkey": {"data_subset": {}},
            "wfa": {"data_subset": {}},
            "campaign_tests": {
                "stage_order": list(DEFAULT_STAGE_ORDER),
                **{stage: {"enabled": True} for stage in DEFAULT_STAGE_ORDER},
            },
            "test_run_id": "run1",
        }
        path = campaign_root / "variants" / variant / "config.yaml"
        path.parent.mkdir(parents=True)
        config = canonicalize_campaign_config(config)
        config["research_metadata"]["validation_gate"]["data_subset"] = {
            "start_date": "2025-12-18",
            "end_date": "2025-12-31",
        }
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    _rewrite_source_contract(campaign_root)
    return campaign_root


def _rewrite_source_contract(campaign_root: Path) -> None:
    campaign = yaml.safe_load((campaign_root / "campaign.yaml").read_text(encoding="utf-8"))
    variants = tuple(campaign["variants"])
    signatures: dict[str, str] = {}
    for variant in variants:
        path = campaign_root / "variants" / variant / "config.yaml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        signature = _config_mechanic_signature(config)
        config.setdefault("research_metadata", {})["mechanic_signature"] = signature
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        signatures[variant] = signature
    strategy_spec = {
        "schema": "alphaquest.strategy-spec/v1",
        "campaign_id": "demo",
        "frozen": True,
        "variants": [{"variant_id": variant, "mechanic_signature": signatures[variant]} for variant in variants],
    }
    (campaign_root / "strategy_spec.yaml").write_text(
        yaml.safe_dump(strategy_spec, sort_keys=False),
        encoding="utf-8",
    )
    compiled_paths = [
        "campaign.yaml",
        "strategy_spec.yaml",
        *(f"variants/{variant}/config.yaml" for variant in variants),
    ]
    manifest = {
        "schema": "alphaquest.authoring-manifest/v1",
        "campaign_id": "demo",
        "variant_count": 5,
        "variant_mechanic_signatures": signatures,
        "compiled_document_sha256": {
            relative: _object_sha(yaml.safe_load((campaign_root / relative).read_text(encoding="utf-8")))
            for relative in compiled_paths
        },
    }
    (campaign_root / "authoring_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _service(root: Path, monkeypatch: pytest.MonkeyPatch) -> FollowUpAttemptService:
    def passed_preflight(*, config_paths, **_kwargs):
        paths = list(config_paths)
        assert len(paths) in {1, 5}
        assert all(".staging" in str(path) for path in paths)
        return {"passed": True, "failures": [], "warnings": []}

    monkeypatch.setattr("alphaquest.studio.followups.run_preflight", passed_preflight)
    monkeypatch.setattr("alphaquest.studio.followups.write_definition_manifests", lambda *_a, **_k: {})
    monkeypatch.setattr(
        "alphaquest.studio.followups.refresh_generated_indexes_if_stale",
        lambda *_a, **_k: {"refreshed": True},
    )
    tokens = iter(("aaa11111", "bbb22222", "ccc33333", "ddd44444"))
    return FollowUpAttemptService(root, now=lambda: FIXED_NOW, token=lambda: next(tokens))


def _request(kind: str, **updates) -> FollowUpAttemptRequestV1:
    values = {
        "campaign_id": "demo",
        "attempt_kind": kind,
        "parent_attempt_id": "original",
        "reason": (
            "The prior attempt is preserved unchanged; this explicit follow-up tests the stated governed "
            "reason without silently redefining the economic edge or using observed PnL to tune mechanics."
        ),
        "created_by": "researcher@example.com",
    }
    values.update(updates)
    return FollowUpAttemptRequestV1.model_validate(values)


def _research_objectives() -> ResearchObjectivesV1:
    return ResearchObjectivesV1.model_validate(
        {
            "schema": "alphaquest.research-objectives/v1",
            "development_goal": (
                "Determine whether this candidate survives every frozen research gate."
            ),
            "development_deadline": "2027-01-15",
            "evaluation_horizon_months": 24,
            "minimum_annualized_return_fraction": 0.20,
            "minimum_mar": 0.40,
            "maximum_drawdown_fraction": 0.10,
            "minimum_complete_wfa_windows": 3,
            "minimum_wfa_oos_trades": 50,
            "minimum_acceptance_oos_trades": 30,
            "monte_carlo_min_runs": 8000,
            "monte_carlo_horizon_months": 6,
            "minimum_net_profit_probability": 0.70,
            "maximum_account_breach_probability": 0.10,
            "forward_incubation_min_calendar_days": 90,
            "forward_incubation_min_trades": 30,
            "maximum_variants": 5,
            "abandonment_rules": [
                "Stop when any frozen stage gate fails; never tune after OOS results."
            ],
            "retirement_rules": [
                "Retire after a live risk breach or sustained degradation."
            ],
            "confirmed": True,
        }
    )


def _destination_benchmark(project_root: Path) -> DestinationBenchmarkSelectionV1:
    resolved = AccountProfileCatalog(project_root).resolve(
        "apex/eod_50k/funded",
        "2026-03-01",
    )
    return DestinationBenchmarkSelectionV1(
        profile_id=resolved.profile.profile_id,
        profile_version=resolved.profile.version,
        profile_sha256=resolved.sha256,
        role="primary",
        costs=AccountAssessmentCostsV1(
            currency="USD",
            evaluation_purchase_price=37.0,
            activation_fee=85.0,
            other_upfront_costs=0.0,
            observed_at=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
            source="Apex checkout observed before performance testing",
            include_as_replacement_cost=True,
        ),
        benchmark_acknowledged=True,
    )


def test_protocol_request_accepts_iso_datetime_from_studio_json() -> None:
    destination = _destination_benchmark(Path(__file__).resolve().parents[1])
    wire_destination = destination.model_dump(mode="json")
    assert isinstance(wire_destination["costs"]["observed_at"], str)

    request = FollowUpAttemptRequestV1.model_validate(
        {
            "campaign_id": "demo",
            "attempt_kind": "pre_pnl_protocol_declaration",
            "parent_attempt_id": "original",
            "target_variant_id": "v03",
            "reason": (
                "This pre-PnL declaration freezes the destination benchmark and "
                "research objectives without changing mechanics or inspecting PnL."
            ),
            "created_by": "researcher@example.com",
            "research_objectives": _research_objectives().model_dump(
                mode="json", by_alias=True
            ),
            "destination_benchmarks": [wire_destination],
            "destination_scope_acknowledged": True,
        }
    )

    observed_at = request.destination_benchmarks[0].costs.observed_at
    assert observed_at == datetime(2026, 7, 14, 12, 0, tzinfo=UTC)


def test_execution_timeline_correction_is_atomic_and_requires_certified_limit():
    config = {
        "engine_lane": "canonical_event_replay",
        "data": {"execution_data": {"rth_end": "16:00:00"}},
        "strategy": {
            "event": {"params": {"max_trades_per_day": 0}},
            "flatten_time": "11:00:00",
        },
        "core": {
            "latest_entry_time": "10:59:59",
            "flatten_time": "11:00:00",
            "max_trades_per_day": 3,
        },
        "apex_rules": {
            "latest_entry_time": "10:59:59",
            "force_flatten_time": "11:00:00",
            "latest_flat_time": "11:00:00",
        },
        "research_metadata": {
            "mechanics_review": {
                "target_exit_rationale": (
                    "The fixed target remains active until the 11:00 forced flatten."
                ),
            },
        },
    }
    timeline = ExecutionTimelinePatchV1(
        latest_entry_time="15:54:59",
        flatten_time="15:55:00",
        max_trades_per_day=0,
    )

    changes = _apply_execution_timeline(
        config,
        timeline,
        variant_id="v02",
    )

    assert len(changes) == 8
    assert config["core"]["latest_entry_time"] == "15:54:59"
    assert config["core"]["flatten_time"] == "15:55:00"
    assert config["core"]["max_trades_per_day"] == 0
    assert config["strategy"]["flatten_time"] == "15:55:00"
    assert config["apex_rules"]["force_flatten_time"] == "15:55:00"
    assert (
        config["research_metadata"]["mechanics_review"]["target_exit_rationale"]
        == "The fixed target remains active until the 15:55 forced flatten."
    )


def test_replication_is_a_new_complete_immutable_identity_and_never_edits_originals(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    originals = {path: path.read_bytes() for path in campaign_root.glob("variants/*/config.yaml")}
    service = _service(tmp_path, monkeypatch)

    first = service.create(_request("replication"))
    second = service.create(_request("replication"))

    assert first.attempt_id == "replication_20260715t123000_aaa11111"
    assert second.attempt_id == "replication_20260715t123000_bbb22222"
    assert first.attempt_id != second.attempt_id
    assert len(first.config_paths) == 5
    assert first.ledger_rows_appended == 5
    assert all(path.is_file() for path in first.config_paths)
    assert originals == {path: path.read_bytes() for path in originals}
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["immutable"] is True
    assert manifest["automatic_replay_permitted"] is False
    assert manifest["preflight"]["verdict"] == "PASS"
    for path in first.config_paths:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert cfg["attempt_id"] == first.attempt_id
        assert cfg["parent_attempt_id"] == "original"
        assert cfg["test_run_id"] == f"attempt_{first.attempt_id}"
        gate = cfg["research_metadata"]["validation_gate"]
        assert first.attempt_id in gate["evidence_dir"]
        assert first.attempt_id in gate["approval_path"]
    ledger = (tmp_path / "research_ledger.csv").read_text(encoding="utf-8")
    assert f"follow_up_attempt/{first.attempt_id}" in ledger
    assert f"follow_up_attempt/{second.attempt_id}" in ledger


def test_targeted_replication_contains_only_independent_target_variant(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)

    result = service.create(
        _request("replication", target_variant_id="v02")
    )

    assert [path.parent.name for path in result.config_paths] == ["v02"]
    assert not (result.destination / "v01").exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["target_variant_id"] == "v02"
    assert manifest["variant_order"] == ["v02"]
    config = yaml.safe_load(result.config_paths[0].read_text(encoding="utf-8"))
    assert config["variant_id"] == "v02"
    assert config["research_metadata"]["parent_variant_id"] == "v02"
    assert result.ledger_rows_appended == 1
    assert (campaign_root / "variants/v01/config.yaml").is_file()


def test_pre_pnl_protocol_declaration_preserves_legacy_mechanics_and_requires_fresh_approval(
    tmp_path,
    monkeypatch,
):
    with pytest.raises(ValueError, match="requires one primary destination benchmark"):
        _request(
            "pre_pnl_protocol_declaration",
            target_variant_id="v03",
            research_objectives=_research_objectives(),
        )

    campaign_root = _workspace(tmp_path)
    parent_path = campaign_root / "variants/v03/config.yaml"
    parent = yaml.safe_load(parent_path.read_text(encoding="utf-8"))
    parent_gate = deepcopy(parent["research_metadata"]["validation_gate"])
    service = _service(tmp_path, monkeypatch)
    repository_root = Path(__file__).resolve().parents[1]
    destination = _destination_benchmark(repository_root)
    resolved_destination = AccountProfileCatalog(repository_root).resolve(
        destination.profile_id,
        destination.profile_version,
    )
    monkeypatch.setattr(
        "alphaquest.accounts.catalog.resolve_account_profile",
        lambda *_args, **_kwargs: resolved_destination,
    )

    result = service.create(
        _request(
            "pre_pnl_protocol_declaration",
            target_variant_id="v03",
            research_objectives=_research_objectives(),
            destination_benchmarks=[destination],
            destination_scope_acknowledged=True,
        )
    )

    assert [path.parent.name for path in result.config_paths] == ["v03"]
    child = yaml.safe_load(result.config_paths[0].read_text(encoding="utf-8"))
    assert child["parent_attempt_id"] == "original"
    assert child["strategy"] == parent["strategy"]
    assert child["data"] == parent["data"]
    assert child["dataset_id"] == parent["dataset_id"]
    assert child["core_grid"]["parameters"] == parent["core_grid"]["parameters"]
    assert child["wfa"].get("parameters") == parent["wfa"].get("parameters")
    assert child["research_objectives"]["confirmed"] is True
    assert child["research_objectives_sha256"] == _object_sha(
        child["research_objectives"]
    )
    assert child["account_profile_bindings"][0]["role"] == "primary"
    benchmark = child["destination_benchmark_contract"]
    assert benchmark["scientific_validity_required"] is True
    assert benchmark["generic_objective_pass_required"] is False
    assert benchmark["approval_scope"] == "exact_primary_profile_only"
    assert benchmark["profiles"][0]["profile_id"] == "apex/eod_50k/funded"
    assert benchmark["profiles"][0]["costs"]["activation_fee"] == 85.0
    assert child["destination_benchmark_contract_sha256"] == _object_sha(
        benchmark
    )
    child_gate = child["research_metadata"]["validation_gate"]
    assert child_gate["evidence_dir"] != parent_gate["evidence_dir"]
    assert child_gate["approval_path"] != parent_gate["approval_path"]
    assert result.attempt_id in child_gate["evidence_dir"]
    assert result.attempt_id in child_gate["approval_path"]

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["research_objectives_sha256"] == child[
        "research_objectives_sha256"
    ]
    assert manifest["target_variant_id"] == "v03"
    assert manifest["destination_benchmark_contract_sha256"] == child[
        "destination_benchmark_contract_sha256"
    ]
    strategy_spec = yaml.safe_load(
        (result.destination / "strategy_spec.yaml").read_text(encoding="utf-8")
    )
    assert strategy_spec["research_objectives_sha256"] == child[
        "research_objectives_sha256"
    ]
    assert strategy_spec["destination_benchmark_contract_sha256"] == child[
        "destination_benchmark_contract_sha256"
    ]

    with pytest.raises(ValueError, match="already has a frozen research-objective"):
        service.create(
            _request(
                "pre_pnl_protocol_declaration",
                parent_attempt_id=result.attempt_id,
                target_variant_id="v03",
                research_objectives=_research_objectives(),
                destination_benchmarks=[destination],
                destination_scope_acknowledged=True,
            )
        )


def test_parameter_declaration_from_targeted_replication_remains_target_only(
    tmp_path, monkeypatch
):
    campaign_root = _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    replication = service.create(_request("replication", target_variant_id="v02"))

    def apply_grid(cfg, parameter_grid, *, project_root):
        del project_root
        canonical = {
            f"event.params.{name}": list(values)
            for name, values in parameter_grid.items()
        }
        cfg.setdefault("core_grid", {})["parameters"] = deepcopy(canonical)
        cfg.setdefault("wfa", {})["parameters"] = deepcopy(canonical)
        return []

    monkeypatch.setattr("alphaquest.studio.followups._apply_parameter_declaration", apply_grid)

    declaration = service.create(
        _request(
            "pre_pnl_parameter_declaration",
            parent_attempt_id=replication.attempt_id,
            target_variant_id="v02",
            parameter_grid={
                "max_aoi_width_points": [3.0, 4.0],
                "entry_offset_ticks": [1, 2],
                "stop_offset_ticks": [1, 2],
            },
        )
    )

    assert [path.parent.name for path in declaration.config_paths] == ["v02"]
    assert not (declaration.destination / "v01").exists()
    manifest = json.loads(declaration.manifest_path.read_text(encoding="utf-8"))
    assert manifest["variant_order"] == ["v02"]
    assert manifest["parent_attempt_id"] == replication.attempt_id
    assert (campaign_root / "variants/v01/config.yaml").is_file()


def test_only_proven_empty_stage_terminal_run_is_pre_performance(tmp_path):
    run_dir = tmp_path / "attempt_run"
    run_dir.mkdir()
    attempt_id = "replication_20260801t091334_0b854c07"
    (run_dir / "campaign_test_summary.json").write_text(
        json.dumps(
            {
                "attempt_id": attempt_id,
                "status": "incomplete",
                "halted": True,
                "stages": [],
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "studio_incomplete_attempt.json").write_text(
        json.dumps(
            {
                "attempt_id": attempt_id,
                "attempt_reserved": True,
                "operational_state": "FAILED_OPERATIONAL",
            }
        ),
        encoding="utf-8",
    )
    for name in ("effective_config.yaml", "source_config.yaml", "variant.yaml"):
        (run_dir / name).write_text("{}\n", encoding="utf-8")
    (run_dir / "limited_core_grid_test").mkdir()

    assert _is_proven_pre_performance_incomplete_run(run_dir, attempt_id) is True

    (run_dir / "limited_core_grid_test/core_grid_results.csv").write_text(
        "net_profit\n1\n", encoding="utf-8"
    )
    assert _is_proven_pre_performance_incomplete_run(run_dir, attempt_id) is False


def test_methodology_rerun_can_move_only_the_mechanics_validation_window(
    tmp_path, monkeypatch
):
    campaign_root = _workspace(tmp_path)
    stale = campaign_root / "variants/v01/config.yaml"
    stale_cfg = yaml.safe_load(stale.read_text(encoding="utf-8"))
    stale_cfg["research_metadata"]["validation_gate"]["data_subset"] = {
        "start_date": "2020-01-01",
        "end_date": "2020-01-08",
    }
    stale.write_text(yaml.safe_dump(stale_cfg, sort_keys=False), encoding="utf-8")
    _rewrite_source_contract(campaign_root)
    originals = {
        path: path.read_bytes()
        for path in campaign_root.glob("variants/*/config.yaml")
    }
    service = _service(tmp_path, monkeypatch)

    result = service.create(
        _request(
            "methodology_rerun",
            mechanics_validation_window={
                "variant_id": "v01",
                "start_date": "2025-12-18",
                "end_date": "2025-12-31",
            },
        )
    )

    v01 = yaml.safe_load(
        next(path for path in result.config_paths if path.parent.name == "v01").read_text(
            encoding="utf-8"
        )
    )
    v02 = yaml.safe_load(
        next(path for path in result.config_paths if path.parent.name == "v02").read_text(
            encoding="utf-8"
        )
    )
    assert v01["research_metadata"]["validation_gate"]["data_subset"] == {
        "start_date": "2025-12-18",
        "end_date": "2025-12-31",
        "session_dates": [
            "2025-12-18",
            "2025-12-19",
            "2025-12-22",
            "2025-12-23",
            "2025-12-24",
            "2025-12-25",
            "2025-12-26",
            "2025-12-29",
            "2025-12-30",
            "2025-12-31",
        ],
    }
    assert v02["research_metadata"]["validation_gate"]["data_subset"] == {
        "start_date": "2025-12-18",
        "end_date": "2025-12-31",
    }
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["changes"] == [
        {
            "field": "data_subset",
            "new": {
                "end_date": "2025-12-31",
                "session_dates": [
                    "2025-12-18",
                    "2025-12-19",
                    "2025-12-22",
                    "2025-12-23",
                    "2025-12-24",
                    "2025-12-25",
                    "2025-12-26",
                    "2025-12-29",
                    "2025-12-30",
                    "2025-12-31",
                ],
                "start_date": "2025-12-18",
            },
            "old": {"end_date": "2020-01-08", "start_date": "2020-01-01"},
            "reviewed": True,
            "scope": "research_metadata.validation_gate",
            "variant_id": "v01",
        }
    ]
    assert originals == {path: path.read_bytes() for path in originals}


def _latest_fixture_validation_subset() -> dict[str, object]:
    return {
        "start_date": "2025-12-18",
        "end_date": "2025-12-31",
        "session_dates": [
            "2025-12-18",
            "2025-12-19",
            "2025-12-22",
            "2025-12-23",
            "2025-12-24",
            "2025-12-25",
            "2025-12-26",
            "2025-12-29",
            "2025-12-30",
            "2025-12-31",
        ],
    }


def test_methodology_rerun_can_adopt_new_policy_with_same_validation_window(
    tmp_path,
    monkeypatch,
):
    campaign_root = _workspace(tmp_path)
    parent = campaign_root / "variants/v01/config.yaml"
    parent_cfg = yaml.safe_load(parent.read_text(encoding="utf-8"))
    stale_policy = deepcopy(parent_cfg["research_policy"])
    stale_policy["version"] = "previous-policy"
    stale_policy["hash"] = "a" * 64
    parent_cfg["research_policy"] = stale_policy
    parent_cfg["campaign_tests"]["research_policy"] = deepcopy(stale_policy)
    parent_cfg["research_metadata"]["validation_gate"]["data_subset"] = (
        _latest_fixture_validation_subset()
    )
    parent.write_text(yaml.safe_dump(parent_cfg, sort_keys=False), encoding="utf-8")
    _rewrite_source_contract(campaign_root)
    service = _service(tmp_path, monkeypatch)

    result = service.create(
        _request(
            "methodology_rerun",
            mechanics_validation_window={
                "variant_id": "v01",
                "start_date": "2025-12-18",
                "end_date": "2025-12-31",
            },
        )
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    policy_changes = [
        item for item in manifest["changes"] if item["field"] == "research_policy"
    ]
    assert [item["variant_id"] for item in policy_changes] == ["v01"]
    assert not any(item["field"] == "data_subset" for item in manifest["changes"])


def test_methodology_rerun_rejects_complete_noop(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    parent = campaign_root / "variants/v01/config.yaml"
    parent_cfg = yaml.safe_load(parent.read_text(encoding="utf-8"))
    parent_cfg["research_metadata"]["validation_gate"]["data_subset"] = (
        _latest_fixture_validation_subset()
    )
    parent.write_text(yaml.safe_dump(parent_cfg, sort_keys=False), encoding="utf-8")
    _rewrite_source_contract(campaign_root)
    service = _service(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="must adopt a different repository policy"):
        service.create(
            _request(
                "methodology_rerun",
                mechanics_validation_window={
                    "variant_id": "v01",
                    "start_date": "2025-12-18",
                    "end_date": "2025-12-31",
                },
            )
        )


def test_relocated_project_paths_are_resolved_and_made_portable(tmp_path: Path) -> None:
    current = tmp_path / "data/raw/ES/sierra-es-trades"
    current.mkdir(parents=True)
    recorded = Path("/former/workspace/alphaquest-research-engine/data/raw/ES/sierra-es-trades")
    cfg = {"data": {"execution_data": {"raw_dir": str(recorded)}}}

    assert _resolve_project_owned_path(recorded, tmp_path) == current
    changes = _rebase_relocated_project_paths(
        cfg,
        variant_id="v03",
        project_root=tmp_path,
    )

    assert cfg["data"]["execution_data"]["raw_dir"] == (
        "data/raw/ES/sierra-es-trades"
    )
    assert changes == [
        {
            "variant_id": "v03",
            "scope": "operational_storage",
            "field": "data.execution_data.raw_dir",
            "old": str(recorded),
            "new": "data/raw/ES/sierra-es-trades",
            "reviewed": True,
        }
    ]


def test_relocated_event_path_rebinds_v2_research_factory(tmp_path: Path) -> None:
    current = tmp_path / "data/raw/ES/sierra-es-trades"
    current.mkdir(parents=True)
    recorded = Path(
        "/former/workspace/alphaquest-research-engine/data/raw/ES/sierra-es-trades"
    )
    objectives = _research_objectives().model_dump(mode="json", by_alias=True)
    data = {
        "dataset_id": "events_v1",
        "canonical_sha256": "1" * 64,
        "source_sha256": "2" * 64,
        "coverage_start": "2020-01-01T00:00:00+00:00",
        "coverage_end": "2025-12-31T00:00:00+00:00",
        "execution_data": {
            "source": "sierra_scid_records",
            "raw_dir": str(recorded),
            "raw_manifest_sha256": "3" * 64,
        },
    }
    cfg = {
        "dataset_id": "events_v1",
        "data": data,
        "research_objectives": objectives,
        "research_factory": research_factory_binding(objectives, dataset=data),
    }
    old_contract = cfg["research_factory"]["dataset"][
        "event_execution_contract_sha256"
    ]

    changes = _rebase_relocated_project_paths(
        cfg,
        variant_id="v04",
        project_root=tmp_path,
    )

    assert cfg["data"]["execution_data"]["raw_dir"] == (
        "data/raw/ES/sierra-es-trades"
    )
    assert cfg["research_factory"] == research_factory_binding(
        objectives,
        dataset=cfg["data"],
    )
    assert (
        cfg["research_factory"]["dataset"]["event_execution_contract_sha256"]
        != old_contract
    )
    assert changes[-1]["scope"] == "research_factory"
    assert changes[-1]["change_kind"] == "operational_path_rebind"


def test_methodology_rerun_revalidates_only_the_selected_variant(
    tmp_path,
    monkeypatch,
):
    campaign_root = _workspace(tmp_path)
    stale = campaign_root / "variants/v02/config.yaml"
    stale_cfg = yaml.safe_load(stale.read_text(encoding="utf-8"))
    stale_cfg["research_metadata"]["validation_gate"]["data_subset"] = {
        "start_date": "2020-01-01",
        "end_date": "2020-01-08",
    }
    stale.write_text(yaml.safe_dump(stale_cfg, sort_keys=False), encoding="utf-8")
    _rewrite_source_contract(campaign_root)
    service = _service(tmp_path, monkeypatch)
    validated: list[str] = []

    def validate_selected(cfg, _dataset_manifest):
        variant = str(cfg["variant_id"])
        validated.append(variant)
        if variant != "v02":
            raise AssertionError("immutable sibling certification must not block a targeted window change")

    monkeypatch.setattr(service, "_validate_certified_mechanics", validate_selected)

    service.create(
        _request(
            "methodology_rerun",
            mechanics_validation_window={
                "variant_id": "v02",
                "start_date": "2025-12-18",
                "end_date": "2025-12-31",
            },
        )
    )

    assert validated == ["v02"]


def test_methodology_rerun_can_refresh_certification_with_the_fixed_window(
    tmp_path,
    monkeypatch,
):
    campaign_root = _workspace(tmp_path)
    stale = campaign_root / "variants/v01/config.yaml"
    stale_cfg = yaml.safe_load(stale.read_text(encoding="utf-8"))
    stale_cfg["research_metadata"]["validation_gate"]["data_subset"] = {
        "start_date": "2020-01-01",
        "end_date": "2020-01-08",
    }
    stale.write_text(yaml.safe_dump(stale_cfg, sort_keys=False), encoding="utf-8")
    _rewrite_source_contract(campaign_root)
    service = _service(tmp_path, monkeypatch)

    def refresh(cfg, *, variant_id, project_root, replacement_strategy_id=None):
        assert variant_id == "v01"
        assert project_root == tmp_path.resolve()
        assert replacement_strategy_id is None
        cfg["certification_refresh_test"] = True
        return [
            {
                "variant_id": variant_id,
                "scope": "strategy_certification",
                "field": "implementation_identity",
                "old": "old",
                "new": "current",
                "reviewed": True,
            }
        ]

    monkeypatch.setattr(
        "alphaquest.studio.followups._apply_certification_refresh",
        refresh,
    )

    result = service.create(
        _request(
            "methodology_rerun",
            refresh_certification=True,
            mechanics_validation_window={
                "variant_id": "v01",
                "start_date": "2025-12-18",
                "end_date": "2025-12-31",
            },
        )
    )

    v01 = yaml.safe_load(
        next(path for path in result.config_paths if path.parent.name == "v01").read_text(
            encoding="utf-8"
        )
    )
    assert v01["certification_refresh_test"] is True
    assert v01["research_metadata"]["validation_gate"]["session_count"] == 10


def test_methodology_rerun_rejects_unbounded_or_out_of_coverage_window(
    tmp_path, monkeypatch
):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="cannot exceed 60"):
        _request(
            "methodology_rerun",
            mechanics_validation_window={
                "variant_id": "v01",
                "start_date": "2025-01-01",
                "end_date": "2025-05-29",
            },
        )
    with pytest.raises(ValueError, match="inside governed dataset coverage"):
        service.create(
            _request(
                "methodology_rerun",
                mechanics_validation_window={
                    "variant_id": "v01",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-08",
                },
            )
        )


def test_attempt_listing_can_skip_expensive_dataset_bindings(tmp_path, monkeypatch):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    monkeypatch.setattr(
        service,
        "_attempt_dataset_bindings",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("dataset bindings should not be loaded")
        ),
    )

    attempts = service.list_attempts("demo", include_dataset_bindings=False)

    assert [item["attempt_id"] for item in attempts] == ["original"]
    assert "dataset_bindings" not in attempts[0]


def test_failed_preflight_leaves_no_follow_up_definition(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    monkeypatch.setattr(
        "alphaquest.studio.followups.run_preflight",
        lambda **_kwargs: {"passed": False, "failures": ["ambiguous session"], "warnings": []},
    )
    service = FollowUpAttemptService(
        tmp_path,
        now=lambda: FIXED_NOW,
        token=lambda: "blocked1",
    )

    with pytest.raises(ValueError, match="ambiguous session"):
        service.create(_request("replication"))

    root = campaign_root / "follow_up_attempts"
    assert not any(path.name == "replication_20260715t123000_blocked1" for path in root.iterdir())
    assert not list(root.glob("*.staging"))


def test_ledger_failure_rolls_back_the_new_source_tree(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "alphaquest.studio.followups.append_planned_follow_up",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("ledger unavailable")),
    )

    with pytest.raises(RuntimeError, match="ledger unavailable"):
        service.create(_request("replication"))

    attempt = campaign_root / "follow_up_attempts/replication_20260715t123000_aaa11111"
    assert not attempt.exists()
    assert not (tmp_path / "research_ledger.csv").exists()


def test_v2_data_refresh_rebinds_exact_dataset_and_acceptance_calendar(tmp_path):
    campaign_root = _workspace(tmp_path)
    old_document = json.loads(
        (tmp_path / "research/datasets/bars_v1/dataset_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    refreshed = DatasetManifestV1.model_validate(
        _dataset(tmp_path, "bars_v2", start="2021-01-01")
    )
    config = yaml.safe_load(
        (campaign_root / "variants/v01/config.yaml").read_text(encoding="utf-8")
    )
    objectives = _research_objectives().model_dump(mode="json", by_alias=True)
    config["research_objectives"] = objectives
    config["research_objectives_sha256"] = _object_sha(objectives)
    config["data"]["coverage_start"] = old_document["coverage_start"]
    config["data"]["coverage_end"] = old_document["coverage_end"]
    config["data"]["source_sha256"] = old_document["source_sha256"]
    config["data"]["canonical_sha256"] = old_document["canonical_sha256"]
    config["research_factory"] = research_factory_binding(
        objectives,
        dataset=old_document,
    )

    changes = _apply_dataset_refresh(
        config,
        refreshed,
        variant_id="v01",
        project_root=tmp_path,
    )

    binding = config["research_factory"]
    assert binding["dataset"]["dataset_id"] == "bars_v2"
    assert binding["dataset"]["canonical_sha256"] == refreshed.canonical_sha256
    assert binding["acceptance_window"]["test_start"] == "2025-06-30"
    assert binding["acceptance_window"]["test_end"] == "2025-12-31"
    assert any(item["scope"] == "research_factory" for item in changes)
    assert canonicalize_campaign_config(config)["research_factory"] == binding


def test_data_refresh_requires_pass_governed_manifest_and_changes_only_declared_data(tmp_path, monkeypatch):
    _workspace(tmp_path)
    _dataset(tmp_path, "bars_v2", start="2021-01-01")
    service = _service(tmp_path, monkeypatch)

    result = service.create(_request("data_refresh", dataset_id="bars_v2"))

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["dataset_id"] == "bars_v2"
    assert len(manifest["changes"]) == 5
    for path in result.config_paths:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert cfg["dataset_id"] == "bars_v2"
        assert cfg["data"]["raw_csv"] == "research/datasets/bars_v2/bars.csv"
        assert cfg["strategy"]["entry"]["params"]["signal_time"] == "09:35:00"

    attempts = service.list_attempts("demo")
    original = next(item for item in attempts if item["attempt_id"] == "original")
    refreshed = next(item for item in attempts if item["attempt_id"] == result.attempt_id)
    assert len(original["dataset_bindings"]) == len(VARIANTS)
    assert len(refreshed["dataset_bindings"]) == len(VARIANTS)
    assert {
        (
            item["dataset_id"],
            item["source_type"],
            item["quality_verdict"],
            item["dataset_change"],
        )
        for item in original["dataset_bindings"]
    } == {("bars_v1", "csv", "PASS", "original")}
    assert {
        (
            item["dataset_id"],
            item["parent_dataset_id"],
            item["dataset_change"],
        )
        for item in refreshed["dataset_bindings"]
    } == {("bars_v2", "bars_v1", "changed")}
    assert all(
        len(str(item["input_data_hash"])) == 64
        for item in refreshed["dataset_bindings"]
    )
    assert all(
        item["coverage_start"] == "2021-01-01T09:30:00-04:00"
        for item in refreshed["dataset_bindings"]
    )
    assert all(
        len(item["test_data_windows"]) == 9
        for item in original["dataset_bindings"]
    ), [item["test_data_windows"] for item in original["dataset_bindings"]]
    for item in original["dataset_bindings"]:
        windows = {row["stage"]: row for row in item["test_data_windows"]}
        assert windows["mechanics_validation"]["planned_start"] == "2025-12-18"
        assert (
            date.fromisoformat(windows["walk_forward_analysis"]["planned_end"])
            < date.fromisoformat(windows["simulated_incubation_core"]["test_start"])
            < date.fromisoformat(windows["acceptance_oos_test"]["test_start"])
        )
        assert windows["simulated_incubation_core"]["test_end"] == "2025-06-29"
        assert windows["acceptance_oos_test"]["test_start"] == "2025-06-30"
    assert all(
        len(item["test_data_windows"]) == 9
        for item in refreshed["dataset_bindings"]
    )
    for item in refreshed["dataset_bindings"]:
        windows = {row["stage"]: row for row in item["test_data_windows"]}
        assert windows["mechanics_validation"]["planned_start"] == "2025-12-18"
        assert windows["simulated_incubation_core"]["status"] == "unavailable"
        assert windows["simulated_incubation_monkey"]["status"] == "unavailable"
        assert windows["acceptance_oos_test"]["status"] == "planned"

    _dataset(tmp_path, "bars_bad", quality="NEEDS MANUAL REVIEW", start="2022-01-01")
    with pytest.raises(ValueError, match="quality verdict PASS"):
        service.create(_request("data_refresh", dataset_id="bars_bad"))


def test_targeted_data_refresh_changes_and_revalidates_only_selected_variant(
    tmp_path,
    monkeypatch,
):
    _workspace(tmp_path)
    _dataset(tmp_path, "bars_v2", start="2021-01-01")
    service = _service(tmp_path, monkeypatch)
    validated: list[str] = []

    def validate_selected(cfg, _dataset_manifest):
        variant = str(cfg["variant_id"])
        validated.append(variant)
        if variant != "v02":
            raise AssertionError(
                "immutable sibling certification must not block a targeted data refresh"
            )

    monkeypatch.setattr(service, "_validate_certified_mechanics", validate_selected)

    result = service.create(
        _request(
            "data_refresh",
            dataset_id="bars_v2",
            target_variant_id="v02",
        )
    )

    assert validated == ["v02"]
    configs = {
        path.parent.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in result.config_paths
    }
    assert configs["v02"]["dataset_id"] == "bars_v2"
    assert all(
        config["dataset_id"] == "bars_v1"
        for variant, config in configs.items()
        if variant != "v02"
    )
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert {change["variant_id"] for change in manifest["changes"]} == {"v02"}


def test_attempt_test_windows_merge_resolved_and_actual_evidence(tmp_path):
    campaign_root = _workspace(tmp_path)
    config = yaml.safe_load(
        (campaign_root / "variants/v01/config.yaml").read_text(encoding="utf-8")
    )
    validation_dir = Path(
        config["research_metadata"]["validation_gate"]["evidence_dir"]
    )
    source_run = tmp_path / "mechanics-source"
    validation_dir.mkdir(parents=True)
    source_run.mkdir()
    (validation_dir / "metadata.json").write_text(
        json.dumps({"source_run_dir": str(source_run)}),
        encoding="utf-8",
    )
    (source_run / "metrics.json").write_text(
        json.dumps(
            {
                "data_subset": {
                    "start_date": "2020-01-01",
                    "end_date": "2020-01-08",
                }
            }
        ),
        encoding="utf-8",
    )
    (source_run / "session_audits.csv").write_text(
        "session_date,trades\n2020-01-02,1\n2020-01-07,2\n",
        encoding="utf-8",
    )

    evidence_root = tmp_path / "research/evidence/runs"
    run_root = evidence_root / "demo/v01/ES/run1"
    core_dir = run_root / "limited_core_grid_test"
    core_dir.mkdir(parents=True)
    (core_dir / "core_grid_summary.json").write_text(
        json.dumps(
            {
                "resolved_data_subset": {
                    "start_date": "2020-02-03",
                    "end_date": "2021-07-30",
                },
                "actual_data_period": {
                    "first_timestamp": "2020-02-03T09:30:00-05:00",
                    "last_timestamp": "2021-07-30T10:59:00-04:00",
                    "strategy_rows": 25000,
                },
            }
        ),
        encoding="utf-8",
    )
    wfa_dir = run_root / "walk_forward_analysis"
    wfa_dir.mkdir(parents=True)
    (wfa_dir / "wfa_results.csv").write_text(
        "test_start,test_end\n2021-01-01,2021-12-31\n2022-01-01,2022-12-30\n",
        encoding="utf-8",
    )

    windows = _attempt_test_data_windows(
        config,
        project_root=tmp_path,
        evidence_root=evidence_root,
    )
    by_stage = {row["stage"]: row for row in windows}

    assert by_stage["mechanics_validation"]["resolved_start"] == "2020-01-01"
    assert by_stage["mechanics_validation"]["actual_start"] == "2020-01-02"
    assert by_stage["mechanics_validation"]["actual_end"] == "2020-01-07"
    assert by_stage["mechanics_validation"]["actual_sessions"] == 2
    assert by_stage["limited_core_grid_test"]["resolved_start"] == "2020-02-03"
    assert by_stage["limited_core_grid_test"]["actual_rows"] == 25000
    assert by_stage["wfa_oos_monkey_test"]["actual_start"] == "2021-01-01"
    assert by_stage["wfa_oos_monkey_test"]["actual_end"] == "2022-12-30"
    assert by_stage["wfa_oos_monkey_test"]["actual_windows"] == 2


def test_event_data_refresh_replaces_bars_and_event_source_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    certification = _synthetic_current_yush_certification(monkeypatch, project_root)
    defaults = {name: parameter.default for name, parameter in certification.parameters.items()}
    event_source = EventExecutionSourceV1(
        source="sierra_scid_records",
        raw_dir="/tmp/governed-scid",
        raw_manifest="research/datasets/sierra/raw_manifest.json",
        raw_manifest_sha256="a" * 64,
        session_levels="research/datasets/sierra/session_levels.parquet",
        session_levels_sha256="b" * 64,
        quality_manifest="research/datasets/sierra/event_capabilities.csv",
        quality_manifest_sha256="c" * 64,
        concordance_report="research/datasets/sierra/concordance.json",
        concordance_report_sha256="d" * 64,
        required_capability="full_strategy_events_extrapolated",
        ineligible_session_policy="blackout",
        roll_calendar="data/reference/ES/roll.csv",
        roll_calendar_sha256="e" * 64,
        root_symbol="ES",
        rth_end="11:00:00",
    )
    manifest = DatasetManifestV1(
        dataset_id="sierra",
        source="parquet",
        path="research/datasets/sierra/bars.parquet",
        symbol="ES",
        timeframe="1m",
        timezone="UTC",
        exchange_timezone="America/New_York",
        timestamp_semantics="bar_open",
        source_timestamp_semantics="bar_open",
        source_sha256="f" * 64,
        canonical_sha256="f" * 64,
        coverage_start="2011-08-15T13:30:00+00:00",
        coverage_end="2026-05-29T14:59:00+00:00",
        roll_policy="explicit governed calendar",
        continuous_contract="explicit_roll_calendar",
        contract_column="contract_symbol",
        source_contract_column="contract_symbol",
        contract_count=60,
        roll_calendar="data/reference/ES/roll.csv",
        roll_calendar_sha256="e" * 64,
        row_count=100,
        quality_verdict="PASS",
        event_source=event_source,
    )
    cfg = {
        "campaign_id": "demo",
        "variant_id": "v01",
        "symbol": "ES",
        "timeframe": "1m",
        "dataset_id": "old",
        "engine_lane": "canonical_event_replay",
        "data": {
            "dataset_id": "old",
            "source": "parquet",
            "raw_parquet": "old.parquet",
            "execution_data": {
                "source": "databento_zip_trades",
                "archive": "old.zip",
            },
        },
        "strategy": {
            "entry": {
                "module": certification.entry_module,
                "params": {"mechanics": deepcopy(defaults)},
            },
            "event": {
                "module": certification.strategy_id,
                "params": deepcopy(defaults),
            },
        },
        "research_metadata": {"validation_gate": {}},
        "core": {},
        "core_grid": {},
        "monkey": {},
        "wfa": {},
    }

    changes = _apply_dataset_refresh(
        cfg,
        manifest,
        variant_id="v01",
        project_root=project_root,
    )

    assert cfg["dataset_id"] == "sierra"
    assert cfg["data"]["raw_parquet"] == "research/datasets/sierra/bars.parquet"
    assert cfg["data"]["execution_data"] == event_source.model_dump(
        mode="json", exclude_none=True
    )
    assert (
        cfg["strategy_certification"]["implementation_version"]
        == certification.implementation_version
    )
    assert any(item["scope"] == "data.execution_data" for item in changes)


def test_follow_up_paths_honor_configured_evidence_and_artifact_roots(tmp_path, monkeypatch):
    _workspace(tmp_path)
    config_root = tmp_path / "config"
    config_root.mkdir()
    (config_root / "storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": "research/campaigns/active",
                "archive_campaign_roots": ["research/campaigns/archive"],
                "evidence_roots": ["custom/evidence"],
                "research_artifact_root": "custom/artifacts",
                "catalog_root": "catalogs",
                "views_root": "views",
                "run_store_root": "run-store",
                "draft_root": "research/drafts",
                "dataset_root": "research/datasets",
                "handoff_root": "research/handoffs",
                "studio_runtime_root": "run-store/studio-runtime",
            }
        ),
        encoding="utf-8",
    )
    service = _service(tmp_path, monkeypatch)

    result = service.create(_request("replication"))
    cfg = yaml.safe_load(result.config_paths[0].read_text(encoding="utf-8"))
    gate = cfg["research_metadata"]["validation_gate"]

    assert gate["evidence_dir"].startswith(str(tmp_path / "custom/evidence"))
    assert gate["approval_path"].startswith(str(tmp_path / "custom/artifacts/validation_approvals"))


def test_data_refresh_daily_tsm_uses_same_latest_ten_session_review(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    for variant in VARIANTS:
        path = campaign_root / "variants" / variant / "config.yaml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        config["strategy"]["entry"] = {
            "module": "daily_time_series_momentum",
            "params": {
                "setup_mode": "close_to_close_trend",
                "rth_end": "16:00:00",
                "signal_time": "10:00:00",
                "bar_interval_minutes": 1.0,
                "lookback_sessions": 20,
                "confirmation_sessions": 1,
                "min_abs_trend_return_pct": 0.0,
                "min_trend_zscore": 0.0,
                "max_trades_per_day": 1,
                "allow_long": True,
                "allow_short": True,
            },
        }
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    _rewrite_source_contract(campaign_root)
    _dataset(tmp_path, "bars_tsm_refresh", start="2021-01-01")
    service = _service(tmp_path, monkeypatch)

    result = service.create(_request("data_refresh", dataset_id="bars_tsm_refresh"))

    for path in result.config_paths:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        subset = config["research_metadata"]["validation_gate"]["data_subset"]
        assert subset == {
            "start_date": "2025-12-18",
            "end_date": "2025-12-31",
            "session_dates": [
                "2025-12-18",
                "2025-12-19",
                "2025-12-22",
                "2025-12-23",
                "2025-12-24",
                "2025-12-25",
                "2025-12-26",
                "2025-12-29",
                "2025-12-30",
                "2025-12-31",
            ],
        }
        assert config["research_metadata"]["validation_gate"]["session_count"] == 10


def test_pre_pnl_correction_records_explicit_scalar_diff_and_is_forbidden_after_pnl(tmp_path, monkeypatch):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    patch = MechanicParameterPatchV1(
        variant_id="v01",
        component="entry",
        parameter_path="signal_time",
        value="09:40:00",
    )

    result = service.create(
        _request(
            "pre_pnl_mechanics_correction",
            target_variant_id="v01",
            mechanic_patches=[patch],
        )
    )
    cfg = yaml.safe_load(result.config_paths[0].read_text(encoding="utf-8"))
    assert cfg["strategy"]["entry"]["params"]["signal_time"] == "09:40:00"
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["preflight"]["config_count"] == 1
    assert manifest["changes"] == [
        {
            "field": "signal_time",
            "new": "09:40:00",
            "old": "09:35:00",
            "reviewed": True,
            "scope": "strategy.entry.params",
            "variant_id": "v01",
        }
    ]

    evidence = tmp_path / "research/evidence/runs/demo/v01/ES/run1"
    evidence.mkdir(parents=True)
    (evidence / "campaign_test_summary.json").write_text(
        json.dumps({"attempt_id": "original", "research_verdict": "FAIL"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="forbidden after performance evidence"):
        service.create(
            _request(
                "pre_pnl_mechanics_correction",
                target_variant_id="v01",
                mechanic_patches=[patch],
            )
        )
    with pytest.raises(ValueError, match="forbidden after performance evidence"):
        service.create(
            _request(
                "pre_pnl_protocol_declaration",
                target_variant_id="v01",
                research_objectives=_research_objectives(),
                destination_benchmarks=[
                    _destination_benchmark(Path(__file__).resolve().parents[1])
                ],
                destination_scope_acknowledged=True,
            )
        )


def test_pre_pnl_certification_refresh_is_explicit_and_mutually_exclusive():
    base = {
        "campaign_id": "demo",
        "attempt_kind": "pre_pnl_mechanics_correction",
        "parent_attempt_id": "original",
        "reason": (
            "The certified implementation changed before any performance evidence existed, so this "
            "attempt freezes the reviewed source identity and requires fresh mechanics approval."
        ),
        "created_by": "researcher@example.com",
        "target_variant_id": "v01",
    }
    request = FollowUpAttemptRequestV1.model_validate(
        {**base, "refresh_certification": True}
    )
    assert request.refresh_certification is True

    with pytest.raises(ValueError, match="exactly one"):
        FollowUpAttemptRequestV1.model_validate(
            {
                **base,
                "refresh_certification": True,
                "mechanic_patches": [
                    {
                        "variant_id": "v01",
                        "component": "entry",
                        "parameter_path": "signal_time",
                        "value": "09:40:00",
                    }
                ],
            }
        )


def test_certification_refresh_adds_new_reviewed_defaults_and_current_identity(
    monkeypatch: pytest.MonkeyPatch,
):
    project_root = Path(__file__).resolve().parents[1]
    certification = _synthetic_current_yush_certification(monkeypatch, project_root)
    defaults = {name: parameter.default for name, parameter in certification.parameters.items()}
    prior = deepcopy(defaults)
    prior.pop("decision_interval_ms")
    grid = {
        "event.params.max_aoi_width_points": [3, 4, 5, 6],
        "event.params.entry_offset_ticks": [0, 1, 2, 3, 4],
        "event.params.stop_offset_ticks": [0, 1, 2, 3, 4],
    }
    cfg = {
        "variant_id": "v01",
        "engine_lane": "canonical_event_replay",
        "strategy": {
            "entry": {
                "module": certification.entry_module,
                "params": {"mechanics": deepcopy(prior)},
            },
            "event": {"module": certification.strategy_id, "params": deepcopy(prior)},
        },
        "strategy_certification": {
            "strategy_id": certification.strategy_id,
            "implementation_version": certification.implementation_version - 1,
            "implementation_sha256": "0" * 64,
            "manifest_sha256": "1" * 64,
        },
        "core_grid": {"parameters": deepcopy(grid)},
        "wfa": {"parameters": deepcopy(grid)},
    }

    changes = _apply_certification_refresh(
        cfg,
        variant_id="v01",
        project_root=project_root,
    )

    assert cfg["strategy"]["event"]["params"] == defaults
    assert cfg["strategy"]["entry"]["params"]["mechanics"] == defaults
    assert cfg["strategy"]["entry"]["module"] == certification.entry_module
    assert cfg["strategy"]["sl"] == {
        "module": certification.stop_module,
        "params": {},
    }
    assert cfg["strategy"]["tp"] == {
        "module": certification.target_module,
        "params": {},
    }
    assert cfg["strategy_certification"] == {
        "strategy_id": certification.strategy_id,
        "implementation_version": certification.implementation_version,
        "implementation_sha256": certification.implementation_sha256,
        "manifest_sha256": certification.manifest_sha256,
    }
    assert any(change["field"] == "decision_interval_ms" for change in changes)


@pytest.mark.skip(
    reason="retired Yush successors cannot be refreshed into executable attempts"
)
def test_certification_refresh_retires_old_grid_and_applies_execution_defaults():
    project_root = Path(__file__).resolve().parents[1]
    certification = get_strategy_certification(
        "yush_adaptive_orderflow_range",
        project_root,
    )
    defaults = {
        name: parameter.default
        for name, parameter in certification.parameters.items()
    }
    prior = {
        **defaults,
        "big_trade_average_multiple": 20,
        "delta_average_multiple": 3,
        "target_mode": "midpoint",
    }
    grid = {
        "event.params.big_trade_average_multiple": [10, 15, 20, 25, 30],
        "event.params.delta_average_multiple": [2, 3, 4, 5, 6],
        "event.params.target_mode": ["midpoint", "opposite_value_edge"],
    }
    cfg = {
        "variant_id": "v02",
        "engine_lane": "canonical_event_replay",
        "strategy": {
            "entry": {
                "module": certification.entry_module,
                "params": {"mechanics": deepcopy(prior)},
            },
            "event": {
                "module": certification.strategy_id,
                "params": deepcopy(prior),
            },
        },
        "strategy_certification": {
            "strategy_id": certification.strategy_id,
            "implementation_version": certification.implementation_version - 1,
            "implementation_sha256": "0" * 64,
            "manifest_sha256": "1" * 64,
        },
        "core_grid": {"parameters": deepcopy(grid)},
        "wfa": {"parameters": deepcopy(grid)},
    }

    changes = _apply_certification_refresh(
        cfg,
        variant_id="v02",
        project_root=project_root,
    )

    assert cfg["strategy"]["event"]["params"] == defaults
    assert cfg["core_grid"]["parameters"] == {}
    assert cfg["wfa"]["parameters"] == cfg["core_grid"]["parameters"]
    assert cfg["timeframe"] == "3m"
    assert cfg["core"]["entry_start"] == "09:33:00"
    assert cfg["core"]["latest_entry_time"] == "15:30:00"
    assert cfg["core"]["flatten_time"] == "15:55:00"
    assert cfg["core"]["max_trades_per_day"] == 0
    assert cfg["core"]["daily_loss_limit"] == 1_000_000_000_000.0
    assert cfg["core"]["entry_slippage_ticks"] == 1
    assert cfg["core"]["protective_stop_slippage_ticks"] == 1
    assert cfg["core"]["target_limit_slippage_ticks"] == 0
    assert cfg["core"]["contracts"] == 2
    assert cfg["core"]["position_sizing"] == {
        "mode": "fixed_dollar_risk",
        "risk_budget": 1600.0,
        "cost_allowance_per_contract": 28.1,
        "rounding": "floor",
        "min_contracts": 2,
        "max_contracts": 2,
    }
    assert cfg["prop_rules"]["max_contracts"] == 2
    assert cfg["monte_carlo"]["position_sizing"] == {
        "mode": "fixed_contracts",
        "contracts": 2,
    }
    assert cfg["strategy"]["flatten_time"] == "15:55:00"
    assert cfg["research_metadata"]["mechanics_review"] == (
        certification.studio["mechanics_review"]
    )
    assert cfg["research_metadata"]["timeframe_rationale"] == (
        certification.studio["timeframe_rationale"]
    )
    assert (
        cfg["research_metadata"]["validation_gate"][
            "minimum_trade_samples"
        ]
        == 5
    )
    assert any(
        change["field"] == "event.params.big_trade_average_multiple"
        and change["change_kind"] == "retired_certified_grid_dimension"
        for change in changes
    )
    assert any(
        change["field"] == "position_sizing"
        and change["change_kind"] == "certified_execution_default"
        for change in changes
    )


@pytest.mark.skip(
    reason="retired Yush successors cannot be refreshed into executable attempts"
)
def test_certification_refresh_removes_parameters_retired_by_new_implementation():
    project_root = Path(__file__).resolve().parents[1]
    certification = get_strategy_certification("yush_failed_auction_reclaim", project_root)
    defaults = {name: parameter.default for name, parameter in certification.parameters.items()}
    prior = {
        **defaults,
        "delta_profile_min_abs": 50,
        "delta_bubble_threshold": 50,
        "big_trade_threshold": 100,
        "opening_range_seconds": 32,
    }
    cfg = {
        "variant_id": "v02",
        "engine_lane": "canonical_event_replay",
        "strategy": {
            "entry": {
                "module": certification.entry_module,
                "params": {"mechanics": deepcopy(prior)},
            },
            "event": {"module": certification.strategy_id, "params": deepcopy(prior)},
        },
        "strategy_certification": {
            "strategy_id": certification.strategy_id,
            "implementation_version": certification.implementation_version - 1,
            "implementation_sha256": "0" * 64,
            "manifest_sha256": "1" * 64,
        },
        "core_grid": {"parameters": {}},
        "wfa": {"parameters": {}},
    }

    changes = _apply_certification_refresh(
        cfg,
        variant_id="v02",
        project_root=project_root,
    )

    assert cfg["strategy"]["event"]["params"] == defaults
    assert cfg["strategy"]["entry"]["params"]["mechanics"] == defaults
    retired = {
        change["field"]
        for change in changes
        if change.get("change_kind") == "retired_certified_parameter"
    }
    assert retired == {
        "big_trade_threshold",
        "delta_bubble_threshold",
        "delta_profile_min_abs",
        "opening_range_seconds",
    }


@pytest.mark.skip(
    reason="retired Yush successors cannot be refreshed into executable attempts"
)
def test_certification_refresh_resets_an_incomplete_residual_grid_to_defaults():
    project_root = Path(__file__).resolve().parents[1]
    certification = get_strategy_certification(
        "yush_adaptive_orderflow_range_v3",
        project_root,
    )
    defaults = {
        name: parameter.default
        for name, parameter in certification.parameters.items()
    }
    prior = {
        **defaults,
        "footprint_grace_bars": 1,
    }
    grid = {
        "event.params.sweep_atr_fraction": [0.1, 0.2, 0.3],
        "event.params.footprint_grace_bars": [0, 1, 2],
        "event.params.maximum_stop_atr_multiple": [1.25, 1.75],
    }
    cfg = {
        "variant_id": "v03",
        "engine_lane": "canonical_event_replay",
        "strategy": {
            "entry": {
                "module": certification.entry_module,
                "params": {"mechanics": deepcopy(prior)},
            },
            "event": {
                "module": certification.strategy_id,
                "params": deepcopy(prior),
            },
        },
        "strategy_certification": {
            "strategy_id": certification.strategy_id,
            "implementation_version": certification.implementation_version - 1,
            "implementation_sha256": "0" * 64,
            "manifest_sha256": "1" * 64,
        },
        "core_grid": {"parameters": deepcopy(grid)},
        "wfa": {"parameters": deepcopy(grid)},
    }

    changes = _apply_certification_refresh(
        cfg,
        variant_id="v03",
        project_root=project_root,
    )

    assert cfg["core_grid"]["parameters"] == {}
    assert cfg["wfa"]["parameters"] == {}
    reset = {
        change["field"]
        for change in changes
        if change.get("change_kind")
        == "incomplete_inherited_grid_reset_to_defaults"
    }
    assert reset == {
        "event.params.sweep_atr_fraction",
        "event.params.maximum_stop_atr_multiple",
    }


def test_pre_pnl_event_parameter_declaration_writes_one_core_and_wfa_grid(
    monkeypatch: pytest.MonkeyPatch,
):
    project_root = Path(__file__).resolve().parents[1]
    certification = _synthetic_current_yush_certification(monkeypatch, project_root)
    defaults = {name: parameter.default for name, parameter in certification.parameters.items()}
    cfg = {
        "campaign_id": "demo",
        "variant_id": "v01",
        "engine_lane": "canonical_event_replay",
        "strategy": {
            "entry": {
                "module": certification.entry_module,
                "params": {"mechanics": deepcopy(defaults)},
            },
            "event": {"module": certification.strategy_id, "params": deepcopy(defaults)},
        },
        "core_grid": {"parameters": {}},
        "wfa": {"parameters": {}},
        "research_metadata": {"validation_gate": {"parameter_mode": "declared_defaults"}},
    }

    changes = _apply_parameter_declaration(
        cfg,
        {
            "max_aoi_width_points": [3, 4, 5, 6],
            "entry_offset_ticks": [0, 1, 2, 3, 4],
            "stop_offset_ticks": [0, 1, 2, 3, 4],
        },
        project_root=project_root,
    )

    assert cfg["core_grid"]["parameters"] == cfg["wfa"]["parameters"]
    assert list(cfg["core_grid"]["parameters"]) == [
        "event.params.max_aoi_width_points",
        "event.params.entry_offset_ticks",
        "event.params.stop_offset_ticks",
    ]
    assert (
        cfg["strategy_certification"]["implementation_version"]
        == certification.implementation_version
    )
    assert len(changes) == 3


def test_pre_pnl_correction_rejects_reserved_job_without_run_files(tmp_path, monkeypatch):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    queue = SQLiteJobQueue(service.layout.studio_runtime_root / "jobs.sqlite3")
    queue.submit(
        job_type="campaign_variant_run",
        campaign_id="demo",
        payload={
            "campaign_id": "demo",
            "variant_id": "v01",
            "attempt_id": "original",
            "config_path": str(tmp_path / "research/campaigns/active/demo/variants/v01/config.yaml"),
        },
        idempotency_key="reserved-original-v01",
        hash_locks={},
    )

    def reserve_then_crash(context, _job):
        context.reserve_attempt()
        raise RuntimeError("simulated post-reservation crash")

    failed = queue.run_once(worker_id="worker", executor=reserve_then_crash, observed_hashes={})
    assert failed is not None and failed.attempt_reserved is True
    patch = MechanicParameterPatchV1(
        variant_id="v01",
        component="sl",
        parameter_path="stop_points",
        value=2.25,
    )

    with pytest.raises(ValueError, match="forbidden after performance evidence"):
        service.create(
            _request(
                "pre_pnl_mechanics_correction",
                target_variant_id="v01",
                mechanic_patches=[patch],
            )
        )


def test_rescue_requires_campaign_authorization_parent_fail_and_maximum_one(tmp_path, monkeypatch):
    _workspace(tmp_path, rescue_allowed=True)
    evidence = tmp_path / "research/evidence/runs/demo/v01/ES/run1"
    evidence.mkdir(parents=True)
    (evidence / "campaign_test_summary.json").write_text(
        json.dumps({"attempt_id": "original", "research_verdict": "FAIL"}),
        encoding="utf-8",
    )
    service = _service(tmp_path, monkeypatch)
    patch = MechanicParameterPatchV1(
        variant_id="v01",
        component="sl",
        parameter_path="stop_points",
        value=2.25,
    )
    request = _request(
        "rescue",
        target_variant_id="v01",
        mechanic_patches=[patch],
        authorized_by="research-lead@example.com",
    )

    with pytest.raises(ValueError, match="complete, hash-valid finalized FAIL"):
        service.create(request)

    bundle_path = evidence / "reporting_v2/result_bundle_v2.json"
    bundle_path.parent.mkdir()
    bundle_path.write_text("{}\n", encoding="utf-8")
    calls = []

    def finalized_fail(path, *, config_path):
        calls.append((Path(path), Path(config_path)))
        return {
            "valid": True,
            "errors": [],
            "bundle": SimpleNamespace(
                campaign_id="demo",
                variant_id="v01",
                run_id="run1",
                verdict="FAIL",
            ),
        }

    monkeypatch.setattr("alphaquest.studio.followups.inspect_finalized_result", finalized_fail)
    result = service.create(request)
    assert result.attempt_kind == "rescue"
    assert json.loads(result.manifest_path.read_text(encoding="utf-8"))["authorized_by"]
    assert calls == [
        (
            bundle_path,
            tmp_path / "research/campaigns/active/demo/variants/v01/config.yaml",
        )
    ]
    with pytest.raises(ValueError, match="one authorized rescue"):
        service.create(request)

    blocked_root = tmp_path / "blocked"
    _workspace(blocked_root, rescue_allowed=False)
    blocked_service = _service(blocked_root, monkeypatch)
    with pytest.raises(ValueError, match="does not authorize"):
        blocked_service.create(request)


def test_mechanics_patch_recomputes_signature_and_rejects_duplicate_variant(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    entries = {
        "v01": "close_to_close_trend",
        "v02": "volatility_normalized_trend",
    }
    for variant, setup_mode in entries.items():
        path = campaign_root / "variants" / variant / "config.yaml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        config["strategy"]["entry"] = {
            "module": "daily_time_series_momentum",
            "params": {
                "setup_mode": setup_mode,
                "rth_end": "16:00:00",
                "signal_time": "10:00:00",
                "bar_interval_minutes": 1.0,
                "lookback_sessions": 20,
                "confirmation_sessions": 1,
                "min_abs_trend_return_pct": 0.0,
                "min_trend_zscore": 0.0,
                "max_trades_per_day": 1,
                "allow_long": True,
                "allow_short": True,
            },
        }
        if variant == "v02":
            config["strategy"]["sl"] = {
                "module": "points_from_entry",
                "params": {"stop_points": 2.0, "round_to_tick": True},
            }
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    _rewrite_source_contract(campaign_root)
    service = _service(tmp_path, monkeypatch)
    patch = MechanicParameterPatchV1(
        variant_id="v02",
        component="entry",
        parameter_path="setup_mode",
        value="close_to_close_trend",
    )

    with pytest.raises(ValueError, match="materially distinct.*duplicate signatures"):
        service.create(
            _request(
                "pre_pnl_mechanics_correction",
                target_variant_id="v02",
                mechanic_patches=[patch],
            )
        )
    assert not (campaign_root / "follow_up_attempts").exists()


def test_queueing_one_attempt_is_idempotent_but_different_attempts_are_distinct(tmp_path, monkeypatch):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    attempt = service.create(_request("replication"))

    def gate(_cfg, path):
        return {
            "required": True,
            "config_hash": _sha(Path(path)),
            "input_data_hash": "d" * 64,
            "errors": ["fresh approval not written"],
        }

    monkeypatch.setattr("alphaquest.studio.followups.inspect_validation_gate", gate)
    first = service.queue_mechanics_validation("demo", attempt.attempt_id)
    repeated = service.queue_mechanics_validation("demo", attempt.attempt_id)

    assert [job.job_id for job in first] == [job.job_id for job in repeated]
    assert all(job.payload["attempt_id"] == attempt.attempt_id for job in first)
    assert len({job.idempotency_key for job in first}) == 1
    assert first[0].payload["variant_id"] == "v05"


def test_failed_unreserved_mechanics_job_allows_bounded_explicit_retry(
    tmp_path,
    monkeypatch,
):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    attempt = service.create(_request("replication"))

    def gate(_cfg, path):
        return {
            "required": True,
            "config_hash": _sha(Path(path)),
            "input_data_hash": "d" * 64,
            "errors": ["fresh approval not written"],
        }

    monkeypatch.setattr("alphaquest.studio.followups.inspect_validation_gate", gate)
    first = service.queue_mechanics_validation("demo", attempt.attempt_id)[0]
    queue = SQLiteJobQueue(service.layout.studio_runtime_root / "jobs.sqlite3")
    failed = queue.run_once(
        worker_id="worker",
        executor=lambda _context, _job: (_ for _ in ()).throw(
            RuntimeError("missing operational path")
        ),
        observed_hashes=first.hash_locks,
    )
    assert failed is not None
    assert failed.job_id == first.job_id
    assert failed.state == OperationalState.FAILED_OPERATIONAL
    assert failed.attempt_reserved is False

    config_path = service.target_config_path("demo", attempt.attempt_id)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    from alphaquest.run_core import _apply_mechanics_validation_contract

    generated = deepcopy(config)
    _apply_mechanics_validation_contract(generated)
    failed_run = (
        service.layout.evidence_roots[0]
        / generated["campaign_id"]
        / generated["variant_id"]
        / generated["symbol"]
        / generated["test_run_id"]
    )
    failed_run.mkdir(parents=True)
    (failed_run / "run_manifest.json").write_text("{}\n", encoding="utf-8")

    retry = service.queue_mechanics_validation("demo", attempt.attempt_id)[0]
    repeated = service.queue_mechanics_validation("demo", attempt.attempt_id)[0]

    assert retry.job_id != failed.job_id
    assert retry.idempotency_key.endswith(":retry:1")
    assert retry.payload["retry_of_job_id"] == failed.job_id
    assert repeated.job_id == retry.job_id
    archive_root = (
        service.layout.studio_runtime_root
        / "failed-mechanics-runs"
        / failed.job_id
    )
    assert not failed_run.exists()
    assert (archive_root / failed_run.name / "run_manifest.json").is_file()
    recovery = json.loads((archive_root / "recovery.json").read_text(encoding="utf-8"))
    assert recovery["failed_job_ids"] == [failed.job_id]


def test_terminal_idempotent_performance_submission_requires_explicit_replication(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    queued = queue.submit(
        job_type="campaign_variant_run",
        campaign_id="demo",
        payload={"attempt_id": "attempt_one"},
        idempotency_key="demo:v01:attempt_one",
        hash_locks={},
    )
    _require_queueable_performance_job(queued, attempt_id="attempt_one")

    failed = queue.run_once(
        worker_id="worker",
        executor=lambda _context, _job: (_ for _ in ()).throw(RuntimeError("interrupted")),
        observed_hashes={},
    )
    assert failed is not None

    with pytest.raises(ValueError, match="Exact replication"):
        _require_queueable_performance_job(failed, attempt_id="attempt_one")


def test_reserved_zero_pnl_campaign_failure_allows_one_explicit_retry(
    tmp_path,
    monkeypatch,
):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    attempt = service.create(_request("replication"))
    config_path = service.target_config_path("demo", attempt.attempt_id)
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    approval_path = tmp_path / "research_artifacts/validation_approvals/demo/approval.json"
    approval_path.parent.mkdir(parents=True)
    approval_path.write_text('{"status":"approved_for_testing"}\n', encoding="utf-8")
    gate = {
        "status": "APPROVED_FOR_TESTING",
        "config_path": str(config_path),
        "config_hash": _sha(config_path),
        "input_data_hash": "d" * 64,
        "approval_path": str(approval_path),
        "strategy_implementation_sha256": "a" * 64,
        "strategy_certification_manifest_sha256": "b" * 64,
    }
    monkeypatch.setattr(
        "alphaquest.studio.followups.require_all_variant_mechanics_approved",
        lambda _paths: [gate],
    )

    first = service.queue_performance("demo", attempt.attempt_id)[0]
    queue = SQLiteJobQueue(service.layout.studio_runtime_root / "jobs.sqlite3")

    def reserve_then_fail(context, _job):
        context.reserve_attempt()
        raise RuntimeError("sequencing gate failed before stage one")

    failed = queue.run_once(
        worker_id="worker",
        executor=reserve_then_fail,
        observed_hashes=first.hash_locks,
    )
    assert failed is not None and failed.attempt_reserved is True

    output_dir = Path(str(first.payload["output_dir"]))
    output_dir.mkdir(parents=True)
    (output_dir / "campaign_test_summary.json").write_text(
        json.dumps(
            {
                "attempt_id": attempt.attempt_id,
                "status": "incomplete",
                "halted": True,
                "stages": [],
            }
        ),
        encoding="utf-8",
    )
    (output_dir / "studio_incomplete_attempt.json").write_text(
        json.dumps(
            {
                "attempt_id": attempt.attempt_id,
                "attempt_reserved": True,
                "operational_state": "FAILED_OPERATIONAL",
            }
        ),
        encoding="utf-8",
    )

    registry = ExperimentRegistry(
        service.layout.research_artifact_root / "governance/experiment_registry.jsonl"
    )
    registry.reserve(
        AttemptReservation(
            campaign_id="demo",
            variant_id=str(cfg["variant_id"]),
            attempt_id=attempt.attempt_id,
            kind="replication",
            economic_edge_fingerprint_sha256="1" * 64,
            research_objectives_sha256="2" * 64,
            config_sha256=gate["config_hash"],
            data_sha256=gate["input_data_hash"],
            parameter_grid_sha256="3" * 64,
            stages=("limited_core_grid_test",),
            reserved_at="2026-07-15T12:30:00+00:00",
        )
    )
    registry.transition(
        AttemptStatusTransition(
            campaign_id="demo",
            variant_id=str(cfg["variant_id"]),
            attempt_id=attempt.attempt_id,
            from_status="RESERVED",
            to_status="RUNNING",
            recorded_at="2026-07-15T12:31:00+00:00",
            reason="Runner accepted the reservation.",
        )
    )
    registry.resolve(
        AttemptResolution(
            campaign_id="demo",
            variant_id=str(cfg["variant_id"]),
            attempt_id=attempt.attempt_id,
            from_status="RUNNING",
            terminal_status="FAILED",
            recorded_at="2026-07-15T12:32:00+00:00",
            reason="Sequencing gate failed before stage one.",
            research_verdict="NEEDS MANUAL REVIEW",
        )
    )

    retry = service.queue_performance("demo", attempt.attempt_id)[0]
    repeated = service.queue_performance("demo", attempt.attempt_id)[0]

    assert retry.job_id != failed.job_id
    assert retry.idempotency_key.endswith(":retry:1")
    assert retry.payload["retry_of_job_id"] == failed.job_id
    assert repeated.job_id == retry.job_id
    assert not output_dir.exists()
    recovery_path = Path(
        str(retry.payload["pre_performance_retry"]["recovery_path"])
    )
    recovery = json.loads(recovery_path.read_text(encoding="utf-8"))
    archive = Path(str(recovery["archived_run_root"]))
    assert (archive / "campaign_test_summary.json").is_file()
    assert retry.hash_locks["pre_performance_proof_sha256"] == _sha(recovery_path)

    blocked = queue.claim_next(worker_id="worker", observed_hashes={})
    assert blocked is None
    first_submission = queue.get(retry.job_id)
    assert first_submission.state == OperationalState.BLOCKED
    assert first_submission.attempt_reserved is False

    replacement = service.queue_performance("demo", attempt.attempt_id)[0]
    repeated_replacement = service.queue_performance("demo", attempt.attempt_id)[0]

    assert replacement.job_id != retry.job_id
    assert replacement.idempotency_key.endswith(":retry:1:submission:2")
    assert replacement.payload["pre_performance_retry"] == retry.payload[
        "pre_performance_retry"
    ]
    assert repeated_replacement.job_id == replacement.job_id


def test_unreserved_legacy_campaign_preflight_is_not_a_performance_replay(tmp_path):
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite3")
    queued = queue.submit(
        job_type="campaign_variant_run",
        campaign_id="demo",
        payload={"attempt_id": "attempt_one", "variant_id": "v02"},
        idempotency_key="demo:v02:attempt_one",
        hash_locks={},
    )
    completed = queue.run_once(
        worker_id="worker",
        observed_hashes={},
        executor=lambda _context, _job: {
            "research_verdict": "NEEDS MANUAL REVIEW",
            "reason": "full staged-submission preflight failed",
            "preflight": {"passed": False, "tests_ran": False},
        },
    )

    assert completed is not None
    assert completed.job_id == queued.job_id
    assert completed.attempt_reserved is False
    assert _is_legacy_unreserved_preflight_only_job(completed) is True


def test_original_compiled_hash_drift_blocks_follow_up_before_source_writes(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    path = campaign_root / "variants/v01/config.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["strategy"]["sl"]["params"]["stop_points"] = 99.0
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    service = _service(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="immutable original compiled source hash drift"):
        service.create(_request("replication"))
    assert not (campaign_root / "follow_up_attempts").exists()
    assert not (tmp_path / "research_ledger.csv").exists()


def test_follow_up_config_hash_drift_requires_another_explicit_attempt(tmp_path, monkeypatch):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    attempt = service.create(_request("replication"))
    path = attempt.config_paths[0]
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["strategy"]["sl"]["params"]["stop_points"] = 99.0
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="immutable follow-up config hash drift"):
        service.config_paths("demo", attempt.attempt_id)


def test_historical_follow_up_keeps_its_frozen_variant_order_after_campaign_expands(
    tmp_path,
    monkeypatch,
):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    attempt = service.create(_request("replication"))
    manifest = json.loads(attempt.manifest_path.read_text(encoding="utf-8"))
    manifest["variant_order"] = ["v01"]
    manifest["config_sha256"] = {
        "v01": manifest["config_sha256"]["v01"],
    }
    attempt.manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    campaign_path = (
        tmp_path
        / "research/campaigns/active/demo/campaign.yaml"
    )
    campaign = yaml.safe_load(campaign_path.read_text(encoding="utf-8"))
    campaign["variants"] = ["v01", "v02"]
    campaign_path.write_text(
        yaml.safe_dump(campaign, sort_keys=False),
        encoding="utf-8",
    )

    paths = service.config_paths("demo", attempt.attempt_id)

    assert [path.parent.name for path in paths] == ["v01"]
