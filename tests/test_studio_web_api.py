from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
import zipfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pandas as pd
import pytest
import yaml

from alphaquest.studio.api import (
    _attempt_mechanics_gate,
    _campaign_workflow_context,
    _follow_up_kind_options,
    _follow_up_parent_options,
    _job_payload,
    _mechanics_event_timeline,
    _mechanics_frozen_parameters,
    _mechanics_strategy_context,
    _mechanics_review_summaries,
    _modules,
    register_api_routes,
)
from alphaquest.studio.jobs import SQLiteJobQueue
from alphaquest.studio.data_import import DataImportSpec, DatasetImporter
from alphaquest.studio.ai import AIDraftProvenance, ResearchBriefSuggestion
from alphaquest.studio.settings import StudioSettings, save_settings
from alphaquest.studio.results import ResultBundleBuilder
from alphaquest.authoring.catalog import get_certified_module_catalog
from alphaquest.accounts.catalog import AccountProfileCatalog
from alphaquest.strategy_certification import StrategyCertificationError


LONG_RATIONALE = (
    "This predeclared explanation is intentionally substantive and distinguishes the completed-bar economic "
    "mechanism from every deterministic active, archived, and failed historical match."
)


def test_finalized_exact_attempt_result_outranks_current_mechanics_blocker() -> None:
    attempt_id = "pre_pnl_protocol_declaration_20260823t021633_94aff48a"
    workflow = _campaign_workflow_context(
        {"campaign_id": "yush_orderflow_range"},
        [
            {
                "attempt_id": attempt_id,
                "attempt_kind": "pre_pnl_protocol_declaration",
                "target_variant_id": "v03",
            }
        ],
        {
            attempt_id: {
                "all_approved": False,
                "variants": [
                    {
                        "variant_id": "v03",
                        "status": "BLOCKED",
                        "review_progress": {
                            "evidence_available": True,
                            "sampled_count": 6,
                            "unreviewed_count": 0,
                        },
                    }
                ],
            }
        },
        {attempt_id: {"v03": {"research_verdict": "FAIL"}}},
    )

    assert workflow["stage"] == "result_review"
    assert workflow["scientific_status"] == "FAIL"
    assert workflow["primary_action"]["section"] == "results"
    assert workflow["primary_action"]["label"] == (
        "Inspect the exact v03 result for this attempt"
    )


def test_finalized_current_attempt_uses_historical_approval_and_leaves_mechanics_queue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempt_id = "pre_pnl_protocol_declaration_20260823t021633_94aff48a"
    config_path = tmp_path / "campaign" / "v03" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump({"campaign_id": "yush_orderflow_range", "variant_id": "v03"}),
        encoding="utf-8",
    )
    attempts = [
        {
            "attempt_id": attempt_id,
            "attempt_kind": "pre_pnl_protocol_declaration",
            "target_variant_id": "v03",
            "created_at": "2026-08-23T02:16:33+00:00",
        }
    ]

    class FakeAttempts:
        def __init__(self, _root):
            pass

        def target_config_path(self, _campaign_id, _attempt_id):
            return config_path

        def list_attempts(self, _campaign_id, *, include_dataset_bindings=False):
            assert include_dataset_bindings is False
            return attempts

        def config_paths(self, _campaign_id, _attempt_id):
            return (config_path,)

    exact_results = {attempt_id: {"v03": {"research_verdict": "FAIL"}}}
    monkeypatch.setattr("alphaquest.studio.api.FollowUpAttemptService", FakeAttempts)
    monkeypatch.setattr("alphaquest.studio.api._attempt_results", lambda *_args: exact_results)
    monkeypatch.setattr(
        "alphaquest.validation.promotion_gate.inspect_historical_validation_approval",
        lambda _cfg, _path: {"status": "APPROVED_FOR_TESTING", "errors": []},
    )
    monkeypatch.setattr(
        "alphaquest.studio.api.list_published_campaigns",
        lambda _root: [
            {
                "campaign_id": "yush_orderflow_range",
                "title": "Yush Orderflow Range Reversal",
                "lifecycle": "active",
                "authored_lifecycle": "active",
                "studio_managed": True,
            }
        ],
    )

    gate = _attempt_mechanics_gate(tmp_path, "yush_orderflow_range", attempts)
    queue = _mechanics_review_summaries(tmp_path)

    assert gate[attempt_id]["all_approved"] is True
    assert gate[attempt_id]["variants"][0]["status"] == "APPROVED_FOR_TESTING"
    assert queue == []


@pytest.mark.parametrize(
    ("visible", "audit_errors", "expected_current", "expected_available"),
    [
        (True, [], True, True),
        (True, ["implementation hash has drifted"], False, False),
        (False, [], True, False),
    ],
)
def test_strategy_package_publication_availability_is_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    visible: bool,
    audit_errors: list[str],
    expected_current: bool,
    expected_available: bool,
) -> None:
    certification = SimpleNamespace(
        strategy_id="yush_adaptive_orderflow_range_v4",
        certification_status="certified",
        implementation_version=19,
        implementation_sha256="a" * 64,
        manifest_sha256="b" * 64,
        required_test_categories=("no_lookahead",),
        required_tests=("tests/test_yush_range_reversal_v2.py",),
        parameters={},
        studio={
            "visible": visible,
            "label": "Yush Orderflow Range Reversal",
            "description": "Stateful causal AOI and order-flow reversal strategy.",
        },
    )
    monkeypatch.setattr(
        "alphaquest.strategy_certification.load_strategy_certifications",
        lambda _root, *, require_current: (
            {"yush_adaptive_orderflow_range_v4": certification}
            if require_current is False
            else {}
        ),
    )
    monkeypatch.setattr(
        "alphaquest.strategy_certification.audit_strategy_certification",
        lambda _certification, _root: list(audit_errors),
    )

    package = next(
        item
        for item in _modules(tmp_path)
        if item.get("strategy_package") is True
    )

    assert package["name"] == "yush_adaptive_orderflow_range_v4"
    assert package["certification_current"] is expected_current
    assert package["certification_errors"] == audit_errors
    assert package["available_for_publication"] is expected_available
    assert package["strategy_label"] == "Yush Orderflow Range Reversal"
    assert package["strategy_description"] == (
        "Stateful causal AOI and order-flow reversal strategy."
    )


def test_strategy_package_loader_failure_keeps_navigation_but_exposes_no_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_loader(_root, *, require_current):
        assert require_current is False
        raise StrategyCertificationError("availability policy is missing")

    monkeypatch.setattr(
        "alphaquest.strategy_certification.load_strategy_certifications",
        unavailable_loader,
    )

    modules = _modules(tmp_path)

    assert len(modules) == len(get_certified_module_catalog().all())
    assert not any(item.get("strategy_package") for item in modules)


def test_follow_up_options_explain_each_type_and_mark_earlier_branch_points() -> None:
    kinds = _follow_up_kind_options(rescue_allowed=False)

    assert {item["value"] for item in kinds} == {
        "replication",
        "data_refresh",
        "methodology_rerun",
        "pre_pnl_mechanics_correction",
        "pre_pnl_parameter_declaration",
        "rescue",
    }
    for item in kinds:
        assert item["summary"]
        assert item["use_when"]
        assert item["do_not_use_when"]
        assert item["parent_rule"].startswith("Select")
    rescue = next(item for item in kinds if item["value"] == "rescue")
    assert rescue["available"] is False
    assert "does not authorize" in rescue["unavailable_reason"]

    parents = _follow_up_parent_options(
        [
            {
                "attempt_id": "original",
                "attempt_kind": "original",
                "parent_attempt_id": None,
                "reason": "Frozen original.",
            },
            {
                "attempt_id": "replication_1",
                "attempt_kind": "replication",
                "parent_attempt_id": "original",
                "reason": "Operational retry.",
            },
            {
                "attempt_id": "data_refresh_1",
                "attempt_kind": "data_refresh",
                "parent_attempt_id": "replication_1",
                "reason": "Corrected data.",
            },
        ]
    )
    original = next(item for item in parents if item["attempt_id"] == "original")
    latest = next(item for item in parents if item["attempt_id"] == "data_refresh_1")
    assert original["is_leaf"] is False
    assert "separate branch" in original["branch_warning"]
    assert latest["recommended"] is True
    assert latest["lineage_label"] == "Recommended current leaf"


def test_follow_up_options_disable_only_pre_pnl_types_after_performance_evidence() -> None:
    kinds = _follow_up_kind_options(
        rescue_allowed=False,
        has_performance_evidence=True,
    )
    by_kind = {item["value"]: item for item in kinds}

    for kind in ("replication", "data_refresh", "methodology_rerun"):
        assert by_kind[kind]["available"] is True
    for kind in ("pre_pnl_mechanics_correction", "pre_pnl_parameter_declaration"):
        assert by_kind[kind]["available"] is False
        assert "performance evidence" in by_kind[kind]["unavailable_reason"]
    assert by_kind["rescue"]["available"] is False


def test_job_api_exposes_durable_progress_elapsed_time_and_eta(tmp_path: Path) -> None:
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite")
    job = queue.submit(
        job_type="mechanics_validation_run",
        campaign_id="demo",
        payload={"variant_id": "v01"},
        idempotency_key="demo-progress",
        hash_locks={},
    )
    queue.claim_next(worker_id="worker-1", observed_hashes={})
    current = queue.update_progress(
        job.job_id,
        worker_id="worker-1",
        phase="event_replay",
        message="Replaying market sessions",
        percent=50.0,
        completed=5,
        total=10,
        unit="sessions",
        active_workers=2,
        expected_workers=3,
    )

    payload = _job_payload(current)

    assert payload["progress"] == 50.0
    assert payload["progress_detail"]["phase"] == "event_replay"
    assert payload["progress_detail"]["completed"] == 5
    assert payload["progress_detail"]["total"] == 10
    assert payload["progress_detail"]["elapsed_seconds"] >= 0
    assert payload["progress_detail"]["eta_seconds"] >= 0
    assert payload["progress_detail"]["active_workers"] == 2
    assert payload["progress_detail"]["expected_workers"] == 3
    assert payload["progress_detail"]["throughput_per_hour"] is not None
    assert payload["progress_detail"]["estimated_finish_at"] is not None
    assert "Only 2 of 3" in payload["progress_detail"]["parallelism_warning"]
    assert payload["heartbeat_at"] == current.heartbeat_at.isoformat()


def test_event_replay_eta_uses_intra_session_percent_instead_of_completed_sessions(tmp_path: Path) -> None:
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite")
    job = queue.submit(
        job_type="mechanics_validation_run",
        campaign_id="demo",
        payload={"variant_id": "v01"},
        idempotency_key="demo-event-progress",
        hash_locks={},
    )
    queue.claim_next(worker_id="worker-1", observed_hashes={})
    current = queue.update_progress(
        job.job_id,
        worker_id="worker-1",
        phase="event_replay",
        message="Replaying session 2/4 · 50,000/100,000 events",
        percent=41.25,
        completed=1,
        total=4,
        unit="sessions",
    )

    payload = _job_payload(current)

    assert payload["progress_detail"]["eta_seconds"] is not None
    elapsed = payload["progress_detail"]["elapsed_seconds"]
    # 41.25% is 37.5% through the 15%-85% replay phase.
    assert payload["progress_detail"]["eta_seconds"] == pytest.approx(
        elapsed * (1.0 - 0.375) / 0.375,
        abs=0.1,
    )


def _client(root: Path) -> TestClient:
    app = FastAPI()
    register_api_routes(app, root)
    return TestClient(app)


def test_browser_explicitly_recovers_finalization_without_queueing_a_rerun(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "research/campaigns/active/demo/variants/v01/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        yaml.safe_dump(
            {
                "campaign_id": "demo",
                "attempt_id": "original",
                "variant_id": "v01",
                "test_run_id": "run-1",
            }
        ),
        encoding="utf-8",
    )
    run_dir = tmp_path / "research/evidence/runs/demo/v01/ES/run-1"
    run_dir.mkdir(parents=True)
    source_job = SimpleNamespace(
        job_id="failed-job",
        payload={"output_dir": str(run_dir)},
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "alphaquest.studio.followups.FollowUpAttemptService.target_config_path",
        lambda _self, campaign_id, attempt_id: config,
    )
    monkeypatch.setattr(
        "alphaquest.studio.api._finalization_recovery_job",
        lambda *_args, **_kwargs: source_job,
    )
    monkeypatch.setattr(
        "alphaquest.studio.api._recover_experiment_finalization",
        lambda *_args, **_kwargs: {"status": "COMPLETED"},
    )

    class Recovered:
        research_verdict = "FAIL"
        result_bundle_path = run_dir / "reporting_v2/result_bundle_v2.json"

        def as_job_result(self, *, project_root):
            return {"result_bundle_path": "research/evidence/result_bundle_v2.json"}

    class Finalizer:
        def __init__(self, project_root):
            calls.append({"project_root": project_root})
            self.registry_refresher = lambda _root: {"runs": 1}

        def recover(self, **kwargs):
            calls.append(kwargs)
            return Recovered()

    monkeypatch.setattr("alphaquest.studio.api.RunFinalizer", Finalizer)

    response = _client(tmp_path).post(
        "/api/campaigns/demo/attempts/original/recover-finalization"
    )

    assert response.status_code == 200, response.text
    assert response.json()["recovered"] is True
    assert response.json()["research_verdict"] == "FAIL"
    assert calls[-1] == {
        "job_id": "failed-job",
        "config_path": config,
        "run_dir": run_dir,
    }


def test_browser_queues_hash_bound_account_assessment_with_current_costs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "research/campaigns/active/demo/variants/v01/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        yaml.safe_dump(
            {
                "campaign_id": "demo",
                "attempt_id": "original",
                "variant_id": "v01",
                "data": {"canonical_sha256": "d" * 64},
            }
        ),
        encoding="utf-8",
    )
    bundle = tmp_path / "evidence/result_bundle_v2.json"
    bundle.parent.mkdir(parents=True)
    bundle.write_text("{}\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    resolved = AccountProfileCatalog(Path(__file__).resolve().parents[1]).resolve(
        "apex/eod_50k/funded",
        "2026-03-01",
    )
    monkeypatch.setattr("alphaquest.studio.api._attempt_config", lambda *_args: config)
    monkeypatch.setattr("alphaquest.studio.api._indexed_result_entry", lambda *_args: {})
    monkeypatch.setattr(
        "alphaquest.studio.api._indexed_bundle_path",
        lambda *_args: bundle,
    )
    monkeypatch.setattr(
        "alphaquest.studio.api._present_indexed_result",
        lambda *_args, **_kwargs: {
            "finalization": {"valid": True},
            "scientific_validity_verdict": "PASS",
        },
    )
    monkeypatch.setattr(
        "alphaquest.accounts.catalog.resolve_account_profile",
        lambda *_args, **_kwargs: resolved,
    )
    monkeypatch.setattr(
        "alphaquest.studio.api.load_storage_layout",
        lambda _root: SimpleNamespace(studio_runtime_root=runtime),
    )

    response = _client(tmp_path).post(
        "/api/campaigns/demo/account-assessments",
        json={
            "attempt_id": "original",
            "variant_id": "v01",
            "profile_id": "apex/eod_50k/funded",
            "profile_version": "2026-03-01",
            "evaluation_purchase_price": 37.0,
            "activation_fee": 85.0,
            "other_upfront_costs": 0.0,
            "cost_observed_at": "2026-08-14T12:00:00Z",
            "cost_source": "Apex checkout observed by researcher",
            "manual_attestations": [
                "no_prohibited_trading_activity_or_cross_account_hedging"
            ],
        },
    )

    assert response.status_code == 201, response.text
    queued = SQLiteJobQueue(runtime / "jobs.sqlite3").get(response.json()["job"]["job_id"])
    assert queued.job_type == "account_assessment_run"
    assert queued.payload["attempt_id"] == "original"
    assert queued.payload["profile_id"] == "apex/eod_50k/funded"
    assert queued.payload["costs"]["evaluation_purchase_price"] == 37.0
    assert queued.hash_locks == {
        "account_profile_hash": resolved.sha256,
        "config_hash": hashlib.sha256(config.read_bytes()).hexdigest(),
        "input_data_hash": "d" * 64,
        "result_bundle_hash": hashlib.sha256(bundle.read_bytes()).hexdigest(),
    }

    frozen_costs = {
        "currency": "USD",
        "evaluation_purchase_price": 19.0,
        "activation_fee": 75.0,
        "other_upfront_costs": 0.0,
        "observed_at": "2026-08-13T12:00:00+00:00",
        "source": "Frozen pre-PnL checkout observation",
        "include_as_replacement_cost": True,
    }
    contract = {
        "schema": "alphaquest.destination-benchmark-contract/v1",
        "declared_at": "2026-08-13T12:01:00+00:00",
        "declared_pre_pnl": True,
        "scientific_validity_required": True,
        "generic_objective_pass_required": False,
        "approval_scope": "exact_primary_profile_only",
        "profiles": [
            {
                "profile_id": resolved.profile.profile_id,
                "profile_version": resolved.profile.version,
                "profile_sha256": resolved.sha256,
                "role": "primary",
                "costs": frozen_costs,
            }
        ],
        "confirmed": True,
    }
    config.write_text(
        yaml.safe_dump(
            {
                "campaign_id": "demo",
                "attempt_id": "original",
                "variant_id": "v01",
                "data": {"canonical_sha256": "d" * 64},
                "destination_benchmark_contract": contract,
                "destination_benchmark_contract_sha256": hashlib.sha256(
                    json.dumps(
                        contract,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode("utf-8")
                ).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    frozen_response = _client(tmp_path).post(
        "/api/campaigns/demo/account-assessments",
        json={
            "attempt_id": "original",
            "variant_id": "v01",
            "profile_id": "apex/eod_50k/funded",
            "profile_version": "2026-03-01",
            "evaluation_purchase_price": 999.0,
            "activation_fee": 999.0,
            "cost_observed_at": "2026-08-14T12:00:00Z",
            "cost_source": "A later value that must not replace the declaration",
            "manual_attestations": [
                "no_prohibited_trading_activity_or_cross_account_hedging"
            ],
        },
    )
    assert frozen_response.status_code == 201, frozen_response.text
    frozen_job = SQLiteJobQueue(runtime / "jobs.sqlite3").get(
        frozen_response.json()["job"]["job_id"]
    )
    assert frozen_job.payload["costs"] == frozen_costs

    undeclared = _client(tmp_path).post(
        "/api/campaigns/demo/account-assessments",
        json={
            "attempt_id": "original",
            "variant_id": "v01",
            "profile_id": "apex/eod_50k/evaluation",
            "profile_version": "2026-03-01",
            "evaluation_purchase_price": 37.0,
            "activation_fee": 85.0,
            "cost_observed_at": "2026-08-14T12:00:00Z",
            "cost_source": "Apex checkout observed by researcher",
        },
    )
    assert undeclared.status_code == 422
    assert "not predeclared" in undeclared.text


def test_browser_queues_declared_strategy_certification_suite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = tmp_path / "runtime"
    manifest = tmp_path / "certification.yaml"
    manifest.write_text("strategy_id: demo\n", encoding="utf-8")
    certification = SimpleNamespace(
        source_files=("src/demo.py",),
        manifest_path=manifest,
        required_tests=("tests/test_demo.py",),
    )
    monkeypatch.setattr(
        "alphaquest.strategy_certification.load_strategy_package_availability",
        lambda _root: SimpleNamespace(active_strategy_ids=frozenset({"demo"})),
    )
    monkeypatch.setattr(
        "alphaquest.strategy_certification.get_strategy_certification",
        lambda *_args, **_kwargs: certification,
    )
    monkeypatch.setattr(
        "alphaquest.strategy_certification.compute_implementation_sha256",
        lambda *_args, **_kwargs: "a" * 64,
    )
    monkeypatch.setattr(
        "alphaquest.studio.api.load_storage_layout",
        lambda _root: SimpleNamespace(studio_runtime_root=runtime),
    )

    response = _client(tmp_path).post(
        "/api/strategies/demo/certify",
        json={"request_id": "browser-request-001"},
    )

    assert response.status_code == 201, response.text
    queued = SQLiteJobQueue(runtime / "jobs.sqlite3").get(response.json()["job"]["job_id"])
    assert queued.job_type == "strategy_certification_run"
    assert queued.payload["required_tests"] == ["tests/test_demo.py"]
    assert queued.hash_locks["implementation_hash"] == "a" * 64
    assert queued.hash_locks["certification_manifest_hash"] == hashlib.sha256(
        manifest.read_bytes()
    ).hexdigest()


def test_event_mechanics_detail_includes_prior_submission_and_strategy_trace(tmp_path: Path) -> None:
    events = pd.DataFrame(
        [
            {
                "trade_id": None,
                "session_date": "2025-07-14",
                "contract": "ESU5",
                "order_id": "VAL",
                "event_index": 10,
                "source_ordinal": 100,
                "timestamp": "2025-07-14T14:30:00Z",
                "transition": "order_submitted",
            },
            {
                "trade_id": 1,
                "session_date": "2025-07-14",
                "contract": "ESU5",
                "order_id": "VAL",
                "event_index": 12,
                "source_ordinal": 102,
                "timestamp": "2025-07-14T14:30:01Z",
                "transition": "entry_filled",
            },
            {
                "trade_id": 1,
                "session_date": "2025-07-14",
                "contract": "ESU5",
                "order_id": "VAL",
                "event_index": 20,
                "source_ordinal": 110,
                "timestamp": "2025-07-14T14:31:00Z",
                "transition": "position_closed",
            },
        ]
    )
    source = tmp_path / "run" / "trade_log.csv"
    source.parent.mkdir()
    pd.DataFrame([{"trade_id": 1, "aoi_side": "VAL", "trigger_kind": "delta_4tick_3m"}]).to_csv(
        source,
        index=False,
    )
    config = tmp_path / "research/campaigns/active/demo/variants/v01/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("campaign_id: demo\n", encoding="utf-8")

    timeline = _mechanics_event_timeline(events, "1")
    context = _mechanics_strategy_context(
        {"source_trade_log": str(source)},
        "1",
        config,
    )

    assert timeline["transition"].tolist() == ["order_submitted", "entry_filled", "position_closed"]
    assert context["aoi_side"] == "VAL"
    assert context["trigger_kind"] == "delta_4tick_3m"


def test_mechanics_review_projects_hash_bound_frozen_parameters(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        yaml.safe_dump(
            {
                "strategy_name": "yush_adaptive_orderflow_range_v3",
                "variant_id": "v03",
                "research_metadata": {
                    "mechanics_review": {
                        "entry_logic_rationale": "A distinct post-AOI confirmation is required."
                    }
                },
                "strategy": {
                    "event": {
                        "module": "yush_adaptive_orderflow_range_v3",
                        "params": {
                            "aoi_level_distance_ticks": 4,
                            "opening_range_seconds": 30,
                            "delta_profile_percentile": 0.9,
                            "target_1_fraction": 0.5,
                        },
                    },
                    "entry": {"module": "yush_adaptive_orderflow_range_v3"},
                    "sl": {"module": "event_atr_bounded_sweep_structural_stop"},
                    "tp": {"module": "event_frozen_midpoint_opposite_edge_scale_out"},
                },
                "core": {
                    "tick_size": 0.25,
                    "point_value": 5.0,
                    "signal_instrument": "ES",
                    "execution_instrument": "MES",
                    "commission_per_contract": 0.51,
                    "entry_slippage_ticks": 1,
                    "position_sizing": {
                        "mode": "risk_percent_net_liq",
                        "risk_pct": 0.004,
                        "min_contracts": 1,
                    },
                },
                "apex_rules": {
                    "force_flatten_time": "15:55:00",
                    "no_overnight_positions": True,
                },
            }
        ),
        encoding="utf-8",
    )

    frozen = _mechanics_frozen_parameters(config)

    assert frozen["strategy_id"] == "yush_adaptive_orderflow_range_v3"
    assert frozen["event_parameters"]["aoi_level_distance_ticks"] == 4
    assert frozen["event_parameters"]["opening_range_seconds"] == 30
    assert frozen["execution"]["signal_instrument"] == "ES"
    assert frozen["execution"]["execution_instrument"] == "MES"
    assert frozen["execution"]["position_sizing"]["risk_pct"] == 0.004
    assert frozen["execution"]["tick_size"] == 0.25
    assert frozen["protocol"]["force_flatten_time"] == "15:55:00"
    assert frozen["specification"]["entry_logic_rationale"].startswith("A distinct")


def _governed_dataset(root: Path) -> None:
    source = root / "administrator-bars.csv"
    # The browser publication fixture must satisfy the same frozen 24-month
    # selection plus terminal 6-month acceptance calendar as a real campaign.
    # A ten-session toy manifest is useful for isolated importer tests, but it
    # must not be able to pass full campaign publication preflight.
    timestamps = pd.DatetimeIndex(
        timestamp
        for session in pd.bdate_range("2023-01-02", "2026-01-16")
        for timestamp in pd.date_range(
            session.replace(hour=9, minute=30),
            periods=18,
            freq="min",
        )
    )
    prices = [5000.0 + index * 0.25 for index in range(len(timestamps))]
    pd.DataFrame(
        {
            "timestamp": timestamps.astype(str),
            "open": prices,
            "high": [item + 1 for item in prices],
            "low": [item - 1 for item in prices],
            "close": [item + 0.25 for item in prices],
            "volume": [1000 + index for index in range(len(timestamps))],
        }
    ).to_csv(source, index=False)
    DatasetImporter(root).import_file(
        source,
        DataImportSpec(
            dataset_id="governed_es_1m",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="single_contract",
            timestamp_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume",
            single_contract_confirmed=True,
        ),
    )


def _brief() -> dict:
    return {
        "research_objectives": {
            "schema": "alphaquest.research-objectives/v1",
            "development_goal": "Reject this candidate unless it survives every frozen research gate.",
            "development_deadline": "2099-12-31",
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
            "abandonment_rules": ["Stop at the first terminal scientific gate failure."],
            "retirement_rules": ["Retire after a frozen live risk boundary is breached."],
            "confirmed": True,
        },
        "title": "Opening auction continuation after completed imbalance",
        "edge_family": "opening_auction_continuation",
        "timeframe": "1m",
        "hypothesis": LONG_RATIONALE,
        "expected_mechanism": LONG_RATIONALE,
        "holding_horizon": "Next bar open through the configured same-session forced flatten.",
        "known_failure_modes": [LONG_RATIONALE],
        "source": {
            "title": "Opening auction price discovery study",
            "authors": ["A. Researcher"],
            "year": 2025,
            "link": "https://example.test/opening-auction",
            "doi": None,
            "relevance": LONG_RATIONALE,
        },
        "economic_edge_fingerprint": {
            "market_behavior": "Completed opening-range expansion persists into the following intraday bars.",
            "causal_mechanism": LONG_RATIONALE,
            "signal_inputs": ["completed opening range", "completed close"],
            "market_context": "ES regular trading hours",
            "holding_period": "Intraday through forced flatten",
        },
    }


def test_bootstrap_is_task_oriented_and_keeps_operational_state_separate(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace"]["ui_runtime"] == "react-fastapi"
    assert payload["workspace"]["candidate_only"] is True
    assert payload["workspace"]["metrics"] == {
        "live_drafts": 0,
        "active_campaigns": 0,
        "review_items": 0,
        "certified_modules": len(get_certified_module_catalog().all()),
    }
    assert payload["jobs"] == []


def test_api_completes_the_seven_gate_draft_without_yaml_or_hash_input(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _governed_dataset(tmp_path)
    client = _client(tmp_path)

    created = client.post(
        "/api/drafts",
        json={"campaign_id": "es_web_publication", "title": "Opening auction continuation", "instrument": "ES"},
    )
    assert created.status_code == 201
    assert len(created.json()["steps"]) == 7

    brief = client.put("/api/drafts/es_web_publication/brief", json=_brief())
    assert brief.status_code == 200, brief.text
    assert brief.json()["steps"][0]["complete"] is True

    context = client.get("/api/drafts/es_web_publication/duplicates")
    assert context.status_code == 200
    duplicate = client.put(
        "/api/drafts/es_web_publication/duplicates",
        json={
            "reviewed_campaign_ids": [item["campaign_id"] for item in context.json()["matches"]],
            "conclusion": "distinct",
            "substantive_distinction": LONG_RATIONALE,
        },
    )
    assert duplicate.status_code == 200, duplicate.text

    dataset = client.post(
        "/api/drafts/es_web_publication/dataset/select",
        json={"dataset_id": "governed_es_1m"},
    )
    assert dataset.status_code == 200, dataset.text

    execution = client.put(
        "/api/drafts/es_web_publication/execution",
        json={
            "roll_policy_confirmed": True,
            "execution": {
                "session_start": "09:30:00",
                "session_end": "16:00:00",
                "latest_entry_time": "15:45:00",
                "flatten_time": "15:55:00",
                "latest_flat_time": "15:56:00",
                "overnight_allowed": False,
                "initial_balance": 150000.0,
                "tick_size": 0.25,
                "point_value": 50.0,
                "tick_value": 12.5,
                "commission_per_contract": 2.5,
                "slippage_ticks": 1.0,
                "contracts": 1,
                "prop_profile": "configured_local_profile",
            },
        },
    )
    assert execution.status_code == 200, execution.text

    recipe = client.put(
        "/api/drafts/es_web_publication/mechanics/recipe",
        json={"recipe": "opening_range_breakout", "confirmed": True},
    )
    assert recipe.status_code == 200, recipe.text

    suggested = client.get("/api/drafts/es_web_publication/variants")
    assert suggested.status_code == 200, suggested.text
    variants = suggested.json()["variants"]
    assert len(variants) == 1
    for item in variants:
        item["confirmed"] = True
    saved = client.put(
        "/api/drafts/es_web_publication/variants",
        json={"variants": variants},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["steps"][5]["complete"] is True

    frozen = client.post(
        "/api/drafts/es_web_publication/freeze",
        json={"confirmed": True},
    )
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["steps"][6]["complete"] is True
    assert frozen.json()["preflight"]["preflight_verdict"] == "PASS"

    published = client.post("/api/drafts/es_web_publication/publish")
    assert published.status_code == 200, published.text
    campaign = client.get("/api/campaigns/es_web_publication")
    assert campaign.status_code == 200, campaign.text
    campaign_payload = campaign.json()
    assert campaign_payload["campaign"]["studio_managed"] is True
    assert len(campaign_payload["stage_matrix"]) == 1
    assert campaign_payload["next_variant"]["eligible"] is False
    assert campaign_payload["protocol"]["hypothesis"] == LONG_RATIONALE
    assert campaign_payload["protocol"]["market_behavior"].startswith(
        "Completed opening-range expansion"
    )
    assert campaign_payload["protocol"]["supporting_sources"][0]["year"] == 2025
    progress = campaign_payload["research_progress"]["campaign"]
    assert progress["variant_id"] == "v01"
    assert progress["current_step"] == 2
    assert progress["total_steps"] == 13
    assert progress["current_stage_label"] == "Mechanics evidence"
    assert [item["id"] for item in progress["stages"]][3:] == [
        "limited_core_grid_test",
        "limited_monkey_test",
        "walk_forward_analysis",
        "wfa_oos_monkey_test",
        "wfa_oos_monte_carlo",
        "simulated_incubation_core",
        "simulated_incubation_monkey",
        "acceptance_oos_test",
        "account_suitability",
        "candidate_review",
    ]
    bootstrap_campaign = next(
        item
        for item in client.get("/api/bootstrap").json()["campaigns"]
        if item["campaign_id"] == "es_web_publication"
    )
    assert bootstrap_campaign["research_progress"]["campaign"]["current_stage_label"] == (
        "Mechanics evidence"
    )
    mechanics = campaign_payload["mechanics"]
    assert mechanics["read_only"] is True
    assert mechanics["variant_ids"] == ["v01"]
    original = next(
        item for item in mechanics["attempts"] if item["attempt_id"] == "original"
    )
    assert original["target_variant_id"] == "v01"
    assert original["variants"][0]["rules"]["forced_flatten"]["flatten_time"] == "15:55:00"
    assert original["variants"][0]["config_sha256"]

    failed_result = (
        tmp_path
        / "research/evidence/runs/es_web_publication/v01/ES/run1/reporting_v2/result_bundle_v2.json"
    )
    failed_result.parent.mkdir(parents=True)
    failed_result.write_text(
        json.dumps({"campaign_id": "es_web_publication", "variant_id": "v01", "verdict": "FAIL"}),
        encoding="utf-8",
    )
    (failed_result.parent.parent / "source_config.yaml").write_bytes(
        (
            tmp_path
            / "research/campaigns/active/es_web_publication/variants/v01/config.yaml"
        ).read_bytes()
    )
    monkeypatch.setattr(
        "alphaquest.studio.sequential_variants.inspect_historical_validation_approval",
        lambda _cfg, _path: {"status": "APPROVED_FOR_TESTING"},
    )
    proposal = client.get("/api/campaigns/es_web_publication/next-variant")
    assert proposal.status_code == 200, proposal.text
    assert proposal.json()["next_variant_id"] == "v02"
    appended = client.post(
        "/api/campaigns/es_web_publication/next-variant",
        json={
            "variant": proposal.json()["variant"],
            "failure_analysis": LONG_RATIONALE,
            "created_by": "mechanics-reviewer",
        },
    )
    assert appended.status_code == 201, appended.text
    assert appended.json()["research_verdict"] == "NEEDS MANUAL REVIEW"
    campaign_root = tmp_path / "research/campaigns/active/es_web_publication"
    assert (campaign_root / "variants/v02/config.yaml").is_file()
    campaign_definition = yaml.safe_load((campaign_root / "campaign.yaml").read_text(encoding="utf-8"))
    assert campaign_definition["variants"] == ["v01", "v02"]
    assert campaign_definition["sequential_variant_history"][0]["predecessor_verdict"] == "FAIL"


def test_api_returns_field_addressable_validation_and_protects_frozen_drafts(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post(
        "/api/drafts",
        json={"campaign_id": "es_invalid", "title": "Invalid fixture", "instrument": "ES"},
    )

    response = client.put("/api/drafts/es_invalid/brief", json={})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert {item["loc"][-1] for item in detail} >= {"title", "hypothesis", "source"}


def test_raw_upload_inspection_never_accepts_a_server_side_path(tmp_path: Path) -> None:
    client = _client(tmp_path)
    body = b"timestamp,open,high,low,close,volume\n2026-01-05 09:30,1,2,0,1.5,10\n"

    response = client.post(
        "/api/uploads/inspect?filename=../../bars.csv",
        content=body,
        headers={"content-type": "application/octet-stream"},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["filename"] == "bars.csv"
    assert payload["columns"] == ["timestamp", "open", "high", "low", "close", "volume"]
    assert Path(payload["upload_token"]).name == payload["upload_token"]
    assert payload["discovery"]["timestamp_candidates"][0]["column"] == "timestamp"


def test_data_manager_exposes_governed_manifest_and_comparison(tmp_path: Path) -> None:
    _governed_dataset(tmp_path)
    source = tmp_path / "comparison-bars.csv"
    timestamps = pd.date_range("2026-02-02 09:30:00", periods=180, freq="min")
    pd.DataFrame(
        {
            "timestamp": timestamps.astype(str),
            "open": 5100.0,
            "high": 5101.0,
            "low": 5099.0,
            "close": 5100.25,
            "volume": 100,
        }
    ).to_csv(source, index=False)
    DatasetImporter(tmp_path).import_file(
        source,
        DataImportSpec(
            dataset_id="governed_es_comparison",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="single_contract",
            timestamp_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume",
            single_contract_confirmed=True,
        ),
    )
    client = _client(tmp_path)

    detail = client.get("/api/datasets/governed_es_1m")
    templates = client.get("/api/data/session-templates")
    comparison = client.get(
        "/api/datasets/compare/governed_es_1m/governed_es_comparison"
    )

    assert detail.status_code == 200, detail.text
    assert detail.json()["quality"]["verdict"] == "PASS"
    assert len(detail.json()["manifest_sha256"]) == 64
    assert templates.json()["templates"][0]["template_id"] == "cme_us_equity_rth"
    assert comparison.json()["comparable"] is True
    assert comparison.json()["comparison"]["canonical_sha256"]["matches"] is False


def test_ai_suggestion_persists_hash_only_provenance_on_the_selected_draft(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path)
    client.post(
        "/api/drafts",
        json={"campaign_id": "es_ai_notes", "title": "AI notes", "instrument": "ES"},
    )
    save_settings(
        StudioSettings(
            assistant_mode="legacy_openai_api",
            openai_model="pinned-model",
        ),
        project_root=tmp_path,
    )

    def suggest(_self, notes: str, *, source_title: str, instrument: str):
        assert notes == "Selected prose only"
        assert source_title == "Research paper"
        assert instrument == "ES"
        return (
            ResearchBriefSuggestion(
                hypothesis="A sufficiently falsifiable hypothesis generated from selected research prose.",
                expected_mechanism="A sufficiently detailed causal mechanism generated from selected research prose.",
                expected_holding_horizon="Intraday",
                known_failure_modes=["The effect may fail outside the declared session."],
                lookahead_risks=["Confirm every rolling input is lagged."],
                missing_questions=[],
                economic_edge_fingerprint={
                    "market_behavior": "Completed bars retain a predeclared directional response.",
                    "causal_mechanism": "Participants adjust inventory after a completed observable imbalance.",
                    "signal_inputs": "completed close and prior rolling mean",
                    "market_context": "ES regular trading session",
                    "holding_period": "intraday",
                },
            ),
            AIDraftProvenance(
                model="pinned-model",
                prompt_sha256="a" * 64,
                source_sha256="b" * 64,
                response_sha256="c" * 64,
                generated_at="2026-07-16T12:00:00+00:00",
            ),
        )

    monkeypatch.setattr("alphaquest.studio.ai.OpenAIResearchDraftAdapter.suggest", suggest)
    response = client.post(
        "/api/ai/suggest",
        json={
            "campaign_id": "es_ai_notes",
            "selected_text": "Selected prose only",
            "source_title": "Research paper",
            "instrument": "ES",
        },
    )

    assert response.status_code == 200, response.text
    state = client.get("/api/drafts/es_ai_notes").json()["state"]
    assert state["ai_provenance_events"][0]["source_sha256"] == "b" * 64
    serialized = str(state)
    assert "Selected prose only" not in serialized
    assert "sufficiently falsifiable" not in serialized


def test_default_subscription_mode_refuses_metered_ai_endpoint(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post(
        "/api/drafts",
        json={"campaign_id": "es_no_paid_api", "title": "No paid API", "instrument": "ES"},
    )

    response = client.post(
        "/api/ai/suggest",
        json={
            "campaign_id": "es_no_paid_api",
            "selected_text": "Selected prose only",
            "source_title": "Research paper",
            "instrument": "ES",
        },
    )

    assert response.status_code == 422
    assert "legacy_openai_api" in response.json()["error"]["message"]


def test_pdf_pages_are_selected_and_extracted_locally_without_provider_access(
    tmp_path: Path,
    monkeypatch,
) -> None:
    PdfWriter = pytest.importorskip("pypdf").PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    raw = BytesIO()
    writer.write(raw)
    client = _client(tmp_path)

    inspected = client.post(
        "/api/ai/pdf/inspect?filename=paper.pdf",
        content=raw.getvalue(),
        headers={"content-type": "application/pdf"},
    )

    assert inspected.status_code == 201, inspected.text
    payload = inspected.json()
    assert payload["local_only"] is True
    assert payload["pages"][0]["page_number"] == 1
    monkeypatch.setattr(
        "alphaquest.studio.ai.extract_pdf_text",
        lambda _path, page_indexes: "Only locally selected page text" if page_indexes == [0] else "",
    )
    extracted = client.post(
        "/api/ai/pdf/extract",
        json={"upload_token": payload["upload_token"], "page_indexes": [0]},
    )
    assert extracted.status_code == 200, extracted.text
    assert extracted.json() == {
        "selected_text": "Only locally selected page text",
        "characters": 31,
        "page_indexes": [0],
        "local_only": True,
    }


def _indexed_bundle_fixture(
    tmp_path: Path,
    *,
    index_verdict: str = "PASS",
    bundle_verdict: str = "FAIL",
):
    campaign_root = tmp_path / "research/campaigns/active/demo"
    config_path = campaign_root / "variants/v01/config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "campaign_id": "demo",
                "variant_id": "v01",
                "test_run_id": "run1",
                "strategy": {"entry": {"params": {"lookback": 5}}},
                "core_grid": {
                    "parameters": {"entry.params.lookback": [5, 10]},
                    "retain_iteration_reports": False,
                },
            }
        ),
        encoding="utf-8",
    )
    (campaign_root / "campaign.yaml").write_text(
        yaml.safe_dump(
            {
                "campaign_id": "demo",
                "title": "Authoritative result presentation",
                "variants": ["v01", "v02", "v03", "v04", "v05"],
            }
        ),
        encoding="utf-8",
    )
    reporting = tmp_path / "research/evidence/runs/demo/v01/ES/run1/reporting_v2"
    core_grid = reporting.parent / "limited_core_grid_test/core_grid_results.csv"
    core_grid.parent.mkdir(parents=True)
    grid_results = pd.DataFrame(
        [
            {
                "run_id": 1,
                "entry.params.lookback": 5,
                "total_trades": 4,
                "net_profit": -50.0,
                "profit_factor": 0.8,
                "max_drawdown": 100.0,
                "mar": -0.5,
            },
            {
                "run_id": 2,
                "entry.params.lookback": 10,
                "total_trades": 3,
                "net_profit": 25.0,
                "profit_factor": 1.1,
                "max_drawdown": 75.0,
                "mar": 0.3,
            },
        ]
    )
    grid_results.to_csv(core_grid, index=False)
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "direction": "long",
                "entry_timestamp": "2025-01-02T14:30:00Z",
                "exit_timestamp": "2025-01-02T14:35:00Z",
                "net_pnl": 100.0 if bundle_verdict == "PASS" else -50.0,
                "r_multiple": 2.0 if bundle_verdict == "PASS" else -1.0,
                "commission": 5.0,
                "slippage_cost": 12.5,
                "apex_rule_violation": False,
                "position_flat_before_deadline": True,
            }
        ]
    )
    bundle = ResultBundleBuilder().build_and_write(
        trades,
        reporting,
        campaign_id="demo",
        variant_id="v01",
        run_id="run1",
        verdict=bundle_verdict,
        scientific_validity_verdict="PASS",
        stage_criteria=[
            {
                "stage": "limited_core_grid_test",
                "metric": "profit_factor",
                "operator": ">=",
                "threshold": {"value": 1.2, "reason": None},
                "actual": {"value": 1.3 if bundle_verdict == "PASS" else 0.8, "reason": None},
                "result": bundle_verdict,
                "reason": (
                    "actual 1.3 met required 1.2"
                    if bundle_verdict == "PASS"
                    else "actual 0.8 was below required 1.2"
                ),
                "evidence_path": "limited_core_grid_test/stage_result.json",
                "decision_role": "generic_objective",
            },
            {
                "stage": "limited_core_grid_test",
                "metric": "summary.percentage_profitable_iterations",
                "operator": ">=",
                "threshold": {"value": 0.7, "reason": None},
                "actual": {"value": 0.8, "reason": None},
                "result": "PASS",
                "reason": "parameter neighborhood evidence passed",
                "evidence_path": "limited_core_grid_test/stage_result.json",
                "decision_role": "scientific_validity",
            },
        ],
        initial_balance=50_000,
        prop_rule_outcome="PASS",
        forced_flatten_compliance=True,
        parameter_neighbors=grid_results,
    )
    bundle_path = reporting / "result_bundle_v2.json"
    (campaign_root / "results_index.yaml").write_text(
        yaml.safe_dump(
            {
                "runs": [
                    {
                        "variant_id": "v01",
                        "test_run_id": "run1",
                        "research_verdict": index_verdict,
                        "passed": index_verdict == "PASS",
                        "failed_stage": None,
                        "updated_at": "2026-07-16T00:00:00+00:00",
                        "result_bundle_path": str(bundle_path),
                        "output_dir": str(reporting.parent),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return config_path, bundle_path, bundle


def test_campaign_result_rejects_schema_valid_bundle_without_complete_finalization(tmp_path: Path) -> None:
    _indexed_bundle_fixture(tmp_path)

    payload = _client(tmp_path).get("/api/campaigns/demo").json()

    row = next(item for item in payload["stage_matrix"] if item["variant"] == "v01")
    result = payload["latest_results"]["v01"]
    assert row["research verdict"] == "NEEDS MANUAL REVIEW"
    assert row["first failed or unresolved gate"] == "result_bundle_v2_finalization"
    assert result["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert result["metrics"] == {}
    assert result["stage_criteria"] == []
    assert result["finalization"]["valid"] is False
    assert any("finalization manifest" in item for item in result["finalization"]["errors"])
    progress = payload["research_progress"]["campaign"]
    assert progress["current_step"] == 4
    assert progress["current_stage_label"] == "Result integrity review"
    assert progress["stages"][3]["status"] == "blocked"
    assert progress["stages"][-1]["status"] == "locked"


def test_campaign_and_candidate_views_use_validated_bundle_not_index_verdict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path, bundle_path, bundle = _indexed_bundle_fixture(tmp_path, index_verdict="PASS")

    def valid_inspection(path, *, config_path=None):
        assert Path(path).resolve() == bundle_path.resolve()
        return {
            "valid": True,
            "errors": [],
            "bundle": bundle,
            "manifest": {"source_config": str(config_path or config_path_fixture)},
        }

    config_path_fixture = config_path
    monkeypatch.setattr("alphaquest.studio.api.inspect_finalized_result", valid_inspection)
    client = _client(tmp_path)

    campaign = client.get("/api/campaigns/demo").json()
    row = next(item for item in campaign["stage_matrix"] if item["variant"] == "v01")
    result = campaign["latest_results"]["v01"]
    assert row["research verdict"] == "FAIL"
    assert row["operational state"] == "SUCCEEDED"
    assert row["first failed or unresolved gate"] == "limited_core_grid_test"
    assert result["research_verdict"] == "FAIL"
    assert result["source_index_verdict"] == "PASS"
    assert result["metrics"]["total_trades"]["value"] == 1
    assert result["stage_criteria"][0]["actual"]["value"] == 0.8
    assert result["finalization"] == {"valid": True, "errors": []}
    assert result["core_grid_inspection"] == {
        "available": True,
        "reason": None,
        "default_run_id": 1,
        "declared_default_parameters": {"entry.params.lookback": 5},
        "parameter_columns": ["entry.params.lookback"],
        "iteration_count": 2,
        "iteration_reports_retained": False,
        "metrics_source": "limited_core_grid_test/core_grid_results.csv",
        "default_metrics_scope": "declared_default_fixed_config",
    }
    progress = campaign["research_progress"]["campaign"]
    assert progress["current_step"] == 12
    assert progress["current_stage_label"] == "Destination account suitability"
    assert progress["stages"][0]["status"] == "complete"
    assert progress["stages"][3]["status"] == "complete"
    assert progress["stages"][4]["status"] == "complete"
    assert progress["stages"][-1]["status"] == "locked"

    assert not any(
        item["campaign_id"] == "demo" for item in client.get("/api/reviews").json()["candidate"]
    )


def test_result_artifact_download_is_allowlisted_and_hash_verified(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path, bundle_path, bundle = _indexed_bundle_fixture(tmp_path)
    index_path = tmp_path / "research/campaigns/active/demo/results_index.yaml"
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    index["runs"][0].update(
        {
            "attempt_id": "original",
            "finalization_state": "COMPLETE",
        }
    )
    index_path.write_text(yaml.safe_dump(index), encoding="utf-8")

    def valid_inspection(path, *, config_path=None):
        return {
            "valid": True,
            "errors": [],
            "bundle": bundle,
            "manifest": {"source_config": str(config_path or config_path_fixture)},
        }

    config_path_fixture = config_path
    monkeypatch.setattr("alphaquest.studio.api.inspect_finalized_result", valid_inspection)
    client = _client(tmp_path)

    response = client.get(
        "/api/campaigns/demo/results/original/v01/artifacts/trade_list"
    )
    missing = client.get(
        "/api/campaigns/demo/results/original/v01/artifacts/not_declared"
    )
    archive = client.get(
        "/api/campaigns/demo/results/original/v01/report.zip"
    )

    assert response.status_code == 200, response.text
    assert "trade_id" in response.text
    assert response.headers["content-type"].startswith("text/csv")
    assert missing.status_code == 404
    assert archive.status_code == 200, archive.text
    assert archive.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(BytesIO(archive.content)) as report:
        names = set(report.namelist())
        assert "result_bundle_v2.json" in names
        assert "trade_list.csv" in names
        assert "performance_statistics.csv" in names


def test_campaign_result_suppresses_bundle_values_when_finalization_hashes_drift(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path, bundle_path, bundle = _indexed_bundle_fixture(tmp_path)

    def drifted_inspection(path, *, config_path=None):
        assert Path(path).resolve() == bundle_path.resolve()
        return {
            "valid": False,
            "errors": ["hashed reporting artifact drifted: result_bundle_v2.json"],
            "bundle": bundle,
            "manifest": {"source_config": str(config_path or config_path_fixture)},
        }

    config_path_fixture = config_path
    monkeypatch.setattr("alphaquest.studio.api.inspect_finalized_result", drifted_inspection)

    payload = _client(tmp_path).get("/api/campaigns/demo").json()
    result = payload["latest_results"]["v01"]

    assert result["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert result["metrics"] == {}
    assert result["stage_criteria"] == []
    assert result["finalization"]["valid"] is False
    assert result["finalization"]["errors"] == [
        "hashed reporting artifact drifted: result_bundle_v2.json"
    ]


def test_candidate_queue_contains_only_unreviewed_valid_terminal_passes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path, bundle_path, bundle = _indexed_bundle_fixture(
        tmp_path,
        index_verdict="FAIL",
        bundle_verdict="PASS",
    )

    def valid_finalization(path, *, config_path=None):
        assert Path(path).resolve() == bundle_path.resolve()
        return {
            "valid": True,
            "errors": [],
            "bundle": bundle,
            "manifest": {"source_config": str(config_path or config_path_fixture)},
        }

    config_path_fixture = config_path
    monkeypatch.setattr("alphaquest.studio.api.inspect_finalized_result", valid_finalization)
    client = _client(tmp_path)

    campaign_progress = client.get("/api/campaigns/demo").json()["research_progress"]["campaign"]
    assert campaign_progress["current_step"] == 13
    assert campaign_progress["current_stage_label"] == "Independent candidate review"
    assert all(
        item["status"] == "complete"
        for item in campaign_progress["stages"][:-2]
    )
    assert campaign_progress["stages"][-2]["status"] == "not_applicable"
    assert campaign_progress["stages"][-1]["status"] == "current"

    candidates = client.get("/api/reviews").json()["candidate"]
    candidate = next(item for item in candidates if item["campaign_id"] == "demo")
    assert candidate["verdict"] == "PASS"
    assert candidate["review_status"] == "required"
    assert candidate["review_blockers"] == []
    assert candidate["metrics"]["total_trades"]["value"] == 1

    review_path = bundle_path.parent / "candidate_review.json"
    review_path.write_text("{}\n", encoding="utf-8")

    def stale_review(self, **kwargs):
        return {
            "valid": False,
            "lifecycle_state": "review_required",
            "errors": ["result bundle hash is stale or mismatched"],
        }

    monkeypatch.setattr(
        "alphaquest.studio.candidate_review.CandidateReviewService.inspect",
        stale_review,
    )
    candidates = client.get("/api/reviews").json()["candidate"]
    candidate = next(item for item in candidates if item["campaign_id"] == "demo")
    assert candidate["review_status"] == "invalid_or_stale"
    assert candidate["review_blockers"] == [
        "Existing candidate review is invalid or stale: result bundle hash is stale or mismatched"
    ]

    def valid_terminal_review(self, **kwargs):
        return {"valid": True, "lifecycle_state": "candidate", "errors": []}

    monkeypatch.setattr(
        "alphaquest.studio.candidate_review.CandidateReviewService.inspect",
        valid_terminal_review,
    )
    assert not any(
        item["campaign_id"] == "demo" for item in client.get("/api/reviews").json()["candidate"]
    )
